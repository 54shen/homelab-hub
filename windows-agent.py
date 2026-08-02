#!/usr/bin/env python3
# ============================================================
# Windows Agent — 心跳上报 + KV 采集 + HTTP 指令接收（静音控制）
# 依赖：pip install requests psutil pycaw flask
# ============================================================
import sys
import os
import time
import signal
import socket
import platform
import logging
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from pycaw.pycaw import AudioUtilities

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[WARN] psutil 未安装，无法获取 CPU/内存/磁盘数据。pip install psutil")

# ══════════════════════════════════════════════════════════════
# 配置区
# ══════════════════════════════════════════════════════════════
BASE_URL     = "http://localhost:8000"
DEVICE_NAME  = "大爷的ROG"
DEVICE_TYPE  = "computer"
DEVICE_GROUP = "PC"
INTERVAL     = 5                       # 心跳间隔（秒）
REPORT_KV    = True                     # 是否上报 KV 变量
KV_INTERVAL  = 6                        # 每 N 次心跳上报一次 KV
SOURCE       = "我的agent"

# Flask 指令监听端口
FLASK_PORT   = int(os.getenv("PC_PORT", "11253"))

HOSTNAME = socket.gethostname()

# Token：优先环境变量 PC_TOKEN → TEST_WRITE_TOKEN → .env 文件 → 硬编码兜底
TOKEN = os.getenv("PC_TOKEN") or os.getenv("TEST_WRITE_TOKEN") or ""
if not TOKEN:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TEST_WRITE_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()
                break
    if not TOKEN:
        TOKEN = "48548564864gsdfgsdg456486486sdgsdg4254456456sdgsdgsdf"

# ══════════════════════════════════════════════════════════════
# 日志
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agent")

# ══════════════════════════════════════════════════════════════
# HTTP 会话（发往中枢服务器）
# ══════════════════════════════════════════════════════════════
session = requests.Session()
session.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
})
if TOKEN:
    session.headers["Authorization"] = f"Bearer {TOKEN}"
    log.info("Token 已加载: %s...", TOKEN[:16])
else:
    log.warning("⚠ 未设置 Token，请求可能被拒绝")

# ══════════════════════════════════════════════════════════════
# Flask 指令服务（静音控制）
# ══════════════════════════════════════════════════════════════
flask_app = Flask(__name__)
_volume = None


def _get_volume():
    global _volume
    if _volume is None:
        _volume = AudioUtilities.GetSpeakers().EndpointVolume
    return _volume


def is_muted() -> bool:
    return _get_volume().GetMute()


# ── Token 校验装饰器 ──
def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        data = request.json
        if not data or data.get("token") != TOKEN:
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        return f(*args, **kwargs)
    return wrapper


# ── 统一静音控制 ──
def _set_mute(target_muted: bool) -> dict:
    """静音/取消静音，返回操作结果"""
    label = "静音" if target_muted else "取消静音"
    emoji = "🔇" if target_muted else "🔊"
    log.info("=" * 50)
    log.info("  %s 收到%s命令", emoji, label)
    log.info("=" * 50)
    vol = _get_volume()
    current = vol.GetMute()
    if current == target_muted:
        log.info("  → 跳过：已经是%s状态", label)
        return {"ok": True, "muted": current, "changed": False, "message": f"已经是{label}状态"}
    vol.SetMute(target_muted, None)
    log.info("  → %s完成 ✓", label)
    _report_state("mute" if target_muted else "unmute")
    return {"ok": True, "muted": target_muted, "changed": True, "message": f"已{label}"}


# ── 后台：上报音量 + 静音状态 + 即时心跳 ──
def _report_state(action: str) -> None:
    """收到控制指令后立即上报音量 + 静音状态到中枢（后台线程，不阻塞响应）"""

    def _run():
        try:
            vol = _get_volume()
            muted = vol.GetMute()
            vol_pct = int(round(vol.GetMasterVolumeLevelScalar() * 100))
            pfx = kv_prefix()

            # KV 上报
            items = [
                {"key": pfx + "系统音量", "value": str(vol_pct), "type": "int", "source": "command"},
                {"key": pfx + "静音状态", "value": "静音" if muted else "非静音", "type": "string", "source": "command"},
            ]
            for item in items:
                post("/api/kv", item, retry=1, delay=1)
            log.info("已上报状态: 音量=%d%%  静音=%s  (触发: %s)", vol_pct, "是" if muted else "否", action)

            # 立即发送心跳（让前端 WebSocket 即时刷新 muted/volume）
            info = collect()
            result = post("/api/device/heartbeat", {
                "name": DEVICE_NAME or HOSTNAME, "online": True,
                "cpu": info["cpu"], "memory": info["memory"], "disk": info["disk"],
                "volume": info.get("volume"), "muted": info.get("muted", False),
                "uptime": info["uptime"], "ip": info["ip"],
                "source": SOURCE,
            }, retry=1, delay=1)
            if result and result.get("success"):
                log.info("即时心跳已发送 → VOL=%d%%  %s", vol_pct, "🔇 已静音" if muted else "🔊 已取消静音")
        except Exception as e:
            log.warning("上报状态失败: %s", e)

    threading.Thread(target=_run, daemon=True).start()


