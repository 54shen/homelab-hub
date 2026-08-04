// ============================================================
// SystemLogs 系统日志页测试
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const logApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  exportCsv: vi.fn(),
  clear: vi.fn()
}))
vi.mock('../api', () => ({ logApi: logApiMock }))

// ---- naive-ui 轻量 stub ----
vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', {}, slots.default?.()) } }),
  NInput: defineComponent({
    props: ['value', 'placeholder'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        placeholder: props.placeholder,
        value: props.value,
        onInput: (e: any) => emit('update:value', e.target.value)
      })
    }
  }),
  NSelect: defineComponent({
    props: ['value', 'options'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        value: props.value ?? '',
        onChange: (e: any) => emit('update:value', (e.target as HTMLSelectElement).value || null)
      }, (props.options || []).map((o: any) => h('option', { value: o.value }, o.label)))
    }
  }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NPagination: defineComponent({ props: ['page', 'pageSize', 'itemCount'], setup() { return () => h('div', { class: 'n-pagination' }) } }),
  NPopconfirm: defineComponent({
    emits: ['positive-click'],
    setup(_, { slots, emit }) {
      return () => h('div', { class: 'n-popconfirm' }, [
        slots.trigger?.(),
        h('button', { class: 'confirm-btn', onClick: () => emit('positive-click') }, '确定')
      ])
    }
  }),
  useMessage: () => ({ success: vi.fn(), error: vi.fn() })
}))

import SystemLogs from './SystemLogs.vue'

beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})

function mockLogs() {
  logApiMock.list.mockResolvedValue({
    data: {
      total: 2,
      items: [
        { id: 1, level: 'error', module: 'webhook', message: 'Webhook 发送失败', detail: '{"error":"timeout"}', created_at: '2026-08-01 10:00:00' },
        { id: 2, level: 'info', module: 'system', message: '服务已启动', detail: null, created_at: '2026-08-01 09:00:00' }
      ]
    }
  } as any)
}

function mountPage() {
  return mount(SystemLogs, { global: { stubs: { 'ion-icon': true } } })
}

describe('SystemLogs.vue', () => {
  beforeEach(() => {
    Object.values(logApiMock).forEach((m) => (m as any).mockReset())
    logApiMock.list.mockResolvedValue({ data: { total: 0, items: [] } })
    logApiMock.exportCsv.mockResolvedValue({ data: new Blob(['csv']) })
    logApiMock.clear.mockResolvedValue({ data: {} })
  })

  it('挂载后加载并渲染日志行', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()
    const items = wrapper.findAll('.log-item')
    expect(items).toHaveLength(2)
    // 级别标签 + 消息
    expect(items[0].text()).toContain('ERROR')
    expect(items[0].text()).toContain('Webhook 发送失败')
    expect(items[1].text()).toContain('INFO')
    expect(wrapper.text()).toContain('共 2 条')
  })

  it('空日志时显示占位', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.n-empty').text()).toContain('暂无日志')
  })

  it('点击有 detail 的日志展开详情,再点收起', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.log-detail').exists()).toBe(false)
    await wrapper.findAll('.log-item')[0].trigger('click')
    await flushPromises()
    const detail = wrapper.find('.log-detail')
    expect(detail.exists()).toBe(true)
    expect(detail.text()).toContain('timeout')

    // 再点一次收起
    await wrapper.findAll('.log-item')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-detail').exists()).toBe(false)
  })

  it('无 detail 的日志点击不展开', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.log-item')[1].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-detail').exists()).toBe(false)
  })

  it('级别筛选 → 重新加载并携带 level 参数', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()
    expect(logApiMock.list).toHaveBeenCalledTimes(1)

    await wrapper.find('select').setValue('error')
    await flushPromises()
    expect(logApiMock.list).toHaveBeenCalledTimes(2)
    expect(logApiMock.list.mock.calls[1][0]).toEqual({ page: 1, page_size: 50, level: 'error' })
  })

  it('模块筛选 → 重新加载并携带 module 参数', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.filter-bar input').setValue('webhook')
    await flushPromises()
    expect(logApiMock.list).toHaveBeenCalledTimes(2)
    expect(logApiMock.list.mock.calls[1][0]).toEqual({ page: 1, page_size: 50, module: 'webhook' })
  })

  it('导出 CSV → 调用 exportCsv 并触发下载', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()
    const exportBtn = wrapper.findAll('button').find((b) => b.text().includes('导出'))
    await exportBtn!.trigger('click')
    await flushPromises()
    expect(logApiMock.exportCsv).toHaveBeenCalled()
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled()
  })

  it('清空日志 → 调用 clear 并重新加载', async () => {
    mockLogs()
    const wrapper = mountPage()
    await flushPromises()

    // 点确认按钮触发 positive-click → handleClear
    await wrapper.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(logApiMock.clear).toHaveBeenCalled()
    expect(logApiMock.list).toHaveBeenCalledTimes(2)
  })
})
