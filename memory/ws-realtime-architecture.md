---
name: ws-realtime-architecture
description: 全站 WebSocket 实时推送架构 — 已删除所有轮询，统一 WS 事件驱动
metadata:
  type: project
---

# WebSocket 实时推送架构

## 核心原则
- **全站数据更新统一走 WebSocket 推送**，不再使用任何定时轮询（无 1s/3s/5s 刷新）
- 顶部栏 WS 指示器：绿点"实时"（WS 已连接 + 开关 ON）、灰点"暂停"（开关 OFF）、红点"断开"（WS 断开）
- 开关状态持久化在 `localStorage.ws_realtime`（`'0'` = 关，其他 = 开）
- 开关关闭时，`useWebSocket.ts` 在 `onmessage` 中直接 return，全局静默

## WS 事件清单

### 后端 → 前端广播事件
| 事件 | 触发时机 | 消费者 |
|------|----------|--------|
| `kv.changed` | KV 变量写入 | Dashboard, KvManager, HistoryViewer |
| `kv.deleted` | KV 变量删除 | KvManager, HistoryViewer |
| `device.heartbeat` | 设备心跳上报 | Dashboard, DeviceManager, DeviceDetail |
| `device.registered` | 设备注册 | DeviceManager |
| `device.unregistered` | 设备注销 | DeviceManager |
| `alert.created` | 告警规则创建 | AlertManager |
| `alert.updated` | 告警规则更新/切换 | AlertManager |
| `alert.deleted` | 告警规则删除 | AlertManager |
| `webhook.created` | Webhook 创建 | WebhookManager |
| `webhook.updated` | Webhook 更新 | WebhookManager |
| `webhook.deleted` | Webhook 删除 | WebhookManager |
| `heartbeat` | 服务端 30s 心跳 | Dashboard（触发 stats 刷新） |

### 后端实现要点
- 广播函数 `broadcast(event, data)` 定义在 `backend/websocket_manager.py`
- 所有 CUD 操作的 endpoint 需改为 `async def` 以支持 `await broadcast(...)`
- `alert.updated` 覆盖 update 和 toggle 两种操作
- 日志（SystemLogs）目前不通过 WS 推送（写入在同步上下文中，无法 await broadcast）

## 前端页面 WS 行为

| 页面 | onMounted 加载 | WS 监听 | 效果 |
|------|---------------|---------|------|
| Dashboard | stats + recentChanges | kv.changed, heartbeat, device.heartbeat | 新变更插入顶部，stats 静默刷新 |
| DeviceManager | deviceApi.list() | device.heartbeat, device.registered/unregistered | 实时更新设备指标，注册/注销刷新列表 |
| DeviceDetail | device + variables + history | device.heartbeat（匹配设备名）| 实时更新 CPU/MEM/Disk/Vol + 图表 |
| KvManager | kvApi.list() | kv.changed, kv.deleted | 实时更新/删除行，新增时全量刷新 |
| HistoryViewer | historyApi.list() | kv.changed（无筛选时插入顶部，有筛选时全量刷新）| 实时看到新变更 |
| AlertManager | alertApi.list() + 依赖数据 | alert.* | 自动刷新规则列表 |
| WebhookManager | webhookApi.list() | webhook.* | 自动刷新列表 |
| SystemLogs | logApi.list() | 无（日志写入在同步上下文）| 仅 onMounted + 筛选变化时加载 |

## 已删除的文件
- `frontend/src/components/RefreshControl.vue` — 轮询间隔选择器
- `frontend/src/composables/useRefreshInterval.ts` — 轮询间隔状态管理

## 注意事项
- SystemLogs 页面暂无 WS 实时推送（日志写入在同步 Python 上下文中，无法 await broadcast）。如需添加，需将日志写入路径改为异步或使用线程安全的广播机制。
- echarts 仍保留在 DeviceDetail.vue 中（心跳历史图表使用真实 API 数据，非假数据）
- Dashboard 的 CPU/内存假数据图表已删除（硬编码 `[15, 22, 30, ...]` 无意义）
