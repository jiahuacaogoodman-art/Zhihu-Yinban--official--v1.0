# -*- coding: utf-8 -*-
"""
@File    : tests/test_file_store.py
@Desc    : Phase 1.2 - 内容寻址文件仓 FileStore
"""
from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.file_store import FileStore, get_file_store, reset_file_store


@pytest.fixture(autouse=True)
def _reset():
    reset_file_store()
    yield
    reset_file_store()


# ── 基本 put/get/verify ────────────────────────────────────
class TestPut:
    def test_writes_file_with_sha256_path(self, tmp_path):
        fs = FileStore(tmp_path)
        content = b"hello world"
        sha = hashlib.sha256(content).hexdigest()

        result = fs.put(content, suffix="jpg")

        assert result.sha256 == sha
        assert result.size == len(content)
        assert result.deduped is False
        # 路径形态：<root>/sha/<aa>/<bb>/<sha>.jpg
        assert result.path.exists()
        rel = result.path.relative_to(tmp_path).as_posix()
        assert rel.startswith("sha/")
        assert rel.endswith(".jpg")
        assert sha[:2] in rel
        assert sha[2:4] in rel

    def test_dedup_returns_existing_file_without_writing(self, tmp_path):
        fs = FileStore(tmp_path)
        content = b"X" * 1024

        first = fs.put(content)
        # 篡改文件 mtime 让我们能看到第二次没有真的写
        first_mtime_ns = first.path.stat().st_mtime_ns

        second = fs.put(content)

        assert second.deduped is True
        assert second.sha256 == first.sha256
        assert second.path == first.path
        # 第二次 put 没改变文件 → mtime 没动
        assert second.path.stat().st_mtime_ns == first_mtime_ns

    def test_different_content_different_path(self, tmp_path):
        fs = FileStore(tmp_path)
        a = fs.put(b"alpha", suffix="png")
        b = fs.put(b"beta", suffix="png")
        assert a.path != b.path
        assert a.sha256 != b.sha256

    def test_suffix_is_normalized(self, tmp_path):
        fs = FileStore(tmp_path)
        # ".jpg" / "jpg" / ".JPG" 都应该归一化到 .jpg
        a = fs.put(b"data1", suffix=".jpg")
        b = fs.put(b"data2", suffix="jpg")
        c = fs.put(b"data3", suffix=".JPG")
        for r in (a, b, c):
            assert r.path.suffix == ".jpg"

    def test_url_prefix_in_rel_url(self, tmp_path):
        fs = FileStore(tmp_path, url_prefix="/uploads")
        r = fs.put(b"x", suffix="jpg")
        assert r.rel_url.startswith("/uploads/sha/")

    def test_rejects_non_bytes(self, tmp_path):
        fs = FileStore(tmp_path)
        with pytest.raises(TypeError):
            fs.put("a string", suffix="jpg")  # type: ignore[arg-type]

    def test_atomic_write_no_tmp_left_on_success(self, tmp_path):
        fs = FileStore(tmp_path)
        fs.put(b"data", suffix="png")
        # 整棵树里不能残留 .tmp 文件
        leftovers = list(tmp_path.rglob("*.tmp"))
        assert leftovers == []


# ── verify / get / delete ──────────────────────────────────
class TestVerifyAndDelete:
    def test_verify_passes_for_intact_file(self, tmp_path):
        fs = FileStore(tmp_path)
        r = fs.put(b"data", suffix="jpg")
        assert fs.verify(r.sha256, suffix="jpg") is True

    def test_verify_fails_for_corrupted_file(self, tmp_path):
        fs = FileStore(tmp_path)
        r = fs.put(b"data", suffix="jpg")
        # 模拟磁盘损坏：覆盖文件内容
        r.path.write_bytes(b"corrupted")
        assert fs.verify(r.sha256, suffix="jpg") is False

    def test_verify_fails_for_missing_file(self, tmp_path):
        fs = FileStore(tmp_path)
        # 没存过的 sha 直接 verify
        fake_sha = "0" * 64
        assert fs.verify(fake_sha, suffix="jpg") is False

    def test_get_returns_none_for_missing(self, tmp_path):
        fs = FileStore(tmp_path)
        assert fs.get("0" * 64, suffix="jpg") is None

    def test_get_returns_path_for_existing(self, tmp_path):
        fs = FileStore(tmp_path)
        r = fs.put(b"data", suffix="jpg")
        got = fs.get(r.sha256, suffix="jpg")
        assert got == r.path

    def test_delete_removes_file_and_empty_buckets(self, tmp_path):
        fs = FileStore(tmp_path)
        r = fs.put(b"data", suffix="jpg")
        bucket_l1 = r.path.parent.parent
        bucket_l2 = r.path.parent

        assert fs.delete(r.sha256, suffix="jpg") is True
        assert not r.path.exists()
        # 桶变空 → 顺便清理
        assert not bucket_l2.exists()
        assert not bucket_l1.exists()

    def test_delete_returns_false_for_missing(self, tmp_path):
        fs = FileStore(tmp_path)
        assert fs.delete("0" * 64, suffix="jpg") is False


# ── 并发 put 同一 sha ──────────────────────────────────────
class TestConcurrentPut:
    def test_two_threads_putting_same_content_both_succeed(self, tmp_path):
        """
        两个线程同时 put 同一份内容，最后只留一份物理文件，
        且任何一个线程都不能拿到损坏的中间产物。
        """
        fs = FileStore(tmp_path)
        content = b"Z" * (1024 * 16)  # 16 KB，让写入有点真实耗时
        latch = threading.Event()
        results = []
        errors = []

        def worker():
            latch.wait()
            try:
                r = fs.put(content, suffix="bin")
                results.append(r)
            except BaseException as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(worker) for _ in range(8)]
            latch.set()
            for f in futures:
                f.result()

        assert errors == []
        assert len(results) == 8
        # 所有线程都拿到同一个 path
        unique_paths = {r.path for r in results}
        assert len(unique_paths) == 1
        # 文件内容正确（没被半写覆盖）
        only = next(iter(unique_paths))
        assert only.read_bytes() == content


# ── stats ──────────────────────────────────────────────────
class TestStats:
    def test_stats_counts_only_persisted_files(self, tmp_path):
        fs = FileStore(tmp_path)
        fs.put(b"a", suffix="jpg")
        fs.put(b"b", suffix="jpg")
        fs.put(b"a", suffix="jpg")  # dedup → 仍然 2 个文件

        s = fs.stats()
        assert s["files"] == 2
        assert s["bytes"] == 2  # 'a' 和 'b' 各 1 字节


# ── singleton ──────────────────────────────────────────────
class TestSingleton:
    def test_get_file_store_returns_same_instance(self, tmp_path):
        fs1 = get_file_store(tmp_path)
        fs2 = get_file_store(tmp_path)
        assert fs1 is fs2

    def test_reset_clears_singleton(self, tmp_path):
        fs1 = get_file_store(tmp_path)
        reset_file_store()
        fs2 = get_file_store(tmp_path)
        assert fs1 is not fs2
