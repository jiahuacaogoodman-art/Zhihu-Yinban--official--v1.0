# -*- coding: utf-8 -*-
"""
@File    : app/routers/wechat_pay.py
@Desc    : 微信支付路由 —— 下单、查询、退款、回调

端点：
  POST /api/pay/wechat/native     创建Native支付订单（返回二维码URL）
  POST /api/pay/wechat/jsapi      创建JSAPI支付订单（微信内支付）
  GET  /api/pay/wechat/query/{no} 查询订单状态
  POST /api/pay/wechat/refund     申请退款
  POST /api/pay/wechat/notify     微信支付回调通知（无鉴权）
  GET  /api/pay/wechat/status     微信支付配置状态
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.middleware.auth import require_permission
from app.services.audit_log import get_audit_log
from app.services.billing_store import get_billing_store
from app.services.care_store import get_care_store
from app.services.permissions import PERM_EHR_WRITE, PERM_EHR_READ
from app.services.user_store import User
from app.services.wechat_pay import get_wechat_pay_service

router = APIRouter()
audit = get_audit_log()


# ================================================================
# Request / Response Models
# ================================================================

class NativePayRequest(BaseModel):
    """Native 支付（扫码支付）请求"""
    admission_id: str = Field(..., description="入住申请ID")
    amount: float = Field(..., gt=0, description="支付金额（元）")
    description: str = Field(default="智护银伴-护理费用", max_length=127, description="商品描述")
    fee_category: str = Field(default="care", description="费用类别")
    billing_cycle: str = Field(default="monthly", description="缴费周期")
    period_start: Optional[str] = Field(default=None, description="费用起始日期")
    period_end: Optional[str] = Field(default=None, description="费用截止日期")


class JsapiPayRequest(BaseModel):
    """JSAPI 支付请求"""
    admission_id: str = Field(..., description="入住申请ID")
    amount: float = Field(..., gt=0, description="支付金额（元）")
    openid: str = Field(..., min_length=1, description="用户微信openid")
    description: str = Field(default="智护银伴-护理费用", max_length=127)
    fee_category: str = Field(default="care", description="费用类别")
    billing_cycle: str = Field(default="monthly", description="缴费周期")
    period_start: Optional[str] = Field(default=None)
    period_end: Optional[str] = Field(default=None)


class RefundRequest(BaseModel):
    """退款请求"""
    out_trade_no: str = Field(..., description="原商户订单号")
    refund_amount: float = Field(..., gt=0, description="退款金额（元）")
    total_amount: float = Field(..., gt=0, description="原订单总金额（元）")
    reason: str = Field(default="", max_length=80, description="退款原因")


# ================================================================
# 端点
# ================================================================

@router.post("/pay/wechat/native", summary="创建Native支付订单(扫码支付)")
async def create_native_pay(
    payload: NativePayRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    创建微信 Native 支付订单，返回 code_url 供前端生成二维码。
    家属用微信扫码即可完成支付。
    """
    # 验证 admission
    care_store = get_care_store()
    admission = care_store.get_admission(payload.admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="入住申请不存在")

    wechat_pay = get_wechat_pay_service()
    out_trade_no = wechat_pay.generate_trade_no("ZHYB")
    total_cents = int(payload.amount * 100)  # 元转分

    # 附加数据：回调时用来关联本地账单
    attach = f"{payload.admission_id}|{payload.fee_category}|{payload.billing_cycle}"
    if payload.period_start:
        attach += f"|{payload.period_start}|{payload.period_end or ''}"

    result = wechat_pay.create_native_order(
        out_trade_no=out_trade_no,
        description=payload.description,
        total_amount=total_cents,
        attach=attach,
    )

    if result.get("error"):
        raise HTTPException(status_code=502, detail=f"微信支付下单失败: {result.get('message', '未知错误')}")

    audit.log("WECHAT_PAY_NATIVE", admission.get("patient_id", ""), user.username,
              doc_id=out_trade_no,
              detail=f"Native支付: {payload.amount}元, admission={payload.admission_id}")
    logger.info(f"Native支付订单创建: {out_trade_no}, {payload.amount}元")

    return {
        "code": 200,
        "out_trade_no": out_trade_no,
        "code_url": result.get("code_url", ""),
        "amount": payload.amount,
        "mock": result.get("mock", False),
    }


