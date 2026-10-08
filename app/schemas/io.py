"""API 请求 / 响应的 Pydantic 模型，同时 Policy 被流水线内部复用。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.audit.events import AuditEvent

Status = Literal["valid", "repaired", "invalid"]


class PolicyInput(BaseModel):
    model_config = {"extra": "forbid"}

    strictness: Literal["strict", "lenient"] = "lenient"
    # 未知字段处理
    unknown_fields: Literal["drop", "keep", "error"] = "drop"
    # null 处理
    null_policy: Literal["keep", "default", "error"] = "default"
    # 字段重命名（支持完整点路径或字段名）
    rename_map: dict[str, str] = Field(default_factory=dict)
    # 默认值补全（支持 {"user.name": "..."} 扁平写法或嵌套 dict）
    defaults: dict[str, Any] = Field(default_factory=dict)
    # 枚举别名：{字段路径: {别名: 标准值}}
    enum_aliases: dict[str, dict[str, str]] = Field(default_factory=dict)
    # 规则修复失败后是否允许 LLM 兜底
    llm_fallback: bool = False
    # 枚举模糊匹配阈值
    fuzzy_enum_threshold: float = 0.85
    # 是否落库溯源
    persist: bool = True


class CleanRequest(BaseModel):
    raw_text: str
    schema: dict[str, Any] | None = None
    policy: PolicyInput | None = None


class ValidateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: Any
    # 避开 BaseModel.schema 属性名，API 上仍以 "schema" 传入
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    policy: PolicyInput | None = None


class BatchCleanRequest(BaseModel):
    items: list[CleanRequest]


class Violation(BaseModel):
    severity: Literal["error", "warning"] = "error"
    path: str
    keyword: str
    message: str
    expected: Any = None
    actual: Any = None


class ConfidenceReport(BaseModel):
    score: float
    field_scores: dict[str, float] = Field(default_factory=dict)
    llm_capped: bool = False


class CleanResponse(BaseModel):
    status: Status
    result: Any = None
    confidence: ConfidenceReport
    violations: list[Violation] = Field(default_factory=list)
    audit_trail: list[AuditEvent] = Field(default_factory=list)
    diff: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str
    raw_input: str
    error: str | None = None
