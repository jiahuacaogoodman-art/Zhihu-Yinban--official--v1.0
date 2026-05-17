# -*- coding: utf-8 -*-
"""
@File    : app/routers/export.py
@Desc    : PDF 导出路由（卫生局检查必备）

端点：
  GET /api/export/patient/{patient_id}/pdf       老人档案卡 PDF
  GET /api/export/billing/receipt/{record_id}/pdf 缴费收据 PDF
  GET /api/export/handover/{handover_id}/pdf     交接班记录单 PDF
  GET /api/export/care-records/{patient_id}/pdf  护理记录单 PDF（按日期范围）

修订 PR4 的关键问题：
  1) PR4 在 weasyprint 不可用时偷偷返回 HTML 但文件名仍是 .pdf —— 已删除。
     ReportLab 是纯 Python，永远返回真 PDF。
  2) PR4 直接拿 ChromaDB metadata（PII 字段是 Fernet 密文）渲染 —— 现在
     调 decrypt_pii_fields，加密未配置时占位符也由 pii_crypto 模块统一处理。
  3) PR4 把所有端点都用 PERM_EHR_READ —— 现在按资源拆：
       档案卡  → ehr.read
       收据    → ehr.read（含 PII 信息）
       交接班  → handover.read
       护理记录 → care_record.read
  4) PR4 没记审计 —— 含 PII 的 PDF 导出全部走 audit.log，便于事后追溯。
  5) PR4 用 f"profile_{patient_id}" 拼 doc_id —— 与 ehr.py 实际写入约定不符。
     改为用 nursing.get_patient_info 同款的 where 查询。
  6) PR4 中文文件名直接进 Content-Disposition —— 改为 RFC 5987 编码。
  7) PR4 在 router 里再用 list comp 过滤日期 —— 改为存储层 limit 之前过滤的
     做法（list_care_records 不支持日期，这里把 limit 放大、Python 侧排序后切片）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from loguru import logger

from app.middleware.auth import require_permission
from app.services.audit_log import get_audit_log
from app.services.billing_store import get_billing_store
from app.services.care_store import get_care_store
from app.services.pdf_generator import (
    generate_billing_receipt_pdf,
    generate_care_records_pdf,
    generate_handover_pdf,
    generate_patient_profile_pdf,
)
from app.services.permissions import (
    PERM_CARE_RECORD_READ,
    PERM_EHR_READ,
    PERM_HANDOVER_READ,
)
from app.services.pii_crypto import decrypt_pii_fields
from app.services.user_store import User

router = APIRouter()


# ============================================================
# Response 构造（真 PDF + 跨浏览器中文文件名）
# ============================================================

def _ascii_fallback(name: str) -> str:
    """把中文文件名退化为 ASCII fallback，给老浏览器用。"""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return safe or "document.pdf"


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    """
    构造 application/pdf 响应。

    Content-Disposition 同时带 ASCII fallback 与 RFC 5987 (UTF-8) 编码，
    现代浏览器走 filename*=UTF-8''xxx，老浏览器走 filename=ASCII。
    """
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        # 兜底防御：理论上不会进这里。如果生成器出问题，宁可 500 也不
        # 把无效字节当 PDF 回客户端。
        logger.error("PDF 生成失败：返回字节非 %PDF 开头")
        raise HTTPException(status_code=500, detail="PDF 生成失败")

    encoded = quote(filename, safe="")
    cd = (
        f'inline; filename="{_ascii_fallback(filename)}"; '
        f"filename*=UTF-8''{encoded}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": cd,
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ============================================================
# 内部工具：从 ChromaDB 取档案 + 解密
# ============================================================

def _fetch_patient_profile(patient_id: str) -> Optional[dict]:
    """
    按 nursing.get_patient_info 同款方式从 ChromaDB 取档案。

    返回已解密的 metadata（含 medical_history 字段，由 documents[i] 填入）。
    找不到返回 None。ChromaDB 不可用 → 返回 None，让上层走 admissions 降级。
    """
    try:
        import main as _main  # 延迟 import 避免循环依赖
        collection = (_main.app_state or {}).get("db_collection")
    except Exception:
        return None
    if collection is None:
        return None

    try:
        result = collection.get(
            where={"patient_id": {"$eq": patient_id}},
            include=["documents", "metadatas"],
        )
    except Exception as e:
        logger.warning(f"ChromaDB 查询失败，将走 admissions 降级: {e}")
        return None

    metadatas = result.get("metadatas") or []
    documents = result.get("documents") or []
    if not metadatas:
        return None

    # 找到 patient_profile（兼容旧数据 doc_type 为空）
    profile_idx = 0
    for i, m in enumerate(metadatas):
        if (m or {}).get("doc_type") in (None, "", "patient_profile"):
            profile_idx = i
            break

    meta = decrypt_pii_fields(metadatas[profile_idx] or {})
    meta = dict(meta)  # 避免修改原对象
    meta["patient_id"] = patient_id

    # medical_history 走 documents（明文，参与向量检索）
    if profile_idx < len(documents):
        meta.setdefault("medical_history", documents[profile_idx] or "")

    return meta


def _fallback_from_admission(patient_id: str) -> Optional[dict]:
    """ChromaDB 取不到时，从 admissions 表凑一份基本信息。"""
    care_store = get_care_store()
    for a in care_store.list_admissions(limit=1000):
        if a.get("patient_id") == patient_id:
            return {
                "patient_id": patient_id,
                "name": a.get("applicant_name"),
                "gender": a.get("applicant_gender"),
                "age": a.get("applicant_age"),
                "id_card": a.get("applicant_id_card"),
                "bed_number": a.get("bed_number"),
                "care_level": a.get("care_level_key"),
                "admission_date": a.get("actual_admission_date"),
                "emergency_contact": a.get("guardian_name"),
                "emergency_phone": a.get("guardian_phone"),
                "emergency_relation": a.get("guardian_relation"),
                "medical_history": a.get("health_summary"),
                "notes": a.get("notes"),
            }
    return None


# ============================================================
# 1. 老人档案卡 PDF
# ============================================================

@router.get(
    "/export/patient/{patient_id}/pdf",
    summary="导出老人档案卡 PDF",
)
async def export_patient_pdf(
    patient_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """
    导出指定老人的档案卡 PDF。
    优先从 ChromaDB 拉完整档案（PII 字段透明解密），失败则从 admissions 凑。
    """
    patient = _fetch_patient_profile(patient_id) or _fallback_from_admission(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="老人档案不存在")

    pdf_bytes = generate_patient_profile_pdf(patient)

    name = patient.get("name") or patient_id
    filename = f"档案卡_{name}_{patient_id}.pdf"

    # 审计：含 PII 的导出必须留痕
    get_audit_log().log(
        "PATIENT_READ", patient_id, user.username,
        detail=f"导出档案卡 PDF（来源=export, 字节={len(pdf_bytes)}）",
    )
    return _pdf_response(pdf_bytes, filename)


# ============================================================
# 2. 缴费收据 PDF
# ============================================================

@router.get(
    "/export/billing/receipt/{record_id}/pdf",
    summary="导出缴费收据 PDF",
)
async def export_billing_receipt_pdf(
    record_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """导出指定缴费记录的收据 PDF。"""
    billing_store = get_billing_store()
    record = billing_store.get_billing_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="缴费记录不存在")

    care_store = get_care_store()
    admission = care_store.get_admission(record.get("admission_id", ""))

    pdf_bytes = generate_billing_receipt_pdf(record, admission)

    receipt_no = record.get("receipt_number") or record_id
    filename = f"收据_{receipt_no}.pdf"

    get_audit_log().log(
        "PATIENT_READ",
        (admission or {}).get("patient_id", ""),
        user.username,
        doc_id=record_id,
        detail=f"导出缴费收据 PDF（admission_id={record.get('admission_id','')}）",
    )
    return _pdf_response(pdf_bytes, filename)


# 兼容 PR4 旧路径（无 /pdf 后缀）。返回相同 PDF。
@router.get(
    "/export/billing/receipt/{record_id}",
    summary="导出缴费收据 PDF（兼容旧路径）",
    include_in_schema=False,
)
async def export_billing_receipt_pdf_legacy(
    record_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    return await export_billing_receipt_pdf(record_id, user)  # type: ignore[arg-type]


# ============================================================
# 3. 交接班记录单 PDF
# ============================================================

@router.get(
    "/export/handover/{handover_id}/pdf",
    summary="导出交接班记录单 PDF",
)
async def export_handover_pdf(
    handover_id: str,
    user: User = Depends(require_permission(PERM_HANDOVER_READ)),
):
    """导出 SBAR 交接班记录 PDF。"""
    care_store = get_care_store()
    handover = care_store.get_handover(handover_id)
    if not handover:
        raise HTTPException(status_code=404, detail="交接班记录不存在")

    pdf_bytes = generate_handover_pdf(handover)
    filename = f"交接班_{handover_id}.pdf"

    get_audit_log().log(
        "PATIENT_READ",
        handover.get("patient_id", ""),
        user.username,
        doc_id=handover_id,
        detail="导出交接班记录 PDF",
    )
    return _pdf_response(pdf_bytes, filename)


# ============================================================
# 4. 护理记录单 PDF
# ============================================================

_DATE_FMT = "%Y-%m-%d"


def _validate_date(s: Optional[str], field: str) -> Optional[str]:
    if not s:
        return None
    try:
        datetime.strptime(s, _DATE_FMT)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"{field} 格式不合法，应为 YYYY-MM-DD",
        )
    return s


@router.get(
    "/export/care-records/{patient_id}/pdf",
    summary="导出护理记录单 PDF（按日期范围）",
)
async def export_care_records_pdf(
    patient_id: str,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(default=200, ge=1, le=1000, description="最多导出条数"),
    user: User = Depends(require_permission(PERM_CARE_RECORD_READ)),
):
    """
    导出指定老人的护理记录 PDF。

    日期范围基于 recorded_at 的日期前缀比较。为避免 PR4 那种"先 limit 再
    过滤导致丢数据"，这里先按 start_date/end_date 过滤再切 limit。
    """
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    care_store = get_care_store()

    # 拉一个较大的窗口再做日期过滤（list_care_records 暂不支持日期参数）。
    # 上限 5000 既给出合理性能边界，又能覆盖单个老人 1 年记录。
    raw = care_store.list_care_records(patient_id=patient_id, limit=5000)

    def _in_range(rec: dict) -> bool:
        ts = (rec.get("recorded_at") or "")[:10]
        if not ts:
            return False
        if start_date and ts < start_date:
            return False
        if end_date and ts > end_date:
            return False
        return True

    filtered = [r for r in raw if _in_range(r)]
    # list_care_records 已按时间倒序，截前 limit 即可
    records = filtered[:limit]

    # 取老人姓名：优先 records 里的（已是冗余字段），否则 admissions 兜底
    patient_name = ""
    for r in records:
        if r.get("patient_name"):
            patient_name = r["patient_name"]
            break
    if not patient_name:
        for a in care_store.list_admissions(limit=1000):
            if a.get("patient_id") == patient_id:
                patient_name = a.get("applicant_name") or ""
                break
    if not patient_name:
        patient_name = patient_id

    pdf_bytes = generate_care_records_pdf(patient_name, patient_id, records)
    filename = f"护理记录_{patient_name}_{patient_id}.pdf"

    get_audit_log().log(
        "PATIENT_READ", patient_id, user.username,
        detail=(
            f"导出护理记录 PDF（{len(records)} 条, "
            f"start={start_date or '-'}, end={end_date or '-'}, limit={limit}）"
        ),
    )
    return _pdf_response(pdf_bytes, filename)
