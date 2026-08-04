// ============================================================
// FilterBar 历史筛选条测试
// naive-ui 全部 stub(输入/选择/日期/按钮),测 update:filters 事件联动
// ============================================================
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NInput: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        class: 'search-input',
        value: props.value ?? '',
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
  // 日期范围:通过测试按钮注入 [开始, 结束] 时间戳或 null
  NDatePicker: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(_, { emit }) {
      const range = [new Date('2026-08-01T00:00:00').getTime(), new Date('2026-08-02T00:00:00').getTime()]
      return () => h('div', { class: 'n-date-picker' }, [
        h('button', { class: 'set-range', onClick: () => emit('update:value', range) }, '设定范围'),
        h('button', { class: 'clear-range', onClick: () => emit('update:value', null) }, '清空范围')
      ])
    }
  })
}))

vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => (k.endsWith('.cpu') ? 'CPU 使用率' : k) })
}))

import FilterBar from './FilterBar.vue'

const keys = [
  { key: 'pc.cpu', count: 5, is_numeric: true, plot_kind: 'number', latest_value: '42', latest_changed_at: null, sources: ['agent'] },
  { key: 'HA.temperature', count: 3, is_numeric: true, plot_kind: 'number', latest_value: '25', latest_changed_at: null, sources: ['homeassistant'] },
  { key: 'pc.uptime', count: 2, is_numeric: true, plot_kind: 'duration', latest_value: '3h', latest_changed_at: null, sources: ['agent'] }
] as any

const sources = [
  { source: 'agent', count: 5 },
  { source: 'homeassistant', count: 3 }
] as any

const emptyFilters = { search: null, key: null, prefix: null, suffix: null, source: null, start: null, end: null }

function mountBar(props: Record<string, unknown> = {}) {
  return mount(FilterBar, {
    props: {
      keys,
      sources,
      filters: { ...emptyFilters },
      ...props
    }
  })
}

