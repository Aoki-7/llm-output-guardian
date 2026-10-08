"""Schema 编译器测试。"""
from __future__ import annotations

import jsonschema
import pytest

from app.schema_engine.compiler import compile_schema, looks_like_json_schema


def test_integer_shorthand():
    schema, standard = compile_schema({"age": "integer"})
    assert standard is False
    assert schema["properties"]["age"] == {"type": "integer"}
    assert schema["required"] == ["age"]


def test_enum_shorthand():
    schema, _ = compile_schema({"gender": ["男", "女"]})
    assert schema["properties"]["gender"] == {"type": "string", "enum": ["男", "女"]}


def test_integer_enum():
    schema, _ = compile_schema({"level": [1, 2, 3]})
    assert schema["properties"]["level"]["type"] == "integer"


def test_array_shorthand():
    schema, _ = compile_schema({"tags": ["string"]})
    assert schema["properties"]["tags"] == {
        "type": "array", "items": {"type": "string"}
    }


def test_nested_object():
    schema, _ = compile_schema({"user": {"name": "string", "age?": "integer"}})
    user = schema["properties"]["user"]
    assert user["properties"]["name"] == {"type": "string"}
    assert user["required"] == ["name"]


def test_standard_json_schema_passthrough():
    raw = {
        "type": "object",
        "properties": {"age": {"type": "integer", "minimum": 0}},
        "required": ["age"],
    }
    schema, standard = compile_schema(raw)
    assert standard is True
    assert schema is raw


def test_simple_compiled_schema_has_no_range_by_default():
    # 简写 schema 无法表达范围：负数不会被拦截（业务需要范围时用标准JSON Schema）
    schema, _ = compile_schema({"age": "integer"})
    jsonschema.Draft7Validator(schema).validate({"age": -1})


def test_standard_schema_rejects_negative():
    schema = {
        "type": "object",
        "properties": {"age": {"type": "integer", "minimum": 0}},
        "required": ["age"],
    }
    compiled, standard = compile_schema(schema)
    assert standard is True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft7Validator(compiled).validate({"age": -1})


def test_looks_standard_detection():
    assert looks_like_json_schema({"$schema": "http://json-schema.org/draft-07/schema#"})
    assert not looks_like_json_schema({"type": ["a", "b"]})
