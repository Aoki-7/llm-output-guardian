"""阶段②：结构修复。

解析顺序：严格 json.loads → 宽容文本修复 → 截断修复 → （可选）LLM 兜底。
解析成功后，按 schema 依次执行字段级修复规则。
"""
from __future__ import annotations

import json
from copy import deepcopy
from json import JSONDecodeError
from typing import Any

from app.audit.center import AuditCenter
from app.rules import (
    array_object,
    enum_fix,
    field_ops,
    lenient_parser,
    null_handling,
    truncation_repair,
    type_coercion,
)


class StructureRepairer:
    def __init__(self, center: AuditCenter, llm_client: object | None = None) -> None:
        self.center = center
        self.llm_client = llm_client

    def _parse(self, text: str, record_events: bool = True) -> Any:
        """按三级策略解析文本；record_events 控制是否登记解析类审计事件。"""
        # 1) 宽容解析
        repaired, actions = lenient_parser.repair_text(text)
        if record_events:
            for action, before_snip, after_snip in actions:
                self.center.record(
                    "structure_repair",
                    action,
                    before=before_snip,
                    after=after_snip,
                    reason="宽容解析文本修复",
                )
        try:
            return json.loads(repaired)
        except JSONDecodeError:
            pass

        # 2) 截断修复
        result = truncation_repair.repair(repaired)
        if result is not None:
            value, final_text = result
            if record_events:
                self.center.record(
                    "structure_repair",
                    "truncation_repair",
                    before=text[:200],
                    after=final_text[:200],
                    reason="栈式闭合修复截断JSON",
                )
            return value
        return None

    def repair(self, text: str, schema: dict | None, policy) -> tuple[Any, Any]:
        """返回 (修复后值, 字段级规则执行前的初始快照)；失败时值为 None。"""
        try:
            value: Any = json.loads(text)
        except JSONDecodeError:
            value = self._parse(text)

        # LLM 兜底：规则链路彻底无法解析时
        if value is None and policy.llm_fallback:
            value = self._llm_fallback(text, schema, policy)

        if value is None:
            return None, None

        initial = deepcopy(value)

        if schema:
            value = field_ops.apply(value, schema, policy, self.center)
            value = null_handling.apply(value, schema, policy, self.center)
            value = array_object.apply(value, schema, policy, self.center)
            value = type_coercion.apply(value, schema, policy, self.center)
            value = enum_fix.apply(value, schema, policy, self.center)

        return value, initial

    def _llm_fallback(self, text: str, schema: dict | None, policy) -> Any:
        if self.llm_client is None:
            self.center.record(
                "structure_repair",
                "llm_unavailable",
                before=text[:120],
                reason="策略要求LLM兜底，但服务未配置LLM连接",
            )
            return None
        try:
            llm_output = self.llm_client.repair(text, schema)
        except Exception as exc:  # 网络/鉴权/超时等
            self.center.record(
                "structure_repair",
                "llm_unavailable",
                before=text[:120],
                reason=f"LLM兜底调用失败: {exc}",
            )
            return None

        value = self._parse(llm_output, record_events=False)
        if value is not None:
            self.center.record(
                "structure_repair",
                "llm_repair",
                before=text[:200],
                after=llm_output[:200],
                reason="规则无法修复，LLM兜底修复成功",
                method="llm",
            )
        return value
