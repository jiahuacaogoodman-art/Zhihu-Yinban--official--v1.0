# -*- coding: utf-8 -*-
"""
@File    : tests/test_branching.py
@Desc    : PR#6 branching helper - 幂等加列 + 索引

测试覆盖
  · 新库建表后调一遍是 no-op
  · 老库（没有 branch_id / version_id 列）能被补齐
  · 默认值正确（branch_id='main', version_id=1）
  · 重复调用不报错（ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS）
  · branch_only 表不会拿到 version_id
  · 跨 store 集成：每个 store 的 _init_db 都把所有受影响表加好了列
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.services.branching import (
    BRANCH_ID_DEFAULT,
    INITIAL_VERSION,
    ensure_branching_columns,
)


# ── helpers ─────────────────────────────────────────────────
def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _indexes(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA index_list({table})").fetchall()}


@pytest.fixture
def conn():
    """开一个 in-memory SQLite,完了自己关。"""
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


# ── 1. 老库:列被补齐 ──────────────────────────────────────
class TestLegacySchemaUpgrade:
    def test_adds_branch_and_version_to_existing_table(self, conn):
        # 模拟 PR#6 之前的老 schema
        conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO patients VALUES ('p1', '张三')")

        result = ensure_branching_columns(conn, full=("patients",))

        assert result["added_branch_id"] == ["patients"]
        assert result["added_version_id"] == ["patients"]
        cols = _columns(conn, "patients")
        assert "branch_id" in cols
        assert "version_id" in cols

    def test_existing_rows_get_default_values(self, conn):
        conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO patients VALUES ('p1')")
        conn.execute("INSERT INTO patients VALUES ('p2')")

        ensure_branching_columns(conn, full=("patients",))

        rows = conn.execute("SELECT id, branch_id, version_id FROM patients").fetchall()
        for r in rows:
            assert r[1] == BRANCH_ID_DEFAULT
            assert r[2] == INITIAL_VERSION

    def test_branch_only_does_not_add_version(self, conn):
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT)")

        result = ensure_branching_columns(conn, full=(), branch_only=("events",))

        assert "events" in result["added_branch_id"]
        assert "events" not in result["added_version_id"]
        cols = _columns(conn, "events")
        assert "branch_id" in cols
        assert "version_id" not in cols

    def test_creates_branch_index(self, conn):
        conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY)")
        ensure_branching_columns(conn, full=("patients",))
        idx = _indexes(conn, "patients")
        assert "idx_patients_branch" in idx


# ── 2. 幂等性 ────────────────────────────────────────────────
class TestIdempotency:
    def test_second_call_is_noop_on_columns(self, conn):
        conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY)")
        first = ensure_branching_columns(conn, full=("patients",))
        second = ensure_branching_columns(conn, full=("patients",))

        assert first["added_branch_id"] == ["patients"]
        # 第二次什么都没加
        assert second["added_branch_id"] == []
        assert second["added_version_id"] == []

    def test_second_call_does_not_break_index(self, conn):
        """ALTER TABLE ADD COLUMN 不幂等;CREATE INDEX IF NOT EXISTS 必须幂等。
        重复调用不能抛 'index already exists'。"""
        conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY)")
        ensure_branching_columns(conn, full=("patients",))
        # 不抛异常即通过
        ensure_branching_columns(conn, full=("patients",))


# ── 3. 新库:CREATE TABLE 已带列时是纯 no-op ─────────────────
class TestFreshSchema:
    def test_table_already_has_columns(self, conn):
        conn.execute(
            "CREATE TABLE patients ("
            "  id TEXT PRIMARY KEY, "
            "  branch_id TEXT NOT NULL DEFAULT 'main', "
            "  version_id INTEGER NOT NULL DEFAULT 1"
            ")"
        )
        result = ensure_branching_columns(conn, full=("patients",))
        assert result["added_branch_id"] == []
        assert result["added_version_id"] == []
        # 索引仍然会被(幂等)创建
        assert "idx_patients_branch" in _indexes(conn, "patients")


# ── 4. 表不存在 ─────────────────────────────────────────────
class TestMissingTable:
    def test_skipped_silently(self, conn):
        result = ensure_branching_columns(conn, full=("nonexistent",))
        assert result["skipped_missing_table"] == ["nonexistent"]
        assert result["added_branch_id"] == []

    def test_missing_table_does_not_block_others(self, conn):
        conn.execute("CREATE TABLE existing (id TEXT)")
        result = ensure_branching_columns(
            conn, full=("nonexistent", "existing"),
        )
        assert "nonexistent" in result["skipped_missing_table"]
        assert "existing" in result["added_branch_id"]


# ── 5. 集成测试:每个 store 都把列加好 ───────────────────────
class TestStoreIntegration:
    """通过实例化每个 store,确认它们的 _init_db 把 branching 列都加好。"""

    def test_billing_store(self, tmp_path):
        from app.services.billing_store import BillingStore
        store = BillingStore(tmp_path / "billing.db")
        with sqlite3.connect(str(tmp_path / "billing.db")) as c:
            for table in ("fee_standards", "billing_records"):
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                assert "branch_id" in cols
                assert "version_id" in cols

    def test_care_store(self, tmp_path):
        from app.services.care_store import CareStore
        store = CareStore(tmp_path / "care.db")
        with sqlite3.connect(str(tmp_path / "care.db")) as c:
            full_tables = (
                "beds", "care_levels", "handovers", "incidents",
                "care_records", "admissions", "assessments",
                "contracts", "payments",
            )
            for table in full_tables:
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                assert "branch_id" in cols, f"{table} 缺 branch_id"
                assert "version_id" in cols, f"{table} 缺 version_id"
            # branch-only tables
            for table in ("care_level_assignments", "admission_timeline"):
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                assert "branch_id" in cols
                assert "version_id" not in cols

    def test_user_store(self, tmp_path):
        from app.services.user_store import UserStore
        store = UserStore(tmp_path / "users.db")
        with sqlite3.connect(str(tmp_path / "users.db")) as c:
            for table in ("users", "api_keys", "roles"):
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                assert "branch_id" in cols
                assert "version_id" in cols
            # global metadata tables NOT branched
            for table in ("permissions", "role_permissions"):
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                assert "branch_id" not in cols
                assert "version_id" not in cols

    def test_event_store(self, tmp_path):
        from app.services.event_store import EventStore
        store = EventStore(tmp_path / "events.db")
        with sqlite3.connect(str(tmp_path / "events.db")) as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(nursing_events)").fetchall()}
            assert "branch_id" in cols
            assert "version_id" in cols

    def test_audit_log(self, tmp_path):
        from app.services.audit_log import AuditLog
        log = AuditLog(tmp_path / "audit.db")
        with sqlite3.connect(str(tmp_path / "audit.db")) as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(audit_log)").fetchall()}
            assert "branch_id" in cols
            # audit is append-only;不带 version_id
            assert "version_id" not in cols

    def test_payment_channels_store(self, tmp_path):
        from app.services.payment_channels import PaymentChannelStore
        store = PaymentChannelStore(tmp_path / "channels.db")
        with sqlite3.connect(str(tmp_path / "channels.db")) as c:
            cols = {r[1] for r in c.execute(
                "PRAGMA table_info(payment_channels)"
            ).fetchall()}
            assert "branch_id" in cols
            assert "version_id" in cols


# ── 6. 老库 → 新库往返:保留原数据 ──────────────────────────
class TestUpgradeRoundtrip:
    def test_legacy_billing_db_upgrades_in_place(self, tmp_path):
        """
        模拟 PR#6 之前的部署:billing.db 已经有完整老 schema 的数据,启动新版后必须:
          1. 老数据原样保留
          2. 老数据自动拿到 branch_id='main' / version_id=1
          3. 新写入仍然能用

        注:legacy schema 必须包含当前 _CREATE_SQL 用到的所有索引列(fee_category 等),
        否则会触发 billing_store 自身未做的"加列迁移",超出 PR#6 范围。
        我们这里只测 branch_id/version_id 部分,所以 legacy schema 用接近完整的版本。
        """
        db_path = tmp_path / "billing.db"
        legacy_conn = sqlite3.connect(str(db_path))
        legacy_conn.execute("""
            CREATE TABLE billing_records (
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
                created_at          TEXT NOT NULL
            )
        """)
        legacy_conn.execute(
            "INSERT INTO billing_records "
            "(record_id, admission_id, amount, period_start, period_end, paid_at, created_at) "
            "VALUES ('legacy-001', 'adm-1', 1000.0, '2026-01-01', '2026-01-31', "
            "'2026-01-15 10:00', '2026-01-15 10:00')"
        )
        legacy_conn.commit()
        legacy_conn.close()

        # 用新版 store 打开 → 自动 migrate
        from app.services.billing_store import BillingStore
        store = BillingStore(db_path)

        # 老数据原样保留 + 默认值
        with sqlite3.connect(str(db_path)) as c:
            row = c.execute(
                "SELECT record_id, amount, branch_id, version_id "
                "FROM billing_records WHERE record_id = 'legacy-001'"
            ).fetchone()
            assert row is not None
            assert row[0] == "legacy-001"
            assert row[1] == 1000.0
            assert row[2] == BRANCH_ID_DEFAULT
            assert row[3] == INITIAL_VERSION

        # 新写入仍然正常工作
        new_record = store.create_billing_record({
            "admission_id": "adm-2",
            "amount": 2000.0,
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
        })
        assert new_record["amount"] == 2000.0
        assert new_record["record_id"].startswith("bill_")
