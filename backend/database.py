# ============================================================
# Shared Center — 数据库
# ============================================================
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# 确保 data 目录存在
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表（含自动迁移）"""
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """自动处理新增字段，避免手动 ALTER TABLE"""
    import sqlalchemy
    with engine.connect() as conn:
        # webhooks.body (v1.x → v2.0)
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE webhooks ADD COLUMN body TEXT DEFAULT ''"))
            conn.commit()
        except Exception:
            pass  # 字段已存在
