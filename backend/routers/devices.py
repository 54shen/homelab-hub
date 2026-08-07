# ============================================================
# Shared Center — 设备管理 API
# ============================================================
from datetime import datetime
import sqlalchemy
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Device, KvEntry, KvHistory
from schemas import (
    DeviceRegisterRequest, DeviceHeartbeatRequest,
    DeviceOut, KvEntryOut, ApiResponse
)
from websocket_manager import broadcast
from auth import auth_write
from config import DEFAULT_HEARTBEAT_TIMEOUT
from constants import CLIPBOARD_DEVICE_NAME, is_clipboard_device
from services.device_activity import device_prefixes, mark_device_active, write_report_time_silent

router = APIRouter(prefix="/api", tags=["设备管理"])


def _gen_device_id(name: str, typ: str) -> str:
    import hashlib
    raw = f"{name}:{typ}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _sync_timeout_kv(db: Session, key: str, timeout: int):
    """同步心跳超时 KV 变量（不存在则创建，存在则更新）"""
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if entry:
        if entry.value != str(timeout):
            entry.value = str(timeout)
            entry.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        db.add(KvEntry(
            key=key,
            value=str(timeout),
            type="int",
            source="system",
            retention_days=3650
        ))


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    # 隐藏内置设备（剪切板等），按 name 过滤兜住同名抢注场景
    return db.query(Device).filter(Device.name != CLIPBOARD_DEVICE_NAME).order_by(
        Device.online.desc(), Device.last_heartbeat.desc()
    ).all()


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.id == device_id).first()
    if not d or is_clipboard_device(device_id=device_id):
        from fastapi import HTTPException
        raise HTTPException(404, "设备不存在")
    return d


@router.get("/devices/{device_id}/variables", response_model=list[KvEntryOut])
def get_device_variables(device_id: str, db: Session = Depends(get_db)):
    if is_clipboard_device(device_id=device_id):
        from fastapi import HTTPException
        raise HTTPException(404, "设备不存在")
    d = db.query(Device).filter(Device.id == device_id).first()
    if not d:
        return []
    # 兼容两种前缀:原始名称(注册/心跳写入用,如 "监控-1.xxx")和
    # 转换名称(连字符/空格→点,如 "监控.1.xxx"),取并集避免漏变量
    # (与 services/device_activity.py 的 device_prefixes 同源)
    prefixes = device_prefixes(d)
    return db.query(KvEntry).filter(
        sqlalchemy.or_(*[KvEntry.key.like(f"{p}%") for p in prefixes])
    ).all()


@router.post("/device/register", response_model=ApiResponse)
async def register_device(req: DeviceRegisterRequest, db: Session = Depends(get_db), token=Depends(auth_write)):
    device_id = _gen_device_id(req.name, req.type)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 心跳超时 KV key
    timeout_kv_key = f"{req.name}.心跳超时"

    existing = db.query(Device).filter(Device.id == device_id).first()
    if existing:
        existing.name = req.name
        existing.hostname = req.hostname or existing.hostname
        existing.type = req.type
        existing.version = req.version
        existing.mac = req.mac or existing.mac
        existing.os = req.os or existing.os
        existing.group = req.group or existing.group
        existing.last_heartbeat = now_str
        # 仅在 agent 明确传入 >0 时更新超时
        if req.heartbeat_timeout > 0:
            existing.heartbeat_timeout = req.heartbeat_timeout
        # 同步 KV（首次或 agent 传入时）
        _sync_timeout_kv(db, timeout_kv_key, existing.heartbeat_timeout or DEFAULT_HEARTBEAT_TIMEOUT)
    else:
        timeout = req.heartbeat_timeout if req.heartbeat_timeout > 0 else DEFAULT_HEARTBEAT_TIMEOUT
        device = Device(
            id=device_id,
            name=req.name,
            hostname=req.hostname,
            type=req.type,
            version=req.version,
            mac=req.mac,
            os=req.os,
            group=req.group,
            online=False,
            heartbeat_timeout=timeout,
            last_heartbeat=now_str,
            registered_at=now_str
        )
        db.add(device)
        # 首次注册：创建 KV
        _sync_timeout_kv(db, timeout_kv_key, timeout)

    # 服务器专用"server_received_at" key（注册即存在，便于前端展示）
    write_report_time_silent(db, existing or device, now_str)

    db.commit()
    await broadcast("device.registered", {"name": req.name, "type": req.type, "group": req.group or "默认"})
    return ApiResponse(success=True, message="OK", data={"device_id": device_id})


