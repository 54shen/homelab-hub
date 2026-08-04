// ============================================================
// API 层测试:拦截器(Token 附加 / 401 处理) + 各 API 对象的方法映射
// ============================================================
import { beforeEach, describe, expect, it, vi } from 'vitest'

const reqUse = vi.hoisted(() => vi.fn())
const resUse = vi.hoisted(() => vi.fn())
const httpMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  interceptors: {
    request: { use: reqUse },
    response: { use: resUse }
  }
}))
vi.mock('axios', () => ({
  default: { create: vi.fn(() => httpMock) }
}))

import {
  alertApi, authApi, dashboardApi, deviceApi, fieldMappingApi, historyApi, kvApi, logApi, settingsApi, webhookApi
} from './index'

// 拦截器回调在模块 import 时注册 —— 必须在文件顶层捕获
// (beforeEach 里的 mockReset 会清掉注册记录,不能放在那时取)
const requestHandler = reqUse.mock.calls[0][0]
const [responseSuccess, responseError] = resUse.mock.calls[0]

describe('拦截器', () => {
  beforeEach(() => {
    localStorage.clear()
    httpMock.get.mockReset()
    httpMock.post.mockReset()
    httpMock.put.mockReset()
    httpMock.delete.mockReset()
  })

  it('请求拦截器:有 token 时附加 Authorization 头', () => {
    localStorage.setItem('sc_token', 'sk-test')
    const config = { headers: {} }
    requestHandler(config)
    expect(config.headers.Authorization).toBe('Bearer sk-test')
  })

  it('请求拦截器:无 token 时不附加', () => {
    const config = { headers: {} }
    requestHandler(config)
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('响应拦截器:401 时清空凭据并跳登录页', () => {
    localStorage.setItem('sc_token', 'sk-test')
    expect(responseSuccess).toBeTypeOf('function')

    // 模拟 window.location(jsdom 不支持真实跳转)
    const location = { pathname: '/dashboard', href: '' }
    Object.defineProperty(window, 'location', { value: location, writable: true })

    responseError({ response: { status: 401 } }).catch(() => {})
    expect(localStorage.getItem('sc_token')).toBeNull()
    expect(location.href).toBe('/login')
  })

  it('响应拦截器:已在登录页时不重复跳转', () => {
    const location = { pathname: '/login', href: '' }
    Object.defineProperty(window, 'location', { value: location, writable: true })
    responseError({ response: { status: 401 } }).catch(() => {})
    expect(location.href).toBe('')
  })
})

describe('API 方法映射', () => {
  beforeEach(() => {
    httpMock.get.mockReset()
    httpMock.post.mockReset()
  })

  it('kvApi 各方法调用正确的 URL', () => {
    kvApi.list('a.')
    expect(httpMock.get).toHaveBeenCalledWith('/list', { params: { prefix: 'a.' } })
    kvApi.get('k')
    expect(httpMock.get).toHaveBeenCalledWith('/kv/k')
    kvApi.set({ key: 'k', value: '1' } as any)
    expect(httpMock.post).toHaveBeenCalledWith('/kv', { key: 'k', value: '1' })
    kvApi.delete('k')
    expect(httpMock.delete).toHaveBeenCalledWith('/kv/k')
    kvApi.exportJson('a.')
    expect(httpMock.get).toHaveBeenCalledWith('/kv/export', { params: { prefix: 'a.' }, responseType: 'blob' })
  })

  it('key 含特殊字符时正确转义', () => {
    kvApi.get('a/b?c')
    expect(httpMock.get).toHaveBeenCalledWith('/kv/a%2Fb%3Fc')
  })

  it('historyApi.trend 透传查询参数', () => {
    historyApi.trend({ key: 't.v', source: 'agent', limit: 100 })
    expect(httpMock.get).toHaveBeenCalledWith('/history/trend', {
      params: { key: 't.v', source: 'agent', limit: 100 }
    })
  })

  it('deviceApi.variables / dashboardApi.stats', () => {
    deviceApi.variables('abc123')
    expect(httpMock.get).toHaveBeenCalledWith('/devices/abc123/variables')
    dashboardApi.stats()
    expect(httpMock.get).toHaveBeenCalledWith('/dashboard/stats')
  })

  it('authApi 2FA 系列方法', () => {
    authApi.twofaStatus()
    expect(httpMock.get).toHaveBeenCalledWith('/auth/2fa/status')
    authApi.twofaConfirm('123456')
    expect(httpMock.post).toHaveBeenCalledWith('/auth/2fa/confirm', { code: '123456' })
  })

  it('alertApi / webhookApi / settingsApi / logApi / fieldMappingApi 抽样', () => {
    alertApi.toggle(5, false)
    expect(httpMock.post).toHaveBeenCalledWith('/alerts/5/toggle', { enabled: false })
    webhookApi.previewUrl('http://x')
    expect(httpMock.post).toHaveBeenCalledWith('/webhooks/preview-url', { url: 'http://x' })
    settingsApi.cleanHistory()
    expect(httpMock.post).toHaveBeenCalledWith('/settings/clean-history')
    logApi.clear()
    expect(httpMock.post).toHaveBeenCalledWith('/logs/clear')
    fieldMappingApi.unmapped()
    expect(httpMock.get).toHaveBeenCalledWith('/field-mappings/unmapped')
  })
})
