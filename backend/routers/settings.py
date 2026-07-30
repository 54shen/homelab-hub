# ============================================================
# Shared Center — 设置 API
# ============================================================
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel as PydanticBase
from sqlalchemy.orm import Session
from database import get_db
from models import KvEntry, KvHistory, Device, User, Token as TokenModel, Session as SessionModel, WebhookConfig, AlertRule, SystemLog, UISetting
from schemas import SystemConfigUpdate, ApiResponse
from auth import auth_write
from config import DEFAULT_RETENTION_DAYS
import json

router = APIRouter(prefix="/api", tags=["设置"])


def _model_to_dict(model_class, db: Session):
    """将整张表导出为字典列表"""
    return [{c.name: str(getattr(r, c.name)) for c in model_class.__table__.columns}
            for r in db.query(model_class).all()]


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
    """导出完整备份（含所有表数据）"""
    from fastapi.responses import StreamingResponse
    import io

    data = {
        "version": "2.0",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kv": _model_to_dict(KvEntry, db),
        "kv_history": _model_to_dict(KvHistory, db),
        "devices": _model_to_dict(Device, db),
        "users": [{c.name: str(getattr(r, c.name))
                   for c in User.__table__.columns
                   if c.name != "password_hash"}  # 不含密码
                  for r in db.query(User).all()],
        "tokens": _model_to_dict(TokenModel, db),
        "webhooks": _model_to_dict(WebhookConfig, db),
        "alert_rules": _model_to_dict(AlertRule, db),
        "system_logs": _model_to_dict(SystemLog, db),
    }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return StreamingResponse(buf, media_type="application/json",
                             headers={"Content-Disposition": "attachment; filename=shared_center_backup.json"})


@router.post("/settings/restore", response_model=ApiResponse)
async def restore_backup(file: UploadFile, db: Session = Depends(get_db), token=Depends(auth_write)):
    """从备份文件恢复数据（增量合并，不删除已有数据）"""
    try:
        content = await file.read()
        data = json.loads(content)
    except Exception:
        raise HTTPException(400, "备份文件格式无效")

    restored = {"kv": 0, "devices": 0, "webhooks": 0, "alert_rules": 0, "tokens": 0, "users": 0}

    # KV（按 key 去重覆盖）
    if "kv" in data:
        for item in data["kv"]:
            existing = db.query(KvEntry).filter(KvEntry.key == item.get("key")).first()
            if existing:
                existing.value = item.get("value", "")
                existing.type = item.get("type", "string")
                existing.source = item.get("source", "restore")
            else:
                db.add(KvEntry(
                    key=item.get("key", ""), value=item.get("value", ""),
                    type=item.get("type", "string"), source=item.get("source", "restore"),
                    retention_days=int(item.get("retention_days", 180)),
                    expire_seconds=int(item["expire_seconds"]) if item.get("expire_seconds") else None
                ))
            restored["kv"] += 1
        db.commit()

    # Devices（按 name 去重覆盖）
    if "devices" in data:
        for item in data["devices"]:
            existing = db.query(Device).filter(Device.name == item.get("name")).first()
            if existing:
                for k, v in item.items():
                    if k != "id" and hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                db.add(Device(**{k: v for k, v in item.items() if k != "id"}))
            restored["devices"] += 1
        db.commit()

    # Webhooks（按 name+url 去重）
    if "webhooks" in data:
        for item in data["webhooks"]:
            existing = db.query(WebhookConfig).filter(
                WebhookConfig.name == item.get("name"),
                WebhookConfig.url == item.get("url")
            ).first()
            if not existing:
                db.add(WebhookConfig(**{k: v for k, v in item.items() if k != "id"}))
                restored["webhooks"] += 1
        db.commit()

    # Alert Rules（按 name 去重）
    if "alert_rules" in data:
        for item in data["alert_rules"]:
            existing = db.query(AlertRule).filter(AlertRule.name == item.get("name")).first()
            if not existing:
                db.add(AlertRule(**{k: v for k, v in item.items() if k != "id"}))
                restored["alert_rules"] += 1
        db.commit()

    # Tokens（按 token 去重）
    if "tokens" in data:
        for item in data["tokens"]:
            existing = db.query(TokenModel).filter(TokenModel.token == item.get("token")).first()
            if not existing:
                db.add(TokenModel(**{k: v for k, v in item.items() if k != "id"}))
                restored["tokens"] += 1
        db.commit()

    # Users（按 username 去重，不含密码的不覆盖已有用户）
    if "users" in data:
        for item in data["users"]:
            existing = db.query(User).filter(User.username == item.get("username")).first()
            if not existing:
                db.add(User(
                    username=item.get("username", ""),
                    password_hash="RESTORED_NEED_RESET",
                    permission=item.get("permission", "read")
                ))
                restored["users"] += 1
        db.commit()

    msg = f"恢复完成: KV×{restored['kv']} 设备×{restored['devices']} Webhook×{restored['webhooks']} 告警×{restored['alert_rules']} Token×{restored['tokens']} 用户×{restored['users']}"
    return ApiResponse(success=True, message=msg, data=restored)


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
    import config
    if cfg.cleanup_interval_hours is not None:
        config.CLEANUP_INTERVAL_HOURS = cfg.cleanup_interval_hours  # type: ignore
    if cfg.default_retention_days is not None:
        config.DEFAULT_RETENTION_DAYS = cfg.default_retention_days  # type: ignore
    if cfg.heartbeat_timeout_seconds is not None:
        config.HEARTBEAT_TIMEOUT_SECONDS = cfg.heartbeat_timeout_seconds  # type: ignore
    return ApiResponse(success=True, message="已保存")


# ---- UI 设置（跨终端同步） ----
class UISettingsPayload(PydanticBase):
    settings: dict  # { key: value, ... }

@router.get("/settings/ui")
def get_ui_settings(db: Session = Depends(get_db)):
    """获取所有 UI 设置"""
    rows = db.query(UISetting).all()
    return {r.key: r.value for r in rows}

@router.put("/settings/ui", response_model=ApiResponse)
def save_ui_settings(payload: UISettingsPayload, db: Session = Depends(get_db)):
    """批量保存 UI 设置"""
    for k, v in payload.settings.items():
        entry = db.query(UISetting).filter(UISetting.key == k).first()
        if entry:
            entry.value = str(v)
        else:
            db.add(UISetting(key=k, value=str(v)))
    db.commit()
    return ApiResponse(success=True, message="已保存")
