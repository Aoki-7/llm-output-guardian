"""测试全局环境：默认关闭溯源落库，避免在工作区产生数据文件。"""
import os

os.environ["GUARDIAN_PERSIST"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
