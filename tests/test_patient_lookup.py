# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import MagicMock


def test_find_patient_name_in_collection_decrypts_pii(monkeypatch):
    from app.services import pii_crypto
    from app.services.patient_lookup import find_patient_name_in_collection

    monkeypatch.setenv("PII_ENCRYPTION_KEY", "rsnsUTFhD0kHb2TLWGukQ3jV-lGGH0nODWIPGOUOkuA=")
    encrypted_name = pii_crypto.encrypt_pii_fields({"name": "张三"})["name"]
    assert encrypted_name.startswith("enc:")

    collection = MagicMock()
    collection.get.return_value = {
        "metadatas": [
            {
                "patient_id": "P001",
                "doc_type": "patient_profile",
                "name": encrypted_name,
            }
        ]
    }

    assert find_patient_name_in_collection(collection, "P001") == "张三"


def test_find_patient_name_in_collection_prefers_profile_doc(monkeypatch):
    from app.services import pii_crypto
    from app.services.patient_lookup import find_patient_name_in_collection

    monkeypatch.setenv("PII_ENCRYPTION_KEY", "rsnsUTFhD0kHb2TLWGukQ3jV-lGGH0nODWIPGOUOkuA=")
    encrypted_profile_name = pii_crypto.encrypt_pii_fields({"name": "李四"})["name"]

    collection = MagicMock()
    collection.get.return_value = {
        "metadatas": [
            {"patient_id": "P002", "doc_type": "medical_record_upload", "name": "旧附件名"},
            {"patient_id": "P002", "doc_type": "patient_profile", "name": encrypted_profile_name},
        ]
    }

    assert find_patient_name_in_collection(collection, "P002") == "李四"