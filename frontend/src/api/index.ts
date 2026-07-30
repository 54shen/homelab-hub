// ============================================================
// Shared Center — API 层
// ============================================================
import axios from 'axios'
import type {
  AlertRule,
  ApiResponse,
  DashboardStats,
  DbStatus,
  Device,
  KvBatchDeleteRequest,
  KvBatchRequest,
  KvEntry,
  KvHistory,
  KvSetRequest,
  SystemLog,
  WebhookConfig
} from '../types'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截：自动附加 Token（所有请求）
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('sc_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：401 自动跳登录
http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('sc_token')
      localStorage.removeItem('sc_username')
      localStorage.removeItem('sc_permission')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

// ---- KV 变量 API ----

export const kvApi = {
  list(prefix?: string) {
    return http.get<KvEntry[]>('/list', { params: { prefix } })
  },
  get(key: string) {
    return http.get<KvEntry>(`/kv/${encodeURIComponent(key)}`)
  },
  set(data: KvSetRequest) {
    return http.post<ApiResponse>('/kv', data)
  },
  /** 批量设置 */
  batchSet(data: KvBatchRequest) {
    return http.post<ApiResponse>('/kv/batch', data)
  },
  delete(key: string) {
    return http.delete<ApiResponse>(`/kv/${encodeURIComponent(key)}`)
  },
  /** 批量删除 */
  batchDelete(data: KvBatchDeleteRequest) {
    return http.post<ApiResponse>('/kv/batch-delete', data)
  },
  /** 导出 JSON */
  exportJson(prefix?: string) {
    return http.get('/kv/export', { params: { prefix }, responseType: 'blob' })
  },
  /** 导入 JSON */
  importJson(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.post<ApiResponse>('/kv/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

// ---- 历史记录 API ----

export const historyApi = {
  list(params: { key?: string; start?: string; end?: string; page?: number; page_size?: number }) {
    return http.get<{ items: KvHistory[]; total: number }>('/history', { params })
  },
  exportCsv(params: { key?: string; start?: string; end?: string }) {
    return http.get('/history/export', { params, responseType: 'blob' })
  }
}

// ---- 设备 API ----

export const deviceApi = {
  list() {
    return http.get<Device[]>('/devices')
  },
  get(id: string) {
    return http.get<Device>(`/devices/${id}`)
  },
  unregister(id: string) {
    return http.delete<ApiResponse>(`/devices/${id}`)
  },
  /** 设备变量 */
  variables(id: string) {
    return http.get<KvEntry[]>(`/devices/${id}/variables`)
  }
}

// ---- Dashboard API ----

export const dashboardApi = {
  stats() {
    return http.get<DashboardStats>('/dashboard/stats')
  },
  recentChanges(limit = 10) {
    return http.get<KvHistory[]>('/dashboard/recent', { params: { limit } })
  },
  dbStatus() {
    return http.get<DbStatus>('/dashboard/db-status')
  },
  /** 时间线事件 */
  timeline(limit = 20) {
    return http.get<{ events: { time: string; icon: string; title: string; description: string; color: string }[] }>('/dashboard/timeline', { params: { limit } })
  }
}

// ---- 告警规则 API ----

export const alertApi = {
  list() {
    return http.get<AlertRule[]>('/alerts')
  },
  create(data: Partial<AlertRule>) {
    return http.post<ApiResponse>('/alerts', data)
  },
  update(id: number, data: Partial<AlertRule>) {
    return http.put<ApiResponse>(`/alerts/${id}`, data)
  },
  delete(id: number) {
    return http.delete<ApiResponse>(`/alerts/${id}`)
  },
  toggle(id: number, enabled: boolean) {
    return http.post<ApiResponse>(`/alerts/${id}/toggle`, { enabled })
  }
}

// ---- Webhook API ----

export const webhookApi = {
  list() {
    return http.get<WebhookConfig[]>('/webhooks')
  },
  create(data: Partial<WebhookConfig>) {
    return http.post<ApiResponse>('/webhooks', data)
  },
  update(id: number, data: Partial<WebhookConfig>) {
    return http.put<ApiResponse>(`/webhooks/${id}`, data)
  },
  delete(id: number) {
    return http.delete<ApiResponse>(`/webhooks/${id}`)
  },
  test(id: number) {
    return http.post<ApiResponse>(`/webhooks/${id}/test`)
  }
}

// ---- 系统日志 API ----

export const logApi = {
  list(params: { level?: string; module?: string; page?: number; page_size?: number }) {
    return http.get<{ items: SystemLog[]; total: number }>('/logs', { params })
  },
  exportCsv(params: { level?: string; start?: string; end?: string }) {
    return http.get('/logs/export', { params, responseType: 'blob' })
  },
  clear() {
    return http.post<ApiResponse>('/logs/clear')
  }
}

// ---- 设置 API ----

export const settingsApi = {
  cleanHistory() {
    return http.post<ApiResponse>('/settings/clean-history')
  },
  exportBackup() {
    return http.get('/settings/backup', { responseType: 'blob' })
  },
  restoreBackup(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.post<ApiResponse>('/settings/restore', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getSystemConfig() {
    return http.get<Record<string, unknown>>('/settings/system')
  },
  saveSystemConfig(config: Record<string, unknown>) {
    return http.put<ApiResponse>('/settings/system', config)
  }
}

export default http
