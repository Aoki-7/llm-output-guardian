"""审计中心：收集审计事件、计算字段级/全局置信度、生成结构化 Diff。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .events import AuditEvent, Method, Stage

_SCORING_PATH = Path(__file__).with_name("scoring.yaml")


def _load_scoring() -> dict:
    with _SCORING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class AuditCenter:
    def __init__(self) -> None:
        scoring = _load_scoring()
        self._actions: dict = scoring.get("actions", {})
        self._caps: dict = scoring.get("caps", {})
        self._llm_cap: float = float(scoring.get("llm_cap", 0.6))
        self.events: list[AuditEvent] = []
        # 规则阶段主动登记的语义违规（如 unknown_fields=error）
        self.manual_violations: list[dict] = []

    def record(
        self,
        stage: Stage,
        action: str,
        path: str = "",
        before: Any = None,
        after: Any = None,
        reason: str = "",
        method: Method = "rule",
        category: str | None = None,
        delta: float | None = None,
    ) -> AuditEvent:
        cfg = self._actions.get(action, {})
        if delta is None:
            delta = float(cfg.get("delta", 0.0))
        if category is None:
            category = str(cfg.get("category", ""))
        event = AuditEvent(
            stage=stage,
            action=action,
            path=path,
            before=before,
            after=after,
            reason=reason,
            method=method,
            confidence_delta=delta,
            category=category,
        )
        self.events.append(event)
        return event

    def add_manual_violation(self, violation: dict) -> None:
        self.manual_violations.append(violation)

    # ------------------------------------------------------------------
    # 置信度
    # ------------------------------------------------------------------
    def compute_confidence(self, schema: dict | None) -> dict:
        """计算字段级与全局置信度。

        字段级：同一 path 下所有事件罚分累加，截断到 [0,1]；
        全局：schema 叶节点字段（含未被修改、初始为 1.0 的字段）的平均分，
              再叠加全局动作罚分（分类罚分受 caps 封顶）；
        LLM 一旦参与修复，全局分封顶 llm_cap。
        """
        # 1) 字段罚分
        field_penalties: dict[str, float] = {}
        for ev in self.events:
            if ev.path:
                field_penalties[ev.path] = field_penalties.get(ev.path, 0.0) + ev.confidence_delta

        known_paths = set(_leaf_paths(schema)) | set(field_penalties)
        field_scores = {
            p: max(0.0, min(1.0, 1.0 + field_penalties.get(p, 0.0))) for p in sorted(known_paths)
        }
        field_avg = sum(field_scores.values()) / len(field_scores) if field_scores else 1.0

        # 2) 全局罚分（path 为空的事件），按 category 汇总并套用封顶
        cat_penalties: dict[str, float] = {}
        uncateg_penalty = 0.0
        for ev in self.events:
            if ev.path:
                continue
            if ev.category:
                cat_penalties[ev.category] = cat_penalties.get(ev.category, 0.0) + ev.confidence_delta
            else:
                uncateg_penalty += ev.confidence_delta

        global_penalty = uncateg_penalty
        for cat, total in cat_penalties.items():
            cap = self._caps.get(cat)
            if cap is not None:
                # cap 为负：罚分不超过 cap（如 -0.15），但实际罚分更轻时尊重实际
                global_penalty += max(float(cap), total)
            else:
                global_penalty += total

        score = max(0.0, min(1.0, field_avg + global_penalty))

        # 3) LLM 封顶
        llm_involved = any(ev.method == "llm" for ev in self.events)
        if llm_involved:
            score = min(score, self._llm_cap)

        return {
            "score": round(score, 4),
            "field_scores": field_scores,
            "llm_capped": llm_involved,
        }

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------
    def make_diff(self, old: Any, new: Any) -> list[dict]:
        """生成 RFC6902 风格的差异操作列表（op/path/old/new）。

        不变量：将 ops 依次应用到 old 可得到 new。
        old 为 None（初次解析即失败、无基线）时，整体记一次 replace。
        """
        return _diff(old, new, "")


def _leaf_paths(schema: dict | None, prefix: str = "") -> list[str]:
    """遍历 JSON Schema 的 object 属性，收集叶节点点路径。"""
    if not schema or not isinstance(schema, dict):
        return []
    paths: list[str] = []
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, sub in props.items():
            p = f"{prefix}.{key}" if prefix else key
            if isinstance(sub, dict) and sub.get("type") == "object" and sub.get("properties"):
                paths.extend(_leaf_paths(sub, p))
            else:
                paths.append(p)
    return paths


def _diff(old: Any, new: Any, prefix: str) -> list[dict]:
    if old is None or new is None or type(old) is not type(new):
        if old != new:
            return [{"op": "replace", "path": prefix or "/", "old": old, "new": new}]
        return []

    if isinstance(old, dict):
        ops: list[dict] = []
        for k in old:
            if k not in new:
                ops.append({"op": "remove", "path": f"{prefix}/{k}", "old": old[k]})
        for k in new:
            if k not in old:
                ops.append({"op": "add", "path": f"{prefix}/{k}", "new": new[k]})
            else:
                ops.extend(_diff(old[k], new[k], f"{prefix}/{k}"))
        return ops

    if isinstance(old, list):
        ops = []
        for i in range(min(len(old), len(new))):
            ops.extend(_diff(old[i], new[i], f"{prefix}/{i}"))
        # 删除按索引倒序，保证回放时索引不发生漂移
        for i in range(len(old) - 1, len(new) - 1, -1):
            ops.append({"op": "remove", "path": f"{prefix}/{i}", "old": old[i]})
        # 新增在尾部按顺序插入
        for j in range(max(0, len(new) - len(old))):
            ops.append({"op": "add", "path": f"{prefix}/{len(old) + j}", "new": new[len(old) + j]})
        return ops

    if old != new:
        return [{"op": "replace", "path": prefix or "/", "old": old, "new": new}]
    return []
