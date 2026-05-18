# -*- coding: utf-8 -*-
"""
@File    : tests/test_sync_agent.py
@Desc    : sync_agent 守护进程 - 配置 / outbox / 推送 / mTLS context

涵盖
  · SyncConfig.from_env: env 变量解析 + dry-run / enabled 校验
  · validate(): 错误配置返回完整错误列表
  · write_outbox / list_outbox / mark_sent: 原子持久化 + 顺序 + sent/ 移动
  · drain_outbox: 部分成功的处理(发到失败那条就停)
  · push_payload 失败路径(httpx 抛错 → 静默返 False)
  · build_ssl_context: 非空 cert/key 时正确加载 (用 self-signed 测)
  · main(--once): 端到端但不真发网络
"""
from __future__ import annotations

import importlib.util
import json
import os
import ssl
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# 项目根目录里的 sync_agent.py 在 sys.path 默认看不到;手动加进去
_PROJ = Path(__file__).resolve().parents[1]
if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))

import sync_agent as agent          # noqa: E402


# ── 1. SyncConfig.from_env ─────────────────────────────────
class TestConfigFromEnv:
    def test_disabled_by_default(self, monkeypatch):
        for k in list(os.environ):
            if k.startswith("SYNC_"):
                monkeypatch.delenv(k, raising=False)
        cfg = agent.SyncConfig.from_env()
        assert cfg.enabled is False
        assert cfg.branch_id == "main"
        assert cfg.interval_seconds == 3600

    def test_minimum_interval_floored(self, monkeypatch):
        monkeypatch.setenv("SYNC_INTERVAL_SECONDS", "10")
        cfg = agent.SyncConfig.from_env()
        # 最低 60 秒,防止配 1 把 CPU 烧光
        assert cfg.interval_seconds >= 60

    def test_cert_paths_parsed(self, tmp_path, monkeypatch):
        cert = tmp_path / "client.crt"
        key = tmp_path / "client.key"
        ca = tmp_path / "ca.pem"
        for p in (cert, key, ca):
            p.write_text("dummy")
        monkeypatch.setenv("SYNC_ENABLED", "true")
        monkeypatch.setenv("SYNC_CLOUD_URL", "https://cloud.example.com/")
        monkeypatch.setenv("SYNC_CLIENT_CERT", str(cert))
        monkeypatch.setenv("SYNC_CLIENT_KEY", str(key))
        monkeypatch.setenv("SYNC_CA_BUNDLE", str(ca))

        cfg = agent.SyncConfig.from_env()
        assert cfg.enabled is True
        # URL 末尾斜杠应被去掉
        assert cfg.cloud_url == "https://cloud.example.com"
        assert cfg.client_cert == cert
        assert cfg.client_key == key
        assert cfg.ca_bundle == ca


# ── 2. validate ────────────────────────────────────────────
class TestValidate:
    def test_disabled_no_errors(self):
        cfg = agent.SyncConfig(enabled=False)
        assert cfg.validate() == []

    def test_enabled_missing_url_errors(self, tmp_path):
        cfg = agent.SyncConfig(
            enabled=True, cloud_url="",
            client_cert=tmp_path / "c", client_key=tmp_path / "k",
        )
        # url + cert 都不存在 → 两条错误
        errs = cfg.validate()
        assert any("SYNC_CLOUD_URL" in e for e in errs)

    def test_enabled_missing_cert_errors(self):
        cfg = agent.SyncConfig(
            enabled=True, cloud_url="https://x.com",
            client_cert=None, client_key=None,
        )
        errs = cfg.validate()
        assert any("SYNC_CLIENT_CERT" in e for e in errs)

    def test_enabled_with_nonexistent_files_errors(self, tmp_path):
        cfg = agent.SyncConfig(
            enabled=True, cloud_url="https://x.com",
            client_cert=tmp_path / "missing.crt",
            client_key=tmp_path / "missing.key",
        )
        errs = cfg.validate()
        assert any("不存在" in e for e in errs)


