"""LLM 兜底路径测试（用 fake client 离线验证）。"""
from __future__ import annotations

from app.core.pipeline import GuardianPipeline
from app.schemas.io import PolicyInput


class FakeLLMClient:
    def repair(self, raw_text: str, schema) -> str:
        return '{"a": 1}'


class FailingLLMClient:
    def repair(self, raw_text: str, schema) -> str:
        raise RuntimeError("connection refused")


def test_llm_fallback_repair():
    pipeline = GuardianPipeline(store=None, llm_client=FakeLLMClient())
    policy = PolicyInput(llm_fallback=True)
    body = pipeline.clean("完全无法解析的一堆乱码", {"a": "integer"}, policy)
    assert body["status"] == "repaired"
    assert body["result"] == {"a": 1}
    assert body["confidence"]["llm_capped"] is True
    assert body["confidence"]["score"] <= 0.6
    llm_events = [e for e in body["audit_trail"] if e["method"] == "llm"]
    assert len(llm_events) == 1
    assert llm_events[0]["action"] == "llm_repair"


def test_llm_fallback_requested_but_unconfigured():
    pipeline = GuardianPipeline(store=None, llm_client=None)
    policy = PolicyInput(llm_fallback=True)
    body = pipeline.clean("无法解析", {"a": "integer"}, policy)
    assert body["status"] == "invalid"
    assert any(e["action"] == "llm_unavailable" for e in body["audit_trail"])


def test_llm_call_failure_recorded():
    pipeline = GuardianPipeline(store=None, llm_client=FailingLLMClient())
    policy = PolicyInput(llm_fallback=True)
    body = pipeline.clean("无法解析", {"a": "integer"}, policy)
    assert body["status"] == "invalid"
    event = next(e for e in body["audit_trail"] if e["action"] == "llm_unavailable")
    assert "connection refused" in event["reason"]
