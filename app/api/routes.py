"""HTTP 接口定义。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.schemas.io import (
    BatchCleanRequest,
    CleanRequest,
    CleanResponse,
    ValidateRequest,
)

router = APIRouter(prefix="/v1")


@router.post("/clean", response_model=CleanResponse)
def clean(req: CleanRequest, request: Request) -> dict:
    return request.app.state.pipeline.clean(req.raw_text, req.schema, req.policy)


@router.post("/repair", response_model=CleanResponse)
def repair(req: CleanRequest, request: Request) -> dict:
    return request.app.state.pipeline.clean(
        req.raw_text, req.schema, req.policy, validate_schema=False
    )


@router.post("/validate", response_model=CleanResponse)
def validate(req: ValidateRequest, request: Request) -> dict:
    return request.app.state.pipeline.validate(req.data, req.schema_)


@router.post("/clean/batch")
def clean_batch(req: BatchCleanRequest, request: Request) -> dict:
    if len(req.items) > settings.max_batch_items:
        raise HTTPException(
            status_code=400,
            detail=f"批量条数超过上限 {settings.max_batch_items}",
        )
    pipeline = request.app.state.pipeline
    results = [
        pipeline.clean(item.raw_text, item.schema, item.policy) for item in req.items
    ]
    return {"count": len(results), "results": results}


@router.get("/traces/{trace_id}", response_model=CleanResponse)
def get_trace(trace_id: str, request: Request) -> dict:
    store = request.app.state.store
    if store is None:
        raise HTTPException(status_code=404, detail="溯源存储未启用")
    record = store.get(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="trace不存在")
    return record
