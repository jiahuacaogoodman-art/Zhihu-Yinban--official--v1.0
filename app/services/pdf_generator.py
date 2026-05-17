# -*- coding: utf-8 -*-
"""
@File    : app/services/pdf_generator.py
@Desc    : PDF 文档生成服务 —— 基于 ReportLab 生成中文 PDF（真 PDF，非 HTML 降级）

支持文档类型：
  1. 老人档案卡       generate_patient_profile_pdf
  2. 缴费收据         generate_billing_receipt_pdf
  3. 交接班记录单     generate_handover_pdf
  4. 护理记录单       generate_care_records_pdf

设计决策（修订 PR4 的糊弄方案）：

  1. **真 PDF**：ReportLab 是纯 Python，无系统库依赖（不需要 pango / cairo /
     gdk-pixbuf / fontconfig）。任何 Python 3.10+ 容器都直接可用。

  2. **中文字体走内置 CIDFont**：使用 Adobe-GB1-0 字符集 + STSong-Light，
     PDF 阅读器（Acrobat / Chrome / 微信内置）都内嵌了对应字符映射，
     PDF 文件本身不需要嵌入字体文件，体积小、跨平台。
     之前 PR4 用 WeasyPrint 还要求系统装 Noto Sans CJK，运维拿不到 PDF。

  3. **统一 Platypus Flowable 流式排版**：自动分页、表格自动撑列宽、
     标题/正文样式统一管理。

  4. **完全字节流**：所有 PDF 不落盘、不产生临时文件，直接 BytesIO → bytes
     交给 FastAPI Response。

  5. **不再有 HTML 降级**：调用方拿到的一定是 application/pdf 字节，
     避免 PR4 那种"装不了 weasyprint 就偷偷给 HTML"的隐患。

注意：本模块**不做**任何 PII 解密；解密责任在 router 层，原因是
解密涉及到密钥配置探测、占位符策略，与渲染逻辑无关。
"""

from __future__ import annotations

import threading
from datetime import datetime
from io import BytesIO
from typing import Iterable, Optional, Sequence

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


# ============================================================
# 中文字体注册（线程安全，启动一次）
# ============================================================

# Adobe-GB1-0 简体中文 CIDFont。STSong-Light 是 Adobe 提供的标准 CJK 字体名，
# 阅读器自带映射；不需要系统装字体文件。
_CN_FONT_REGULAR = "STSong-Light"
# 黑体常用别名（GBK 黑体），ReportLab 也内置；做粗体标题用
_CN_FONT_BOLD = "STSongStd-Light"  # 同字体，只用作语义命名

_font_lock = threading.Lock()
_font_registered = False


def _ensure_fonts() -> None:
    """惰性注册中文 CIDFont。线程安全，只注册一次。"""
    global _font_registered
    if _font_registered:
        return
    with _font_lock:
        if _font_registered:
            return
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(_CN_FONT_REGULAR))
        except Exception as e:
            # 极端情况下 reportlab 字体资源损坏；记录但继续，
            # ReportLab 会降级到 Helvetica（中文显示为方框，但不会崩）
            logger.error(f"注册中文 CIDFont 失败: {e}")
        _font_registered = True


# ============================================================
# 通用样式 & 文档模板
# ============================================================

INSTITUTION_NAME = "智护银伴 · 养老护理管理系统"


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _styles() -> dict:
    """构造统一段落样式表。"""
    _ensure_fonts()
    base = getSampleStyleSheet()["Normal"]
    return {
        "title": ParagraphStyle(
            "ZhTitle", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=20, leading=26, alignment=1, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "ZhSubtitle", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=10, leading=14, alignment=1,
            textColor=colors.HexColor("#666666"), spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "ZhH2", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=13, leading=18, spaceBefore=10, spaceAfter=6,
            textColor=colors.HexColor("#0f172a"),
        ),
        "body": ParagraphStyle(
            "ZhBody", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=10.5, leading=16, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "ZhSmall", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=9, leading=12, textColor=colors.HexColor("#888888"),
            alignment=1,
        ),
        "amount_big": ParagraphStyle(
            "ZhAmount", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=16, leading=20, textColor=colors.HexColor("#b91c1c"),
        ),
        "cell": ParagraphStyle(
            "ZhCell", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=10, leading=14,
        ),
        "cell_label": ParagraphStyle(
            "ZhCellLabel", parent=base, fontName=_CN_FONT_REGULAR,
            fontSize=10, leading=14, textColor=colors.HexColor("#374151"),
        ),
    }


