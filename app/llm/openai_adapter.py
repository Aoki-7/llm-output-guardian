"""OpenAI 兼容 Chat Completions 协议的兜底客户端（同步 httpx）。"""
from __future__ import annotations

import json

import httpx

_SYSTEM_PROMPT = (
    "你是一个严格的JSON修复引擎。用户会给出一段来自大模型的脏输出，"
    "可能包含Markdown围栏、思考废话、单引号、尾逗号、截断、字段缺失等问题。"
    "请将其修复为合法、可被json.loads直接解析的JSON。要求：\n"
    "1. 只输出JSON本身，不要任何解释、前后缀或代码围栏；\n"
    "2. 尽量保留原有字段与数据，不允许臆造业务字段；\n"
    "3. 缺失的结构按JSON语法补全。"
)


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def repair(self, raw_text: str, schema: dict | None) -> str:
        user_content = raw_text
        if schema:
            user_content = f"目标Schema：{json.dumps(schema, ensure_ascii=False)}\n\n待修复输出：\n{raw_text}"

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
