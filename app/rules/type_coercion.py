"""类型安全转换：按 schema 目标类型把值转换为可消费类型。

无法安全转换时保留原值，由语义校验报违规 —— 不硬转、不猜值。
"""
from __future__ import annotations

import re
from typing import Any

from app.audit.center import AuditCenter
from app.rules._base import transform

_INT_RE = re.compile(r"^[+-]?\d+$")
_NUM_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_BOOL_WORDS = {
    "true": True, "false": False, "1": True, "0": False,
    "yes": True, "no": False, "是": True, "否": False,
}

_MISSING = object()


def _target_types(sub: dict) -> list[str]:
    t = sub.get("type")
    if t is None:
        return []
    return t if isinstance(t, list) else [t]


def _matches(node: Any, t: str) -> bool:
    if t == "null":
        return node is None
    if node is None:
        return False
    if t == "string":
        return isinstance(node, str)
    if t == "integer":
        return isinstance(node, int) and not isinstance(node, bool)
    if t == "number":
        return isinstance(node, (int, float)) and not isinstance(node, bool)
    if t == "boolean":
        return isinstance(node, bool)
    if t == "object":
        return isinstance(node, dict)
    if t == "array":
        return isinstance(node, list)
    return False


def _coerce(node: Any, t: str) -> Any:
    if t == "integer":
        if isinstance(node, str) and _INT_RE.match(node.strip()):
            return int(node.strip())
        if isinstance(node, float) and float(node).is_integer():
            return int(node)
    elif t == "number":
        if isinstance(node, str) and _NUM_RE.match(node.strip()):
            return float(node.strip())
    elif t == "boolean":
        if isinstance(node, str):
            key = node.strip().lower()
            if key in _BOOL_WORDS:
                return _BOOL_WORDS[key]
        if isinstance(node, int) and not isinstance(node, bool) and node in (0, 1):
            return bool(node)
    elif t == "string":
        if isinstance(node, bool):
            return "true" if node else "false"
        if isinstance(node, (int, float)):
            return str(node)
    return _MISSING


def apply(value: Any, schema: dict, policy, center: AuditCenter) -> Any:
    def fn(node: Any, sub: dict, path: str) -> Any:
        if node is None:
            return node
        types = _target_types(sub)
        if not types:
            return node
        if any(_matches(node, t) for t in types):
            return node
        for t in types:
            converted = _coerce(node, t)
            if converted is not _MISSING:
                center.record(
                    "structure_repair",
                    "type_coercion",
                    path=path,
                    before=node,
                    after=converted,
                    reason=f"schema要求 {t}，原值可安全转换",
                )
                return converted
        return node

    return transform(value, schema, "", fn)
