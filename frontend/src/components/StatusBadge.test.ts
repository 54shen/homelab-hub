// ============================================================
// StatusBadge 在线状态徽章测试
// 纯展示组件:online 布尔值 → 状态类名 + 中文文案
// ============================================================
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatusBadge from './StatusBadge.vue'

function mountBadge(props: { online: boolean; size?: 'small' | 'default' }) {
  return mount(StatusBadge, { props })
}

describe('StatusBadge.vue', () => {
  it('online=true → 显示 "在线" + online 类', () => {
    const wrapper = mountBadge({ online: true })
    expect(wrapper.text()).toBe('在线')
    expect(wrapper.find('.status-badge').classes()).toContain('online')
    expect(wrapper.find('.status-dot').classes()).toContain('online')
  })

  it('online=false → 显示 "离线" + offline 类', () => {
    const wrapper = mountBadge({ online: false })
    expect(wrapper.text()).toBe('离线')
    expect(wrapper.find('.status-badge').classes()).toContain('offline')
    expect(wrapper.find('.status-dot').classes()).toContain('offline')
  })

  it('响应式更新:online 变化后文案与类同步切换', async () => {
    const wrapper = mountBadge({ online: true })
    expect(wrapper.text()).toBe('在线')
    await wrapper.setProps({ online: false })
    expect(wrapper.text()).toBe('离线')
    expect(wrapper.find('.status-badge').classes()).toContain('offline')
  })

  it('默认 size 渲染无额外类,不报错', () => {
    const wrapper = mountBadge({ online: true })
    // 组件未对 size 做样式类绑定,只需确保渲染正常
    expect(wrapper.find('.status-badge').exists()).toBe(true)
  })
})
