# -*- coding: utf-8 -*-
"""
@File    : app/services/billing_store.py
@Desc    : 缴费管理数据持久化层 (SQLite WAL)

覆盖模块：
  - 收费标准 (fee_standards)
  - 缴费记录 (billing_records)
  - 续费逻辑（基于上次截止日期自动延期）
  - 到期状态计算（正常/即将到期/已欠费）

设计决策：
  - 独立 SQLite 数据库文件 local_billing/billing.db
  - WAL 模式支持多线程并发读写
  - 统一使用 threading.Lock 保证进程内线程安全
  - 所有时间字段用 ISO 格式字符串
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from app.services.branching import ensure_branching_columns


class BillingStore:
    """缴费管理数据统一存储层。"""

    _CREATE_SQL = """
        -- 收费标准
        CREATE TABLE IF NOT EXISTS fee_standards (
            standard_id     TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            category        TEXT NOT NULL DEFAULT 'care',
            care_level_key  TEXT NOT NULL DEFAULT '',
            room_type       TEXT NOT NULL DEFAULT '',
            unit_price      REAL NOT NULL DEFAULT 0,
            billing_cycle   TEXT NOT NULL DEFAULT 'monthly',
            description     TEXT NOT NULL DEFAULT '',
            is_required     INTEGER NOT NULL DEFAULT 1,
            is_active       INTEGER NOT NULL DEFAULT 1,
            sort_order      INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            -- PR#6: 多租户 / 乐观锁 schema 准备(routers 暂不读)
            branch_id       TEXT NOT NULL DEFAULT 'main',
            version_id      INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_fee_standards_category ON fee_standards(category);
        CREATE INDEX IF NOT EXISTS idx_fee_standards_active ON fee_standards(is_active);
        CREATE INDEX IF NOT EXISTS idx_fee_standards_level ON fee_standards(care_level_key);

        -- 缴费记录
        CREATE TABLE IF NOT EXISTS billing_records (
            record_id           TEXT PRIMARY KEY,
            admission_id        TEXT NOT NULL,
            patient_name        TEXT NOT NULL DEFAULT '',
            fee_standard_id     TEXT NOT NULL DEFAULT '',
            fee_standard_name   TEXT NOT NULL DEFAULT '',
            fee_category        TEXT NOT NULL DEFAULT 'care',
            amount              REAL NOT NULL,
            billing_cycle       TEXT NOT NULL DEFAULT 'monthly',
            period_start        TEXT NOT NULL,
            period_end          TEXT NOT NULL,
            payment_method      TEXT NOT NULL DEFAULT 'cash',
            receipt_number      TEXT NOT NULL DEFAULT '',
            payer               TEXT NOT NULL DEFAULT '',
            paid_at             TEXT NOT NULL,
            notes               TEXT NOT NULL DEFAULT '',
            created_at          TEXT NOT NULL,
            -- PR#6: 多租户 / 乐观锁 schema 准备(routers 暂不读)
            branch_id           TEXT NOT NULL DEFAULT 'main',
            version_id          INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_billing_admission ON billing_records(admission_id);
        CREATE INDEX IF NOT EXISTS idx_billing_category ON billing_records(fee_category);
        CREATE INDEX IF NOT EXISTS idx_billing_period_end ON billing_records(period_end);
        CREATE INDEX IF NOT EXISTS idx_billing_paid_at ON billing_records(paid_at);
    """

    _SCHEMA_VERSION: int = 1

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self._CREATE_SQL)
            # PR#6: 给老库加 branch_id (+ version_id) 列;新库的 _CREATE_SQL
            # 里也声明了同名列,这里是空操作。
            ensure_branching_columns(
                conn,
                full=("fee_standards", "billing_records"),
            )
        logger.debug(f"BillingStore 初始化完成: {self._path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _gen_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    # ================================================================
    # 收费标准 CRUD
    # ================================================================

    def create_fee_standard(self, data: dict) -> dict:
        standard_id = self._gen_id("fs")
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO fee_standards (standard_id, name, category, care_level_key, "
                "room_type, unit_price, billing_cycle, description, is_required, is_active, "
                "sort_order, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (standard_id, data["name"], data.get("category") or "care",
                 data.get("care_level_key") or "", data.get("room_type") or "",
                 data["unit_price"], data.get("billing_cycle") or "monthly",
                 data.get("description") or "",
                 1 if data.get("is_required", True) else 0,
                 1 if data.get("is_active", True) else 0,
                 data.get("sort_order") or 0, now, now),
            )
            conn.execute("COMMIT")
        return self.get_fee_standard(standard_id)

    def get_fee_standard(self, standard_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM fee_standards WHERE standard_id = ?", (standard_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_required"] = bool(d.get("is_required", 1))
        d["is_active"] = bool(d.get("is_active", 1))
        return d

    def list_fee_standards(self, category: Optional[str] = None,
                           care_level_key: Optional[str] = None,
                           active_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM fee_standards WHERE 1=1"
        params: list = []
        if active_only:
            sql += " AND is_active = 1"
        if category:
            sql += " AND category = ?"
            params.append(category)
        if care_level_key:
            sql += " AND (care_level_key = ? OR care_level_key = '')"
            params.append(care_level_key)
        sql += " ORDER BY sort_order, category, name"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["is_required"] = bool(d.get("is_required", 1))
            d["is_active"] = bool(d.get("is_active", 1))
            result.append(d)
        return result

    def update_fee_standard(self, standard_id: str, data: dict) -> Optional[dict]:
        fields = []
        params = []
        for key in ("name", "category", "care_level_key", "room_type", "unit_price",
                    "billing_cycle", "description", "sort_order"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = ?")
                params.append(data[key])
        # bool 字段特殊处理
        if "is_required" in data and data["is_required"] is not None:
            fields.append("is_required = ?")
            params.append(1 if data["is_required"] else 0)
        if "is_active" in data and data["is_active"] is not None:
            fields.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)
        if not fields:
            return self.get_fee_standard(standard_id)
        fields.append("updated_at = ?")
        params.append(self._now())
        params.append(standard_id)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                f"UPDATE fee_standards SET {', '.join(fields)} WHERE standard_id = ?", params
            )
            if cur.rowcount == 0:
                conn.execute("ROLLBACK")
                return None
            conn.execute("COMMIT")
        return self.get_fee_standard(standard_id)

    def delete_fee_standard(self, standard_id: str) -> bool:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "DELETE FROM fee_standards WHERE standard_id = ?", (standard_id,)
            )
            if cur.rowcount == 0:
                conn.execute("ROLLBACK")
                return False
            conn.execute("COMMIT")
        return True

    # ================================================================
    # 缴费记录 CRUD
    # ================================================================

    def create_billing_record(self, data: dict) -> dict:
        record_id = self._gen_id("bill")
        now = self._now()
        # 如果关联了收费标准，获取标准名称
        fee_standard_name = ""
        if data.get("fee_standard_id"):
            std = self.get_fee_standard(data["fee_standard_id"])
            if std:
                fee_standard_name = std["name"]
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO billing_records (record_id, admission_id, patient_name, "
                "fee_standard_id, fee_standard_name, fee_category, amount, billing_cycle, "
                "period_start, period_end, payment_method, receipt_number, payer, "
                "paid_at, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_id, data["admission_id"], data.get("patient_name") or "",
                 data.get("fee_standard_id") or "", fee_standard_name,
                 data.get("fee_category") or "care",
                 data["amount"], data.get("billing_cycle") or "monthly",
                 data["period_start"], data["period_end"],
                 data.get("payment_method") or "cash",
                 data.get("receipt_number") or "",
                 data.get("payer") or "", now,
                 data.get("notes") or "", now),
            )
            conn.execute("COMMIT")
        return self.get_billing_record(record_id)

    def get_billing_record(self, record_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM billing_records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_billing_records(self, admission_id: Optional[str] = None,
                             fee_category: Optional[str] = None,
                             limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM billing_records WHERE 1=1"
        params: list = []
        if admission_id:
            sql += " AND admission_id = ?"
            params.append(admission_id)
        if fee_category:
            sql += " AND fee_category = ?"
            params.append(fee_category)
        sql += " ORDER BY paid_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ================================================================
    # 续费逻辑
    # ================================================================

    def get_latest_period_end(self, admission_id: str,
                              fee_category: Optional[str] = None) -> Optional[str]:
        """获取某入住申请某类费用的最新截止日期"""
        sql = ("SELECT MAX(period_end) AS latest_end FROM billing_records "
               "WHERE admission_id = ?")
        params: list = [admission_id]
        if fee_category:
            sql += " AND fee_category = ?"
            params.append(fee_category)
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        if row and row["latest_end"]:
            return row["latest_end"]
        return None

    def renew(self, data: dict) -> dict:
        """续费：从上次截止日期往后延 N 个周期。

        如果没有历史记录，则从今天开始计。
        返回新创建的缴费记录。
        """
        admission_id = data["admission_id"]
        fee_category = data.get("fee_category") or "care"
        billing_cycle = data.get("billing_cycle") or "monthly"
        num_cycles = data.get("num_cycles", 1)

        # 确定起始日期 = 上次截止日期的次日，或今天
        latest_end = self.get_latest_period_end(admission_id, fee_category)
        if latest_end:
            start_date = (datetime.strptime(latest_end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = self._today()

        # 计算新截止日期
        end_date = self._calc_period_end(start_date, billing_cycle, num_cycles)

        record_data = {
            "admission_id": admission_id,
            "patient_name": data.get("patient_name") or "",
            "fee_standard_id": data.get("fee_standard_id") or "",
            "fee_category": fee_category,
            "amount": data["amount"],
            "billing_cycle": billing_cycle,
            "period_start": start_date,
            "period_end": end_date,
            "payment_method": data.get("payment_method") or "cash",
            "receipt_number": data.get("receipt_number") or "",
            "payer": data.get("payer") or "",
            "notes": data.get("notes") or "",
        }
        record = self.create_billing_record(record_data)
        # 附加续费特有字段
        record["previous_end_date"] = latest_end or ""
        record["new_end_date"] = end_date
        return record

    @staticmethod
    def _calc_period_end(start_date: str, billing_cycle: str, num_cycles: int = 1) -> str:
        """根据起始日期和周期计算截止日期。"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        if billing_cycle == "monthly":
            end = start + relativedelta(months=num_cycles) - timedelta(days=1)
        elif billing_cycle == "quarterly":
            end = start + relativedelta(months=3 * num_cycles) - timedelta(days=1)
        elif billing_cycle == "semi_annual":
            end = start + relativedelta(months=6 * num_cycles) - timedelta(days=1)
        elif billing_cycle == "yearly":
            end = start + relativedelta(years=num_cycles) - timedelta(days=1)
        else:
            end = start + relativedelta(months=num_cycles) - timedelta(days=1)
        return end.strftime("%Y-%m-%d")

    # ================================================================
    # 到期状态计算
    # ================================================================

    def get_billing_status_for_admission(self, admission_id: str) -> dict:
        """计算单个入住老人的缴费状态。

        Returns:
            {
                "billing_status": "normal" / "expiring_soon" / "overdue" / "settled",
                "latest_period_end": "2026-06-30" or None,
                "days_remaining": int or None,
                "total_paid": float,
                "total_records": int,
            }
        """
        with self._connect() as conn:
            # 最新截止日期
            row = conn.execute(
                "SELECT MAX(period_end) AS latest_end, "
                "COALESCE(SUM(amount), 0) AS total_paid, "
                "COUNT(*) AS total_records "
                "FROM billing_records WHERE admission_id = ?",
                (admission_id,)
            ).fetchone()

        latest_end = row["latest_end"] if row else None
        total_paid = float(row["total_paid"]) if row else 0.0
        total_records = int(row["total_records"]) if row else 0

        if not latest_end or total_records == 0:
            return {
                "billing_status": "normal",
                "latest_period_end": None,
                "days_remaining": None,
                "total_paid": total_paid,
                "total_records": total_records,
            }

        today = datetime.now().date()
        end_date = datetime.strptime(latest_end, "%Y-%m-%d").date()
        days_remaining = (end_date - today).days

        if days_remaining < 0:
            status = "overdue"
        elif days_remaining <= 7:
            status = "expiring_soon"
        else:
            status = "normal"

        return {
            "billing_status": status,
            "latest_period_end": latest_end,
            "days_remaining": days_remaining,
            "total_paid": total_paid,
            "total_records": total_records,
        }

    def get_all_billing_overviews(self, status_filter: Optional[str] = None) -> list[dict]:
        """获取所有有缴费记录的入住老人的缴费状态总览。

        仅返回有 billing_records 记录的 admission_id。
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT admission_id, MAX(period_end) AS latest_end, "
                "COALESCE(SUM(amount), 0) AS total_paid, "
                "COUNT(*) AS total_records "
                "FROM billing_records GROUP BY admission_id"
            ).fetchall()

        today = datetime.now().date()
        results = []
        for r in rows:
            latest_end = r["latest_end"]
            total_paid = float(r["total_paid"])
            total_records = int(r["total_records"])

            if latest_end:
                end_date = datetime.strptime(latest_end, "%Y-%m-%d").date()
                days_remaining = (end_date - today).days
                if days_remaining < 0:
                    status = "overdue"
                elif days_remaining <= 7:
                    status = "expiring_soon"
                else:
                    status = "normal"
            else:
                days_remaining = None
                status = "normal"

            if status_filter and status != status_filter:
                continue

            results.append({
                "admission_id": r["admission_id"],
                "billing_status": status,
                "latest_period_end": latest_end,
                "days_remaining": days_remaining,
                "total_paid": total_paid,
                "total_records": total_records,
            })

        # 排序：欠费优先，然后即将到期，最后正常
        priority = {"overdue": 0, "expiring_soon": 1, "normal": 2, "settled": 3}
        results.sort(key=lambda x: (priority.get(x["billing_status"], 9),
                                     x.get("days_remaining") or 9999))
        return results

    def get_expiry_alerts(self, days_threshold: int = 7) -> list[dict]:
        """获取即将到期和已欠费的入住老人列表。

        Args:
            days_threshold: 提前多少天算"即将到期"，默认7天
        """
        today = datetime.now().date()
        threshold_date = (today + timedelta(days=days_threshold)).strftime("%Y-%m-%d")

        with self._connect() as conn:
            # 找出最新截止日期在 threshold_date 之内（含已过期）的
            rows = conn.execute(
                "SELECT admission_id, MAX(period_end) AS latest_end "
                "FROM billing_records GROUP BY admission_id "
                "HAVING latest_end <= ?",
                (threshold_date,)
            ).fetchall()

        results = []
        for r in rows:
            latest_end = r["latest_end"]
            end_date = datetime.strptime(latest_end, "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
            if days_remaining < 0:
                status = "overdue"
            else:
                status = "expiring_soon"
            results.append({
                "admission_id": r["admission_id"],
                "billing_status": status,
                "latest_period_end": latest_end,
                "days_remaining": days_remaining,
            })

        results.sort(key=lambda x: x["days_remaining"])
        return results


# ================================================================
# 单例
# ================================================================
_billing_store: Optional[BillingStore] = None
_billing_store_lock = threading.Lock()


def get_billing_store() -> BillingStore:
    """获取 BillingStore 单例"""
    global _billing_store
    if _billing_store is None:
        with _billing_store_lock:
            if _billing_store is None:
                base_dir = Path(__file__).resolve().parent.parent.parent
                db_dir = base_dir / "local_billing"
                db_dir.mkdir(parents=True, exist_ok=True)
                _billing_store = BillingStore(db_dir / "billing.db")
    return _billing_store
