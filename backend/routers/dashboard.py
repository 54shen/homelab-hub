# ============================================================
# Shared Center — Dashboard API
# ============================================================
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import Device, KvEntry, KvHistory, Session as SessionModel, Token as TokenModel, TotpDisplay, SystemLog
from schemas import ApiResponse, DashboardStatsOut, DbStatusOut, TimelineEvent
from constants import CLIPBOARD_DEVICE_NAME, CLIPBOARD_KEY
import os

router = APIRouter(prefix="/api", tags=["Dashboard"])


def _is_admin(request: Request, db: Session) -> bool:
    """操作者是否为 admin(Web 会话或 API Token)"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token_str = auth[7:]
    session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first()
    if session_record and session_record.permission == "admin":
        return True
    token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
    if token_record and token_record.permission == "admin":
        return True
    return False


def _current_user(request: Request, db: Session):
    """当前登录用户(Web 会话或 API Token 关联)"""
    from models import User
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_str = auth[7:]
    session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first()
    if session_record:
        return db.query(User).filter(User.id == session_record.user_id).first()
    token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
    if token_record and token_record.user_id:
        return db.query(User).filter(User.id == token_record.user_id).first()
    return None


def _totp_target(request: Request, db: Session, user_id: int | None):
    """解析 TOTP 目标用户:默认自己;带 user_id 查/改别人仅限 admin。
    返回 (target_user_id, error_response)"""
    user = _current_user(request, db)
    if not user:
        return None, HTTPException(401, "未登录")
    target_id = user_id if user_id is not None else user.id
    if target_id != user.id and not _is_admin(request, db):
        return None, HTTPException(403, "仅管理员可查看/修改其他用户的 TOTP")
    return target_id, None


# ---- TOTP 展示器:每用户独立密钥(单独保存,不作为 KV 变量),仪表盘实时展示自己的验证码 ----
class TotpSecretPayload(BaseModel):
    secret: str


@router.get("/dashboard/totp-code")
def totp_code(request: Request, db: Session = Depends(get_db),
              user_id: int | None = None):
    """当前 6 位验证码 + 本周期剩余秒数(查自己的;admin 可带 user_id 查别人的)"""
    target_id, err = _totp_target(request, db, user_id)
    if err:
        raise err
    row = db.query(TotpDisplay).filter(TotpDisplay.user_id == target_id).first()
    if not row or not row.secret:
        return {"configured": False}
    import pyotp
    return {
        "configured": True,
        "code": pyotp.TOTP(row.secret).now(),
        # 整数秒取模:周期边界(余数 0)时正确返回 30(新周期刚开始的完整 30 秒)
        "period_remaining": 30 - (int(time.time()) % 30),
    }


@router.put("/dashboard/totp-secret", response_model=ApiResponse)
def set_totp_secret(req: TotpSecretPayload, request: Request, db: Session = Depends(get_db),
                    user_id: int | None = None):
    """设置自己的 TOTP 密钥(保存前校验 Base32 有效);admin 可代其他用户设置"""
    target_id, err = _totp_target(request, db, user_id)
    if err:
        raise err
    secret = req.secret.strip().upper()
    import pyotp
    try:
        pyotp.TOTP(secret).now()  # 试算一次,非法 Base32 抛异常
    except Exception:
        raise HTTPException(400, "密钥格式无效,请检查 Base32 密钥")
    row = db.query(TotpDisplay).filter(TotpDisplay.user_id == target_id).first()
    if not row:
        row = TotpDisplay(user_id=target_id)
        db.add(row)
    row.secret = secret
    row.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return ApiResponse(success=True, message="TOTP 展示器已更新")


@router.get("/dashboard/stats", response_model=DashboardStatsOut)
def dashboard_stats(db: Session = Depends(get_db)):
    # 统计排除内置设备/变量（剪切板等系统实体不计入）
    total = db.query(Device).filter(Device.name != CLIPBOARD_DEVICE_NAME).count()
    online = db.query(Device).filter(
        Device.online == True,
        Device.name != CLIPBOARD_DEVICE_NAME,
    ).count()

    # 统计服务数量（type=service 的 KV）
    total_services = db.query(KvEntry).filter(KvEntry.key.like("service.%")).count()
    running_services = db.query(KvEntry).filter(
        KvEntry.key.like("service.%"),
        KvEntry.value == "running"
    ).count()

    # 变量总数
    total_keys = db.query(KvEntry).filter(KvEntry.key != CLIPBOARD_KEY).count()

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
    """最近 KV 值变更记录（排除剪切板等内置 key，其历史在仪表盘面板内展示）"""
    rows = db.query(KvHistory).filter(
        KvHistory.key != CLIPBOARD_KEY
    ).order_by(KvHistory.changed_at.desc()).limit(limit).all()
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

    total_keys = db.query(KvEntry).filter(KvEntry.key != CLIPBOARD_KEY).count()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    active_24h = db.query(KvEntry).filter(
        KvEntry.updated_at >= yesterday,
        KvEntry.key != CLIPBOARD_KEY,
    ).count()

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
