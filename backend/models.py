# ============================================================
# Shared Center — ORM 模型
# ============================================================
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from database import Base


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---- KV 数据表 ----
class KvEntry(Base):
    __tablename__ = "kv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    type = Column(String(32), default="string")
    source = Column(String(128), default="")
    updated_at = Column(String(32), default=_now)
    expire_seconds = Column(Integer, nullable=True)
    retention_days = Column(Integer, default=180)


# ---- 历史记录表 ----
class KvHistory(Base):
    __tablename__ = "kv_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, default="")
    source = Column(String(128), default="")
    changed_at = Column(String(32), default=_now)


# ---- 设备表 ----
class Device(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    hostname = Column(String(128), default="")
    type = Column(String(32), default="unknown")
    group = Column(String(64), default="默认")
    version = Column(String(32), default="1.0")
    ip = Column(String(45), default="")
    mac = Column(String(32), default="")
    os = Column(String(64), default="")
    online = Column(Boolean, default=False)
    cpu = Column(Integer, nullable=True)
    memory = Column(Integer, nullable=True)
    disk = Column(Integer, nullable=True)
    uptime = Column(String(32), default="")
    notes = Column(String(512), default="")
    last_heartbeat = Column(String(32), default=_now)
    registered_at = Column(String(32), default=_now)


# ---- Token 表 ----
class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), default="")
    name = Column(String(128), unique=True, nullable=False)
    token = Column(String(256), nullable=False)
    permission = Column(String(32), default="read")  # read / write / admin
    created_at = Column(String(32), default=_now)


# ---- 登录会话表 ----
class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(Integer, nullable=False)
    username = Column(String(64), default="")
    token_name = Column(String(128), default="")
    permission = Column(String(32), default="")
    ip = Column(String(45), default="")
    user_agent = Column(String(256), default="")
    created_at = Column(String(32), default=_now)
    last_active = Column(String(32), default=_now)


# ---- 告警规则表 ----
class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), default="")
    trigger_key = Column(String(256), nullable=False)
    condition = Column(String(32), default="eq")
    threshold = Column(String(128), default="")
    action = Column(String(32), default="notification")
    action_target = Column(String(256), default="")
    enabled = Column(Boolean, default=True)
    last_triggered = Column(String(32), nullable=True)


# ---- Webhook 配置表 ----
class WebhookConfig(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    url = Column(String(512), nullable=False)
    method = Column(String(8), default="POST")
    headers = Column(JSON, default=dict)
    event_types = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    last_sent = Column(String(32), nullable=True)
    fail_count = Column(Integer, default=0)


# ---- 系统日志表 ----
class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(16), default="info")  # debug/info/warn/error
    module = Column(String(64), default="system")
    message = Column(String(512), default="")
    detail = Column(Text, nullable=True)
    created_at = Column(String(32), default=_now)