@router.post("/device/heartbeat", response_model=ApiResponse)
async def device_heartbeat(req: DeviceHeartbeatRequest, db: Session = Depends(get_db), token=Depends(auth_write)):
    # 尝试按名称匹配
    device = db.query(Device).filter(Device.name == req.name).first()
    if not device:
        # 自动注册
        device_id = _gen_device_id(req.name, "unknown")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device = Device(
            id=device_id,
            name=req.name,
            online=False,
            last_heartbeat=now_str,
            registered_at=now_str
        )
        db.add(device)
        db.flush()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 统一刷新活跃度：online 状态 + last_heartbeat + "server_received_at" key + 重新预约离线检查
    mark_device_active(db, device, now_str, online=req.online)
    if req.cpu is not None:
        device.cpu = req.cpu
    if req.memory is not None:
        device.memory = req.memory
    if req.disk is not None:
        device.disk = req.disk
    if req.uptime:
        device.uptime = req.uptime
    if req.ip:
        device.ip = req.ip
    # 保存旧值（在更新前），用于 KV 同步
    old_volume = device.volume

    if req.volume is not None:
        device.volume = req.volume
        device.muted = (req.volume < 0)  # 负数表示静音
    if req.heartbeat_timeout > 0:
        device.heartbeat_timeout = req.heartbeat_timeout

    # ---- 同步心跳字段到 KV（驱动历史记录 + 变量表实时更新） ----
    kv_changes: list[dict] = []
    pfx = req.name + "."

    def _sync_kv(suffix: str, new_val: str, old_val: str | None):
        """写入/更新 KV 变量 + 历史记录"""
        key = pfx + suffix
        entry = db.query(KvEntry).filter(KvEntry.key == key).first()
        if entry:
            if entry.value == new_val:
                return
            old = entry.value
            entry.value = new_val
            entry.updated_at = now_str
            db.add(KvHistory(key=key, old_value=old, new_value=new_val,
                             source=req.source, retention_days=entry.retention_days,
                             changed_at=now_str))
            kv_changes.append({"key": key, "value": new_val, "old_value": old, "source": req.source, "changed_at": now_str})
        else:
            db.add(KvEntry(key=key, value=new_val, type="string", source=req.source,
                           retention_days=180, updated_at=now_str))
            db.add(KvHistory(key=key, old_value=None, new_value=new_val,
                             source=req.source, retention_days=180,
                             changed_at=now_str))
            kv_changes.append({"key": key, "value": new_val, "old_value": None, "source": req.source, "changed_at": now_str})

    if req.volume is not None:
        _sync_kv("volume", str(req.volume), str(old_volume) if old_volume is not None else None)

    db.commit()

    await broadcast("device.heartbeat", {
        "name": req.name, "online": req.online,
        "cpu": req.cpu, "memory": req.memory, "disk": req.disk,
        "volume": req.volume,
        "uptime": req.uptime, "ip": req.ip
    })
    # 同步心跳字段的 KV 变更广播（驱动变量表 + 历史弹窗实时更新）
    for c in kv_changes:
        await broadcast("kv.changed", c)
    return ApiResponse(success=True, message="OK")


@router.delete("/devices/{device_id}", response_model=ApiResponse)
async def unregister_device(device_id: str, db: Session = Depends(get_db), token=Depends(auth_write)):
    if is_clipboard_device(device_id=device_id):
        from fastapi import HTTPException
        raise HTTPException(403, "剪切板为内置设备，不允许删除")
    d = db.query(Device).filter(Device.id == device_id).first()
    name = d.name if d else None
    if d:
        db.delete(d)
        db.commit()
    if name:
        await broadcast("device.unregistered", {"id": device_id, "name": name})
    return ApiResponse(success=True, message="OK")