# ── 路由 ──
@flask_app.route("/mute", methods=["POST"])
@require_token
def api_mute():
    return jsonify(_set_mute(True))


@flask_app.route("/unmute", methods=["POST"])
@require_token
def api_unmute():
    return jsonify(_set_mute(False))


@flask_app.route("/toggle", methods=["POST"])
@require_token
def api_toggle():
    return jsonify(_set_mute(not is_muted()))


@flask_app.route("/status", methods=["POST"])
@require_token
def api_status():
    muted = is_muted()
    return jsonify({"ok": True, "muted": muted, "message": "静音" if muted else "非静音"})


@flask_app.route("/command", methods=["POST"])
@require_token
def api_command():
    """中枢 Webhook 统一入口：{"action":"on"|"off"} → on=取消静音 off=静音"""
    action = (request.json or {}).get("action", "")
    action_map = {"on": False, "off": True}  # on → unmute, off → mute
    if action in action_map:
        return jsonify(_set_mute(action_map[action]))
    muted = is_muted()
    return jsonify({"ok": True, "muted": muted, "changed": False,
                    "message": f"未知 action '{action}'，当前: {'静音' if muted else '非静音'}"})


def run_flask():
    log.info("指令监听 http://0.0.0.0:%d", FLASK_PORT)
    flask_app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════════
# 系统信息采集
# ══════════════════════════════════════════════════════════════
def get_mac() -> str:
    import uuid
    try:
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
    except Exception:
        return ""


def get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(HOSTNAME)


