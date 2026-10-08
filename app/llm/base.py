"""LLM 兜底客户端的统一接口与工厂。"""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def repair(self, raw_text: str, schema: dict | None) -> str:
        """把规则无法修复的脏输出交给 LLM，要求其只返回修复后的 JSON 文本。"""
        ...


def build_llm_client(settings) -> object | None:
    """按环境变量构造客户端；任一必要配置缺失则返回 None（离线模式）。"""
    if not (settings.llm_base_url and settings.llm_api_key and settings.llm_model):
        return None
    from app.llm.openai_adapter import OpenAICompatibleClient

    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )
