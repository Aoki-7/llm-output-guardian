"""全局运行配置，全部通过环境变量注入，提供合理默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: str = "1") -> bool:
    return os.getenv(name, default) == "1"


@dataclass(frozen=True)
class Settings:
    service_name: str = "llm-output-guardian"
    # 请求体大小上限（默认 2MB）
    max_body_bytes: int = int(os.getenv("GUARDIAN_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
    # JSON 嵌套递归深度上限
    max_depth: int = int(os.getenv("GUARDIAN_MAX_DEPTH", "32"))
    # 批量接口最大条数
    max_batch_items: int = int(os.getenv("GUARDIAN_MAX_BATCH_ITEMS", "50"))
    # 溯源落库
    persist: bool = _env_bool("GUARDIAN_PERSIST")
    db_path: str = os.getenv("GUARDIAN_DB_PATH", "data/traces.db")
    # LLM 兜底（默认不配置 = 完全离线）
    llm_base_url: str = os.getenv("GUARDIAN_LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("GUARDIAN_LLM_API_KEY", "")
    llm_model: str = os.getenv("GUARDIAN_LLM_MODEL", "")
    llm_timeout: float = float(os.getenv("GUARDIAN_LLM_TIMEOUT", "30"))


settings = Settings()