def get_uptime() -> str:
    try:
        if HAS_PSUTIL:
            secs = time.time() - psutil.boot_time()
        elif platform.system() == "Windows":
            import ctypes
            secs = ctypes.windll.kernel32.GetTickCount64() / 1000.0
        else:
            return ""
    except Exception:
        return ""
    d = int(secs // 86400)
    h = int((secs % 86400) // 3600)
    m = int((secs % 3600) // 60)
    if d: return f"{d}d {h}h {m}m"
    if h: return f"{h}h {m}m"
    return f"{m}m"


def collect() -> dict:
    info: dict = {
        "hostname": HOSTNAME,
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "ip": get_ip(),
        "mac": get_mac(),
        "uptime": get_uptime(),
        "cpu": None, "memory": None, "disk": None, "volume": None,
    }
    if HAS_PSUTIL:
        info["cpu"] = int(psutil.cpu_percent(interval=1))
        info["memory"] = int(psutil.virtual_memory().percent)
        info["disk"] = int(psutil.disk_usage("/").percent)
        info["mem_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["disk_total_gb"] = round(psutil.disk_usage("/").total / (1024**3), 1)
        info["cpu_count"] = psutil.cpu_count(logical=False) or os.cpu_count() or 0
        info["process_count"] = len(psutil.pids())
        info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        io = psutil.net_io_counters()
        info["net_sent_mb"] = round(io.bytes_sent / (1024**2), 1)
        info["net_recv_mb"] = round(io.bytes_recv / (1024**2), 1)
    # 系统音量 + 静音（pycaw）
    try:
        vol = _get_volume()
        info["volume"] = int(round(vol.GetMasterVolumeLevelScalar() * 100))
        info["muted"] = vol.GetMute()
    except Exception:
        pass
    return info


# ══════════════════════════════════════════════════════════════
# HTTP 请求
# ══════════════════════════════════════════════════════════════
def post(path: str, data: dict, retry: int = 3, delay: int = 5) -> dict | None:
    url = f"{BASE_URL.rstrip('/')}{path}"
    for attempt in range(retry + 1):
        try:
            resp = session.post(url, json=data, timeout=10)
            if 400 <= resp.status_code < 500:
                log.error("HTTP %d: %s", resp.status_code, resp.text[:200])
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            last = "timeout"
        except requests.exceptions.ConnectionError:
            last = "connection refused"
        except requests.exceptions.RequestException as e:
            last = str(e)
        if attempt < retry:
            wait = delay * (2 ** attempt)
            log.warning("请求失败，%ds 后重试 (%d/%d): %s", wait, attempt + 1, retry, last)
            time.sleep(wait)
    log.error("请求最终失败: %s", last)
    return None


# ══════════════════════════════════════════════════════════════
# 业务：注册 / 心跳 / KV 上报
# ══════════════════════════════════════════════════════════════
def kv_prefix() -> str:
    name = DEVICE_NAME or HOSTNAME
    return name.replace("-", ".").replace(" ", ".") + "."


def register() -> bool:
    info = collect()
    name = DEVICE_NAME or HOSTNAME
    payload = {
        "name": name,
        "type": DEVICE_TYPE,
        "version": "2.0",
        "hostname": info["hostname"],
        "mac": info["mac"],
        "os": f"{info['os']} {info['os_release']}",
        "group": DEVICE_GROUP,
    }
    result = post("/api/device/register", payload)
    if result and result.get("success"):
        device_id = (result.get("data") or {}).get("device_id", "?")
        log.info("注册成功: %s (ID: %s)", name, device_id)
        return True
    log.error("注册失败: %s", result)
    return False


def heartbeat() -> bool:
    info = collect()
    name = DEVICE_NAME or HOSTNAME
    result = post("/api/device/heartbeat", {
        "name": name, "online": True,
        "cpu": info["cpu"], "memory": info["memory"], "disk": info["disk"],
        "volume": info.get("volume"), "muted": info.get("muted", False),
        "uptime": info["uptime"], "ip": info["ip"],
        "source": SOURCE,
    }, retry=1, delay=2)
    if result and result.get("success"):
        log.info("♥ 心跳  CPU:%s%%  MEM:%s%%  DISK:%s%%  VOL:%s%%  %s  IP:%s",
                 info["cpu"], info["memory"], info["disk"],
                 info.get("volume", "?"),
                 "🔇" if info.get("muted") else "🔊",
                 info["ip"])
        return True
    log.warning("心跳失败: %s", result)
    return False


def report_kv() -> None:
    info = collect()
    pfx = kv_prefix()

    items = []
    def a(k, v, t="string"):
        items.append({"key": pfx + k, "value": str(v) if v is not None else "", "type": t})

    a("主机名", info["hostname"])
    a("操作系统", info["os"])
    a("系统版本", info["os_release"])
    a("系统架构", info["architecture"])
    a("IP地址", info["ip"])
    a("MAC地址", info["mac"])
    a("运行时长", info["uptime"])
    if info["cpu"] is not None:
        a("CPU使用率", info["cpu"], "int")
    if info["memory"] is not None:
        a("内存使用率", info["memory"], "int")
    if info["disk"] is not None:
        a("磁盘使用率", info["disk"], "int")
    if info.get("process_count"):
        a("进程数", info["process_count"], "int")
    if info.get("mem_total_gb"):
        a("内存总量_GB", info["mem_total_gb"], "float")
    if info.get("disk_total_gb"):
        a("磁盘总量_GB", info["disk_total_gb"], "float")
    if info.get("net_sent_mb"):
        a("网络发送_MB", info["net_sent_mb"], "float")
    if info.get("net_recv_mb"):
        a("网络接收_MB", info["net_recv_mb"], "float")
    if info.get("cpu_count"):
        a("CPU核心数", info["cpu_count"], "int")
    if info.get("boot_time"):
        a("启动时间", info["boot_time"])
    if info.get("volume") is not None:
        a("系统音量", info["volume"], "int")
    for item in items:
        item["source"] = SOURCE
        post("/api/kv", item, retry=1, delay=2)


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════
def shutdown(*_):
    log.info("正在退出...")
    sys.exit(0)


signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)


def main():
    name = DEVICE_NAME or HOSTNAME
    log.info("=" * 50)
    log.info("设备名: %s  |  主机名: %s", name, HOSTNAME)
    log.info("服务地址: %s  |  指令端口: %d", BASE_URL, FLASK_PORT)
    log.info("心跳间隔: %ds  |  KV: %s  |  KV 前缀: %s", INTERVAL, "开" if REPORT_KV else "关", kv_prefix())
    log.info("=" * 50)

    # 启动 Flask 指令监听（后台线程）
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 注册
    if not register():
        log.error("注册失败，30s 后重试...")
        time.sleep(30)
        if not register():
            log.critical("注册反复失败，退出")
            sys.exit(1)

    # 首次 KV
    if REPORT_KV:
        try:
            report_kv()
            log.info("首次 KV 上报完成")
        except Exception as e:
            log.warning("首次 KV 失败: %s", e)

    # 心跳循环
    kv_cnt = 0
    while True:
        try:
            heartbeat()
            if REPORT_KV:
                kv_cnt += 1
                if kv_cnt >= KV_INTERVAL:
                    report_kv()
                    kv_cnt = 0
        except Exception as e:
            log.error("异常: %s", e, exc_info=True)

        for _ in range(INTERVAL * 10):
            time.sleep(0.1)


if __name__ == "__main__":
    main()
