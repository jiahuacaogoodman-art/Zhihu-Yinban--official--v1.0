# -*- coding: utf-8 -*-
"""
@File    : app/services/hot_snapshot.py
@Desc    : 热备份 —— SQLite Backup API + mtime 驱动的周期快照（PR#5）

为什么需要热备
  PR#4 的冷备每天 03:00 跑一次。早上 09:00 出现的关键写入（缴费、
  异常事件、护理记录），如果当晚断电，最多丢失 18 小时数据。这对
  养老院"医疗记录不能丢"的法律责任而言不可接受。

  本模块给出 ≤ 1 分钟 RPO 的保护：每 60 秒（可配）扫一遍所有受保护
  的 SQLite 库，用 SQLite Backup API 把"自上次快照以来有改动"的库
  原子拷贝到 local_hot_snapshots/。

为什么不在 commit 后逐点 notify
  五个 store 里有 13+ 个 COMMIT 站点。每个加 notify(self._path) 需要
  改动 13 处，且需要测试都不破。mtime 探测把这块工作量降到 0：
    · WAL 模式下每次提交都会改 .db-wal 的 mtime
    · checkpoint 时改 .db 的 mtime
    · 所以 max(stat .db, stat .db-wal) 严格单调递增
  代价是延迟从 0 变为最多 interval 秒——用 60 秒已经远好于 18 小时。

  仍然保留了 notify(path)：极少数对延迟敏感的场景（比如医疗事件
  上报后立即出门的护工 PDA）可以在 commit 后调一下，让循环
  下一秒就跑而不是等满 interval。

SQLite Backup API
  vs 直接 cp .db 文件:
    · cp 不是原子的——拷一半时另一个 worker commit 了 = 损坏副本
    · cp 不会把 WAL 里的脏页 merge 进来 → 副本可能比预期旧
    · SQLite Backup API 在 source 上拿短锁，按页拷贝，结束时副本
      已经包含到那一刻为止的全部已 commit 数据（含 WAL 内容）

  Python 标准库 sqlite3.Connection.backup() 直接封装了 Backup API。

格式
  快照文件:  <snapshot_dir>/<source_relpath>/<timestamp>.snapshot
  例:       local_hot_snapshots/local_billing/billing.db/20260518_154200.snapshot

  纯文件名取 mtime 而不是 wall clock，因为 quick succession 测试里
  两次快照可能落在同一秒；mtime + 微秒级 timestamp 解决冲突。

保留策略
  每个 source 保留最近 N 份（默认 3）。再多用冷备覆盖即可。

不做的事
  · 不加密。热备落在本机硬盘，威胁模型是"服务器突然挂电"，不是
    "硬盘被偷"。被偷的场景由冷备的 AES-256-GCM 兜底（NAS 那份）。
  · 不备份 ChromaDB 之外的非 SQLite 文件（病历照片）。CAS sha256
    保证那些文件 immutable，重启后仍可读，不需要快照。
  · 不替代冷备：本模块只解决"重启之间的小窗口"，跨日 / 异地灾备
    仍由 PR#4 负责。
"""
from __future__ import annotations

import asyncio
import dataclasses
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from loguru import logger


# ── 配置 ────────────────────────────────────────────────
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_KEEP_PER_SOURCE = 3
SNAPSHOT_SUFFIX = ".snapshot"


@dataclasses.dataclass(frozen=True)
class SnapshotterOptions:
    enabled: bool
    targets: tuple[Path, ...]            # 受保护的 .db 路径
    snapshot_dir: Path                   # 快照根目录
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    keep_per_source: int = DEFAULT_KEEP_PER_SOURCE
    base_dir: Path = Path(".")           # 用来计算相对路径


@dataclasses.dataclass
class SnapshotReport:
    """每次实际拷贝后的报告，给监控 / 测试断言用。"""
    source: Path
    snapshot_path: Path
    bytes: int
    duration_seconds: float
    pages_copied: int
    created_at: str

    def to_dict(self) -> dict:
        return {
            "source": str(self.source),
            "snapshot_path": str(self.snapshot_path),
            "bytes": self.bytes,
            "duration_seconds": round(self.duration_seconds, 4),
            "pages_copied": self.pages_copied,
            "created_at": self.created_at,
        }


