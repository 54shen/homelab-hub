# ============================================================
# 定时清理服务测试(直接调用函数,不依赖真实定时器)
# ============================================================
from datetime import datetime, timedelta

from models import Device, KvHistory
from services.cleanup import check_device_offline, cleanup_history


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_cleanup_history_removes_only_expired(client, db):
    old = _fmt(datetime.now() - timedelta(days=200))      # 超过 180 天保留期
    recent = _fmt(datetime.now())
    db.add(KvHistory(key="old.k", old_value=None, new_value="1", retention_days=180, changed_at=old))
    db.add(KvHistory(key="new.k", old_value=None, new_value="1", retention_days=180, changed_at=recent))
    db.commit()

    cleanup_history()

    db.expire_all()
    keys = [k[0] for k in db.query(KvHistory.key).all()]
    assert "old.k" not in keys
    assert "new.k" in keys


def test_cleanup_history_respects_custom_retention(client, db):
    """保留期 30 天的记录,100 天后被清;保留期 3650 天的保留"""
    old = _fmt(datetime.now() - timedelta(days=100))
    db.add(KvHistory(key="short.k", old_value=None, new_value="1", retention_days=30, changed_at=old))
    db.add(KvHistory(key="long.k", old_value=None, new_value="1", retention_days=3650, changed_at=old))
    db.commit()

    cleanup_history()

    db.expire_all()
    keys = {k[0] for k in db.query(KvHistory.key).all()}
    assert "short.k" not in keys
    assert "long.k" in keys


def test_check_device_offline_marks_timeout_only(client, db):
    old = _fmt(datetime.now() - timedelta(minutes=10))    # 超过默认 180s 阈值
    fresh = _fmt(datetime.now())
    db.add(Device(id="a" * 12, name="超时设备", online=True, last_heartbeat=old, type="pc"))
    db.add(Device(id="b" * 12, name="在线设备", online=True, last_heartbeat=fresh, type="pc"))
    db.commit()

    check_device_offline()

    db.expire_all()
    states = {d.name: d.online for d in db.query(Device).all()}
    assert states["超时设备"] is False
    assert states["在线设备"] is True