class _DocTemplate(BaseDocTemplate):
    """带页眉页脚（机构名 + 打印时间 + 页码）的 A4 文档。"""

    def __init__(self, buf: BytesIO, *, doc_title: str):
        super().__init__(
            buf,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
            title=doc_title,
            author=INSTITUTION_NAME,
        )
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id="main", showBoundary=0,
        )
        self.addPageTemplates([
            PageTemplate(id="default", frames=[frame], onPage=self._draw_chrome)
        ])
        self._print_time = _now_str()

    def _draw_chrome(self, canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFont(_CN_FONT_REGULAR, 9)
        canvas.setFillColor(colors.HexColor("#888888"))
        # 页眉：机构名居中
        canvas.drawCentredString(A4[0] / 2, A4[1] - 1.0 * cm, INSTITUTION_NAME)
        # 页脚左：打印时间；页脚右：页码
        canvas.drawString(1.5 * cm, 1.0 * cm, f"打印时间：{self._print_time}")
        canvas.drawRightString(
            A4[0] - 1.5 * cm, 1.0 * cm,
            f"第 {canvas.getPageNumber()} 页",
        )
        canvas.restoreState()


# ============================================================
# 表格构造工具
# ============================================================

def _kv_table(rows: Sequence[tuple[str, object]], styles: dict) -> Table:
    """两列键值表，左列标签、右列值。值用 Paragraph 包裹支持自动换行。"""
    data = []
    for label, value in rows:
        v = value if value not in (None, "") else "—"
        data.append([
            Paragraph(str(label), styles["cell_label"]),
            Paragraph(str(v), styles["cell"]),
        ])
    t = Table(data, colWidths=[3.2 * cm, None], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT_REGULAR),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _grid_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    col_widths: Sequence[Optional[float]],
    styles: dict,
) -> Table:
    """普通带表头的多列表格。"""
    cell_style = styles["cell"]
    header_style = ParagraphStyle(
        "ZhTH", parent=cell_style, textColor=colors.white,
    )
    data: list[list] = [[Paragraph(str(h), header_style) for h in headers]]
    for r in rows:
        data.append([Paragraph(_safe_str(c), cell_style) for c in r])
    t = Table(data, colWidths=list(col_widths), repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT_REGULAR),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _safe_str(v: object) -> str:
    """把任意值转字符串，None/空 → '—'。Paragraph 会自动 escape XML 特殊字符。"""
    if v is None:
        return "—"
    s = str(v)
    if s == "":
        return "—"
    # Paragraph 内部会处理 & < > 等转义；但 & 后跟分号的串会被它当成 entity，
    # 显式预转义最安全。
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _signature_block(styles: dict, left_label: str, right_label: str) -> Table:
    """收据/交接班用的双栏签字盖章区。"""
    cell = ParagraphStyle("ZhSign", parent=styles["body"], leading=22)
    data = [[
        Paragraph(left_label, cell),
        Paragraph(right_label, cell),
    ]]
    t = Table(data, colWidths=["50%", "50%"])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT_REGULAR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 24),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _build(
    flowables: list, *, doc_title: str
) -> bytes:
    """把 Flowable 列表渲染成 PDF 字节。"""
    buf = BytesIO()
    doc = _DocTemplate(buf, doc_title=doc_title)
    doc.build(flowables)
    return buf.getvalue()


# ============================================================
# 1. 老人档案卡 PDF
# ============================================================