# ── 3. outbox helpers ──────────────────────────────────────
class TestOutbox:
    def test_write_outbox_atomic(self, tmp_path):
        path = agent.write_outbox(tmp_path, {"hello": "world"})
        assert path.exists()
        assert path.suffix == ".json"
        # 不应留下 .partial
        assert not list(tmp_path.glob("*.partial"))
        # 内容可读回
        assert json.loads(path.read_text())["hello"] == "world"

    def test_list_outbox_sorted_by_mtime(self, tmp_path):
        # 依次创建 3 个,显式 mtime
        a = agent.write_outbox(tmp_path, {"v": "a"})
        b = agent.write_outbox(tmp_path, {"v": "b"})
        c = agent.write_outbox(tmp_path, {"v": "c"})
        os.utime(a, (1000, 1000))
        os.utime(b, (2000, 2000))
        os.utime(c, (3000, 3000))
        listed = agent.list_outbox(tmp_path)
        assert [p.name for p in listed] == [a.name, b.name, c.name]

    def test_list_outbox_excludes_partial_and_sent(self, tmp_path):
        agent.write_outbox(tmp_path, {"v": "a"})
        # 制造一个 partial 文件
        (tmp_path / "fake.json.partial").write_text("x")
        # sent 子目录
        (tmp_path / "sent").mkdir()
        (tmp_path / "sent" / "old.json").write_text("y")
        listed = agent.list_outbox(tmp_path)
        assert len(listed) == 1
        assert all(p.parent == tmp_path for p in listed)

    def test_mark_sent_moves_file(self, tmp_path):
        path = agent.write_outbox(tmp_path, {"v": "x"})
        agent.mark_sent(tmp_path, path)
        assert not path.exists()
        assert (tmp_path / "sent" / path.name).exists()


# ── 4. drain_outbox ─────────────────────────────────────────
class TestDrainOutbox:
    def test_all_succeed(self, tmp_path):
        cfg = agent.SyncConfig(outbox_dir=tmp_path)
        agent.write_outbox(tmp_path, {"v": "a"})
        agent.write_outbox(tmp_path, {"v": "b"})

        with patch.object(agent, "push_payload", return_value=True):
            sent = agent.drain_outbox(cfg)

        assert sent == 2
        assert agent.list_outbox(tmp_path) == []
        assert len(list((tmp_path / "sent").iterdir())) == 2

    def test_first_fails_stops_loop(self, tmp_path):
        """第一条发不出去 → 停掉,后面的等下一 tick。"""
        cfg = agent.SyncConfig(outbox_dir=tmp_path)
        agent.write_outbox(tmp_path, {"v": "a"})
        agent.write_outbox(tmp_path, {"v": "b"})
        agent.write_outbox(tmp_path, {"v": "c"})

        with patch.object(agent, "push_payload", return_value=False):
            sent = agent.drain_outbox(cfg)

        assert sent == 0
        assert len(agent.list_outbox(tmp_path)) == 3   # 一条都没动

    def test_corrupted_json_quarantined(self, tmp_path):
        cfg = agent.SyncConfig(outbox_dir=tmp_path)
        bad = tmp_path / "20990101_000000_000.json"
        bad.write_text("not-json{")

        with patch.object(agent, "push_payload", return_value=True):
            sent = agent.drain_outbox(cfg)

        assert sent == 0
        # 损坏文件应该被移到 corrupt/
        assert (tmp_path / "corrupt" / bad.name).exists()
        assert not bad.exists()

    def test_pii_in_outbox_is_blocked_and_quarantined(self, tmp_path):
        """
        关键测试: outbox 落盘后被人篡改/老版本残留塞入了 patient_id,
        新版 sync_agent 必须拒绝发送并隔离。
        """
        cfg = agent.SyncConfig(outbox_dir=tmp_path)
        bad_path = tmp_path / "20990101_000000_000.json"
        bad_path.write_text(json.dumps({
            "schema_version": 1,
            "occupancy": {"total_beds": 10, "patient_id": "p_x"},
        }))

        push_mock = MagicMock(return_value=True)
        with patch.object(agent, "push_payload", push_mock):
            agent.drain_outbox(cfg)

        # 绝不能调 push_payload (PII 提前拦下)
        assert push_mock.call_count == 0
        assert (tmp_path / "corrupt" / bad_path.name).exists()


