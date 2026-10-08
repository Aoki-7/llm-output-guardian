"""JSON 截断修复。

输出被流式截断时，常见症状：
- 字符串未闭合、对象/数组括号未闭合；
- 最后一个元素只写了一半（"key": 、"key": 12、tru）；
- 末尾残留逗号。

策略：先栈式闭合，再用 json.loads 验证；若错误位置指向半截元素，
回退到上一个安全边界（`,`/`{`/`[`）后重新闭合，迭代至多 max_iter 次。
"""
from __future__ import annotations

import json
from json import JSONDecodeError


def _scan(s: str) -> tuple[list[str], bool]:
    """返回 (未闭合开括号栈, 结束时是否处于未闭合字符串内)。"""
    stack: list[str] = []
    in_str = False
    quote = ""
    escaped = False
    for c in s:
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                in_str = False
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
        elif c in "{[":
            stack.append(c)
        elif c in "}]":
            if stack and ((c == "}" and stack[-1] == "{") or (c == "]" and stack[-1] == "[")):
                stack.pop()
    return stack, in_str


def _strip_dangling_key(t: str) -> str:
    """`:key` 残留时，连同键一起回退到上一个分隔符。"""
    seps = [t.rfind(","), t.rfind("{"), t.rfind("[")]
    j = max(seps)
    if j < 0:
        return ""
    if t[j] in "{[":
        return t[: j + 1]
    return t[:j]  # 丢弃半截逗号


def _cleanup_tail(t: str) -> str:
    changed = True
    while changed:
        changed = False
        t = t.rstrip()
        if t.endswith(","):
            t = t[:-1]
            changed = True
        elif t.endswith(":"):
            t = _strip_dangling_key(t[:-1])
            changed = True
    return t


def close_brackets(s: str) -> str:
    stack, in_str = _scan(s)
    tail = s
    if in_str:
        tail += '"'
    tail = _cleanup_tail(tail)
    closers = "".join("}" if o == "{" else "]" for o in reversed(stack))
    return tail + closers


def _separator_positions(s: str) -> list[int]:
    """收集字符串外的结构分隔符位置（',' '{' '['）。"""
    positions: list[int] = []
    in_str = False
    quote = ""
    escaped = False
    for i, c in enumerate(s):
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                in_str = False
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
        elif c in ",{[":
            positions.append(i)
    return positions


def _cut_to_boundary(s: str, pos: int) -> str:
    candidates = [p for p in _separator_positions(s) if p <= pos]
    if not candidates:
        return ""
    j = candidates[-1]
    if s[j] in "{[":
        return s[: j + 1]
    return s[:j]  # 逗号连同半截元素一起丢弃


def repair(s: str, max_iter: int = 10) -> tuple[object, str] | None:
    """迭代修复截断 JSON。

    成功返回 (解析值, 最终修复文本)；无法修复返回 None。
    """
    cur = s
    for _ in range(max_iter):
        candidate = close_brackets(cur)
        try:
            return json.loads(candidate), candidate
        except JSONDecodeError as e:
            nxt = _cut_to_boundary(cur, min(e.pos, len(cur) - 1))
            if nxt == cur or not nxt:
                break
            cur = nxt
    return None
