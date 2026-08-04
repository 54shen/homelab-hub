// ============================================================
// AppSidebar 侧边栏导航测试
// vue-router 的 useRoute 与 RouterLink 均 stub,测菜单渲染 / 高亮 / 收起
// ============================================================
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const routePath = vi.hoisted(() => ({ value: '/history' }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: routePath.value })
}))

// RouterLink stub:渲染 <a>,声明 emits:['click'] 避免原生事件 + 自定义事件双触发
const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: ['to'],
  emits: ['click'],
  setup(props, { slots, attrs, emit }) {
    return () => h('a', {
      ...attrs,
      href: typeof props.to === 'string' ? props.to : props.to?.path,
      onClick: () => emit('click')
    }, slots.default?.())
  }
})

import AppSidebar from './AppSidebar.vue'

function mountSidebar(props: Record<string, unknown> = {}) {
  return mount(AppSidebar, {
    props: { collapsed: false, ...props },
    global: { stubs: { RouterLink: RouterLinkStub, 'ion-icon': true } }
  })
}

// 移动端宽度模拟(jsdom 默认 1024)
let currentWidth = 1024
function setViewport(width: number) {
  currentWidth = width
  Object.defineProperty(window, 'innerWidth', { configurable: true, get: () => currentWidth })
}

describe('AppSidebar.vue', () => {
  beforeEach(() => {
    routePath.value = '/history'
    setViewport(1024)
  })

  afterEach(() => {
    delete (window as any).innerWidth
  })

  it('渲染品牌、分组与全部导航项', () => {
    const wrapper = mountSidebar()
    expect(wrapper.find('.brand-text').text()).toBe('Shared Center')
    // 5 个分组
    const groups = wrapper.findAll('.nav-group-label').map(g => g.text())
    expect(groups).toEqual(['概览', '数据', '设备', '自动化', '系统'])
    // 10 个导航项
    const items = wrapper.findAll('.nav-item').map(a => a.text())
    expect(items).toHaveLength(10)
    expect(items).toContain('仪表盘')
    expect(items).toContain('变量管理')
    expect(items).toContain('历史记录')
    expect(items).toContain('变更动态')
    expect(items).toContain('系统日志')
    // 链接指向正确路径
    expect(wrapper.find('.nav-item').attributes('href')).toBe('/dashboard')
  })

  it('当前路由对应项高亮 active', () => {
    const wrapper = mountSidebar()
    const active = wrapper.findAll('.nav-item').filter(a => a.classes().includes('active'))
    expect(active).toHaveLength(1)
    expect(active[0].attributes('href')).toBe('/history')
  })

  it('子路径也命中父级导航(如 /devices/abc 高亮设备管理)', () => {
    routePath.value = '/devices/abc'
    const wrapper = mountSidebar()
    const active = wrapper.findAll('.nav-item').filter(a => a.classes().includes('active'))
    expect(active).toHaveLength(1)
    expect(active[0].attributes('href')).toBe('/devices')
  })

  it('无匹配路由时不高亮任何项', () => {
    routePath.value = '/no-such-page'
    const wrapper = mountSidebar()
    expect(wrapper.findAll('.nav-item.active')).toHaveLength(0)
  })

  it('collapsed=true → aside 加 collapsed 类', () => {
    const wrapper = mountSidebar({ collapsed: true })
    expect(wrapper.find('aside').classes()).toContain('collapsed')
  })

  it('桌面宽度点击导航 → 不触发 toggle', async () => {
    const wrapper = mountSidebar()
    await wrapper.findAll('.nav-item')[0].trigger('click')
    expect(wrapper.emitted('toggle')).toBeUndefined()
  })

  it('移动宽度(400px)点击导航 → 触发 toggle 收起侧边栏', async () => {
    setViewport(400)
    const wrapper = mountSidebar()
    await wrapper.findAll('.nav-item')[0].trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('移动宽度点击不改变内部状态(展开收起由父级控制)', async () => {
    setViewport(400)
    const wrapper = mountSidebar()
    await wrapper.findAll('.nav-item')[0].trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })
})
