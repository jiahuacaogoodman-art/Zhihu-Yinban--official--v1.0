# -*- coding: utf-8 -*-
"""
@File    : tests/test_pdf_generator.py
@Desc    : PDF 生成器单元测试

覆盖：
  1. amount_to_chinese：边界、跨节零、四舍五入、负数、0.x 金额
  2. 4 种文档生成：返回真 PDF（%PDF 头）、字节非空
  3. XML 注入字符不会让 reportlab 崩溃
"""

from __future__ import annotations

import pytest

from app.services.pdf_generator import (
    amount_to_chinese,
    generate_billing_receipt_pdf,
    generate_care_records_pdf,
    generate_handover_pdf,
    generate_patient_profile_pdf,
)


class TestAmountToChinese:
    """金额转中文大写。修复 PR4 原版的多处 bug。"""

    @pytest.mark.parametrize("amt,expect", [
        (0, "零元整"),
        (1, "壹元整"),
        (10, "壹拾元整"),
        (100, "壹佰元整"),
        (1000, "壹仟元整"),
        (10000, "壹万元整"),
        (100000, "壹拾万元整"),
        (1000000, "壹佰万元整"),
        (10000000, "壹仟万元整"),
        (100000000, "壹亿元整"),
        (10000000000, "壹佰亿元整"),
    ])
    def test_basic_powers(self, amt, expect):
        assert amount_to_chinese(amt) == expect

    @pytest.mark.parametrize("amt,expect", [
        # 跨节零 —— PR4 原版会丢掉这个"零"
        (10001, "壹万零壹元整"),
        (100050, "壹拾万零伍拾元整"),
        (100100, "壹拾万零壹佰元整"),
        (100200000, "壹亿零贰拾万元整"),
        # 节内零归并
        (1005, "壹仟零伍元整"),
        (1234.56, "壹仟贰佰叁拾肆元伍角陆分"),
    ])
    def test_zero_compaction(self, amt, expect):
        assert amount_to_chinese(amt) == expect

    @pytest.mark.parametrize("amt,expect", [
        (1.5, "壹元伍角"),
        (1.55, "壹元伍角伍分"),
        (1.05, "壹元零伍分"),
        (100000.5, "壹拾万元伍角"),
        # 0.x 不带"零元"
        (0.5, "伍角"),
        (0.55, "伍角伍分"),
        (0.05, "伍分"),
    ])
    def test_jiao_fen(self, amt, expect):
        assert amount_to_chinese(amt) == expect

    @pytest.mark.parametrize("amt,expect", [
        # ROUND_HALF_UP（PR4 用 round() 是 banker rounding）
        (0.005, "壹分"),
        (0.004, "零元整"),
        (1.999, "贰元整"),
        (0.999, "壹元整"),
    ])
    def test_rounding(self, amt, expect):
        assert amount_to_chinese(amt) == expect

    def test_negative(self):
        assert amount_to_chinese(-1) == "负壹元整"
        assert amount_to_chinese(-1234.56) == "负壹仟贰佰叁拾肆元伍角陆分"

    def test_real_world_receipt(self):
        # PR4 原版描述里的样例：3800 -> "叁仟捌佰元整"
        assert amount_to_chinese(3800) == "叁仟捌佰元整"


class TestPdfRendering:
    """所有生成器必须输出真 PDF（%PDF-1.x 开头），永远不返回 HTML。"""

    PDF_MAGIC = b"%PDF"

    def test_patient_profile_returns_pdf(self):
        pdf = generate_patient_profile_pdf({
            "patient_id": "P001", "name": "张三", "gender": "男", "age": 82,
            "bed_number": "A-101", "care_level": "一级", "allergy": "青霉素",
            "emergency_contact": "李四", "emergency_phone": "13800138000",
            "notes": "测试备注",
        })
        assert pdf[:4] == self.PDF_MAGIC
        assert len(pdf) > 1000

    def test_billing_receipt_returns_pdf(self):
        pdf = generate_billing_receipt_pdf(
            record={
                "record_id": "bill_x", "admission_id": "adm_1",
                "patient_name": "张三", "fee_category": "care",
                "amount": 3800.50, "period_start": "2026-05-01",
                "period_end": "2026-05-31", "payment_method": "wechat",
                "payer": "李四", "paid_at": "2026-05-17",
                "notes": "5月护理费",
            },
            admission=None,
        )
        assert pdf[:4] == self.PDF_MAGIC
        assert len(pdf) > 1000

    def test_handover_returns_pdf(self):
        pdf = generate_handover_pdf({
            "handover_id": "h_1", "shift_from": "王护士", "shift_to": "赵护士",
            "shift_type": "day_to_night", "patient_id": "P001",
            "patient_name": "张三", "status": "pending",
            "situation": "血压偏高", "background": "高血压病史",
            "assessment": "稳定", "recommendation": "继续观察",
            "pending_tasks": "4 小时后复测", "created_at": "2026-05-17 16:00",
        })
        assert pdf[:4] == self.PDF_MAGIC
        assert len(pdf) > 1000

    def test_care_records_returns_pdf(self):
        records = [
            {"recorded_at": "2026-05-17 08:00", "record_type": "observation",
             "content": "晨起精神良好", "recorded_by": "王护士", "shift": "morning"},
            {"recorded_at": "2026-05-17 12:30", "record_type": "medication",
             "content": "按医嘱服用降压药", "recorded_by": "王护士", "shift": "morning"},
        ]
        pdf = generate_care_records_pdf("张三", "P001", records)
        assert pdf[:4] == self.PDF_MAGIC
        assert len(pdf) > 1000

    def test_care_records_handles_empty(self):
        pdf = generate_care_records_pdf("张三", "P001", [])
        assert pdf[:4] == self.PDF_MAGIC

    def test_xml_special_chars_do_not_crash(self):
        """档案里有 < > & 等 XML 特殊字符时不能让 reportlab 崩。"""
        pdf = generate_patient_profile_pdf({
            "patient_id": "P002", "name": "<script>alert('x')</script>",
            "notes": "AT&T 与 R&D 部门 <主任>",
            "allergy": "Q&A 测试 <已知>",
        })
        assert pdf[:4] == self.PDF_MAGIC

    def test_missing_fields_render_dash(self):
        """字段缺失时不应抛 KeyError。"""
        pdf = generate_patient_profile_pdf({"patient_id": "P003"})
        assert pdf[:4] == self.PDF_MAGIC
