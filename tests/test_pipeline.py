"""端到端流水线与 HTTP 接口测试。"""
from __future__ import annotations

SIMPLE_SCHEMA = {
    "gender": ["男", "女"],
    "age": "integer",
    "risk_level": ["低", "中", "高"],
}


def test_valid_passthrough(client):
    r = client.post(
        "/v1/clean",
        json={
            "raw_text": '{"gender": "男", "age": 30, "risk_level": "低"}',
            "schema": SIMPLE_SCHEMA,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "valid"
    assert body["confidence"]["score"] == 1.0
    assert body["audit_trail"] == []
    assert body["diff"] == []
    assert body["raw_input"] == '{"gender": "男", "age": 30, "risk_level": "低"}'


def test_fence_and_coercion_repaired(client):
    raw = '好的，结果如下：```json\n{"gender":"女","age":"28","risk_level":"中"}\n```'
    r = client.post("/v1/clean", json={"raw_text": raw, "schema": SIMPLE_SCHEMA})
    body = r.json()
    assert body["status"] == "repaired"
    assert body["result"] == {"gender": "女", "age": 28, "risk_level": "中"}
    assert body["confidence"]["score"] < 1.0
    actions = [e["action"] for e in body["audit_trail"]]
    assert "strip_fence" in actions
    assert "type_coercion" in actions


def test_negative_age_invalid_with_range_schema(client):
    schema = {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "minimum": 0},
        },
        "required": ["age"],
    }
    r = client.post("/v1/clean", json={"raw_text": '{"age": -5}', "schema": schema})
    body = r.json()
    assert body["status"] == "invalid"
    assert body["violations"][0]["keyword"] == "minimum"
    assert body["violations"][0]["path"] == "$.age"


def test_enum_violation_invalid(client):
    r = client.post(
        "/v1/clean",
        json={"raw_text": '{"gender": "未知", "age": 30, "risk_level": "低"}',
              "schema": SIMPLE_SCHEMA},
    )
    body = r.json()
    assert body["status"] == "invalid"
    assert any(v["keyword"] == "enum" for v in body["violations"])


def test_missing_required_invalid(client):
    r = client.post(
        "/v1/clean", json={"raw_text": '{"gender": "男"}', "schema": SIMPLE_SCHEMA}
    )
    assert r.json()["status"] == "invalid"


def test_unparseable_input(client):
    r = client.post("/v1/clean", json={"raw_text": "没有任何JSON内容", "schema": SIMPLE_SCHEMA})
    body = r.json()
    assert body["status"] == "invalid"
    assert body["violations"][0]["keyword"] == "parse_error"


def test_no_schema_legality_only(client):
    r = client.post("/v1/clean", json={"raw_text": '```json\n{"a": 1}\n```'})
    body = r.json()
    assert body["status"] == "repaired"
    assert body["result"] == {"a": 1}


def test_validate_endpoint(client):
    r = client.post(
        "/v1/validate",
        json={"data": {"age": -1}, "schema": {"properties": {"age": {"minimum": 0}}}},
    )
    body = r.json()
    assert body["status"] == "invalid"


def test_validate_endpoint_ok(client):
    r = client.post(
        "/v1/validate",
        json={"data": {"a": 1}, "schema": {"properties": {"a": {"type": "integer"}}}},
    )
    assert r.json()["status"] == "valid"


def test_repair_endpoint_skips_schema_violation(client):
    # 修复接口：即使 age 为负也只做结构修复，不报语义违规
    schema = {"type": "object", "properties": {"age": {"type": "integer", "minimum": 0}}}
    r = client.post(
        "/v1/repair", json={"raw_text": '{"age": -1}', "schema": schema}
    )
    body = r.json()
    assert body["status"] == "valid"
    assert body["violations"] == []


def test_batch(client):
    r = client.post(
        "/v1/clean/batch",
        json={
            "items": [
                {"raw_text": '{"a": 1}'},
                {"raw_text": "废话"},
            ]
        },
    )
    body = r.json()
    assert body["count"] == 2
    assert body["results"][0]["status"] == "valid"
    assert body["results"][1]["status"] == "invalid"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"guardian_requests_total" in r.content


def test_body_too_large(client):
    big = "x" * (3 * 1024 * 1024)
    r = client.post("/v1/clean", json={"raw_text": big})
    assert r.status_code == 413
