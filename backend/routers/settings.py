# ============================================================
# Shared Center — 设置 API
# ============================================================
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import KvEntry, KvHistory, Token as TokenModel
from schemas import SystemConfigUpdate, ApiResponse
from auth import auth_write
from config import DEFAULT_RETENTION_DAYS
import os, uuid, json

router = APIRouter(prefix="/api", tags=["设置"])


@router.post("/settings/clean-history", response_model=ApiResponse)
def clean_history(db: Session = Depends(get_db), token=Depends(auth_write)):
    """手动清理过期历史数据"""
    deleted_total = 0
    entries = db.query(KvEntry).all()
    now = datetime.now()

    for entry in entries:
        days = entry.retention_days or DEFAULT_RETENTION_DAYS
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        count = db.query(KvHistory).filter(
            KvHistory.key == entry.key,
            KvHistory.changed_at < cutoff
        ).delete()
        deleted_total += count

    db.commit()
    return ApiResponse(success=True, message=f"已清理 {deleted_total} 条过期记录")


@router.get("/settings/backup")
def export_backup(db: Session = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import io

    data = {
        "kv": [{c.name: str(getattr(r, c.name)) for c in KvEntry.__table__.columns} for r in db.query(KvEntry).all()],
        "devices": [{c.name: str(getattr(r, c.name)) for c in __import__("models").Device.__table__.columns} for r in
                    db.query(__import__("models").Device).all()],
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return StreamingResponse(buf, media_type="application/json",
                             headers={"Content-Disposition": "attachment; filename=shared_center_backup.json"})


@router.get("/settings/system")
def get_system_config(db: Session = Depends(get_db)):
    from config import CLEANUP_INTERVAL_HOURS, DEFAULT_RETENTION_DAYS, HEARTBEAT_TIMEOUT_SECONDS
    return {
        "cleanup_interval_hours": CLEANUP_INTERVAL_HOURS,
        "default_retention_days": DEFAULT_RETENTION_DAYS,
        "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS
    }


@router.put("/settings/system", response_model=ApiResponse)
def save_system_config(cfg: SystemConfigUpdate, db: Session = Depends(get_db), token=Depends(auth_write)):
    # 运行时更新配置（单进程有效）
    import config
    if cfg.cleanup_interval_hours is not None:
        config.CLEANUP_INTERVAL_HOURS = cfg.cleanup_interval_hours  # type: ignore
    if cfg.default_retention_days is not None:
        config.DEFAULT_RETENTION_DAYS = cfg.default_retention_days  # type: ignore
    if cfg.heartbeat_timeout_seconds is not None:
        config.HEARTBEAT_TIMEOUT_SECONDS = cfg.heartbeat_timeout_seconds  # type: ignore
    return ApiResponse(success=True, message="已保存")
