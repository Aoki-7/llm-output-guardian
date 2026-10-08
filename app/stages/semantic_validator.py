"""阶段③：语义校验。

- 无 schema：只做 JSON 合法性检查（NaN/Infinity 等不可消费值）；
- 有 schema：按 JSON Schema（Draft 7）校验类型、枚举、范围、正则、必填、嵌套等。
"""
from __future__ import annotations

import math
from typing import Any

import jsonschema


class SemanticValidator:
    def validate(self, value: Any, schema: dict | None) -> list[dict]:
        violations = self._check_legality(value)
        if schema:
            violations.extend(self._check_schema(value, schema))
        return violations

    # ------------------------------------------------------------------
    def _check_legality(self, value: Any, path: str = "$") -> list[dict]:
        violations: list[dict] = []
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            violations.append(
                {
                    "severity": "error",
                    "path": path,
                    "keyword": "invalid_json_number",
                    "message": "JSON不允许 NaN/Infinity",
                    "expected": "finite number",
                    "actual": str(value),
                }
            )
        elif isinstance(value, dict):
            for k, v in value.items():
                violations.extend(self._check_legality(v, f"{path}.{k}"))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                violations.extend(self._check_legality(v, f"{path}[{i}]"))
        return violations

    # ------------------------------------------------------------------
    def _check_schema(self, value: Any, schema: dict) -> list[dict]:
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(value), key=lambda e: list(e.absolute_path))
        return [self._convert_error(e) for e in errors]

    def _convert_error(self, err: jsonschema.ValidationError) -> dict:
        path = self._format_path(err.absolute_path)
        return {
            "severity": "error",
            "path": path,
            "keyword": str(err.validator),
            "message": err.message,
            "expected": self._expected(err),
            "actual": err.instance,
        }

    @staticmethod
    def _format_path(parts) -> str:
        path = "$"
        for p in parts:
            if isinstance(p, int):
                path += f"[{p}]"
            else:
                path += f".{p}"
        return path

    @staticmethod
    def _expected(err: jsonschema.ValidationError) -> Any:
        kw = err.validator
        if kw in {"enum", "type", "pattern", "minLength", "maxLength", "minItems", "maxItems"}:
            return err.validator_value
        if kw in {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}:
            return {kw: err.validator_value}
        if kw == "required":
            return {"required_fields": err.validator_value}
        return None