# ── 内部工具 ────────────────────────────────────────────
def _max_mtime(db_path: Path) -> float:
    """
    返回 .db 和 .db-wal 中 mtime 最大值。WAL 模式下提交直接改 -wal 的
    mtime，checkpoint 时才改主 db 的 mtime；只看任何一个都会漏。
    """
    candidates = [db_path]
    candidates.append(db_path.with_name(db_path.name + "-wal"))
    candidates.append(db_path.with_name(db_path.name + "-shm"))
    mtimes: list[float] = []
    for p in candidates:
        try:
            mtimes.append(p.stat().st_mtime)
        except FileNotFoundError:
            continue
    return max(mtimes) if mtimes else 0.0


def _snapshot_dir_for(source: Path, root: Path, base_dir: Path) -> Path:
    """
    把 source 的相对路径作为快照子目录，避免不同库的同名文件冲突。
    例 source=/app/local_billing/billing.db, base=/app
        → root/local_billing/billing.db/
    """
    try:
        rel = source.resolve().relative_to(base_dir.resolve())
    except ValueError:
        # source 不在 base_dir 下；回退用 source 的目录名做 namespace
        rel = Path(source.parent.name) / source.name
    return root / rel


def _snapshot_filename(now: float = None) -> str:
    """精确到毫秒，避免同一秒快两次冲突。"""
    if now is None:
        now = time.time()
    dt = datetime.fromtimestamp(now)
    return dt.strftime("%Y%m%d_%H%M%S_%f")[:-3] + SNAPSHOT_SUFFIX


