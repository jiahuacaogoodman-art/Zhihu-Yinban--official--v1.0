# -*- coding: utf-8 -*-
"""
@File    : tests/test_db_helper.py
@Desc    : Phase 1.1 db helper 测试
           - PRAGMA busy_timeout 真的设上了
           - @with_db_retry 对 locked 错误指数退避，对其他错误立即抛
           - 多线程并发写不会再裸抛 "database is locked"
"""
from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import db


# ── 1. connect() 行为 ───────────────────────────────────────
class TestConnect:
    def test_pragma_busy_timeout_is_set(self, tmp_path):
        conn = db.connect(tmp_path / "x.db")
        try:
            v = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()
        # 默认 5000，且必须 >= 1000（再快就不算"等锁"了）
        assert v >= 1000

    def test_journal_mode_is_wal(self, tmp_path):
        conn = db.connect(tmp_path / "x.db")
        try:
            v = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        assert v.lower() == "wal"

    def test_foreign_keys_off_by_default(self, tmp_path):
        conn = db.connect(tmp_path / "x.db")
        try:
            v = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        finally:
            conn.close()
        assert v == 0

    def test_foreign_keys_on_when_requested(self, tmp_path):
        conn = db.connect(tmp_path / "x.db", foreign_keys=True)
        try:
            v = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        finally:
            conn.close()
        assert v == 1

    def test_row_factory_returns_named_rows(self, tmp_path):
        conn = db.connect(tmp_path / "x.db")
        try:
            conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'hi')")
            row = conn.execute("SELECT * FROM t").fetchone()
            assert row["a"] == 1
            assert row["b"] == "hi"
        finally:
            conn.close()


# ── 2. is_locked_error ──────────────────────────────────────
class TestIsLockedError:
    def test_locked_oerror_matches(self):
        e = sqlite3.OperationalError("database is locked")
        assert db.is_locked_error(e)

    def test_table_locked_matches(self):
        e = sqlite3.OperationalError("database table is locked: foo")
        assert db.is_locked_error(e)

    def test_other_oerror_does_not_match(self):
        e = sqlite3.OperationalError("disk I/O error")
        assert not db.is_locked_error(e)

    def test_non_oerror_does_not_match(self):
        # IntegrityError 不重试
        e = sqlite3.IntegrityError("UNIQUE constraint failed")
        assert not db.is_locked_error(e)
        e2 = ValueError("foo")
        assert not db.is_locked_error(e2)


# ── 3. @with_db_retry ───────────────────────────────────────
class TestRetryDecorator:
    def test_succeeds_on_first_try(self):
        calls = {"n": 0}

        @db.with_db_retry()
        def f():
            calls["n"] += 1
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 1

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        @db.with_db_retry(base_delay=0.001, jitter=0)
        def f():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 3

    def test_gives_up_after_max_attempts(self):
        calls = {"n": 0}

        @db.with_db_retry(max_attempts=3, base_delay=0.001, jitter=0)
        def f():
            calls["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            f()
        assert calls["n"] == 3

    def test_does_not_retry_non_locked_oerror(self):
        """disk I/O error 等致命错误立即抛，不浪费时间退避。"""
        calls = {"n": 0}

        @db.with_db_retry(base_delay=0.001)
        def f():
            calls["n"] += 1
            raise sqlite3.OperationalError("disk I/O error")

        with pytest.raises(sqlite3.OperationalError, match="disk"):
            f()
        assert calls["n"] == 1

    def test_does_not_retry_integrity_error(self):
        """UNIQUE 约束等业务错误必须立即抛——重试会破坏幂等性。"""
        calls = {"n": 0}

        @db.with_db_retry(base_delay=0.001)
        def f():
            calls["n"] += 1
            raise sqlite3.IntegrityError("UNIQUE constraint failed")

        with pytest.raises(sqlite3.IntegrityError):
            f()
        assert calls["n"] == 1

    def test_preserves_signature_via_functools_wraps(self):
        @db.with_db_retry()
        def my_func(a, b):
            """docstring"""
            return a + b

        assert my_func.__name__ == "my_func"
        assert "docstring" in (my_func.__doc__ or "")
        assert my_func(2, 3) == 5

    def test_method_decoration_works(self):
        class Foo:
            @db.with_db_retry(base_delay=0.001, jitter=0)
            def bar(self, x):
                return x * 2

        assert Foo().bar(5) == 10


# ── 4. 集成：多线程并发写不再裸抛 locked ────────────────────
#
# 这是 Phase 1.1 的核心承诺：早高峰 50-100 并发打卡不再 500。
# 用 EventStore 模拟 N 个线程同时调 save_event。
class TestConcurrentWriteSurvivesContention:
    def test_concurrent_save_event(self, tmp_path):
        from app.services.event_store import EventStore

        store = EventStore(tmp_path / "concurrent.db")

        N = 60        # 60 并发，比单院预期峰值还高
        errors: list[BaseException] = []
        latch = threading.Event()

        def writer(i: int):
            # 让所有线程"同时起跑"，最大化锁争抢
            latch.wait()
            try:
                store.save_event(
                    {
                        "event_id": f"ev_{i}",
                        "patient_id": f"p_{i % 10}",
                        "status": "processing",
                        "created_at": "2026-05-18 10:00:00",
                        "payload": "x" * 200,
                    }
                )
            except BaseException as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=N) as ex:
            futures = [ex.submit(writer, i) for i in range(N)]
            time.sleep(0.05)
            latch.set()
            for f in futures:
                f.result()

        # 不能有任何 locked 异常逃逸到调用方
        assert errors == [], f"并发写出现错误: {errors[:3]}"
        # 60 条事件都落库
        assert len(store.load_events()) == N
