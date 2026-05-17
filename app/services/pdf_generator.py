# -*- coding: utf-8 -*-
"""
@File    : app/services/pdf_generator.py
@Desc    : PDF 文档生成服务 —— 基于 ReportLab，纯 Python 不依赖系统库

中文渲染：使用 ReportLab 内置的 Adobe CID 字体 STSong-Light（不需要安装任何 TTF 文件）。
如果系统装了中文字体（如 Noto Sans CJK），会自动优先使用更好看的字体。

支持文档类型：
  1. 老人档案卡（generate_patient_profile_pdf）
  2. 缴费收据（generate_billing_receipt_pdf）
  3. 交接班记录单 SBAR（generate_handover_pdf）
  4. 护理记录单（generate_care_records_pdf）

设计：
  - 全部直接返回 PDF bytes，不落盘
  - A4 排版，统一页眉页脚
  - 金额自动转中文大写
  - 收据含盖章区+签字区
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
)


# ============================================================
# 字体注册：先尝试中文 TTF，再降级到 ReportLab 自带 CID 字体
# ============================================================

_FONT_NAME = "ZH-Default"
_FONT_REGISTERED = False


def _register_font():
    """注册中文字体。优先 TTF（更好看），降级 CID（自带不需要安装）。"""
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME

    # 尝试常见的中文 TTF 路径（Linux/macOS/Windows/Docker）
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        try:
            p = Path(path)
            if p.is_file():
                # TTC 文件需指定子字体索引
                if path.endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(p), subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(p)))
                _FONT_REGISTERED = True
                logger.info(f"PDF 中文字体已注册（TTF）: {path}")
                return _FONT_NAME
        except Exception:
            continue

    # 降级：用 ReportLab 自带的 Adobe CID 字体（裸装就能用）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FONT_NAME = "STSong-Light"
        _FONT_REGISTERED = True
        logger.info("PDF 中文字体已注册（CID 内置）: STSong-Light")
        return _FONT_NAME
    except Exception as e:
        logger.error(f"PDF 字体注册失败: {e}")
        raise


# ============================================================
# 通用样式与工具
# ============================================================

def _styles():
    """获取统一的段落样式。"""
    font = _register_font()
    return {
        "title": ParagraphStyle(
            name="Title", fontName=font, fontSize=20, alignment=1,  # center
            spaceAfter=14, textColor=colors.HexColor("#1a1a1a"),
        ),
        "h2": ParagraphStyle(
            name="H2", fontName=font, fontSize=13, spaceBefore=10, spaceAfter=6,
            textColor=colors.HexColor("#0f766e"), borderPadding=2,
        ),
        "body": ParagraphStyle(
            name="Body", fontName=font, fontSize=10.5, leading=16,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "small": ParagraphStyle(
            name="Small", fontName=font, fontSize=9, leading=13,
            textColor=colors.HexColor("#666666"),
        ),
        "amount": ParagraphStyle(
            name="Amount", fontName=font, fontSize=18,
            textColor=colors.HexColor("#d32f2f"),
        ),
        "footer": ParagraphStyle(
            name="Footer", fontName=font, fontSize=8.5, alignment=1,
            textColor=colors.HexColor("#999999"),
        ),
    }


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _draw_page_decoration(canvas, doc):
    """页眉页脚装饰：每页都画。"""
    font = _register_font()
    canvas.saveState()
    # 页眉
    canvas.setFont(font, 9)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(A4[0] / 2, A4[1] - 1.2 * cm, "智护银伴 · 养老护理管理系统")
    canvas.setStrokeColor(colors.HexColor("#dddddd"))
    canvas.line(1.5 * cm, A4[1] - 1.5 * cm, A4[0] - 1.5 * cm, A4[1] - 1.5 * cm)
    # 页脚
    canvas.drawString(1.5 * cm, 1 * cm, f"打印时间：{_now_str()}")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, f"第 {doc.page} 页")
    canvas.restoreState()


def _make_doc(buf: BytesIO) -> SimpleDocTemplate:
    """创建标准 A4 文档对象。"""
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
    )


def _kv_table(data: list[tuple[str, str]], col1_width: float = 3.5 * cm) -> Table:
    """生成"标签-值"两列表格。"""
    font = _register_font()
    table_data = [[label, value if value else "—"] for label, value in data]
    t = Table(table_data, colWidths=[col1_width, None])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cccccc")),
    ]))
    return t


# ============================================================
# 1. 老人档案卡
# ============================================================

def generate_patient_profile_pdf(patient: dict) -> bytes:
    """生成老人档案卡 PDF。"""
    s = _styles()
    buf = BytesIO()
    doc = _make_doc(buf)
    story = []

    story.append(Paragraph("老人档案卡", s["title"]))
    story.append(Paragraph(
        f"编号：{patient.get('patient_id', '')} &nbsp;&nbsp;|&nbsp;&nbsp; 打印时间：{_now_str()}",
        s["small"]
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("一、基本信息", s["h2"]))
    story.append(_kv_table([
        ("姓名", str(patient.get("name") or "")),
        ("性别", str(patient.get("gender") or "")),
        ("年龄", str(patient.get("age") or "")),
        ("出生日期", str(patient.get("birth_date") or "")),
        ("身份证号", str(patient.get("id_card") or "")),
        ("床位号", str(patient.get("bed_number") or "")),
        ("护理级别", str(patient.get("care_level") or "")),
        ("入院日期", str(patient.get("admission_date") or "")),
        ("主管护士", str(patient.get("primary_nurse") or "")),
    ]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("二、健康信息", s["h2"]))
    story.append(_kv_table([
        ("血型", str(patient.get("blood_type") or "")),
        ("身高(cm)", str(patient.get("height_cm") or "")),
        ("体重(kg)", str(patient.get("weight_kg") or "")),
        ("过敏史", str(patient.get("allergy") or "")),
        ("饮食禁忌", str(patient.get("diet_restriction") or "")),
        ("既往病史", str(patient.get("medical_history") or "")),
    ]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("三、紧急联系人", s["h2"]))
    story.append(_kv_table([
        ("联系人", str(patient.get("emergency_contact") or "")),
        ("联系电话", str(patient.get("emergency_phone") or "")),
        ("与老人关系", str(patient.get("emergency_relation") or "")),
    ]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("四、备注", s["h2"]))
    story.append(Paragraph(str(patient.get("notes") or "无"), s["body"]))
    story.append(Spacer(1, 30))
    story.append(Paragraph("— 本文档由智护银伴系统生成 —", s["footer"]))

    doc.build(story, onFirstPage=_draw_page_decoration, onLaterPages=_draw_page_decoration)
    return buf.getvalue()


# ============================================================
# 2. 缴费收据
# ============================================================

def generate_billing_receipt_pdf(record: dict, admission: Optional[dict] = None) -> bytes:
    """生成缴费收据 PDF。"""
    s = _styles()
    buf = BytesIO()
    doc = _make_doc(buf)
    story = []

    cat_map = {"bed": "床位费", "care": "护理费", "meal": "餐饮费", "medical": "医疗费",
               "supplies": "耗材费", "service": "增值服务", "other": "其他"}
    method_map = {"cash": "现金", "bank_transfer": "银行转账", "wechat": "微信支付",
                  "alipay": "支付宝", "pos": "POS刷卡", "other": "其他"}

    patient_name = record.get("patient_name") or (admission.get("applicant_name") if admission else "") or "—"
    amount = float(record.get("amount", 0))
    amount_cn = _amount_to_chinese(amount)

    story.append(Paragraph("缴 费 收 据", s["title"]))
    story.append(Paragraph(
        f"收据编号：{record.get('receipt_number') or record.get('record_id', '')} &nbsp;&nbsp;|&nbsp;&nbsp; 打印时间：{_now_str()}",
        s["small"]
    ))
    story.append(Spacer(1, 12))

    story.append(_kv_table([
        ("老人姓名", patient_name),
        ("入住编号", str(record.get("admission_id", ""))),
        ("费用类别", cat_map.get(record.get("fee_category", ""), str(record.get("fee_category", "")))),
    ]))
    story.append(Spacer(1, 4))

    # 金额单独高亮显示
    font = _register_font()
    amount_table = Table([
        ["缴费金额", f"¥ {amount:,.2f}"],
        ["大写金额", amount_cn],
    ], colWidths=[3.5 * cm, None])
    amount_table.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), font, 10),
        ("FONT", (1, 0), (1, 0), font, 18),  # 金额大字
        ("FONT", (1, 1), (1, 1), font, 11),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#d32f2f")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fff5f5")),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d32f2f")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ffcccc")),
    ]))
    story.append(amount_table)
    story.append(Spacer(1, 4))

    story.append(_kv_table([
        ("缴费周期", f"{record.get('period_start', '')} 至 {record.get('period_end', '')}"),
        ("支付方式", method_map.get(record.get("payment_method", ""), str(record.get("payment_method", "")))),
        ("缴费人", str(record.get("payer", "") or "—")),
        ("缴费时间", str(record.get("paid_at", ""))),
        ("备注", str(record.get("notes", "") or "—")),
    ]))

    story.append(Spacer(1, 30))

    # 盖章/签字区
    sign_table = Table([
        ["收款单位（盖章）：", "缴费人签字："],
        ["", ""],
        ["", ""],
        ["经办人：_______________", "日期：_______________"],
    ], colWidths=[(A4[0] - 3.6 * cm) / 2, (A4[0] - 3.6 * cm) / 2])
    sign_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sign_table)

    story.append(Spacer(1, 24))
    story.append(Paragraph("— 本收据由智护银伴系统生成，加盖公章后有效 —", s["footer"]))

    doc.build(story, onFirstPage=_draw_page_decoration, onLaterPages=_draw_page_decoration)
    return buf.getvalue()


# ============================================================
# 3. 交接班记录单（SBAR）
# ============================================================

def generate_handover_pdf(handover: dict) -> bytes:
    """生成 SBAR 交接班记录单 PDF。"""
    s = _styles()
    buf = BytesIO()
    doc = _make_doc(buf)
    story = []
    font = _register_font()

    story.append(Paragraph("护理交接班记录单（SBAR）", s["title"]))
    story.append(Paragraph(
        f"交接编号：{handover.get('handover_id', '')} &nbsp;&nbsp;|&nbsp;&nbsp; 创建时间：{handover.get('created_at', '')}",
        s["small"]
    ))
    story.append(Spacer(1, 10))

    story.append(_kv_table([
        ("交班人", str(handover.get("shift_from", ""))),
        ("接班人", str(handover.get("shift_to", ""))),
        ("班次", str(handover.get("shift_type", ""))),
        ("老人", f"{handover.get('patient_name', '')} ({handover.get('patient_id', '')})"),
        ("确认状态", str(handover.get("status", ""))),
    ]))
    story.append(Spacer(1, 12))

    sections = [
        ("S — 现状 (Situation)", handover.get("situation")),
        ("B — 背景 (Background)", handover.get("background")),
        ("A — 评估 (Assessment)", handover.get("assessment")),
        ("R — 建议 (Recommendation)", handover.get("recommendation")),
    ]
    for title, content in sections:
        story.append(Paragraph(title, s["h2"]))
        story.append(Paragraph(str(content or "—"), s["body"]))
        story.append(Spacer(1, 6))

    if handover.get("pending_tasks"):
        story.append(Paragraph("待办事项", s["h2"]))
        story.append(Paragraph(str(handover["pending_tasks"]), s["body"]))
        story.append(Spacer(1, 6))

    if handover.get("notes"):
        story.append(Paragraph("备注", s["h2"]))
        story.append(Paragraph(str(handover["notes"]), s["body"]))

    story.append(Spacer(1, 30))
    sign_table = Table([
        ["交班人签字：_______________", "接班人签字：_______________"],
    ], colWidths=[(A4[0] - 3.6 * cm) / 2, (A4[0] - 3.6 * cm) / 2])
    sign_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 24))
    story.append(Paragraph("— 本记录由智护银伴系统生成 —", s["footer"]))

    doc.build(story, onFirstPage=_draw_page_decoration, onLaterPages=_draw_page_decoration)
    return buf.getvalue()


# ============================================================
# 4. 护理记录单
# ============================================================

def generate_care_records_pdf(patient_name: str, patient_id: str, records: list[dict]) -> bytes:
    """生成护理记录单 PDF。"""
    s = _styles()
    buf = BytesIO()
    doc = _make_doc(buf)
    story = []
    font = _register_font()

    story.append(Paragraph("护理记录单", s["title"]))
    story.append(Paragraph(
        f"老人：{patient_name}（{patient_id}） &nbsp;|&nbsp; 记录数：{len(records)} 条 &nbsp;|&nbsp; 打印时间：{_now_str()}",
        s["small"]
    ))
    story.append(Spacer(1, 10))

    # 表格内容
    if not records:
        table_data = [["时间", "类型", "内容", "记录人", "班次"], ["—", "—", "暂无护理记录", "—", "—"]]
    else:
        table_data = [["时间", "类型", "内容", "记录人", "班次"]]
        for r in records:
            table_data.append([
                str(r.get("recorded_at", ""))[:16],
                str(r.get("record_type", "")),
                str(r.get("content", "")),
                str(r.get("recorded_by", "")),
                str(r.get("shift", "")),
            ])

    # 列宽：时间略宽，内容最宽
    col_widths = [3 * cm, 1.8 * cm, None, 1.8 * cm, 1.4 * cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 9),
        ("FONT", (0, 0), (-1, 0), font, 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
    ]))
    story.append(t)

    story.append(Spacer(1, 30))
    story.append(Paragraph("— 本记录由智护银伴系统生成 —", s["footer"]))

    doc.build(story, onFirstPage=_draw_page_decoration, onLaterPages=_draw_page_decoration)
    return buf.getvalue()


# ============================================================
# 辅助：金额转中文大写
# ============================================================

def _amount_to_chinese(amount: float) -> str:
    """将金额转为中文大写（财务专用，处理零、整、角分等所有边界情况）。"""
    if amount < 0:
        return "负" + _amount_to_chinese(-amount)

    units = ["", "拾", "佰", "仟", "万", "拾", "佰", "仟", "亿", "拾", "佰", "仟"]
    digits = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"]

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    jiao = decimal_part // 10
    fen = decimal_part % 10

    if integer_part == 0:
        result = ""
    else:
        s = str(integer_part)
        result = ""
        for i, c in enumerate(s):
            pos = len(s) - i - 1
            if int(c) == 0:
                if result and not result.endswith("零") and not result.endswith("万") and not result.endswith("亿"):
                    result += "零"
                # 万、亿位即使是零也要写单位
                if pos == 4 and "万" not in result:
                    result = result.rstrip("零") + "万"
                elif pos == 8 and "亿" not in result:
                    result = result.rstrip("零") + "亿"
            else:
                result += digits[int(c)] + units[pos]
        result = result.rstrip("零")

    # 整数部分有内容才加"元"
    if integer_part > 0:
        result += "元"
    if jiao > 0:
        result += digits[jiao] + "角"
    if fen > 0:
        result += digits[fen] + "分"
    # 边界：整数部分>0 且无角分 → 加"整"
    if jiao == 0 and fen == 0 and integer_part > 0:
        result += "整"
    # 全0金额
    if integer_part == 0 and jiao == 0 and fen == 0:
        result = "整"

    return result
