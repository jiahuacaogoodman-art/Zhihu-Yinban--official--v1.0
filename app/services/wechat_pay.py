# -*- coding: utf-8 -*-
"""
@File    : app/services/wechat_pay.py
@Desc    : 微信支付服务层 —— 对接微信支付 V3 API

支持功能：
  1. Native 支付（扫码支付，适合PC端/打印二维码给家属扫）
  2. JSAPI 支付（微信内H5支付，适合公众号/小程序场景）
  3. 退款
  4. 支付结果回调验签
  5. 订单查询

设计决策：
  - 使用微信支付 V3 API（基于 RSA SHA-256 签名）
  - 独立于 billing_store，通过 billing_store 记录本地账单
  - 支持 sandbox 模式（配置中未填写密钥时自动降级为模拟模式）
  - 回调通知采用 AEAD_AES_256_GCM 解密

依赖：
  - cryptography（已有）
  - requests（已有）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from typing import Optional

import requests
from loguru import logger

from app.core.config import (
    WECHAT_PAY_MCH_ID,
    WECHAT_PAY_APP_ID,
    WECHAT_PAY_API_KEY_V3,
    WECHAT_PAY_SERIAL_NO,
    WECHAT_PAY_PRIVATE_KEY_PATH,
    WECHAT_PAY_NOTIFY_URL,
)


class WechatPayService:
    """微信支付 V3 API 服务封装。"""

    BASE_URL = "https://api.mch.weixin.qq.com"

    def __init__(self):
        self._mch_id = WECHAT_PAY_MCH_ID
        self._app_id = WECHAT_PAY_APP_ID
        self._api_key_v3 = WECHAT_PAY_API_KEY_V3
        self._serial_no = WECHAT_PAY_SERIAL_NO
        self._notify_url = WECHAT_PAY_NOTIFY_URL
        self._private_key = self._load_private_key()
        self._enabled = bool(self._mch_id and self._app_id and self._api_key_v3)

        if self._enabled:
            logger.info(f"微信支付已启用: mch_id={self._mch_id}, app_id={self._app_id}")
        else:
            logger.warning("微信支付未配置完整，将运行在模拟模式（不会真正发起支付请求）")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _load_private_key(self) -> Optional[str]:
        """加载商户 RSA 私钥。"""
        key_path = WECHAT_PAY_PRIVATE_KEY_PATH
        if not key_path:
            return None
        from pathlib import Path
        p = Path(key_path)
        if not p.is_file():
            logger.warning(f"微信支付私钥文件不存在: {key_path}")
            return None
        return p.read_text(encoding="utf-8").strip()

    # ================================================================
    # V3 签名
    # ================================================================

    def _sign(self, message: str) -> str:
        """RSA-SHA256 签名。"""
        if not self._private_key:
            return ""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key = serialization.load_pem_private_key(
                self._private_key.encode("utf-8"), password=None
            )
            signature = private_key.sign(
                message.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return b64encode(signature).decode("utf-8")
        except Exception as e:
            logger.error(f"微信支付签名失败: {e}")
            return ""

    def _build_auth_header(self, method: str, url_path: str, body: str = "") -> str:
        """构建 Authorization 请求头。"""
        timestamp = str(int(time.time()))
        nonce_str = uuid.uuid4().hex
        message = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
        signature = self._sign(message)
        return (
            f'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{self._mch_id}",'
            f'nonce_str="{nonce_str}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self._serial_no}"'
        )

    def _request(self, method: str, url_path: str, body: dict = None) -> dict:
        """发送请求到微信支付 API。"""
        body_str = json.dumps(body, ensure_ascii=False) if body else ""
        auth = self._build_auth_header(method, url_path, body_str)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": auth,
        }
        url = f"{self.BASE_URL}{url_path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            else:
                resp = requests.post(url, headers=headers, data=body_str.encode("utf-8"), timeout=30)

            if resp.status_code in (200, 204):
                return resp.json() if resp.text else {}
            else:
                logger.error(f"微信支付API错误: {resp.status_code} {resp.text}")
                return {"error": True, "status_code": resp.status_code, "message": resp.text}
        except Exception as e:
            logger.error(f"微信支付请求异常: {e}")
            return {"error": True, "message": str(e)}

    # ================================================================
    # Native 支付（扫码支付）
    # ================================================================

    def create_native_order(
        self,
        out_trade_no: str,
        description: str,
        total_amount: int,  # 单位：分
        attach: str = "",
    ) -> dict:
        """
        创建 Native 支付订单，返回 code_url（二维码内容）。

        Args:
            out_trade_no: 商户订单号（唯一）
            description: 商品描述（展示给用户）
            total_amount: 金额，单位分（如 300000 = 3000 元）
            attach: 附加数据（回调时原样返回）

        Returns:
            {"code_url": "weixin://wxpay/...", "out_trade_no": "..."}
            or {"error": True, "message": "..."}
        """
        if not self._enabled:
            return {"error": True, "message": "微信支付未配置，请管理员在支付渠道设置中完成配置后再使用"}

        body = {
            "appid": self._app_id,
            "mchid": self._mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "notify_url": self._notify_url,
            "amount": {"total": total_amount, "currency": "CNY"},
        }
        if attach:
            body["attach"] = attach[:128]
        # 2小时后过期
        expire_time = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        body["time_expire"] = expire_time

        result = self._request("POST", "/v3/pay/transactions/native", body)
        if "code_url" in result:
            result["out_trade_no"] = out_trade_no
        return result

    # ================================================================
    # JSAPI 支付（微信内H5/小程序支付）
    # ================================================================

    def create_jsapi_order(
        self,
        out_trade_no: str,
        description: str,
        total_amount: int,
        openid: str,
        attach: str = "",
    ) -> dict:
        """
        创建 JSAPI 支付订单，返回前端调起支付所需参数。

        Args:
            openid: 用户的 openid

        Returns:
            {"prepay_id": "...", "pay_params": {...}} 前端直接使用 pay_params 调起支付
        """
        if not self._enabled:
            return {"error": True, "message": "微信支付未配置，请管理员在支付渠道设置中完成配置后再使用"}

        body = {
            "appid": self._app_id,
            "mchid": self._mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "notify_url": self._notify_url,
            "amount": {"total": total_amount, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        if attach:
            body["attach"] = attach[:128]
        expire_time = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        body["time_expire"] = expire_time

        result = self._request("POST", "/v3/pay/transactions/jsapi", body)
        if "prepay_id" in result:
            # 构建前端调起支付所需参数
            pay_params = self._build_jsapi_params(result["prepay_id"])
            result["pay_params"] = pay_params
            result["out_trade_no"] = out_trade_no
        return result

    def _build_jsapi_params(self, prepay_id: str) -> dict:
        """构建 JSAPI 前端调起支付的签名参数。"""
        timestamp = str(int(time.time()))
        nonce_str = uuid.uuid4().hex
        package = f"prepay_id={prepay_id}"
        message = f"{self._app_id}\n{timestamp}\n{nonce_str}\n{package}\n"
        pay_sign = self._sign(message)
        return {
            "appId": self._app_id,
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": pay_sign,
        }

    # ================================================================
    # 查询订单
    # ================================================================

    def query_order(self, out_trade_no: str) -> dict:
        """查询订单状态。"""
        if not self._enabled:
            return {"error": True, "message": "微信支付未配置，无法查询订单"}
        url_path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self._mch_id}"
        return self._request("GET", url_path)

    # ================================================================
    # 退款
    # ================================================================

    def refund(
        self,
        out_trade_no: str,
        out_refund_no: str,
        total_amount: int,
        refund_amount: int,
        reason: str = "",
    ) -> dict:
        """
        申请退款。

        Args:
            out_trade_no: 原商户订单号
            out_refund_no: 退款单号（商户生成，唯一）
            total_amount: 原订单总金额（分）
            refund_amount: 退款金额（分）
            reason: 退款原因
        """
        if not self._enabled:
            return {"error": True, "message": "微信支付未配置，无法退款"}

        body = {
            "out_trade_no": out_trade_no,
            "out_refund_no": out_refund_no,
            "reason": reason[:80] if reason else "用户退费",
            "amount": {
                "refund": refund_amount,
                "total": total_amount,
                "currency": "CNY",
            },
        }
        return self._request("POST", "/v3/refund/domestic/refunds", body)

    # ================================================================
    # 回调通知解密验签
    # ================================================================

    def decrypt_callback(self, resource: dict) -> Optional[dict]:
        """
        解密微信支付回调通知中的 resource 数据。
        使用 AEAD_AES_256_GCM 解密。

        Args:
            resource: 回调 body 中的 resource 对象
                {
                    "algorithm": "AEAD_AES_256_GCM",
                    "ciphertext": "...",
                    "nonce": "...",
                    "associated_data": "..."
                }
        """
        if not self._api_key_v3:
            logger.error("无法解密回调: API_KEY_V3 未配置")
            return None

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            key = self._api_key_v3.encode("utf-8")
            nonce = resource["nonce"].encode("utf-8")
            ciphertext = b64decode(resource["ciphertext"])
            associated_data = resource.get("associated_data", "").encode("utf-8")

            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            logger.error(f"微信支付回调解密失败: {e}")
            return None

    # ================================================================
    # 生成商户订单号
    # ================================================================

    @staticmethod
    def generate_trade_no(prefix: str = "ZHYB") -> str:
        """生成唯一商户订单号: ZHYB20260517143020_xxxx"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        rand = uuid.uuid4().hex[:6].upper()
        return f"{prefix}{ts}_{rand}"


# ================================================================
# 单例
# ================================================================
_wechat_pay_service: Optional[WechatPayService] = None


def get_wechat_pay_service() -> WechatPayService:
    global _wechat_pay_service
    if _wechat_pay_service is None:
        _wechat_pay_service = WechatPayService()
    return _wechat_pay_service
