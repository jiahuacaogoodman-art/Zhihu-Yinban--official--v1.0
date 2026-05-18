# -*- coding: utf-8 -*-
"""
@File    : tests/test_sync_metrics.py
@Desc    : Edge sync 指标采集 + PII 守门
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services.sync_metrics import (
    METRICS_SCHEMA_VERSION,
    assert_no_pii,
    collect_metrics,
)


# ── helpers ─────────────────────────────────────────────────
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _hours_ago(h: int) -> str:
    return (datetime.now() - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")


def _setup_care_db(base: Path, branch_id: str = "main") -> Path:
    p = base / "local_care" / "care.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "CREATE TABLE beds (bed_id TEXT PRIMARY KEY, status TEXT, branch_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE incidents ("
            "  incident_id TEXT PRIMARY KEY, incident_type TEXT,"
            "  patient_id TEXT, description TEXT,"
            "  created_at TEXT, branch_id TEXT)"
        )
        # 5 个床位:3 occupied, 1 available, 1 reserved
        for i, status in enumerate(["occupied", "occupied", "occupied",
                                    "available", "reserved"]):
            conn.execute(
                "INSERT INTO beds VALUES (?, ?, ?)",
                (f"bed_{i}", status, branch_id),
            )
        # 24h 内 2 个跌倒 + 1 个用药错误
        for i, t, ts in [
            (1, "fall", _hours_ago(2)),
            (2, "fall", _hours_ago(20)),
            (3, "medication_error", _hours_ago(5)),
            (4, "fall", _hours_ago(48)),  # 老的,不该算
        ]:
            conn.execute(
                "INSERT INTO incidents VALUES (?, ?, 'p_secret', '伤口出血', ?, ?)",
                (f"inc_{i}", t, ts, branch_id),
            )
        conn.commit()
    finally:
        conn.close()
    return p


def _setup_billing_db(base: Path, branch_id: str = "main") -> Path:
    p = base / "local_billing" / "billing.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "CREATE TABLE billing_records ("
            "  record_id TEXT PRIMARY KEY, admission_id TEXT, "
            "  amount REAL, period_end TEXT, branch_id TEXT)"
        )
        # 3 admission: 1 overdue, 1 expiring (7d), 1 normal
        today = datetime.now().date()
        rows = [
            ("r1", "adm-1", 100, (today - timedelta(days=3)).strftime("%Y-%m-%d")),
            ("r2", "adm-2", 100, (today + timedelta(days=2)).strftime("%Y-%m-%d")),
            ("r3", "adm-3", 100, (today + timedelta(days=60)).strftime("%Y-%m-%d")),
        ]
        for r in rows:
            conn.execute(
                "INSERT INTO billing_records VALUES (?,?,?,?,?)",
                (*r, branch_id),
            )
        conn.commit()
    finally:
        conn.close()
    return p


def _setup_audit_db(base: Path, branch_id: str = "main") -> Path:
    p = base / "local_audit_log" / "audit.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "CREATE TABLE audit_log ("
            "  id TEXT PRIMARY KEY, ts TEXT, action TEXT, "
            "  patient_id TEXT, operator TEXT, branch_id TEXT)"
        )
        for i, action, ts in [
            (1, "PATIENT_UPDATE", _hours_ago(2)),
            (2, "PATIENT_UPDATE", _hours_ago(3)),
            (3, "RECORD_UPLOAD", _hours_ago(5)),
            (4, "PATIENT_READ", _hours_ago(48)),  # 老的
        ]:
            conn.execute(
                "INSERT INTO audit_log VALUES (?,?,?,?,?,?)",
                (f"a_{i}", ts, action, "patient_X", "admin", branch_id),
            )
        conn.commit()
    finally:
        conn.close()
    return p


def _setup_users_db(base: Path, branch_id: str = "main") -> Path:
    p = base / "local_auth" / "users.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "CREATE TABLE users ("
            "  user_id TEXT PRIMARY KEY, username TEXT, "
            "  active INTEGER, branch_id TEXT)"
        )
        # 3 active, 1 inactive
        for i, active in [(1, 1), (2, 1), (3, 1), (4, 0)]:
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?)",
                (f"u_{i}", f"user_{i}", active, branch_id),
            )
        conn.commit()
    finally:
        conn.close()
    return p


# ── 1. collect_metrics 整体形状 ────────────────────────────
class TestCollectMetricsShape:
    def test_returns_known_keys(self, tmp_path):
        _setup_care_db(tmp_path)
        _setup_billing_db(tmp_path)
        _setup_audit_db(tmp_path)
        _setup_users_db(tmp_path)

        m = collect_metrics(tmp_path, "main")

        assert m["schema_version"] == METRICS_SCHEMA_VERSION
        assert m["branch_id"] == "main"
        assert "collected_at" in m
        assert {"occupancy", "billing_alerts", "incidents_24h",
                "audit_24h", "users"}.issubset(m.keys())

    def test_works_with_no_dbs_at_all(self, tmp_path):
        """新部署还没数据库 → 全 0 而不是崩。"""
        m = collect_metrics(tmp_path, "main")
        assert m["occupancy"]["total_beds"] == 0
        assert m["billing_alerts"]["overdue"] == 0
        assert m["incidents_24h"] == {}
        assert m["audit_24h"] == {}
        assert m["users"]["active"] == 0


# ── 2. occupancy 指标 ──────────────────────────────────────
class TestOccupancy:
    def test_counts_by_status(self, tmp_path):
        _setup_care_db(tmp_path)
        m = collect_metrics(tmp_path, "main")
        occ = m["occupancy"]
        assert occ["total_beds"] == 5
        assert occ["occupied"] == 3
        assert occ["available"] == 1
        assert occ["reserved"] == 1
        assert occ["occupancy_rate"] == round(3 / 5, 4)

    def test_branch_id_filter_excludes_other_branches(self, tmp_path):
        _setup_care_db(tmp_path, branch_id="branch_A")
        # 多塞两个 main 的床
        conn = sqlite3.connect(str(tmp_path / "local_care" / "care.db"))
        try:
            conn.execute(
                "INSERT INTO beds VALUES ('main_b1', 'occupied', 'main')"
            )
            conn.commit()
        finally:
            conn.close()

        m_a = collect_metrics(tmp_path, "branch_A")
        m_main = collect_metrics(tmp_path, "main")
        assert m_a["occupancy"]["total_beds"] == 5
        assert m_main["occupancy"]["total_beds"] == 1


# ── 3. 24 小时窗口指标 ─────────────────────────────────────
class TestRollingWindow:
    def test_incidents_only_last_24h(self, tmp_path):
        _setup_care_db(tmp_path)
        m = collect_metrics(tmp_path, "main")
        # 本院 24h 内: 2 fall + 1 medication_error
        assert m["incidents_24h"].get("fall") == 2
        assert m["incidents_24h"].get("medication_error") == 1

    def test_audit_aggregated_by_action(self, tmp_path):
        _setup_audit_db(tmp_path)
        m = collect_metrics(tmp_path, "main")
        assert m["audit_24h"].get("PATIENT_UPDATE") == 2
        assert m["audit_24h"].get("RECORD_UPLOAD") == 1
        # 48h 前那条不应该出现
        assert "PATIENT_READ" not in m["audit_24h"]


# ── 4. billing 告警 ────────────────────────────────────────
class TestBillingAlerts:
    def test_separates_overdue_from_expiring(self, tmp_path):
        _setup_billing_db(tmp_path)
        m = collect_metrics(tmp_path, "main")
        assert m["billing_alerts"]["overdue"] == 1
        assert m["billing_alerts"]["expiring_soon"] == 1


# ── 5. users ──────────────────────────────────────────────
class TestUsers:
    def test_active_inactive_count(self, tmp_path):
        _setup_users_db(tmp_path)
        m = collect_metrics(tmp_path, "main")
        assert m["users"]["active"] == 3
        assert m["users"]["inactive"] == 1


# ── 6. 关键安全:载荷不含 PII ───────────────────────────────
class TestNoPII:
    def test_collected_payload_passes_no_pii_check(self, tmp_path):
        """
        每张表都塞了 PII 字段值 (patient_X / 伤口出血 / admin / user_N),
        collect_metrics 必须只返回聚合数字 + action key,不能让任一 PII 值
        混进 payload。assert_no_pii() 是上线前最后一道闸,这里调一次。
        """
        _setup_care_db(tmp_path)
        _setup_billing_db(tmp_path)
        _setup_audit_db(tmp_path)
        _setup_users_db(tmp_path)

        m = collect_metrics(tmp_path, "main")
        # 不抛即通过 (黑名单包含 patient_id / operator / username 等所有泄密 key)
        assert_no_pii(m)

        # 显式的"载荷字符串扫一遍"也算个保险:不应有 patient_X / user_3 等值
        flat = repr(m)
        assert "patient_X" not in flat
        assert "user_3" not in flat
        assert "admin" not in flat
        assert "伤口出血" not in flat

    def test_assert_no_pii_catches_injected_field(self):
        # 模拟未来某次开发把 patient_id 误塞进 metrics 输出
        bad = {
            "schema_version": 1,
            "occupancy": {"total_beds": 10, "patient_id": "p1"},
        }
        with pytest.raises(ValueError, match="patient_id"):
            assert_no_pii(bad)

    def test_assert_no_pii_catches_nested_in_list(self):
        bad = {
            "incidents": [
                {"type": "fall", "description": "倒地不起"},
            ],
        }
        with pytest.raises(ValueError, match="description"):
            assert_no_pii(bad)

    def test_assert_no_pii_passes_clean_payload(self):
        ok = {
            "schema_version": 1,
            "occupancy": {"total_beds": 10, "occupied": 5},
            "incidents_24h": {"fall": 2},
        }
        assert_no_pii(ok)         # 不抛即可
