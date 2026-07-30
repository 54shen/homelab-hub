# ============================================================
# Shared Center — 设备管理 API
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Device, KvEntry
from schemas import (
    DeviceRegisterRequest, DeviceHeartbeatRequest,
    DeviceOut, KvEntryOut, ApiResponse
)
from websocket_manager import broadcast
from auth import auth_optional

router = APIRouter(prefix="/api", tags=["设备管理"])


def _gen_device_id(name: str, typ: str) -> str:
    import hashlib
    raw = f"{name}:{typ}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.online.desc(), Device.last_heartbeat.desc()).all()


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.id == device_id).first()
    if not d:
        from fastapi import HTTPException
        raise HTTPException(404, "设备不存在")
    return d


@router.get("/devices/{device_id}/variables", response_model=list[KvEntryOut])
def get_device_variables(device_id: str, db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.id == device_id).first()
    if not d:
        return []
    prefix = d.name.lower().replace("-", ".").replace(" ", ".") + "."
    return db.query(KvEntry).filter(KvEntry.key.like(f"{prefix}%")).all()


@router.post("/device/register", response_model=ApiResponse)
def register_device(req: DeviceRegisterRequest, db: Session = Depends(get_db), _auth=Depends(auth_optional)):
    device_id = _gen_device_id(req.name, req.type)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    else:
        db.add(Device(
            id=device_id,
            name=req.name,
            hostname=req.hostname,
            type=req.type,
            version=req.version,
            mac=req.mac,
            os=req.os,
            group=req.group,
            online=False,
            last_heartbeat=now_str,
            registered_at=now_str
        ))

    db.commit()
    return ApiResponse(success=True, message="OK", data={"device_id": device_id})


@router.post("/device/heartbeat", response_model=ApiResponse)
async def device_heartbeat(req: DeviceHeartbeatRequest, db: Session = Depends(get_db), _auth=Depends(auth_optional)):
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
    device.online = req.online
    device.last_heartbeat = now_str
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

    db.commit()
    await broadcast("device.heartbeat", {"name": req.name, "online": req.online, "cpu": req.cpu, "memory": req.memory, "disk": req.disk})
    return ApiResponse(success=True, message="OK")


@router.delete("/devices/{device_id}", response_model=ApiResponse)
def unregister_device(device_id: str, db: Session = Depends(get_db), _auth=Depends(auth_optional)):
    d = db.query(Device).filter(Device.id == device_id).first()
    if d:
        db.delete(d)
        db.commit()
    return ApiResponse(success=True, message="OK")
