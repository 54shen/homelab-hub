// ============================================================
// StatCard 统计卡片测试
// 纯展示组件:验证 props 渲染 + 可点击时跳转 $router.push
// ============================================================
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StatCard from './StatCard.vue'

const routerPush = vi.fn()

function mountCard(props: Record<string, unknown> = {}) {
  return mount(StatCard, {
    props: {
      icon: 'pulse-outline',
      iconBg: '#eef4ff',
      iconColor: '#5B8DEF',
      primary: 12,
      label: '在线设备',
      ...props
    },
    global: {
      mocks: { $router: { push: routerPush } },
      stubs: { 'ion-icon': true }
    }
  })
}

describe('StatCard.vue', () => {
  beforeEach(() => {
    routerPush.mockReset()
  })

  it('渲染 primary / label / 图标', () => {
    const wrapper = mountCard({ primary: 42, label: '总变量' })
    expect(wrapper.find('.value-highlight').text()).toBe('42')
    expect(wrapper.find('.stat-label').text()).toBe('总变量')
    // ion-icon stub 上透传了 name
    expect(wrapper.find('ion-icon').attributes('name')).toBe('pulse-outline')
  })

  it('传入 secondary 时渲染 " / secondary"', () => {
    const wrapper = mountCard({ primary: 5, secondary: 20, label: '服务' })
    // Vue 模板会压缩文本节点首尾空白,实际渲染为 "/ 20"
    expect(wrapper.find('.value-total').text()).toBe('/ 20')
  })

  it('不传 secondary 时不渲染 "/" 部分', () => {
    const wrapper = mountCard({ primary: 5, label: '服务' })
    expect(wrapper.find('.value-total').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('/')
  })

  it('trend 为正数 → 上升样式 + 显示绝对值', () => {
    const wrapper = mountCard({ trend: 15 })
    const trend = wrapper.find('.stat-trend')
    expect(trend.classes()).toContain('up')
    expect(trend.text()).toContain('15%')
  })

  it('trend 为负数 → 下降样式 + 显示绝对值', () => {
    const wrapper = mountCard({ trend: -8 })
    const trend = wrapper.find('.stat-trend')
    expect(trend.classes()).toContain('down')
    expect(trend.text()).toContain('8%')
  })

  it('不传 trend 时不渲染趋势块', () => {
    const wrapper = mountCard()
    expect(wrapper.find('.stat-trend').exists()).toBe(false)
  })

  it('传入 to → 卡片可点击并跳转', async () => {
    const wrapper = mountCard({ to: '/devices' })
    expect(wrapper.find('.stat-card').classes()).toContain('clickable')
    await wrapper.trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/devices')
  })

  it('未传 to → 点击不跳转', async () => {
    const wrapper = mountCard()
    expect(wrapper.find('.stat-card').classes()).not.toContain('clickable')
    await wrapper.trigger('click')
    expect(routerPush).not.toHaveBeenCalled()
  })
})
