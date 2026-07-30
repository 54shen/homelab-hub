# ============================================================
# Shared Center — Python SDK
# ============================================================
"""家庭实验室统一数据中心 Python SDK

 使用方法:
     from shared import Client

     client = Client(base_url="http://localhost:8000", token="sk-xxx")

     client.set("pc.ip", "192.168.5.66")
     ip = client.get("pc.ip")
     all_pc = client.list("pc.")

     client.heartbeat("Windows-PC", online=True, cpu=32, memory=45)
"""

import json
import os
import platform
import socket
from datetime import datetime
from typing import Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError


class Client:
    """Shared Center 客户端

    Args:
        base_url: Shared Center 服务地址
        token: API 认证 Token
    """

    def __init__(
        self,
        base_url: str = "",
        token: Optional[str] = None,
        source: str = "python-sdk"
    ):
        self.base_url = (base_url or os.environ.get("SHARED_CENTER_URL", "http://localhost:8000")).rstrip("/")
        self.token = token or os.environ.get("SHARED_CENTER_TOKEN")
        self.source = source

    # ---- 内部 ----
    def _request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except URLError as e:
            raise ConnectionError(f"请求失败: {e}") from e

    # ---- KV 操作 ----
    def set(
        self,
        key: str,
        value: Any,
        typ: str = "string",
        retention_days: int = 180
    ) -> dict:
        """写入变量"""
        return self._request("POST", "/api/kv", {
            "key": key,
            "value": str(value),
            "type": typ,
            "source": self.source,
            "retention_days": retention_days
        })

    def get(self, key: str) -> Optional[str]:
        """读取变量值"""
        try:
            resp = self._request("GET", f"/api/kv/{key}")
            return resp.get("value")
        except Exception:
            return None

    def get_obj(self, key: str) -> Optional[dict]:
        """读取变量完整信息"""
        try:
            return self._request("GET", f"/api/kv/{key}")
        except Exception:
            return None

    def delete(self, key: str) -> dict:
        """删除变量"""
        return self._request("DELETE", f"/api/kv/{key}")

    def exists(self, key: str) -> bool:
        """检查变量是否存在"""
        return self.get(key) is not None

    def list(self, prefix: str = "") -> list:
        """按前缀查询变量"""
        resp = self._request("GET", f"/api/list?prefix={prefix}")
        if isinstance(resp, list):
            return resp
        return []

    # ---- 设备操作 ----
    def register(
        self,
        name: str,
        typ: str = "computer",
        version: str = "1.0",
        hostname: str = "",
        mac: str = "",
        os_name: str = "",
        group: str = ""
    ) -> dict:
        """注册设备"""
        return self._request("POST", "/api/device/register", {
            "name": name,
            "type": typ,
            "version": version,
            "hostname": hostname or socket.gethostname(),
            "mac": mac,
            "os": os_name or platform.system(),
            "group": group
        })

    def heartbeat(
        self,
        name: str,
        online: bool = True,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        disk: Optional[int] = None,
        uptime: str = "",
        ip: str = ""
    ) -> dict:
        """发送心跳"""
        return self._request("POST", "/api/device/heartbeat", {
            "name": name,
            "online": online,
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "uptime": uptime,
            "ip": ip
        })

    # ---- 便捷方法 ----
    def report_self(self) -> dict:
        """上报本机基本信息"""
        import os
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        except ImportError:
            cpu, mem, disk = None, None, None

        return self.heartbeat(
            name=socket.gethostname(),
            online=True,
            cpu=int(cpu) if cpu is not None else None,
            memory=int(mem) if mem is not None else None,
            disk=int(disk) if disk is not None else None,
            ip=socket.gethostbyname(socket.gethostname())
        )
