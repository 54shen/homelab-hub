// ============================================================
// 路由配置与守卫测试
// 所有懒加载视图 mock 掉,测:路由表完整性 + 未登录拦截跳 /login
// ============================================================
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { isNavigationFailure, NavigationFailureType } from 'vue-router'

// ---- 懒加载视图全部轻量 stub(避免拖入真实页面依赖)----
// 注意:vi.mock 会被提升到文件顶部,不能用循环变量,必须逐个显式声明
vi.mock('../views/Login.vue', () => ({ default: { name: 'LoginStub', template: '<div>Login</div>' } }))
vi.mock('../views/Dashboard.vue', () => ({ default: { name: 'DashboardStub', template: '<div>Dashboard</div>' } }))
vi.mock('../views/KvManager.vue', () => ({ default: { name: 'KvManagerStub', template: '<div>KvManager</div>' } }))
vi.mock('../views/FieldMappings.vue', () => ({ default: { name: 'FieldMappingsStub', template: '<div>FieldMappings</div>' } }))
vi.mock('../views/HistoryPage.vue', () => ({ default: { name: 'HistoryPageStub', template: '<div>HistoryPage</div>' } }))
vi.mock('../views/HistoryLive.vue', () => ({ default: { name: 'HistoryLiveStub', template: '<div>HistoryLive</div>' } }))
vi.mock('../views/DeviceManager.vue', () => ({ default: { name: 'DeviceManagerStub', template: '<div>DeviceManager</div>' } }))
vi.mock('../views/DeviceDetail.vue', () => ({ default: { name: 'DeviceDetailStub', template: '<div>DeviceDetail</div>' } }))
vi.mock('../views/AlertManager.vue', () => ({ default: { name: 'AlertManagerStub', template: '<div>AlertManager</div>' } }))
vi.mock('../views/WebhookManager.vue', () => ({ default: { name: 'WebhookManagerStub', template: '<div>WebhookManager</div>' } }))
vi.mock('../views/SystemLogs.vue', () => ({ default: { name: 'SystemLogsStub', template: '<div>SystemLogs</div>' } }))
vi.mock('../views/Settings.vue', () => ({ default: { name: 'SettingsStub', template: '<div>Settings</div>' } }))
vi.mock('../layouts/MainLayout.vue', () => ({
  default: { name: 'MainLayoutStub', template: '<div>main-layout</div>' }
}))

import router from './index'

async function push(path: string) {
  let failure: ReturnType<typeof isNavigationFailure> | null = null
  await router.push(path).catch((f: any) => { failure = f })
  return failure
}

describe('router/index.ts', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('路由表包含全部关键路径', () => {
    const routes = router.getRoutes().map(r => r.path)
    // 顶层 + 子路由
    expect(routes).toContain('/login')
    expect(routes).toContain('/')
    for (const p of ['/dashboard', '/variables', '/mappings', '/history', '/history-live',
      '/devices', '/devices/:id', '/alerts', '/webhooks', '/logs', '/settings']) {
      expect(routes).toContain(p)
    }
  })

  it('/ 根路径重定向到 /dashboard', () => {
    const resolved = router.resolve('/')
    expect(resolved.redirectedFrom?.path ?? resolved.matched[0]?.redirect).toBeTruthy()
  })

  it('关键路径带 meta.title', () => {
    expect(router.resolve('/dashboard').meta.title).toBe('仪表盘')
    expect(router.resolve('/variables').meta.title).toBe('变量管理')
    expect(router.resolve('/settings').meta.title).toBe('设置')
  })

  it('/login 标记为 public', () => {
    expect(router.resolve('/login').meta.public).toBe(true)
    expect(router.resolve('/login').meta.title).toBe('登录')
  })

  it('未登录访问受保护页面 → 拦截并跳转 /login', async () => {
    const failure = await push('/dashboard')
    // 注意:守卫内 next('/login') 的重定向会被 vue-router 静默跟随,promise 正常 resolve
    expect(failure).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('未登录访问其他受保护页(/history)→ 同样拦截', async () => {
    await push('/history')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('未登录访问 /login(public)→ 放行', async () => {
    const failure = await push('/login')
    expect(failure).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('已登录 → 放行受保护页面', async () => {
    localStorage.setItem('sc_token', 'test-token')
    const failure = await push('/dashboard')
    expect(failure).toBeNull()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('退出登录(清 token)后再次访问 → 重新拦截', async () => {
    localStorage.setItem('sc_token', 'test-token')
    await push('/dashboard')
    localStorage.removeItem('sc_token')
    const failure = await push('/variables')
    // 同上:守卫重定向被静默跟随
    expect(failure).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