@router.post("/pay/wechat/jsapi", summary="创建JSAPI支付订单(微信内支付)")
async def create_jsapi_pay(
    payload: JsapiPayRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    创建微信 JSAPI 支付订单，返回前端调起支付的参数。
    适用于微信公众号/小程序内的支付场景。
    """
    care_store = get_care_store()
    admission = care_store.get_admission(payload.admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="入住申请不存在")

    wechat_pay = get_wechat_pay_service()
    out_trade_no = wechat_pay.generate_trade_no("ZHYB")
    total_cents = int(payload.amount * 100)

    attach = f"{payload.admission_id}|{payload.fee_category}|{payload.billing_cycle}"
    if payload.period_start:
        attach += f"|{payload.period_start}|{payload.period_end or ''}"

    result = wechat_pay.create_jsapi_order(
        out_trade_no=out_trade_no,
        description=payload.description,
        total_amount=total_cents,
        openid=payload.openid,
        attach=attach,
    )

    if result.get("error"):
        raise HTTPException(status_code=502, detail=f"微信支付下单失败: {result.get('message', '未知错误')}")

    audit.log("WECHAT_PAY_JSAPI", admission.get("patient_id", ""), user.username,
              doc_id=out_trade_no,
              detail=f"JSAPI支付: {payload.amount}元, openid={payload.openid[:8]}...")

    return {
        "code": 200,
        "out_trade_no": out_trade_no,
        "prepay_id": result.get("prepay_id", ""),
        "pay_params": result.get("pay_params", {}),
        "amount": payload.amount,
        "mock": result.get("mock", False),
    }


@router.get("/pay/wechat/query/{out_trade_no}", summary="查询微信支付订单状态")
async def query_wechat_order(
    out_trade_no: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """查询微信支付订单的支付状态。"""
    wechat_pay = get_wechat_pay_service()
    result = wechat_pay.query_order(out_trade_no)
    return {"code": 200, "order": result}


@router.post("/pay/wechat/refund", summary="申请微信支付退款")
async def refund_wechat(
    payload: RefundRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """申请退款（部分退或全额退）。"""
    wechat_pay = get_wechat_pay_service()
    out_refund_no = wechat_pay.generate_trade_no("ZHRF")

    result = wechat_pay.refund(
        out_trade_no=payload.out_trade_no,
        out_refund_no=out_refund_no,
        total_amount=int(payload.total_amount * 100),
        refund_amount=int(payload.refund_amount * 100),
        reason=payload.reason,
    )

    if result.get("error"):
        raise HTTPException(status_code=502, detail=f"退款失败: {result.get('message', '未知错误')}")

    audit.log("WECHAT_PAY_REFUND", "", user.username,
              doc_id=payload.out_trade_no,
              detail=f"退款: {payload.refund_amount}元, refund_no={out_refund_no}")

    return {
        "code": 200,
        "out_refund_no": out_refund_no,
        "status": result.get("status", "PROCESSING"),
        "mock": result.get("mock", False),
    }


@router.post("/pay/wechat/notify", summary="微信支付回调通知(无鉴权)", include_in_schema=False)
async def wechat_pay_notify(request: Request):
    """
    微信支付结果通知回调。
    此接口不走 AuthToken 鉴权（微信服务器调用），在 middleware 中白名单放行。
    收到支付成功通知后自动创建本地缴费记录。
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"code": "FAIL", "message": "Invalid JSON"})

    if body.get("event_type") != "TRANSACTION.SUCCESS":
        # 非支付成功事件，直接返回成功
        return JSONResponse(content={"code": "SUCCESS", "message": "OK"})

    resource = body.get("resource", {})
    wechat_pay = get_wechat_pay_service()
    plaintext = wechat_pay.decrypt_callback(resource)

    if not plaintext:
        logger.error("微信支付回调解密失败")
        return JSONResponse(status_code=400, content={"code": "FAIL", "message": "Decrypt failed"})

    # 解析支付结果
    trade_state = plaintext.get("trade_state", "")
    if trade_state != "SUCCESS":
        return JSONResponse(content={"code": "SUCCESS", "message": "OK"})

    out_trade_no = plaintext.get("out_trade_no", "")
    amount_total = plaintext.get("amount", {}).get("total", 0)  # 分
    attach = plaintext.get("attach", "")

    logger.info(f"微信支付回调成功: {out_trade_no}, {amount_total}分, attach={attach}")

    # 解析 attach -> 创建本地缴费记录
    try:
        parts = attach.split("|")
        admission_id = parts[0] if len(parts) > 0 else ""
        fee_category = parts[1] if len(parts) > 1 else "care"
        billing_cycle = parts[2] if len(parts) > 2 else "monthly"
        period_start = parts[3] if len(parts) > 3 else ""
        period_end = parts[4] if len(parts) > 4 else ""

        if admission_id and amount_total > 0:
            billing_store = get_billing_store()
            care_store = get_care_store()
            admission = care_store.get_admission(admission_id)
            patient_name = admission.get("applicant_name", "") if admission else ""

            record_data = {
                "admission_id": admission_id,
                "patient_name": patient_name,
                "fee_category": fee_category,
                "amount": amount_total / 100.0,  # 分转元
                "billing_cycle": billing_cycle,
                "period_start": period_start,
                "period_end": period_end,
                "payment_method": "wechat",
                "receipt_number": out_trade_no,
                "payer": "微信支付",
                "notes": f"微信支付自动入账: {out_trade_no}",
            }
            billing_store.create_billing_record(record_data)
            logger.info(f"微信支付自动创建缴费记录: admission={admission_id}, amount={amount_total/100}元")

            audit.log("WECHAT_PAY_SUCCESS", "", "system",
                      doc_id=out_trade_no,
                      detail=f"支付成功自动入账: {amount_total/100}元, admission={admission_id}")
    except Exception as e:
        logger.error(f"微信支付回调处理异常(不影响返回): {e}")

    return JSONResponse(content={"code": "SUCCESS", "message": "OK"})


@router.get("/pay/wechat/status", summary="微信支付配置状态")
async def wechat_pay_status(
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """查询当前微信支付配置是否完整可用。"""
    wechat_pay = get_wechat_pay_service()
    return {
        "code": 200,
        "enabled": wechat_pay.is_enabled,
        "mch_id": wechat_pay._mch_id[:4] + "****" if wechat_pay._mch_id else "",
        "app_id": wechat_pay._app_id[:4] + "****" if wechat_pay._app_id else "",
        "message": "微信支付已配置" if wechat_pay.is_enabled else "微信支付未配置（模拟模式）",
    }
