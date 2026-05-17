# -*- coding: utf-8 -*-
"""
@File    : app/services/pdf_generator.py
@Desc    : PDF 文档生成服务 —— 基于 WeasyPrint 生成中文 PDF

支持文档类型：
  1. 老人档案卡
  2. 缴费收据
  3. 交接班记录单
  4. 护理记录单（按日期范围）
  5. 入住合同摘要

设计决策：
  - 使用 HTML → PDF 方案（WeasyPrint），方便控制样式
  - 内置中文字体支持（系统需要安装 Noto Sans CJK 或 WenQuanYi）
  - 统一页眉页脚（机构名称+打印时间+页码）
  - 所有生成的 PDF 不落盘，直接作为 Response 返回（不产生临时文件）
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Optional

from loguru import logger


# ============================================================
# 通用 HTML 模板基础
# ============================================================

_BASE_CSS = """
@page {
    size: A4;
    margin: 2cm 1.5cm;
    @top-center {
        content: "智护银伴 · 养老护理管理系统";
        font-size: 9pt;
        color: #666;
    }
    @bottom-right {
        content: "第 " counter(page) " 页";
        font-size: 9pt;
        color: #666;
    }
    @bottom-left {
        content: "打印时间：PRINT_TIME";
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: "Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
}
h1 { font-size: 18pt; text-align: center; margin-bottom: 12pt; font-weight: 600; }
h2 { font-size: 13pt; margin: 16pt 0 8pt; padding-bottom: 4pt; border-bottom: 1px solid #ddd; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0; }
th, td { padding: 6pt 8pt; border: 1px solid #ccc; font-size: 10pt; text-align: left; }
th { background: #f5f5f5; font-weight: 600; }
.header-info { text-align: center; margin-bottom: 16pt; color: #666; font-size: 10pt; }
.field-label { font-weight: 600; color: #333; min-width: 80pt; }
.field-value { color: #1a1a1a; }
.stamp-area { margin-top: 40pt; display: flex; justify-content: space-between; }
.stamp-box { width: 45%; }
.stamp-box p { margin: 12pt 0; font-size: 10pt; }
.amount-big { font-size: 16pt; font-weight: 700; color: #d32f2f; }
.seal-note { text-align: center; margin-top: 30pt; color: #999; font-size: 9pt; }
"""


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _render_pdf(html_content: str) -> bytes:
    """将 HTML 字符串渲染为 PDF 字节。
    
    优先使用 WeasyPrint（需系统安装 pango/cairo）。
    如果不可用，降级为返回 print-ready HTML（浏览器 Ctrl+P 打印效果一样好）。
    """
    css = _BASE_CSS.replace("PRINT_TIME", _now_str())
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{html_content}</body></html>"
    
    # 尝试 WeasyPrint
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=full_html).write_pdf()
        return pdf_bytes
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"WeasyPrint 生成失败，降级为 HTML: {e}")
    
    # 降级：返回 print-ready HTML（浏览器打印效果好）
    # 加上 print 优化的额外 CSS + 自动弹出打印对话框的脚本
    print_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>智护银伴 · 打印文档</title>
<style>
{css}
@media print {{
    body {{ margin: 0; }}
    .no-print {{ display: none !important; }}
}}
@media screen {{
    body {{ max-width: 210mm; margin: 20px auto; padding: 20px; background: #f5f5f5; }}
    .print-container {{ background: #fff; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    .no-print {{ position: fixed; top: 16px; right: 16px; z-index: 999; }}
    .no-print button {{ padding: 10px 20px; font-size: 14px; background: #0ea5a4; color: #fff;
        border: none; border-radius: 8px; cursor: pointer; }}
    .no-print button:hover {{ opacity: 0.9; }}
}}
</style>
</head><body>
<div class="no-print">
    <button onclick="window.print()">打印 / 导出PDF</button>
</div>
<div class="print-container">
{html_content}
</div>
</body></html>"""
    return print_html.encode("utf-8")


# ============================================================
# 1. 老人档案卡 PDF
# ============================================================

def generate_patient_profile_pdf(patient: dict) -> bytes:
    """生成老人档案卡 PDF。"""
    def field(label, value):
        v = value if value else "—"
        return f'<tr><td class="field-label">{label}</td><td class="field-value">{v}</td></tr>'

    html = f"""
    <h1>老人档案卡</h1>
    <div class="header-info">编号：{patient.get('patient_id', '')} | 打印时间：{_now_str()}</div>

    <h2>基本信息</h2>
    <table>
        {field('姓名', patient.get('name'))}
        {field('性别', patient.get('gender'))}
        {field('年龄', patient.get('age'))}
        {field('出生日期', patient.get('birth_date'))}
        {field('身份证号', patient.get('id_card'))}
        {field('床位号', patient.get('bed_number'))}
        {field('护理级别', patient.get('care_level'))}
        {field('入院日期', patient.get('admission_date'))}
        {field('主管护士', patient.get('primary_nurse'))}
    </table>

    <h2>健康信息</h2>
    <table>
        {field('血型', patient.get('blood_type'))}
        {field('身高(cm)', patient.get('height_cm'))}
        {field('体重(kg)', patient.get('weight_kg'))}
        {field('过敏史', patient.get('allergy'))}
        {field('饮食禁忌', patient.get('diet_restriction'))}
        {field('既往病史', patient.get('medical_history'))}
    </table>

    <h2>紧急联系人</h2>
    <table>
        {field('联系人', patient.get('emergency_contact'))}
        {field('联系电话', patient.get('emergency_phone'))}
        {field('与老人关系', patient.get('emergency_relation'))}
    </table>

    <h2>备注</h2>
    <p>{patient.get('notes') or '无'}</p>

    <div class="seal-note">— 本文档由智护银伴系统生成，仅供内部使用 —</div>
    """
    return _render_pdf(html)


# ============================================================
# 2. 缴费收据 PDF
# ============================================================

def generate_billing_receipt_pdf(record: dict, admission: dict = None) -> bytes:
    """生成缴费收据 PDF。"""
    patient_name = record.get('patient_name') or (admission.get('applicant_name') if admission else '') or '—'
    cat_map = {'bed': '床位费', 'care': '护理费', 'meal': '餐饮费', 'medical': '医疗费',
               'supplies': '耗材费', 'service': '增值服务', 'other': '其他'}
    method_map = {'cash': '现金', 'bank_transfer': '银行转账', 'wechat': '微信支付',
                  'alipay': '支付宝', 'pos': 'POS刷卡', 'other': '其他'}

    amount = record.get('amount', 0)
    amount_cn = _amount_to_chinese(amount)

    html = f"""
    <h1>缴费收据</h1>
    <div class="header-info">收据编号：{record.get('receipt_number') or record.get('record_id', '')} | 打印时间：{_now_str()}</div>

    <table>
        <tr><td class="field-label">老人姓名</td><td class="field-value">{patient_name}</td></tr>
        <tr><td class="field-label">入住编号</td><td class="field-value">{record.get('admission_id', '')}</td></tr>
        <tr><td class="field-label">费用类别</td><td class="field-value">{cat_map.get(record.get('fee_category'), record.get('fee_category', ''))}</td></tr>
        <tr><td class="field-label">缴费金额</td><td class="field-value"><span class="amount-big">¥ {amount:,.2f}</span></td></tr>
        <tr><td class="field-label">大写金额</td><td class="field-value">{amount_cn}</td></tr>
        <tr><td class="field-label">缴费周期</td><td class="field-value">{record.get('period_start', '')} 至 {record.get('period_end', '')}</td></tr>
        <tr><td class="field-label">支付方式</td><td class="field-value">{method_map.get(record.get('payment_method'), record.get('payment_method', ''))}</td></tr>
        <tr><td class="field-label">缴费人</td><td class="field-value">{record.get('payer') or '—'}</td></tr>
        <tr><td class="field-label">缴费时间</td><td class="field-value">{record.get('paid_at', '')}</td></tr>
        <tr><td class="field-label">备注</td><td class="field-value">{record.get('notes') or '—'}</td></tr>
    </table>

    <div class="stamp-area">
        <div class="stamp-box">
            <p>收款单位（盖章）：</p>
            <p style="margin-top:40pt">经办人：_____________</p>
        </div>
        <div class="stamp-box">
            <p>缴费人签字：</p>
            <p style="margin-top:40pt">日期：_____________</p>
        </div>
    </div>

    <div class="seal-note">— 本收据由智护银伴系统生成，加盖公章后有效 —</div>
    """
    return _render_pdf(html)


# ============================================================
# 3. 交接班记录单 PDF
# ============================================================

def generate_handover_pdf(handover: dict) -> bytes:
    """生成 SBAR 交接班记录单 PDF。"""
    html = f"""
    <h1>护理交接班记录单（SBAR）</h1>
    <div class="header-info">交接编号：{handover.get('handover_id', '')} | 创建时间：{handover.get('created_at', '')}</div>

    <table>
        <tr><td class="field-label">交班人</td><td class="field-value">{handover.get('shift_from', '')}</td></tr>
        <tr><td class="field-label">接班人</td><td class="field-value">{handover.get('shift_to', '')}</td></tr>
        <tr><td class="field-label">班次</td><td class="field-value">{handover.get('shift_type', '')}</td></tr>
        <tr><td class="field-label">老人</td><td class="field-value">{handover.get('patient_name', '')} ({handover.get('patient_id', '')})</td></tr>
        <tr><td class="field-label">确认状态</td><td class="field-value">{handover.get('status', '')}</td></tr>
    </table>

    <h2>S — 现状 (Situation)</h2>
    <p>{handover.get('situation', '—')}</p>

    <h2>B — 背景 (Background)</h2>
    <p>{handover.get('background', '—')}</p>

    <h2>A — 评估 (Assessment)</h2>
    <p>{handover.get('assessment', '—')}</p>

    <h2>R — 建议 (Recommendation)</h2>
    <p>{handover.get('recommendation', '—')}</p>

    <h2>待办事项</h2>
    <p>{handover.get('pending_tasks') or '无'}</p>

    <h2>备注</h2>
    <p>{handover.get('notes') or '无'}</p>

    <div class="stamp-area">
        <div class="stamp-box"><p>交班人签字：_____________</p></div>
        <div class="stamp-box"><p>接班人签字：_____________</p></div>
    </div>

    <div class="seal-note">— 本记录由智护银伴系统生成 —</div>
    """
    return _render_pdf(html)


# ============================================================
# 4. 护理记录单 PDF（按老人+日期范围）
# ============================================================

def generate_care_records_pdf(patient_name: str, patient_id: str, records: list[dict]) -> bytes:
    """生成护理记录单 PDF。"""
    if not records:
        rows = '<tr><td colspan="5" style="text-align:center;color:#999">暂无护理记录</td></tr>'
    else:
        rows = ""
        for r in records:
            rows += f"""<tr>
                <td>{r.get('recorded_at', '')[:16]}</td>
                <td>{r.get('record_type', '')}</td>
                <td>{r.get('content', '')}</td>
                <td>{r.get('recorded_by', '')}</td>
                <td>{r.get('shift', '')}</td>
            </tr>"""

    html = f"""
    <h1>护理记录单</h1>
    <div class="header-info">老人：{patient_name}（{patient_id}） | 记录数：{len(records)}条 | 打印时间：{_now_str()}</div>

    <table>
        <thead>
            <tr><th>时间</th><th>类型</th><th>内容</th><th>记录人</th><th>班次</th></tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <div class="seal-note">— 本记录由智护银伴系统生成 —</div>
    """
    return _render_pdf(html)


# ============================================================
# 辅助：金额转中文大写
# ============================================================

def _amount_to_chinese(amount: float) -> str:
    """将金额转为中文大写（简化版，够收据用）。"""
    units = ['', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿']
    digits = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    jiao = decimal_part // 10
    fen = decimal_part % 10

    if integer_part == 0:
        result = '零'
    else:
        s = str(integer_part)
        result = ''
        for i, c in enumerate(s):
            pos = len(s) - i - 1
            if int(c) == 0:
                if result and result[-1] != '零':
                    result += '零'
            else:
                result += digits[int(c)] + units[pos]
        result = result.rstrip('零')

    result += '元'
    if jiao > 0:
        result += digits[jiao] + '角'
    if fen > 0:
        result += digits[fen] + '分'
    elif jiao == 0:
        result += '整'

    return result
