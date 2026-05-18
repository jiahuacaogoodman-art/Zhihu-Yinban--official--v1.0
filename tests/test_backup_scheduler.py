# -*- coding: utf-8 -*-
"""
@File    : tests/test_backup_scheduler.py
@Desc    : 备份调度器测试 - 时间计算 / 配置解析 / 启停 / trigger_now
"""
from __future__ import annotations

import asyncio
import base64
import os
from datetime import datetime
from pathlib import Path

import pytest

from app.services import backup as bk
from app.services import backup_scheduler as bs


# ── 1. _seconds_until_next_run ──────────────────────────────
class TestSecondsUntilNextRun:
    def test_target_today_in_future(self):
        # 现在是 01:00，目标 03:00 → 7200 秒
        now = datetime(2026, 5, 18, 1, 0, 0)
        s = bs._seconds_until_next_run(now, hour=3, minute=0)
        assert s == 7200

    def test_target_today_already_passed_jumps_tomorrow(self):
        # 现在 04:00，目标 03:00 → 23 小时（明天 03:00）
        now = datetime(2026, 5, 18, 4, 0, 0)
        s = bs._seconds_until_next_run(now, hour=3, minute=0)
        assert s == 23 * 3600

    def test_target_exactly_now_treated_as_tomorrow(self):
        """
        正好相等 → 走"今天的时间点已过" → 明天。这避免了边界毛刺：
        刚跑完后立即又触发的死循环。
        """
        now = datetime(2026, 5, 18, 3, 0, 0)
        s = bs._seconds_until_next_run(now, hour=3, minute=0)
        assert s == 24 * 3600

    def test_minute_precision(self):
        now = datetime(2026, 5, 18, 2, 50, 0)
        s = bs._seconds_until_next_run(now, hour=3, minute=15)
        assert s == 25 * 60


# ── 2. options_from_env ─────────────────────────────────────
class TestOptionsFromEnv:
    def test_disabled_by_default(self, tmp_path, monkeypatch):
        for k in ("BACKUP_ENABLED", "BACKUP_ENCRYPTION_KEY",
                  "BACKUP_DIR", "BACKUP_HOUR", "BACKUP_MINUTE", "BACKUP_RETENTION_DAYS"):
            monkeypatch.delenv(k, raising=False)
        opts = bs.options_from_env(tmp_path)
        assert opts.enabled is False

    def test_enabled_true_but_no_key_falls_back_to_disabled(self, tmp_path, monkeypatch):
        """
        env 里 ENABLED=true 但 KEY 缺失 / 格式错 → 调度器自动 disable，
        不能让 startup 因为环境配错就崩溃。
        """
        monkeypatch.setenv("BACKUP_ENABLED", "true")
        monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
        opts = bs.options_from_env(tmp_path)
        assert opts.enabled is False

    def test_full_valid_config(self, tmp_path, monkeypatch):
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        target = tmp_path / "nas-mount"
        monkeypatch.setenv("BACKUP_ENABLED", "true")
        monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", key)
        monkeypatch.setenv("BACKUP_DIR", str(target))
        monkeypatch.setenv("BACKUP_HOUR", "5")
        monkeypatch.setenv("BACKUP_MINUTE", "30")
        monkeypatch.setenv("BACKUP_RETENTION_DAYS", "30")

        opts = bs.options_from_env(tmp_path)
        assert opts.enabled is True
        assert opts.target_dir == target
        assert opts.hour == 5
        assert opts.minute == 30
        assert opts.retention_days == 30
        assert len(opts.encryption_key) == 32

    def test_invalid_hour_falls_back_to_3(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BACKUP_ENABLED", "false")
        monkeypatch.setenv("BACKUP_HOUR", "not-a-number")
        opts = bs.options_from_env(tmp_path)
        assert opts.hour == 3

    def test_hour_clamped_to_valid_range(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BACKUP_HOUR", "99")
        opts = bs.options_from_env(tmp_path)
        assert opts.hour == 23


# ── 3. trigger_now（同步 API，整端到端跑一次）──────────────
class TestTriggerNow:
    @pytest.mark.asyncio
    async def test_trigger_now_creates_backup_file(self, tmp_path):
        # 准备真实 source 目录
        src = tmp_path / "local_billing"
        src.mkdir()
        (src / "billing.db").write_bytes(b"x" * 100)

        # 关键：让 default_sources 只看到我们准备的目录
        # 直接构造 SchedulerOptions，不走 env
        opts = bs.SchedulerOptions(
            enabled=True,
            hour=3,
            minute=0,
            target_dir=tmp_path / "out",
            encryption_key=os.urandom(32),
            base_dir=tmp_path,
            retention_days=14,
        )
        bs.reset_scheduler()
        sched = bs.init_scheduler(opts)

        report = await sched.trigger_now()
        assert report.path.exists()
        assert report.size > 0
        # 验证还能解开
        manifest = bk.verify_backup(report.path, opts.encryption_key)
        assert any(s["path"].endswith("local_billing") for s in manifest["sources"])

    @pytest.mark.asyncio
    async def test_trigger_now_records_last_report(self, tmp_path):
        src = tmp_path / "local_billing"
        src.mkdir()
        (src / "billing.db").write_bytes(b"x")
        opts = bs.SchedulerOptions(
            enabled=True, hour=3, minute=0,
            target_dir=tmp_path / "out",
            encryption_key=os.urandom(32),
            base_dir=tmp_path,
        )
        bs.reset_scheduler()
        sched = bs.init_scheduler(opts)

        assert sched.last_report is None
        await sched.trigger_now()
        assert sched.last_report is not None
        assert sched.last_error is None


# ── 4. start/stop 生命周期 ──────────────────────────────────
class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_when_disabled_is_noop(self, tmp_path):
        opts = bs.SchedulerOptions(
            enabled=False, hour=3, minute=0,
            target_dir=tmp_path / "out",
            encryption_key=os.urandom(32),
            base_dir=tmp_path,
        )
        bs.reset_scheduler()
        sched = bs.init_scheduler(opts)
        sched.start()
        assert sched._task is None
        # stop 也安全
        await sched.stop()

    @pytest.mark.asyncio
    async def test_start_then_stop_releases_task(self, tmp_path):
        # hour=23 + minute=59，让首次 sleep 极长，task 不会真的跑备份
        opts = bs.SchedulerOptions(
            enabled=True, hour=23, minute=59,
            target_dir=tmp_path / "out",
            encryption_key=os.urandom(32),
            base_dir=tmp_path,
        )
        bs.reset_scheduler()
        sched = bs.init_scheduler(opts)
        sched.start()
        assert sched._task is not None
        # 立即停掉
        await sched.stop()
        assert sched._task is None
