# -*- coding: utf-8 -*-
"""
@File    : tests/test_hot_snapshot_router.py
@Desc    : 热快照路由 (admin 专用) — 通过 TestClient
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import AuthTokenMiddleware
from app.routers import backup as backup_router
from app.services import hot_snapshot as hs
from app.services.user_store import UserStore, ROLE_ADMIN, ROLE_NURSE


def _make_db(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('hello')")
        conn.commit()
    finally:
        conn.close()
    return p


@pytest.fixture
def env(tmp_path):
    store = UserStore(tmp_path / "users.db")
    admin = store.create_user("admin", role=ROLE_ADMIN)
    admin_token, _ = store.create_token(admin.user_id)
    nurse = store.create_user("nurse1", role=ROLE_NURSE)
    nurse_token, _ = store.create_token(nurse.user_id)

    db = _make_db(tmp_path / "local_billing" / "billing.db")

    hs.reset_snapshotter()
    snap = hs.init_snapshotter(hs.SnapshotterOptions(
        enabled=True,
        targets=(db,),
        snapshot_dir=tmp_path / "hot",
        interval_seconds=600,         # 不会被自动循环触发
        keep_per_source=3,
        base_dir=tmp_path,
    ))

    app = FastAPI()
    app.state.user_store = store
    app.state.auth_mode = "user_store"
    app.include_router(backup_router.router, prefix="/api")
    app.add_middleware(AuthTokenMiddleware, legacy_token=None, user_store=store)

    yield {
        "app": app,
        "admin_token": admin_token,
        "nurse_token": nurse_token,
        "snap": snap,
        "db": db,
    }
    hs.reset_snapshotter()


# ── 1. 权限 ─────────────────────────────────────────────────
class TestPermissions:
    def test_nurse_cannot_run_hot(self, env):
        with TestClient(env["app"]) as c:
            r = c.post("/api/backup/hot/run", headers={"X-Auth-Token": env["nurse_token"]})
            assert r.status_code == 403

    def test_nurse_cannot_get_hot_status(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/hot/status", headers={"X-Auth-Token": env["nurse_token"]})
            assert r.status_code == 403

    def test_no_token_rejected(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/hot/status")
            assert r.status_code == 401


# ── 2. status ───────────────────────────────────────────────
class TestStatus:
    def test_returns_config_and_targets(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/hot/status", headers={"X-Auth-Token": env["admin_token"]})
            assert r.status_code == 200
            data = r.json()
            assert data["enabled"] is True
            assert data["interval_seconds"] == 600
            assert any("billing.db" in t for t in data["targets"])
            # 还没跑过 → reports 是空
            assert data["last_reports"] == []


# ── 3. run-now ──────────────────────────────────────────────
class TestRunNow:
    def test_admin_can_trigger_hot_snapshot(self, env):
        with TestClient(env["app"]) as c:
            r = c.post("/api/backup/hot/run", headers={"X-Auth-Token": env["admin_token"]})
            assert r.status_code == 200, r.text
            data = r.json()
            assert len(data["snapshots"]) == 1
            snap_path = Path(data["snapshots"][0]["snapshot_path"])
            assert snap_path.exists()
            assert snap_path.suffix == hs.SNAPSHOT_SUFFIX

    def test_run_now_returns_503_when_not_initialized(self, tmp_path):
        """未 init_snapshotter 时,/api/backup/hot/run 必须 503,而不是崩。"""
        from app.middleware.auth import AuthTokenMiddleware
        store = UserStore(tmp_path / "users.db")
        admin = store.create_user("admin", role=ROLE_ADMIN)
        token, _ = store.create_token(admin.user_id)

        hs.reset_snapshotter()             # 强制 None
        app = FastAPI()
        app.state.user_store = store
        app.state.auth_mode = "user_store"
        app.include_router(backup_router.router, prefix="/api")
        app.add_middleware(AuthTokenMiddleware, legacy_token=None, user_store=store)

        with TestClient(app) as c:
            r = c.post("/api/backup/hot/run", headers={"X-Auth-Token": token})
            assert r.status_code == 503

    def test_status_after_run_lists_report(self, env):
        with TestClient(env["app"]) as c:
            c.post("/api/backup/hot/run", headers={"X-Auth-Token": env["admin_token"]})
            r = c.get("/api/backup/hot/status", headers={"X-Auth-Token": env["admin_token"]})
            data = r.json()
            assert len(data["last_reports"]) == 1
            assert data["last_reports"][0]["bytes"] > 0
