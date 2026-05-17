# -*- coding: utf-8 -*-
"""
@File    : tests/test_pdf_export.py
@Desc    : PDF 导出真实生成测试

验证内容：
  1. 4种文档（档案/收据/交接班/护理记录）都能生成有效 PDF
  2. 每个 PDF 都以 %PDF 标志开头（真实 PDF 文件）
  3. 中文字符正确嵌入（提取文字验证）
  4. 金额转中文大写正确（财务规范）
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAmountToChinese:
    """金额转中文大写测试 — 财务规范，必须100%正确"""

    def test_integer_amounts(self):
        from app.services.pdf_generator import _amount_to_chinese
        assert _amount_to_chinese(0) == "整"
        assert _amount_to_chinese(1) == "壹元整"
        assert _amount_to_chinese(10) == "壹拾元整"
        assert _amount_to_chinese(100) == "壹佰元整"
        assert _amount_to_chinese(1000) == "壹仟元整"
        assert _amount_to_chinese(3000) == "叁仟元整"
        assert _amount_to_chinese(3800) == "叁仟捌佰元整"
        assert _amount_to_chinese(10000) == "壹万元整"
        assert _amount_to_chinese(1000000) == "壹佰万元整"

    def test_amounts_with_decimals(self):
        from app.services.pdf_generator import _amount_to_chinese
        assert _amount_to_chinese(100.5) == "壹佰元伍角"
        assert _amount_to_chinese(100.55) == "壹佰元伍角伍分"
        assert _amount_to_chinese(100.05) == "壹佰元伍分"
        assert _amount_to_chinese(0.5) == "伍角"
        assert _amount_to_chinese(0.55) == "伍角伍分"

    def test_complex_amounts(self):
        from app.services.pdf_generator import _amount_to_chinese
        assert _amount_to_chinese(12345.67) == "壹万贰仟叁佰肆拾伍元陆角柒分"
        assert _amount_to_chinese(1234567.89) == "壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分"


class TestPDFGeneration:
    """真实 PDF 生成测试"""

    def test_patient_profile_pdf_is_valid_pdf(self):
        """档案卡：必须是有效PDF，且包含老人姓名"""
        from app.services.pdf_generator import generate_patient_profile_pdf
        pdf = generate_patient_profile_pdf({
            "patient_id": "P001", "name": "张奶奶", "gender": "女", "age": 82,
            "bed_number": "301-A", "care_level": "二级护理",
            "medical_history": "高血压20年",
        })
        # 真实 PDF 文件以 %PDF- 开头
        assert pdf[:5] == b"%PDF-", f"不是有效PDF: {pdf[:20]}"
        assert len(pdf) > 1000, "PDF 文件太小，可能内容不完整"

    def test_billing_receipt_pdf_contains_amount_and_chinese(self):
        """收据：必须包含金额、大写、缴费人"""
        from app.services.pdf_generator import generate_billing_receipt_pdf
        pdf = generate_billing_receipt_pdf({
            "record_id": "bill_001",
            "admission_id": "adm_xyz",
            "patient_name": "张奶奶",
            "fee_category": "care",
            "amount": 3800.00,
            "billing_cycle": "monthly",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "payment_method": "wechat",
            "payer": "张小明",
            "paid_at": "2026-05-28 14:30:00",
        })
        assert pdf[:5] == b"%PDF-"
        # 用 PyMuPDF 提取文字验证（如果 fitz 不可用就只验 PDF 头）
        try:
            import fitz
            doc = fitz.open(stream=pdf, filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            doc.close()
            assert "缴费收据" in text or "缴 费 收 据" in text
            assert "3,800" in text  # 数字金额
            assert "叁仟捌佰元整" in text  # 大写金额
            assert "张奶奶" in text
            assert "微信支付" in text
            assert "张小明" in text
        except ImportError:
            pass  # 没装 fitz 就只验头部

    def test_handover_pdf_contains_sbar_sections(self):
        """交接班：必须包含 SBAR 四段式"""
        from app.services.pdf_generator import generate_handover_pdf
        pdf = generate_handover_pdf({
            "handover_id": "hov_001",
            "shift_from": "王护士", "shift_to": "赵护士",
            "shift_type": "白班→夜班",
            "patient_name": "张奶奶", "patient_id": "P001",
            "situation": "下午3点诉头晕",
            "background": "糖尿病15年",
            "assessment": "考虑低血糖",
            "recommendation": "继续观察",
            "status": "acknowledged",
            "created_at": "2026-05-17 16:00:00",
        })
        assert pdf[:5] == b"%PDF-"
        try:
            import fitz
            doc = fitz.open(stream=pdf, filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            doc.close()
            assert "SBAR" in text
            assert "Situation" in text
            assert "Background" in text
            assert "Assessment" in text
            assert "Recommendation" in text
            assert "王护士" in text
            assert "赵护士" in text
        except ImportError:
            pass

    def test_care_records_pdf_with_records(self):
        """护理记录：包含多条记录"""
        from app.services.pdf_generator import generate_care_records_pdf
        records = [
            {"recorded_at": "2026-05-17 08:00", "record_type": "体征",
             "content": "体温36.5℃", "recorded_by": "王护士", "shift": "白班"},
            {"recorded_at": "2026-05-17 12:00", "record_type": "进食",
             "content": "午餐进食2/3", "recorded_by": "李护士", "shift": "白班"},
        ]
        pdf = generate_care_records_pdf("张奶奶", "P001", records)
        assert pdf[:5] == b"%PDF-"
        try:
            import fitz
            doc = fitz.open(stream=pdf, filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            doc.close()
            assert "护理记录单" in text
            assert "张奶奶" in text
            assert "王护士" in text
            assert "李护士" in text
            assert "体温36.5℃" in text
            assert "记录数：2" in text
        except ImportError:
            pass

    def test_care_records_empty_list(self):
        """空护理记录也应该正常生成"""
        from app.services.pdf_generator import generate_care_records_pdf
        pdf = generate_care_records_pdf("张奶奶", "P001", [])
        assert pdf[:5] == b"%PDF-"
