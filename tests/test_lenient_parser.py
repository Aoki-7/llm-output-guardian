"""宽容解析预处理规则测试。"""
from __future__ import annotations

import json

from app.rules.lenient_parser import repair_text


def parse(s: str):
    repaired, actions = repair_text(s)
    return json.loads(repaired), actions


def test_single_quotes():
    value, actions = parse("{'name': '张三'}")
    assert value == {"name": "张三"}
    assert any(a[0] == "lenient_quote" for a in actions)


def test_unquoted_keys():
    value, actions = parse("{name: 1}")
    assert value == {"name": 1}
    assert any(a[0] == "lenient_unquoted_key" for a in actions)


def test_trailing_commas():
    value, actions = parse('{"a": 1,}')
    assert value == {"a": 1}
    assert any(a[0] == "lenient_trailing_comma" for a in actions)


def test_comments():
    text = '{"a": 1 /* note */, "b": 2 // tail\n}'
    value, actions = parse(text)
    assert value == {"a": 1, "b": 2}
    assert any(a[0] == "lenient_comment" for a in actions)


def test_python_literals():
    value, actions = parse("{'a': None, 'b': True, 'c': False}")
    assert value == {"a": None, "b": True, "c": False}
    assert any(a[0] == "lenient_literal" for a in actions)


def test_nan_becomes_null():
    value, actions = parse('{"a": NaN}')
    assert value == {"a": None}
    assert any(a[0] == "lenient_nan" for a in actions)


def test_apostrophe_inside_double_quoted_string_untouched():
    value, _ = repair_text('{"msg": "it\'s ok"}')
    assert json.loads(value) == {"msg": "it's ok"}


def test_strict_json_no_actions():
    repaired, actions = repair_text('{"a": 1}')
    assert actions == []
