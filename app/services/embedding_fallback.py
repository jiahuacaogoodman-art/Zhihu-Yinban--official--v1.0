# -*- coding: utf-8 -*-
"""
@File    : services/embedding_fallback.py
@Desc    : Embedding 兜底实现 —— 用于 EMBEDDING_DISABLED=true 的 API-only 部署

设计目标：
    在不引入 torch / transformers / sentence-transformers 的前提下，
    提供一个能被 ChromaDB 接受的 embedding_function，让索引、写入、
    按 metadata 过滤的查询都能正常工作。

什么场景用：
    - 受限网络下不能下载模型权重
    - 服务器不装 GPU 也不想装 ~5GB 的 PyTorch
    - 部署文档里建议用 requirements-api.txt 的"轻量 API-only"模式

什么场景不能用：
    - 任何依赖语义召回的检索（HybridRetriever 的语义分数会失效）
    - 真正的 RAG 端点（/api/nursing/decision 召回质量会变差）
    患者档案按 patient_id 过滤检索仍然正常 —— 这是 v17/v18 前端的主路径。

实现要点：
    - 用 SHA-256 把文本切成定长 64 维浮点向量，结果完全确定（同输入永远同输出）
    - 不引任何外部依赖（标准库 hashlib 即可）
    - 同时实现 sentence-transformers 的 .encode() 协议，让 HybridRetriever 直接复用
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable, List, Sequence


_VECTOR_DIM = 64  # 64 维足够 ChromaDB 建索引；维度越大，CPU 开销越高


def _hash_to_vector(text: str, dim: int = _VECTOR_DIM) -> List[float]:
    """把字符串映射到一个 dim 维 [-1, 1] 浮点向量。"""
    if text is None:
        text = ""
    # 用多次哈希滚动产生足够字节
    out: List[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(f"{counter}|{text}".encode("utf-8")).digest()
        for b in h:
            # b 是 0..255，归一化到 [-1, 1]
            out.append((b / 127.5) - 1.0)
            if len(out) >= dim:
                break
        counter += 1
    # L2 归一化，避免 ChromaDB cosine 距离爆炸
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


class HashEmbeddingFunction:
    """
    可以被 ChromaDB / HybridRetriever 复用的兜底 embedding 函数。

    暴露两组接口：
      1. ChromaDB embedding_function 协议：``__call__(input: List[str]) -> List[List[float]]``
         （Chroma 0.5+）/ ``embed_documents``（Chroma 0.4-）。两者都实现以兼容多版本。
      2. sentence-transformers 协议：``encode(sentences, ...) -> List[List[float]]``
         项目里 HybridRetriever / DecisionMemory 直接调 ``embedding_function.encode(...)``，
         必须实现这个方法才能无侵入替换 SentenceTransformer。
    """

    def __init__(self, dim: int = _VECTOR_DIM):
        self._dim = dim

    # ── ChromaDB 协议 ────────────────────────────────────────
    def __call__(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002 - chroma 用了保留字
        return [_hash_to_vector(t, self._dim) for t in (input or [])]

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return self(texts)

    def embed_query(self, text: str) -> List[float]:
        return _hash_to_vector(text, self._dim)

    # ── sentence-transformers 协议 ───────────────────────────
    def encode(
        self,
        sentences,
        batch_size: int = 32,            # noqa: ARG002 - 兼容签名
        show_progress_bar: bool = False, # noqa: ARG002
        convert_to_numpy: bool = True,   # noqa: ARG002
        normalize_embeddings: bool = True,  # noqa: ARG002 - 我们已默认 L2
        **kwargs,                        # noqa: ARG002
    ):
        """
        接受单条字符串或字符串列表，返回与 sentence-transformers 相同形状的结果：
          - 输入 str → 单条 List[float]
          - 输入 list[str] → List[List[float]]
        故意返回 list 而非 numpy.ndarray，避免硬依赖 numpy。
        HybridRetriever 调用时只用 list-like 索引，没有 numpy 专属操作。
        """
        if isinstance(sentences, str):
            return _hash_to_vector(sentences, self._dim)
        if isinstance(sentences, Iterable):
            return [_hash_to_vector(t, self._dim) for t in sentences]
        raise TypeError(f"Unsupported sentences type: {type(sentences)}")

    # 让 ``str(embedding_function)`` 看到的是有意义的标识
    def __repr__(self) -> str:  # pragma: no cover - 仅日志友好
        return f"<HashEmbeddingFunction dim={self._dim}>"
