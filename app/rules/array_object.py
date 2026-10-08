"""数组 / 对象互转与标量包裹。"""
from __future__ import annotations

from typing import Any

from app.audit.center import AuditCenter
from app.rules._base import transform

_SCALAR_TYPES = {"string", "integer", "number", "boolean"}


def apply(value: Any, schema: dict, policy, center: AuditCenter) -> Any:
    def fn(node: Any, sub: dict, path: str) -> Any:
        t = sub.get("type")
        if node is None:
            return node

        # schema 要数组，实际是标量 → 包裹
        if t == "array" and not isinstance(node, (list, dict)):
            center.record(
                "structure_repair",
                "array_wrap",
                path=path,
                before=node,
                after=[node],
                reason="schema要求array，将标量包裹为单元素数组",
            )
            return [node]

        # schema 要数组，实际是对象 → key/value 列表
        if t == "array" and isinstance(node, dict):
            kv = [{"key": k, "value": v} for k, v in node.items()]
            center.record(
                "structure_repair",
                "object_kv",
                path=path,
                before=node,
                after=kv,
                reason="schema要求array，对象转key/value列表",
            )
            return kv

        # schema 要对象，实际是 key/value 列表 → 对象
        if t == "object" and isinstance(node, list):
            if all(isinstance(x, dict) and "key" in x and "value" in x for x in node):
                obj = {x["key"]: x["value"] for x in node}
                center.record(
                    "structure_repair",
                    "object_kv",
                    path=path,
                    before=node,
                    after=obj,
                    reason="schema要求object，key/value列表转对象",
                )
                return obj

        # schema 要标量，实际是单元素数组 → 解包
        if t in _SCALAR_TYPES and isinstance(node, list) and len(node) == 1:
            center.record(
                "structure_repair",
                "array_unwrap",
                path=path,
                before=node,
                after=node[0],
                reason="schema要求标量，单元素数组解包",
            )
            return node[0]

        return node

    return transform(value, schema, "", fn)
