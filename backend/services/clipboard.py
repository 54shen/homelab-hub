# ============================================================
# 剪切板 — 内置实体幂等创建
# ============================================================
from constants import (
    CLIPBOARD_DEVICE_GROUP, CLIPBOARD_DEVICE_HOSTNAME, CLIPBOARD_DEVICE_ID,
    CLIPBOARD_DEVICE_NAME, CLIPBOARD_DEVICE_TYPE, CLIPBOARD_KEY,
)
from models import Device, KvEntry


def ensure_clipboard(db) -> None:
    """幂等创建剪切板设备 + key。

    只在"不存在"时插入 → 天然幂等；不写 KvHistory、不广播 WS
    （启动初始化的空值不应出现在历史里）。
    """
    dev = db.query(Device).filter(Device.name == CLIPBOARD_DEVICE_NAME).first()
    if not dev:
        dev = Device(
            id=CLIPBOARD_DEVICE_ID, name=CLIPBOARD_DEVICE_NAME,
            type=CLIPBOARD_DEVICE_TYPE, group=CLIPBOARD_DEVICE_GROUP,
            hostname=CLIPBOARD_DEVICE_HOSTNAME, online=False,
            heartbeat_timeout=0,
        )
        db.add(dev)
    elif dev.id != CLIPBOARD_DEVICE_ID:
        # 极端情况：agent 抢注了同名设备 → 接管并纠正类型（不影响其 id）
        dev.type = CLIPBOARD_DEVICE_TYPE

    entry = db.query(KvEntry).filter(KvEntry.key == CLIPBOARD_KEY).first()
    if not entry:
        db.add(KvEntry(
            key=CLIPBOARD_KEY, value="", type="string",
            source="system", retention_days=3650,
        ))
    db.commit()
