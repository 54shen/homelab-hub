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
import subprocess
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
BASE_URL     = "https://sc.54shen.cn"
DEVICE_NAME  = "大爷的ROG"
DEVICE_TYPE  = "computer"
DEVICE_GROUP = "PC"
INTERVAL     = 5                       # 心跳间隔（秒）
REPORT_KV    = True                     # 是否上报 KV 变量
KV_INTERVAL  = 6                        # 每 N 次心跳上报一次 KV
SOURCE       = "我的agent"

# ── FRP 设备:frpc 作为独立设备上报,代码整合在本 agent 内 ──
FRP_DEVICE_NAME  = "FRP"
FRP_DEVICE_TYPE  = "frpc"
FRP_DEVICE_GROUP = "服务"
FRP_OS           = "windows_amd64"    # frp 构建平台(独立身份,不是 PC 的 os)
FRPC_TOML        = os.getenv("FRPC_TOML", r"C:\Program Files\FRP\frpc.toml")
FRPC_EXE         = os.getenv("FRPC_EXE", r"C:\Program Files\FRP\frpc.exe")
FRP_ADMIN_DEFAULT = (7501, "admin", "admin")   # frpc.toml 读取失败时的兜底

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


# ── 后台：上报音量状态 + 即时心跳 ──
def _report_state(action: str) -> None:
    """收到控制指令后立即上报音量到中枢（后台线程，不阻塞响应）"""

    def _run():
        try:
            vol = _get_volume()
            muted = vol.GetMute()
            vol_pct = int(round(vol.GetMasterVolumeLevelScalar() * 100))
            vol_val = -1 if muted else vol_pct
            pfx = kv_prefix()

            # KV 上报（静音时值为 -1）
            items = [
                {"key": pfx + "volume", "value": str(vol_val), "type": "int", "source": "command"},
            ]
            for item in items:
                post("/api/kv", item, retry=1, delay=1)
            log.info("已上报状态: 音量=%d%%  静音=%s  (触发: %s)", vol_pct, "是" if muted else "否", action)

            # 立即发送心跳（让前端 WebSocket 即时刷新音量/静音）
            info = collect()
            result = post("/api/device/heartbeat", {
                "name": DEVICE_NAME or HOSTNAME, "online": True,
                "cpu": info["cpu"], "memory": info["memory"], "disk": info["disk"],
                "volume": info.get("volume"),
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


def _fmt_uptime(secs: float) -> str:
    d = int(secs // 86400)
    h = int((secs % 86400) // 3600)
    m = int((secs % 3600) // 60)
    if d: return f"{d}d {h}h {m}m"
    if h: return f"{h}h {m}m"
    return f"{m}m"


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
    return _fmt_uptime(secs)


def frp_uptime() -> str:
    """frpc 进程自身的运行时长(独立于系统 uptime;进程不在时返回空)"""
    if not HAS_PSUTIL:
        return ""
    try:
        for p in psutil.process_iter(["name", "create_time"]):
            if (p.info["name"] or "").lower() in ("frpc", "frpc.exe"):
                return _fmt_uptime(time.time() - p.info["create_time"])
    except Exception:
        pass
    return ""


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
    # 系统音量（pycaw）— 静音时值为 -1
    try:
        vol = _get_volume()
        vol_pct = int(round(vol.GetMasterVolumeLevelScalar() * 100))
        info["volume"] = -1 if vol.GetMute() else vol_pct
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
def kv_prefix(name: str = "") -> str:
    name = name or DEVICE_NAME or HOSTNAME
    return name.replace("-", ".").replace(" ", ".") + "."


def register(name: str = "", dev_type: str = "", group: str = "", version: str = "2.0",
             hostname: str | None = None, mac: str | None = None, os_str: str | None = None) -> bool:
    """注册设备。默认采集本机信息(主设备);传 hostname/mac/os_str 时用独立身份(如 FRP 传空)"""
    info = collect()
    payload = {
        "name": name or DEVICE_NAME or HOSTNAME,
        "type": dev_type or DEVICE_TYPE,
        "version": version,
        "hostname": info["hostname"] if hostname is None else hostname,
        "mac": info["mac"] if mac is None else mac,
        "os": f"{info['os']} {info['os_release']}" if os_str is None else os_str,
        "group": group or DEVICE_GROUP,
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
        "volume": info.get("volume"),
        "uptime": info["uptime"], "ip": info["ip"],
        "source": SOURCE,
    }, retry=1, delay=2)
    if result and result.get("success"):
        vol_val = info.get("volume")
        vol_str = "🔇" if (vol_val is not None and vol_val < 0) else f"{vol_val}%"
        log.info("♥ 心跳  CPU:%s%%  MEM:%s%%  DISK:%s%%  VOL:%s  IP:%s",
                 info["cpu"], info["memory"], info["disk"],
                 vol_str,
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

    a("hostname", info["hostname"])
    a("os", info["os"])
    a("os_release", info["os_release"])
    a("architecture", info["architecture"])
    a("ip", info["ip"])
    a("mac", info["mac"])
    a("uptime", info["uptime"])
    if info["cpu"] is not None:
        a("cpu", info["cpu"], "int")
    if info["memory"] is not None:
        a("memory", info["memory"], "int")
    if info["disk"] is not None:
        a("disk", info["disk"], "int")
    if info.get("process_count"):
        a("process_count", info["process_count"], "int")
    if info.get("mem_total_gb"):
        a("mem_total_gb", info["mem_total_gb"], "float")
    if info.get("disk_total_gb"):
        a("disk_total_gb", info["disk_total_gb"], "float")
    if info.get("net_sent_mb"):
        a("net_sent_mb", info["net_sent_mb"], "float")
    if info.get("net_recv_mb"):
        a("net_recv_mb", info["net_recv_mb"], "float")
    if info.get("cpu_count"):
        a("cpu_count", info["cpu_count"], "int")
    if info.get("boot_time"):
        a("boot_time", info["boot_time"])
    if info.get("volume") is not None:
        a("volume", info["volume"], "int")
    for item in items:
        item["source"] = SOURCE
        post("/api/kv", item, retry=1, delay=2)


# ══════════════════════════════════════════════════════════════
# FRP 设备:frpc 作为独立设备上报(探测 → 心跳 → KV)
# ══════════════════════════════════════════════════════════════
def frp_admin_config() -> tuple:
    """从 frpc.toml 读取管理接口(端口/账号/密码),失败用默认值"""
    port, user, pwd = FRP_ADMIN_DEFAULT
    try:
        for line in Path(FRPC_TOML).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("admin_port"):
                port = int(line.split("=", 1)[1].strip())
            elif line.startswith("admin_user"):
                user = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("admin_pwd"):
                pwd = line.split("=", 1)[1].strip().strip('"').strip("'")
    except (OSError, ValueError):
        pass
    return port, user, pwd


def frp_version() -> str:
    """frpc -v 取版本号(启动时调用一次)"""
    try:
        out = subprocess.run([FRPC_EXE, "-v"], capture_output=True, text=True, timeout=5)
        return (out.stdout or out.stderr).strip() or "unknown"
    except Exception:
        return "unknown"


def check_frp() -> dict:
    """探测 frpc 管理接口:能返回 JSON = 进程活着且连上服务器;失败 = 挂了"""
    port, user, pwd = frp_admin_config()
    state = {"online": False, "proxies_running": 0, "proxies_total": 0, "error": ""}
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/api/status", auth=(user, pwd), timeout=3)
        if resp.status_code != 200:
            state["error"] = f"管理接口 HTTP {resp.status_code}"
            return state
        data = resp.json()
        proxies = []
        for k in ("tcp", "udp", "http", "https", "stcp", "xtcp"):
            proxies += data.get(k, [])
        state["proxies_total"] = len(proxies)
        state["proxies_running"] = sum(1 for p in proxies if p.get("status") == "running")
        state["online"] = True
    except requests.exceptions.ConnectionError:
        state["error"] = "frpc 进程未运行(连接拒绝)"
    except requests.exceptions.Timeout:
        state["error"] = "frpc 响应超时(与服务器失联)"
    except Exception as e:
        state["error"] = f"探测异常: {e}"
    return state


def heartbeat_frp(state: dict) -> bool:
    """FRP 设备心跳:online 取决于 frpc 管理接口探测结果;只带 frpc 自身指标,不带 PC 信息"""
    result = post("/api/device/heartbeat", {
        "name": FRP_DEVICE_NAME,
        "online": state["online"],
        "uptime": frp_uptime() if state["online"] else "",
        "source": SOURCE,
    }, retry=1, delay=2)
    if result and result.get("success"):
        log.info("FRP 设备心跳: %s", "🟢 运行中" if state["online"] else "🔴 已离线")
        return True
    log.warning("FRP 设备心跳失败: %s", result)
    return False


def report_kv_frp(state: dict, version: str) -> None:
    """FRP 设备的 KV 变量(键前缀 FRP.)。存活与否靠设备 online 状态表达,不另设 alive 键"""
    pfx = kv_prefix(FRP_DEVICE_NAME)
    items = [
        {"key": pfx + "proxies_running", "value": str(state["proxies_running"]), "type": "int"},
        {"key": pfx + "proxies_total", "value": str(state["proxies_total"]), "type": "int"},
        {"key": pfx + "version", "value": version, "type": "string"},
    ]
    if not state["online"] and state.get("error"):
        items.append({"key": pfx + "error", "value": state["error"], "type": "string"})
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
    log.info("FRP 设备: %s (独立设备上报,管理接口 %s)", FRP_DEVICE_NAME, FRPC_TOML)
    log.info("=" * 50)

    # 启动 Flask 指令监听（后台线程）
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 注册主设备
    if not register():
        log.error("注册失败，30s 后重试...")
        time.sleep(30)
        if not register():
            log.critical("注册反复失败，退出")
            sys.exit(1)

    # 注册 FRP 设备(失败不退出,主设备继续工作);独立身份:hostname/mac 显式传空,不带 PC 信息
    frp_ver = frp_version()
    if not register(FRP_DEVICE_NAME, FRP_DEVICE_TYPE, FRP_DEVICE_GROUP,
                    version=frp_ver, os_str=FRP_OS, hostname="", mac=""):
        log.error("FRP 设备注册失败，30s 后重试...")
        time.sleep(30)
        register(FRP_DEVICE_NAME, FRP_DEVICE_TYPE, FRP_DEVICE_GROUP,
                 version=frp_ver, os_str=FRP_OS, hostname="", mac="")

    # 首次探测 FRP
    frp_state = check_frp()

    # 首次 KV
    if REPORT_KV:
        try:
            report_kv()
            report_kv_frp(frp_state, frp_ver)
            log.info("首次 KV 上报完成")
        except Exception as e:
            log.warning("首次 KV 失败: %s", e)

    # 心跳循环
    kv_cnt = 0
    while True:
        try:
            heartbeat()
            frp_state = check_frp()
            heartbeat_frp(frp_state)
            if REPORT_KV:
                kv_cnt += 1
                if kv_cnt >= KV_INTERVAL:
                    report_kv()
                    report_kv_frp(frp_state, frp_ver)
                    kv_cnt = 0
        except Exception as e:
            log.error("异常: %s", e, exc_info=True)

        for _ in range(INTERVAL * 10):
            time.sleep(0.1)


if __name__ == "__main__":
    main()
