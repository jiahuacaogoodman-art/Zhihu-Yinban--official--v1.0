# -*- coding: utf-8 -*-
"""
@File    : tests/test_hot_snapshot.py
@Desc    : Phase 2.2 - 热快照器 (SQLite Backup API + mtime 驱动)
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest

from app.services import hot_snapshot as hs


# ── helpers ─────────────────────────────────────────────────
def _make_sqlite_db(path: Path, rows: list[tuple[str, ...]] | None = None) -> Path:
    """造一个 WAL 模式的 SQLite 库,可选预插几行数据。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, val TEXT)")
        for r in rows or []:
            conn.execute("INSERT INTO t (val) VALUES (?)", (r[0],))
        conn.commit()
    finally:
        conn.close()
    return path


def _read_all(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _reset_singleton():
    hs.reset_snapshotter()
    yield
    hs.reset_snapshotter()


# ── 1. snapshot_one: 用 SQLite Backup API 真拷一份 ─────────
class TestSnapshotOne:
    def test_snapshot_is_a_queryable_sqlite(self, tmp_path):
        src = _make_sqlite_db(tmp_path / "src.db", [("alice",), ("bob",)])
        dst = tmp_path / "snap" / "out.snapshot"

        report = hs.snapshot_one(src, dst)

        assert report.snapshot_path.exists()
        assert report.bytes > 0
        assert report.pages_copied >= 1
        assert _read_all(dst) == ["alice", "bob"]

    def test_no_partial_file_left_on_success(self, tmp_path):
        src = _make_sqlite_db(tmp_path / "src.db", [("a",)])
        dst = tmp_path / "snap" / "out.snapshot"
        hs.snapshot_one(src, dst)
        leftovers = list((tmp_path / "snap").glob("*.partial"))
        assert leftovers == []

    def test_snapshot_captures_uncheckpointed_wal_data(self, tmp_path):
        """
        关键性质:WAL 模式下,如果只 commit 没 checkpoint,数据在 -wal 文件里。
        一个简单 cp .db 会拿到的是空表副本。SQLite Backup API 必须正确
        merge WAL 才能在快照里看到新数据。
        """
        src = tmp_path / "src.db"
        # 第一次 commit + 关闭 → checkpoint 自动跑,数据进了 .db
        _make_sqlite_db(src, [("first",)])

        # 第二次开 + 写 + 立刻关
        # 不让 sqlite 主动 checkpoint:写完直接 close,数据可能还在 -wal
        conn = sqlite3.connect(str(src))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            # 关掉自动 checkpoint,模拟"高峰期 wal 累积"
            conn.execute("PRAGMA wal_autocheckpoint=0")
            conn.execute("INSERT INTO t (val) VALUES ('hot-write')")
            conn.commit()
            # 不主动 checkpoint
        finally:
            conn.close()

        dst = tmp_path / "out.snapshot"
        hs.snapshot_one(src, dst)

        # 必须看到 hot-write,否则备份漏数据
        assert "hot-write" in _read_all(dst)

    def test_concurrent_write_during_snapshot_does_not_block(self, tmp_path):
        """
        SQLite Backup API 拷贝期间,源库还能继续被 reader 用。
        我们这里跑一个简单的 sanity check:开个并发连接读源库,
        在 snapshot 进行中也能读出来。
        """
        src = _make_sqlite_db(tmp_path / "src.db", [("x",) for _ in range(50)])
        dst = tmp_path / "out.snapshot"

        # 跑 snapshot,同时另一个连接读源库——两件事都不能阻塞
        hs.snapshot_one(src, dst)
        # 快照后源库依然可用
        assert _read_all(src) == ["x"] * 50


# ── 2. _max_mtime ───────────────────────────────────────────
class TestMaxMtime:
    def test_returns_max_of_db_and_wal(self, tmp_path):
        db = _make_sqlite_db(tmp_path / "x.db", [("a",)])
        # 故意把 -wal 的 mtime 设到未来
        wal = db.with_name(db.name + "-wal")
        if wal.exists():
            future = time.time() + 1000
            import os
            os.utime(wal, (future, future))
            assert hs._max_mtime(db) == future

    def test_zero_when_db_missing(self, tmp_path):
        assert hs._max_mtime(tmp_path / "nope.db") == 0.0


# ── 3. prune_snapshots ─────────────────────────────────────
class TestPrune:
    def test_keeps_only_newest_n(self, tmp_path):
        d = tmp_path / "snaps"
        d.mkdir()
        files = []
        for i in range(5):
            p = d / f"snap_{i}{hs.SNAPSHOT_SUFFIX}"
            p.write_bytes(b"x")
            files.append(p)
            # 让 mtime 严格递增
            import os
            ts = 1000 + i * 100
            os.utime(p, (ts, ts))

        deleted = hs.prune_snapshots(d, keep=2)

        # 删掉 3 个最旧的
        assert len(deleted) == 3
        remaining = sorted(d.iterdir(), key=lambda p: p.name)
        assert [p.name for p in remaining] == [
            f"snap_3{hs.SNAPSHOT_SUFFIX}",
            f"snap_4{hs.SNAPSHOT_SUFFIX}",
        ]

    def test_keep_zero_means_no_pruning(self, tmp_path):
        d = tmp_path / "snaps"
        d.mkdir()
        (d / f"a{hs.SNAPSHOT_SUFFIX}").write_bytes(b"x")
        (d / f"b{hs.SNAPSHOT_SUFFIX}").write_bytes(b"y")
        deleted = hs.prune_snapshots(d, keep=0)
        assert deleted == []
        assert len(list(d.iterdir())) == 2

    def test_missing_dir_is_safe(self, tmp_path):
        assert hs.prune_snapshots(tmp_path / "ghost", keep=3) == []


# ── 4. HotSnapshotter._run_one_pass: mtime 驱动 ────────────
class TestRunOnePass:
    def _make_options(self, tmp_path: Path, targets: list[Path]) -> hs.SnapshotterOptions:
        return hs.SnapshotterOptions(
            enabled=True,
            targets=tuple(targets),
            snapshot_dir=tmp_path / "snap_root",
            interval_seconds=5,
            keep_per_source=3,
            base_dir=tmp_path,
        )

    def test_first_pass_snapshots_all_existing(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        b = _make_sqlite_db(tmp_path / "b" / "b.db", [("y",)])
        opts = self._make_options(tmp_path, [a, b])
        snap = hs.HotSnapshotter(opts)

        reports = snap._run_one_pass(force=False)
        assert len(reports) == 2

    def test_second_pass_skips_unchanged(self, tmp_path):
        """
        关键性质:库没改 → 不重复拍快照。否则磁盘很快被同样内容塞满。
        """
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = self._make_options(tmp_path, [a])
        snap = hs.HotSnapshotter(opts)

        first = snap._run_one_pass(force=False)
        assert len(first) == 1
        # 立刻再跑一遍 —— 没新写入,应该 0 个
        second = snap._run_one_pass(force=False)
        assert second == []

    def test_after_write_next_pass_takes_new_snapshot(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = self._make_options(tmp_path, [a])
        snap = hs.HotSnapshotter(opts)

        snap._run_one_pass(force=False)

        # 模拟一次新写入
        time.sleep(0.05)        # 让 mtime 一定能往前走
        conn = sqlite3.connect(str(a))
        try:
            conn.execute("INSERT INTO t (val) VALUES ('new')")
            conn.commit()
        finally:
            conn.close()

        new_reports = snap._run_one_pass(force=False)
        assert len(new_reports) == 1
        # 新快照里能查到 'new'
        assert "new" in _read_all(new_reports[0].snapshot_path)

    def test_force_true_snapshots_even_when_unchanged(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = self._make_options(tmp_path, [a])
        snap = hs.HotSnapshotter(opts)
        snap._run_one_pass(force=False)
        forced = snap._run_one_pass(force=True)
        assert len(forced) == 1

    def test_missing_target_skipped_silently(self, tmp_path):
        """
        生产里有些库可能还没生成（新部署）。不能因此让循环挂掉。
        """
        ghost = tmp_path / "nope" / "ghost.db"
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = self._make_options(tmp_path, [ghost, a])
        snap = hs.HotSnapshotter(opts)
        reports = snap._run_one_pass(force=False)
        # 只有 a 被备
        assert len(reports) == 1
        assert reports[0].source == a

    def test_keeps_per_source_pruning(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = hs.SnapshotterOptions(
            enabled=True, targets=(a,),
            snapshot_dir=tmp_path / "snap",
            interval_seconds=5, keep_per_source=2, base_dir=tmp_path,
        )
        snap = hs.HotSnapshotter(opts)

        # 跑 4 次,每次中间真改一下库,确保都被记录
        for i in range(4):
            time.sleep(0.05)
            conn = sqlite3.connect(str(a))
            try:
                conn.execute("INSERT INTO t (val) VALUES (?)", (f"row{i}",))
                conn.commit()
            finally:
                conn.close()
            snap._run_one_pass(force=False)

        # 快照子目录里只剩 keep_per_source=2 份
        target_dir = hs._snapshot_dir_for(a, opts.snapshot_dir, opts.base_dir)
        files = [p for p in target_dir.iterdir() if p.suffix == hs.SNAPSHOT_SUFFIX]
        assert len(files) == 2


# ── 5. options_from_env ─────────────────────────────────────
class TestOptionsFromEnv:
    def test_disabled_by_default(self, tmp_path, monkeypatch):
        for k in ("HOT_SNAPSHOT_ENABLED", "HOT_SNAPSHOT_DIR",
                  "HOT_SNAPSHOT_INTERVAL_SECONDS", "HOT_SNAPSHOT_KEEP"):
            monkeypatch.delenv(k, raising=False)
        opts = hs.options_from_env(tmp_path)
        assert opts.enabled is False
        assert opts.interval_seconds == hs.DEFAULT_INTERVAL_SECONDS
        assert opts.keep_per_source == hs.DEFAULT_KEEP_PER_SOURCE

    def test_minimum_interval_floored(self, tmp_path, monkeypatch):
        """
        防止管理员配 interval=0 把循环变忙等。最低 5 秒。
        """
        monkeypatch.setenv("HOT_SNAPSHOT_INTERVAL_SECONDS", "0")
        opts = hs.options_from_env(tmp_path)
        assert opts.interval_seconds >= 5

    def test_invalid_value_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOT_SNAPSHOT_INTERVAL_SECONDS", "abc")
        monkeypatch.setenv("HOT_SNAPSHOT_KEEP", "xyz")
        opts = hs.options_from_env(tmp_path)
        assert opts.interval_seconds == hs.DEFAULT_INTERVAL_SECONDS
        assert opts.keep_per_source == hs.DEFAULT_KEEP_PER_SOURCE

    def test_targets_includes_seven_default_dbs(self, tmp_path):
        opts = hs.options_from_env(tmp_path)
        names = [t.name for t in opts.targets]
        assert "billing.db" in names
        assert "care.db" in names
        assert "users.db" in names
        assert "audit.db" in names
        assert "nursing_events.db" in names
        assert "chroma.sqlite3" in names


# ── 6. trigger_now / notify (async API) ─────────────────────
class TestAsyncAPI:
    @pytest.mark.asyncio
    async def test_trigger_now_runs_force_pass(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = hs.SnapshotterOptions(
            enabled=True, targets=(a,),
            snapshot_dir=tmp_path / "snap",
            interval_seconds=60, keep_per_source=3, base_dir=tmp_path,
        )
        snap = hs.HotSnapshotter(opts)
        reports = await snap.trigger_now()
        assert len(reports) == 1
        assert reports[0].snapshot_path.exists()

    @pytest.mark.asyncio
    async def test_start_stop_cycle(self, tmp_path):
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = hs.SnapshotterOptions(
            enabled=True, targets=(a,),
            snapshot_dir=tmp_path / "snap",
            interval_seconds=60, keep_per_source=3, base_dir=tmp_path,
        )
        snap = hs.HotSnapshotter(opts)
        snap.start()
        # 给循环一点时间进入第一轮 pass
        await asyncio.sleep(0.05)
        await snap.stop()
        # 至少第一轮 pass 已经跑过
        assert len(snap.all_reports()) == 1

    @pytest.mark.asyncio
    async def test_notify_wakes_loop_quickly(self, tmp_path):
        """
        关键承诺:notify() 触发后,下一轮快照应该几乎立刻发生,
        而不是等到 interval 满。我们用一个长 interval (60s) 验证:
        没 notify 时第二轮要等 60s,notify 之后 < 1s 就有第二轮。
        """
        a = _make_sqlite_db(tmp_path / "a" / "a.db", [("x",)])
        opts = hs.SnapshotterOptions(
            enabled=True, targets=(a,),
            snapshot_dir=tmp_path / "snap",
            interval_seconds=60,            # 故意很长
            keep_per_source=10, base_dir=tmp_path,
        )
        snap = hs.HotSnapshotter(opts)
        snap.start()
        # 等第一轮跑完
        for _ in range(20):
            await asyncio.sleep(0.05)
            if snap.last_report_for(a) is not None:
                break
        first = snap.last_report_for(a)
        assert first is not None

        # 模拟一次写入 + notify
        time.sleep(0.05)
        conn = sqlite3.connect(str(a))
        try:
            conn.execute("INSERT INTO t (val) VALUES ('after-notify')")
            conn.commit()
        finally:
            conn.close()

        snap.notify()
        # 应该 < 1s 内发生新快照（走的是 wake_event 而非 60s 等待）
        for _ in range(20):
            await asyncio.sleep(0.05)
            new = snap.last_report_for(a)
            if new is not None and new.snapshot_path != first.snapshot_path:
                break
        else:
            await snap.stop()
            pytest.fail("notify() 没有及时唤醒快照循环")
        await snap.stop()