describe('FilterBar.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染输入框、4 个下拉、日期选择与两个按钮', () => {
    const wrapper = mountBar()
    expect(wrapper.find('.search-input').exists()).toBe(true)
    expect(wrapper.findAll('select')).toHaveLength(4)
    expect(wrapper.find('.n-date-picker').exists()).toBe(true)
    const buttons = wrapper.findAll('button')
    expect(buttons.some(b => b.text().includes('筛选'))).toBe(true)
    expect(buttons.some(b => b.text().includes('重置'))).toBe(true)
  })

  it('下拉选项带计数,可绘图 key 带图标标记', () => {
    const wrapper = mountBar()
    const selects = wrapper.findAll('select')
    // key 下拉:label = 字段映射名 (count) + 图标
    const keyOptions = selects[0].findAll('option').map(o => o.text())
    expect(keyOptions).toContain('CPU 使用率 (5)📈')
    expect(keyOptions).toContain('HA.temperature (3)📈')
    expect(keyOptions).toContain('pc.uptime (2)⏱️')
    // 前缀下拉:按设备分组排序
    const prefixOptions = selects[1].findAll('option').map(o => o.text())
    expect(prefixOptions).toEqual(['HA (3)', 'pc (7)'])
    // 后缀下拉:按指标分组
    const suffixOptions = selects[2].findAll('option').map(o => o.text())
    expect(suffixOptions).toEqual(['cpu (5)', 'temperature (3)', 'uptime (2)'])
    // 来源下拉
    const sourceOptions = selects[3].findAll('option').map(o => o.text())
    expect(sourceOptions).toEqual(['agent (5)', 'homeassistant (3)'])
  })

  it('搜索输入 → 触发 apply 并携带 search', async () => {
    const wrapper = mountBar()
    await wrapper.find('.search-input').setValue('pc')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0]).toEqual({
      search: 'pc', key: null, prefix: null, suffix: null, source: null, start: null, end: null
    })
  })

  it('输入纯空格 → search 转为 null', async () => {
    const wrapper = mountBar()
    await wrapper.find('.search-input').setValue('   ')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0].search).toBeNull()
  })

  it('选择精确 key → apply 携带 key', async () => {
    const wrapper = mountBar()
    await wrapper.findAll('select')[0].setValue('pc.cpu')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0].key).toBe('pc.cpu')
  })

  it('选择前缀 / 后缀 / 来源 → apply 携带对应字段', async () => {
    const wrapper = mountBar()
    const selects = wrapper.findAll('select')
    await selects[1].setValue('pc')
    await selects[2].setValue('cpu')
    await selects[3].setValue('agent')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[0][0].prefix).toBe('pc')
    expect(emitted[1][0].suffix).toBe('cpu')
    expect(emitted[2][0].source).toBe('agent')
  })

  it('选择时间范围 → apply 携带格式化后的 start/end', async () => {
    const wrapper = mountBar()
    await wrapper.find('.set-range').trigger('click')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0].start).toBe('2026-08-01 00:00:00')
    expect(emitted[emitted.length - 1][0].end).toBe('2026-08-02 00:00:00')
  })

  it('点"筛选"按钮 → apply 触发一次并携带当前状态', async () => {
    const wrapper = mountBar()
    await wrapper.findAll('select')[0].setValue('pc.cpu')
    const emittedEvents = wrapper.emitted('update:filters') as any[]
    emittedEvents.length = 0 // 清掉之前的事件(内部数组可直接截断)
    const filterBtn = wrapper.findAll('button').find(b => b.text().includes('筛选'))!
    await filterBtn.trigger('click')
    expect(emittedEvents).toHaveLength(1)
    expect(emittedEvents[0][0]).toEqual({
      search: null, key: 'pc.cpu', prefix: null, suffix: null, source: null, start: null, end: null
    })
  })

  it('点"重置" → 清空本地状态并提交全 null 过滤器', async () => {
    const wrapper = mountBar()
    await wrapper.findAll('select')[0].setValue('pc.cpu')
    await wrapper.find('.search-input').setValue('abc')
    await wrapper.find('.set-range').trigger('click')
    const emittedEvents = wrapper.emitted('update:filters') as any[]
    emittedEvents.length = 0

    const resetBtn = wrapper.findAll('button').find(b => b.text().includes('重置'))!
    await resetBtn.trigger('click')
    expect(emittedEvents).toHaveLength(1)
    expect(emittedEvents[0][0]).toEqual(emptyFilters)
    // 本地控件已清空
    expect(wrapper.find('.search-input').element.value).toBe('')
    expect((wrapper.findAll('select')[0].element as HTMLSelectElement).value).toBe('')
  })

  it('外部修改 filters → 本地控件同步(watch)', async () => {
    const wrapper = mountBar()
    await wrapper.setProps({
      filters: { search: 'abc', key: 'pc.cpu', prefix: 'pc', suffix: 'cpu', source: 'agent', start: '2026-08-01 00:00:00', end: '2026-08-02 00:00:00' }
    })
    await wrapper.find('.search-input').trigger('input') // 强制走一次 apply 检查本地状态
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0]).toEqual({
      search: 'abc', key: 'pc.cpu', prefix: 'pc', suffix: 'cpu', source: 'agent',
      start: '2026-08-01 00:00:00', end: '2026-08-02 00:00:00'
    })
    expect((wrapper.findAll('select')[0].element as HTMLSelectElement).value).toBe('pc.cpu')
  })

  it('外部清空 filters(含时间)→ 本地时间范围归零', async () => {
    const wrapper = mountBar({
      filters: { search: null, key: null, prefix: null, suffix: null, source: null, start: '2026-08-01 00:00:00', end: '2026-08-02 00:00:00' }
    })
    await wrapper.setProps({ filters: { ...emptyFilters } })
    await wrapper.find('.search-input').trigger('input')
    const emitted = wrapper.emitted('update:filters')!
    expect(emitted[emitted.length - 1][0]).toEqual(emptyFilters)
  })
})
