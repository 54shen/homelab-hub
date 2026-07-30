# ============================================================
# Shared Center — 定时清理服务
# ============================================================
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import KvEntry, KvHistory, Device
from config import DEFAULT_RETENTION_DAYS, HEARTBEAT_TIMEOUT_SECONDS


def cleanup_history():
    """清理过期历史记录"""
    db: Session = SessionLocal()
    try:
        deleted_total = 0
        for entry in db.query(KvEntry).all():
            days = entry.retention_days or DEFAULT_RETENTION_DAYS
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            count = db.query(KvHistory).filter(
                KvHistory.key == entry.key,
                KvHistory.changed_at < cutoff
            ).delete()
            deleted_total += count
        if deleted_total > 0:
            db.commit()
            print(f"[Cleanup] 清理了 {deleted_total} 条过期历史记录")
    except Exception as e:
        print(f"[Cleanup] 清理出错: {e}")
        db.rollback()
    finally:
        db.close()


def check_device_offline():
    """检查超时设备并标记离线（每设备独立超时），触发离线告警"""
    db: Session = SessionLocal()
    try:
        now = datetime.now()
        # 找出在线设备，逐个检查
        online_devices = db.query(Device).filter(Device.online == True).all()
        offline_list = []

        for d in online_devices:
            timeout = d.heartbeat_timeout if d.heartbeat_timeout and d.heartbeat_timeout > 0 else HEARTBEAT_TIMEOUT_SECONDS
            cutoff = (now - timedelta(seconds=timeout)).strftime("%Y-%m-%d %H:%M:%S")
            if d.last_heartbeat < cutoff:
                d.online = False
                offline_list.append(d)

        if offline_list:
            db.commit()
            from services.alerts import check_device_offline_alert
            for d in offline_list:
                print(f"[Heartbeat] {d.name} 超时离线 (超时阈值: {d.heartbeat_timeout or HEARTBEAT_TIMEOUT_SECONDS}s)")
                check_device_offline_alert(d.name)
    except Exception as e:
        print(f"[Heartbeat] 检查出错: {e}")
        db.rollback()
    finally:
        db.close()
