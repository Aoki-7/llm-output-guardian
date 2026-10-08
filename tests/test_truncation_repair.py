"""截断修复测试。"""
from __future__ import annotations

from app.rules.truncation_repair import close_brackets, repair


def test_unterminated_string():
    result = repair('{"name": "张三')
    assert result is not None
    value, _ = result
    assert value == {"name": "张三"}


def test_unterminated_object():
    value, _ = repair('{"a": 1, "b": 2')
    assert value == {"a": 1, "b": 2}


def test_unterminated_array():
    value, _ = repair('[1, 2, 3')
    assert value == [1, 2, 3]


def test_trailing_comma_after_cut():
    value, _ = repair('{"a": 1,')
    assert value == {"a": 1}


def test_dangling_key_removed():
    value, _ = repair('{"a": 1, "b":')
    assert value == {"a": 1}


def test_half_value_token_removed():
    value, _ = repair('{"a": 1, "b": tru')
    assert value == {"a": 1}


def test_nested_truncation():
    value, _ = repair('{"a": {"x": 1, "y": [1, 2')
    assert value == {"a": {"x": 1, "y": [1, 2]}}


def test_close_brackets_string_scan():
    assert close_brackets('{"a": [1, 2') == '{"a": [1, 2]}'


def test_unrepairable():
    assert repair("not json at all") is None
