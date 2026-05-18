# -*- coding: utf-8 -*-
"""
@File    : tests/test_backup.py
@Desc    : Phase 2.2 - 冷备份核心 (打包 / AES-256-GCM / 校验 / 恢复)
"""
from __future__ import annotations

import base64
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.services import backup as bk


# ── helpers ────────────────────────────────────────────────
def _make_data_dir(tmp_path: Path, name: str, files: dict[str, bytes]) -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return d


def _make_key() -> bytes:
    return os.urandom(32)


# ── 1. parse_key ────────────────────────────────────────────
class TestParseKey:
    def test_hex_64_chars(self):
        raw = "00" * 32
        assert bk.parse_key(raw) == b"\x00" * 32

    def test_urlsafe_b64(self):
        key = os.urandom(32)
        raw = base64.urlsafe_b64encode(key).decode()
        assert bk.parse_key(raw) == key

    def test_standard_b64(self):
        key = os.urandom(32)
        raw = base64.b64encode(key).decode()
        assert bk.parse_key(raw) == key

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="未配置"):
            bk.parse_key("")

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            bk.parse_key("deadbeef" * 4)  # 只有 32 hex chars = 16 bytes

    def test_with_whitespace_trimmed(self):
        key = os.urandom(32)
        raw = "  " + base64.urlsafe_b64encode(key).decode() + "  \n"
        assert bk.parse_key(raw) == key


# ── 2. derive_key_from_passphrase ──────────────────────────
class TestDerive:
    def test_deterministic(self):
        salt = b"x" * 16
        a = bk.derive_key_from_passphrase("hunter2", salt)
        b = bk.derive_key_from_passphrase("hunter2", salt)
        assert a == b
        assert len(a) == 32

    def test_different_salts_different_keys(self):
        a = bk.derive_key_from_passphrase("hunter2", b"a" * 16)
        b = bk.derive_key_from_passphrase("hunter2", b"b" * 16)
        assert a != b

    def test_short_salt_rejected(self):
        with pytest.raises(ValueError):
            bk.derive_key_from_passphrase("x", b"too short")


# ── 3. create_backup + verify_backup roundtrip ─────────────
class TestBackupRoundtrip:
    def test_create_and_verify(self, tmp_path):
        src = _make_data_dir(tmp_path, "local_billing", {
            "billing.db": b"fake-sqlite",
            "x/extra.txt": b"hello",
        })
        target = tmp_path / "backups"
        key = _make_key()

        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=target,
            encryption_key=key,
        )
        report = bk.create_backup(cfg)

        # 备份文件存在 + 大小合理
        assert report.path.exists()
        assert report.size > 100
        assert report.path.name.endswith(bk.BACKUP_FILE_EXT)
        # .partial 不应残留
        assert not list(target.glob("*.partial"))

        # verify_backup 能成功 + manifest 正确
        manifest = bk.verify_backup(report.path, key)
        assert manifest["version"] == bk.MODULE_VERSION
        assert any(s["path"].endswith("local_billing") for s in manifest["sources"])
        # 文件数 = 2 (billing.db + x/extra.txt)
        for s in manifest["sources"]:
            if s["path"].endswith("local_billing"):
                assert s["files"] == 2
                assert s["bytes"] == len(b"fake-sqlite") + len(b"hello")

    def test_wrong_key_fails(self, tmp_path):
        src = _make_data_dir(tmp_path, "data", {"f.bin": b"x"})
        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=tmp_path / "out",
            encryption_key=_make_key(),
        )
        report = bk.create_backup(cfg)

        wrong_key = _make_key()
        with pytest.raises(Exception):
            bk.verify_backup(report.path, wrong_key)

    def test_tampered_blob_fails(self, tmp_path):
        """
        AESGCM 是 AEAD，篡改 1 字节就解密失败。
        这是"军事级灾备"承诺的核心：备份内容损坏永远不会被静默接受。
        """
        src = _make_data_dir(tmp_path, "data", {"f.bin": b"x" * 1000})
        key = _make_key()
        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=tmp_path / "out",
            encryption_key=key,
        )
        report = bk.create_backup(cfg)

        blob = report.path.read_bytes()
        # 翻转 ciphertext 中段一个字节（避开 magic + nonce）
        idx = len(bk.MAGIC) + bk.NONCE_LEN + 50
        tampered = bytearray(blob)
        tampered[idx] ^= 0x01
        report.path.write_bytes(bytes(tampered))

        with pytest.raises(Exception):
            bk.verify_backup(report.path, key)

    def test_restore_extracts_to_dest(self, tmp_path):
        src = _make_data_dir(tmp_path, "data", {
            "a.txt": b"alpha",
            "sub/b.txt": b"beta",
        })
        key = _make_key()
        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=tmp_path / "out",
            encryption_key=key,
        )
        report = bk.create_backup(cfg)

        dest = tmp_path / "restored"
        manifest = bk.restore_backup(report.path, key, dest)

        assert (dest / "data" / "a.txt").read_bytes() == b"alpha"
        assert (dest / "data" / "sub" / "b.txt").read_bytes() == b"beta"
        assert manifest["version"] == bk.MODULE_VERSION


