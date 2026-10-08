"""字段级修复规则测试：类型/null/字段操作/数组对象/枚举。"""
from __future__ import annotations

from app.audit.center import AuditCenter
from app.rules import array_object, enum_fix, field_ops, null_handling, type_coercion
from app.schemas.io import PolicyInput


def _policy(**kw) -> PolicyInput:
    return PolicyInput(**kw)


def _schema(props: dict, required=None) -> dict:
    s = {"type": "object", "properties": props, "additionalProperties": True}
    if required:
        s["required"] = required
    return s


# —— 类型转换 ——

def test_string_to_integer():
    center = AuditCenter()
    schema = _schema({"age": {"type": "integer"}}, ["age"])
    out = type_coercion.apply({"age": "18"}, schema, _policy(), center)
    assert out == {"age": 18}
    assert center.events[0].action == "type_coercion"


def test_float_to_integer():
    center = AuditCenter()
    schema = _schema({"age": {"type": "integer"}})
    out = type_coercion.apply({"age": 18.0}, schema, _policy(), center)
    assert out == {"age": 18}


def test_string_to_boolean_chinese():
    center = AuditCenter()
    schema = _schema({"ok": {"type": "boolean"}})
    out = type_coercion.apply({"ok": "是"}, schema, _policy(), center)
    assert out == {"ok": True}


def test_number_to_string():
    center = AuditCenter()
    schema = _schema({"code": {"type": "string"}})
    out = type_coercion.apply({"code": 200}, schema, _policy(), center)
    assert out == {"code": "200"}


def test_uncoercible_kept():
    center = AuditCenter()
    schema = _schema({"age": {"type": "integer"}})
    out = type_coercion.apply({"age": "abc"}, schema, _policy(), center)
    assert out == {"age": "abc"}
    assert center.events == []


def test_boolean_not_coerced_to_integer():
    center = AuditCenter()
    schema = _schema({"v": {"type": "integer"}})
    out = type_coercion.apply({"v": True}, schema, _policy(), center)
    assert out == {"v": True}


# —— null 处理 ——

def test_null_default_from_policy():
    center = AuditCenter()
    schema = _schema({"level": {"type": "string"}})
    policy = _policy(defaults={"level": "低"})
    out = null_handling.apply({"level": None}, schema, policy, center)
    assert out == {"level": "低"}


def test_null_kept_when_nullable():
    center = AuditCenter()
    schema = _schema({"note": {"type": ["string", "null"]}})
    out = null_handling.apply({"note": None}, schema, _policy(), center)
    assert out == {"note": None}
    assert center.events == []


# —— 字段操作 ——

def test_rename():
    center = AuditCenter()
    schema = _schema({"gender": {"type": "string"}})
    policy = _policy(rename_map={"sex": "gender"})
    out = field_ops.apply({"sex": "男"}, schema, policy, center)
    assert out == {"gender": "男"}


def test_unknown_field_dropped():
    center = AuditCenter()
    schema = _schema({"a": {"type": "integer"}})
    out = field_ops.apply({"a": 1, "b": 2}, schema, _policy(unknown_fields="drop"), center)
    assert out == {"a": 1}
    assert any(e.action == "field_drop" for e in center.events)


def test_unknown_field_error_registers_violation():
    center = AuditCenter()
    schema = _schema({"a": {"type": "integer"}})
    out = field_ops.apply({"a": 1, "b": 2}, schema, _policy(unknown_fields="error"), center)
    assert out == {"a": 1, "b": 2}
    assert center.manual_violations[0]["keyword"] == "additional_field"


def test_missing_field_default_fill():
    center = AuditCenter()
    schema = _schema({"a": {"type": "integer"}, "level": {"type": "string"}}, ["a", "level"])
    policy = _policy(defaults={"level": "低"})
    out = field_ops.apply({"a": 1}, schema, policy, center)
    assert out == {"a": 1, "level": "低"}


def test_nested_rename():
    center = AuditCenter()
    schema = _schema({"user": {"type": "object", "properties": {"name": {"type": "string"}}}})
    policy = _policy(rename_map={"old_name": "name"})
    out = field_ops.apply({"user": {"old_name": "张三"}}, schema, policy, center)
    assert out == {"user": {"name": "张三"}}
    assert center.events[0].path == "user.old_name"


# —— 数组/对象 ——

def test_scalar_wrapped_to_array():
    center = AuditCenter()
    schema = _schema({"tags": {"type": "array", "items": {"type": "string"}}})
    out = array_object.apply({"tags": "x"}, schema, _policy(), center)
    assert out == {"tags": ["x"]}


def test_single_array_unwrapped():
    center = AuditCenter()
    schema = _schema({"name": {"type": "string"}})
    out = array_object.apply({"name": ["张三"]}, schema, _policy(), center)
    assert out == {"name": "张三"}


def test_kv_list_to_object():
    center = AuditCenter()
    schema = _schema({"info": {"type": "object"}})
    out = array_object.apply(
        {"info": [{"key": "a", "value": 1}]}, schema, _policy(), center
    )
    assert out == {"info": {"a": 1}}


# —— 枚举 ——

def test_enum_exact():
    center = AuditCenter()
    schema = _schema({"g": {"type": "string", "enum": ["男", "女"]}})
    out = enum_fix.apply({"g": "男"}, schema, _policy(), center)
    assert out == {"g": "男"}
    assert center.events == []


def test_enum_casefold():
    center = AuditCenter()
    schema = _schema({"g": {"type": "string", "enum": ["High", "Low"]}})
    out = enum_fix.apply({"g": "high"}, schema, _policy(), center)
    assert out == {"g": "High"}
    assert center.events[0].action == "enum_normalize"


def test_enum_alias():
    center = AuditCenter()
    schema = _schema({"g": {"type": "string", "enum": ["男", "女"]}})
    policy = _policy(enum_aliases={"g": {"male": "男"}})
    out = enum_fix.apply({"g": "male"}, schema, policy, center)
    assert out == {"g": "男"}


def test_enum_fuzzy_hit():
    center = AuditCenter()
    schema = _schema({"level": {"type": "string", "enum": ["低风险", "中风险", "高风险"]}})
    out = enum_fix.apply({"level": "低凤险"}, schema, _policy(fuzzy_enum_threshold=0.6), center)
    assert out == {"level": "低风险"}
    assert center.events[0].action == "enum_fuzzy"
    assert "分数=" in center.events[0].reason


def test_enum_no_match_kept():
    center = AuditCenter()
    schema = _schema({"g": {"enum": ["男", "女"]}})
    out = enum_fix.apply({"g": "未知值xyz"}, schema, _policy(), center)
    assert out == {"g": "未知值xyz"}
