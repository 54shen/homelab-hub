# ============================================================
# 设备活跃度服务 — KV 上报/心跳统一刷新设备在线状态
#
# 背景：在线判定只认 Device.last_heartbeat。本模块让"变量上报"
#       也成为设备活跃信号（复用现有超时离线检测与离线告警），
#       并为每设备维护服务器专用 key "{name}.server_received_at"。
# ============================================================
from datetime import datetime
from sqlalchemy.orm import Session
from models import Device, KvEntry
from constants import CLIPBOARD_DEVICE_NAME, REPORT_TIME_SUFFIX

# 改名前的旧后缀（"设备上报时间"→"server_received_at"），启动同步时清理残留
LEGACY_REPORT_TIME_SUFFIX = ".设备上报时间"


def device_prefixes(d: Device) -> list[str]:
    """设备 key 前缀集合（与 routers/devices.py get_device_variables 同源）

    原始名称 + 转换名称（连字符/空格→点，小写），两种前缀都要覆盖，
    因为 agent 实际上报可能用其中任意一种。
    """
    p = [d.name + "."]
    transformed = d.name.lower().replace("-", ".").replace(" ", ".") + "."
    if transformed != p[0]:
        p.append(transformed)
    return p


def resolve_device_by_key(db: Session, key: str) -> Device | None:
    """按 KV key 反推设备（最长前缀匹配）

    - 排除剪切板（Web 复制粘贴写 "剪切板.内容" 不算设备活跃）与 HA
      （HA 已有 /api/ha/state 独立心跳机制）
    - 最长前缀：设备名含点（如 "A.B" 与 "A" 并存）时归最具体的设备
    """
    best: Device | None = None
    best_len = -1
    for d in db.query(Device).filter(
            Device.name != CLIPBOARD_DEVICE_NAME,
            Device.type != "ha").all():
        for p in device_prefixes(d):
            if key.startswith(p) and len(p) > best_len:
                best, best_len = d, len(p)
    return best


def write_report_time_silent(db: Session, device: Device, now_str: str,
                             update_existing: bool = True) -> None:
    """静默 upsert 服务器专用 key "{name}.server_received_at"

    只服务器写（source 恒为 "system"）；不写 KvHistory、不触发告警、
    不广播 WS —— 该 key 每次上报都变，写历史是纯噪音。
    update_existing=False 时已有 key 保持原值（启动同步只保证存在性，
    不虚增上报时间）。
    """
    key = f"{device.name}{REPORT_TIME_SUFFIX}"
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if entry:
        if update_existing and entry.value != now_str:  # 同一秒重复上报 → 无操作
            entry.value = now_str
            entry.source = "system"
            entry.type = "string"
            entry.updated_at = now_str
    else:
        db.add(KvEntry(
            key=key,
            value=now_str,
            type="string",
            source="system",
            retention_days=3650,
            updated_at=now_str
        ))


def ensure_report_time_keys(db: Session) -> None:
    """启动同步（幂等）：设备存在 → server_received_at key 必须存在

    - 迁移：清理改名前的旧 key "*.设备上报时间" 残留（已被新 key 取代）
    - 为所有非剪切板设备补齐 key（含 HA，HA 由 /api/ha/state 每次刷新）；
      已有 key 保持原值（update_existing=False），不虚增上报时间
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for old in db.query(KvEntry).filter(
            KvEntry.key.like(f"%{LEGACY_REPORT_TIME_SUFFIX}")).all():
        db.delete(old)

    for d in db.query(Device).filter(Device.name != CLIPBOARD_DEVICE_NAME).all():
        write_report_time_silent(db, d, now_str, update_existing=False)

    db.commit()


def mark_device_active(db: Session, device: Device, now_str: str,
                       online: bool = True, rearm_offline: bool = True) -> None:
    """统一刷新设备活跃度：online 状态 + last_heartbeat + 上报时间 key

    rearm_offline=True 时重新预约离线检查（每次活跃都推迟离线判定），
    否则 KV-only 设备在心跳预约过期后，离线告警会静默失效
    （周期扫描 check_device_offline 只标离线、不触发告警）。
    """
    device.online = online
    device.last_heartbeat = now_str
    write_report_time_silent(db, device, now_str)

    if online and rearm_offline:
        from services.alerts import schedule_offline_check
        from config import DEFAULT_HEARTBEAT_TIMEOUT
        timeout = device.heartbeat_timeout if device.heartbeat_timeout and device.heartbeat_timeout > 0 else DEFAULT_HEARTBEAT_TIMEOUT
        schedule_offline_check(device.name, timeout)
