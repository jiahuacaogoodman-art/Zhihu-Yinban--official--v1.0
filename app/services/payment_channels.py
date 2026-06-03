# -*- coding: utf-8 -*-
"""
@File    : app/services/payment_channels.py
@Desc    : 多支付渠道管理服务 —— 统一管理所有支付方式的配置与状态

支持渠道：
  1. cash          现金（纯本地，无需联网）
  2. bank_transfer 银行转账（纯本地记录，无需联网）
  3. pos           POS机刷卡（纯本地记录，无需联网）
  4. wechat        微信支付（需联网，对接微信支付V3 API）
  5. alipay        支付宝（需联网，对接支付宝开放平台）

设计原则：
  - 每种渠道的配置独立存储在 SQLite（本地持久化）
  - 管理员通过后台界面启用/停用渠道、填写密钥
  - 密钥等敏感信息加密存储（Fernet）
  - 离线渠道（现金/转账/POS）始终可用，不依赖外部服务
  - 在线渠道（微信/支付宝）需配置完整才能启用

联网需求：
  ┌─────────────┬──────────┬────────────────────┐
  │ 渠道        │ 联网需求 │ 说明               │
  ├─────────────┼──────────┼────────────────────┤
  │ cash        │ 不需要   │ 纯本地记账         │
  │ bank_transfer│ 不需要  │ 纯本地记账         │
  │ pos         │ 不需要   │ 纯本地记账         │
  │ wechat      │ 需要     │ 调用微信支付API    │
  │ alipay      │ 需要     │ 调用支付宝API      │
  └─────────────┴──────────┴────────────────────┘
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:  # pragma: no cover - requirements 已包含 cryptography
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]
    _FERNET_AVAILABLE = False


# 渠道元数据（静态定义）
CHANNEL_META = {
    "cash": {
        "name": "现金",
        "icon": "fa-money-bill-wave",
        "color": "#10b981",
        "requires_network": False,
        "requires_config": False,
        "description": "现金收款，手动记录收据编号",
    },
    "bank_transfer": {
        "name": "银行转账",
        "icon": "fa-building-columns",
        "color": "#6366f1",
        "requires_network": False,
        "requires_config": False,
        "description": "银行转账/汇款，记录转账流水号",
    },
    "pos": {
        "name": "POS机刷卡",
        "icon": "fa-credit-card",
        "color": "#8b5cf6",
        "requires_network": False,
        "requires_config": False,
        "description": "POS终端刷卡/插卡/挥卡，记录交易凭证号",
    },
    "wechat": {
        "name": "微信支付",
        "icon": "fa-weixin",
        "color": "#07c160",
        "requires_network": True,
        "requires_config": True,
        "description": "微信扫码支付/JSAPI支付，需配置商户号和密钥",
        "config_fields": [
            {"key": "mch_id", "label": "商户号", "type": "text", "required": True},
            {"key": "app_id", "label": "AppID", "type": "text", "required": True},
            {"key": "api_key_v3", "label": "APIv3密钥", "type": "password", "required": True},
            {"key": "serial_no", "label": "证书序列号", "type": "text", "required": True},
            {"key": "private_key_path", "label": "私钥文件路径", "type": "text", "required": True},
            {"key": "notify_url", "label": "回调通知地址", "type": "text", "required": True,
             "hint": "必须是外网可访问的HTTPS地址"},
        ],
    },
    "alipay": {
        "name": "支付宝",
        "icon": "fa-alipay",
        "color": "#1677ff",
        "requires_network": True,
        "requires_config": True,
        "description": "支付宝扫码/H5支付，需配置应用ID和密钥",
        "config_fields": [
            {"key": "app_id", "label": "应用APPID", "type": "text", "required": True},
            {"key": "private_key", "label": "应用私钥", "type": "password", "required": True},
            {"key": "alipay_public_key", "label": "支付宝公钥", "type": "password", "required": True},
            {"key": "notify_url", "label": "回调通知地址", "type": "text", "required": True},
            {"key": "gateway", "label": "网关地址", "type": "text", "required": False,
             "hint": "默认: https://openapi.alipay.com/gateway.do"},
        ],
    },
}

_ENC_PREFIX = "enc:"
_MASKED_SECRET = "●●●●●●"


def _get_payment_cipher() -> Optional["Fernet"]:
    """
    支付渠道密钥加密器。

    优先使用 PAYMENT_CONFIG_ENCRYPTION_KEY；未单独配置时复用
    PII_ENCRYPTION_KEY，方便小型养老院只维护一把本地密钥。
    """
    if not _FERNET_AVAILABLE:
        return None
    key = (
        os.getenv("PAYMENT_CONFIG_ENCRYPTION_KEY", "").strip()
        or os.getenv("PII_ENCRYPTION_KEY", "").strip()
    )
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))  # type: ignore[union-attr]
    except Exception as e:
        logger.error(f"PAYMENT_CONFIG_ENCRYPTION_KEY/PII_ENCRYPTION_KEY 无效，支付密钥加密关闭: {e}")
        return None


def _secret_field_keys(channel_key: str) -> set[str]:
    meta = CHANNEL_META.get(channel_key, {})
    return {
        field["key"]
        for field in meta.get("config_fields", [])
        if field.get("type") == "password"
    }


def _encrypt_secret(value: str) -> str:
    if not value or value.startswith(_ENC_PREFIX):
        return value
    cipher = _get_payment_cipher()
    if cipher is None:
        logger.warning(
            "支付渠道敏感配置将以明文保存：请配置 PAYMENT_CONFIG_ENCRYPTION_KEY "
            "或 PII_ENCRYPTION_KEY 以启用 Fernet 加密。"
        )
        return value
    return _ENC_PREFIX + cipher.encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_secret(value: str, *, preserve_ciphertext: bool = False) -> str:
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    cipher = _get_payment_cipher()
    if cipher is None:
        logger.warning("支付渠道敏感配置已加密，但当前未配置解密密钥。")
        return value if preserve_ciphertext else ""
    try:
        token = value[len(_ENC_PREFIX):].encode("ascii")
        return cipher.decrypt(token).decode("utf-8")
    except (InvalidToken, Exception) as e:
        logger.warning(f"支付渠道敏感配置解密失败: {e}")
        return value if preserve_ciphertext else ""


class PaymentChannelStore:
    """支付渠道配置持久化存储。"""

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS payment_channels (
            channel_key     TEXT PRIMARY KEY,
            is_enabled      INTEGER NOT NULL DEFAULT 0,
            config_json     TEXT NOT NULL DEFAULT '{}',
            updated_at      TEXT NOT NULL,
            updated_by      TEXT NOT NULL DEFAULT '',
            -- PR#6: 多租户 / 乐观锁 schema 准备
            branch_id       TEXT NOT NULL DEFAULT 'main',
            version_id      INTEGER NOT NULL DEFAULT 1
        );
    """

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self._CREATE_SQL)
            # PR#6: 老库幂等加 branch_id + version_id 列
            from app.services.branching import ensure_branching_columns
            ensure_branching_columns(conn, full=("payment_channels",))
            # 确保所有渠道都有记录
            for key in CHANNEL_META:
                conn.execute(
                    "INSERT OR IGNORE INTO payment_channels (channel_key, is_enabled, config_json, updated_at) "
                    "VALUES (?, ?, '{}', ?)",
                    (key, 1 if not CHANNEL_META[key]["requires_config"] else 0,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
        logger.debug(f"PaymentChannelStore 初始化完成: {self._path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _decode_config(
        channel_key: str,
        config_json: str,
        *,
        decrypt_secrets: bool,
        preserve_ciphertext: bool = False,
    ) -> dict:
        """解析渠道配置；password 字段可按需解密。"""
        try:
            config = json.loads(config_json or "{}")
        except json.JSONDecodeError:
            logger.warning(f"支付渠道 {channel_key} 配置 JSON 损坏，已按空配置处理")
            config = {}

        secret_keys = _secret_field_keys(channel_key)
        if not decrypt_secrets:
            return config

        result = dict(config)
        for key in secret_keys:
            value = result.get(key)
            if isinstance(value, str):
                result[key] = _decrypt_secret(value, preserve_ciphertext=preserve_ciphertext)
        return result

    @staticmethod
    def _encode_config(channel_key: str, config: dict) -> str:
        """将渠道配置编码为 JSON；password 字段写库前加密。"""
        secret_keys = _secret_field_keys(channel_key)
        stored = dict(config)
        for key in secret_keys:
            value = stored.get(key)
            if isinstance(value, str):
                stored[key] = _encrypt_secret(value)
        return json.dumps(stored, ensure_ascii=False)

    def get_all_channels(self) -> list[dict]:
        """获取所有渠道状态（含元数据）。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM payment_channels").fetchall()
        result = []
        for row in rows:
            key = row["channel_key"]
            meta = CHANNEL_META.get(key, {})
            config = self._decode_config(
                key,
                row["config_json"] or "{}",
                decrypt_secrets=False,
            )
            # 脱敏：密码类字段只显示是否已配置
            safe_config = {}
            for field in meta.get("config_fields", []):
                fk = field["key"]
                if field.get("type") == "password":
                    safe_config[fk] = _MASKED_SECRET if config.get(fk) else ""
                else:
                    safe_config[fk] = config.get(fk, "")
            # 判断配置是否完整
            config_complete = True
            if meta.get("requires_config"):
                for field in meta.get("config_fields", []):
                    if field.get("required") and not config.get(field["key"]):
                        config_complete = False
                        break
            result.append({
                "channel_key": key,
                "name": meta.get("name", key),
                "icon": meta.get("icon", ""),
                "color": meta.get("color", ""),
                "requires_network": meta.get("requires_network", False),
                "requires_config": meta.get("requires_config", False),
                "description": meta.get("description", ""),
                "config_fields": meta.get("config_fields", []),
                "is_enabled": bool(row["is_enabled"]),
                "config_complete": config_complete,
                "config": safe_config,
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
            })
        return result

    def get_channel(self, channel_key: str) -> Optional[dict]:
        """获取单个渠道信息。"""
        channels = self.get_all_channels()
        return next((c for c in channels if c["channel_key"] == channel_key), None)

    def update_channel(self, channel_key: str, is_enabled: Optional[bool] = None,
                       config: Optional[dict] = None, operator: str = "") -> Optional[dict]:
        """更新渠道配置/状态。"""
        if channel_key not in CHANNEL_META:
            return None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            # 先读当前配置
            row = conn.execute(
                "SELECT * FROM payment_channels WHERE channel_key = ?", (channel_key,)
            ).fetchone()
            if not row:
                return None
            current_config = self._decode_config(
                channel_key,
                row["config_json"] or "{}",
                decrypt_secrets=True,
                preserve_ciphertext=True,
            )
            # 合并新配置（只更新传入的字段）
            if config:
                for k, v in config.items():
                    if v is not None and v != "":
                        current_config[k] = v
                    # 如果传入空字符串，表示清除该字段
                    elif v == "" and k in current_config:
                        del current_config[k]
            fields = ["updated_at = ?", "updated_by = ?"]
            params = [now, operator]
            if is_enabled is not None:
                fields.append("is_enabled = ?")
                params.append(1 if is_enabled else 0)
            if config is not None:
                fields.append("config_json = ?")
                params.append(self._encode_config(channel_key, current_config))
            params.append(channel_key)
            conn.execute(
                f"UPDATE payment_channels SET {', '.join(fields)} WHERE channel_key = ?",
                params,
            )
        return self.get_channel(channel_key)

    def get_enabled_channels(self) -> list[str]:
        """获取当前已启用的渠道列表。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT channel_key FROM payment_channels WHERE is_enabled = 1"
            ).fetchall()
        return [r["channel_key"] for r in rows]

    def get_raw_config(self, channel_key: str) -> dict:
        """获取渠道原始配置（含敏感信息，仅供内部服务使用）。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT config_json FROM payment_channels WHERE channel_key = ?",
                (channel_key,)
            ).fetchone()
        if not row:
            return {}
        return self._decode_config(
            channel_key,
            row["config_json"] or "{}",
            decrypt_secrets=True,
        )


# 单例
_channel_store: Optional[PaymentChannelStore] = None
_channel_store_lock = threading.Lock()


def get_payment_channel_store() -> PaymentChannelStore:
    global _channel_store
    if _channel_store is None:
        with _channel_store_lock:
            if _channel_store is None:
                base_dir = Path(__file__).resolve().parent.parent.parent
                db_dir = base_dir / "local_billing"
                db_dir.mkdir(parents=True, exist_ok=True)
                _channel_store = PaymentChannelStore(db_dir / "payment_channels.db")
    return _channel_store
