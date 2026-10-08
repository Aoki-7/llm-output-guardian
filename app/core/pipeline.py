"""流水线编排器：串联三阶段，汇总审计结果并裁决状态。"""
from __future__ import annotations

import uuid
from typing import Any

from app.audit.center import AuditCenter
from app.schema_engine.compiler import compile_schema
from app.schemas.io import PolicyInput, Violation
from app.stages.semantic_validator import SemanticValidator
from app.stages.structure_repairer import StructureRepairer
from app.stages.syntax_cleaner import SyntaxCleaner


class GuardianPipeline:
    def __init__(self, store: object | None = None, llm_client: object | None = None) -> None:
        self.store = store
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # 主接口：清洗 + 修复 + 校验
    # ------------------------------------------------------------------
    def clean(
        self,
        raw_text: str,
        schema_in: dict | None,
        policy_in: PolicyInput | None,
        validate_schema: bool = True,
    ) -> dict:
        policy = policy_in or PolicyInput()
        center = AuditCenter()
        trace_id = uuid.uuid4().hex

        compiled_schema: dict | None = None
        if schema_in:
            compiled_schema, _ = compile_schema(schema_in)

        # ① 语法清洗
        candidate = SyntaxCleaner(center).clean(raw_text)
        repairer = StructureRepairer(center, self.llm_client)
        if candidate is not None:
            # ② 结构修复
            value, initial = repairer.repair(candidate, compiled_schema, policy)
        elif policy.llm_fallback:
            # 语法层未定位到任何JSON片段：直接交修复器，由其内部触发LLM兜底
            value, initial = repairer.repair(raw_text, compiled_schema, policy)
        else:
            value, initial = None, None

        if value is None:
            return self._build_response(
                center, trace_id, raw_text, None,
                [self._fatal("JSON结构无法定位或修复失败")],
                compiled_schema, policy=policy,
            )

        # ③ 语义校验
        violations = SemanticValidator().validate(value, compiled_schema if validate_schema else None)
        violations_dicts = violations + center.manual_violations

        return self._build_response(
            center, trace_id, raw_text, value, violations_dicts,
            compiled_schema, initial=initial, policy=policy,
        )

    # ------------------------------------------------------------------
    # 仅校验：输入必须已经是合法 JSON 值
    # ------------------------------------------------------------------
    def validate(self, data: Any, schema_in: dict | None) -> dict:
        center = AuditCenter()
        trace_id = uuid.uuid4().hex
        compiled_schema: dict | None = None
        if schema_in:
            compiled_schema, _ = compile_schema(schema_in)

        violations = SemanticValidator().validate(data, compiled_schema)
        return self._build_response(
            center, trace_id, "", data, violations, compiled_schema, initial=data,
        )

    # ------------------------------------------------------------------
    def _build_response(
        self,
        center: AuditCenter,
        trace_id: str,
        raw_text: str,
        value: Any,
        violation_dicts: list[dict],
        schema: dict | None,
        initial: Any = None,
        policy: PolicyInput | None = None,
    ) -> dict:
        violations = [Violation(**v) for v in violation_dicts]
        confidence = center.compute_confidence(schema)
        diff = center.make_diff(initial, value)

        has_error = any(v.severity == "error" for v in violations)
        if value is None or has_error:
            status = "invalid"
        elif center.events:
            status = "repaired"
        else:
            status = "valid"

        response = {
            "status": status,
            "result": value,
            "confidence": confidence,
            "violations": [v.model_dump() for v in violations],
            "audit_trail": [ev.model_dump() for ev in center.events],
            "diff": diff,
            "trace_id": trace_id,
            "raw_input": raw_text,
        }

        if self.store is not None and (policy is None or policy.persist):
            self.store.save(trace_id, response)

        return response

    @staticmethod
    def _fatal(message: str) -> dict:
        return {
            "severity": "error",
            "path": "$",
            "keyword": "parse_error",
            "message": message,
            "expected": None,
            "actual": None,
        }
