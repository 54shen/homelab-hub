// ============================================================
// Shared Center — 类型定义
// ============================================================

/** KV 变量 */
export interface KvEntry {
  id: number
  key: string
  value: string
  type: 'string' | 'int' | 'float' | 'bool' | 'json'
  source: string
  updated_at: string
  expire_seconds: number | null
  retention_days: number
}

/** 设备信息 */
export interface Device {
  id: string
  name: string
  hostname: string
  type: string
  group: string
  version: string
  ip: string
  mac: string
  os: string
  online: boolean
  cpu?: number
  memory?: number
  disk?: number
  volume?: number   // 0-100 正常, -1=静音
  uptime?: string
  notes: string
  heartbeat_timeout: number
  sort_order: number
  last_heartbeat: string
  registered_at: string
}

/** 写入变量请求 */
export interface KvSetRequest {
  key: string
  value: string
  type?: string
  source?: string
  retention_days?: number
}

/** 批量写入 */
export interface KvBatchRequest {
  items: KvSetRequest[]
}

/** 批量删除 */
export interface KvBatchDeleteRequest {
  keys: string[]
}

/** API 响应 */
export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  message?: string
}

/** Dashboard 统计数据 */
export interface DashboardStats {
  total_devices: number
  online_devices: number
  total_services: number
  running_services: number
  network_status: 'online' | 'offline'
  public_ip: string
  system_health: number
}

/** 数据库状态 */
export interface DbStatus {
  file_size: string
  total_keys: number
  active_keys_24h: number
  history_count: number
}

/** 告警规则 */
export interface AlertRule {
  id: number
  name: string
  description: string
  trigger_key: string
  condition: 'eq' | 'neq' | 'gt' | 'lt' | 'changed' | 'offline' | 'stale' | 'unchanged'
  threshold: string
  action: string  // 逗号分隔多选，如 "webhook,log"
  action_target: string
  enabled: boolean
  last_triggered: string | null
  body?: string | null  // 自定义 Webhook Body 模板（覆盖 Webhook 默认模板）
}

/** Webhook 配置 */
export interface WebhookConfig {
  id: number
  name: string
  url: string
  method: 'GET' | 'POST' | 'PUT'
  headers: Record<string, string>
  body: string        // 信封（强制结构）
  body_extra: string  // 默认内容（规则未填 body 时回退）
  event_types: string[]
  enabled: boolean
  last_sent: string | null
  fail_count: number
}

/** 系统日志 */
export interface SystemLog {
  id: number
  level: 'info' | 'warn' | 'error' | 'debug'
  module: string
  message: string
  detail: string | null
  created_at: string
}

/** 时间线事件 */
export interface TimelineEvent {
  time: string
  icon: string
  title: string
  description: string
  color: string
}

/** 历史记录 */
export interface KvHistory {
  id: number
  key: string
  old_value: string | null
  new_value: string
  source: string
  retention_days: number
  changed_at: string
}
