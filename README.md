# LLM Output Guardian

把大模型"不稳定、不规范、不可直接消费"的输出，转换为**稳定、可验证、可追踪**的结构化结果。

一个独立部署的 FastAPI 微服务，内置三阶段处理流水线：

```
原始LLM输出 ──► ① 语法清洗 ──► ② 结构修复 ──► ③ 语义校验 ──► 稳定结构化结果
                 SyntaxCleaner   StructureRepairer  SemanticValidator
                        └──────── AuditCenter 可信度与溯源 ────────┘
```

## 特性

**① 语法清洗（纯文本层，不改语义）**
- Markdown 代码围栏剥离（含流式截断导致的未闭合围栏）
- 前后废话 / 思考链剔除：字符串感知的括号配平定位，多候选取最优
- XML 标签包裹提取（`<result>`、`<json>` 等）
- BOM / 零宽字符 / 全角标点规范化

**② 结构修复（规则驱动，逐条可审计）**
- 宽容解析：单引号、未引用 key、尾逗号、注释、Python 字面量、NaN
- 截断修复：未闭合字符串/对象/数组栈式补全，半截元素按安全边界丢弃
- 类型转换：按 schema 目标类型安全转换（`"18"→18`、`"是"→true`），无法转换不硬转
- 字段操作：缺失补全（defaults）、未知字段删除/报错、重命名（rename_map）
- 数组/对象互转：标量包裹、单元素解包、kv 列表与对象互转
- 枚举修正：归一化 → 别名映射 → rapidfuzz 模糊匹配（阈值可配，不猜值）
- null 处理：keep / default / error 三种策略

**③ 语义校验**
- 无 schema：JSON 合法性检查（NaN/Infinity 等不可消费值）
- 有 schema：标准 JSON Schema（类型、枚举、数值范围、正则、必填、嵌套）
- 业务简写 schema 自动编译：`{"age": "integer", "gender": ["男","女"]}` → 标准 JSON Schema

**置信度与溯源（不偷偷修改）**
- 每次修改产生不可变 `AuditEvent`：before / after / reason / method / confidence_delta
- 字段级 + 全局置信度，罚分外置 [scoring.yaml](app/audit/scoring.yaml) 可调
- RFC6902 风格 Diff 可回放（hypothesis 模糊测试验证不变量）
- 原始输入原样返回；状态裁决 `valid / repaired / invalid`

**工程化**
- 确定性规则优先，LLM 兜底可选（OpenAI 兼容协议，默认关闭 = 完全离线、100% 可复现）
- SQLite 溯源存储（可插拔），按 trace_id 查询历史
- structlog 结构化日志、Prometheus 指标、请求体/深度/批量上限
- Docker 一键部署、GitHub Actions CI、90+ 测试用例

## 快速开始

### Docker（推荐）

```bash
docker compose up --build
# 服务运行在 http://localhost:8000，交互式文档 http://localhost:8000/docs
```

### 本地运行

```bash
pip install -e ".[dev]"
uvicorn app.main:app --port 8000
```

## 使用示例

```bash
curl -X POST http://localhost:8000/v1/clean -H "Content-Type: application/json" -d '{
  "raw_text": "好的，结果如下：```json\n{\"gender\":\"女\",\"age\":\"28\",\"risk_level\":\"中\"}\n```",
  "schema": {"gender": ["男", "女"], "age": "integer", "risk_level": ["低", "中", "高"]},
  "policy": {"unknown_fields": "drop"}
}'
```

响应（完整流水线自动完成围栏剥离 + 类型转换）：

```json
{
  "status": "repaired",
  "result": {"gender": "女", "age": 28, "risk_level": "中"},
  "confidence": {"score": 0.9125, "field_scores": {"age": 0.9, "gender": 1.0, "risk_level": 1.0}, "llm_capped": false},
  "audit_trail": [
    {"action": "strip_fence", "reason": "剥离Markdown代码围栏", ...},
    {"action": "type_coercion", "path": "age", "before": "28", "after": 28, "reason": "schema要求 integer，原值可安全转换", ...}
  ],
  "diff": [{"op": "replace", "path": "/age", "old": "28", "new": 28}],
  "trace_id": "..."
}
```

数值范围约束（age 不允许负数）使用标准 JSON Schema 直传：

```json
{
  "raw_text": "{\"age\": -5}",
  "schema": {
    "type": "object",
    "properties": {"age": {"type": "integer", "minimum": 0}},
    "required": ["age"]
  }
}
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/clean` | 完整流水线：清洗 + 修复 + schema 校验 |
| POST | `/v1/repair` | 清洗 + 修复，不做 schema 强校验 |
| POST | `/v1/validate` | 仅校验（输入已是 JSON 值） |
| POST | `/v1/clean/batch` | 批量处理（默认上限 50 条） |
| GET | `/v1/traces/{trace_id}` | 查询历史溯源记录 |
| GET | `/health` / `/metrics` | 健康检查 / Prometheus 指标 |

完整请求示例见 [examples/sample_requests.http](examples/sample_requests.http)。

## 策略配置（policy）

```jsonc
{
  "strictness": "lenient",           // strict | lenient
  "unknown_fields": "drop",          // drop | keep | error
  "null_policy": "default",          // keep | default | error
  "rename_map": {"sex": "gender"},   // 字段重命名
  "defaults": {"risk_level": "低"},  // 缺失字段默认值，支持 "user.name" 点路径
  "enum_aliases": {"gender": {"male": "男"}},
  "fuzzy_enum_threshold": 0.85,      // 枚举模糊匹配阈值，低于则不猜值
  "llm_fallback": false              // 规则失败后是否允许 LLM 兜底
}
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GUARDIAN_PERSIST` | `0` | 是否开启 SQLite 溯源落库 |
| `GUARDIAN_DB_PATH` | `data/traces.db` | 数据库路径 |
| `GUARDIAN_MAX_BODY_BYTES` | `2097152` | 请求体大小上限 |
| `GUARDIAN_MAX_DEPTH` | `32` | JSON 递归深度上限 |
| `GUARDIAN_MAX_BATCH_ITEMS` | `50` | 批量接口条数上限 |
| `GUARDIAN_LLM_BASE_URL` | 空 | LLM 兜底地址（不配置 = 离线） |
| `GUARDIAN_LLM_API_KEY` | 空 | LLM 密钥 |
| `GUARDIAN_LLM_MODEL` | 空 | LLM 模型名 |

## 测试

```bash
pytest                # 90+ 用例，含 hypothesis Diff 回放模糊测试
pytest tests/test_corpus_repair_rate.py -s   # 输出修复率基线对比表
```

真实脏输出语料（12 场景）服务可消费率 **91.7%**（11/12），基线 `json.loads` 仅 **58.3%**（7/12）；唯一 invalid 场景为数值范围违规（age=-5），属正确拒绝。

## 架构

详细设计（架构图、时序图、置信度罚分表）见 [docs/design.md](docs/design.md)。

## License

[MIT](LICENSE)
