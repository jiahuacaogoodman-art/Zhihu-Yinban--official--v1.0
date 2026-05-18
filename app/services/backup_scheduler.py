# -*- coding: utf-8 -*-
"""
@File    : app/services/backup_scheduler.py
@Desc    : 备份调度器 —— 纯 asyncio task，每天指定时间跑一次

为什么不用 APScheduler / cron
  · APScheduler 增加新依赖，对乡镇离线部署不友好
  · cron 在 docker compose 里需要单独的 sidecar 容器，复杂
  · 业务量小（每天一次，几百 MB 内），asyncio 单 task 完全够

行为
  · lifespan startup 阶段调用 start()
  · lifespan shutdown 阶段 stop() 优雅退出
  · 每次循环：算到下一个 BACKUP_HOUR 的秒数，sleep，跑 create_backup
  · 跑备份本身丢到 to_thread（避免阻塞 event loop）
  · 任何异常都不会让循环退出——只 log，下一天继续

异常恢复
  · 服务重启后 task 重新建立循环，下一个 03:00 自动跑
  · 如果当天 03:00 已经过了，等明天
  · 如果用户调用 trigger_now()，立即跑一次（不破坏定时循环）
"""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from app.services.backup import (
    BackupConfig,
    BackupReport,
    create_backup,
    default_sources,
    parse_key,
)


@dataclasses.dataclass
class SchedulerOptions:
    """
    从环境 / app config 推导出来的运行参数。

    enabled = False 时调度器完全不启动，等价于禁用功能；用户手动
    `POST /api/backup/run` 仍然可以跑（只要 key 配了）。
    """

    enabled: bool
    hour: int                       # 0-23
    minute: int                     # 0-59
    target_dir: Path
    encryption_key: bytes
    base_dir: Path
    retention_days: int = 14


def _seconds_until_next_run(now: datetime, hour: int, minute: int) -> float:
    """计算从 now 到下一个 (hour:minute) 的秒数。如果今天的时间点已过，跳到明天。"""
    target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target_today <= now:
        target_today += timedelta(days=1)
    return (target_today - now).total_seconds()


class BackupScheduler:
    """
    单实例长跑后台任务。

    设计上**只**承担"什么时候跑"的职责；具体打包/加密都由 backup.py 负责。
    """

    def __init__(self, options: SchedulerOptions):
        self._opts = options
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event() if False else None   # set in start()
        self._last_report: Optional[BackupReport] = None
        self._last_error: Optional[str] = None

    # ── 公开 API ───────────────────────────────────────
    @property
    def last_report(self) -> Optional[BackupReport]:
        return self._last_report

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        启动循环。在 lifespan startup 里调一次。
        如果 enabled=False，本方法是 no-op。
        """
        if not self._opts.enabled:
            logger.info("备份调度器: 未启用 (BACKUP_ENABLED=false 或 key 缺失)")
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop(), name="backup_scheduler")
        logger.info(
            f"备份调度器已启动: 每天 {self._opts.hour:02d}:{self._opts.minute:02d} "
            f"打包至 {self._opts.target_dir}"
        )

    async def stop(self) -> None:
        """lifespan shutdown 时调，最多等 5 秒。"""
        if self._task is None or self._stop_event is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except asyncio.TimeoutError:
            logger.warning("备份调度器停止超时，强制取消")
            self._task.cancel()
        self._task = None

    async def trigger_now(self) -> BackupReport:
        """
        手动立即跑一次备份，用在管理端"立即备份"按钮 / 测试。
        不影响主循环的下次定时。
        """
        return await asyncio.to_thread(self._run_one)

    # ── 内部 ───────────────────────────────────────────
    async def _run_loop(self) -> None:
        """主循环。任何异常都不能让它退出。"""
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            wait = _seconds_until_next_run(
                datetime.now(), self._opts.hour, self._opts.minute,
            )
            logger.debug(f"备份调度器: 下次执行 {wait/3600:.2f} 小时后")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait)
                # 如果 wait 提前返回，说明 stop() 被调用，跳出循环
                break
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.to_thread(self._run_one)
            except Exception as e:
                self._last_error = str(e)
                logger.exception(f"备份失败 (会在下一个调度点重试): {e}")
                # sleep 一下避免 hour:minute 边界附近反复触发
                await asyncio.sleep(60)

    def _run_one(self) -> BackupReport:
        """同步版备份；在 to_thread 里跑，避免阻塞 event loop。"""
        cfg = BackupConfig(
            sources=default_sources(self._opts.base_dir),
            target_dir=self._opts.target_dir,
            encryption_key=self._opts.encryption_key,
            retention_days=self._opts.retention_days,
        )
        report = create_backup(cfg)
        self._last_report = report
        self._last_error = None
        return report


# ── 单例（与 audit_log / file_store 风格保持一致）────────
_scheduler: Optional[BackupScheduler] = None


def get_scheduler() -> Optional[BackupScheduler]:
    """获取当前单例。lifespan 之外没初始化过则返回 None。"""
    return _scheduler


def init_scheduler(options: SchedulerOptions) -> BackupScheduler:
    global _scheduler
    _scheduler = BackupScheduler(options)
    return _scheduler


def reset_scheduler() -> None:
    """仅测试用。"""
    global _scheduler
    _scheduler = None


def options_from_env(base_dir: Path) -> SchedulerOptions:
    """
    从环境变量构造 SchedulerOptions。

    环境变量：
      BACKUP_ENABLED            "true"/"1"/"yes" → 启用调度；默认 false
      BACKUP_DIR                目标目录（NAS 挂载 / USB 挂载）；默认 BASE_DIR/local_backups
      BACKUP_ENCRYPTION_KEY     32 字节 key（hex / base64 / urlsafe-base64）
      BACKUP_HOUR               0-23，默认 3
      BACKUP_MINUTE             0-59，默认 0
      BACKUP_RETENTION_DAYS     默认 14
    """
    import os as _os

    enabled_raw = _os.getenv("BACKUP_ENABLED", "false").strip().lower()
    enabled = enabled_raw in {"true", "1", "yes"}

    target_dir_raw = _os.getenv("BACKUP_DIR", "").strip()
    target_dir = Path(target_dir_raw) if target_dir_raw else base_dir / "local_backups"

    key_raw = _os.getenv("BACKUP_ENCRYPTION_KEY", "")
    try:
        key = parse_key(key_raw)
    except ValueError:
        # key 缺失 → 强制 disable，不会让 startup 崩
        if enabled:
            logger.warning(
                "BACKUP_ENABLED=true 但 BACKUP_ENCRYPTION_KEY 未配置/格式非法；"
                "调度器自动禁用（用户仍可在 KMS 上线后手动恢复）"
            )
        enabled = False
        key = b"\x00" * 32

    try:
        hour = max(0, min(23, int(_os.getenv("BACKUP_HOUR", "3"))))
    except ValueError:
        hour = 3
    try:
        minute = max(0, min(59, int(_os.getenv("BACKUP_MINUTE", "0"))))
    except ValueError:
        minute = 0
    try:
        retention = max(1, int(_os.getenv("BACKUP_RETENTION_DAYS", "14")))
    except ValueError:
        retention = 14

    return SchedulerOptions(
        enabled=enabled,
        hour=hour,
        minute=minute,
        target_dir=target_dir,
        encryption_key=key,
        base_dir=base_dir,
        retention_days=retention,
    )


__all__ = [
    "BackupScheduler",
    "SchedulerOptions",
    "get_scheduler",
    "init_scheduler",
    "options_from_env",
    "reset_scheduler",
    "_seconds_until_next_run",   # 暴露给单测
]
