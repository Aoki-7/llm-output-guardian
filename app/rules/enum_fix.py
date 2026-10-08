"""枚举修正：精确 → 归一化 → 别名 → 模糊匹配。

模糊匹配低于阈值时不猜值，保留原值交由语义校验判违规。
"""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from app.audit.center import AuditCenter
from app.rules._base import last_key, transform


def apply(value: Any, schema: dict, policy, center: AuditCenter) -> Any:
    def fn(node: Any, sub: dict, path: str) -> Any:
        enum = sub.get("enum")
        if not enum or node is None or node in enum:
            return node

        sval = str(node)

        # 1) 大小写 / 空白归一化
        folded = sval.strip().casefold()
        for cand in enum:
            if str(cand).strip().casefold() == folded:
                center.record(
                    "structure_repair",
                    "enum_normalize",
                    path=path,
                    before=node,
                    after=cand,
                    reason="枚举值大小写/空白归一化后命中",
                )
                return cand

        # 2) 别名
        aliases = policy.enum_aliases.get(path) or policy.enum_aliases.get(last_key(path))
        if aliases and node in aliases:
            canonical = aliases[node]
            center.record(
                "structure_repair",
                "enum_alias",
                path=path,
                before=node,
                after=canonical,
                reason="按枚举别名映射到标准值",
            )
            return canonical

        # 3) 模糊匹配
        choices = [str(x) for x in enum]
        best = process.extractOne(
            sval,
            choices,
            processor=lambda x: x.strip().casefold(),
            scorer=fuzz.WRatio,
        )
        if best is not None:
            matched, score = best[0], best[1]
            if score / 100.0 >= policy.fuzzy_enum_threshold:
                canonical = enum[choices.index(matched)]
                center.record(
                    "structure_repair",
                    "enum_fuzzy",
                    path=path,
                    before=node,
                    after=canonical,
                    reason=f"枚举模糊匹配命中，分数={score:.1f}",
                )
                return canonical

        return node

    return transform(value, schema, "", fn)
