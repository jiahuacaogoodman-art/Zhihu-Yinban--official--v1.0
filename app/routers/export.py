# -*- coding: utf-8 -*-
"""
@File    : app/routers/export.py
@Desc    : PDF 导出/打印路由

端点：
  GET /api/export/patient/{patient_id}/pdf       老人档案卡 PDF
  GET /api/export/billing/receipt/{record_id}    缴费收据 PDF
  GET /api/export/handover/{handover_id}/pdf     交接班记录单 PDF
  GET /api/export/care-records/{patient_id}/pdf  护理记录单 PDF（支持日期范围）

所有端点返回 application/pdf，浏览器直接下载或预览打印。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.middleware.auth import require_permission
from app.services.billing_store import get_billing_store
from app.services.care_store import get_care_store
from app.services.pdf_generator import (
    generate_patient_profile_pdf,
    generate_billing_receipt_pdf,
    generate_handover_pdf,
    generate_care_records_pdf,
)
from app.services.permissions import PERM_EHR_READ
from app.services.user_store import User

router = APIRouter()


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    """构建 PDF 或 print-ready HTML 下载响应。"""
    # 如果生成的是真 PDF（以 %PDF 开头）
    if pdf_bytes[:4] == b'%PDF':
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
    # 降级为 print-ready HTML 页面（浏览器直接打印）
    return Response(
        content=pdf_bytes,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/export/patient/{patient_id}/pdf", summary="导出老人档案卡PDF")
async def export_patient_pdf(
    patient_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """导出指定老人的档案卡为 PDF，可直接打印。"""
    # 从 ChromaDB 获取档案
    try:
        import main as _main
        collection = _main.app_state.get("db_collection")
        if collection:
            result = collection.get(ids=[f"profile_{patient_id}"])
            if result and result.get("metadatas"):
                patient = result["metadatas"][0]
                patient["patient_id"] = patient_id
            else:
                raise HTTPException(status_code=404, detail="老人档案不存在")
        else:
            raise HTTPException(status_code=503, detail="数据库不可用")
    except HTTPException:
        raise
    except Exception:
        # 降级：尝试从 admissions 获取基本信息
        care_store = get_care_store()
        admissions = care_store.list_admissions()
        patient = None
        for a in admissions:
            if a.get("patient_id") == patient_id:
                patient = {
                    "patient_id": patient_id,
                    "name": a.get("applicant_name"),
                    "gender": a.get("applicant_gender"),
                    "age": a.get("applicant_age"),
                    "bed_number": a.get("bed_number"),
                    "care_level": a.get("care_level_key"),
                    "admission_date": a.get("actual_admission_date"),
                }
                break
        if not patient:
            raise HTTPException(status_code=404, detail="老人档案不存在")

    pdf_bytes = generate_patient_profile_pdf(patient)
    name = patient.get("name", patient_id)
    return _pdf_response(pdf_bytes, f"档案卡_{name}_{patient_id}.pdf")


@router.get("/export/billing/receipt/{record_id}", summary="导出缴费收据PDF")
async def export_billing_receipt_pdf(
    record_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """导出指定缴费记录的收据为 PDF，可直接打印交给家属。"""
    billing_store = get_billing_store()
    record = billing_store.get_billing_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="缴费记录不存在")

    # 尝试获取入住信息
    care_store = get_care_store()
    admission = care_store.get_admission(record.get("admission_id", ""))

    pdf_bytes = generate_billing_receipt_pdf(record, admission)
    return _pdf_response(pdf_bytes, f"收据_{record_id}.pdf")


@router.get("/export/handover/{handover_id}/pdf", summary="导出交接班记录单PDF")
async def export_handover_pdf(
    handover_id: str,
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """导出指定交接班记录为 SBAR 格式 PDF。"""
    care_store = get_care_store()
    handover = care_store.get_handover(handover_id)
    if not handover:
        raise HTTPException(status_code=404, detail="交接班记录不存在")

    pdf_bytes = generate_handover_pdf(handover)
    return _pdf_response(pdf_bytes, f"交接班_{handover_id}.pdf")


@router.get("/export/care-records/{patient_id}/pdf", summary="导出护理记录单PDF")
async def export_care_records_pdf(
    patient_id: str,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(default=200, le=500),
    user: User = Depends(require_permission(PERM_EHR_READ)),
):
    """
    导出指定老人的护理记录为 PDF。
    支持按日期范围筛选。不传日期则导出最近200条。
    """
    care_store = get_care_store()
    records = care_store.list_care_records(patient_id=patient_id, limit=limit)

    # 按日期范围过滤
    if start_date:
        records = [r for r in records if r.get("recorded_at", "") >= start_date]
    if end_date:
        records = [r for r in records if r.get("recorded_at", "")[:10] <= end_date]

    # 获取老人姓名
    patient_name = patient_id
    # 尝试从 admissions 找
    admissions = care_store.list_admissions()
    for a in admissions:
        if a.get("patient_id") == patient_id:
            patient_name = a.get("applicant_name", patient_id)
            break

    pdf_bytes = generate_care_records_pdf(patient_name, patient_id, records)
    return _pdf_response(pdf_bytes, f"护理记录_{patient_name}_{patient_id}.pdf")
