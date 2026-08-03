# ============================================================
# Shared Center — Dashboard API
# ============================================================
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Device, KvEntry, KvHistory, SystemLog
from schemas import DashboardStatsOut, DbStatusOut, TimelineEvent
import os

router = APIRouter(prefix="/api", tags=["Dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStatsOut)
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(Device).count()
    online = db.query(Device).filter(Device.online == True).count()

    # 统计服务数量（type=service 的 KV）
    total_services = db.query(KvEntry).filter(KvEntry.key.like("service.%")).count()
    running_services = db.query(KvEntry).filter(
        KvEntry.key.like("service.%"),
        KvEntry.value == "running"
    ).count()

    # 变量总数
    total_keys = db.query(KvEntry).count()

    # 网络状态：有已注册设备或有公网IP记录即为正常
    public_ip_entry = db.query(KvEntry).filter(KvEntry.key == "network.public_ip").first()
    public_ip = public_ip_entry.value if public_ip_entry else "—"
    # 有任意设备记录或公网IP，说明网络曾通
    network_status = "online" if (total > 0 or public_ip_entry) else "offline"

    # 系统健康
    if total > 0:
        health = int((online / total) * 100)
    else:
        health = 100

    return DashboardStatsOut(
        total_devices=total,
        online_devices=online,
        total_services=total_services,
        running_services=running_services,
        total_keys=total_keys,
        network_status=network_status,
        public_ip=public_ip,
        system_health=health
    )


@router.get("/dashboard/recent", response_model=list)
def recent_changes(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    """最近 KV 值变更记录"""
    rows = db.query(KvHistory).order_by(KvHistory.changed_at.desc()).limit(limit).all()
    return [
        {"id": r.id, "key": r.key, "old_value": r.old_value,
         "new_value": r.new_value, "source": r.source, "changed_at": r.changed_at}
        for r in rows
    ]


@router.get("/dashboard/db-status", response_model=DbStatusOut)
def db_status(db: Session = Depends(get_db)):
    from config import BASE_DIR
    db_path = os.path.join(BASE_DIR, "data", "shared_center.db")
    file_size = "—"
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        if size_bytes < 1024 * 1024:
            file_size = f"{size_bytes / 1024:.1f} KB"
        else:
            file_size = f"{size_bytes / (1024 * 1024):.1f} MB"

    total_keys = db.query(KvEntry).count()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    active_24h = db.query(KvEntry).filter(KvEntry.updated_at >= yesterday).count()

    history_count = db.query(KvHistory).count()

    return DbStatusOut(
        file_size=file_size,
        total_keys=total_keys,
        active_keys_24h=active_24h,
        history_count=history_count
    )


@router.get("/dashboard/timeline")
def dashboard_timeline(limit: int = Query(20), db: Session = Depends(get_db)):
    events: list[TimelineEvent] = []

    # 设备心跳
    recent_devices = db.query(Device).order_by(Device.last_heartbeat.desc()).limit(5).all()
    for d in recent_devices:
        events.append(TimelineEvent(
            time=d.last_heartbeat,
            icon="hardware-chip-outline",
            title=f"{d.name} 心跳",
            description="在线" if d.online else "离线",
            color="#22C55E" if d.online else "#EF4444"
        ))

    # 排序（仅设备心跳事件）
    events.sort(key=lambda e: e.time, reverse=True)
    return {"events": [e.dict() for e in events[:limit]]}
