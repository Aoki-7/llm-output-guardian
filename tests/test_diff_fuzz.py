"""Diff 不变量的属性模糊测试：任意 old/new，回放 ops 必须得到 new。"""
from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from app.audit.center import _diff

# 安全键名字母（不含会破坏 JSON Pointer 的 / 与 ~）
_KEY_ALPHABET = "abcABC012_-\u4e00\u4e2d\u6587"

json_value = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-1000, 1000)
    | st.text(alphabet="abcABC012 \u4e00-\u9fa5", max_size=8)
    | st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False, width=16),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(
            st.text(alphabet=_KEY_ALPHABET, min_size=1, max_size=5),
            children,
            max_size=5,
        )
    ),
    max_leaves=25,
)


def _apply_ops(old, ops):
    root = old
    for op in ops:
        if op["path"] == "/":
            root = op["new"]
            continue
        parts = op["path"].split("/")[1:]
        node = root
        for p in parts[:-1]:
            node = node[int(p)] if isinstance(node, list) else node[p]
        key = parts[-1]
        kind = op["op"]
        if kind == "replace":
            if isinstance(node, list):
                node[int(key)] = op["new"]
            else:
                node[key] = op["new"]
        elif kind == "remove":
            if isinstance(node, list):
                del node[int(key)]
            else:
                del node[key]
        elif kind == "add":
            if isinstance(node, list):
                node.insert(int(key), op["new"])
            else:
                node[key] = op["new"]
    return root


@settings(max_examples=300, deadline=None)
@given(old=json_value, new=json_value)
def test_diff_replay_invariant(old, new):
    ops = _diff(old, new, "")
    assert _apply_ops(old, ops) == new


@settings(max_examples=100, deadline=None)
@given(value=json_value)
def test_diff_self_is_empty(value):
    assert _diff(value, value, "") == []
