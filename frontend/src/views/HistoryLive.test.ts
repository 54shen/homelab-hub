// ============================================================
// HistoryLive 变更动态(实时模式)测试
// 初始 API 加载 + WS 续流 + 前端筛选 + 清空/导出
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const dashboardApiMock = vi.hoisted(() => ({ recentChanges: vi.fn() }))
const historyApiMock = vi.hoisted(() => ({ hourly: vi.fn(), list: vi.fn() }))
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))

vi.mock('../api', () => ({ dashboardApi: dashboardApiMock, historyApi: historyApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))
vi.mock('../components/TrendChart.vue', () => ({
  default: defineComponent({
    props: ['points', 'title', 'plotKind'],
    emits: ['reach-start'],
    setup(props) {
      return () => h('div', { class: 'trend-chart-stub' }, String((props.points || []).length) + '点')
    }
  })
}))

vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) }
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
  NDatePicker: defineComponent({
    props: ['value', 'placeholder', 'type'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        class: 'n-date-picker',
        placeholder: props.placeholder,
        value: props.value ?? '',
        onInput: (e: any) => emit('update:value', e.target.value === '' ? null : Number(e.target.value))
      })
    }
  }),
  NDataTable: defineComponent({
    props: ['data'],
    setup(props) {
      return () => h('div', { class: 'n-data-table' },
        // 注意:displayItems 把 key 换成了 String(id),原始 key 在 kv_key 字段
        (props.data || []).map((r: any) => h('div', { class: 'table-row', 'data-key': String(r.id) }, `${r.kv_key ?? r.key} | ${r.new_value ?? r.value ?? ''}`)))
    }
  }),
  useMessage: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() })
}))

import HistoryLive from './HistoryLive.vue'

let wrapper: ReturnType<typeof mount> | null = null

beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})

beforeEach(() => {
  Object.values(dashboardApiMock).forEach((m) => (m as any).mockReset())
  Object.values(historyApiMock).forEach((m) => (m as any).mockReset())
  wsOnMock.mockReset()
  wsOnMock.mockReturnValue(() => {})
  dashboardApiMock.recentChanges.mockResolvedValue({ data: [] })
  historyApiMock.hourly.mockResolvedValue({ data: [] })
  historyApiMock.list.mockResolvedValue({ data: { total: 0, items: [] } })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function mountPage() {
  wrapper = mount(HistoryLive, { global: { stubs: { 'ion-icon': true } } })
  return wrapper
}

function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

describe('HistoryLive.vue', () => {
  it('挂载后加载最近 20 条并渲染', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [
        { id: 1, key: 'a.b', old_value: '1', new_value: '2', source: 'agent', changed_at: '2026-08-01 10:00:00', retention_days: 180 },
        { id: 2, key: 'c.d', old_value: null, new_value: '5', source: 'ws', changed_at: '2026-08-01 09:00:00', retention_days: 180 }
      ]
    })
    const w = mountPage()
    await flushPromises()
    const rows = w.findAll('.table-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('a.b')
    expect(dashboardApiMock.recentChanges).toHaveBeenCalledWith(20)
  })

  it('无数据时显示等待提示', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('.n-data-table').exists()).toBe(true)
    expect(w.text()).toContain('实时监听中')
  })

  it('WS kv.changed 实时插入新行并计数', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(0)

    wsHandler()('kv.changed', { key: 'live.k', value: '42', old_value: '1', source: 'agent', changed_at: '2026-08-01 11:00:00' })
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(1)
    expect(w.text()).toContain('已接收 1 条')
  })

  it('WS 重复消息被去重', async () => {
    const w = mountPage()
    await flushPromises()
    const h = wsHandler()
    const msg = { key: 'dup.k', value: '1', old_value: null, source: 'a', changed_at: '2026-08-01 10:00:00' }
    h('kv.changed', msg)
    h('kv.changed', msg)  // 完全相同 → 跳过
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(1)
    expect(w.text()).toContain('已接收 2 条')  // 计数仍增加,但行不重复
  })

  it('搜索过滤本地数据', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [
        { id: 1, key: 'pc.cpu', old_value: '1', new_value: '2', source: 'a', changed_at: '2026-08-01 10:00:00', retention_days: 180 },
        { id: 2, key: 'HA.temp', old_value: '1', new_value: '2', source: 'a', changed_at: '2026-08-01 10:00:00', retention_days: 180 }
      ]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(2)

    await w.find('.filter-bar input').setValue('pc')
    await flushPromises()
    const rows = w.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('pc.cpu')
  })

  it('时间范围筛选', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [
        { id: 1, key: 'old.k', old_value: null, new_value: '1', source: 'a', changed_at: '2026-08-01 08:00:00', retention_days: 180 },
        { id: 2, key: 'new.k', old_value: null, new_value: '2', source: 'a', changed_at: '2026-08-01 12:00:00', retention_days: 180 }
      ]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(2)

    // 开始时间 = 2026-08-01 10:00 (时间戳)
    const startTs = new Date('2026-08-01T10:00:00').getTime()
    const pickers = w.findAll('.n-date-picker')
    await pickers[0].setValue(String(startTs))
    await flushPromises()
    const rows = w.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('new.k')
  })

  it('清空按钮清掉所有行', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [{ id: 1, key: 'x.y', old_value: null, new_value: '1', source: 'a', changed_at: '2026-08-01 10:00:00', retention_days: 180 }]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(1)

    const clearBtn = w.findAll('button').find((b) => b.text().includes('清空'))
    await clearBtn!.trigger('click')
    await flushPromises()
    expect(w.findAll('.table-row')).toHaveLength(0)
  })

  it('导出 CSV 触发下载', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [{ id: 1, key: 'e.k', old_value: '1', new_value: '2', source: 'a', changed_at: '2026-08-01 10:00:00', retention_days: 180 }]
    })
    const w = mountPage()
    await flushPromises()

    const exportBtn = w.findAll('button').find((b) => b.text().includes('导出'))
    await exportBtn!.trigger('click')
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled()
  })
})
