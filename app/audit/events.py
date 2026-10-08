"""审计事件模型：记录每一次清洗/修复动作的完整上下文。"""
from __future__ import annotations

import itertools
from typing import Any, Literal

from pydantic import BaseModel, Field

Stage = Literal["syntax_clean", "structure_repair", "semantic_validate"]
Method = Literal["rule", "llm"]

_event_counter = itertools.count(1)


class AuditEvent(BaseModel):
    """单条不可变审计事件。

    - path 为空表示作用于整个文档的全局动作（如剥离围栏、截断修复）；
    - before/after 保留修改前值与修改后值，保证可解释；
    - method 区分确定性规则与 LLM 兜底。
    """

    event_id: str = Field(default_factory=lambda: f"evt_{next(_event_counter):04d}")
    stage: Stage
    action: str
    path: str = ""
    before: Any = None
    after: Any = None
    reason: str = ""
    method: Method = "rule"
    confidence_delta: float = 0.0
    category: str = ""
