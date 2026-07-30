# ============================================================
# Shared Center — Pydantic 请求/响应模型
# ============================================================
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ---- KV ----
class KvSetRequest(BaseModel):
    key: str
    value: str
    type: str = "string"
    source: str = ""
    retention_days: int = 180
    expire_seconds: Optional[int] = None


class KvBatchRequest(BaseModel):
    items: list[KvSetRequest]


class KvBatchDeleteRequest(BaseModel):
    keys: list[str]


class KvEntryOut(BaseModel):
    id: int
    key: str
    value: str
    type: str
    source: str
    updated_at: str
    expire_seconds: Optional[int]
    retention_days: int

    class Config:
        orm_mode = True


# ---- History ----
class KvHistoryOut(BaseModel):
    id: int
    key: str
    old_value: Optional[str]
    new_value: str
    source: str
    changed_at: str

    class Config:
        orm_mode = True


class HistoryListOut(BaseModel):
    items: list[KvHistoryOut]
    total: int


# ---- Device ----
class DeviceRegisterRequest(BaseModel):
    name: str
    type: str = "unknown"
    version: str = "1.0"
    hostname: str = ""
    mac: str = ""
    os: str = ""
    group: str = ""


class DeviceHeartbeatRequest(BaseModel):
    name: str
    online: bool = True
    cpu: Optional[int] = None
    memory: Optional[int] = None
    disk: Optional[int] = None
    uptime: str = ""
    ip: str = ""


class DeviceOut(BaseModel):
    id: str
    name: str
    hostname: str
    type: str
    group: str
    version: str
    ip: str
    mac: str
    os: str
    online: bool
    cpu: Optional[int]
    memory: Optional[int]
    disk: Optional[int]
    uptime: str
    notes: str
    last_heartbeat: str
    registered_at: str

    class Config:
        orm_mode = True


# ---- Dashboard ----
class DashboardStatsOut(BaseModel):
    total_devices: int
    online_devices: int
    total_services: int
    running_services: int
    network_status: str
    public_ip: str
    system_health: int


class DbStatusOut(BaseModel):
    file_size: str
    total_keys: int
    active_keys_24h: int
    history_count: int


class TimelineEvent(BaseModel):
    time: str
    icon: str
    title: str
    description: str
    color: str


# ---- Alert ----
class AlertRuleCreate(BaseModel):
    name: str
    description: str = ""
    trigger_key: str = ""
    condition: str = "eq"
    threshold: str = ""
    action: str = "notification"
    action_target: str = ""


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_key: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[str] = None
    action: Optional[str] = None
    action_target: Optional[str] = None
    enabled: Optional[bool] = None


class AlertRuleToggle(BaseModel):
    enabled: bool


class AlertRuleOut(BaseModel):
    id: int
    name: str
    description: str
    trigger_key: str
    condition: str
    threshold: str
    action: str
    action_target: str
    enabled: bool
    last_triggered: Optional[str]

    class Config:
        orm_mode = True


# ---- Webhook ----
class WebhookCreate(BaseModel):
    name: str
    url: str
    method: str = "POST"
    headers: dict = {}
    event_types: list[str] = []


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict] = None
    event_types: Optional[list[str]] = None
    enabled: Optional[bool] = None


class WebhookOut(BaseModel):
    id: int
    name: str
    url: str
    method: str
    headers: dict
    event_types: list[str]
    enabled: bool
    last_sent: Optional[str]
    fail_count: int

    class Config:
        orm_mode = True


# ---- System Log ----
class SystemLogOut(BaseModel):
    id: int
    level: str
    module: str
    message: str
    detail: Optional[str]
    created_at: str

    class Config:
        orm_mode = True


class SystemLogListOut(BaseModel):
    items: list[SystemLogOut]
    total: int


# ---- API Response ----
class ApiResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[dict] = None


# ---- Settings ----
class SystemConfigUpdate(BaseModel):
    cleanup_interval_hours: Optional[int] = None
    default_retention_days: Optional[int] = None
    heartbeat_timeout_seconds: Optional[int] = None
