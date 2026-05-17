# -*- coding: utf-8 -*-
"""
@File    : app/routers/billing.py
@Desc    : 缴费管理路由 —— 收费标准后台设置 + 缴费记录 + 续费 + 到期提醒

完整功能清单：
  1. 收费标准 CRUD（后台管理员设置不同档位的收费标准）
  2. 缴费记录管理（记录入院时间/缴费时间/缴费金额/缴费周期）
  3. 续费操作（自动根据上次截止时间向后延续）
  4. 账单状态总览（列出所有老人的缴费状态：正常/即将到期/已欠费）
  5. 到期提醒列表（运营人员每日关注）
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.middleware.auth import require_permission
from app.models.billing_schemas import (
    FeeStandardCreateRequest, FeeStandardUpdateRequest,
    FeeStandardResponse, FeeStandardListResponse,
    BillingRecordCreateRequest, BillingRecordResponse, BillingRecordListResponse,
    RenewalRequest, RenewalResponse,
    ResidentBillingOverview, BillingOverviewListResponse,
    ExpiryAlertItem, ExpiryAlertListResponse,
)
from app.services.audit_log import get_audit_log
from app.services.billing_store import get_billing_store
from app.services.care_store import get_care_store
from app.services.permissions import PERM_EHR_WRITE, PERM_EHR_READ
from app.services.user_store import User

router = APIRouter()
audit = get_audit_log()


# ================================================================
# 1. 收费标准管理 (Fee Standards)
# ================================================================

@router.post("/billing/fee-standards", response_model=FeeStandardResponse,
             summary="创建收费标准(后台设置)")
async def create_fee_standard(
    payload: FeeStandardCreateRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    后台管理员创建收费标准。可按护理等级、房型分别设置不同费用项。
    例如：
      - 单人间床位费 3000元/月
      - 二级护理费 2500元/月
      - 三餐餐饮费 800元/月
    """
    store = get_billing_store()
    standard = store.create_fee_standard(payload.model_dump())
    audit.log("BILLING_FEE_STANDARD_CREATE", "", user.username,
              doc_id=standard["standard_id"],
              detail=f"创建收费标准: {payload.name}, {payload.unit_price}元/{payload.billing_cycle}")
    logger.info(f"收费标准创建: {standard['standard_id']}, name={payload.name}, operator={user.username}")
    return FeeStandardResponse(**standard)


@router.get("/billing/fee-standards", response_model=FeeStandardListResponse,
            summary="查询收费标准列表")
