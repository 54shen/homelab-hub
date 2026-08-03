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
            pass
        # devices.heartbeat_timeout (v2.1)
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE devices ADD COLUMN heartbeat_timeout INTEGER DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        # ui_settings (v2.2)
        try:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS ui_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT DEFAULT ''
                )
            """))
            conn.commit()
        except Exception:
            pass
        # alert_rules.body (v2.3) — 规则级自定义 Webhook Body 模板
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE alert_rules ADD COLUMN body TEXT"))
            conn.commit()
        except Exception:
            pass
        # webhooks.body_extra (v2.4) — Webhook 默认 Body+ 内容
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE webhooks ADD COLUMN body_extra TEXT DEFAULT ''"))
            conn.commit()
        except Exception:
            pass
        # devices.volume (v2.5) — 系统音量 0-100
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE devices ADD COLUMN volume INTEGER"))
            conn.commit()
        except Exception:
            pass
        # users.totp_secret / totp_enabled (v2.10) — 登录二次验证(TOTP)
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN totp_secret TEXT DEFAULT ''"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN totp_enabled INTEGER DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        # devices.muted (v2.6) — 是否静音
        try:
            conn.execute(sqlalchemy.text("ALTER TABLE devices ADD COLUMN muted BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        # kv_history (v2.7) — KV 值变更历史记录表
        try:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS kv_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    retention_days INTEGER DEFAULT 180,
                    changed_at TEXT DEFAULT (datetime('now','localtime'))
                )
            """))
            conn.commit()
        except Exception:
            pass
        # field_mappings (v2.9) — 字段英文→中文映射表
        try:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS field_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_key TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL
                )
            """))
            conn.commit()
        except Exception:
            pass
