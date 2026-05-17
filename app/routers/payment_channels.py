# -*- coding: utf-8 -*-
"""
@File    : app/routers/payment_channels.py
@Desc    : 支付渠道管理路由 —— 管理员后台设置支付方式

端点：
  GET    /api/payment/channels          获取所有支付渠道状态
  GET    /api/payment/channels/{key}    获取单个渠道详情
  PATCH  /api/payment/channels/{key}    更新渠道配置（启停/填写密钥）
  POST   /api/payment/channels/{key}/test  测试渠道连通性
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware.auth import require_permission
from app.services.audit_log import get_audit_log
from app.services.payment_channels import get_payment_channel_store, CHANNEL_META
from app.services.permissions import PERM_EHR_WRITE, PERM_EHR_READ
from app.services.user_store import User

router = APIRouter()
audit = get_audit_log()


class ChannelUpdateRequest(BaseModel):
    """更新渠道配置请求"""
    is_enabled: Optional[bool] = Field(default=None, description="是否启用")
    config: Optional[dict] = Field(default=None, description="渠道配置项（key-value）")


@router.get("/payment/channels", summary="获取所有支付渠道状态(管理员设置面板)")
async def list_channels(
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """
    返回所有支付渠道的状态信息，供管理员后台设置面板使用。

    每个渠道包含：
      - channel_key: 渠道标识
      - name: 中文名称
      - is_enabled: 是否启用
      - requires_network: 是否需要联网
      - requires_config: 是否需要填写配置
      - config_complete: 配置是否完整
      - config_fields: 需要配置哪些字段（含字段类型/说明）
      - config: 当前已配置的值（密码类已脱敏）
    """
    store = get_payment_channel_store()
    channels = store.get_all_channels()
    return {
        "code": 200,
        "channels": channels,
        "summary": {
            "total": len(channels),
            "enabled": sum(1 for c in channels if c["is_enabled"]),
            "online_channels": [c["channel_key"] for c in channels if c["requires_network"]],
            "offline_channels": [c["channel_key"] for c in channels if not c["requires_network"]],
        },
    }


@router.get("/payment/channels/{channel_key}", summary="获取单个渠道详情")
async def get_channel(
    channel_key: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    if channel_key not in CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"支付渠道 '{channel_key}' 不存在")
    store = get_payment_channel_store()
    channel = store.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道信息未找到")
    return {"code": 200, "channel": channel}


@router.patch("/payment/channels/{channel_key}", summary="更新渠道配置(启停/密钥)")
async def update_channel(
    channel_key: str,
    payload: ChannelUpdateRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    管理员更新支付渠道配置。

    可以：
      - 启用/停用渠道 (is_enabled)
      - 填写/更新配置参数 (config)

    示例：启用微信支付并填写商户号
    ```json
    {
      "is_enabled": true,
      "config": {
        "mch_id": "1234567890",
        "app_id": "wx...",
        "api_key_v3": "your-32-byte-key",
        "serial_no": "CERT-SERIAL-NO",
        "private_key_path": "/app/certs/apiclient_key.pem",
        "notify_url": "https://your-domain.com/api/pay/wechat/notify"
      }
    }
    ```
    """
    if channel_key not in CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"支付渠道 '{channel_key}' 不存在")

    meta = CHANNEL_META[channel_key]

    # 验证：启用在线渠道时检查配置是否完整
    if payload.is_enabled and meta.get("requires_config"):
        store = get_payment_channel_store()
        current = store.get_raw_config(channel_key)
        # 合并新配置
        merged = {**current}
        if payload.config:
            merged.update({k: v for k, v in payload.config.items() if v})
        # 检查必填字段
        missing = []
        for field in meta.get("config_fields", []):
            if field.get("required") and not merged.get(field["key"]):
                missing.append(field["label"])
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"启用 {meta['name']} 需要先完成配置，缺少: {', '.join(missing)}"
            )

    store = get_payment_channel_store()
    result = store.update_channel(
        channel_key,
        is_enabled=payload.is_enabled,
        config=payload.config,
        operator=user.username,
    )
    if not result:
        raise HTTPException(status_code=500, detail="更新失败")

    action = []
    if payload.is_enabled is not None:
        action.append(f"{'启用' if payload.is_enabled else '停用'}")
    if payload.config:
        action.append(f"更新配置({len(payload.config)}项)")
    audit.log("PAYMENT_CHANNEL_UPDATE", "", user.username,
              doc_id=channel_key,
              detail=f"{meta['name']}: {' + '.join(action)}")

    return {"code": 200, "message": f"{meta['name']}配置已更新", "channel": result}


@router.post("/payment/channels/{channel_key}/test", summary="测试渠道连通性")
async def test_channel(
    channel_key: str,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    测试支付渠道是否可用。
    - 离线渠道（现金/转账/POS）：始终返回成功
    - 在线渠道（微信/支付宝）：尝试调用API验证配置正确性
    """
    if channel_key not in CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"支付渠道 '{channel_key}' 不存在")

    meta = CHANNEL_META[channel_key]

    # 离线渠道直接成功
    if not meta.get("requires_network"):
        return {
            "code": 200,
            "channel_key": channel_key,
            "test_result": "success",
            "message": f"{meta['name']}无需联网，始终可用",
        }

    # 在线渠道：检查配置完整性
    store = get_payment_channel_store()
    config = store.get_raw_config(channel_key)
    missing = []
    for field in meta.get("config_fields", []):
        if field.get("required") and not config.get(field["key"]):
            missing.append(field["label"])

    if missing:
        return {
            "code": 200,
            "channel_key": channel_key,
            "test_result": "incomplete",
            "message": f"配置不完整，缺少: {', '.join(missing)}",
        }

    # 微信支付：尝试查询一个不存在的订单来验证签名
    if channel_key == "wechat":
        try:
            from app.services.wechat_pay import get_wechat_pay_service
            svc = get_wechat_pay_service()
            if not svc.is_enabled:
                return {
                    "code": 200,
                    "channel_key": channel_key,
                    "test_result": "warning",
                    "message": "微信支付服务未激活（检查.env或渠道配置）",
                }
            # 查询一个不存在的订单，如果返回"订单不存在"说明签名正确
            result = svc.query_order("TEST_NONEXIST_ORDER_12345")
            if result.get("error") and "ORDERNOTEXIST" not in str(result.get("message", "")):
                return {
                    "code": 200,
                    "channel_key": channel_key,
                    "test_result": "failed",
                    "message": f"连接失败: {result.get('message', '未知错误')[:100]}",
                }
            return {
                "code": 200,
                "channel_key": channel_key,
                "test_result": "success",
                "message": "微信支付API连接正常，签名验证通过",
            }
        except Exception as e:
            return {
                "code": 200,
                "channel_key": channel_key,
                "test_result": "failed",
                "message": f"测试异常: {str(e)[:100]}",
            }

    # 支付宝：暂时只检查配置完整性
    if channel_key == "alipay":
        return {
            "code": 200,
            "channel_key": channel_key,
            "test_result": "success",
            "message": "支付宝配置已完整（实际连通性需首次交易验证）",
        }

    return {
        "code": 200,
        "channel_key": channel_key,
        "test_result": "unknown",
        "message": "未知渠道类型",
    }
