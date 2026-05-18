# -*- coding: utf-8 -*-
"""
@File    : tests/test_retrieval_async.py
@Desc    : Phase 1.2 - HybridRetriever.retrieve_async()

核心承诺:
  · async 入口在结果上等价于 sync 入口（不能因为多了一层 to_thread 就改变排序/打分）
  · async 入口在执行期间不阻塞 event loop（可以并发跑别的 async 任务）
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.retrieval import HybridRetriever, Evidence


# ── 假 Chroma collection（够用就行）──────────────────────────
def _fake_collection(docs: list[dict]):
    """
    docs: [{"id": "...", "doc": "...", "meta": {...}}, ...]
    返回的 mock 同时支持 .get(...) 和 .query(...)，符合 Chroma 0.5.x 接口形状。
    """
    ids = [d["id"] for d in docs]
    documents = [d["doc"] for d in docs]
    metadatas = [d["meta"] for d in docs]

    col = MagicMock()
    col.get = MagicMock(return_value={
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
    })
    # query 简化：按 id 顺序原样返回前 n_results 个
    def _query(query_embeddings, n_results, where, include):
        return {
            "ids": [ids[:n_results]],
            "metadatas": [metadatas[:n_results]],
        }
    col.query = MagicMock(side_effect=_query)
    return col


def _fake_embedding_function():
    ef = MagicMock()
    ef.encode = MagicMock(return_value=np.array([0.1, 0.2, 0.3]))
    return ef


# ── 1. 等价性：async 和 sync 输出一致 ───────────────────────
class TestAsyncEquivalence:
    @pytest.mark.asyncio
    async def test_async_matches_sync_output(self):
        docs = [
            {
                "id": "p1_profile",
                "doc": "患者张三 76 岁 糖尿病病史 长期服用二甲双胍",
                "meta": {"patient_id": "p1", "doc_type": "patient_profile"},
            },
            {
                "id": "p1_record_1",
                "doc": "2026-05-10 复查血糖 8.2 mmol/L 偏高",
                "meta": {"patient_id": "p1", "doc_type": "medical_record_upload",
                         "uploaded_at": "2026-05-10 09:00:00"},
            },
            {
                "id": "p1_decision_1",
                "doc": "建议监测血糖 调整饮食",
                "meta": {"patient_id": "p1", "doc_type": "decision_log",
                         "timestamp": "2026-05-15 14:00:00"},
            },
        ]
        col = _fake_collection(docs)
        ef = _fake_embedding_function()
        retriever = HybridRetriever(col, ef)

        sync_out = retriever.retrieve(patient_id="p1", query="糖尿病 血糖")
        async_out = await retriever.retrieve_async(patient_id="p1", query="糖尿病 血糖")

        assert len(sync_out) == len(async_out)
        for a, b in zip(sync_out, async_out):
            assert a.evidence_id == b.evidence_id
            assert a.doc_id == b.doc_id
            assert a.snippet == b.snippet
            assert a.score == b.score

    @pytest.mark.asyncio
    async def test_async_returns_empty_when_patient_missing(self):
        col = _fake_collection([])
        ef = _fake_embedding_function()
        retriever = HybridRetriever(col, ef)

        out = await retriever.retrieve_async(patient_id="ghost", query="anything")
        assert out == []


# ── 2. 不阻塞 event loop ────────────────────────────────────
class TestEventLoopNotBlocked:
    @pytest.mark.asyncio
    async def test_other_coroutines_can_progress_during_retrieve(self):
        """
        让 collection.get 故意 sleep 200ms。同期跑另一个 async 任务，
        如果 retrieve 阻塞了 event loop，另一个任务必须等到 retrieve
        完成才能跑完；用 to_thread 后两者总耗时应该 ≈ max 而不是 sum。
        """
        col = MagicMock()
        ef = _fake_embedding_function()

        def slow_get(**kw):
            time.sleep(0.2)
            return {"ids": [], "documents": [], "metadatas": []}

        col.get = MagicMock(side_effect=slow_get)
        retriever = HybridRetriever(col, ef)

        async def heartbeat():
            # 期望 retrieve 跑的 ~200 ms 期间这个任务能正常推进
            for _ in range(5):
                await asyncio.sleep(0.02)
            return "alive"

        t0 = time.perf_counter()
        retrieve_task = asyncio.create_task(
            retriever.retrieve_async(patient_id="x", query="q"),
        )
        heartbeat_task = asyncio.create_task(heartbeat())
        await retrieve_task
        result = await heartbeat_task
        elapsed = time.perf_counter() - t0

        assert result == "alive"
        # retrieve 是 200ms, heartbeat 是 100ms，并发跑总耗时应明显 < 300ms
        # 给 50ms 容差应付测试机抖动
        assert elapsed < 0.30, f"retrieve_async 似乎阻塞了 event loop（实际耗时 {elapsed:.3f}s）"
