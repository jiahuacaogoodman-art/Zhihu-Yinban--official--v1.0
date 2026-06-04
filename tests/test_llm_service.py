# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services import llm_service as llm_module
from app.services.llm_service import OpenAICompatibleLLMService


class _FakeSSEContext:
    def __init__(self, lines: list[bytes]):
        self.lines = lines
        self.encoding = "ISO-8859-1"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode: bool = False):
        for line in self.lines:
            if decode_unicode:
                yield line.decode(self.encoding)
            else:
                yield line


def test_openai_stream_decodes_sse_as_utf8_when_charset_is_missing(monkeypatch):
    chinese_token = "请观察体温"
    raw_line = (
        'data: {"choices":[{"delta":{"content":"'
        + chinese_token
        + '"}}]}'
    ).encode("utf-8")
    fake_response = _FakeSSEContext([raw_line, b"data: [DONE]"])

    def fake_post(*args, **kwargs):
        return fake_response

    monkeypatch.setattr(llm_module.requests, "post", fake_post)

    service = OpenAICompatibleLLMService(
        api_base="http://example.test/v1",
        api_key="",
        model_name="test-model",
    )

    tokens = list(service.generate_stream("测试中文输出"))

    assert tokens == [chinese_token]