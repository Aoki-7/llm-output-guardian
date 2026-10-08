"""规则共享工具：schema 跟随的递归变换、路径与默认值查找。"""
from __future__ import annotations

from typing import Any, Callable

from app.core.config import settings

NodeFn = Callable[[Any, dict, str], Any]

_MISSING = object()


def transform(value: Any, schema: dict, path: str, fn: NodeFn, depth: int = 0) -> Any:
    """先对当前节点应用 fn，再按 schema 递归进入对象属性 / 数组元素。"""
    value = fn(value, schema, path)
    if depth >= settings.max_depth:
        return value
    if isinstance(value, dict) and schema.get("type") == "object":
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                child_path = f"{path}.{k}" if path else k
                value[k] = transform(value[k], sub, child_path, fn, depth + 1)
    elif isinstance(value, list) and schema.get("type") == "array":
        item_schema = schema.get("items", {})
        for i in range(len(value)):
            value[i] = transform(value[i], item_schema, f"{path}[{i}]", fn, depth + 1)
    return value


def last_key(path: str) -> str:
    """user.age[0] → age。"""
    leaf = path.split(".")[-1]
    return leaf.split("[")[0]


def lookup_default(defaults: dict, path: str) -> tuple[Any, bool]:
    """默认值查找：先试完整点路径，再按嵌套 dict 逐层下钻。"""
    if path in defaults:
        return defaults[path], True
    cur: Any = defaults
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None, False
    return cur, True
