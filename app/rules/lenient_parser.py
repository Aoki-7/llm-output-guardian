"""宽容解析的文本预处理规则。

在严格 json.loads 失败后，逐条尝试可审计的文本修复：
注释剥离、单引号转换、未引用 key 补引号、尾逗号删除、
Python 字面量转换、NaN/Infinity 处理。

所有"结构性替换"都只在字符串字面量之外进行。
"""
from __future__ import annotations

import re

# —— 字符串感知的分段工具 ——

def _split_string_segments(s: str) -> list[tuple[bool, str]]:
    """把文本切分为 [(是否在字符串内, 片段)]。

    同时识别单双引号；转义符按反斜杠处理。
    """
    segments: list[tuple[bool, str]] = []
    buf: list[str] = []
    in_str = False
    quote = ""
    escaped = False

    def flush(in_string: bool) -> None:
        if buf:
            segments.append((in_string, "".join(buf)))
            buf.clear()

    for c in s:
        if in_str:
            buf.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                in_str = False
                flush(True)
            continue
        if c in ('"', "'"):
            flush(False)
            in_str = True
            quote = c
            buf.append(c)
        else:
            buf.append(c)
    flush(in_str)
    return segments


def _replace_outside_strings(s: str, pattern: re.Pattern, repl) -> tuple[str, bool]:
    changed = False
    parts: list[str] = []
    for is_str, seg in _split_string_segments(s):
        if is_str:
            parts.append(seg)
        else:
            new_seg, n = pattern.subn(repl, seg)
            if n:
                changed = True
            parts.append(new_seg)
    return "".join(parts), changed


# —— 各条修复 ——

_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE_RE = re.compile(r"//[^\n]*")
_SINGLE_QUOTE_RE = re.compile(r"'((?:[^'\\\n]|\\.)*)'")
_UNQUOTED_KEY_RE = re.compile(r'([\{\,]\s*)([A-Za-z_$][\w$\-]*)(\s*:)')
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_PY_NONE_RE = re.compile(r"\bNone\b")
_PY_TRUE_RE = re.compile(r"\bTrue\b")
_PY_FALSE_RE = re.compile(r"\bFalse\b")
_NAN_RE = re.compile(r"\b(?:NaN|Infinity|-Infinity)\b")


def _convert_single_quotes(s: str) -> tuple[str, bool]:
    def repl(m: re.Match) -> str:
        inner = m.group(1).replace("\\'", "'").replace('\\"', '"')
        inner = inner.replace('"', '\\"')
        return f'"{inner}"'

    # 单引号字符串的转换不能用"字符串外分段"（它本身就是字符串），
    # 直接全局正则；双引号字符串内的撇号不会被匹配（要求成对单引号）。
    new, n = _SINGLE_QUOTE_RE.subn(repl, s)
    return new, n > 0


def repair_text(s: str) -> tuple[str, list[tuple[str, str, str]]]:
    """对文本依次尝试宽容修复。

    返回 (修复后文本, 触发的动作列表[(action, before_snippet, after_snippet)])。
    """
    actions: list[tuple[str, str, str]] = []

    def run(name: str, func) -> None:
        nonlocal s
        before = s
        s, changed = func(s)
        if changed:
            actions.append((name, before[:80], s[:80]))

    run("lenient_comment", lambda x: _replace_outside_strings(x, _COMMENT_BLOCK_RE, ""))
    run("lenient_comment", lambda x: _replace_outside_strings(x, _COMMENT_LINE_RE, ""))
    run("lenient_quote", _convert_single_quotes)
    run(
        "lenient_unquoted_key",
        lambda x: _replace_outside_strings(x, _UNQUOTED_KEY_RE, r'\1"\2"\3'),
    )
    run(
        "lenient_trailing_comma",
        lambda x: _replace_outside_strings(x, _TRAILING_COMMA_RE, r"\1"),
    )
    run("lenient_literal", lambda x: _replace_outside_strings(x, _PY_NONE_RE, "null"))
    run("lenient_literal", lambda x: _replace_outside_strings(x, _PY_TRUE_RE, "true"))
    run("lenient_literal", lambda x: _replace_outside_strings(x, _PY_FALSE_RE, "false"))
    run("lenient_nan", lambda x: _replace_outside_strings(x, _NAN_RE, "null"))

    return s, actions
