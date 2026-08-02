# ============================================================
# Shared Center — 定时清理服务
# ============================================================
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Device, KvHistory
from config import DEFAULT_HEARTBEAT_TIMEOUT


def cleanup_history():
    """清理过期的历史记录（每条按自己的 retention_days 判断）"""
    db: Session = SessionLocal()
    try:
        # 获取所有不同的 retention_days 值，分组清理
        retention_values = db.query(KvHistory.retention_days).distinct().all()
        total = 0
        now = datetime.now()
        for (rd,) in retention_values:
            cutoff = (now - timedelta(days=rd)).strftime("%Y-%m-%d %H:%M:%S")
            deleted = db.query(KvHistory).filter(
                KvHistory.retention_days == rd,
                KvHistory.changed_at < cutoff
            ).delete()
            total += deleted
        if total:
            db.commit()
            print(f"[Cleanup] 清理了 {total} 条过期历史记录")
        else:
            db.rollback()
    except Exception as e:
        print(f"[Cleanup] 清理出错: {e}")
        db.rollback()
    finally:
        db.close()


def check_device_offline():
    """检查超时设备并标记离线（仅负责 DB 状态，告警由心跳路径实时预约触发）"""
    db: Session = SessionLocal()
    try:
        now = datetime.now()
        online_devices = db.query(Device).filter(
            Device.online == True,
            Device.type != "ha"
        ).all()

        for d in online_devices:
            timeout = d.heartbeat_timeout if d.heartbeat_timeout and d.heartbeat_timeout > 0 else DEFAULT_HEARTBEAT_TIMEOUT
            cutoff = (now - timedelta(seconds=timeout)).strftime("%Y-%m-%d %H:%M:%S")
            if d.last_heartbeat < cutoff:
                d.online = False
                print(f"[Heartbeat] {d.name} 超时离线 (超时阈值: {timeout}s)")

        db.commit()
    except Exception as e:
        print(f"[Heartbeat] 检查出错: {e}")
        db.rollback()
    finally:
        db.close()