# ── 5. push_payload 失败路径 ────────────────────────────────
class TestPushPayload:
    def test_returns_false_on_network_error(self, tmp_path, monkeypatch):
        """httpx 任意异常 → push_payload 静默返回 False。"""
        cfg = agent.SyncConfig(
            enabled=True,
            cloud_url="https://nowhere.invalid",
            client_cert=tmp_path / "c",
            client_key=tmp_path / "k",
        )
        # build_ssl_context 不能真跑(没 cert),mock 掉
        monkeypatch.setattr(agent, "build_ssl_context",
                            lambda c: ssl.create_default_context())

        # mock httpx.Client 让它抛连接错误
        class _FakeClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, *a, **k): raise ConnectionError("offline")

        with patch.dict(sys.modules, {"httpx": MagicMock(Client=_FakeClient)}):
            ok = agent.push_payload(cfg, {"schema_version": 1})
        assert ok is False

    def test_returns_false_on_5xx(self, tmp_path, monkeypatch):
        cfg = agent.SyncConfig(
            enabled=True,
            cloud_url="https://x.example.com",
            client_cert=tmp_path / "c",
            client_key=tmp_path / "k",
        )
        monkeypatch.setattr(agent, "build_ssl_context",
                            lambda c: ssl.create_default_context())

        fake_resp = MagicMock(status_code=503, text="upstream down", content=b"ud")

        class _FakeClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, *a, **k): return fake_resp

        with patch.dict(sys.modules, {"httpx": MagicMock(Client=_FakeClient)}):
            ok = agent.push_payload(cfg, {"schema_version": 1})
        assert ok is False


# ── 6. build_ssl_context ────────────────────────────────────
class TestSSLContext:
    def test_context_has_strict_settings(self, tmp_path):
        """没传 cert 时 context 仍然要求 server cert + TLSv1.2+。"""
        cfg = agent.SyncConfig(enabled=False)   # 不传 cert
        ctx = agent.build_ssl_context(cfg)
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_loads_real_self_signed_cert(self, tmp_path):
        """生成 self-signed cert 验证 load_cert_chain 路径走通。"""
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
            import datetime as _dt
        except ImportError:
            pytest.skip("cryptography 不可用")

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "client-test"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(_dt.datetime.now(_dt.timezone.utc))
            .not_valid_after(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        cert_path = tmp_path / "client.crt"
        key_path = tmp_path / "client.key"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        cfg = agent.SyncConfig(
            enabled=True,
            cloud_url="https://x.example.com",
            client_cert=cert_path,
            client_key=key_path,
        )
        ctx = agent.build_ssl_context(cfg)
        # 不抛即过——load_cert_chain 真的加载成功
        assert ctx.verify_mode == ssl.CERT_REQUIRED


# ── 7. main(--once) 端到端不连网 ────────────────────────────
class TestMainOnce:
    def test_once_writes_outbox_when_disabled(self, tmp_path, monkeypatch):
        for k in list(os.environ):
            if k.startswith("SYNC_"):
                monkeypatch.delenv(k, raising=False)
        # 切换 base_dir 到 tmp_path,落盘到 tmp_path/local_sync_outbox
        monkeypatch.setattr(agent, "_HERE", tmp_path)
        monkeypatch.setenv("SYNC_OUTBOX_DIR", str(tmp_path / "outbox"))

        rc = agent.main(["--once"])
        assert rc == 0
        # outbox 应该有一份 payload
        files = list((tmp_path / "outbox").glob("*.json"))
        assert len(files) == 1

    def test_once_returns_2_when_enabled_but_misconfigured(self, tmp_path, monkeypatch):
        """启用但缺 cert → 退出码 2,outbox 不写 (避免无意义堆积)。"""
        monkeypatch.setattr(agent, "_HERE", tmp_path)
        for k in list(os.environ):
            if k.startswith("SYNC_"):
                monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("SYNC_ENABLED", "true")
        monkeypatch.setenv("SYNC_CLOUD_URL", "https://x.com")
        # cert 缺失
        rc = agent.main(["--once"])
        assert rc == 2
