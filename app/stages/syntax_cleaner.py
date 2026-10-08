"""阶段①：语法清洗。

纯文本层面的处理，不改变 JSON 表达的数据语义：
- Markdown 代码围栏剥离
- XML 标签包裹提取
- 前后废话 / 思考链剔除（括号配平定位 JSON 区间）
- BOM / 零宽字符 / 全角标点规范化
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.audit.center import AuditCenter

# ```json ... ``` 或未闭合的 ```json ...（输出被截断时）
_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*(.*?)(?:```|$)", re.S)
# 常见 XML 包裹标签
_XML_RE = re.compile(r"<(json|result|output|data|response)\s*>(.*?)</\1\s*>", re.S | re.I)

_BOM_AND_ZERO_WIDTH = {
    "\ufeff": "",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\u2060": "",
}
_FULLWIDTH_MAP = str.maketrans({"｛": "{", "｝": "}", "［": "[", "］": "]", "：": ":", "，": ","})


@dataclass
class Span:
    text: str
    complete: bool  # 括号是否完整配平


def _iter_spans(s: str) -> tuple[list[tuple[int, int]], int | None]:
    """字符串感知的括号扫描。

    返回 (完整配平区间[(start,end)], 未闭合时最早开括号位置)。
    """
    stack: list[tuple[str, int]] = []
    complete: list[tuple[int, int]] = []
    in_str = False
    quote = ""
    escaped = False
    start = -1

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
            continue
        if c in "{[":
            if not stack:
                start = i
            stack.append((c, i))
        elif c in "}]":
            if stack and ((c == "}" and stack[-1][0] == "{") or (c == "]" and stack[-1][0] == "[")):
                stack.pop()
                if not stack:
                    complete.append((start, i + 1))
    return complete, (stack[0][1] if stack else None)


def locate_best_span(s: str) -> Span | None:
    """从文本中定位最可能的 JSON 片段。"""
    complete, open_start = _iter_spans(s)
    if complete:
        # 多个候选时取最长（通常是主体结果而非示例片段）
        start, end = max(complete, key=lambda se: se[1] - se[0])
        return Span(s[start:end], True)
    if open_start is not None:
        return Span(s[open_start:], False)
    return None


class SyntaxCleaner:
    def __init__(self, center: AuditCenter) -> None:
        self.center = center

    def clean(self, raw_text: str) -> str | None:
        text = raw_text

        # 1) BOM / 零宽字符
        stripped = text
        for ch, rep in _BOM_AND_ZERO_WIDTH.items():
            stripped = stripped.replace(ch, rep)
        if stripped != text:
            self.center.record(
                "syntax_clean",
                "normalize_chars",
                before=text[:80],
                after=stripped[:80],
                reason="移除BOM/零宽字符",
            )
            text = stripped

        # 2) Markdown 围栏
        fenced: list[str] = []
        for m in _FENCE_RE.finditer(text):
            inner = m.group(1).strip()
            if "{" in inner or "[" in inner:
                fenced.append(inner)
        if fenced:
            source = max(fenced, key=len)
            self.center.record(
                "syntax_clean",
                "strip_fence",
                before=text[:120],
                after=source[:120],
                reason="剥离Markdown代码围栏",
            )
        else:
            # 3) XML 包裹
            m = _XML_RE.search(text)
            if m and ("{" in m.group(2) or "[" in m.group(2)):
                source = m.group(2).strip()
                self.center.record(
                    "syntax_clean",
                    "xml_extract",
                    before=text[:120],
                    after=source[:120],
                    reason="从XML标签中提取JSON",
                )
            else:
                source = text

        # 4) 括号定位
        span = locate_best_span(source)
        if span is None:
            # 5) 全角标点兜底
            normalized = source.translate(_FULLWIDTH_MAP)
            if normalized != source:
                self.center.record(
                    "syntax_clean",
                    "normalize_chars",
                    before=source[:120],
                    after=normalized[:120],
                    reason="全角标点规范化为半角",
                )
                source = normalized
                span = locate_best_span(source)

        if span is None:
            return None

        candidate = span.text.strip()
        if candidate != source.strip():
            self.center.record(
                "syntax_clean",
                "extract_json",
                before=source[:120],
                after=candidate[:120],
                reason="剔除JSON前后的废话/思考链内容",
            )
        return candidate