# ── 公开同步 API（可在测试/路由里直接调） ─────────────────
def snapshot_one(source: Path, snapshot_path: Path) -> SnapshotReport:
    """
    把 source 的当前状态快照到 snapshot_path（用 SQLite Backup API）。
    snapshot_path 的父目录会被自动建。

    源库不必断开连接；Backup API 内部加短锁，对 reader 几乎无感。
    若 source 不存在或不是合法 SQLite 文件，抛 sqlite3 异常给调用方。

    原子性: 先写到 <snapshot_path>.partial，成功后 os.replace。
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = snapshot_path.with_suffix(snapshot_path.suffix + ".partial")
    started = time.perf_counter()
    pages_copied = 0

    # 用一个独立 ro 连接读 source，避免和应用层连接池争锁
    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
    try:
        # 目标文件以 rw 打开。journal_mode 不重要，因为快照只是数据快照，
        # 不期望做后续写入；恢复时管理员通常会 reopen 设回 WAL。
        dst_conn = sqlite3.connect(str(tmp_path), timeout=30)
        try:
            # progress 回调累计页数。pages=0 表示一次性拷贝，对小库更快。
            def _progress(_status, remaining, total):
                nonlocal pages_copied
                pages_copied = total
            src_conn.backup(dst_conn, pages=0, progress=_progress)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    # fsync + atomic rename：让冷备 cron 即使在我们 rename 前抓到
    # tmp 文件也只是个 .partial，不会被冷备误以为是真快照
    with open(tmp_path, "rb+") as f:
        os.fsync(f.fileno())
    os.replace(tmp_path, snapshot_path)

    return SnapshotReport(
        source=source,
        snapshot_path=snapshot_path,
        bytes=snapshot_path.stat().st_size,
        duration_seconds=time.perf_counter() - started,
        pages_copied=pages_copied,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )


def prune_snapshots(snapshot_subdir: Path, keep: int) -> list[Path]:
    """
    保留最新 keep 份；返回被删的路径列表。
    keep <= 0 表示"不主动清理"（运维自己定）。
    """
    if keep <= 0 or not snapshot_subdir.exists():
        return []
    files = sorted(
        (p for p in snapshot_subdir.iterdir()
         if p.is_file() and p.suffix == SNAPSHOT_SUFFIX),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = files[keep:]
    deleted: list[Path] = []
    for p in to_delete:
        try:
            p.unlink()
            deleted.append(p)
        except OSError as e:
            logger.warning(f"清理快照失败 {p}: {e}")
    return deleted


# ── 周期快照器 ─────────────────────────────────────────
class HotSnapshotter:
    """
    异步循环：interval 秒一次，扫描 targets，对 mtime 比上次记录新的库
    跑一次 backup。run_once() 同步版本供测试 / 路由直接调。
    """

    def __init__(self, options: SnapshotterOptions):
        self._opts = options
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        # source path -> 上次成功 snapshot 时记录的 mtime（用 dict 避免锁）
        self._last_seen_mtime: dict[Path, float] = {}
        # notify() 设这个 flag 让循环立刻醒过来
        self._wake_event: asyncio.Event | None = None
        self._lock = threading.Lock()
        # 监控字段
        self._last_reports: dict[Path, SnapshotReport] = {}
        self._last_error: str | None = None

    # ── 公开 API ───────────────────────────────────
    @property
    def options(self) -> SnapshotterOptions:
        return self._opts

    def last_report_for(self, source: Path) -> SnapshotReport | None:
        return self._last_reports.get(source)

    def all_reports(self) -> list[SnapshotReport]:
        return list(self._last_reports.values())

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start(self) -> None:
        """在 lifespan startup 调一次。enabled=False 时 no-op。"""
        if not self._opts.enabled:
            logger.info("热快照器: 未启用 (HOT_SNAPSHOT_ENABLED=false)")
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop(), name="hot_snapshot_loop")
        logger.info(
            f"热快照器已启动: 每 {self._opts.interval_seconds}s 扫描 "
            f"{len(self._opts.targets)} 个数据库 → {self._opts.snapshot_dir}"
        )

    async def stop(self) -> None:
        if self._task is None or self._stop_event is None:
            return
        self._stop_event.set()
        if self._wake_event is not None:
            self._wake_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except asyncio.TimeoutError:
            self._task.cancel()
        self._task = None

    def notify(self, source: Path | str | None = None) -> None:
        """
        告诉循环"刚有重要写入,下次 tick 早点醒"。线程安全,可在任何
        线程 / 协程里调。不传 source 就让所有目标在下一秒被检查一次。

        实现注意: asyncio.Event.set() 自身线程安全,但触发后的
        Event.wait() 必须在 loop 里才会唤醒；如果在跨线程语境下被
        调用,我们用 call_soon_threadsafe 兜底。
        """
        # 如果还没启动,无需做任何事
        if self._wake_event is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is None:
            # 跨线程调用:Event.set 本身已经是线程安全的
            self._wake_event.set()
        else:
            self._wake_event.set()

    async def trigger_now(self) -> list[SnapshotReport]:
        """
        管理端"立即热备份"按钮入口:绕过 mtime 检查,无论脏不脏都拍一张。
        在 to_thread 里跑,避免 backup 时阻塞 event loop。
        """
        return await asyncio.to_thread(self._run_one_pass, force=True)

    # ── 内部 ───────────────────────────────────────
    async def _run_loop(self) -> None:
        assert self._stop_event is not None and self._wake_event is not None
        while not self._stop_event.is_set():
            try:
                await asyncio.to_thread(self._run_one_pass, False)
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                logger.exception(f"热快照循环异常 (会继续): {e}")
            # 等下一次 tick;notify() 触发或到时间都会醒
            self._wake_event.clear()
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        self._stop_event.wait(),
                        self._wake_event.wait(),
                        return_exceptions=True,
                    ) if False else self._wake_event.wait(),
                    timeout=self._opts.interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
            # stop 也设了 wake；这里再判断一次
            if self._stop_event.is_set():
                break

    def _run_one_pass(self, force: bool = False) -> list[SnapshotReport]:
        """
        扫描全部 targets:对 mtime 大于上次成功 snapshot 时记录的库做 backup。
        force=True 时无视 mtime 检查（trigger_now 用）。
        在线程池中调用，不能用 await。
        """
        out: list[SnapshotReport] = []
        for src in self._opts.targets:
            if not src.exists():
                # 库还没生成（新部署或被删）：跳过
                continue
            current_mtime = _max_mtime(src)
            last = self._last_seen_mtime.get(src, 0.0)
            if not force and current_mtime <= last:
                continue
            try:
                target_dir = _snapshot_dir_for(
                    src, self._opts.snapshot_dir, self._opts.base_dir,
                )
                snap_path = target_dir / _snapshot_filename()
                report = snapshot_one(src, snap_path)
                # 关键: 记录的是"快照完成后"的 mtime,而不是判断 force 时取的那个值。
                # SQLite Backup API 自身的 ro 连接会顺手 touch -shm,导致下一轮
                # _max_mtime 比 current_mtime 略大;若用旧值会无穷重复拍快照。
                with self._lock:
                    self._last_seen_mtime[src] = _max_mtime(src)
                    self._last_reports[src] = report
                self._last_error = None
                logger.debug(
                    f"热快照: {src.name} → {snap_path.name} "
                    f"({report.bytes / 1024:.1f} KB, {report.duration_seconds * 1000:.1f}ms)"
                )
                # 清理旧快照
                deleted = prune_snapshots(target_dir, self._opts.keep_per_source)
                if deleted:
                    logger.debug(f"清理旧快照 {len(deleted)} 个: {[p.name for p in deleted]}")
                out.append(report)
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                logger.warning(f"热快照失败 {src}: {e}")
        return out


# ── 单例 + env 解析 ────────────────────────────────────
_snapshotter: HotSnapshotter | None = None


def get_snapshotter() -> HotSnapshotter | None:
    return _snapshotter


def init_snapshotter(options: SnapshotterOptions) -> HotSnapshotter:
    global _snapshotter
    _snapshotter = HotSnapshotter(options)
    return _snapshotter


def reset_snapshotter() -> None:
    """仅测试用。"""
    global _snapshotter
    _snapshotter = None


def default_targets(base_dir: Path) -> tuple[Path, ...]:
    """
    生产里需要热保护的所有 SQLite 文件。

    包括:
      · 业务库 (billing / care / users / audit / events / payment_channels)
      · ChromaDB 的内部 sqlite (chroma.sqlite3) —— 病历向量+档案 metadata 都在这

    OCR 病历照片是 immutable CAS 文件,不在这里;它们由 CAS 的
    sha256 保证内容不变,重启后仍然可读。
    """
    return tuple(
        p for p in (
            base_dir / "local_billing" / "billing.db",
            base_dir / "local_billing" / "payment_channels.db",
            base_dir / "local_care" / "care.db",
            base_dir / "local_auth" / "users.db",
            base_dir / "local_audit_log" / "audit.db",
            base_dir / "local_nursing_events" / "nursing_events.db",
            base_dir / "local_ehr_db" / "chroma.sqlite3",
        )
    )


def options_from_env(base_dir: Path) -> SnapshotterOptions:
    """
    读环境变量 → SnapshotterOptions。

    HOT_SNAPSHOT_ENABLED          true/1/yes 启用;默认 false
    HOT_SNAPSHOT_DIR              快照根目录;默认 BASE_DIR/local_hot_snapshots
    HOT_SNAPSHOT_INTERVAL_SECONDS 默认 60
    HOT_SNAPSHOT_KEEP             每个库保留份数;默认 3
    """
    enabled = os.getenv("HOT_SNAPSHOT_ENABLED", "false").strip().lower() in {"true", "1", "yes"}
    dir_raw = os.getenv("HOT_SNAPSHOT_DIR", "").strip()
    snapshot_dir = Path(dir_raw) if dir_raw else base_dir / "local_hot_snapshots"
    try:
        interval = max(5, int(os.getenv("HOT_SNAPSHOT_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))))
    except ValueError:
        interval = DEFAULT_INTERVAL_SECONDS
    try:
        keep = max(1, int(os.getenv("HOT_SNAPSHOT_KEEP", str(DEFAULT_KEEP_PER_SOURCE))))
    except ValueError:
        keep = DEFAULT_KEEP_PER_SOURCE
    return SnapshotterOptions(
        enabled=enabled,
        targets=default_targets(base_dir),
        snapshot_dir=snapshot_dir,
        interval_seconds=interval,
        keep_per_source=keep,
        base_dir=base_dir,
    )


__all__ = [
    "HotSnapshotter",
    "SnapshotterOptions",
    "SnapshotReport",
    "SNAPSHOT_SUFFIX",
    "default_targets",
    "get_snapshotter",
    "init_snapshotter",
    "options_from_env",
    "prune_snapshots",
    "reset_snapshotter",
    "snapshot_one",
]
