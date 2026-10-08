"""字段操作：重命名、未知字段删除/报错、缺失字段默认值补全（递归）。"""
from __future__ import annotations

from typing import Any

from app.audit.center import AuditCenter
from app.rules._base import lookup_default


def apply(value: Any, schema: dict, policy, center: AuditCenter) -> Any:
    return _apply_object(value, schema, "", policy, center)


def _apply_object(node: Any, sub: dict, path: str, policy, center: AuditCenter) -> Any:
    # 数组：递归元素
    if isinstance(node, list) and sub.get("type") == "array":
        item_schema = sub.get("items", {})
        for i in range(len(node)):
            node[i] = _apply_object(node[i], item_schema, f"{path}[{i}]", policy, center)
        return node

    if not isinstance(node, dict) or sub.get("type") != "object":
        return node

    props = sub.get("properties", {})

    # 1) 重命名（先于其他操作，保证后续按新名匹配 schema）
    for old in list(node.keys()):
        full = f"{path}.{old}" if path else old
        new = policy.rename_map.get(full) or policy.rename_map.get(old)
        if new and new not in node:
            node[new] = node.pop(old)
            center.record(
                "structure_repair",
                "rename_field",
                path=full,
                before=old,
                after=new,
                reason="按rename_map重命名字段",
            )

    # 2) 递归处理子节点
    for k in list(node.keys()):
        if k in props:
            child_path = f"{path}.{k}" if path else k
            node[k] = _apply_object(node[k], props[k], child_path, policy, center)

    # 3) 未知字段
    for k in list(node.keys()):
        if k not in props:
            full = f"{path}.{k}" if path else k
            if policy.unknown_fields == "drop":
                val = node.pop(k)
                center.record(
                    "structure_repair",
                    "field_drop",
                    path=full,
                    before=val,
                    after="<removed>",
                    reason="schema外未知字段，按策略删除",
                )
            elif policy.unknown_fields == "error":
                center.add_manual_violation(
                    {
                        "severity": "error",
                        "path": full,
                        "keyword": "additional_field",
                        "message": f"存在schema外未知字段: {k}",
                        "expected": None,
                        "actual": k,
                    }
                )

    # 4) 缺失字段默认值补全
    for k, ksub in props.items():
        if k not in node:
            child_path = f"{path}.{k}" if path else k
            val, found = lookup_default(policy.defaults, child_path)
            if not found and isinstance(ksub, dict) and "default" in ksub:
                val, found = ksub["default"], True
            if found:
                node[k] = val
                center.record(
                    "structure_repair",
                    "default_fill",
                    path=child_path,
                    before="<missing>",
                    after=val,
                    reason="缺失字段按默认值补全",
                )

    return node
