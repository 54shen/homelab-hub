# ============================================================
# Shared Center — Home Assistant 状态接收 API
#
# 架构：一个统一的 "HA" 设备，所有 HA 实体作为其 KV 变量
#   例如：HA.显示器开关 / HA.空调温度 / HA.二氧化碳浓度 ...
#   每个状态变化都会刷新 HA 设备的心跳，确保设备保持在线
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from typing import Optional

from database import get_db
from models import KvEntry, KvHistory, Device
from schemas import ApiResponse
from websocket_manager import broadcast
from auth import auth_write

router = APIRouter(prefix="/api/ha", tags=["Home Assistant"])

# ══════════════════════════════════════════════════════════════
# 配置：统一 HA 设备名（可改，改完后所有变量前缀跟着变）
# ══════════════════════════════════════════════════════════════
HA_DEVICE_NAME = "HA"
HA_DEVICE_TYPE = "ha"
HA_DEVICE_GROUP = "智能家居"


# ---- 请求模型 ----

class HAStateReport(BaseModel):
    """HA 单个实体状态上报

    HA 自动化传参示例：
      entity_id: "{{ trigger.entity_id }}"
      state: "{{ trigger.to_state.state }}"
      friendly_name: "{{ state_attr(trigger.entity_id, 'friendly_name') }}"
    """
    entity_id: str              # switch.xianshiqi 或 sensor.co2
    state: str                  # on / off / 23.5 / 未知
    friendly_name: str = ""     # 显示器开关 / CO2浓度（为空则自动推导）
    unit: str = ""              # °C / % / W / km …
    source: str = "homeassistant"

    @validator("entity_id")
    @classmethod
    def entity_id_required(cls, v: str) -> str:
        if not v or "." not in v:
            raise ValueError("entity_id 格式错误，应为 domain.entity 形式")
        return v


class HABatchStateReport(BaseModel):
    """批量上报"""
    states: list[HAStateReport]


# ---- 工具函数 ----

def _resolve_name(entity_id: str, friendly_name: str) -> str:
    """从 entity_id+friendly_name 推导变量名（去掉 domain 前缀）

    switch.xianshiqi + "显示器开关" → "显示器开关"
    sensor.co2_sensor   + ""        → "co2.sensor"
    """
    if friendly_name.strip():
        return friendly_name.strip()

    # fallback：取 entity_id 的实体部分
    parts = entity_id.split(".", 1)
    name = parts[1] if len(parts) > 1 else parts[0]
    return name.replace("_", ".")


def _guess_type(state: str) -> str:
    """根据状态值推测数据类型"""
    s = state.strip()
    # 布尔
    if s.lower() in ("on", "off", "true", "false", "open", "closed",
                     "locked", "unlocked", "home", "not_home",
                     "playing", "paused", "idle", "active"):
        return "string"
    # 整数
    try:
        int(s)
        return "int"
    except ValueError:
        pass
    # 浮点
    try:
        float(s)
        return "float"
    except ValueError:
        pass
    return "string"


def _ensure_ha_device(db: Session) -> Device:
    """确保 HA 统一设备存在，每次调用刷心跳 + server_received_at"""
    import hashlib
    device_id = hashlib.md5(f"HA:{HA_DEVICE_NAME}".encode()).hexdigest()[:12]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dev = db.query(Device).filter(Device.id == device_id).first()
    if dev:
        dev.online = True
        dev.last_heartbeat = now_str
    else:
        dev = Device(
            id=device_id,
            name=HA_DEVICE_NAME,
            type=HA_DEVICE_TYPE,
            version="—",
            group=HA_DEVICE_GROUP,
            online=True,
            last_heartbeat=now_str,
            registered_at=now_str
        )
        db.add(dev)

    # 刷新服务器专用 server_received_at key（HA 状态上报 = 服务器接收上报时间）
    from services.device_activity import write_report_time_silent
    write_report_time_silent(db, dev, now_str)
    return dev


def _write_kv(db: Session, key: str, value: str, source: str, typ: str):
    """写入 KV 变量 → 返回 (now_str, changed, old_value)

    值无变化时完全静默：不更新 entry、不触发告警。
    """
    # autoflush=False 时,先 flush 让同一会话内刚写入的 key 对后续查询可见
    # (否则批量上报中重复 entity 会走"新建"分支 → UNIQUE 冲突)
    db.flush()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()

    if entry:
        old = entry.value
        # ---- 值没变 → 什么都不做 ----
        if old == value:
            return now_str, False, old

        # ---- 值变更 → 更新 entry + 触发告警 ----
        from services.alerts import check_kv_change
        print(f"[HA] 值变更: key={key} {old} -> {value}，触发告警检查")
        check_kv_change(key, old, value)

        entry.value = value
        entry.type = typ
        entry.source = source
        entry.updated_at = now_str
        # 记录历史
        db.add(KvHistory(
            key=key, old_value=old, new_value=value,
            source=source, retention_days=entry.retention_days,
            changed_at=now_str
        ))
        return now_str, True, old

    # ---- 新 key → 创建 entry ----
    entry = KvEntry(
        key=key,
        value=value,
        type=typ,
        source=source,
        retention_days=180,
        updated_at=now_str
    )
    db.add(entry)
    # 记录历史（新建 key）
    db.add(KvHistory(
        key=key, old_value=None, new_value=value,
        source=source, retention_days=180,
        changed_at=now_str
    ))
    return now_str, True, None


