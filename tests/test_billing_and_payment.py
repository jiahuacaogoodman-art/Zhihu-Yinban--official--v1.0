# -*- coding: utf-8 -*-
"""
@File    : tests/test_billing_and_payment.py
@Desc    : 缴费管理 + 支付渠道 核心逻辑单元测试

验证内容：
  1. BillingStore 基础 CRUD
  2. 收费标准创建/查询/更新/删除
  3. 缴费记录创建/查询
  4. 续费逻辑（周期计算、自动延期）
  5. 到期状态计算（正常/即将到期/已欠费）
  6. PaymentChannelStore 渠道管理
  7. 微信支付模拟模式
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestBillingStore:
    """BillingStore 核心功能测试"""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.services.billing_store import BillingStore
        self.store = BillingStore(tmp_path / "test_billing.db")

    def test_create_fee_standard(self):
        """测试创建收费标准"""
        std = self.store.create_fee_standard({
            "name": "单人间床位费",
            "category": "bed",
            "unit_price": 3000,
            "billing_cycle": "monthly",
            "room_type": "单人间",
        })
        assert std["standard_id"].startswith("fs_")
        assert std["name"] == "单人间床位费"
        assert std["unit_price"] == 3000
        assert std["category"] == "bed"
        assert std["is_active"] is True
        assert std["is_required"] is True

    def test_list_fee_standards(self):
        """测试查询收费标准列表"""
        self.store.create_fee_standard({"name": "床位费", "category": "bed", "unit_price": 2000})
        self.store.create_fee_standard({"name": "护理费", "category": "care", "unit_price": 1500})
        self.store.create_fee_standard({"name": "餐饮费", "category": "meal", "unit_price": 800})

        all_stds = self.store.list_fee_standards()
        assert len(all_stds) == 3

        bed_only = self.store.list_fee_standards(category="bed")
        assert len(bed_only) == 1
        assert bed_only[0]["name"] == "床位费"

    def test_update_fee_standard(self):
        """测试更新收费标准"""
        std = self.store.create_fee_standard({"name": "旧名称", "category": "care", "unit_price": 1000})
        updated = self.store.update_fee_standard(std["standard_id"], {"name": "新名称", "unit_price": 1500})
        assert updated["name"] == "新名称"
        assert updated["unit_price"] == 1500

    def test_delete_fee_standard(self):
        """测试删除收费标准"""
        std = self.store.create_fee_standard({"name": "临时标准", "category": "other", "unit_price": 100})
        assert self.store.delete_fee_standard(std["standard_id"]) is True
        assert self.store.get_fee_standard(std["standard_id"]) is None

    def test_create_billing_record(self):
        """测试创建缴费记录"""
        record = self.store.create_billing_record({
            "admission_id": "adm_test001",
            "patient_name": "张三",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "payment_method": "cash",
            "payer": "张小明",
        })
        assert record["record_id"].startswith("bill_")
        assert record["amount"] == 3000
        assert record["period_start"] == "2026-06-01"
        assert record["period_end"] == "2026-06-30"
        assert record["patient_name"] == "张三"

    def test_period_calculation_monthly(self):
        """测试月周期计算"""
        end = self.store._calc_period_end("2026-06-01", "monthly", 1)
        assert end == "2026-06-30"

        end3 = self.store._calc_period_end("2026-06-01", "monthly", 3)
        assert end3 == "2026-08-31"

    def test_period_calculation_quarterly(self):
        """测试季度周期计算"""
        end = self.store._calc_period_end("2026-01-01", "quarterly", 1)
        assert end == "2026-03-31"

    def test_period_calculation_yearly(self):
        """测试年周期计算"""
        end = self.store._calc_period_end("2026-01-01", "yearly", 1)
        assert end == "2026-12-31"

    def test_period_calculation_semi_annual(self):
        """测试半年周期计算"""
        end = self.store._calc_period_end("2026-01-01", "semi_annual", 1)
        assert end == "2026-06-30"

    def test_renew_from_scratch(self):
        """测试首次续费（无历史记录时从今天开始）"""
        result = self.store.renew({
            "admission_id": "adm_new001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "num_cycles": 1,
        })
        assert result["record_id"].startswith("bill_")
        assert result["period_start"] == datetime.now().strftime("%Y-%m-%d")
        assert result["previous_end_date"] == ""

    def test_renew_continues_from_last(self):
        """测试续费从上次截止日期继续"""
        # 先创建一笔记录
        self.store.create_billing_record({
            "admission_id": "adm_renew001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "payment_method": "cash",
        })
        # 续费
        result = self.store.renew({
            "admission_id": "adm_renew001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "num_cycles": 2,
        })
        assert result["period_start"] == "2026-06-01"  # 上次截止的次日
        assert result["new_end_date"] == "2026-07-31"  # 2个月
        assert result["previous_end_date"] == "2026-05-31"

    def test_billing_status_normal(self):
        """测试缴费状态：正常"""
        future_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_status001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "period_start": "2026-01-01",
            "period_end": future_end,
            "payment_method": "cash",
        })
        status = self.store.get_billing_status_for_admission("adm_status001")
        assert status["billing_status"] == "normal"
        assert status["days_remaining"] > 7
        assert status["total_paid"] == 3000
        assert status["total_records"] == 1

    def test_billing_status_expiring_soon(self):
        """测试缴费状态：即将到期"""
        soon_end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_expiring001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "period_start": "2026-01-01",
            "period_end": soon_end,
            "payment_method": "cash",
        })
        status = self.store.get_billing_status_for_admission("adm_expiring001")
        assert status["billing_status"] == "expiring_soon"
        assert 0 <= status["days_remaining"] <= 7

    def test_billing_status_overdue(self):
        """测试缴费状态：已欠费"""
        past_end = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_overdue001",
            "fee_category": "care",
            "amount": 3000,
            "billing_cycle": "monthly",
            "period_start": "2025-01-01",
            "period_end": past_end,
            "payment_method": "cash",
        })
        status = self.store.get_billing_status_for_admission("adm_overdue001")
        assert status["billing_status"] == "overdue"
        assert status["days_remaining"] < 0

    def test_expiry_alerts(self):
        """测试到期提醒列表"""
        # 一个快到期的
        soon = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_alert001",
            "amount": 1000, "fee_category": "care", "billing_cycle": "monthly",
            "period_start": "2026-01-01", "period_end": soon, "payment_method": "cash",
        })
        # 一个已欠费的
        past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_alert002",
            "amount": 2000, "fee_category": "care", "billing_cycle": "monthly",
            "period_start": "2025-01-01", "period_end": past, "payment_method": "cash",
        })
        # 一个正常的
        future = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        self.store.create_billing_record({
            "admission_id": "adm_alert003",
            "amount": 3000, "fee_category": "care", "billing_cycle": "monthly",
            "period_start": "2026-01-01", "period_end": future, "payment_method": "cash",
        })
        alerts = self.store.get_expiry_alerts(days_threshold=7)
        assert len(alerts) == 2  # 只有前两个
        # 欠费的排在最前面
        assert alerts[0]["admission_id"] == "adm_alert002"
        assert alerts[0]["billing_status"] == "overdue"


class TestPaymentChannelStore:
    """PaymentChannelStore 渠道管理测试"""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.services.payment_channels import PaymentChannelStore
        self.store = PaymentChannelStore(tmp_path / "test_channels.db")

    def test_initial_channels(self):
        """测试初始渠道列表"""
        channels = self.store.get_all_channels()
        keys = [c["channel_key"] for c in channels]
        assert "cash" in keys
        assert "bank_transfer" in keys
        assert "wechat" in keys
        assert "alipay" in keys
        assert "pos" in keys

    def test_offline_channels_enabled_by_default(self):
        """测试离线渠道默认启用"""
        channels = self.store.get_all_channels()
        for c in channels:
            if not c["requires_config"]:
                assert c["is_enabled"] is True, f"{c['channel_key']} should be enabled"

    def test_online_channels_disabled_by_default(self):
        """测试在线渠道默认停用（需配置后才能启用）"""
        channels = self.store.get_all_channels()
        for c in channels:
            if c["requires_config"]:
                assert c["is_enabled"] is False, f"{c['channel_key']} should be disabled"

    def test_enable_disable_channel(self):
        """测试启用/停用渠道"""
        # 停用现金
        self.store.update_channel("cash", is_enabled=False, operator="admin")
        ch = self.store.get_channel("cash")
        assert ch["is_enabled"] is False

        # 重新启用
        self.store.update_channel("cash", is_enabled=True, operator="admin")
        ch = self.store.get_channel("cash")
        assert ch["is_enabled"] is True

    def test_update_config(self):
        """测试更新渠道配置"""
        self.store.update_channel("wechat", config={
            "mch_id": "1234567890",
            "app_id": "wx_test_app",
        }, operator="admin")
        raw = self.store.get_raw_config("wechat")
        assert raw["mch_id"] == "1234567890"
        assert raw["app_id"] == "wx_test_app"

    def test_config_masking(self):
        """测试配置脱敏（密码字段不暴露）"""
        self.store.update_channel("wechat", config={
            "mch_id": "1234567890",
            "api_key_v3": "super_secret_key_32_bytes_long!!",
        }, operator="admin")
        ch = self.store.get_channel("wechat")
        # mch_id 不是 password 类型，应该显示
        assert ch["config"]["mch_id"] == "1234567890"
        # api_key_v3 是 password 类型，应该脱敏
        assert ch["config"]["api_key_v3"] == "●●●●●●"

    def test_enabled_channels_list(self):
        """测试获取已启用渠道列表"""
        enabled = self.store.get_enabled_channels()
        # 默认只有离线渠道启用
        assert "cash" in enabled
        assert "bank_transfer" in enabled
        assert "pos" in enabled
        assert "wechat" not in enabled
        assert "alipay" not in enabled


class TestWechatPayNotConfigured:
    """微信支付未配置时应直接报错不可用"""

    def test_native_order_unavailable(self):
        """未配置时下单应返回错误"""
        from app.services.wechat_pay import WechatPayService
        svc = WechatPayService()
        assert svc.is_enabled is False

        result = svc.create_native_order(
            out_trade_no="TEST001",
            description="测试订单",
            total_amount=100,
        )
        assert result.get("error") is True
        assert "未配置" in result.get("message", "")

    def test_jsapi_order_unavailable(self):
        """未配置时 JSAPI 下单应返回错误"""
        from app.services.wechat_pay import WechatPayService
        svc = WechatPayService()

        result = svc.create_jsapi_order(
            out_trade_no="TEST002",
            description="测试JSAPI",
            total_amount=200,
            openid="test_openid",
        )
        assert result.get("error") is True
        assert "未配置" in result.get("message", "")

    def test_query_unavailable(self):
        """未配置时查询应返回错误"""
        from app.services.wechat_pay import WechatPayService
        svc = WechatPayService()

        result = svc.query_order("TEST001")
        assert result.get("error") is True

    def test_refund_unavailable(self):
        """未配置时退款应返回错误"""
        from app.services.wechat_pay import WechatPayService
        svc = WechatPayService()

        result = svc.refund(
            out_trade_no="TEST001",
            out_refund_no="REFUND001",
            total_amount=100,
            refund_amount=50,
        )
        assert result.get("error") is True

    def test_generate_trade_no(self):
        """测试订单号生成唯一性"""
        from app.services.wechat_pay import WechatPayService
        no1 = WechatPayService.generate_trade_no()
        no2 = WechatPayService.generate_trade_no()
        assert no1 != no2
        assert no1.startswith("ZHYB")
