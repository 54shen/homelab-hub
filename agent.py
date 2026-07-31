#!/usr/bin/env python3
# ============================================================
# Shared Center Agent — 电脑监控客户端
# 功能：注册设备 + 定时心跳上报（CPU/内存/磁盘/网络/运行时长）
# 依赖：pip install requests psutil
# 用法：python agent.py
# ============================================================

import json
import os
import sys
import time
import signal
import socket
import platform
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# ---- 依赖 ----
import requests

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[WARN] psutil 未安装，无法获取 CPU/内存/磁盘数据。安装: pip install psutil")

# ---- 日志配置 ----
LOG_FILE = Path(__file__).parent / "agent.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("agent")

# ============================================================
# 配置（优先级：环境变量 > config.json > 默认值）
# ============================================================

DEFAULTS: Dict[str, Any] = {
    "base_url": "http://localhost:8000",
    "token": "",
    # ══════════════════════════════════════════════════════════
    # ⚠️ device_name = 设备显示名，也是 KV 前缀（kv_prefix）的来源！
    #    留空则自动使用本机主机名作为 fallback。
    #    与下方 hostname（系统主机名）是两个独立字段，不会互相覆盖。
    # ══════════════════════════════════════════════════════════
    "device_name": "",              # ← KV前缀来源！设备显示名，留空=用主机名
    "hostname": socket.gethostname(),  # 系统主机名（只读，不上报为设备名）
    "device_type": "computer",
    "device_group": "PC",
    "heartbeat_interval": 30,       # 心跳间隔（秒）
    "heartbeat_timeout": 0,         # 离线超时（秒），0=使用服务端全局默认(60s)
    "report_kv": True,              # 是否同时上报 KV 变量
    "kv_prefix": "",                # KV 前缀，留空则自动使用 device_name（再为空则用主机名）
    "source": "agent",              # KV 上报时的来源标记
    "retry_times": 3,               # 失败重试次数
    "retry_delay": 5,               # 重试间隔（秒）
}


def _parse_jsonc(filepath: Path) -> dict:
    """解析 JSONC 文件（支持 // 行注释）"""
    import re
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    # 移除 // 行注释（排除 :// 如 https://，避免误伤 URL）
    text = re.sub(r'(?<!:)//.*', '', text)
    return json.loads(text)


