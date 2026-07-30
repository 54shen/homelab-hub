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
    """检查超时设备并标记离线"""
    db: Session = SessionLocal()
    try:
        cutoff = (datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
        offline_count = db.query(Device).filter(
            Device.online == True,
            Device.last_heartbeat < cutoff
        ).update({"online": False})
        if offline_count > 0:
            db.commit()
            print(f"[Heartbeat] {offline_count} 台设备超时离线")
    except Exception as e:
        print(f"[Heartbeat] 检查出错: {e}")
        db.rollback()
    finally:
        db.close()