# ---- API 端点 ----

@router.post("/state", response_model=ApiResponse)
async def ha_state_report(req: HAStateReport,
                          db: Session = Depends(get_db),
                          token=Depends(auth_write)):
    """接收 HA 单个实体状态 → 写入 HA.xxx KV 变量

    每次调用同时刷新 "HA" 设备心跳，保持设备在线。
    """
    var_name = _resolve_name(req.entity_id, req.friendly_name)
    kv_key = f"{HA_DEVICE_NAME}.{var_name}"
    typ = _guess_type(req.state)

    now_str, changed, old_value = _write_kv(db, kv_key, req.state, req.source, typ)
    _ensure_ha_device(db)
    db.commit()

    if changed:
        await broadcast("kv.changed", {"key": kv_key, "value": req.state, "old_value": old_value, "source": req.source, "changed_at": now_str})

    unit_str = f" {req.unit}" if req.unit else ""
    return ApiResponse(success=True, message=f"{kv_key} = {req.state}{unit_str}")


@router.post("/states", response_model=ApiResponse)
async def ha_batch_states(req: HABatchStateReport,
                          db: Session = Depends(get_db),
                          token=Depends(auth_write)):
    """批量接收 HA 实体状态"""
    changed = 0
    for item in req.states:
        var_name = _resolve_name(item.entity_id, item.friendly_name)
        kv_key = f"{HA_DEVICE_NAME}.{var_name}"
        typ = _guess_type(item.state)
        _, did_change, _old = _write_kv(db, kv_key, item.state, item.source, typ)
        if did_change:
            changed += 1

    _ensure_ha_device(db)
    db.commit()

    # 只有真正有变更才广播
    if changed:
        await broadcast("kv.refresh", {"count": changed})
    return ApiResponse(success=True, message=f"HA 已同步 {changed} 个变更（{len(req.states)} 个状态）")


# ══════════════════════════════════════════════════════════════
# HA 端配置
# ══════════════════════════════════════════════════════════════
#
# 1. configuration.yaml — 全局 REST 命令：
#
#     rest_command:
#       ha_to_hub:
#         url: "http://192.168.5.232:8000/api/ha/state"
#         method: POST
#         headers:
#           Authorization: "Bearer sk-f6ac12cf94f742f8bcea76b609da6786"
#           Content-Type: "application/json"
#         payload: >
#           {
#             "entity_id": "{{ entity_id }}",
#             "state": "{{ state }}",
#             "friendly_name": "{{ friendly_name }}",
#             "unit": "{{ unit }}"
#           }
#
#
# 2. HA UI → 自动化 → 新建 → YAML 模式：
#
#     alias: 所有实体同步到中枢
#     triggers:
#       - trigger: state
#         entity_id:
#           - switch.xianshiqi
#           - sensor.co2
#           - sensor.aqi
#           - switch.jinghuaqi
#           - climate.kongtiao
#           - sensor.diantan_wendu
#           - device_tracker.nio
#           # ... 把你需要同步的实体都列在这
#     actions:
#       - action: rest_command.ha_to_hub
#         data:
#           entity_id: "{{ trigger.entity_id }}"
#           state: "{{ trigger.to_state.state }}"
#           friendly_name: "{{ state_attr(trigger.entity_id, 'friendly_name') }}"
#           unit: "{{ state_attr(trigger.entity_id, 'unit_of_measurement') or '' }}"
#     mode: parallel
#
#
# 3. 重载 HA 配置 → 触发一下设备状态 → 中枢前端就能看到：
#    设备列表 → HA（智能家居分组）→ 点进去查看所有变量
#
# ============================================================
# 快速测试 curl：
#
#   curl -X POST http://localhost:8000/api/ha/state \
#     -H "Authorization: Bearer sk-f6ac12cf94f742f8bcea76b609da6786" \
#     -H "Content-Type: application/json" \
#     -d '{"entity_id":"switch.test","state":"on","friendly_name":"测试开关"}'
#
#   curl -X POST http://localhost:8000/api/ha/state \
#     -H "Authorization: Bearer sk-f6ac12cf94f742f8bcea76b609da6786" \
#     -H "Content-Type: application/json" \
#     -d '{"entity_id":"sensor.test","state":"23.5","friendly_name":"测试温度","unit":"°C"}'
# ══════════════════════════════════════════════════════════════