def load_config() -> Dict[str, Any]:
    """加载配置：agent_config.json → 环境变量 → 默认值"""
    cfg = DEFAULTS.copy()

    # 1. 尝试加载 agent_config.json（支持 JSONC 注释）
    config_file = Path(__file__).parent / "agent_config.jsonc"
    if config_file.exists():
        try:
            file_cfg = _parse_jsonc(config_file)
            cfg.update(file_cfg)
            log.info(f"已加载配置文件: {config_file}")
        except Exception as e:
            log.warning(f"配置文件读取失败: {e}")

    # 2. 环境变量覆盖
    env_map = {
        "SHARED_CENTER_URL": "base_url",
        "SHARED_CENTER_TOKEN": "token",
        "AGENT_NAME": "device_name",
        "AGENT_TYPE": "device_type",
        "AGENT_GROUP": "device_group",
        "AGENT_INTERVAL": "heartbeat_interval",
        "AGENT_TIMEOUT": "heartbeat_timeout",
        "AGENT_SOURCE": "source",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            # 数字类型转换
            if cfg_key in ("heartbeat_interval", "heartbeat_timeout"):
                cfg[cfg_key] = int(val)
            elif cfg_key == "report_kv":
                cfg[cfg_key] = val.lower() in ("1", "true", "yes")
            else:
                cfg[cfg_key] = val

    # 3. 自动生成 kv_prefix（优先 device_name，为空则 fallback 到主机名）
    if not cfg["kv_prefix"]:
        name_for_prefix = cfg["device_name"] or cfg["hostname"]
        cfg["kv_prefix"] = name_for_prefix.replace("-", ".").replace(" ", ".") + "."

    return cfg


# ============================================================
# 系统信息采集
# ============================================================

def get_mac_address() -> str:
    """获取本机 MAC 地址"""
    import uuid
    try:
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
    except Exception:
        return ""


def get_local_ip() -> str:
    """获取本机局域网 IP"""
    try:
        # 尝试连接外部地址获取本机 IP（不会真正发送数据）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def get_uptime() -> str:
    """获取系统运行时长"""
    try:
        if HAS_PSUTIL:
            boot = psutil.boot_time()
            uptime_seconds = time.time() - boot
        else:
            # Windows fallback
            if platform.system() == "Windows":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                uptime_ms = kernel32.GetTickCount64()
                uptime_seconds = uptime_ms / 1000.0
            else:
                return ""
    except Exception:
        return ""

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def collect_system_info() -> Dict[str, Any]:
    """采集本机系统信息"""
    info: Dict[str, Any] = {
        "hostname": socket.gethostname(),
        "hostname_fqdn": socket.getfqdn(),
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "ip": get_local_ip(),
        "mac": get_mac_address(),
        "uptime": get_uptime(),
        "cpu": None,
        "memory": None,
        "disk": None,
        "cpu_count": os.cpu_count(),
        "cpu_count_logical": None,
        "memory_total_gb": None,
        "disk_total_gb": None,
        "boot_time": None,
    }

    if HAS_PSUTIL:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        info["cpu"] = int(cpu_percent)

        # 内存
        mem = psutil.virtual_memory()
        info["memory"] = int(mem.percent)
        info["memory_total_gb"] = round(mem.total / (1024 ** 3), 1)

        # 磁盘（根分区）
        disk = psutil.disk_usage("/")
        info["disk"] = int(disk.percent)
        info["disk_total_gb"] = round(disk.total / (1024 ** 3), 1)

        # CPU 核心数
        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["cpu_count_physical"] = psutil.cpu_count(logical=False)

        # 启动时间
        info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")

        # 网络 IO
        net_io = psutil.net_io_counters()
        info["net_sent_mb"] = round(net_io.bytes_sent / (1024 ** 2), 1)
        info["net_recv_mb"] = round(net_io.bytes_recv / (1024 ** 2), 1)

        # 进程数
        info["process_count"] = len(psutil.pids())

        # 温度（仅 Linux 常见路径，Windows 较复杂）
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        info[f"temp_{name}"] = int(entries[0].current)
        except Exception:
            pass

    return info


# ============================================================
# Agent 主逻辑
# ============================================================

class Agent:
    """设备监控 Agent —— 使用 requests.Session 直连 Shared Center"""

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.base_url = cfg["base_url"].rstrip("/")
        self.device_id: Optional[str] = None
        self._running = True

        # 创建 requests Session，预置认证 headers
        self._session = requests.Session()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if cfg["token"]:
            headers["Authorization"] = f"Bearer {cfg['token']}"
        self._session.headers.update(headers)

    # ---- HTTP 请求（带自动重试） ----
    def _post(self, path: str, data: dict, retry: int = 3, delay: int = 5) -> Optional[dict]:
        """POST 请求，自动重试（4xx 不重试，5xx/网络错误指数退避）"""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(retry + 1):
            try:
                resp = self._session.post(url, json=data, timeout=10)

                if 400 <= resp.status_code < 500:
                    log.error(f"请求失败 HTTP {resp.status_code}: {url} — {resp.text[:200]}")
                    return None

                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.Timeout as e:
                last_error = e
            except requests.exceptions.ConnectionError as e:
                last_error = e
            except requests.exceptions.RequestException as e:
                last_error = e

            if attempt < retry:
                wait = delay * (2 ** attempt)
                log.warning(f"请求失败，{wait}s 后重试 ({attempt + 1}/{retry}): {last_error}")
                time.sleep(wait)

        log.error(f"请求最终失败 (已重试 {retry} 次): {last_error}")
        return None

    # ---- 设备注册 ----
    def register(self) -> bool:
        """注册设备（重复注册会更新信息）"""
        sys_info = collect_system_info()

        payload = {
            "name": self.cfg["device_name"] or sys_info["hostname"],  # device_name 为空则用主机名
            "type": self.cfg["device_type"],
            "version": "2.0",
            "hostname": sys_info["hostname"],
            "mac": sys_info["mac"],
            "os": f"{sys_info['os']} {sys_info['os_release']}",
            "group": self.cfg["device_group"],
        }
        timeout = self.cfg.get("heartbeat_timeout", 0)
        if timeout > 0:
            payload["heartbeat_timeout"] = timeout

        result = self._post("/api/device/register", payload,
                            retry=self.cfg["retry_times"],
                            delay=self.cfg["retry_delay"])
        if result and result.get("success"):
            self.device_id = result.get("data", {}).get("device_id", "")
            log.info(f"设备注册成功: {self.cfg['device_name'] or self.cfg['hostname']} (ID: {self.device_id})")
            return True
        else:
            log.error(f"设备注册失败: {result}")
            return False

    # ---- 心跳上报 ----
    def send_heartbeat(self) -> bool:
        """发送一次心跳"""
        sys_info = collect_system_info()

        payload = {
            "name": self.cfg["device_name"] or self.cfg["hostname"],  # device_name 为空则用主机名
            "online": True,
            "cpu": sys_info["cpu"],
            "memory": sys_info["memory"],
            "disk": sys_info["disk"],
            "uptime": sys_info["uptime"],
            "ip": sys_info["ip"],
        }

        result = self._post("/api/device/heartbeat", payload,
                            retry=1, delay=2)  # 心跳重试少一些，不阻塞下次上报
        if result and result.get("success"):
            cpu_str = f"CPU:{sys_info['cpu']}%" if sys_info["cpu"] is not None else "CPU:?"
            mem_str = f"MEM:{sys_info['memory']}%" if sys_info["memory"] is not None else "MEM:?"
            disk_str = f"DISK:{sys_info['disk']}%" if sys_info["disk"] is not None else "DISK:?"
            log.info(f"♥ 心跳成功  {cpu_str}  {mem_str}  {disk_str}  IP:{sys_info['ip']}")
            return True
        else:
            log.warning(f"心跳失败: {result}")
            return False

    # ---- KV 上报 ----
    def report_kv(self) -> None:
        """上报详细系统信息为 KV 变量"""
        sys_info = collect_system_info()
        pfx = self.cfg["kv_prefix"]

        kv_items = []

        def add(key_suffix: str, value: Any, typ: str = "string"):
            kv_items.append({
                "key": pfx + key_suffix,
                "value": str(value) if value is not None else "",
                "type": typ,
            })

        # 基础信息
        add("主机名", sys_info["hostname"])
        add("操作系统", sys_info["os"])
        add("系统版本", sys_info["os_release"])
        add("系统架构", sys_info["architecture"])
        add("IP地址", sys_info["ip"])
        add("MAC地址", sys_info["mac"])
        add("运行时长", sys_info["uptime"])

        # 资源使用率
        if sys_info["cpu"] is not None:
            add("CPU使用率", sys_info["cpu"], typ="int")
        if sys_info["memory"] is not None:
            add("内存使用率", sys_info["memory"], typ="int")
        if sys_info["disk"] is not None:
            add("磁盘使用率", sys_info["disk"], typ="int")

        # 硬件信息
        if sys_info["cpu_count"]:
            add("CPU核心数", sys_info["cpu_count"], typ="int")
        if sys_info["memory_total_gb"]:
            add("内存总量_GB", sys_info["memory_total_gb"], typ="float")
        if sys_info["disk_total_gb"]:
            add("磁盘总量_GB", sys_info["disk_total_gb"], typ="float")

        # 其他
        if sys_info.get("process_count"):
            add("进程数", sys_info["process_count"], typ="int")
        if sys_info.get("net_sent_mb"):
            add("网络发送_MB", sys_info["net_sent_mb"], typ="float")
        if sys_info.get("net_recv_mb"):
            add("网络接收_MB", sys_info["net_recv_mb"], typ="float")
        if sys_info.get("boot_time"):
            add("启动时间", sys_info["boot_time"])

        # 温度
        for k, v in sys_info.items():
            if k.startswith("temp_"):
                add(f"温度_{k[5:]}", v, typ="int")

        # 每次仅上报变化的（批量写入已有值的会自然覆盖）
        source = self.cfg.get("source", "agent")
        for item in kv_items:
            self._post("/api/kv", {
                "key": item["key"],
                "value": item["value"],
                "type": item["type"],
                "source": source,
            }, retry=1, delay=2)

    # ---- 主循环 ----
    def run(self):
        """启动 Agent 主循环"""
        log.info("=" * 60)
        log.info(f"Shared Center Agent v2.0")
        log.info(f"设备名: {self.cfg['device_name'] or self.cfg['hostname']}")
        log.info(f"主机名: {self.cfg['hostname']}")
        log.info(f"类型: {self.cfg['device_type']} / {self.cfg['device_group']}")
        log.info(f"服务地址: {self.cfg['base_url']}")
        log.info(f"心跳间隔: {self.cfg['heartbeat_interval']}s")
        log.info(f"KV 上报: {'开' if self.cfg['report_kv'] else '关'}")
        log.info(f"Token: {'已设置' if self.cfg['token'] else '⚠ 未设置'}")
        log.info("=" * 60)

        # 1. 注册设备
        if not self.register():
            log.error("设备注册失败，30s 后重试...")
            time.sleep(30)
            if not self.register():
                log.critical("设备注册反复失败，退出。请检查服务地址和 Token 是否正确。")
                sys.exit(1)

        # 2. 首次上报 KV
        if self.cfg["report_kv"]:
            try:
                self.report_kv()
                log.info("首次 KV 上报完成")
            except Exception as e:
                log.warning(f"首次 KV 上报失败: {e}")

        # 3. 定时心跳循环
        kv_counter = 0
        kv_report_every = 6  # 每 6 次心跳（约 3 分钟）上报一次完整 KV

        while self._running:
            try:
                self.send_heartbeat()

                if self.cfg["report_kv"]:
                    kv_counter += 1
                    if kv_counter >= kv_report_every:
                        self.report_kv()
                        kv_counter = 0

            except Exception as e:
                log.error(f"心跳异常: {e}", exc_info=True)

            # 分段 sleep，支持优雅退出
            for _ in range(self.cfg["heartbeat_interval"]):
                if not self._running:
                    break
                time.sleep(1)

        self._shutdown()

    def stop(self):
        """停止 Agent"""
        log.info("收到停止信号，正在退出...")
        self._running = False

    def _shutdown(self):
        """优雅退出"""
        log.info("发送离线心跳...")
        try:
            self._post("/api/device/heartbeat", {
                "name": self.cfg["device_name"] or self.cfg["hostname"],  # device_name 为空则用主机名
                "online": False,
            }, retry=1, delay=1)
            log.info("已标记为离线")
        except Exception as e:
            log.warning(f"离线心跳发送失败: {e}")

        log.info("Agent 已停止")


# ============================================================
# 入口
# ============================================================

def main():
    cfg = load_config()

    # 快速校验
    if not cfg["token"]:
        log.warning(
            "未设置 Token！请通过以下方式之一设置：\n"
            "  1. 环境变量: set SHARED_CENTER_TOKEN=sk-xxx\n"
            "  2. config.json: {\"token\": \"sk-xxx\"}\n"
            "  3. 命令行: python agent.py --token sk-xxx\n"
            "（如果后端未启用认证，可以忽略此警告）"
        )

    # 命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="Shared Center Agent — 电脑监控客户端")
    parser.add_argument("--url", help="服务地址，如 http://192.168.5.232:8000")
    parser.add_argument("--token", help="API Token")
    parser.add_argument("--name", help="设备显示名（也是KV前缀！留空则用主机名）")
    parser.add_argument("--interval", type=int, help="心跳间隔（秒）")
    parser.add_argument("--no-kv", action="store_true", help="关闭 KV 上报")
    parser.add_argument("--once", action="store_true", help="仅上报一次后退出（调试用）")
    args = parser.parse_args()

    if args.url:
        cfg["base_url"] = args.url
    if args.token:
        cfg["token"] = args.token
    if args.name:
        cfg["device_name"] = args.name
    if args.interval:
        cfg["heartbeat_interval"] = args.interval
    if args.no_kv:
        cfg["report_kv"] = False

    agent = Agent(cfg)

    # 注册信号处理（优雅退出）
    def _sig_handler(signum, frame):
        agent.stop()
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    if args.once:
        # 单次模式：注册 + 心跳 + KV 后退出
        log.info("单次上报模式")
        agent.register()
        agent.send_heartbeat()
        if cfg["report_kv"]:
            agent.report_kv()
        agent._shutdown()
    else:
        agent.run()


if __name__ == "__main__":
    main()
