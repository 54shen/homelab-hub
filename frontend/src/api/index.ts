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
  HistoryKeyInfo,
  HistorySource,
  HistoryStats,
  KvBatchDeleteRequest,
  KvBatchRequest,
  KvEntry,
  KvHistory,
  KvSetRequest,
  SystemLog,
  TrendSeries,
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
  },
  /** TOTP 展示器:当前验证码(未配置 → configured=false) */
  totpCode() {
    return http.get<{ configured: boolean; code?: string; period_remaining?: number }>('/dashboard/totp-code')
  },
  /** TOTP 展示器:管理员录入密钥(仅 admin) */
  totpSecret(secret: string) {
    return http.put<ApiResponse>('/dashboard/totp-secret', { secret })
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
  },
  previewUrl(url: string) {
    return http.post<{ url: string }>('/webhooks/preview-url', { url })
  }
}

// ---- 历史记录 API ----

export interface HistoryListParams {
  key?: string
  search?: string
  prefix?: string
  suffix?: string
  source?: string
  start?: string
  end?: string
  /** 模糊搜索新值内容(剪切板内容搜索等) */
  value_search?: string
  page?: number
  page_size?: number
  order?: 'asc' | 'desc'
  /** 游标分页:只返回 id 小于该值的记录(实时写入下翻页不重复,翻页用) */
  before_id?: number
}

export const historyApi = {
  list(params: HistoryListParams) {
    return http.get<{ items: KvHistory[]; total: number }>('/history', { params })
  },
  keys() {
    return http.get<HistoryKeyInfo[]>('/history/keys')
  },
  sources() {
    return http.get<HistorySource[]>('/history/sources')
  },
  trend(params: { key: string; source?: string; start?: string; end?: string; limit?: number }) {
    return http.get<TrendSeries>('/history/trend', { params })
  },
  stats() {
    return http.get<HistoryStats>('/history/stats')
  },
  /** 按分钟聚合的上报频率(时间范围 = 图表缩放窗口) */
  frequency(params: { key: string; start?: string; end?: string }) {
    return http.get<Array<{ minute: string; count: number }>>('/history/frequency', { params })
  },
  /** 全部 key 按小时聚合的变更数(任意时间范围) */
  hourly(params: { start?: string; end?: string }) {
    return http.get<Array<{ hour: string; count: number }>>('/history/hourly', { params })
  },
  exportCsv(params: HistoryListParams) {
    return http.get('/history/export', { params, responseType: 'blob' })
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

// ---- 字段映射 API ----
export interface FieldMapping {
  id: number
  field_key: string
  display_name: string
}

export const fieldMappingApi = {
  list() {
    return http.get<FieldMapping[]>('/field-mappings')
  },
  create(data: { field_key: string; display_name: string }) {
    return http.post<FieldMapping>('/field-mappings', data)
  },
  update(id: number, data: { field_key?: string; display_name?: string }) {
    return http.put<FieldMapping>(`/field-mappings/${id}`, data)
  },
  delete(id: number) {
    return http.delete<ApiResponse>(`/field-mappings/${id}`)
  },
  exportTemplate() {
    return http.get('/field-mappings/export/template', { responseType: 'blob' })
  },
  importCsv(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.post<ApiResponse>('/field-mappings/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  unmapped() {
    return http.get<string[]>('/field-mappings/unmapped')
  }
}

// ---- 二次验证(TOTP) ----
export const authApi = {
  twofaStatus() {
    return http.get<{ username: string; enabled: boolean }>('/auth/2fa/status')
  },
  twofaSetup() {
    return http.post<{ secret: string; uri: string }>('/auth/2fa/setup')
  },
  twofaConfirm(code: string) {
    return http.post<ApiResponse>('/auth/2fa/confirm', { code })
  },
  twofaDisable(code: string) {
    return http.post<ApiResponse>('/auth/2fa/disable', { code })
  }
}

export default http
