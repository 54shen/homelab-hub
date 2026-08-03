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


# ---- Device ----
class DeviceRegisterRequest(BaseModel):
    name: str
    type: str = "unknown"
    version: str = "1.0"
    hostname: str = ""
    mac: str = ""
    os: str = ""
    group: str = ""
    heartbeat_timeout: int = 0  # 0=全局默认，>0=自定义秒数


class DeviceHeartbeatRequest(BaseModel):
    name: str
    online: bool = True
    cpu: Optional[int] = None
    memory: Optional[int] = None
    disk: Optional[int] = None
    volume: Optional[int] = None  # 系统音量 0-100, -1=静音
    uptime: str = ""
    ip: str = ""
    source: str = "agent"  # 数据来源标识，Agent 可自定义
    heartbeat_timeout: int = 0  # 可在心跳中动态更新超时


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
    volume: Optional[int]
    muted: bool
    uptime: str
    notes: str
    heartbeat_timeout: int
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
    total_keys: int
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
    body: str = ""  # 自定义 Webhook Body 模板（覆盖 Webhook 默认模板）


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_key: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[str] = None
    action: Optional[str] = None
    action_target: Optional[str] = None
    enabled: Optional[bool] = None
    body: Optional[str] = None  # 自定义 Webhook Body 模板


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
    body: Optional[str]

    class Config:
        orm_mode = True


# ---- Webhook ----
class WebhookCreate(BaseModel):
    name: str
    url: str
    method: str = "POST"
    headers: dict = {}
    body: str = ""       # 信封（强制结构）
    body_extra: str = "" # 默认内容（规则未填 body 时回退）
    event_types: list[str] = []


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict] = None
    body: Optional[str] = None
    body_extra: Optional[str] = None
    event_types: Optional[list[str]] = None
    enabled: Optional[bool] = None


class WebhookOut(BaseModel):
    id: int
    name: str
    url: str
    method: str
    headers: dict
    body: str
    body_extra: str
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


# ---- KvHistory ----
class KvHistoryOut(BaseModel):
    id: int
    key: str
    old_value: Optional[str]  # None = 新建 key
    new_value: str
    source: str
    retention_days: int
    changed_at: str

    class Config:
        orm_mode = True


class KvHistoryListOut(BaseModel):
    items: list[KvHistoryOut]
    total: int


# ---- 历史记录统计/分析（融合 kv-history-viewer） ----
class HistoryKeyInfo(BaseModel):
    key: str
    count: int
    is_numeric: bool
    plot_kind: str = ""  # '' / 'number' / 'duration' / 'timestamp' 可绘图格式
    latest_value: Optional[str] = None
    latest_changed_at: Optional[str] = None
    sources: list[str] = []


class HistorySource(BaseModel):
    source: Optional[str] = None
    count: int


class TrendPoint(BaseModel):
    changed_at: str
    value: float
    raw: Optional[str] = None  # 原始值(时长/时间戳等非纯数值格式)用于展示


class TrendSeries(BaseModel):
    key: str
    points: list[TrendPoint]
    count: int
    kind: str = ""  # '' / 'number' / 'duration' / 'timestamp'


class HistoryStats(BaseModel):
    total_records: int
    max_changed_at: Optional[str] = None
    start_24h: str
    per_source: list[HistorySource]
    per_hour: list[dict]


# ---- Field Mapping ----
class FieldMappingCreate(BaseModel):
    field_key: str
    display_name: str


class FieldMappingUpdate(BaseModel):
    field_key: Optional[str] = None
    display_name: Optional[str] = None


class FieldMappingOut(BaseModel):
    id: int
    field_key: str
    display_name: str

    class Config:
        orm_mode = True


# ---- Settings ----
class SystemConfigUpdate(BaseModel):
    cleanup_interval_hours: Optional[int] = None
    default_retention_days: Optional[int] = None
    heartbeat_timeout_seconds: Optional[int] = None
