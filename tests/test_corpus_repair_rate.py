"""真实脏输出语料验证：修复率与基线对比（数据驱动）。"""
from __future__ import annotations

import json
import pathlib

from app.core.pipeline import GuardianPipeline
from app.schemas.io import PolicyInput

CORPUS_PATH = pathlib.Path(__file__).parent / "corpus" / "cases.json"


def _load_cases() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_corpus_and_baseline_comparison(capsys):
    cases = _load_cases()
    pipeline = GuardianPipeline(store=None)

    rows = []
    guard_consumable = 0
    baseline_consumable = 0

    for case in cases:
        policy = PolicyInput(**(case.get("policy") or {}))
        body = pipeline.clean(case["raw"], case.get("schema"), policy)

        assert body["status"] == case["expected_status"], f"场景失败: {case['name']}"
        if "expected_result" in case:
            assert body["result"] == case["expected_result"], f"结果不符: {case['name']}"

        # 基线：仅严格 json.loads，能解析就算"可消费"（不做schema校验）
        try:
            json.loads(case["raw"])
            baseline_ok = True
        except json.JSONDecodeError:
            baseline_ok = False

        guard_ok = body["status"] in ("valid", "repaired")
        guard_consumable += int(guard_ok)
        baseline_consumable += int(baseline_ok)
        rows.append((case["scene"], body["status"], body["confidence"]["score"], baseline_ok))

    total = len(cases)
    with capsys.disabled():
        print("\n场景                       | 服务状态  | 置信度 | 基线json.loads")
        print("-" * 72)
        for scene, status, score, baseline_ok in rows:
            print(f"{scene:<26} | {status:<9} | {score:<6.2f} | {'通过' if baseline_ok else '失败'}")
        print("-" * 72)
        print(f"服务可消费率: {guard_consumable}/{total}   基线严格解析率: {baseline_consumable}/{total}")

    # 语料为精选样例，服务应能处理除明确语义违规外的全部场景
    assert guard_consumable == total - 1
    # 服务必须显著优于基线
    assert guard_consumable > baseline_consumable
