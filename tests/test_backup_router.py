# -*- coding: utf-8 -*-
"""
@File    : tests/test_backup_router.py
@Desc    : 备份管理路由 (admin 专用) — 通过 TestClient 全栈测
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import AuthTokenMiddleware
from app.routers import backup as backup_router
from app.services import backup as bk
from app.services import backup_scheduler as bs
from app.services.user_store import UserStore, ROLE_ADMIN, ROLE_NURSE


@pytest.fixture
def env(tmp_path, monkeypatch):
    """
    准备一套完整环境：UserStore + admin token + nurse token + 已初始化的备份调度器
    + 一个真实备份文件（trigger_now 跑一次）。
    """
    # User store + admin / nurse
    store = UserStore(tmp_path / "users.db")
    admin = store.create_user("admin", role=ROLE_ADMIN)
    admin_token, _ = store.create_token(admin.user_id)
    nurse = store.create_user("nurse1", role=ROLE_NURSE)
    nurse_token, _ = store.create_token(nurse.user_id)

    # 一个真实的源目录
    src = tmp_path / "local_billing"
    src.mkdir()
    (src / "billing.db").write_bytes(b"data")

    # 调度器
    target_dir = tmp_path / "backups"
    key = os.urandom(32)
    bs.reset_scheduler()
    sched = bs.init_scheduler(bs.SchedulerOptions(
        enabled=True, hour=23, minute=59,    # 几乎不会自动触发
        target_dir=target_dir,
        encryption_key=key,
        base_dir=tmp_path,
        retention_days=14,
    ))

    # 同步搭一份备份文件，让 list/verify 有东西测
    cfg = bk.BackupConfig(
        sources=(src,),
        target_dir=target_dir,
        encryption_key=key,
    )
    report = bk.create_backup(cfg)

    app = FastAPI()
    app.state.user_store = store
    app.state.auth_mode = "user_store"
    app.include_router(backup_router.router, prefix="/api")
    app.add_middleware(AuthTokenMiddleware, legacy_token=None, user_store=store)

    yield {
        "app": app,
        "admin_token": admin_token,
        "nurse_token": nurse_token,
        "key": key,
        "target": target_dir,
        "report": report,
    }
    bs.reset_scheduler()


# ── 1. 权限：nurse 不能访问任何备份接口 ─────────────────────
class TestPermissions:
    def test_nurse_cannot_run_backup(self, env):
        with TestClient(env["app"]) as c:
            r = c.post("/api/backup/run", headers={"X-Auth-Token": env["nurse_token"]})
            assert r.status_code == 403

    def test_nurse_cannot_list(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/list", headers={"X-Auth-Token": env["nurse_token"]})
            assert r.status_code == 403

    def test_nurse_cannot_verify(self, env):
        with TestClient(env["app"]) as c:
            r = c.get(
                f"/api/backup/{env['report'].path.name}/verify",
                headers={"X-Auth-Token": env["nurse_token"]},
            )
            assert r.status_code == 403

    def test_no_token_rejected(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/list")
            assert r.status_code == 401


# ── 2. 列表 / 校验 / 状态 ───────────────────────────────────
class TestListVerifyStatus:
    def test_list_returns_existing_backup(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/list", headers={"X-Auth-Token": env["admin_token"]})
            assert r.status_code == 200
            data = r.json()
            assert data["total"] >= 1
            names = [b["filename"] for b in data["backups"]]
            assert env["report"].path.name in names

    def test_verify_succeeds_for_intact_backup(self, env):
        with TestClient(env["app"]) as c:
            r = c.get(
                f"/api/backup/{env['report'].path.name}/verify",
                headers={"X-Auth-Token": env["admin_token"]},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["valid"] is True
            assert data["manifest"]["version"] == bk.MODULE_VERSION

    def test_verify_fails_for_tampered_backup(self, env):
        # 翻一个字节（绕过 magic + nonce）
        path = env["report"].path
        blob = bytearray(path.read_bytes())
        blob[len(bk.MAGIC) + bk.NONCE_LEN + 100] ^= 0x80
        path.write_bytes(bytes(blob))

        with TestClient(env["app"]) as c:
            r = c.get(
                f"/api/backup/{path.name}/verify",
                headers={"X-Auth-Token": env["admin_token"]},
            )
            assert r.status_code == 200          # endpoint 自己不抛，把 valid=false 透出去
            data = r.json()
            assert data["valid"] is False
            assert data["error"]

    def test_verify_rejects_path_traversal(self, env):
        with TestClient(env["app"]) as c:
            for fname in ("../etc/passwd.zybak.gcm", "..\\foo.zybak.gcm"):
                r = c.get(
                    f"/api/backup/{fname}/verify",
                    headers={"X-Auth-Token": env["admin_token"]},
                )
                # ../ 路径会被路由匹配规则切掉一部分；只要不是 200 valid 就行
                assert r.status_code in (400, 404)

    def test_verify_rejects_wrong_extension(self, env):
        with TestClient(env["app"]) as c:
            r = c.get(
                "/api/backup/foo.tar.gz/verify",
                headers={"X-Auth-Token": env["admin_token"]},
            )
            assert r.status_code == 400

    def test_status_returns_scheduler_state(self, env):
        with TestClient(env["app"]) as c:
            r = c.get("/api/backup/status", headers={"X-Auth-Token": env["admin_token"]})
            assert r.status_code == 200
            data = r.json()
            assert data["enabled"] is True
            assert "23:59" in data["schedule"]


# ── 3. 立即触发备份 ─────────────────────────────────────────
class TestRunNow:
    def test_admin_can_trigger_backup(self, env):
        before = len(list(env["target"].glob("*.zybak.gcm")))
        with TestClient(env["app"]) as c:
            r = c.post("/api/backup/run", headers={"X-Auth-Token": env["admin_token"]})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["filename"].endswith(bk.BACKUP_FILE_EXT)
            assert data["size"] > 0
        after = len(list(env["target"].glob("*.zybak.gcm")))
        assert after == before + 1