def generate_patient_profile_pdf(patient: dict) -> bytes:
    """
    生成老人档案卡 PDF。

    入参 patient 字典约定字段（按业务实际可能缺失，会显示为 '—'）：
      patient_id / name / gender / age / birth_date / id_card
      bed_number / care_level / admission_date / primary_nurse
      blood_type / height_cm / weight_kg / allergy / diet_restriction
      medical_history / emergency_contact / emergency_phone /
      emergency_relation / notes
    """
    s = _styles()
    fls: list = []

    fls.append(Paragraph("老人档案卡", s["title"]))
    fls.append(Paragraph(
        f"编号：{_safe_str(patient.get('patient_id'))} &nbsp;|&nbsp; "
        f"打印时间：{_now_str()}",
        s["subtitle"],
    ))

    fls.append(Paragraph("基本信息", s["h2"]))
    fls.append(_kv_table([
        ("姓名", patient.get("name")),
        ("性别", patient.get("gender")),
        ("年龄", patient.get("age")),
        ("出生日期", patient.get("birth_date")),
        ("身份证号", patient.get("id_card")),
        ("床位号", patient.get("bed_number")),
        ("护理级别", patient.get("care_level")),
        ("入院日期", patient.get("admission_date")),
        ("主管护士", patient.get("primary_nurse")),
    ], s))

    fls.append(Paragraph("健康信息", s["h2"]))
    fls.append(_kv_table([
        ("血型", patient.get("blood_type")),
        ("身高(cm)", patient.get("height_cm")),
        ("体重(kg)", patient.get("weight_kg")),
        ("过敏史", patient.get("allergy")),
        ("饮食禁忌", patient.get("diet_restriction")),
        ("既往病史", patient.get("medical_history")),
    ], s))

    fls.append(Paragraph("紧急联系人", s["h2"]))
    fls.append(_kv_table([
        ("联系人", patient.get("emergency_contact")),
        ("联系电话", patient.get("emergency_phone")),
        ("与老人关系", patient.get("emergency_relation")),
    ], s))

    fls.append(Paragraph("备注", s["h2"]))
    fls.append(Paragraph(_safe_str(patient.get("notes") or "无"), s["body"]))

    fls.append(Spacer(1, 0.6 * cm))
    fls.append(Paragraph(
        "— 本文档由智护银伴系统生成，仅供内部使用 —", s["small"]
    ))
    return _build(fls, doc_title="老人档案卡")


# ============================================================
# 2. 缴费收据 PDF
# ============================================================

# 类别 / 支付方式中文映射（与 billing_schemas 保持一致）
_CAT_MAP = {
    "bed": "床位费", "care": "护理费", "meal": "餐饮费",
    "medical": "医疗费", "supplies": "耗材费",
    "service": "增值服务", "other": "其他",
}
_METHOD_MAP = {
    "cash": "现金", "bank_transfer": "银行转账",
    "wechat": "微信支付", "alipay": "支付宝",
    "pos": "POS刷卡", "other": "其他",
}


def generate_billing_receipt_pdf(record: dict, admission: Optional[dict] = None) -> bytes:
    """生成缴费收据 PDF。record 对应 billing_records 表行，admission 可选。"""
    s = _styles()
    fls: list = []

    patient_name = (
        record.get("patient_name")
        or (admission.get("applicant_name") if admission else "")
        or ""
    )
    amount = float(record.get("amount") or 0)
    amount_cn = amount_to_chinese(amount)
    receipt_no = record.get("receipt_number") or record.get("record_id", "")

    fls.append(Paragraph("缴费收据", s["title"]))
    fls.append(Paragraph(
        f"收据编号：{_safe_str(receipt_no)} &nbsp;|&nbsp; "
        f"打印时间：{_now_str()}",
        s["subtitle"],
    ))

    # 大金额单独高亮一行
    fls.append(Paragraph(
        f'<font color="#b91c1c">¥ {amount:,.2f}</font>',
        s["amount_big"],
    ))
    fls.append(Spacer(1, 0.2 * cm))

    fls.append(_kv_table([
        ("老人姓名", patient_name),
        ("入住编号", record.get("admission_id")),
        ("费用类别", _CAT_MAP.get(record.get("fee_category"), record.get("fee_category"))),
        ("收费项目", record.get("fee_standard_name")),
        ("缴费金额", f"¥ {amount:,.2f}"),
        ("大写金额", amount_cn),
        ("缴费周期", f"{record.get('period_start','')} 至 {record.get('period_end','')}"),
        ("支付方式", _METHOD_MAP.get(record.get("payment_method"), record.get("payment_method"))),
        ("缴费人", record.get("payer")),
        ("缴费时间", record.get("paid_at")),
        ("备注", record.get("notes")),
    ], s))

    fls.append(Spacer(1, 0.6 * cm))
    fls.append(_signature_block(
        s,
        "收款单位（盖章）：<br/><br/>经办人：______________",
        "缴费人签字：<br/><br/>日期：______________",
    ))

    fls.append(Spacer(1, 0.6 * cm))
    fls.append(Paragraph(
        "— 本收据由智护银伴系统生成，加盖公章后有效 —", s["small"]
    ))
    return _build(fls, doc_title="缴费收据")