async def list_fee_standards(
    category: Optional[str] = Query(default=None, description="费用类别筛选"),
    care_level_key: Optional[str] = Query(default=None, description="适用护理等级筛选"),
    include_inactive: bool = Query(default=False, description="是否包含已停用的标准"),
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    store = get_billing_store()
    standards = store.list_fee_standards(
        category=category,
        care_level_key=care_level_key,
        active_only=not include_inactive,
    )
    return FeeStandardListResponse(
        code=200, total=len(standards),
        standards=[FeeStandardResponse(**s) for s in standards],
    )


@router.get("/billing/fee-standards/{standard_id}", response_model=FeeStandardResponse,
            summary="查询单个收费标准")
async def get_fee_standard(
    standard_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    store = get_billing_store()
    standard = store.get_fee_standard(standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="收费标准不存在")
    return FeeStandardResponse(**standard)


@router.patch("/billing/fee-standards/{standard_id}", response_model=FeeStandardResponse,
              summary="更新收费标准")
async def update_fee_standard(
    standard_id: str,
    payload: FeeStandardUpdateRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    store = get_billing_store()
    # 只传有值的字段
    update_data = payload.model_dump(exclude_unset=True)
    result = store.update_fee_standard(standard_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="收费标准不存在")
    audit.log("BILLING_FEE_STANDARD_UPDATE", "", user.username,
              doc_id=standard_id, detail=f"更新收费标准: {update_data}")
    return FeeStandardResponse(**result)


@router.delete("/billing/fee-standards/{standard_id}", summary="删除收费标准")
async def delete_fee_standard(
    standard_id: str,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    store = get_billing_store()
    success = store.delete_fee_standard(standard_id)
    if not success:
        raise HTTPException(status_code=404, detail="收费标准不存在")
    audit.log("BILLING_FEE_STANDARD_DELETE", "", user.username,
              doc_id=standard_id, detail="删除收费标准")
    return {"code": 200, "message": "收费标准已删除"}


# ================================================================
# 2. 缴费记录管理 (Billing Records)
# ================================================================

@router.post("/billing/records", response_model=BillingRecordResponse,
             summary="创建缴费记录(首次缴费)")
async def create_billing_record(
    payload: BillingRecordCreateRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    记录一笔缴费。需要指定：
      - admission_id: 入住申请ID
      - amount: 缴费金额
      - period_start / period_end: 费用覆盖的起止日期
      - billing_cycle: 缴费周期
      - payment_method: 支付方式
    """
    # 验证 admission_id 存在
    care_store = get_care_store()
    admission = care_store.get_admission(payload.admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="入住申请不存在")

    billing_store = get_billing_store()
    record_data = payload.model_dump()
    record_data["patient_name"] = admission.get("applicant_name", "")
    record = billing_store.create_billing_record(record_data)

    audit.log("BILLING_RECORD_CREATE", admission.get("patient_id", ""), user.username,
              doc_id=record["record_id"],
              detail=f"缴费: {payload.amount}元, 周期={payload.period_start}~{payload.period_end}")
    logger.info(f"缴费记录创建: {record['record_id']}, admission={payload.admission_id}, "
                f"amount={payload.amount}, operator={user.username}")
    return BillingRecordResponse(**record)


@router.get("/billing/records", response_model=BillingRecordListResponse,
            summary="查询缴费记录列表")
async def list_billing_records(
    admission_id: Optional[str] = Query(default=None, description="按入住申请ID筛选"),
    fee_category: Optional[str] = Query(default=None, description="按费用类别筛选"),
    limit: int = Query(default=100, le=500),
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    billing_store = get_billing_store()
    records = billing_store.list_billing_records(
        admission_id=admission_id, fee_category=fee_category, limit=limit
    )
    return BillingRecordListResponse(
        code=200, total=len(records),
        records=[BillingRecordResponse(**r) for r in records],
    )


@router.get("/billing/records/{record_id}", response_model=BillingRecordResponse,
            summary="查询单个缴费记录")
async def get_billing_record(
    record_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    billing_store = get_billing_store()
    record = billing_store.get_billing_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="缴费记录不存在")
    return BillingRecordResponse(**record)


# ================================================================
# 3. 续费 (Renewal)
# ================================================================

@router.post("/billing/renew", response_model=RenewalResponse,
             summary="续费(自动从上次截止日期往后延续)")
async def renew_billing(
    payload: RenewalRequest,
    user: User = Depends(require_permission(PERM_EHR_WRITE)),
):
    """
    续费操作。系统自动根据该老人该类费用的最后截止日期，
    向后延续 num_cycles 个周期。

    示例：
      - 上次截止日期 2026-05-31，续费 1 个月 → 新起止 2026-06-01 ~ 2026-06-30
      - 上次截止日期 2026-05-31，续费 3 个月 → 新起止 2026-06-01 ~ 2026-08-31
      - 无历史记录 → 从今天开始计算
    """
    care_store = get_care_store()
    admission = care_store.get_admission(payload.admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="入住申请不存在")

    billing_store = get_billing_store()
    renew_data = payload.model_dump()
    renew_data["patient_name"] = admission.get("applicant_name", "")
    record = billing_store.renew(renew_data)

    audit.log("BILLING_RENEW", admission.get("patient_id", ""), user.username,
              doc_id=record["record_id"],
              detail=f"续费: {payload.amount}元, {payload.num_cycles}x{payload.billing_cycle}, "
                     f"新截止={record.get('new_end_date')}")
    logger.info(f"续费完成: admission={payload.admission_id}, new_end={record.get('new_end_date')}, "
                f"operator={user.username}")
    return RenewalResponse(**record)


# ================================================================
# 4. 账单状态总览 (Billing Overview)
# ================================================================

@router.get("/billing/overview", response_model=BillingOverviewListResponse,
            summary="所有老人缴费状态总览(运营仪表盘)")
async def billing_overview(
    status: Optional[str] = Query(default=None,
                                   description="状态筛选: normal/expiring_soon/overdue"),
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """
    列出所有有缴费记录的在住老人的缴费状态，便于运营人员一目了然：
      - normal: 缴费正常（离截止还有7天以上）
      - expiring_soon: 即将到期（7天内到期）
      - overdue: 已欠费（超过截止日期）
    """
    billing_store = get_billing_store()
    care_store = get_care_store()

    overviews = billing_store.get_all_billing_overviews(status_filter=status)

    # 丰富入住信息
    residents = []
    for ov in overviews:
        admission = care_store.get_admission(ov["admission_id"])
        resident = ResidentBillingOverview(
            admission_id=ov["admission_id"],
            patient_name=admission.get("applicant_name", "") if admission else "",
            bed_number=admission.get("bed_number") if admission else None,
            care_level_key=admission.get("care_level_key") if admission else None,
            admission_date=admission.get("actual_admission_date") if admission else None,
            billing_status=ov["billing_status"],
            latest_period_end=ov["latest_period_end"],
            days_remaining=ov["days_remaining"],
            total_paid=ov["total_paid"],
            total_records=ov["total_records"],
        )
        residents.append(resident)

    # 汇总统计
    summary = {"normal": 0, "expiring_soon": 0, "overdue": 0}
    for r in residents:
        if r.billing_status in summary:
            summary[r.billing_status] += 1

    return BillingOverviewListResponse(
        code=200, total=len(residents), summary=summary, residents=residents
    )


# ================================================================
# 5. 到期提醒列表 (Expiry Alerts)
# ================================================================

@router.get("/billing/alerts", response_model=ExpiryAlertListResponse,
            summary="缴费到期/欠费提醒列表")
async def get_expiry_alerts(
    days: int = Query(default=7, ge=1, le=90,
                      description="提前多少天算即将到期(默认7天)"),
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """
    获取即将到期和已欠费的老人列表，便于运营人员主动联系家属续费。
    返回内容包含老人姓名、床位号、截止日期、剩余天数、紧急联系人。
    """
    billing_store = get_billing_store()
    care_store = get_care_store()

    raw_alerts = billing_store.get_expiry_alerts(days_threshold=days)

    alerts = []
    for a in raw_alerts:
        admission = care_store.get_admission(a["admission_id"])
        # 只展示在住（active）的老人的提醒
        if not admission or admission.get("status") not in ("active", "paid", "moving_in"):
            continue
        alerts.append(ExpiryAlertItem(
            admission_id=a["admission_id"],
            patient_name=admission.get("applicant_name", ""),
            bed_number=admission.get("bed_number"),
            billing_status=a["billing_status"],
            latest_period_end=a["latest_period_end"],
            days_remaining=a["days_remaining"],
            contact_name=admission.get("guardian_name"),
            contact_phone=admission.get("guardian_phone"),
        ))

    return ExpiryAlertListResponse(code=200, total=len(alerts), alerts=alerts)


# ================================================================
# 6. 单个老人缴费状态查询
# ================================================================

@router.get("/billing/status/{admission_id}", response_model=ResidentBillingOverview,
            summary="查询单个老人的缴费状态")
async def get_resident_billing_status(
    admission_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """查询指定老人的缴费状态：当前是否正常、截止日期、剩余天数、累计缴费等。"""
    care_store = get_care_store()
    admission = care_store.get_admission(admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="入住申请不存在")

    billing_store = get_billing_store()
    status_info = billing_store.get_billing_status_for_admission(admission_id)

    return ResidentBillingOverview(
        admission_id=admission_id,
        patient_name=admission.get("applicant_name", ""),
        bed_number=admission.get("bed_number"),
        care_level_key=admission.get("care_level_key"),
        admission_date=admission.get("actual_admission_date"),
        billing_status=status_info["billing_status"],
        latest_period_end=status_info["latest_period_end"],
        days_remaining=status_info["days_remaining"],
        total_paid=status_info["total_paid"],
        total_records=status_info["total_records"],
    )
