"""null 处理：按 nullable 与 policy.null_policy 决定保留/填默认值。"""
from __future__ import annotations

from typing import Any

from app.audit.center import AuditCenter
from app.rules._base import lookup_default, transform


def apply(value: Any, schema: dict, policy, center: AuditCenter) -> Any:
    def fn(node: Any, sub: dict, path: str) -> Any:
        if node is not None:
            return node
        types = sub.get("type")
        if isinstance(types, str):
            types = [types]
        nullable = bool(sub.get("nullable")) or (isinstance(types, list) and "null" in types)
        if nullable or policy.null_policy == "keep":
            return node
        if policy.null_policy == "default":
            val, found = lookup_default(policy.defaults, path)
            if not found and "default" in sub:
                val, found = sub["default"], True
            if found:
                center.record(
                    "structure_repair",
                    "default_fill",
                    path=path,
                    before=None,
                    after=val,
                    reason="null值按策略替换为默认值",
                )
                return val
        # error 或无默认值可用：保留 null，由语义校验报类型违规
        return node

    return transform(value, schema, "", fn)
