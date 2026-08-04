# ============================================================
# 测试全局配置 — 必须先于一切业务模块执行:
# 1. 把数据库切换到临时测试库(绝不碰真实数据)
# 2. 把 backend/ 加入模块搜索路径
# ============================================================
import os
import sys

# ⚠️ 必须在 import database/main 之前设置!否则 engine 会连到真实数据库
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".test_shared.db"
)

# 确保 backend/ 在模块搜索路径(pytest 默认只加 tests/ 所在目录)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app          # 此时才 import,保证读到测试库
from database import SessionLocal, Base, engine


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空所有表,保证测试互相独立、可重复运行"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    """API 测试客户端。

    注意:TestClient 会触发 lifespan → 建表 + 创建默认 admin/admin123
    用户 + 启动定时任务(定时任务操作的是临时库,不影响真实数据)。
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """直接操作测试数据库的会话(用于准备数据/断言库内状态)"""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def admin_headers(client):
    """管理员会话 Token(login 是公开路径,无需先鉴权)"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
