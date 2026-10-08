"""语法清洗器测试。"""
from __future__ import annotations

from app.audit.center import AuditCenter
from app.stages.syntax_cleaner import SyntaxCleaner, locate_best_span


def _clean(text: str):
    center = AuditCenter()
    result = SyntaxCleaner(center).clean(text)
    return result, center


def test_plain_json_unchanged():
    raw = '{"a": 1}'
    out, center = _clean(raw)
    assert out == '{"a": 1}'
    assert center.events == []


def test_markdown_fence_stripped():
    raw = '好的，结果如下：```json\n{"a": 1}\n```\n希望对你有帮助'
    out, center = _clean(raw)
    assert out == '{"a": 1}'
    # 围栏内容本身就是纯JSON时，只需剥离围栏
    assert any(e.action == "strip_fence" for e in center.events)


def test_inline_fence():
    raw = '结果是 ```json {"a": 1} ``` 谢谢'
    out, _ = _clean(raw)
    assert out == '{"a": 1}'


def test_preamble_only():
    raw = '让我分析一下数据……\n{"name": "张三", "age": 20}\n以上是结果。'
    out, center = _clean(raw)
    assert '"name": "张三"' in out
    assert any(e.action == "extract_json" for e in center.events)


def test_xml_wrapped():
    raw = '<result>{"a": 1}</result>'
    out, center = _clean(raw)
    assert out == '{"a": 1}'
    assert any(e.action == "xml_extract" for e in center.events)


def test_fullwidth_recovery():
    raw = '｛"a"： 1｝'
    out, center = _clean(raw)
    assert out == '{"a": 1}'
    assert any(e.action == "normalize_chars" for e in center.events)


def test_no_json_returns_none():
    out, _ = _clean("今天天气不错，适合出门。")
    assert out is None


def test_locate_prefers_longest_span():
    text = '{"x": 1} some text {"y": 2, "z": 3}'
    span = locate_best_span(text)
    assert span.text == '{"y": 2, "z": 3}'


def test_bom_and_zero_width_removed():
    raw = '\ufeff{"a":\u200b 1}'
    out, center = _clean(raw)
    assert out == '{"a": 1}'
    assert any(e.action == "normalize_chars" for e in center.events)


def test_array_output():
    raw = '结果如下：\n[1, 2, 3]\n'
    out, _ = _clean(raw)
    assert out == '[1, 2, 3]'