# ============================================================
# 3. SBAR 交接班记录单 PDF
# ============================================================

def generate_handover_pdf(handover: dict) -> bytes:
    """生成 SBAR 格式交接班记录单 PDF。"""
    s = _styles()
    fls: list = []

    fls.append(Paragraph("护理交接班记录单（SBAR）", s["title"]))
    fls.append(Paragraph(
        f"交接编号：{_safe_str(handover.get('handover_id'))} &nbsp;|&nbsp; "
        f"创建时间：{_safe_str(handover.get('created_at'))}",
        s["subtitle"],
    ))

    fls.append(_kv_table([
        ("交班人", handover.get("shift_from")),
        ("接班人", handover.get("shift_to")),
        ("班次", handover.get("shift_type")),
        ("老人", f"{handover.get('patient_name','')} ({handover.get('patient_id','')})"),
        ("确认状态", handover.get("status")),
        ("确认时间", handover.get("acknowledged_at")),
    ], s))

    for heading, key in [
        ("S — 现状 (Situation)", "situation"),
        ("B — 背景 (Background)", "background"),
        ("A — 评估 (Assessment)", "assessment"),
        ("R — 建议 (Recommendation)", "recommendation"),
        ("待办事项", "pending_tasks"),
        ("备注", "notes"),
    ]:
        fls.append(Paragraph(heading, s["h2"]))
        fls.append(Paragraph(
            _safe_str(handover.get(key) or "无"), s["body"]
        ))

    fls.append(Spacer(1, 0.6 * cm))
    fls.append(_signature_block(
        s,
        "交班人签字：______________",
        "接班人签字：______________",
    ))

    fls.append(Spacer(1, 0.4 * cm))
    fls.append(Paragraph("— 本记录由智护银伴系统生成 —", s["small"]))
    return _build(fls, doc_title="交接班记录单")


# ============================================================
# 4. 护理记录单 PDF
# ============================================================

def generate_care_records_pdf(
    patient_name: str,
    patient_id: str,
    records: Iterable[dict],
) -> bytes:
    """
    生成护理记录单 PDF。

    records 应为 care_records 表行的迭代器；按 recorded_at 倒序由调用方决定。
    """
    s = _styles()
    fls: list = []

    rec_list = list(records)

    fls.append(Paragraph("护理记录单", s["title"]))
    fls.append(Paragraph(
        f"老人：{_safe_str(patient_name)}（{_safe_str(patient_id)}） "
        f"&nbsp;|&nbsp; 记录数：{len(rec_list)} 条 &nbsp;|&nbsp; "
        f"打印时间：{_now_str()}",
        s["subtitle"],
    ))

    headers = ["时间", "类型", "内容", "记录人", "班次"]
    if rec_list:
        rows = []
        for r in rec_list:
            ts = (r.get("recorded_at") or "")[:16]
            rows.append([
                ts,
                r.get("record_type") or "",
                r.get("content") or "",
                r.get("recorded_by") or "",
                r.get("shift") or "",
            ])
        # 列宽（None 让 reportlab 自适应；这里 content 占主要空间）
        col_widths = [3.2 * cm, 2.0 * cm, None, 2.0 * cm, 1.6 * cm]
        fls.append(_grid_table(headers, rows, col_widths, s))
    else:
        fls.append(Paragraph("（暂无护理记录）", s["body"]))

    fls.append(Spacer(1, 0.4 * cm))
    fls.append(Paragraph("— 本记录由智护银伴系统生成 —", s["small"]))
    return _build(fls, doc_title="护理记录单")


# ============================================================
# 辅助：金额转中文大写（修复 PR4 的 bug）
# ============================================================

# PR4 原版的 bug：
#   1. units 索引到 "亿" 就停（pos>=9 越界 IndexError）
#   2. "壹拾万整" 被错写成 "壹拾整"（rstrip 把"万"当零去掉）
#   3. 跨节零省略不正确，比如 "壹拾万零伍拾" 会出 "壹拾万伍拾"
# 这里按"分节处理 + 节内零归并"重写，覆盖单元测试见
# tests/test_amount_to_chinese.py


