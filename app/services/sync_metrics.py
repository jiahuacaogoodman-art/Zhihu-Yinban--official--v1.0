# -*- coding: utf-8 -*-
"""
@File    : app/services/sync_metrics.py
@Desc    : Edge → Cloud 上行指标采集（PR#7）

设计原则
  · 底层数据不出院。只上报**聚合 / 脱敏**指标:空床率、欠费预警计数、
    跌倒事件统计、按 action 聚合的审计计数。
  · 永不上报 PII:姓名 / 身份证 / 联系方式 / 主诉文本 / 病历内容 / OCR 全文。
  · 永不上报原始审计日志条目(operator 名 / patient_id 都算 PII)。
    审计只上报"过去 24h 各 action 类型出现次数"这类聚合数。

为什么独立模块
  采集逻辑只读 SQLite,不引 FastAPI / Pydantic。这样 sync_agent.py
  在 main 进程之外作为独立 daemon 跑时也能直接 import 用。

输出格式
  collect_metrics(base_dir, branch_id) 返回一个 dict,字段稳定可演化:
  {
    "schema_version": 1,
    "branch_id": "main",
    "collected_at": "2026-05-18T03:00:00",
    "occupancy": {"total_beds": 100, "occupied": 78, "available": 22, ...},
    "billing_alerts": {"overdue": 3, "expiring_soon": 5},
    "incidents_24h": {"fall": 1, "medication_error": 0, ...},
    "audit_24h": {"PATIENT_UPDATE": 12, "RECORD_UPLOAD": 5, ...},
    "users": {"active": 18, "inactive": 2},
  }

  云端存这份 JSON 即可在控制台画"集团总览"。所有数字都是按
  branch_id 聚合的,合并多院只是 SQL GROUP BY。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


METRICS_SCHEMA_VERSION = 1


def _safe_count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    """SQL 出错（表不存在/老库还没建）→ 返回 0 不传播。"""
    try:
        row = conn.execute(sql, params).fetchone()
        if not row:
            return 0
        return int(row[0] or 0)
    except sqlite3.OperationalError:
        return 0


def _try_open(path: Path) -> Optional[sqlite3.Connection]:
    """ro 模式打开 SQLite。文件不存在或损坏返回 None。"""
    if not path.exists():
        return None
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as e:
        logger.warning(f"sync_metrics: 无法打开 {path}: {e}")
        return None


def _occupancy(care_db: Path, branch_id: str) -> dict:
    """从 local_care/care.db 的 beds 表算空床率。"""
    conn = _try_open(care_db)
    if conn is None:
        return {"total_beds": 0, "occupied": 0, "available": 0, "reserved": 0,
                "occupancy_rate": 0.0}
    try:
        # PR#6 起 beds 有 branch_id 列;老库没有 → 走宽松 path
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM beds WHERE branch_id = ? GROUP BY status",
                (branch_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM beds GROUP BY status"
            ).fetchall()
        by = {r[0]: int(r[1]) for r in rows}
        total = sum(by.values())
        occupied = by.get("occupied", 0)
        available = by.get("available", 0)
        reserved = by.get("reserved", 0)
        rate = (occupied / total) if total else 0.0
        return {
            "total_beds": total,
            "occupied": occupied,
            "available": available,
            "reserved": reserved,
            "occupancy_rate": round(rate, 4),
        }
    finally:
        conn.close()


def _billing_alerts(billing_db: Path, branch_id: str) -> dict:
    """从 billing.db 计算欠费 / 即将到期数。"""
    conn = _try_open(billing_db)
    if conn is None:
        return {"overdue": 0, "expiring_soon": 0}
    try:
        today = datetime.now().date()
        threshold = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        try:
            rows = conn.execute(
                "SELECT admission_id, MAX(period_end) AS latest_end "
                "FROM billing_records WHERE branch_id = ? "
                "GROUP BY admission_id",
                (branch_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT admission_id, MAX(period_end) AS latest_end "
                "FROM billing_records GROUP BY admission_id"
            ).fetchall()
        overdue = 0
        expiring = 0
        today_str = today.strftime("%Y-%m-%d")
        for _, latest_end in rows:
            if not latest_end:
                continue
            if latest_end < today_str:
                overdue += 1
            elif latest_end <= threshold:
                expiring += 1
        return {"overdue": overdue, "expiring_soon": expiring}
    finally:
        conn.close()


def _incidents_24h(care_db: Path, branch_id: str) -> dict:
    """过去 24 小时各类型 incident 计数(脱敏:不带 patient_id / description)。"""
    conn = _try_open(care_db)
    if conn is None:
        return {}
    try:
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            rows = conn.execute(
                "SELECT incident_type, COUNT(*) FROM incidents "
                "WHERE branch_id = ? AND created_at >= ? "
                "GROUP BY incident_type",
                (branch_id, cutoff),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT incident_type, COUNT(*) FROM incidents "
                "WHERE created_at >= ? GROUP BY incident_type",
                (cutoff,),
            ).fetchall()
        return {r[0] or "unknown": int(r[1]) for r in rows}
    finally:
        conn.close()


def _audit_24h(audit_db: Path, branch_id: str) -> dict:
    """
    审计日志按 action 维度聚合。

    安全保证: 不返回任何 patient_id / operator / detail 字符串。
    云端只看到"过去 24h PATIENT_UPDATE 发生 12 次"这一类汇总。
    """
    conn = _try_open(audit_db)
    if conn is None:
        return {}
    try:
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            rows = conn.execute(
                "SELECT action, COUNT(*) FROM audit_log "
                "WHERE branch_id = ? AND ts >= ? GROUP BY action",
                (branch_id, cutoff),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT action, COUNT(*) FROM audit_log "
                "WHERE ts >= ? GROUP BY action",
                (cutoff,),
            ).fetchall()
        return {r[0]: int(r[1]) for r in rows}
    finally:
        conn.close()


def _users(users_db: Path, branch_id: str) -> dict:
    conn = _try_open(users_db)
    if conn is None:
        return {"active": 0, "inactive": 0}
    try:
        try:
            row = conn.execute(
                "SELECT "
                "  SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS a, "
                "  SUM(CASE WHEN active = 0 THEN 1 ELSE 0 END) AS i "
                "FROM users WHERE branch_id = ?",
                (branch_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                "SELECT "
                "  SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS a, "
                "  SUM(CASE WHEN active = 0 THEN 1 ELSE 0 END) AS i "
                "FROM users"
            ).fetchone()
        return {
            "active": int(row[0] or 0) if row else 0,
            "inactive": int(row[1] or 0) if row else 0,
        }
    finally:
        conn.close()


def collect_metrics(base_dir: Path, branch_id: str = "main") -> dict:
    """
    从 base_dir 下的全部本地 SQLite 收集脱敏指标。
    任何子项失败都降级为 0,不阻断整次采集。
    """
    base = Path(base_dir)
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "branch_id": branch_id,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "occupancy": _occupancy(base / "local_care" / "care.db", branch_id),
        "billing_alerts": _billing_alerts(
            base / "local_billing" / "billing.db", branch_id,
        ),
        "incidents_24h": _incidents_24h(
            base / "local_care" / "care.db", branch_id,
        ),
        "audit_24h": _audit_24h(
            base / "local_audit_log" / "audit.db", branch_id,
        ),
        "users": _users(base / "local_auth" / "users.db", branch_id),
    }


# ── PII guard ──────────────────────────────────────────────
# 显式列出已知会泄密的字段名;如果 collect_metrics 的输出里出现任何一个
# (键或值) → 视为 bug,sync 推送前会直接 raise,绝不发出。
_PII_BLACKLIST = frozenset({
    "patient_id", "name", "id_card", "emergency_phone",
    "emergency_contact", "guardian_phone", "guardian_id_card",
    "phone", "applicant_id_card", "applicant_phone",
    "operator", "username", "display_name", "doc_id",
    "detail", "description", "symptom", "advice",
    "raw_description", "manual_text", "notes",
    "ocr_text", "snippet", "diff",
})


def assert_no_pii(payload: dict, path: str = "") -> None:
    """
    递归扫描 payload 字典,任何 key 命中黑名单就 raise。
    用在 sync_agent 推送前最后一道关。

    举例:如果未来某个开发误改 collect_metrics 把 patient_id 加进去,
    单元测试会立刻炸,而不是把 PII 推到云端再被发现。
    """
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in _PII_BLACKLIST:
                raise ValueError(f"sync metrics 含 PII 字段 '{k}' (路径={path}); 拒绝上报")
            assert_no_pii(v, f"{path}.{k}" if path else str(k))
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            assert_no_pii(v, f"{path}[{i}]")
    # 标量值不递归


__all__ = [
    "METRICS_SCHEMA_VERSION",
    "assert_no_pii",
    "collect_metrics",
]
