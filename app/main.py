"""FastAPI 应用入口：中间件、依赖装配、路由注册。"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.api.routes import router
from app.core.config import settings
from app.core.pipeline import GuardianPipeline
from app.llm.base import build_llm_client
from app.persistence.sqlite_store import SQLiteTraceStore

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ]
)
logger = structlog.get_logger()

REQUEST_COUNT = Counter(
    "guardian_requests_total", "总请求数", ["endpoint", "method", "status"]
)
REQUEST_LATENCY = Histogram(
    "guardian_request_duration_seconds", "请求耗时(秒)", ["endpoint"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteTraceStore(settings.db_path) if settings.persist else None
    llm_client = build_llm_client(settings)
    app.state.store = store
    app.state.pipeline = GuardianPipeline(store=store, llm_client=llm_client)
    logger.info("startup", persist=settings.persist, llm_enabled=llm_client is not None)
    yield


app = FastAPI(
    title="LLM Output Guardian",
    description="把不规范的大模型输出转换为稳定、可验证、可追踪的结构化结果",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.middleware("http")
async def observe_and_limit(request: Request, call_next):
    # 请求体大小限制
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_body_bytes:
        return JSONResponse(status_code=413, content={"detail": "请求体超过大小限制"})

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error", path=request.url.path)
        raise
    elapsed = time.perf_counter() - start

    REQUEST_COUNT.labels(
        endpoint=request.url.path, method=request.method, status=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(elapsed)
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
