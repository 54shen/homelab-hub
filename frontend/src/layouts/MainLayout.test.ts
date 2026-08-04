// ============================================================
// MainLayout 布局测试
// AppSidebar / AppTopbar 子组件与 RouterView 均 stub,测折叠联动 / 遮罩 / 响应式
// ============================================================
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ---- 子组件 stub:渲染按钮,点击 emit toggle ----
// 注意:vi.mock 工厂会被提升到文件顶部,stub 定义必须放在工厂内部
vi.mock('../components/AppSidebar.vue', () => ({
  default: defineComponent({
    name: 'AppSidebar',
    props: ['collapsed'],
    emits: ['toggle'],
    setup(props, { emit }) {
      return () => h('button', { class: 'sidebar-stub', 'data-collapsed': String(props.collapsed), onClick: () => emit('toggle') }, 'sidebar')
    }
  })
}))
vi.mock('../components/AppTopbar.vue', () => ({
  default: defineComponent({
    name: 'AppTopbar',
    props: ['collapsed'],
    emits: ['toggle'],
    setup(props, { emit }) {
      return () => h('button', { class: 'topbar-stub', 'data-collapsed': String(props.collapsed), onClick: () => emit('toggle') }, 'topbar')
    }
  })
}))
// RouterView stub:提供 v-slot 作用域(Component + route)
const RouterViewStub = defineComponent({
  name: 'RouterView',
  setup(_, { slots }) {
    const PageStub = { name: 'PageStub', render: () => h('div', { class: 'page-stub' }) }
    return () => slots.default?.({ Component: PageStub, route: { fullPath: '/dashboard' } })
  }
})

import MainLayout from './MainLayout.vue'

// 视口宽度模拟(jsdom 默认 1024;matchMedia 需手写 stub)
let currentWidth = 1024
let mediaChangeHandler: (() => void) | null = null

function setViewport(width: number) {
  currentWidth = width
  Object.defineProperty(window, 'innerWidth', { configurable: true, get: () => currentWidth })
}

function mountLayout() {
  return mount(MainLayout, {
    global: {
      stubs: { RouterView: RouterViewStub, 'ion-icon': true }
    }
  })
}

describe('MainLayout.vue', () => {
  beforeEach(() => {
    currentWidth = 1024
    setViewport(1024)
    mediaChangeHandler = null
    window.matchMedia = vi.fn(() => ({
      addEventListener: vi.fn((_: string, cb: any) => { mediaChangeHandler = cb }),
      removeEventListener: vi.fn()
    })) as any
  })

  afterEach(() => {
    delete (window as any).innerWidth
    delete (window as any).matchMedia
  })

  it('桌面宽度 → 折叠关闭,无遮罩,渲染页面插槽', () => {
    const wrapper = mountLayout()
    expect(wrapper.find('.main-layout').classes()).not.toContain('sidebar-collapsed')
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)
    expect(wrapper.find('.sidebar-stub').attributes('data-collapsed')).toBe('false')
    expect(wrapper.find('.topbar-stub').attributes('data-collapsed')).toBe('false')
    // RouterView 插槽内容渲染
    expect(wrapper.find('.page-stub').exists()).toBe(true)
  })

  it('侧边栏 toggle → 折叠状态切换并联动顶栏', async () => {
    const wrapper = mountLayout()
    await wrapper.find('.sidebar-stub').trigger('click')
    expect(wrapper.find('.main-layout').classes()).toContain('sidebar-collapsed')
    expect(wrapper.find('.sidebar-stub').attributes('data-collapsed')).toBe('true')
    expect(wrapper.find('.topbar-stub').attributes('data-collapsed')).toBe('true')
  })

  it('顶栏 toggle → 同样切换折叠状态', async () => {
    const wrapper = mountLayout()
    await wrapper.find('.topbar-stub').trigger('click')
    expect(wrapper.find('.main-layout').classes()).toContain('sidebar-collapsed')
  })

  it('再点一次 → 折叠恢复', async () => {
    const wrapper = mountLayout()
    await wrapper.find('.sidebar-stub').trigger('click')
    await wrapper.find('.sidebar-stub').trigger('click')
    expect(wrapper.find('.main-layout').classes()).not.toContain('sidebar-collapsed')
  })

  it('移动端(400px)→ 初始折叠;展开侧边栏后显示遮罩,点击遮罩收起', async () => {
    setViewport(400)
    const wrapper = mountLayout()
    expect(wrapper.find('.main-layout').classes()).toContain('sidebar-collapsed')
    // 折叠状态下遮罩不显示(遮罩只在移动端展开时出现)
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)

    // 展开侧边栏 → 遮罩出现
    await wrapper.find('.sidebar-stub').trigger('click')
    expect(wrapper.find('.main-layout').classes()).not.toContain('sidebar-collapsed')
    const overlay = wrapper.find('.sidebar-overlay')
    expect(overlay.exists()).toBe(true)

    // 点击遮罩 → 收起(遮罩消失)
    await overlay.trigger('click')
    expect(wrapper.find('.main-layout').classes()).toContain('sidebar-collapsed')
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)
  })

  it('桌面端展开时无遮罩,但点击遮罩逻辑不生效(遮罩不存在)', () => {
    const wrapper = mountLayout()
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)
  })

  it('matchMedia change → 切到移动宽度自动折叠,切回桌面展开', async () => {
    const wrapper = mountLayout()
    expect(wrapper.find('.main-layout').classes()).not.toContain('sidebar-collapsed')

    // 模拟媒体查询变化:宽度 500 → 折叠(直接调用回调,需等渲染刷新)
    setViewport(500)
    mediaChangeHandler!()
    await nextTick()
    expect(wrapper.find('.main-layout').classes()).toContain('sidebar-collapsed')
    // 折叠时无遮罩
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)

    // 移动端展开 → 遮罩出现
    await wrapper.find('.sidebar-stub').trigger('click')
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(true)

    // 回到桌面 → 展开,遮罩消失
    setViewport(1280)
    mediaChangeHandler!()
    await nextTick()
    expect(wrapper.find('.main-layout').classes()).not.toContain('sidebar-collapsed')
    expect(wrapper.find('.sidebar-overlay').exists()).toBe(false)
  })
})
