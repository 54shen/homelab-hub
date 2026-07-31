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
INTERVAL     = 30                       # 心跳间隔（秒）
REPORT_KV    = True                     # 是否上报 KV 变量
KV_INTERVAL  = 6                        # 每 N 次心跳上报一次 KV
SOURCE       = "agent"

# Flask 指令监听端口
FLASK_PORT   = int(os.getenv("PC_PORT", "24868"))

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
    log.info(f"Token 已加载: {TOKEN[:16]}...")
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


def do_mute() -> dict:
    vol = _get_volume()
    if vol.GetMute():
        return {"ok": True, "muted": True, "changed": False, "message": "已经是静音状态"}
    vol.SetMute(True, None)
    log.info("收到指令 → 静音")
    return {"ok": True, "muted": True, "changed": True, "message": "已静音"}


def do_unmute() -> dict:
    vol = _get_volume()
    if not vol.GetMute():
        return {"ok": True, "muted": False, "changed": False, "message": "已经是非静音状态"}
    vol.SetMute(False, None)
    log.info("收到指令 → 取消静音")
    return {"ok": True, "muted": False, "changed": True, "message": "已取消静音"}


def _check_token() -> bool:
    data = request.json
    if not data:
        return False
    return data.get("token") == TOKEN


@flask_app.route("/mute", methods=["POST"])
def api_mute():
    if not _check_token():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify(do_mute())


@flask_app.route("/unmute", methods=["POST"])
def api_unmute():
    if not _check_token():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify(do_unmute())


@flask_app.route("/toggle", methods=["POST"])
def api_toggle():
    if not _check_token():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify(do_unmute() if is_muted() else do_mute())


@flask_app.route("/status", methods=["POST"])
def api_status():
    if not _check_token():
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    muted = is_muted()
    return jsonify({"ok": True, "muted": muted, "message": "静音" if muted else "非静音"})


def run_flask():
    log.info(f"指令监听 http://0.0.0.0:{FLASK_PORT}")
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
        "cpu": None, "memory": None, "disk": None,
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
                log.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
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
            log.warning(f"请求失败，{wait}s 后重试 ({attempt+1}/{retry}): {last}")
            time.sleep(wait)
    log.error(f"请求最终失败: {last}")
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
        log.info(f"注册成功: {name} (ID: {device_id})")
        return True
    log.error(f"注册失败: {result}")
    return False


def heartbeat() -> bool:
    info = collect()
    name = DEVICE_NAME or HOSTNAME
    result = post("/api/device/heartbeat", {
        "name": name, "online": True,
        "cpu": info["cpu"], "memory": info["memory"], "disk": info["disk"],
        "uptime": info["uptime"], "ip": info["ip"],
    }, retry=1, delay=2)
    if result and result.get("success"):
        log.info(f"♥ 心跳  CPU:{info['cpu']}%  MEM:{info['memory']}%  DISK:{info['disk']}%  IP:{info['ip']}")
        return True
    log.warning(f"心跳失败: {result}")
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
    log.info(f"设备名: {name}  |  主机名: {HOSTNAME}")
    log.info(f"服务地址: {BASE_URL}  |  指令端口: {FLASK_PORT}")
    log.info(f"心跳间隔: {INTERVAL}s  |  KV: {'开' if REPORT_KV else '关'}  |  KV 前缀: {kv_prefix()}")
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
            log.warning(f"首次 KV 失败: {e}")

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
            log.error(f"异常: {e}", exc_info=True)

        for _ in range(INTERVAL * 10):
            time.sleep(0.1)


if __name__ == "__main__":
    main()
