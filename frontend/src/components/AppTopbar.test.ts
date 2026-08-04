// ============================================================
// AppTopbar 顶栏测试
// naive-ui / vue-router / useWebSocket 均 mock,测标题 / WS 开关 / 退出
// ============================================================
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerReplace = vi.hoisted(() => vi.fn())
const routeMeta = vi.hoisted(() => ({ title: '仪表盘' }))
// WS 全局状态容器:mock 工厂执行时(此时 vue 已初始化)再创建 ref,测试经此共享引用
const wsState = vi.hoisted(() => ({ wsConnected: null as any, wsRealtime: null as any }))

vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { class: 'n-button', onClick: () => emit('click') }, slots.default?.())
    }
  })
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: routeMeta }),
  useRouter: () => ({ replace: routerReplace })
}))

vi.mock('../composables/useWebSocket', () => {
  const wsConnected = ref(false)
  const wsRealtime = ref(true)
  wsState.wsConnected = wsConnected
  wsState.wsRealtime = wsRealtime
  return { wsConnected, wsRealtime }
})

import AppTopbar from './AppTopbar.vue'

function mountTopbar(props: Record<string, unknown> = {}) {
  return mount(AppTopbar, {
    props: { collapsed: false, ...props },
    global: { stubs: { 'ion-icon': true } }
  })
}

describe('AppTopbar.vue', () => {
  beforeEach(() => {
    localStorage.clear()
    routerReplace.mockReset()
    wsState.wsConnected.value = false
    wsState.wsRealtime.value = true
    routeMeta.title = '仪表盘'
  })

  it('渲染页面标题(route.meta.title)、用户名与退出按钮', () => {
    localStorage.setItem('sc_username', 'admin')
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-title').text()).toBe('仪表盘')
    expect(wrapper.find('.topbar-username').text()).toBe('admin')
    expect(wrapper.findAll('button').some(b => b.text().includes('退出'))).toBe(true)
  })

  it('无 meta.title → 显示默认标题 Shared Center', () => {
    routeMeta.title = undefined as any
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-title').text()).toBe('Shared Center')
  })

  it('无用户名 → 显示空字符串', () => {
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-username').text()).toBe('')
  })

  it('汉堡按钮点击 → 触发 toggle 事件', async () => {
    const wrapper = mountTopbar()
    await wrapper.find('.hamburger').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('collapsed=true → header 加 collapsed 类', () => {
    const wrapper = mountTopbar({ collapsed: true })
    expect(wrapper.find('header').classes()).toContain('collapsed')
  })

  it('WS 已连接且实时 → 显示 "实时" + online 圆点', () => {
    wsState.wsConnected.value = true
    wsState.wsRealtime.value = true
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-indicator').text()).toContain('实时')
    expect(wrapper.find('.topbar-indicator .status-dot').classes()).toContain('online')
  })

  it('点击状态指示 → 切换实时开关(实时 ↔ 暂停)', async () => {
    wsState.wsConnected.value = true
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-indicator').text()).toContain('实时')

    await wrapper.find('.topbar-indicator').trigger('click')
    expect(wsState.wsRealtime.value).toBe(false)
    expect(wrapper.find('.topbar-indicator').text()).toContain('暂停')
    expect(wrapper.find('.topbar-indicator .status-dot').classes()).toContain('idle')

    await wrapper.find('.topbar-indicator').trigger('click')
    expect(wsState.wsRealtime.value).toBe(true)
    expect(wrapper.find('.topbar-indicator').text()).toContain('实时')
  })

  it('WS 断开 → 显示 "断开" + offline 圆点', () => {
    wsState.wsConnected.value = false
    const wrapper = mountTopbar()
    expect(wrapper.find('.topbar-indicator').text()).toContain('断开')
    expect(wrapper.find('.topbar-indicator .status-dot').classes()).toContain('offline')
  })

  it('点退出 → 清空登录信息并跳转 /login', async () => {
    localStorage.setItem('sc_username', 'admin')
    localStorage.setItem('sc_token', 'abc')
    localStorage.setItem('sc_permission', 'admin')
    const wrapper = mountTopbar()

    const logoutBtn = wrapper.findAll('button').find(b => b.text().includes('退出'))!
    await logoutBtn.trigger('click')
    await flushPromises()

    expect(localStorage.getItem('sc_token')).toBeNull()
    expect(localStorage.getItem('sc_username')).toBeNull()
    expect(localStorage.getItem('sc_permission')).toBeNull()
    expect(routerReplace).toHaveBeenCalledWith('/login')
  })
})
