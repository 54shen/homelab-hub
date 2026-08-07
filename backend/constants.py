# ============================================================
# 内置常量与判断辅助（剪切板等系统内置实体）
# ============================================================
import hashlib

CLIPBOARD_DEVICE_NAME = "剪切板"
CLIPBOARD_DEVICE_TYPE = "clipboard"
CLIPBOARD_DEVICE_GROUP = "系统"
CLIPBOARD_DEVICE_HOSTNAME = "系统内置"
CLIPBOARD_KEY = f"{CLIPBOARD_DEVICE_NAME}.内容"
# 与 routers/devices.py 的 _gen_device_id 公式保持一致（md5(name:type) 前 12 位）
CLIPBOARD_DEVICE_ID = hashlib.md5(
    f"{CLIPBOARD_DEVICE_NAME}:{CLIPBOARD_DEVICE_TYPE}".encode()
).hexdigest()[:12]

# ---- 登录安全：仅验证码登录开关（存 UISetting） ----
AUTH_CODE_ONLY_KEY = "auth_code_only"

# ---- 服务器专用 key：设备上报时间（只能服务器写，设备上传被强制覆盖） ----
REPORT_TIME_SUFFIX = ".设备上报时间"


def is_report_time_key(key: str) -> bool:
    return key.endswith(REPORT_TIME_SUFFIX)


def is_clipboard_key(key: str) -> bool:
    return key == CLIPBOARD_KEY


def is_clipboard_device(device_id: str = "", name: str = "") -> bool:
    if device_id and device_id == CLIPBOARD_DEVICE_ID:
        return True
    return bool(name and name == CLIPBOARD_DEVICE_NAME)
