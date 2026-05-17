# -*- coding: utf-8 -*-
"""
@File    : app/models/billing_schemas.py
@Desc    : 缴费管理 Pydantic Schema —— 收费标准、缴费记录、续费、到期状态

功能模块：
  1. 收费标准(Fee Standard)：后台设置不同档位的收费标准（按护理等级/房型/服务项目）
  2. 缴费记录(Billing Record)：记录每笔缴费的详细信息（入院时间、缴费时间、金额、周期）
  3. 续费管理(Renewal)：续费操作，自动延长截止时间
  4. 到期状态(Billing Status)：根据缴费截止时间计算当前状态（正常/即将到期/已欠费）
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 收费标准 (Fee Standard)
# ============================================================
FeeCategory = Literal[
    "bed",           # 床位费
    "care",          # 护理费
    "meal",          # 餐饮费
    "medical",       # 医疗费
    "supplies",      # 耗材费
    "service",       # 增值服务费
    "other",         # 其他
]

BillingCycle = Literal["monthly", "quarterly", "semi_annual", "yearly"]


class FeeStandardCreateRequest(BaseModel):
    """POST /api/billing/fee-standards — 创建收费标准"""
    name: str = Field(..., min_length=1, max_length=64, description="标准名称，如：单人间床位费/二级护理费")
    category: FeeCategory = Field(..., description="费用类别")
    care_level_key: Optional[str] = Field(default=None, max_length=32,
                                           description="适用护理等级(空=不限)")
    room_type: Optional[str] = Field(default=None, max_length=32,
                                      description="适用房型: 单人间/双人间/多人间(空=不限)")
    unit_price: float = Field(..., ge=0, description="单价(元)")
    billing_cycle: BillingCycle = Field(default="monthly", description="计费周期")
    description: Optional[str] = Field(default=None, max_length=512, description="说明")
    is_required: bool = Field(default=True, description="是否为必选项目(入住必缴)")
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, ge=0, description="排序序号")


class FeeStandardUpdateRequest(BaseModel):
    """PATCH /api/billing/fee-standards/{standard_id} — 更新收费标准"""
    name: Optional[str] = Field(default=None, max_length=64)
    category: Optional[FeeCategory] = None
    care_level_key: Optional[str] = Field(default=None, max_length=32)
    room_type: Optional[str] = Field(default=None, max_length=32)
    unit_price: Optional[float] = Field(default=None, ge=0)
    billing_cycle: Optional[BillingCycle] = None
    description: Optional[str] = Field(default=None, max_length=512)
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class FeeStandardResponse(BaseModel):
    """收费标准响应"""
    model_config = ConfigDict(extra="ignore")

    standard_id: str
    name: str
    category: str
    care_level_key: Optional[str] = None
    room_type: Optional[str] = None
    unit_price: float
    billing_cycle: str = "monthly"
    description: Optional[str] = None
    is_required: bool = True
    is_active: bool = True
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""


class FeeStandardListResponse(BaseModel):
    code: int = 200
    message: Optional[str] = None
    total: int
    standards: List[FeeStandardResponse] = Field(default_factory=list)


# ============================================================
# 缴费记录 (Billing Record)
# ============================================================
PaymentMethod = Literal["cash", "bank_transfer", "wechat", "alipay", "pos", "other"]

BillingStatus = Literal[
    "normal",         # 正常（未到期）
    "expiring_soon",  # 即将到期（7天内）
    "overdue",        # 已欠费（超过截止日期）
    "settled",        # 已结清（离院结算）
]


class BillingRecordCreateRequest(BaseModel):
    """POST /api/billing/records — 创建缴费记录（首次缴费/续费）"""
    admission_id: str = Field(..., min_length=1, description="入住申请ID")
    fee_standard_id: Optional[str] = Field(default=None, description="关联收费标准ID(可选)")
    fee_category: FeeCategory = Field(default="care", description="费用类别")
    amount: float = Field(..., gt=0, description="缴费金额(元)")
    billing_cycle: BillingCycle = Field(default="monthly", description="缴费周期")
    period_start: str = Field(..., min_length=1, description="费用起始日期 YYYY-MM-DD")
    period_end: str = Field(..., min_length=1, description="费用截止日期 YYYY-MM-DD")
    payment_method: PaymentMethod = Field(default="cash", description="支付方式")
    receipt_number: Optional[str] = Field(default=None, max_length=64, description="收据/发票编号")
    payer: Optional[str] = Field(default=None, max_length=64, description="缴费人")
    notes: Optional[str] = Field(default=None, max_length=256)


class BillingRecordResponse(BaseModel):
    """缴费记录响应"""
    model_config = ConfigDict(extra="ignore")

    record_id: str
    admission_id: str
    patient_name: Optional[str] = None
    fee_standard_id: Optional[str] = None
    fee_standard_name: Optional[str] = None
    fee_category: str = "care"
    amount: float
    billing_cycle: str = "monthly"
    period_start: str
    period_end: str
    payment_method: str = "cash"
    receipt_number: Optional[str] = None
    payer: Optional[str] = None
    paid_at: str = ""
    notes: Optional[str] = None
    created_at: str = ""


class BillingRecordListResponse(BaseModel):
    code: int = 200
    message: Optional[str] = None
    total: int
    records: List[BillingRecordResponse] = Field(default_factory=list)


# ============================================================
# 续费 (Renewal)
# ============================================================
class RenewalRequest(BaseModel):
    """POST /api/billing/renew — 续费（自动根据上次缴费截止日期往后延）"""
    admission_id: str = Field(..., min_length=1, description="入住申请ID")
    fee_category: FeeCategory = Field(default="care", description="续费的费用类别")
    amount: float = Field(..., gt=0, description="续费金额(元)")
    billing_cycle: BillingCycle = Field(default="monthly", description="续费周期")
    num_cycles: int = Field(default=1, ge=1, le=24, description="续费周期数(如3个月=cycle=monthly,num=3)")
    payment_method: PaymentMethod = Field(default="cash", description="支付方式")
    receipt_number: Optional[str] = Field(default=None, max_length=64)
    payer: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=256)


class RenewalResponse(BaseModel):
    """续费响应"""
    model_config = ConfigDict(extra="ignore")

    record_id: str
    admission_id: str
    patient_name: Optional[str] = None
    fee_category: str
    amount: float
    billing_cycle: str
    period_start: str
    period_end: str
    payment_method: str = "cash"
    receipt_number: Optional[str] = None
    payer: Optional[str] = None
    paid_at: str = ""
    previous_end_date: str = ""
    new_end_date: str = ""
    notes: Optional[str] = None


# ============================================================
# 账单状态总览 (Billing Overview per resident)
# ============================================================
class ResidentBillingOverview(BaseModel):
    """单个老人的缴费状态总览"""
    model_config = ConfigDict(extra="ignore")

    admission_id: str
    patient_name: str = ""
    bed_number: Optional[str] = None
    care_level_key: Optional[str] = None
    admission_date: Optional[str] = None

    # 缴费状态
    billing_status: str = "normal"  # normal/expiring_soon/overdue/settled
    latest_period_end: Optional[str] = None  # 最近一笔缴费的截止日期
    days_remaining: Optional[int] = None  # 剩余天数（负数=已欠费天数）
    total_paid: float = 0.0  # 累计已缴金额
    total_records: int = 0  # 缴费笔数


class BillingOverviewListResponse(BaseModel):
    code: int = 200
    message: Optional[str] = None
    total: int
    summary: dict = Field(default_factory=dict)  # 汇总：正常/即将到期/已欠费 人数
    residents: List[ResidentBillingOverview] = Field(default_factory=list)


# ============================================================
# 到期提醒列表
# ============================================================
class ExpiryAlertItem(BaseModel):
    """到期/欠费提醒条目"""
    admission_id: str
    patient_name: str = ""
    bed_number: Optional[str] = None
    billing_status: str  # expiring_soon / overdue
    latest_period_end: str = ""
    days_remaining: int = 0  # 负=已欠费天数
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class ExpiryAlertListResponse(BaseModel):
    code: int = 200
    message: Optional[str] = None
    total: int
    alerts: List[ExpiryAlertItem] = Field(default_factory=list)


__all__ = [
    "FeeCategory", "BillingCycle", "PaymentMethod", "BillingStatus",
    "FeeStandardCreateRequest", "FeeStandardUpdateRequest",
    "FeeStandardResponse", "FeeStandardListResponse",
    "BillingRecordCreateRequest", "BillingRecordResponse", "BillingRecordListResponse",
    "RenewalRequest", "RenewalResponse",
    "ResidentBillingOverview", "BillingOverviewListResponse",
    "ExpiryAlertItem", "ExpiryAlertListResponse",
]