_DIGITS = "零壹贰叁肆伍陆柒捌玖"
_UNITS_INSIDE = ["", "拾", "佰", "仟"]
# 节单位：每 4 位一节。中国央行/财务规范用 "万亿" 而非 "兆"（避免与日韩"兆"=10^12 与中文古意冲突）。
# 覆盖到 万亿 (10^12)，已足够任何养老机构收据需求。
_UNITS_SECTION = ["", "万", "亿", "万亿"]


def _section_to_chinese(section: int) -> str:
    """把 0~9999 的整数转为节内中文，带零归并：1005 -> 壹仟零伍。

    规则：
      · 零归并：连续多个 0 只输出一个 "零"
      · 节首前导 0 不输出（"壹元" 不写成 "零零零壹元"）
      · 末尾 0 不输出（"壹拾" 不写成 "壹拾零"）
    """
    if section == 0:
        return ""
    s = str(section)
    pad = "0" * (4 - len(s)) + s  # 左补 0 到 4 位
    out: list[str] = []
    zero_pending = False
    for i, ch in enumerate(pad):
        unit = _UNITS_INSIDE[3 - i]
        if ch == "0":
            # 只有在已经有非零输出后，才标记需要补 "零"
            if out:
                zero_pending = True
        else:
            if zero_pending:
                out.append(_DIGITS[0])  # 零
                zero_pending = False
            out.append(_DIGITS[int(ch)] + unit)
    return "".join(out)


def amount_to_chinese(amount: float) -> str:
    """
    把金额（人民币元）转中文大写。
    覆盖 0 ~ 兆 范围；负数加"负"前缀；分位四舍五入（ROUND_HALF_UP）。

    示例：
      0       -> 零元整
      1.05    -> 壹元零伍分
      1.5     -> 壹元伍角
      1234.56 -> 壹仟贰佰叁拾肆元伍角陆分
      100000  -> 壹拾万元整
      100050  -> 壹拾万零伍拾元整
      10001   -> 壹万零壹元整
    """
    from decimal import Decimal, ROUND_HALF_UP

    sign = ""
    if amount < 0:
        sign = "负"
        amount = -amount

    # 用 Decimal + ROUND_HALF_UP，避免 float banker rounding
    # （round(0.005*100)==0 而非 1）。
    cents = int((Decimal(str(amount)) * 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ))
    yuan = cents // 100
    decimals = cents % 100
    jiao = decimals // 10
    fen = decimals % 10

    # 整数部分按 4 位一节切（万、亿、万亿）
    if yuan == 0:
        integer_str = "" if (jiao or fen) else "零"
    else:
        sections: list[tuple[int, int]] = []  # (section_value, section_index)
        idx = 0
        n = yuan
        while n > 0:
            sections.append((n % 10000, idx))
            n //= 10000
            idx += 1
        # 从高位到低位拼接，跨节零规则：
        #   1) 高节存在但本节为 0：跳过本节单位，下一非零节前补"零"
        #   2) 本节非零但千位为 0（即 sec_val < 1000）：前面也要补"零"
        #      （前提：已经有非零节输出过）
        parts: list[str] = []
        any_emitted = False
        zero_gap = False
        for sec_val, sec_idx in reversed(sections):
            if sec_val == 0:
                if any_emitted:
                    zero_gap = True
                continue
            if any_emitted and (zero_gap or sec_val < 1000):
                parts.append(_DIGITS[0])  # 零
            parts.append(_section_to_chinese(sec_val) + _UNITS_SECTION[sec_idx])
            any_emitted = True
            zero_gap = False
        integer_str = "".join(parts)

    # 拼接元/角/分
    has_yuan = yuan > 0 or (jiao == 0 and fen == 0)
    if has_yuan:
        result = sign + integer_str + "元"
    else:
        # 0.x 的情况：不输出 "零元"，直接出 角/分
        result = sign

    if jiao == 0 and fen == 0:
        result += "整"
    else:
        if jiao > 0:
            result += _DIGITS[jiao] + "角"
        elif yuan > 0:
            # 元后面没角但有分时，按规范要补 "零"
            if fen > 0:
                result += _DIGITS[0]
        if fen > 0:
            result += _DIGITS[fen] + "分"

    return result


# 兼容旧调用（PR4 原版函数名带下划线前缀）
_amount_to_chinese = amount_to_chinese


__all__ = [
    "generate_patient_profile_pdf",
    "generate_billing_receipt_pdf",
    "generate_handover_pdf",
    "generate_care_records_pdf",
    "amount_to_chinese",
]
