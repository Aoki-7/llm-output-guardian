"""Schema 编译器：业务简写格式 → 标准 JSON Schema（Draft 7）。

支持的简写：
    {"age": "integer"}                  → {"type":"integer"}
    {"gender": ["男", "女"]}            → {"type":"string","enum":[...]}
    {"score": "number"}                 → {"type":"number"}
    {"tags": ["string"]}                → 数组，元素 string
    {"profile": {...}}                  → 嵌套 object
    {"age?": "integer"}                 → 键名以 ? 结尾表示非必填

也可直接传入标准 JSON Schema（用于 minimum/pattern 等强约束）。
"""
from __future__ import annotations

_TYPE_ALIASES = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "num": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "object": "object",
    "dict": "object",
    "array": "array",
    "list": "array",
}

_JSON_SCHEMA_MARKERS = {
    "type", "properties", "items", "required", "enum", "const", "$schema", "$ref",
    "anyOf", "allOf", "oneOf", "minimum", "maximum", "pattern", "format",
    "minLength", "maxLength", "nullable", "additionalProperties", "default",
}


# 仅可能出现在 JSON Schema 中、业务字段几乎不可能同名的结构性关键字
_STRUCTURAL_KEYWORDS = {
    "properties", "items", "required", "$ref", "additionalProperties",
    "anyOf", "oneOf", "allOf", "not", "definitions", "$defs",
}


def looks_like_json_schema(d: dict) -> bool:
    """启发式判断：dict 是标准 JSON Schema 而非业务简写。

    - 含 $schema → 标准；
    - 含结构性关键字（properties/items/required 等）→ 标准；
    - type 与其他约束关键字同时出现 → 标准；
    - 仅含 type 一个关键字时，业务字段恰好叫 type 的场景更常见，视为简写。
    """
    if not isinstance(d, dict):
        return False
    if "$schema" in d:
        return True
    if _STRUCTURAL_KEYWORDS & set(d.keys()):
        return True
    markers = _JSON_SCHEMA_MARKERS & set(d.keys())
    return "type" in markers and len(markers) >= 2


def compile_schema(schema: dict) -> tuple[dict, bool]:
    """返回 (JSON Schema, 是否本来就是标准格式)。"""
    if looks_like_json_schema(schema):
        return schema, True
    return _compile_object(schema), False


def _compile_object(d: dict) -> dict:
    properties: dict = {}
    required: list[str] = []
    for raw_key, v in d.items():
        optional = raw_key.endswith("?")
        key = raw_key[:-1] if optional else raw_key
        properties[key] = _compile_value(v)
        if not optional:
            required.append(key)
    result: dict = {"type": "object", "properties": properties, "additionalProperties": True}
    if required:
        result["required"] = required
    return result


def _enum_schema(values: list) -> dict:
    if all(isinstance(x, bool) for x in values):
        return {"type": "boolean", "enum": values}
    if all(isinstance(x, int) and not isinstance(x, bool) for x in values):
        return {"type": "integer", "enum": values}
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in values):
        return {"type": "number", "enum": values}
    return {"type": "string", "enum": values}


def _compile_value(v: object) -> dict:
    if isinstance(v, str):
        t = _TYPE_ALIASES.get(v.strip().lower())
        return {"type": t} if t else {"type": "string"}

    if isinstance(v, list):
        # ["string"] / ["integer"] → 该类型的数组
        if len(v) == 1:
            only = v[0]
            if isinstance(only, str) and only.strip().lower() in _TYPE_ALIASES:
                return {"type": "array", "items": {"type": _TYPE_ALIASES[only.strip().lower()]}}
            if isinstance(only, dict):
                return {"type": "array", "items": _compile_value(only)}
        return _enum_schema(v)

    if isinstance(v, dict):
        if looks_like_json_schema(v):
            return v
        return _compile_object(v)

    return {}
