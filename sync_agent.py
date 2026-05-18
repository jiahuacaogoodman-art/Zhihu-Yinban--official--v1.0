#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@File    : sync_agent.py
@Desc    : Edge Sync Daemon (PR#7)

独立于 FastAPI 之外的后台守护进程。运行模型:
    python sync_agent.py
或在 systemd / docker-compose 里作为单独服务。

行为
  · 每隔 SYNC_INTERVAL_SECONDS 抓一次本地脱敏指标(sync_metrics.collect_metrics)
  · 试着用 mTLS POST 到 SYNC_CLOUD_URL/api/v1/branches/<branch_id>/metrics
  · 推送前 assert_no_pii: 任何 PII 字段名出现就立即 raise + 写本地错误日志
  · 推送失败:把 payload 落到 local_sync_outbox/<ts>.json,下次开机重试
  · 收到 2xx → 把 outbox 里同名文件移到 local_sync_outbox/sent/
  · 弱网 / 完全离线: 永远不阻塞;循环只产生 outbox 累积,等网恢复再吐

退出
  · SIGINT / SIGTERM → 优雅退出: 把当前正在处理的 payload 落盘后再退
  · loop 内任何异常都被吞 + 日志,**绝不退出**

Why a separate process
  · 主 FastAPI 即使挂了/重启,sync 仍能跑(独立 systemd unit)
  · 网络 retry 不影响主线请求延迟
  · mTLS 客户端证书的解锁密码可以单独提供给这个进程,降低主进程的攻击面

Why no APScheduler / aiohttp / asyncio.create_subprocess
  · 标准库 + httpx(已在 requirements.txt 作 dev 依赖) 足够
  · 单循环 + signal.signal 比 asyncio task 在系统级守护下更直观
  · 没引新依赖,部署只用 pip install httpx 即可

mTLS 配置 (env / CLI):
  SYNC_ENABLED               true/1/yes 才启动循环;否则 dry-run
  SYNC_CLOUD_URL             https://cloud.example.com (无尾斜杠)
  SYNC_BRANCH_ID             默认 main
  SYNC_INTERVAL_SECONDS      默认 3600 (1 小时)
  SYNC_CLIENT_CERT           PEM 文件路径(client cert)
  SYNC_CLIENT_KEY            PEM 文件路径(client key,可加密)
  SYNC_CLIENT_KEY_PASSWORD   client key 的解锁密码(可选)
  SYNC_CA_BUNDLE             cloud server 的 CA 证书(用于 server cert 校验)
  SYNC_OUTBOX_DIR            离线 payload 落盘目录;默认 BASE_DIR/local_sync_outbox
  SYNC_TIMEOUT_SECONDS       单次 HTTP 超时;默认 15
"""
from __future__ import annotations

import json
import logging
import os
import signal
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── 在加 import 之前先把 BASE_DIR 加进 sys.path,允许独立运行 ──
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from app.services.sync_metrics import (   # noqa: E402  isort:skip
    assert_no_pii,
    collect_metrics,
)


log = logging.getLogger("sync_agent")


# ── 配置 ────────────────────────────────────────────────
@dataclass
class SyncConfig:
    enabled: bool = False
    cloud_url: str = ""                      # https://cloud.example.com
    branch_id: str = "main"
    interval_seconds: int = 3600
    client_cert: Optional[Path] = None
    client_key: Optional[Path] = None
    client_key_password: Optional[str] = None
    ca_bundle: Optional[Path] = None
    outbox_dir: Path = field(default_factory=lambda: _HERE / "local_sync_outbox")
    timeout_seconds: float = 15.0
    base_dir: Path = field(default_factory=lambda: _HERE)

    @classmethod
    def from_env(cls) -> "SyncConfig":
        enabled = os.getenv("SYNC_ENABLED", "false").strip().lower() in {"true", "1", "yes"}
        try:
            interval = max(60, int(os.getenv("SYNC_INTERVAL_SECONDS", "3600")))
        except ValueError:
            interval = 3600
        try:
            timeout = max(1.0, float(os.getenv("SYNC_TIMEOUT_SECONDS", "15")))
        except ValueError:
            timeout = 15.0

        outbox = os.getenv("SYNC_OUTBOX_DIR", "").strip()
        outbox_dir = Path(outbox) if outbox else _HERE / "local_sync_outbox"

        def _path(env: str) -> Optional[Path]:
            v = os.getenv(env, "").strip()
            return Path(v) if v else None

        return cls(
            enabled=enabled,
            cloud_url=os.getenv("SYNC_CLOUD_URL", "").strip().rstrip("/"),
            branch_id=os.getenv("SYNC_BRANCH_ID", "main").strip() or "main",
            interval_seconds=interval,
            client_cert=_path("SYNC_CLIENT_CERT"),
            client_key=_path("SYNC_CLIENT_KEY"),
            client_key_password=os.getenv("SYNC_CLIENT_KEY_PASSWORD") or None,
            ca_bundle=_path("SYNC_CA_BUNDLE"),
            outbox_dir=outbox_dir,
            timeout_seconds=timeout,
            base_dir=_HERE,
        )

    def validate(self) -> list[str]:
        """返回错误列表;空表示配置完整。"""
        errors: list[str] = []
        if not self.enabled:
            return errors
        if not self.cloud_url.startswith(("https://", "http://")):
            errors.append("SYNC_CLOUD_URL 必须是 http(s):// 开头")
        if self.client_cert is None or self.client_key is None:
            errors.append(
                "SYNC_CLIENT_CERT / SYNC_CLIENT_KEY 必须配置 (mTLS 客户端身份)",
            )
        else:
            if not self.client_cert.exists():
                errors.append(f"SYNC_CLIENT_CERT 不存在: {self.client_cert}")
            if not self.client_key.exists():
                errors.append(f"SYNC_CLIENT_KEY 不存在: {self.client_key}")
        if self.ca_bundle is not None and not self.ca_bundle.exists():
            errors.append(f"SYNC_CA_BUNDLE 不存在: {self.ca_bundle}")
        return errors


# ── outbox: 持久化未送达 payload ────────────────────────
def write_outbox(outbox_dir: Path, payload: dict) -> Path:
    """
    把 payload 落到 outbox/<ts>.json,原子 rename。

    时间戳精度到毫秒,但仍可能在同毫秒内被两个调用碰上(测试里就会发生);
    用一个进程级递增计数器消歧。
    """
    outbox_dir.mkdir(parents=True, exist_ok=True)
    base_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    final_path = outbox_dir / f"{base_ts}.json"
    if final_path.exists():
        # 同毫秒撞了,加个递增后缀直到找到空名
        n = 1
        while True:
            alt = outbox_dir / f"{base_ts}-{n}.json"
            if not alt.exists():
                final_path = alt
                break
            n += 1
    tmp_path = final_path.with_suffix(".json.partial")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, final_path)
    return final_path


def list_outbox(outbox_dir: Path) -> list[Path]:
    """outbox 中所有未送达的 .json,按 mtime 升序(老的先发)。"""
    if not outbox_dir.exists():
        return []
    files = [p for p in outbox_dir.iterdir()
             if p.is_file() and p.suffix == ".json" and not p.name.endswith(".partial")]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def mark_sent(outbox_dir: Path, payload_path: Path) -> None:
    """把已发送的文件移到 sent/ 子目录,云端可继续 GC。"""
    sent_dir = outbox_dir / "sent"
    sent_dir.mkdir(parents=True, exist_ok=True)
    target = sent_dir / payload_path.name
    if target.exists():
        target.unlink()
    payload_path.rename(target)


# ── 推送 ────────────────────────────────────────────────
def build_ssl_context(cfg: SyncConfig) -> ssl.SSLContext:
    """
    构造一个正经的 mTLS SSLContext。

    - 服务器证书校验:用 ca_bundle 验证云端证书链 (不接受任何 server)
    - 客户端身份:加载 client_cert + client_key,可选 password
    - hostname 校验默认开启 (cfg.cloud_url 里的 hostname 必须匹配 server cert)
    - 不支持 TLS 1.0 / 1.1
    """
    if cfg.ca_bundle is not None:
        ctx = ssl.create_default_context(cafile=str(cfg.ca_bundle))
    else:
        # 没指定 CA 走系统默认信任池(企业级建议总是显式指定 CA)
        ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if cfg.client_cert and cfg.client_key:
        ctx.load_cert_chain(
            certfile=str(cfg.client_cert),
            keyfile=str(cfg.client_key),
            password=cfg.client_key_password,
        )
    return ctx


def push_payload(cfg: SyncConfig, payload: dict) -> bool:
    """
    单次 mTLS 推送。返回 True 表示 2xx,False 表示失败(网络 / 证书 / HTTP)。

    httpx 在 dev 依赖里已经声明;sync_agent 是可选服务,没装就报错给运维。
    """
    try:
        import httpx
    except ImportError:
        log.error("sync_agent 需要 httpx (pip install httpx)")
        return False

    ssl_ctx = build_ssl_context(cfg)
    url = f"{cfg.cloud_url}/api/v1/branches/{cfg.branch_id}/metrics"
    headers = {
        "Content-Type": "application/json",
        "X-Branch-Id": cfg.branch_id,
        "X-Schema-Version": str(payload.get("schema_version", "")),
    }
    try:
        with httpx.Client(verify=ssl_ctx, timeout=cfg.timeout_seconds) as client:
            resp = client.post(url, json=payload, headers=headers)
        if 200 <= resp.status_code < 300:
            log.info(f"sync push ok: {resp.status_code} ({len(resp.content)} B response)")
            return True
        log.warning(f"sync push 非 2xx: {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        log.warning(f"sync push 失败: {type(e).__name__}: {e}")
        return False


def drain_outbox(cfg: SyncConfig) -> int:
    """
    清空 outbox 中的累积 payload。每个发送成功就移到 sent/。
    任一失败就停止本轮(后续 payload 留到下个 tick)。
    返回成功发送的条数。
    """
    sent = 0
    for path in list_outbox(cfg.outbox_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"sync outbox: 解析 {path.name} 失败: {e}; 移到 corrupt/")
            corrupt = cfg.outbox_dir / "corrupt"
            corrupt.mkdir(exist_ok=True)
            path.rename(corrupt / path.name)
            continue
        # PII 守门: 即使 outbox 文件被人改过也不会送出
        try:
            assert_no_pii(payload)
        except ValueError as e:
            log.error(f"sync outbox: {path.name} 含 PII,拒绝发送: {e}")
            corrupt = cfg.outbox_dir / "corrupt"
            corrupt.mkdir(exist_ok=True)
            path.rename(corrupt / path.name)
            continue
        if not push_payload(cfg, payload):
            log.info(f"sync outbox: 暂时无法发送 {path.name},稍后重试")
            return sent
        mark_sent(cfg.outbox_dir, path)
        sent += 1
    return sent


# ── 主循环 ──────────────────────────────────────────────
class _Stopper:
    """SIGINT / SIGTERM → set flag,主循环检测后优雅退。"""
    def __init__(self):
        self._stop = False

    def request_stop(self, *_):
        self._stop = True

    @property
    def should_stop(self) -> bool:
        return self._stop


def run_loop(cfg: SyncConfig) -> None:
    """阻塞运行直至收到信号。任何异常都被吞,循环不退出。"""
    stopper = _Stopper()
    signal.signal(signal.SIGINT, stopper.request_stop)
    signal.signal(signal.SIGTERM, stopper.request_stop)

    log.info(
        f"sync_agent 启动: enabled={cfg.enabled} interval={cfg.interval_seconds}s "
        f"cloud={cfg.cloud_url} outbox={cfg.outbox_dir}"
    )

    while not stopper.should_stop:
        try:
            payload = collect_metrics(cfg.base_dir, cfg.branch_id)
            assert_no_pii(payload)              # 关键:出门前最后一道闸
            # 不管能不能发,都先落 outbox(防进程崩溃 → 数据丢)
            path = write_outbox(cfg.outbox_dir, payload)
            log.debug(f"sync_agent: 已落 outbox {path.name}")
            sent = drain_outbox(cfg)
            log.info(f"sync tick: 本轮发送 {sent} 条,outbox 剩 {len(list_outbox(cfg.outbox_dir))}")
        except Exception as e:
            log.exception(f"sync tick 异常 (会继续): {e}")

        # 用小步 sleep 让 SIGINT 快速生效
        for _ in range(cfg.interval_seconds):
            if stopper.should_stop:
                break
            time.sleep(1)

    log.info("sync_agent 优雅退出")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("SYNC_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = SyncConfig.from_env()

    # --once 仅做一次采集 + 落 outbox(运维拿来 cron 触发也行)
    once = bool(argv and "--once" in argv) or os.getenv("SYNC_ONCE") in {"1", "true"}

    errors = cfg.validate()
    if errors:
        for e in errors:
            log.error(f"配置错误: {e}")
        if cfg.enabled:
            return 2
        log.warning("sync_agent: 启用配置不全; dry-run 模式仅本地落盘")

    if once:
        try:
            payload = collect_metrics(cfg.base_dir, cfg.branch_id)
            assert_no_pii(payload)
            path = write_outbox(cfg.outbox_dir, payload)
            log.info(f"sync --once: 已落 outbox {path.name}")
            if cfg.enabled and not errors:
                sent = drain_outbox(cfg)
                log.info(f"sync --once: 发送 {sent} 条")
            return 0
        except Exception as e:
            log.exception(f"sync --once 失败: {e}")
            return 1

    run_loop(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
