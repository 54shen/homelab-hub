# Shared Center

家庭实验室统一数据中心 —— 连接所有设备、服务、脚本的数据交换平台。

---

## 目录

- [项目背景](#项目背景)
- [系统架构](#系统架构)
- [技术选型](#技术选型)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [Python SDK](#python-sdk)
- [数据库设计](#数据库设计)
- [Web 管理后台](#web-管理后台)
- [项目结构](#项目结构)
- [设备接入指南](#设备接入指南)
- [开发计划](#开发计划)

---

## 项目背景

### 当前环境

| 系统 | 说明 |
|------|------|
| PVE | 虚拟化平台 |
| 飞牛 NAS | 网络存储 |
| 宝塔服务器 | Web 管理面板 |
| 公网云服务器 | 外网入口 |
| Home Assistant | 智能家居中枢 |
| 青龙面板 | 定时任务管理 |
| Windows 工作站 | 主力开发/办公机 |
| Docker | 容器化服务 |
| Python 自动化脚本 | 各类自动化 |
| 微信机器人 | 消息通知 |

### 问题

各系统之间直接调用，形成网状依赖：

```
脚本A → 直接调用 → 脚本B
```

- 耦合严重，一处改动影响多处
- IP 变化导致全部失效
- 配置分散在各处，无统一管理
- 数据格式不一致

### 解决方案

```
          Windows ──┐
           PVE ─────┤
    Home Assistant ─┤
          青龙 ─────┤
          ... ──────┤
                     ↓
              Shared Center
               (数据中心)
                     ↓
        统一 API / WebSocket / SDK
```

所有设备不再直接通信，通过 Shared Center 交换数据。

---

## 系统架构

```
                             Internet
                                |
                        公网云服务器
                                |
                          API Gateway
                                |
                     Shared Center (FastAPI)
                     ├─ SQLite 数据库
                     ├─ WebSocket 实时推送
                     └─ 定时清理/心跳检测
                                |
              ┌─────────────────┼─────────────────┐
              │                 │                 │
         Windows Agent     PVE Script     Home Assistant
              │                 │                 │
         心跳上报          变量读写          MQTT 桥接
```

### 设计原则

1. **低耦合** — 设备间禁止直接通信，统一经过数据中心
2. **数据统一** — 所有共享数据使用 `namespace.key` 格式
3. **可扩展** — 预留 Redis、PostgreSQL、MQTT 接口

---

## 技术选型

### 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | — |
| 框架 | FastAPI | 异步 Web 框架，自动生成 API 文档 |
| ORM | SQLAlchemy | 数据库操作 |
| 数据库 | SQLite | 轻量级，单文件部署 |
| 认证 | JWT Token | 设备独立 Token |
| 实时通信 | WebSocket | 变量变更、设备心跳实时推送 |
| 调度器 | APScheduler | 定时清理历史数据、心跳超时检测 |

### 前端

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 响应式 SPA |
| UI 组件库 | Naive UI | 高质量 Vue3 组件库 |
| 图表 | ECharts | 资源监控图表 |
| 图标 | Ionicons | 开源图标集 |
| HTTP 客户端 | Axios | API 请求 |
| 构建工具 | Vite 5 | 快速开发构建 |

### 部署

Docker Compose 一键部署，目录规划：

```
shared-center/
├── backend/          # FastAPI 后端
├── frontend/         # Vue3 前端
├── database/         # SQLite 数据文件
├── docker-compose.yml
└── README.md
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

### 1. 克隆项目

```bash
git clone <repo-url>
cd shared-center
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

后端运行在 `http://localhost:8000`

首次启动会自动创建数据库并生成 Admin Token：

```
==================================================
  默认 Admin Token: sk-xxxxxxxxxxxxxxxxxxxxxxxxxx
  请妥善保存！
==================================================
```

API 文档自动生成：`http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`

Vite 自动代理 `/api` 请求到后端 `http://localhost:8000`

### 4. 生产构建

```bash
# 前端
cd frontend && npm run build   # 输出到 dist/

# 后端
cd backend && python main.py   # 直接运行或用 gunicorn
```

---

## API 文档

### 基础信息

- 基础路径: `/api`
- 认证方式: **写操作**（POST/PUT/DELETE）必须 `Authorization: Bearer <token>`，**读操作**（GET）无需认证
- 内容类型: `application/json`

### 端点总览（27 个）

#### KV 变量

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/list?prefix=pc.` | 前缀查询变量列表 |
| `GET` | `/api/kv/{key}` | 获取单个变量 |
| `POST` | `/api/kv` | 写入变量 |
| `POST` | `/api/kv/batch` | 批量写入 |
| `DELETE` | `/api/kv/{key}` | 删除变量 |
| `POST` | `/api/kv/batch-delete` | 批量删除 |
| `GET` | `/api/kv/export?prefix=pc.` | 导出 JSON |
| `POST` | `/api/kv/import` | 导入 JSON（文件上传） |

#### 历史记录

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/history?key=pc.cpu&start=&end=&page=1` | 查询变更历史 |
| `GET` | `/api/history/export` | 导出 CSV |

#### 设备管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/devices` | 设备列表 |
| `GET` | `/api/devices/{id}` | 设备详情 |
| `GET` | `/api/devices/{id}/variables` | 设备关联变量 |
| `POST` | `/api/device/register` | 注册设备 |
| `POST` | `/api/device/heartbeat` | 心跳上报 |
| `DELETE` | `/api/devices/{id}` | 注销设备 |

#### Dashboard

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/dashboard/stats` | 统计数据 |
| `GET` | `/api/dashboard/recent?limit=10` | 最近变更 |
| `GET` | `/api/dashboard/db-status` | 数据库状态 |
| `GET` | `/api/dashboard/timeline` | 时间线事件 |

#### 告警规则 / Webhook / 日志 / 设置

| 方法 | 路径 | 说明 |
|------|------|------|
| `CRUD` | `/api/alerts` `/api/alerts/{id}` `/api/alerts/{id}/toggle` | 告警规则 |
| `CRUD` | `/api/webhooks` `/api/webhooks/{id}` `/api/webhooks/{id}/test` | Webhook |
| `GET` | `/api/logs?level=error` | 系统日志 |
| `POST` | `/api/logs/clear` | 清空日志 |
| `POST` | `/api/settings/clean-history` | 手动清理过期数据 |
| `GET` | `/api/settings/backup` | 导出完整备份 |
| `GET` `PUT` | `/api/settings/system` | 系统配置 |

### 接口示例

**写入变量**

```bash
curl -X POST http://localhost:8000/api/kv \
  -H "Content-Type: application/json" \
  -d '{"key":"pc.cpu","value":"32","type":"int","source":"windows-agent","retention_days":180}'
```

响应：

```json
{"success": true, "message": "OK"}
```

**读取变量**

```bash
curl http://localhost:8000/api/kv/pc.cpu
```

响应：

```json
{
  "id": 1,
  "key": "pc.cpu",
  "value": "32",
  "type": "int",
  "source": "windows-agent",
  "updated_at": "2026-07-29 17:30:00",
  "expire_seconds": null,
  "retention_days": 180
}
```

**设备心跳**

```bash
curl -X POST http://localhost:8000/api/device/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"name":"Windows-PC","online":true,"cpu":32,"memory":45,"disk":60,"uptime":"2d 5h","ip":"192.168.5.66"}'
```

### WebSocket

连接地址：`ws://localhost:8000/ws`

**客户端 → 服务端**

| 消息 | 说明 |
|------|------|
| `ping` | 心跳（每 25 秒发送一次） |

**服务端 → 客户端**

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `connected` | `{time: timestamp}` | 连接建立 |
| `pong` | `{time: timestamp}` | 响应心跳 |
| `kv.changed` | `{key, value, source}` | 变量写入 |
| `kv.deleted` | `{key}` | 变量删除 |
| `device.heartbeat` | `{name, online, cpu, memory, disk}` | 设备心跳 |
| `heartbeat` | `{time: timestamp}` | 服务端 30 秒定时 |

---

## Python SDK

### 安装

```python
# 将 sdk/shared.py 复制到项目中
from shared import Client
```

### 使用

```python
# 初始化
client = Client(
    base_url="http://localhost:8000",
    token="sk-xxxxxxxx",     # 可选，后端目前未强制验证
    source="my-script"       # 数据来源标记
)

# KV 操作
client.set("pc.ip", "192.168.5.66", retention_days=180)
ip = client.get("pc.ip")                     # "192.168.5.66"
info = client.get_obj("pc.ip")               # 完整信息 dict
exists = client.exists("pc.cpu")             # True/False
all_pc = client.list("pc.")                  # 前缀查询
client.delete("temp.var")                    # 删除

# 设备管理
client.register("MyPC", typ="computer", group="PC")
client.heartbeat("MyPC", online=True, cpu=32, memory=45, disk=60)

# 一键上报本机信息（需要 psutil）
client.report_self()
```

### SDK 方法列表

| 方法 | 说明 |
|------|------|
| `set(key, value, typ, retention_days)` | 写入变量 |
| `get(key)` | 获取变量值（字符串或 None） |
| `get_obj(key)` | 获取变量完整信息（dict 或 None） |
| `delete(key)` | 删除变量 |
| `exists(key)` | 检查是否存在 |
| `list(prefix)` | 前缀查询 |
| `register(name, typ, version, ...)` | 注册设备 |
| `heartbeat(name, online, cpu, memory, ...)` | 发送心跳 |
| `report_self()` | 一键上报本机信息 |

---

## 数据库设计

### 表结构（6 张表）

#### `kv` — KV 变量存储

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `key` | TEXT UNIQUE | 变量名，如 `pc.ip` |
| `value` | TEXT | 变量值 |
| `type` | TEXT | 数据类型（string/int/float/bool/json） |
| `source` | TEXT | 数据来源 |
| `updated_at` | DATETIME | 更新时间 |
| `expire_seconds` | INTEGER | 过期时间（秒） |
| `retention_days` | INTEGER | 历史保留天数，默认 180 |

#### `kv_history` — 变更历史

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `key` | TEXT | 变量名 |
| `old_value` | TEXT | 变更前的值（新增时为 NULL） |
| `new_value` | TEXT | 变更后的值 |
| `source` | TEXT | 变更来源 |
| `changed_at` | DATETIME | 变更时间 |

#### `devices` — 设备信息

| 字段 | 说明 |
|------|------|
| `id` | 设备唯一 ID（MD5(name:type)） |
| `name` | 设备名称 |
| `hostname` | 主机名 |
| `type` | 类型（computer/server/nas/iot/cloud） |
| `group` | 分组 |
| `ip` | IP 地址 |
| `mac` | MAC 地址 |
| `os` | 操作系统 |
| `cpu` / `memory` / `disk` | 资源使用率 |
| `online` | 在线状态 |
| `last_heartbeat` | 最后心跳时间 |
| `registered_at` | 注册时间 |
| `notes` | 备注 |

#### `tokens` / `alert_rules` / `webhooks` / `system_logs`

认证 Token、告警规则、Webhook 配置、系统日志表，详见 [数据库设计文档](DEVELOPMENT.md#5-数据库设计)。

### 数据命名规范

统一格式：`模块.变量`

```
pc.ip           → 192.168.5.66
pc.hostname     → DESKTOP-ABC
pc.cpu          → 32
pc.memory       → 45
pc.online       → true

ha.mqtt         → connected
ha.status       → running

network.public_ip  → 1.2.3.4
network.frp        → true

service.xxx.status  → running
service.xxx.version → 1.2.0
```

### 历史数据保留策略

- 默认保留 **180 天**（6 个月）
- 每个 key 可通过 `retention_days` 字段自定义
- 定时任务每天凌晨扫描并清理过期记录
- 可在设置页面手动触发清理

---

## Web 管理后台

### 页面

| 页面 | 功能 |
|------|------|
| **仪表盘** | 统计卡片、CPU/内存图表（ECharts）、最近变更列表、WebSocket 实时更新 |
| **变量管理** | 表格展示、搜索、新增/编辑 Modal、批量删除、JSON 导入/导出 |
| **历史记录** | 按 key/时间筛选、old→new 对比、CSV 导出 |
| **设备管理** | 卡片/表格双视图、分组筛选、进度条指标、抽屉详情、设备注销 |
| **告警规则** | CRUD + 开关、条件（等于/大于/变更/离线）、动作（通知/Webhook/日志） |
| **Webhook** | URL 配置、事件类型选择、Headers 编辑、测试发送 |
| **系统日志** | 级别筛选（DEBUG/INFO/WARN/ERROR）、模块筛选、展开详情、CSV 导出 |
| **设置** | 系统参数、Token 管理、数据库状态、手动清理、完整备份 |

### 设计风格

- 浅色系配色，低饱和度
- 大圆角矩形（18px）
- 玻璃拟态顶栏
- 柔和微阴影
- Apple 系统字体栈
- 参考：极简 NAS / Home Assistant 风格

### 截图预览

访问 `http://localhost:5173` 查看完整界面。

---

## 项目结构

```
家庭服务中枢/
├── README.md                     # 项目说明（本文档）
├── DEVELOPMENT.md                # 开发设计文档 + 变更日志
├── PYTHON_API.md                 # Python 调用完全指南
│
├── backend/                      # 后端 (FastAPI + SQLite)
│   ├── main.py                   # 入口 + 调度器 + WebSocket
│   ├── config.py                 # 配置
│   ├── database.py               # SQLAlchemy 引擎
│   ├── models.py                 # ORM 模型 (6 张表)
│   ├── schemas.py                # Pydantic 请求/响应模型
│   ├── auth.py                   # JWT 认证
│   ├── websocket_manager.py      # WebSocket 连接管理器
│   ├── requirements.txt          # Python 依赖
│   ├── routers/                  # API 路由
│   │   ├── kv.py                 # KV 变量 API
│   │   ├── history.py            # 历史记录 API
│   │   ├── devices.py            # 设备管理 API
│   │   ├── dashboard.py          # Dashboard API
│   │   ├── alerts.py             # 告警规则 API
│   │   ├── webhooks.py           # Webhook API
│   │   ├── logs.py               # 系统日志 API
│   │   └── settings.py           # 设置 API
│   ├── services/                 # 后台服务
│   │   └── cleanup.py            # 历史清理 + 心跳超时检测
│   └── data/                     # SQLite 数据库文件（自动创建）
│       └── shared_center.db
│
├── frontend/                     # 前端 (Vue3 + Naive UI)
│   ├── index.html
│   ├── vite.config.ts            # Vite 配置 + API 代理
│   ├── package.json
│   └── src/
│       ├── main.ts               # 应用入口 + WebSocket 初始化
│       ├── App.vue               # 根组件
│       ├── types/index.ts        # TypeScript 类型定义
│       ├── api/index.ts          # API 层 (axios)
│       ├── router/index.ts       # 路由配置 (8 页面)
│       ├── styles/global.css     # 全局样式 + CSS 变量
│       ├── composables/
│       │   └── useWebSocket.ts   # WebSocket 连接管理
│       ├── layouts/
│       │   └── MainLayout.vue    # 主布局
│       ├── components/
│       │   ├── AppSidebar.vue    # 侧边导航栏
│       │   ├── AppTopbar.vue     # 顶部状态栏
│       │   ├── StatCard.vue      # 统计卡片
│       │   └── StatusBadge.vue   # 在线/离线标签
│       └── views/
│           ├── Dashboard.vue     # 仪表盘
│           ├── KvManager.vue     # 变量管理
│           ├── HistoryViewer.vue # 历史记录
│           ├── DeviceManager.vue # 设备管理
│           ├── AlertManager.vue  # 告警规则
│           ├── WebhookManager.vue# Webhook 管理
│           ├── SystemLogs.vue    # 系统日志
│           └── Settings.vue      # 设置
│
├── sdk/
│   └── shared.py                 # Python SDK
│
├── .env                          # 环境变量
├── .gitignore
└── 123.py                        # 测试脚本
```

---

## 详细调用示例

### 环境变量配置

```bash
# Python SDK 自动读取以下环境变量
export SHARED_CENTER_URL=http://192.168.5.232:8000
export SHARED_CENTER_TOKEN=sk-xxxxxxxxxxxx
```

### 一、Python SDK（推荐）

#### 1. 基础用法

```python
from shared import Client

# 初始化（优先级：参数 > 环境变量 > 默认值）
client = Client(
    base_url="http://localhost:8000",   # 可选，默认读 SHARED_CENTER_URL
    token="sk-xxx",                      # 可选，默认读 SHARED_CENTER_TOKEN
    source="my-script"                   # 数据来源标记
)

# === KV 变量操作 ===

# 写入字符串
client.set("pc.ip", "192.168.5.66")

# 写入整数（指定类型和保留天数）
client.set("pc.cpu", "32", typ="int", retention_days=30)

# 写入布尔值
client.set("pc.online", "true", typ="bool")

# 写入 JSON
client.set("config.app", '{"version":"1.0","debug":false}', typ="json")

# 读取变量值（返回字符串或 None）
ip = client.get("pc.ip")            # "192.168.5.66"
cpu = client.get("pc.cpu")          # "32"

# 读取完整信息（返回 dict 或 None）
info = client.get_obj("pc.ip")
# {"id":1, "key":"pc.ip", "value":"192.168.5.66", "type":"string", ...}

# 检查是否存在
if client.exists("pc.ip"):
    print("IP 已记录")

# 按前缀查询
all_pc_vars = client.list("pc.")    # 返回 list[dict]
for v in all_pc_vars:
    print(f"{v['key']} = {v['value']}")

# 删除变量
client.delete("temp.debug")
```

#### 2. 设备注册 + 心跳

```python
# 注册设备（首次调用，后续可重复调用更新信息）
client.register(
    name="Windows-PC",
    typ="computer",
    version="1.0",
    hostname="DESKTOP-ABC",
    mac="AA:BB:CC:DD:EE:FF",
    os_name="Windows 11",
    group="PC"                         # 分组筛选用
)

# 定时心跳上报（建议每 30 秒）
import time, psutil

while True:
    client.heartbeat(
        name="Windows-PC",
        online=True,
        cpu=int(psutil.cpu_percent()),
        memory=int(psutil.virtual_memory().percent),
        disk=int(psutil.disk_usage("/").percent),
        uptime="3d 12h",
        ip="192.168.5.66"
    )
    time.sleep(30)
```

#### 3. 一键上报本机信息

```python
# 自动获取本机 CPU/内存/磁盘/IP/主机名（需要 psutil）
result = client.report_self()
print(result)  # {"success": true, "message": "OK"}
```

### 二、curl（Shell / Bash）

#### 写入变量

```bash
# 基础写入
curl -X POST http://localhost:8000/api/kv \
  -H "Content-Type: application/json" \
  -d '{"key":"pc.cpu","value":"32","type":"int","source":"bash-script","retention_days":180}'

# 批量写入
curl -X POST http://localhost:8000/api/kv/batch \
  -H "Content-Type: application/json" \
  -d '{"items":[
    {"key":"pc.cpu","value":"32","type":"int"},
    {"key":"pc.memory","value":"45","type":"int"},
    {"key":"pc.disk","value":"60","type":"int"}
  ]}'
```

#### 读取变量

```bash
# 单个读取
curl http://localhost:8000/api/kv/pc.cpu

# 前缀查询
curl "http://localhost:8000/api/list?prefix=pc."

# 查询所有
curl http://localhost:8000/api/list
```

#### 删除变量

```bash
# 单个删除
curl -X DELETE http://localhost:8000/api/kv/pc.cpu

# 批量删除
curl -X POST http://localhost:8000/api/kv/batch-delete \
  -H "Content-Type: application/json" \
  -d '{"keys":["pc.cpu","pc.memory"]}'
```

#### 导出 / 导入

```bash
# 导出 JSON
curl "http://localhost:8000/api/kv/export?prefix=pc." -o kv_backup.json

# 导入 JSON
curl -X POST http://localhost:8000/api/kv/import \
  -F "file=@kv_backup.json"
```

#### 设备操作

```bash
# 注册设备
curl -X POST http://localhost:8000/api/device/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Windows-PC","type":"computer","version":"1.0","hostname":"DESKTOP","group":"PC"}'

# 发送心跳
curl -X POST http://localhost:8000/api/device/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"name":"Windows-PC","online":true,"cpu":32,"memory":45,"disk":60,"uptime":"2d 5h","ip":"192.168.5.66"}'

# 查看所有设备
curl http://localhost:8000/api/devices

# 查看某设备详情
curl http://localhost:8000/api/devices/83a0ad4f4930

# 注销设备
curl -X DELETE http://localhost:8000/api/devices/83a0ad4f4930
```

#### 历史记录

```bash
# 查询全部（默认最近 30 天）
curl "http://localhost:8000/api/history?page=1&page_size=20"

# 按 key 筛选
curl "http://localhost:8000/api/history?key=pc.cpu"

# 按时间范围筛选
curl "http://localhost:8000/api/history?start=2026-07-01&end=2026-07-30"

# 导出 CSV
curl "http://localhost:8000/api/history/export?key=pc.cpu" -o history.csv
```

#### Dashboard / 系统

```bash
# 统计数据
curl http://localhost:8000/api/dashboard/stats

# 最近变更
curl "http://localhost:8000/api/dashboard/recent?limit=20"

# 数据库状态
curl http://localhost:8000/api/dashboard/db-status

# 时间线
curl "http://localhost:8000/api/dashboard/timeline?limit=30"

# 系统日志
curl "http://localhost:8000/api/logs?level=error&page=1"

# 完整备份
curl http://localhost:8000/api/settings/backup -o backup.json

# 手动清理过期数据
curl -X POST http://localhost:8000/api/settings/clean-history
```

#### 告警规则

```bash
# 创建规则（PC 离线时通知）
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{"name":"PC离线告警","trigger_key":"pc.online","condition":"eq","threshold":"false","action":"notification","action_target":"admin"}'

# 查询所有规则
curl http://localhost:8000/api/alerts

# 启用/禁用
curl -X POST http://localhost:8000/api/alerts/1/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled":false}'

# 删除规则
curl -X DELETE http://localhost:8000/api/alerts/1
```

#### Webhook

```bash
# 创建（设备离线时调用企业微信）
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name":"微信通知","url":"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx","method":"POST","event_types":["device.offline","alert.triggered"]}'

# 测试发送
curl -X POST http://localhost:8000/api/webhooks/1/test
```

### 三、PowerShell（Windows 脚本）

```powershell
# 写入变量
$body = @{key="pc.ip";value="192.168.5.66";type="string";source="powershell"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/kv" -Method POST -Body $body -ContentType "application/json"

# 读取变量
$resp = Invoke-RestMethod -Uri "http://localhost:8000/api/kv/pc.ip"
Write-Host $resp.value

# 前缀查询（获取所有 PC 数据）
$vars = Invoke-RestMethod -Uri "http://localhost:8000/api/list?prefix=pc."
$vars | ForEach-Object { Write-Host "$($_.key) = $($_.value)" }

# 发送心跳
$heartbeat = @{
    name="Windows-PC"; online=$true
    cpu=(Get-Counter "\Processor(_Total)\% Processor Time").CounterSamples.CookedValue
    memory=(Get-Counter "\Memory\% Committed Bytes In Use").CounterSamples.CookedValue
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/device/heartbeat" -Method POST -Body $heartbeat -ContentType "application/json"

# 导出备份
Invoke-WebRequest -Uri "http://localhost:8000/api/settings/backup" -OutFile "D:\backup\shared_center_$(Get-Date -Format 'yyyyMMdd').json"
```

### 四、JavaScript / Node.js

```javascript
// === 写入变量 ===
await fetch("http://localhost:8000/api/kv", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    key: "pc.cpu", value: "32", type: "int",
    source: "node-script", retention_days: 180
  })
});

// === 读取变量 ===
const resp = await fetch("http://localhost:8000/api/kv/pc.cpu");
const data = await resp.json();
console.log(`${data.key} = ${data.value}`);

// === 前缀查询 ===
const list = await fetch("http://localhost:8000/api/list?prefix=pc.");
const vars = await list.json();
vars.forEach(v => console.log(`${v.key} = ${v.value}`));

// === 设备心跳 ===
await fetch("http://localhost:8000/api/device/heartbeat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    name: "NodeJS-App", online: true,
    cpu: 15, memory: 40
  })
});

// === WebSocket ===
const ws = new WebSocket("ws://localhost:8000/ws");
ws.onopen = () => console.log("WS 已连接");
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.event === "kv.changed") {
    console.log(`变量 ${msg.data.key} 更新为 ${msg.data.value}`);
  }
};
// 心跳
setInterval(() => ws.send("ping"), 25000);
```

### 五、青龙面板（JavaScript 脚本）

```javascript
// 青龙环境变量设置：SHARED_CENTER_URL、SHARED_CENTER_TOKEN

const BASE = process.env.SHARED_CENTER_URL || "http://localhost:8000";

// 写入变量
await fetch(`${BASE}/api/kv`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    key: "ql.task_status", value: "running",
    type: "string", source: "qinglong"
  })
});

// 读取变量
const resp = await fetch(`${BASE}/api/kv/pc.ip`);
const { value } = await resp.json();
console.log("当前 PC IP:", value);

// 发送通知到 Shared Center
await fetch(`${BASE}/api/kv`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    key: "ql.notification",
    value: `任务完成: ${process.env.TASK_NAME}`,
    type: "string", source: "qinglong"
  })
});
```

### 六、Home Assistant（RESTful Sensor）

```yaml
# configuration.yaml
rest:
  # 从 Shared Center 读取数据
  - resource: http://192.168.5.232:8000/api/kv/pc.cpu
    sensor:
      - name: "PC CPU"
        value_template: "{{ value_json.value }}"
        unit_of_measurement: "%"

  - resource: http://192.168.5.232:8000/api/kv/network.public_ip
    sensor:
      - name: "公网 IP"
        value_template: "{{ value_json.value }}"

# 写入数据到 Shared Center
shell_command:
  report_to_center: >
    curl -X POST http://192.168.5.232:8000/api/kv
    -H "Content-Type: application/json"
    -d '{"key":"ha.mqtt","value":"{{ states(\"binary_sensor.mqtt\") }}","type":"string","source":"homeassistant"}'
```

### 心跳超时说明

- 默认超时 **60 秒**，可在设置页修改
- 超过 2 次心跳（120 秒）未收到 → 自动标记为离线
- 后台定时任务每 60 秒检查一次

---

## 开发计划

### 第一阶段 MVP ✅ 已完成

- [x] SQLite 数据库 + 6 张表
- [x] FastAPI 后端 + 27 个 API 端点
- [x] Vue3 管理后台（8 个页面）
- [x] Python SDK
- [x] JWT Token 认证
- [x] WebSocket 实时推送
- [x] 定时清理历史数据
- [x] 设备心跳超时检测

### 第二阶段 计划中

- [ ] MQTT 桥接（接入 Home Assistant）
- [ ] Webhook 事件触发（设备离线 → 微信通知）
- [ ] 自动化规则引擎（条件 → 执行）
- [ ] WebSocket 心跳实时图表更新
- [ ] 多用户/权限细化

### 第三阶段 远期

- [ ] Redis 缓存层
- [ ] PostgreSQL 迁移（大数据量场景）
- [ ] AI 助手（自然语言查询）
- [ ] 集群部署支持
- [ ] 移动端适配

---

## License

MIT
