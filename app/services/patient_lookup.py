# -*- coding: utf-8 -*-
"""
@File    : app/services/patient_lookup.py
@Desc    : 从 EHR 向量库查询患者基础信息的小工具
"""

from __future__ import annotations

from typing import Any

from app.services.pii_crypto import decrypt_pii_fields

_PROFILE_DOC_TYPES = (None, "", "patient_profile")


def _plain_meta(meta: Any) -> dict:
    if not isinstance(meta, dict):
        return {}
    return decrypt_pii_fields(meta)


def find_patient_name_in_collection(collection: Any, patient_id: str) -> str:
    """从 Chroma collection 里查患者姓名，并透明解密 PII metadata。"""
    if not collection or not patient_id:
        return ""
    try:
        result = collection.get(
            where={"patient_id": {"$eq": patient_id}},
            include=["metadatas"],
        )
    except Exception:
        return ""

    metadatas = result.get("metadatas", []) or []
    for raw_meta in metadatas:
        meta = _plain_meta(raw_meta)
        if meta.get("doc_type") in _PROFILE_DOC_TYPES and meta.get("name"):
            return str(meta["name"])
    for raw_meta in metadatas:
        meta = _plain_meta(raw_meta)
        if meta.get("name"):
            return str(meta["name"])
    return ""


def find_patient_name(patient_id: str) -> str:
    """从 main.app_state 的 db_collection 查询患者姓名。"""
    try:
        from main import app_state

        collection = app_state.get("db_collection")
    except Exception:
        collection = None
    return find_patient_name_in_collection(collection, patient_id)