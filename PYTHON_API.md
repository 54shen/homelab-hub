# Shared Center — Python 调用完全指南

所有 API 端点共 27 个，覆盖三种调用方式：SDK、requests、urllib。

---

## 目录

- [00. 环境准备](#00-环境准备)
- [01. 写入变量 (SET)](#01-写入变量-set)
- [02. 读取变量 (GET)](#02-读取变量-get)
- [03. 前缀查询 (LIST)](#03-前缀查询-list)
- [04. 批量写入 (BATCH SET)](#04-批量写入-batch-set)
- [05. 删除变量 (DELETE)](#05-删除变量-delete)
- [06. 批量删除 (BATCH DELETE)](#06-批量删除-batch-delete)
- [07. 导出 JSON (EXPORT)](#07-导出-json-export)
- [08. 导入 JSON (IMPORT)](#08-导入-json-import)
- [09. 历史记录查询 (HISTORY)](#09-历史记录查询-history)
- [10. 历史记录导出 CSV](#10-历史记录导出-csv)
- [11. 设备注册 (REGISTER)](#11-设备注册-register)
- [12. 设备心跳 (HEARTBEAT)](#12-设备心跳-heartbeat)
- [13. 设备列表 (LIST DEVICES)](#13-设备列表-list-devices)
- [14. 设备详情 + 变量](#14-设备详情--变量)
- [15. 注销设备](#15-注销设备)
- [16. Dashboard 统计](#16-dashboard-统计)
- [17. Dashboard 最近变更](#17-dashboard-最近变更)
- [18. Dashboard 数据库状态](#18-dashboard-数据库状态)
- [19. Dashboard 时间线](#19-dashboard-时间线)
- [20. 告警规则 CRUD](#20-告警规则-crud)
- [21. Webhook CRUD + 测试](#21-webhook-crud--测试)
- [22. 系统日志查询](#22-系统日志查询)
- [23. 系统日志清空](#23-系统日志清空)
- [24. 清理过期数据](#24-清理过期数据)
- [25. 导出完整备份](#25-导出完整备份)
- [26. 系统配置读写](#26-系统配置读写)
- [27. WebSocket 实时连接](#27-websocket-实时连接)
- [附录A：完整设备 Agent 脚本](#附录a完整设备-agent-脚本)
- [附录B：错误处理最佳实践](#附录b错误处理最佳实践)

---

## 00. 环境准备

### 安装依赖

```bash
# SDK 方式（仅需标准库，无需额外安装）
# 直接复制 sdk/shared.py 到项目中即可

# requests 方式
pip install requests

# WebSocket 方式
pip install websockets
```

### 服务地址

```python
BASE_URL = "http://localhost:8000"      # 本地开发
# BASE_URL = "http://192.168.5.232:8000"  # 局域网
# BASE_URL = "https://your-server.com"    # 公网
```

### 三种调用方式总览

```python
# ==================================================
# 方式一：SDK（推荐，最简单）
# ==================================================
from shared import Client

client = Client(base_url=BASE_URL, token="sk-xxx", source="my-script")
client.set("pc.cpu", "32", typ="int")
cpu = client.get("pc.cpu")

# ==================================================
# 方式二：requests 库
# ==================================================
import requests

resp = requests.post(f"{BASE_URL}/api/kv", json={
    "key": "pc.cpu", "value": "32", "type": "int", "source": "my-script"
})
resp = requests.get(f"{BASE_URL}/api/kv/pc.cpu")

# ==================================================
# 方式三：urllib（标准库，零依赖）
# ==================================================
import json, urllib.request

data = json.dumps({"key":"pc.cpu","value":"32"}).encode()
req = urllib.request.Request(f"{BASE_URL}/api/kv", data=data, method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())
```

---

## 01. 写入变量 (SET)

### 端点

```
POST /api/kv
Content-Type: application/json

请求体:
{
    "key": "pc.cpu",
    "value": "32",
    "type": "int",           // 可选，默认 "string"
    "source": "windows",     // 可选，数据来源标记
    "retention_days": 180,   // 可选，历史保留天数
    "expire_seconds": null   // 可选，变量过期时间（秒）
}
```

### SDK

```python
# 基础写入
client.set("pc.cpu", "32")

# 完整参数
client.set(
    key="pc.cpu",
    value="32",
    typ="int",
    retention_days=30   # 仅保留 30 天历史
)

# 各种数据类型
client.set("pc.ip", "192.168.5.66", typ="string")
client.set("pc.cpu", "32", typ="int")
client.set("pc.memory", "45.5", typ="float")
client.set("pc.online", "true", typ="bool")
client.set("app.config", '{"version":"1.0","debug":false}', typ="json")

# 设置过期时间（10分钟后自动过期）
client.set("temp.session", "abc123", expire_seconds=600)
```

### requests

```python
import requests

def set_kv(key, value, typ="string", source="script", retention_days=180):
    resp = requests.post(f"{BASE_URL}/api/kv", json={
        "key": key,
        "value": str(value),
        "type": typ,
        "source": source,
        "retention_days": retention_days
    })
    return resp.json()  # {"success": true, "message": "OK"}

# 调用
set_kv("pc.cpu", 32, typ="int", source="windows-agent")
set_kv("pc.ip", "192.168.5.66", source="windows-agent")
set_kv("service.nginx.status", "running", source="monitor")
```

### urllib（标准库，零依赖）

```python
import json
import urllib.request

def set_kv(key, value, typ="string", source="script", retention_days=180):
    url = f"{BASE_URL}/api/kv"
    data = json.dumps({
        "key": key,
        "value": str(value),
        "type": typ,
        "source": source,
        "retention_days": retention_days
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    # 如果需要 Token 认证（生产环境）
    # req.add_header("Authorization", f"Bearer {TOKEN}")

    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# 调用
result = set_kv("pc.cpu", 32, typ="int")
print(result)  # {'success': True, 'message': 'OK'}
```

---

## 02. 读取变量 (GET)

### 端点

```
GET /api/kv/{key}

响应:
{
    "id": 1,
    "key": "pc.cpu",
    "value": "32",
    "type": "int",
    "source": "windows-agent",
    "updated_at": "2026-07-30 10:00:00",
    "expire_seconds": null,
    "retention_days": 180
}
```

### SDK

```python
# 只取 value 字符串（最常用）
cpu = client.get("pc.cpu")       # 返回 "32" 或 None

# 取完整对象
info = client.get_obj("pc.cpu")  # 返回 dict 或 None
if info:
    print(f"值: {info['value']}")
    print(f"类型: {info['type']}")
    print(f"来源: {info['source']}")
    print(f"更新时间: {info['updated_at']}")

# 检查是否存在
if client.exists("pc.cpu"):
    print("变量已存在")
else:
    print("变量不存在，需要初始化")
```

### requests

```python
import requests

def get_kv(key):
    resp = requests.get(f"{BASE_URL}/api/kv/{key}")
    if resp.status_code == 200:
        return resp.json()["value"]   # 只返回值
    elif resp.status_code == 404:
        return None                    # 不存在
    else:
        raise Exception(f"请求失败: {resp.status_code}")

# 调用
cpu = get_kv("pc.cpu")

# 取完整对象
def get_kv_obj(key):
    resp = requests.get(f"{BASE_URL}/api/kv/{key}")
    return resp.json() if resp.status_code == 200 else None
```

### urllib

```python
import json
import urllib.request
import urllib.error

def get_kv(key):
    url = f"{BASE_URL}/api/kv/{key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())["value"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

ip = get_kv("pc.ip")
print(ip)  # "192.168.5.66"
```

---

## 03. 前缀查询 (LIST)

### 端点

```
GET /api/list?prefix=pc.

响应: KV 变量数组
[
    {"id":1, "key":"pc.ip", "value":"192.168.5.66", "type":"string", ...},
    {"id":2, "key":"pc.cpu", "value":"32", "type":"int", ...},
    {"id":3, "key":"pc.memory", "value":"45", "type":"int", ...}
]

# 不传 prefix 返回全部变量
GET /api/list
```

### SDK

```python
# 查询所有 pc 相关变量
all_pc = client.list("pc.")
for item in all_pc:
    print(f"{item['key']} = {item['value']}")

# 查询所有变量
all_vars = client.list()
print(f"共 {len(all_vars)} 个变量")

# 按分类查询
network_vars = client.list("network.")
service_vars = client.list("service.")
ha_vars = client.list("ha.")
```

### requests

```python
import requests

def list_kv(prefix=""):
    resp = requests.get(f"{BASE_URL}/api/list", params={"prefix": prefix})
    return resp.json()

# 调用
for v in list_kv("pc."):
    print(f"{v['key']:20s} = {v['value']:15s}  ({v['type']})")

# 输出:
# pc.ip                = 192.168.5.66     (string)
# pc.cpu               = 32               (int)
# pc.memory            = 45               (int)
```

### urllib

```python
import json
import urllib.request
import urllib.parse

def list_kv(prefix=""):
    params = urllib.parse.urlencode({"prefix": prefix})
    url = f"{BASE_URL}/api/list?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 04. 批量写入 (BATCH SET)

### 端点

```
POST /api/kv/batch

请求体:
{
    "items": [
        {"key": "pc.cpu",  "value": "32", "type": "int"},
        {"key": "pc.memory", "value": "45", "type": "int"},
        {"key": "pc.disk", "value": "60", "type": "int"}
    ]
}
```

### SDK

```python
# SDK 没有单独的批量方法，循环调用即可
data = {
    "pc.cpu": 32,
    "pc.memory": 45,
    "pc.disk": 60,
    "pc.ip": "192.168.5.66",
    "pc.online": "true"
}
for key, val in data.items():
    client.set(key, str(val), typ="int" if isinstance(val, int) else "string")

# 或者直接用 requests 批量发送
```

### requests

```python
import requests

def batch_set(items):
    """items 格式: [{"key":"pc.cpu","value":"32","type":"int"}, ...]"""
    resp = requests.post(f"{BASE_URL}/api/kv/batch", json={"items": items})
    return resp.json()

# 调用
batch_set([
    {"key": "pc.cpu",    "value": "32", "type": "int", "source": "agent"},
    {"key": "pc.memory", "value": "45", "type": "int", "source": "agent"},
    {"key": "pc.disk",   "value": "60", "type": "int", "source": "agent"},
    {"key": "pc.ip",     "value": "192.168.5.66", "type": "string", "source": "agent"},
])
```

### urllib

```python
import json
import urllib.request

def batch_set(items):
    url = f"{BASE_URL}/api/kv/batch"
    data = json.dumps({"items": items}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 05. 删除变量 (DELETE)

### 端点

```
DELETE /api/kv/{key}
响应: {"success": true, "message": "OK"}
```

### SDK

```python
# 删除单个
client.delete("temp.debug")

# 安全删除（先检查再删）
if client.exists("temp.debug"):
    client.delete("temp.debug")
```

### requests

```python
import requests

def delete_kv(key):
    resp = requests.delete(f"{BASE_URL}/api/kv/{key}")
    return resp.json()

delete_kv("temp.debug")
```

### urllib

```python
import json
import urllib.request

def delete_kv(key):
    req = urllib.request.Request(f"{BASE_URL}/api/kv/{key}", method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 06. 批量删除 (BATCH DELETE)

### 端点

```
POST /api/kv/batch-delete

请求体: {"keys": ["pc.cpu", "pc.memory", "pc.disk"]}
```

### requests

```python
import requests

def batch_delete(keys):
    resp = requests.post(f"{BASE_URL}/api/kv/batch-delete", json={"keys": keys})
    return resp.json()

# 删除所有 temp 开头的变量
temp_vars = [v["key"] for v in list_kv("temp.")]
if temp_vars:
    batch_delete(temp_vars)
```

### urllib

```python
import json
import urllib.request

def batch_delete(keys):
    url = f"{BASE_URL}/api/kv/batch-delete"
    data = json.dumps({"keys": keys}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 07. 导出 JSON (EXPORT)

### 端点

```
GET /api/kv/export?prefix=pc.
响应: JSON 文件下载
```

### SDK

```python
# SDK 不直接支持导出，用 list + 写入文件
import json
all_vars = client.list()
with open("kv_backup.json", "w", encoding="utf-8") as f:
    json.dump(all_vars, f, ensure_ascii=False, indent=2)
```

### requests

```python
import requests

def export_kv(filepath, prefix=""):
    resp = requests.get(f"{BASE_URL}/api/kv/export", params={"prefix": prefix})
    with open(filepath, "wb") as f:
        f.write(resp.content)
    print(f"已导出到 {filepath}")

export_kv("pc_backup.json", prefix="pc.")
export_kv("all_backup.json")
```

### urllib

```python
import urllib.request
import urllib.parse

def export_kv(filepath, prefix=""):
    params = urllib.parse.urlencode({"prefix": prefix})
    url = f"{BASE_URL}/api/kv/export?{params}"
    urllib.request.urlretrieve(url, filepath)
    print(f"已导出到 {filepath}")
```

---

## 08. 导入 JSON (IMPORT)

### 端点

```
POST /api/kv/import
Content-Type: multipart/form-data
字段: file (上传 .json 文件)
```

### requests

```python
import requests

def import_kv(filepath):
    with open(filepath, "rb") as f:
        resp = requests.post(f"{BASE_URL}/api/kv/import", files={"file": f})
    return resp.json()

import_kv("pc_backup.json")
```

---

## 09. 历史记录查询 (HISTORY)

### 端点

```
GET /api/history?key=pc.cpu&start=2026-07-01&end=2026-07-30&page=1&page_size=50

响应:
{
    "items": [
        {
            "id": 1,
            "key": "pc.cpu",
            "old_value": "20",
            "new_value": "32",
            "source": "windows-agent",
            "changed_at": "2026-07-30 10:00:00"
        }
    ],
    "total": 1
}
```

### requests

```python
import requests
from datetime import datetime, timedelta

def get_history(key=None, start=None, end=None, page=1, page_size=50):
    params = {"page": page, "page_size": page_size}
    if key:
        params["key"] = key
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    resp = requests.get(f"{BASE_URL}/api/history", params=params)
    return resp.json()

# 查询某个 key 的全部历史
history = get_history(key="pc.cpu")
for h in history["items"]:
    arrow = "→"
    old = h["old_value"] or "(空)"
    print(f"{h['changed_at']}  {h['key']}: {old} {arrow} {h['new_value']}  [{h['source']}]")

# 查询最近 7 天所有变更
end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
history = get_history(start=start, end=end)
```

### urllib

```python
import json
import urllib.request
import urllib.parse

def get_history(key=None, start=None, end=None, page=1, page_size=50):
    params = {"page": page, "page_size": page_size}
    if key: params["key"] = key
    if start: params["start"] = start
    if end: params["end"] = end
    url = f"{BASE_URL}/api/history?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 10. 历史记录导出 CSV

### 端点

```
GET /api/history/export?key=pc.cpu&start=2026-07-01
响应: CSV 文件下载
```

### requests

```python
import requests

def export_history_csv(filepath, key=None, start=None, end=None):
    params = {}
    if key: params["key"] = key
    if start: params["start"] = start
    if end: params["end"] = end
    resp = requests.get(f"{BASE_URL}/api/history/export", params=params)
    with open(filepath, "wb") as f:
        f.write(resp.content)
    print(f"已导出 {len(resp.content)} 字节到 {filepath}")

export_history_csv("pc_cpu_history.csv", key="pc.cpu")
```

---

## 11. 设备注册 (REGISTER)

### 端点

```
POST /api/device/register

请求体:
{
    "name": "Windows-PC",
    "type": "computer",
    "version": "1.0",
    "hostname": "DESKTOP-ABC",
    "mac": "AA:BB:CC:DD:EE:FF",
    "os": "Windows 11",
    "group": "PC"
}

响应: {"success": true, "message": "OK", "data": {"device_id": "83a0ad4f4930"}}
```

### SDK

```python
# 完整注册
device_id = client.register(
    name="Windows-PC",
    typ="computer",
    version="1.0",
    hostname="DESKTOP-ABC",
    mac="AA:BB:CC:DD:EE:FF",
    os_name="Windows 11",
    group="PC"
)

# 最简注册（仅名称和类型）
client.register("Raspberry-Pi", typ="iot")
```

### requests

```python
import requests
import socket
import platform

def register_device(name, typ, version="1.0"):
    resp = requests.post(f"{BASE_URL}/api/device/register", json={
        "name": name,
        "type": typ,
        "version": version,
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "group": typ
    })
    return resp.json()

result = register_device("Windows-PC", "computer")
device_id = result["data"]["device_id"]
print(f"设备已注册: {device_id}")
```

### urllib

```python
import json
import urllib.request
import socket
import platform

def register_device(name, typ, version="1.0"):
    url = f"{BASE_URL}/api/device/register"
    data = json.dumps({
        "name": name,
        "type": typ,
        "version": version,
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "group": typ
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 12. 设备心跳 (HEARTBEAT)

### 端点

```
POST /api/device/heartbeat

请求体:
{
    "name": "Windows-PC",
    "online": true,
    "cpu": 32,
    "memory": 45,
    "disk": 60,
    "uptime": "2d 5h",
    "ip": "192.168.5.66"
}
```

### SDK

```python
# 基础心跳
client.heartbeat("Windows-PC", online=True)

# 完整心跳（含资源指标）
client.heartbeat(
    name="Windows-PC",
    online=True,
    cpu=32,
    memory=45,
    disk=60,
    uptime="2d 5h",
    ip="192.168.5.66"
)

# 一键上报本机信息（需 pip install psutil）
client.report_self()
```

### requests

```python
import requests
import psutil
import socket

def send_heartbeat(name):
    resp = requests.post(f"{BASE_URL}/api/device/heartbeat", json={
        "name": name,
        "online": True,
        "cpu": int(psutil.cpu_percent(interval=1)),
        "memory": int(psutil.virtual_memory().percent),
        "disk": int(psutil.disk_usage("/").percent),
        "ip": socket.gethostbyname(socket.gethostname())
    })
    return resp.json()

# 定时心跳循环
import time
while True:
    result = send_heartbeat("Windows-PC")
    print(f"心跳: {result}")
    time.sleep(30)
```

### urllib

```python
import json
import urllib.request
import time

def send_heartbeat(name, online=True, cpu=None, mem=None):
    url = f"{BASE_URL}/api/device/heartbeat"
    payload = {"name": name, "online": online}
    if cpu is not None: payload["cpu"] = cpu
    if mem is not None: payload["memory"] = mem
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 13. 设备列表 (LIST DEVICES)

### 端点

```
GET /api/devices
响应: 设备数组
```

### SDK

```python
# SDK 不直接支持，用 requests 或 urllib
```

### requests

```python
import requests

def list_devices():
    resp = requests.get(f"{BASE_URL}/api/devices")
    return resp.json()

devices = list_devices()
for d in devices:
    status = "🟢" if d["online"] else "🔴"
    print(f"{status} {d['name']:20s} {d['ip']:15s}  CPU:{d.get('cpu','?')}%  MEM:{d.get('memory','?')}%")

# 输出:
# 🟢 Windows-PC           192.168.5.66      CPU:32%  MEM:45%
# 🔴 Raspberry-Pi         192.168.5.100     CPU:?%   MEM:?%
```

### urllib

```python
import json
import urllib.request

def list_devices():
    with urllib.request.urlopen(f"{BASE_URL}/api/devices", timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 14. 设备详情 + 变量

### 端点

```
GET /api/devices/{device_id}               # 设备详情
GET /api/devices/{device_id}/variables     # 该设备上报的变量
```

### requests

```python
import requests

def get_device_detail(device_id):
    # 设备基本信息
    resp = requests.get(f"{BASE_URL}/api/devices/{device_id}")
    device = resp.json()

    # 该设备的变量
    resp = requests.get(f"{BASE_URL}/api/devices/{device_id}/variables")
    variables = resp.json()

    return device, variables

# 调用
device, variables = get_device_detail("83a0ad4f4930")
print(f"设备: {device['name']}")
print(f"在线: {device['online']}")
print(f"变量数: {len(variables)}")
for v in variables:
    print(f"  {v['key']} = {v['value']}")
```

---

## 15. 注销设备

### 端点

```
DELETE /api/devices/{device_id}
```

### requests

```python
import requests

def unregister_device(device_id):
    resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}")
    return resp.json()

# 注销所有离线设备
for d in list_devices():
    if not d["online"]:
        unregister_device(d["id"])
        print(f"已注销: {d['name']}")
```

---

## 16. Dashboard 统计

### 端点

```
GET /api/dashboard/stats

响应:
{
    "total_devices": 5,
    "online_devices": 3,
    "total_services": 8,
    "running_services": 6,
    "network_status": "online",
    "public_ip": "1.2.3.4",
    "system_health": 80
}
```

### requests

```python
import requests

def dashboard_stats():
    resp = requests.get(f"{BASE_URL}/api/dashboard/stats")
    return resp.json()

stats = dashboard_stats()
print(f"设备: {stats['online_devices']}/{stats['total_devices']} 在线")
print(f"服务: {stats['running_services']}/{stats['total_services']} 运行中")
print(f"网络: {stats['network_status']}  (公网IP: {stats['public_ip']})")
print(f"健康: {stats['system_health']}%")
```

### urllib

```python
import json
import urllib.request

def dashboard_stats():
    with urllib.request.urlopen(f"{BASE_URL}/api/dashboard/stats", timeout=10) as resp:
        return json.loads(resp.read())
```

---

## 17. Dashboard 最近变更

### 端点

```
GET /api/dashboard/recent?limit=10
响应: KvHistory 数组
```

### requests

```python
import requests

def recent_changes(limit=10):
    resp = requests.get(f"{BASE_URL}/api/dashboard/recent", params={"limit": limit})
    return resp.json()

for item in recent_changes(5):
    old = item["old_value"] or "(新增)"
    print(f"{item['changed_at']}  {item['key']}: {old} → {item['new_value']}")
```

---

## 18. Dashboard 数据库状态

### 端点

```
GET /api/dashboard/db-status

响应:
{
    "file_size": "48.0 KB",
    "total_keys": 15,
    "active_keys_24h": 12,
    "history_count": 230
}
```

### requests

```python
def db_status():
    resp = requests.get(f"{BASE_URL}/api/dashboard/db-status")
    return resp.json()

status = db_status()
print(f"数据库大小: {status['file_size']}")
print(f"变量总数:   {status['total_keys']}")
print(f"24h 活跃:   {status['active_keys_24h']}")
print(f"历史记录:   {status['history_count']} 条")
```

---

## 19. Dashboard 时间线

### 端点

```
GET /api/dashboard/timeline?limit=20
响应: {"events": [{"time":"...","icon":"...","title":"...","description":"...","color":"..."}]}
```

### requests

```python
def timeline(limit=20):
    resp = requests.get(f"{BASE_URL}/api/dashboard/timeline", params={"limit": limit})
    return resp.json()["events"]

for e in timeline(10):
    print(f"{e['time']}  {e['icon']}  {e['title']}: {e['description']}")
```

---

## 20. 告警规则 CRUD

### 端点

```
GET    /api/alerts                  # 列表
POST   /api/alerts                  # 创建
PUT    /api/alerts/{id}             # 更新
POST   /api/alerts/{id}/toggle      # 启用/禁用
DELETE /api/alerts/{id}             # 删除
```

### requests

```python
import requests

# 创建告警规则（PC 离线时通知）
def create_alert(name, trigger_key, condition, threshold, action="notification", action_target=""):
    resp = requests.post(f"{BASE_URL}/api/alerts", json={
        "name": name,
        "trigger_key": trigger_key,
        "condition": condition,
        "threshold": threshold,
        "action": action,
        "action_target": action_target
    })
    return resp.json()

create_alert(
    name="PC离线告警",
    trigger_key="pc.online",
    condition="eq",
    threshold="false",
    action="notification",
    action_target="admin"
)

# 创建告警（CPU 超过 80% 时通知）
create_alert(
    name="CPU 高负载告警",
    trigger_key="pc.cpu",
    condition="gt",
    threshold="80",
    action="webhook",
    action_target="微信通知"
)

# 查看所有规则
resp = requests.get(f"{BASE_URL}/api/alerts")
for rule in resp.json():
    enabled = "✅" if rule["enabled"] else "❌"
    print(f"{enabled} {rule['name']}: {rule['trigger_key']} {rule['condition']} {rule['threshold']}")

# 启用/禁用
def toggle_alert(rule_id, enabled):
    resp = requests.post(f"{BASE_URL}/api/alerts/{rule_id}/toggle", json={"enabled": enabled})
    return resp.json()

toggle_alert(1, False)  # 禁用规则 1

# 更新规则
def update_alert(rule_id, **kwargs):
    resp = requests.put(f"{BASE_URL}/api/alerts/{rule_id}", json=kwargs)
    return resp.json()

update_alert(1, name="新的规则名", threshold="50")

# 删除规则
resp = requests.delete(f"{BASE_URL}/api/alerts/1")
```

---

## 21. Webhook CRUD + 测试

### 端点

```
GET    /api/webhooks             # 列表
POST   /api/webhooks             # 创建
PUT    /api/webhooks/{id}        # 更新
DELETE /api/webhooks/{id}        # 删除
POST   /api/webhooks/{id}/test   # 测试发送
```

### requests

```python
import requests

# 创建 Webhook（企业微信机器人）
def create_webhook(name, url, method="POST", event_types=None, headers=None):
    resp = requests.post(f"{BASE_URL}/api/webhooks", json={
        "name": name,
        "url": url,
        "method": method,
        "event_types": event_types or [],
        "headers": headers or {}
    })
    return resp.json()

create_webhook(
    name="微信通知",
    url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    method="POST",
    event_types=["device.offline", "device.online", "alert.triggered"],
    headers={"Content-Type": "application/json"}
)

# 支持的事件类型
# device.online    - 设备上线
# device.offline   - 设备离线
# kv.changed       - 变量变更
# kv.created       - 变量新增
# kv.deleted       - 变量删除
# alert.triggered  - 告警触发

# 查看所有 Webhook
resp = requests.get(f"{BASE_URL}/api/webhooks")
for wh in resp.json():
    print(f"{'✅' if wh['enabled'] else '❌'} {wh['name']}: {wh['url']}")
    print(f"  事件: {', '.join(wh['event_types']) or '全部'}")

# 测试发送
def test_webhook(webhook_id):
    resp = requests.post(f"{BASE_URL}/api/webhooks/{webhook_id}/test")
    result = resp.json()
    if result["success"]:
        print("测试成功")
    else:
        print(f"测试失败: {result['message']}")

test_webhook(1)

# 删除
requests.delete(f"{BASE_URL}/api/webhooks/1")
```

---

## 22. 系统日志查询

### 端点

```
GET /api/logs?level=error&module=cleanup&page=1&page_size=50

响应:
{
    "items": [
        {"id":1,"level":"error","module":"cleanup","message":"...","detail":"...","created_at":"..."}
    ],
    "total": 5
}
```

### requests

```python
import requests

def get_logs(level=None, module=None, page=1, page_size=50):
    params = {"page": page, "page_size": page_size}
    if level: params["level"] = level
    if module: params["module"] = module
    resp = requests.get(f"{BASE_URL}/api/logs", params=params)
    return resp.json()

# 查看所有错误日志
result = get_logs(level="error")
for log in result["items"]:
    print(f"[{log['level'].upper()}] {log['created_at']}  {log['module']}: {log['message']}")

# 查看告警模块日志
result = get_logs(module="alert")

# 导出 CSV
def export_logs_csv(filepath, level=None):
    params = {}
    if level: params["level"] = level
    resp = requests.get(f"{BASE_URL}/api/logs/export", params=params)
    with open(filepath, "wb") as f:
        f.write(resp.content)
```

---

## 23. 系统日志清空

### 端点

```
POST /api/logs/clear
响应: {"success": true, "message": "已清空"}
```

### requests

```python
import requests

def clear_logs():
    resp = requests.post(f"{BASE_URL}/api/logs/clear")
    return resp.json()

clear_logs()
```

---

## 24. 清理过期数据

### 端点

```
POST /api/settings/clean-history
```

### requests

```python
import requests

def clean_history():
    resp = requests.post(f"{BASE_URL}/api/settings/clean-history")
    return resp.json()

result = clean_history()
print(result["message"])  # "已清理 15 条过期记录"
```

---

## 25. 导出完整备份

### 端点

```
GET /api/settings/backup
响应: JSON 文件下载（含 kv + devices 数据）
```

### requests

```python
import requests
from datetime import datetime

def export_full_backup(filepath=None):
    if filepath is None:
        filepath = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    resp = requests.get(f"{BASE_URL}/api/settings/backup")
    with open(filepath, "wb") as f:
        f.write(resp.content)
    print(f"备份完成: {filepath}")

export_full_backup()
```

---

## 26. 系统配置读写

### 端点

```
GET  /api/settings/system    # 读取配置
PUT  /api/settings/system    # 保存配置
```

### requests

```python
import requests

# 读取配置
def get_system_config():
    resp = requests.get(f"{BASE_URL}/api/settings/system")
    return resp.json()

config = get_system_config()
print(config)
# {"cleanup_interval_hours": 24, "default_retention_days": 180, "heartbeat_timeout_seconds": 60}

# 修改配置
def set_system_config(**kwargs):
    resp = requests.put(f"{BASE_URL}/api/settings/system", json=kwargs)
    return resp.json()

set_system_config(heartbeat_timeout_seconds=120, default_retention_days=365)
```

---

## 27. WebSocket 实时连接

### 端点

```
ws://localhost:8000/ws

客户端 → 服务端: 发送 "ping" 保持心跳
服务端 → 客户端: 推送事件
```

### websockets 库

```python
import asyncio
import json
import websockets

async def ws_listener():
    async with websockets.connect(f"ws://localhost:8000/ws") as ws:
        # 接收连接确认
        msg = json.loads(await ws.recv())
        print(f"已连接: {msg}")

        # 启动心跳
        async def heartbeat():
            while True:
                await asyncio.sleep(25)
                await ws.send("ping")

        asyncio.create_task(heartbeat())

        # 持续接收事件
        while True:
            msg = json.loads(await ws.recv())
            event = msg["event"]
            data = msg["data"]

            if event == "pong":
                print(f"心跳响应: {data['time']}")
            elif event == "kv.changed":
                print(f"🔵 变量变更: {data['key']} = {data['value']}  (来源: {data['source']})")
            elif event == "kv.deleted":
                print(f"🔴 变量删除: {data['key']}")
            elif event == "device.heartbeat":
                status = "在线" if data["online"] else "离线"
                cpu = f"CPU:{data.get('cpu','?')}%" if data.get('cpu') is not None else ""
                mem = f"MEM:{data.get('memory','?')}%" if data.get('memory') is not None else ""
                print(f"📡 {data['name']} {status}  {cpu}  {mem}")
            elif event == "heartbeat":
                pass  # 服务端定时心跳，可忽略
            else:
                print(f"📨 未知事件: {event} {data}")

# 运行
asyncio.run(ws_listener())
```

### websockets 同步风格（适合脚本）

```python
import asyncio
import json
import websockets

async def watch_key(key):
    """监听特定 key 的变化"""
    async with websockets.connect(f"ws://localhost:8000/ws") as ws:
        await ws.recv()  # 跳过连接确认
        print(f"开始监听 {key} ...")
        while True:
            msg = json.loads(await ws.recv())
            if msg["event"] == "kv.changed" and msg["data"]["key"] == key:
                print(f"{key} 更新为: {msg['data']['value']}")

# 监听 pc.ip 的变化
asyncio.run(watch_key("pc.ip"))
```

---

## 附录A：完整设备 Agent 脚本

以下是一个可直接部署在 Windows/Linux 上的完整监控 Agent：

```python
#!/usr/bin/env python3
"""
Shared Center Agent — 设备监控客户端
每 30 秒上报一次 CPU/内存/磁盘/网络信息
"""

import json
import time
import socket
import platform
import urllib.request
from datetime import datetime

# ===== 配置 =====
BASE_URL = "http://192.168.5.232:8000"   # 改为你的 Shared Center 地址
DEVICE_NAME = socket.gethostname()        # 设备名
DEVICE_TYPE = "computer"
DEVICE_GROUP = "PC"
INTERVAL = 30                             # 心跳间隔（秒）

# ===== 工具函数 =====
def api_post(path, data):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"API 请求失败: {e}")
        return None

def get_system_info():
    """获取本机系统信息"""
    info = {"cpu": None, "memory": None, "disk": None, "uptime": "", "ip": ""}
    try:
        import psutil
        info["cpu"] = int(psutil.cpu_percent(interval=1))
        info["memory"] = int(psutil.virtual_memory().percent)
        info["disk"] = int(psutil.disk_usage("/").percent)

        # 运行时长
        boot = psutil.boot_time()
        uptime_seconds = time.time() - boot
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        info["uptime"] = f"{days}d {hours}h" if days > 0 else f"{hours}h"
    except ImportError:
        print("提示: pip install psutil 可获取系统资源数据")

    info["ip"] = socket.gethostbyname(socket.gethostname())
    return info

# ===== 主循环 =====
def main():
    print(f"[Agent] 设备名: {DEVICE_NAME}")
    print(f"[Agent] 上报地址: {BASE_URL}")
    print(f"[Agent] 心跳间隔: {INTERVAL}s")

    # 注册设备
    result = api_post("/api/device/register", {
        "name": DEVICE_NAME,
        "type": DEVICE_TYPE,
        "version": "1.0",
        "hostname": DEVICE_NAME,
        "os": platform.system(),
        "group": DEVICE_GROUP
    })
    print(f"[Agent] 设备注册: {result}")

    # 定时心跳
    while True:
        sys_info = get_system_info()

        result = api_post("/api/device/heartbeat", {
            "name": DEVICE_NAME,
            "online": True,
            "cpu": sys_info["cpu"],
            "memory": sys_info["memory"],
            "disk": sys_info["disk"],
            "uptime": sys_info["uptime"],
            "ip": sys_info["ip"]
        })

        ts = datetime.now().strftime("%H:%M:%S")
        if result and result.get("success"):
            print(f"[{ts}] 心跳  CPU:{sys_info['cpu']}%  MEM:{sys_info['memory']}%  DISK:{sys_info['disk']}%")
        else:
            print(f"[{ts}] 心跳失败: {result}")

        # 可选：上报额外 KV 数据
        if sys_info["ip"]:
            api_post("/api/kv", {
                "key": f"{DEVICE_NAME.lower().replace('-','.')}.ip",
                "value": sys_info["ip"],
                "type": "string",
                "source": "agent"
            })

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
```

---

## 附录B：错误处理最佳实践

### 通用重试装饰器

```python
import time
import functools

def retry(max_retries=3, delay=2, backoff=2):
    """自动重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    print(f"重试 {attempt + 1}/{max_retries}: {e}，{_delay}s 后重试...")
                    time.sleep(_delay)
                    _delay *= backoff
            return None
        return wrapper
    return decorator

# 使用
@retry(max_retries=3, delay=2)
def set_kv_safe(key, value):
    return requests.post(f"{BASE_URL}/api/kv", json={
        "key": key, "value": str(value)
    }).json()

set_kv_safe("pc.cpu", 32)  # 失败会自动重试3次
```

### 完整错误处理示例

```python
import requests

class SharedCenterError(Exception):
    pass

def safe_request(method, path, **kwargs):
    """安全的 API 请求，包含完整错误处理"""
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=kwargs.pop("timeout", 10), **kwargs)
        data = resp.json()

        if isinstance(data, dict) and data.get("success") is False:
            raise SharedCenterError(f"API 返回失败: {data.get('message', '未知错误')}")

        return data
    except requests.exceptions.ConnectionError:
        raise SharedCenterError(f"无法连接到 {BASE_URL}，请检查服务是否启动")
    except requests.exceptions.Timeout:
        raise SharedCenterError(f"请求 {path} 超时")
    except requests.exceptions.RequestException as e:
        raise SharedCenterError(f"网络错误: {e}")
    except ValueError:
        raise SharedCenterError("响应不是有效的 JSON")

# 使用
try:
    result = safe_request("GET", "/api/kv/pc.cpu")
    print(result["value"])
except SharedCenterError as e:
    print(f"错误: {e}")
```
