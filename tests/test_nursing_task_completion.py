# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_complete_care_task_accepts_pending_status(monkeypatch):
    from app.models.schemas import TaskCompleteRequest
    from app.routers import nursing

    event = {
        "event_id": "evt_1",
        "reporter": "护工端",
        "immediate_tasks": [
            {
                "task_id": "t1",
                "text": "复测血压",
                "status": "done",
                "completed_at": "2026-06-10 12:00:00",
                "completed_by": "护工端",
                "note": "已完成",
                "value": "128/76",
                "audit_trail": [],
            }
        ],
        "execution_logs": [],
    }

    def fake_update_event(event_id: str, updater):
        assert event_id == "evt_1"
        return updater(event)

    monkeypatch.setattr(nursing, "_update_event", fake_update_event)

    res = await nursing.complete_care_task(
        "evt_1",
        "t1",
        TaskCompleteRequest(status="pending"),
    )

    task = res["event"]["immediate_tasks"][0]
    assert task["status"] == "pending"
    assert task["completed_at"] is None
    assert task["completed_by"] is None
    assert task["value"] is None