# ── 4. WAL/SHM 副产物被跳过 ────────────────────────────────
class TestSkipsWalShm:
    def test_skips_sqlite_wal_and_shm(self, tmp_path):
        """
        SQLite WAL 备份时不应纳入 -wal / -shm 文件——这俩是临时副本，
        恢复时会让 SQLite 拒绝打开主库。
        """
        src = tmp_path / "local_care"
        src.mkdir()
        (src / "care.db").write_bytes(b"main")
        (src / "care.db-wal").write_bytes(b"wal-content")
        (src / "care.db-shm").write_bytes(b"shm-content")
        (src / "tmp.tmp").write_bytes(b"tmp-content")

        key = _make_key()
        cfg = bk.BackupConfig(sources=(src,), target_dir=tmp_path / "o", encryption_key=key)
        report = bk.create_backup(cfg)
        manifest = bk.verify_backup(report.path, key)

        for s in manifest["sources"]:
            if s["path"].endswith("local_care"):
                # 只有 care.db 被打进去
                assert s["files"] == 1
                assert s["bytes"] == 4   # b"main"


# ── 5. retention 清理 ──────────────────────────────────────
class TestRetention:
    def test_old_backups_deleted(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        # 模拟旧备份（mtime = 30 天前）
        old_files = []
        for i in range(3):
            f = target / f"zhihu-yinban_2026010{i}_030000{bk.BACKUP_FILE_EXT}"
            f.write_bytes(b"x")
            os.utime(f, (0, 0))   # mtime = 1970，绝对超出 retention
            old_files.append(f)

        src = _make_data_dir(tmp_path, "data", {"a": b"a"})
        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=target,
            encryption_key=_make_key(),
            retention_days=7,
        )
        report = bk.create_backup(cfg)

        assert len(report.deleted_old) == 3
        for old in old_files:
            assert not old.exists()
        # 新备份保留
        assert report.path.exists()

    def test_retention_zero_keeps_everything(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        old = target / f"zhihu-yinban_old{bk.BACKUP_FILE_EXT}"
        old.write_bytes(b"x")
        os.utime(old, (0, 0))

        src = _make_data_dir(tmp_path, "data", {"a": b"a"})
        cfg = bk.BackupConfig(
            sources=(src,),
            target_dir=target,
            encryption_key=_make_key(),
            retention_days=0,
        )
        report = bk.create_backup(cfg)

        assert report.deleted_old == []
        assert old.exists()


# ── 6. 缺源目录不阻塞 ──────────────────────────────────────
class TestMissingSources:
    def test_missing_source_marked_in_manifest_no_crash(self, tmp_path):
        """
        生产里某些目录可能尚未生成（比如新部署还没有 local_audit_log）。
        备份必须忍受缺失，manifest 里如实标记 exists=False。
        """
        existing = _make_data_dir(tmp_path, "exists", {"a.txt": b"a"})
        missing = tmp_path / "ghost"  # 不创建

        cfg = bk.BackupConfig(
            sources=(existing, missing),
            target_dir=tmp_path / "out",
            encryption_key=_make_key(),
        )
        report = bk.create_backup(cfg)
        manifest = bk.verify_backup(report.path, cfg.encryption_key)

        by_path = {s["path"]: s for s in manifest["sources"]}
        assert by_path[str(existing)]["exists"] is True
        assert by_path[str(missing)]["exists"] is False
        assert by_path[str(missing)]["files"] == 0


# ── 7. list_backups ────────────────────────────────────────
class TestListBackups:
    def test_returns_only_matching_files_sorted(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        # 我们的备份 — 用 utime 显式控制 mtime，避免同纳秒落地导致排序不稳定
        f1 = target / f"zhihu-yinban_20260101_030000{bk.BACKUP_FILE_EXT}"
        f2 = target / f"zhihu-yinban_20260102_030000{bk.BACKUP_FILE_EXT}"
        f1.write_bytes(b"a")
        f2.write_bytes(b"b")
        os.utime(f1, (1735689600, 1735689600))   # 2025-01-01
        os.utime(f2, (1735776000, 1735776000))   # 2025-01-02
        # 其他文件——不应进列表
        (target / "random.txt").write_bytes(b"x")
        (target / f"some-other-prefix{bk.BACKUP_FILE_EXT}").write_bytes(b"y")

        result = bk.list_backups(target)
        names = [r["filename"] for r in result]
        assert names == [
            f"zhihu-yinban_20260102_030000{bk.BACKUP_FILE_EXT}",
            f"zhihu-yinban_20260101_030000{bk.BACKUP_FILE_EXT}",
        ]

    def test_missing_target_returns_empty(self, tmp_path):
        assert bk.list_backups(tmp_path / "nope") == []


# ── 8. 真正的 SQLite 库往返恢复 ─────────────────────────────
class TestRealSqliteRoundtrip:
    """
    这是关键集成测试：备份恢复后的 SQLite 必须能正常打开 + 读出原始数据。
    任何破坏 SQLite 文件结构的改动（比如错误的 tar mode、错误的解码）
    都会让这个测试失败。
    """

    def test_real_sqlite_roundtrip(self, tmp_path):
        # 1) 建一个真 SQLite 库写两行
        src_dir = tmp_path / "local_billing"
        src_dir.mkdir()
        db_path = src_dir / "billing.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t (name) VALUES ('alice'), ('bob')")
        conn.commit()
        conn.close()

        # 2) 备份
        key = _make_key()
        cfg = bk.BackupConfig(
            sources=(src_dir,),
            target_dir=tmp_path / "out",
            encryption_key=key,
        )
        report = bk.create_backup(cfg)

        # 3) 恢复到新位置
        restored = tmp_path / "restored"
        bk.restore_backup(report.path, key, restored)

        restored_db = restored / "local_billing" / "billing.db"
        assert restored_db.exists()

        conn2 = sqlite3.connect(str(restored_db))
        rows = conn2.execute("SELECT name FROM t ORDER BY id").fetchall()
        conn2.close()
        assert [r[0] for r in rows] == ["alice", "bob"]


# ── 9. default_sources ─────────────────────────────────────
class TestDefaultSources:
    def test_includes_all_seven_data_dirs(self, tmp_path):
        srcs = bk.default_sources(tmp_path)
        names = [s.name for s in srcs]
        assert "local_ehr_db" in names
        assert "local_ehr_uploads" in names
        assert "local_billing" in names
        assert "local_care" in names
        assert "local_auth" in names
        assert "local_audit_log" in names
        assert "local_nursing_events" in names
