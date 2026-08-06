# 🏠 Shared Center 家庭服务中枢

> 家庭实验室统一数据中心 —— 连接所有设备、服务、脚本的数据交换平台。

> 本项目由 [DeepSeek-v4-Pro](https://deepseek.com) 、[Claude Code](https://claude.ai/code) 还有个超级超级重要的项目主理人联合开发

---

## ✨ 核心能力

| 能力 | 说明 |
|---|---|
| **KV 变量中心** | 设备/脚本统一读写共享数据,支持过期时间、保留天数、批量操作、JSON 导入导出 |
| **设备监控** | Agent 注册 + 心跳上报,实时查看 CPU / 内存 / 磁盘 / 音量,超时自动标记离线 |
| **历史记录** | 所有 KV 变更留痕,支持 key/来源/时间筛选、数值趋势图、统计、CSV 导出 |
| **实时推送** | WebSocket 双向实时,「变更动态」页零 API 请求,纯推送刷新 |
| **剪切板** | 内置「剪切板.内容」key(不可删除),仪表盘一键复制内容,多端 WS 实时同步 |
| **TOTP 展示器** | 每用户独立录入 TOTP 密钥(单独保存,非 KV 变量,相互隔离),仪表盘/设置页实时展示自己的 6 位验证码,点击即复制;密钥仅服务器保存、前端不可见;管理员可在用户管理中查看所有用户的验证码 |
| **告警 & Webhook** | 规则引擎(阈值/变化/离线/过期)+ HTTP 回调,自动通知 |
| **字段映射** | key → 中文显示名,全站生效(筛选下拉、表格、设备详情) |
| **Home Assistant** | HA 实体状态一键同步为 KV 变量 |
| **认证体系** | Bearer Token + Web 会话,read / write / admin 三级权限 |

## 🏗️ 架构

单机部署,四个组成部分:

```
                ┌─────────────────────────────┐
  浏览器        │  frontend  Vue3 + Naive UI   │
  :5173 ──────► │  仪表盘/变量/历史/设备/告警    │
                └──────────────┬──────────────┘
                               │ /api (REST) + /ws (WebSocket)
                ┌──────────────┴──────────────┐
  设备 Agent ──►│  backend  FastAPI + SQLite   │
  SDK 脚本 ────►│  认证 / 路由 / 调度 / 广播     │
  Home Assistant│                             │
                └─────────────────────────────┘
```

- **后端**:FastAPI + SQLAlchemy + SQLite,单进程零外部依赖(无 Redis/MySQL)
- **前端**:Vue 3 + TypeScript + Naive UI + ECharts + Vite
- **接入端**:Python Agent(SDK 客户端)、SDK、Home Assistant

## 🚀 快速开始

### 1. 后端(端口 8000)

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # 可选,默认配置也可直接运行
python main.py               # 或 uvicorn main:app --host 0.0.0.0 --port 8000
```

首次启动自动创建默认管理员 **admin / admin123**,并在终端打印 API Token,**请尽快修改默认密码**。

### 2. 前端(端口 5173)

```bash
cd frontend
npm install
npm run dev       # 开发模式,Vite 代理 /api 与 /ws → 127.0.0.1:8000
npm run build     # 生产构建(vue-tsc 类型检查 + vite)
```

浏览器打开 <http://localhost:5173> ,使用后端打印的管理员账号登录。

### 3. Agent(可选,接入一台设备)

```bash
pip install requests psutil
# 编辑 agent_config.jsonc:base_url 指向服务器,token 填 API Token
python agent.py
```

---

## 🐧 Linux 部署(systemd 开机自启)

以 `/root/homelab-hub` 为例(路径可换)。

### 1. 克隆 + 安装依赖

```bash
git clone https://github.com/54shen/homelab-hub.git
cd ~/homelab-hub/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # 国内可加 -i https://pypi.tuna.tsinghua.edu.cn/simple

cd ~/homelab-hub/frontend
npm install                               # 国内可加 --registry=https://registry.npmmirror.com

cp ~/homelab-hub/.env.example ~/homelab-hub/.env   # 可选,默认配置也能跑
```

### 2. 创建 systemd 服务

后端 —— **ExecStart 必须用 venv 里的 python**(不是系统 python3,否则依赖找不到):

```bash
cat > /etc/systemd/system/homelab-backend.service << 'EOF'
[Unit]
Description=Homelab Hub Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/homelab-hub/backend
ExecStart=/root/homelab-hub/backend/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

前端(家庭自用 dev 模式够用;长期跑建议生产模式,见第 6 节):

```bash
cat > /etc/systemd/system/homelab-frontend.service << 'EOF'
[Unit]
Description=Homelab Hub Frontend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/homelab-hub/frontend
ExecStart=/usr/bin/npm run dev
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

> ⚠ `npm` 路径不一定在 `/usr/bin`:先 `which npm` 确认;用 nvm 装的要把 ExecStart 换成完整路径(如 `/root/.nvm/versions/node/v22.x.x/bin/npm`)。

### 3. 启动 + 开机自启

```bash
systemctl daemon-reload
systemctl enable homelab-backend homelab-frontend
systemctl start homelab-backend homelab-frontend
systemctl status homelab-backend        # 确认 running
```

### 4. 访问与验证

- 前端:`http://服务器IP:5173`
- 后端健康检查:`curl http://localhost:8000/api/health` → `{"status":"ok"}`
- 首次登录:`admin / admin123`(首次启动终端会打印 API Token,请尽快改默认密码)

> 防火墙放行端口(二选一):
> - firewalld:`firewall-cmd --permanent --add-port={5173,8000}/tcp && firewall-cmd --reload`
> - ufw:`ufw allow 5173 && ufw allow 8000`

### 5. 更新与运维

```bash
# 一键全部更新:拉代码 + 装依赖 + 重启(推荐)
cd ~/homelab-hub && git pull && cd backend && venv/bin/pip install -r requirements.txt && cd ../frontend && npm install && cd .. && systemctl restart homelab-backend homelab-frontend

# 快速更新:只改后端代码时
cd ~/homelab-hub && git pull && systemctl restart homelab-backend homelab-frontend

# 看日志
journalctl -u homelab-backend -f
journalctl -u homelab-frontend -f
```

### 6. 宝塔面板反向代理(可选)

如果服务器装了宝塔面板,可以在「网站 → 反向代理」里直接添加如下配置,把前端(5173)和 WebSocket(8000)统一反代到域名/公网入口,避免暴露两个端口。

```nginx
location ^~ /ws {
    proxy_pass http://192.168.5.148:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
}

location ^~ / {
    proxy_pass http://192.168.5.148:5173;
    proxy_set_header Host 192.168.5.148;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Real-Port $remote_port;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header REMOTE-HOST $remote_addr;
    proxy_connect_timeout 60s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    # 支持websocket链接
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
}
```

要点:
- `192.168.5.148` 换成你服务器实际内网 IP
- 两块都要:`/ws` 管 WebSocket 实时推送,`/` 管前端页面 + API
- `proxy_read_timeout 86400s` 保证 WS 长连接不被 Nginx 掐断
- 若报 `$connection_upgrade` 未定义,在配置顶部加一行 `map $http_upgrade $connection_upgrade { default upgrade; '' close; }`(宝塔一般已自动生成)

---

## 📁 目录结构

```
家庭服务中枢/
├── agent.py                    # 🤖 设备监控 Agent:注册 + 定时心跳上报(CPU/内存/磁盘/网络)
├── windows-agent.py            # 🪟 Windows 专用 Agent:心跳 + KV 采集 + HTTP 指令接收(静音控制)
├── agent_config.jsonc          # Agent 配置(JSONC 支持注释;含 token,不入库)
├── .env.example                # 后端环境变量示例
├── sdk/
│   └── shared.py               # 🐍 Python SDK:零依赖,一行接入(set/get/list/heartbeat)
├── backend/                    # ⚙️ FastAPI 后端
│   ├── main.py                 # 入口:路由挂载、Token 认证中间件、登录、WebSocket、定时任务
│   ├── reset_admin.py          # 应急:重置管理员密码 / 清除 TOTP(服务器终端用)
│   ├── config.py               # 配置读取(.env)
│   ├── constants.py            # 内置常量(剪切板 key/设备,删除保护判断)
│   ├── database.py             # SQLAlchemy 引擎 + 建表
│   ├── models.py               # ORM 模型(11 张表)
│   ├── schemas.py              # Pydantic 请求/响应模型
│   ├── auth.py                 # API Token 校验
│   ├── websocket_manager.py    # WebSocket 连接管理 + 事件广播
│   ├── requirements.txt        # Python 依赖
│   ├── routers/                # API 路由(10 个模块)
│   │   ├── kv.py               #   KV 变量:读写 / 批量 / 导入导出
│   │   ├── history.py          #   历史记录:分页 / 筛选 / 趋势 / 统计 / CSV
│   │   ├── devices.py          #   设备:注册 / 心跳 / 列表 / 详情
│   │   ├── dashboard.py        #   仪表盘:统计 / 最近变更 / 数据库状态
│   │   ├── alerts.py           #   告警规则 CRUD
│   │   ├── webhooks.py         #   Webhook 配置 / 测试 / 预览
│   │   ├── logs.py             #   系统日志:查询 / 导出 / 清空
│   │   ├── settings.py         #   设置:备份 / 恢复 / 系统参数 / UI 偏好
│   │   ├── field_mappings.py   #   字段映射:key → 中文显示名
│   │   └── ha_incoming.py      #   Home Assistant 状态同步
│   ├── services/
│   │   ├── scheduler.py        # 定时任务调度
│   │   ├── cleanup.py          # 历史数据清理 + 设备离线检查
│   │   ├── alerts.py           # 告警检测引擎
│   │   └── clipboard.py        # 剪切板内置实体幂等创建(启动时)
│   └── data/                   # SQLite 数据库文件(不入库)
├── frontend/                   # 🎨 Vue 3 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts          # 开发代理:/api、/ws → 127.0.0.1:8000
│   ├── .env.example            # 前端环境变量示例
│   └── src/
│       ├── main.ts             # 入口
│       ├── App.vue
│       ├── router/index.ts     # 路由 + 登录守卫
│       ├── api/index.ts        # axios 封装(自动携带 Token)
│       ├── types/index.ts      # TypeScript 类型定义
│       ├── styles/global.css   # 主题(CSS 变量,浅色卡片风格)
│       ├── composables/        # useWebSocket / useFieldLabels / useSorter / useUISetting
│       ├── utils/clipboard.ts  # 剪切板 key 常量 + 主题/内容编解码
│       ├── layouts/MainLayout.vue
│       ├── components/         # 通用组件(见下方说明)
│       └── views/              # 页面(11 个,见下方说明)
├── memory/                     # 🧠 Claude Code 开发辅助记忆(非业务文件)
└── MEMORY.md                   # 同上
```

### 前端组件速查

| 组件 | 说明 |
|---|---|
| `AppSidebar / AppTopbar` | 侧边栏 + 顶栏(导航、主题、刷新设置) |
| `StatCard` | 仪表盘统计卡片 |
| `StatusBadge` | 在线/离线状态徽标 |
| `ClipboardPanel` | 剪切板面板(主题+内容输入 / 实时历史 / 一键复制) |
| `FilterBar` | 历史记录筛选栏(key/来源/时间,key 带字段映射 tooltip) |
| `RecordsTable` | 历史记录表格(旧值删除线 → 新值高亮,分页页码折叠) |
| `TrendChart` | ECharts 趋势折线图(数值/时长/时间戳/开关阶梯,默认 48h 窗口) |
| `HistoryModal` | 单个 key 的历史弹窗(值趋势 ⇄ 上报频率,粒度自适应,拖动扩展更早数据) |

### 页面一览

| 分组 | 页面 | 路由 | 说明 |
|---|---|---|---|
| 概览 | 仪表盘 | `/dashboard` | 统计卡片 + 设备状态(剪切板占 2×2 位)+ 变更动态,WS 实时刷新 |
| 数据 | 变量管理 | `/variables` | KV 变量增删改查、批量、导入导出(内置剪切板不可删) |
| 数据 | 字段映射 | `/mappings` | key → 中文显示名,全站生效 |
| 数据 | 历史记录 | `/history` | 筛选 + 趋势图 + 自动刷新 + 分页 |
| 数据 | 变更动态 | `/history-live` | 纯 WS 实时流,零 API 请求 |
| 设备 | 设备管理 | `/devices` | 设备列表、分组、排序、删除 |
| 设备 | 设备详情 | `/devices/:id` | 指标、变量、历史弹窗 |
| 自动化 | 告警规则 | `/alerts` | 规则 CRUD、启停 |
| 自动化 | Webhook | `/webhooks` | 配置、测试、URL 预览 |
| 系统 | 系统日志 | `/logs` | 日志查询、导出、清空 |
| 系统 | 设置 | `/settings` | Token / 用户 / 会话 / 备份恢复 / 系统参数 |

---

## 🔌 API 概览

所有端点前缀 `/api`,除公开路径外均需 `Authorization: Bearer <token>`。

### KV 变量

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/list?prefix=` | 按前缀查询变量 |
| GET | `/api/kv/{key}` | 读取单个变量 |
| POST | `/api/kv` | 写入 / 更新变量 |
| POST | `/api/kv/batch` | 批量写入 |
| DELETE | `/api/kv/{key}` | 删除变量 |
| POST | `/api/kv/batch-delete` | 批量删除 |
| GET | `/api/kv/export` | 导出全部变量 JSON |
| POST | `/api/kv/import` | 导入 JSON(可合并/覆盖) |

> 内置变量 `剪切板.内容` 删除会返回 403(单删与批量删都会跳过),导入/更新不受限。

### 历史记录

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/history` | 分页查询(key / source / 时间范围 / value_search 搜内容 / 排序) |
| GET | `/api/history/keys` | key 列表(计数 + 数值型标记,筛选下拉用) |
| GET | `/api/history/sources` | 来源统计 |
| GET | `/api/history/trend?key=` | 数值型 key 趋势点(超限自动抽稀,≤50000) |
| GET | `/api/history/stats` | 总览:总数 / 最近变更 / 近 24h 来源与小时分布 |
| GET | `/api/history/export` | 导出 CSV(带当前筛选) |

### 设备

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/device/register` | 注册设备 |
| POST | `/api/device/heartbeat` | 心跳上报(cpu/memory/disk/volume/ip) |
| GET | `/api/devices` | 设备列表 |
| GET | `/api/devices/{id}` | 设备详情 |
| GET | `/api/devices/{id}/variables` | 设备变量 |
| DELETE | `/api/devices/{id}` | 删除设备 |

### 仪表盘 / 告警 / Webhook / 字段映射 / 系统

| 模块 | 端点 |
|---|---|
| 仪表盘 | `GET /dashboard/stats`、`GET /dashboard/recent`、`GET /dashboard/db-status`、`GET /dashboard/timeline`、`GET /dashboard/totp-code`(查自己,admin 可带 user_id)、`GET|PUT /dashboard/totp-secret`(自己,admin 可带 user_id) |
| 告警 | `GET|POST /alerts`、`PUT|DELETE /alerts/{id}`、`POST /alerts/{id}/toggle` |
| Webhook | `GET|POST /webhooks`、`PUT|DELETE /webhooks/{id}`、`POST /webhooks/{id}/test`、`POST /webhooks/preview-url` |
| 字段映射 | `GET|POST /field-mappings`、`PUT|DELETE /field-mappings/{id}`、`GET /field-mappings/unmapped`、`GET /field-mappings/export/template`、`POST /field-mappings/import` |
| 系统日志 | `GET /logs`、`GET /logs/export`、`POST /logs/clear` |
| 设置 | `GET|PUT /settings/system`、`GET|PUT /settings/ui`、`POST /settings/clean-history`、`GET /settings/backup`、`POST /settings/restore` |
| Home Assistant | `POST /ha/state`、`POST /ha/states`(批量) |

### 认证 / 用户 / 会话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | Web 登录(返回 `ws-` 会话 Token) |
| PUT | `/api/auth/password` | 修改密码 |
| GET/POST/PUT/DELETE | `/api/tokens` | API Token 管理 |
| GET/POST/PUT/DELETE | `/api/users` | 用户管理 |
| GET/DELETE | `/api/sessions` | 会话管理(踢下线) |
| POST | `/api/sessions/kick-all` | 踢掉其他所有会话 |

## 🔄 WebSocket 事件

连接 `ws://host:8000/ws`(公开,无需 Token)。发送 `ping` 可收到 `pong` 保活。

| 事件 | 触发时机 | 数据 |
|---|---|---|
| `connected` | 连接成功 | `{time}` |
| `heartbeat` | 每 30 秒 | `{time}` |
| `kv.changed` | KV 写入 / 心跳携带变化 | `{key, value, old_value, source, changed_at}` |
| `kv.deleted` | KV 删除 | `{key}` |
| `kv.refresh` | HA 批量同步完成 | `{count}` |
| `device.heartbeat` | 设备心跳 | `{name, cpu, memory, disk, volume, online, ip, ...}` |
| `device.registered` / `device.unregistered` | 设备注册 / 删除 | `{name, type, group}` |
| `alert.created/updated/deleted` | 告警规则变化 | 规则对象 |
| `webhook.created/updated/deleted` | Webhook 变化 | Webhook 对象 |

## 🔐 认证与权限

- **API Token**:`Authorization: Bearer sk-xxx`(在设置页创建)
- **Web 会话**:登录后自动携带 `ws-` 会话 Token
- **三级权限**:`read`(只读)/ `write`(读写)/ `admin`(全部)
- 写操作(POST/PUT/DELETE/PATCH)要求 `write` 或 `admin`
- **用户管理仅 admin 可操作**(write 无法增删改用户/改权限,堵提权链);**管理员账号禁止删除**;用户管理里不能修改自己的密码(走「修改密码」旧密码验证模块),admin 可修改其他账户(含其他 admin)的密码
- 公开路径(免认证):`/api/health`、`/docs`、`/openapi.json`、`/redoc`、`/api/auth/login`、`/api/auth/login-mode`、`/api/auth/totp-login`、`/`、`/ws`

### 仅验证码登录(可选开关,设置页开启)

开启后登录页**默认只需输入 6 位验证码**(免账号密码):

| 用户 | 登录方式 |
|---|---|
| 已绑定 TOTP | 纯验证码(系统遍历匹配用户);或 用户名+密码+验证码(任何时候可用) |
| 未绑定 TOTP | 照常密码登录 |
| 开关关闭 | 全部照旧 |

**安全锁定**(锁定状态内存存储,重启清零):

- 纯验证码连续错 **5 次** → 纯验证码登录渠道全局锁定 **30 分钟**(用户名+密码+验证码 与密码登录不受影响);**管理员用 用户名+密码+验证码 登录成功即立即解锁**
- 用户名+密码+验证码 连续失败 **5 次**(按用户名)→ 该用户名锁定 **1 分钟**
- 一次性 ticket 机制:密码验证通过后才签发(5 分钟有效),验证码登录无法绕过密码

**应急重置脚本**(忘记密码 / 手机验证器丢失 / 被锁死时,服务器终端执行):

```bash
cd ~/homelab-hub/backend
venv/bin/python reset_admin.py
# 交互式:输入用户名(默认 admin)、新密码、是否清除 TOTP → 自动踢出所有会话
```

## 🐍 Python SDK

[sdk/shared.py](sdk/shared.py) 零依赖(纯标准库),复制到任何设备即可用:

```python
from shared import Client

client = Client(base_url="http://服务器IP:8000", token="sk-xxx")

# 读写变量
client.set("pc.ip", "192.168.5.66")
ip = client.get("pc.ip")
all_pc = client.list("pc.")              # 前缀查询

# 设备心跳
client.heartbeat("Windows-PC", online=True, cpu=32, memory=45)

# 一键上报本机 CPU/内存/磁盘
client.report_self()
```

Token 也支持环境变量:`SHARED_CENTER_URL` / `SHARED_CENTER_TOKEN`。

## 🤖 Agent

| 文件 | 适用 | 依赖 | 功能 |
|---|---|---|---|
| `agent.py` | 通用(电脑/服务器) | requests + psutil | 注册设备、定时心跳、可选上报详细 KV |
| `windows-agent.py` | Windows | requests + psutil + pycaw + flask | 心跳 + KV 采集 + HTTP 指令接收(静音控制) |

配置见 `agent_config.jsonc`(支持 `//` 注释):`base_url`、`token`、`device_name`、`heartbeat_interval` 等。
命令行参数 / 环境变量可覆盖配置文件(`--name`、`AGENT_NAME`、`SHARED_CENTER_TOKEN` 等)。

## 📋 剪切板

多端共享的局域网剪贴板:在仪表盘复制一段内容,任何一端(手机 / 电脑 / 平板)都能立刻看到并复制。

**内置实体**(首次启动自动创建,不可删除,不出现在设备列表与统计中):

| 实体 | 值 |
|---|---|
| 设备 | `剪切板`(type=clipboard,group=系统,完全隐藏) |
| Key | `剪切板.内容`(type=string,保留 10 年) |

**Value 格式**:JSON `{"t":"主题","c":"内容"}`,主题可选(为空时 `t` 为 `""`),与普通 key 完全一致 —— 支持 SDK / API 读写、历史记录页搜索、告警规则:

```python
from shared import Client
client = Client(base_url="http://服务器IP:8000", token="sk-xxx")
client.set("剪切板.内容", '{"t":"服务器告警","c":"CPU 超 90%,请检查"}')
```

**仪表盘操作**:
- 输入主题(可选)+ 内容,`Enter` 发送(输入框内 `Ctrl/⌘+Enter` 换行)
- 右侧实时历史(最近 20 条,WS 推送,多端秒级同步)
- **搜索**:历史区顶部搜索框支持按主题/内容模糊搜索全部剪切板历史(防抖 300ms,最多 50 条结果;清空恢复实时列表)
- 点击任意条目或复制按钮 → 内容复制到系统剪贴板(非 https 环境自动降级)

**注意**:与普通 key 一样,内容完全相同时重复发送不会产生新历史(值未变则静默)。

## 🏠 Home Assistant 集成

HA 实体状态变化时自动同步为中枢 KV 变量(写入 key 为 `HA.{实体名}`,来源标记 `homeassistant`),仪表盘 / 历史记录 / 趋势图立即可用。

**1. `configuration.yaml` 添加 REST 命令:**

```yaml
rest_command:
  ha_to_hub:
    url: "https://sc.54shen.cn/api/ha/state"
    method: POST
    headers:
      Authorization: "Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      Content-Type: "application/json"
    payload: '{"entity_id":"{{ entity_id }}","state":"{{ state }}","friendly_name":"{{ friendly_name }}"}'
```

**2. `automations.yaml` 创建自动化(按需增删 `entity_id`):**

```yaml
alias: 全屋设备状态同步到中枢
description: ""
triggers:
  - trigger: state
    entity_id:
      - switch.cuco_cn_961948487_v3_on_p_2_1
      - sensor.mqtt_presence_status
      - sensor.lpy_es6_server_time
      - switch.cuco_cn_943202649_v3_on_p_2_1
actions:
  - action: rest_command.ha_to_hub
    data:
      entity_id: "{{ trigger.entity_id }}"
      state: "{{ trigger.to_state.state }}"
      friendly_name: "{{ state_attr(trigger.entity_id, 'friendly_name') }}"
      unit: "{{ state_attr(trigger.entity_id, 'unit_of_measurement') or '' }}"
mode: parallel
```

要点:
- `sk-xxx` 换成设置页创建的 API Token(需 write 权限)
- `sc.54shen.cn` 域名需已反代到后端(见部署章节宝塔反代)
- 实体状态写入后 key 为 `HA.{实体名}`,如 `HA.服务器时间`

## ⚙️ 环境变量

### 后端(`.env`)

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/shared_center.db` | 数据库路径 |
| `DEFAULT_RETENTION_DAYS` | `180` | 历史数据默认保留天数(每个 key 可单独覆盖) |
| `CLEANUP_INTERVAL_HOURS` | `24` | 定时清理间隔(小时) |
| `HEARTBEAT_TIMEOUT_SECONDS` | `60` | 设备心跳超时,超过自动标记离线 |

### 前端(`frontend/.env`)

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_API_BASE` | `/api` | 后端 API 地址(开发模式走 Vite 代理) |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | WebSocket 地址(留空 = 当前页面地址) |
| `VITE_REFRESH_INTERVAL` | `0` | 全局默认自动刷新间隔(秒) |

---

## 📄 License

本项目由 [DeepSeek-v4-Pro](https://deepseek.com) 、[Claude Code](https://claude.ai/code) 还有个超级超级重要的项目主理人联合开发

[MIT License](LICENSE) — Copyright (c) 2026 54shen

可自由使用、修改、商用,只需保留版权声明。
