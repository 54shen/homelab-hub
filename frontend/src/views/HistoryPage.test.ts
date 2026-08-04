// ============================================================
// HistoryPage 历史记录页测试
// naive-ui / vue-router / API / 子组件(FilterBar/RecordsTable/TrendChart)全部 mock
// 覆盖:初始加载 / 空状态 / key 筛选与趋势图 / 路由同步 / 分组模式 / 自动刷新 / 频率模式 / 向前扩展 / 错误处理
// ============================================================
import { defineComponent, h } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const historyApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  keys: vi.fn(),
  sources: vi.fn(),
  trend: vi.fn(),
  stats: vi.fn(),
  frequency: vi.fn()
}))
const routerPushMock = vi.hoisted(() => vi.fn())
// route.query 用普通对象,watch(() => route.query.key) 不会触发(route 非响应式),行为可控
const routeQueryMock = vi.hoisted(() => ({} as Record<string, unknown>))
const msgSuccess = vi.hoisted(() => vi.fn())
const msgWarning = vi.hoisted(() => vi.fn())
const msgInfo = vi.hoisted(() => vi.fn())
const msgError = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({ historyApi: historyApiMock }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQueryMock, params: {} }),
  useRouter: () => ({ push: routerPushMock })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))

// ---- 子组件 stub ----
vi.mock('../components/FilterBar.vue', () => ({
  default: defineComponent({
    props: ['keys', 'sources', 'filters'],
    emits: ['update:filters'],
    setup(props, { emit }) {
      return () => h('div', { class: 'filter-bar' }, [
        h('input', {
          class: 'fb-search',
          value: props.filters.search ?? '',
          onInput: (e: any) => emit('update:filters', { ...props.filters, search: e.target.value || null })
        }),
        h('button', { class: 'fb-prefix', onClick: () => emit('update:filters', { ...props.filters, prefix: 'pc' }) }, '前缀pc')
      ])
    }
  })
}))
vi.mock('../components/RecordsTable.vue', () => ({
  default: defineComponent({
    props: ['items', 'total', 'page', 'pageSize', 'pages', 'showPager'],
    emits: ['select-key', 'update:page', 'update:page-size'],
    setup(props, { emit }) {
      return () => h('div', { class: 'records-table' }, [
        h('span', { class: 'rt-total' }, `共 ${props.total} 条`),
        h('span', { class: 'rt-pager' }, `第 ${props.page}/${props.pages} 页 每页${props.pageSize}`),
        ...(props.items || []).map((r: any) =>
          h('div', { class: 'rt-row', key: r.key, onClick: () => emit('select-key', r.key) }, String(r.key))
        ),
        h('button', { class: 'rt-next', onClick: () => emit('update:page', (props.page || 1) + 1) }, '下一页'),
        h('button', { class: 'rt-ps', onClick: () => emit('update:page-size', 50) }, '50条/页')
      ])
    }
  })
}))
vi.mock('../components/TrendChart.vue', () => ({
  default: defineComponent({
    props: ['points', 'title', 'plotKind', 'zoom'],
    emits: ['click', 'zoom', 'reach-start'],
    setup(props, { emit }) {
      return () => h('div', { class: 'trend-chart' }, [
        h('div', { class: 'tc-title' }, props.title),
        h('span', { class: 'tc-count' }, `点数 ${(props.points || []).length}`),
        h('button', { class: 'tc-switch', onClick: () => emit('click', { start: '2026-08-01 00:00:00', end: '2026-08-01 23:00:00' }) }, '切模式'),
        h('button', { class: 'tc-earlier', onClick: () => emit('reach-start') }, '更早')
      ])
    }
  })
}))

// ---- naive-ui 轻量 stub ----
vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NSelect: defineComponent({
    props: ['value', 'options'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        value: String(props.value ?? ''),
        onChange: (e: any) => {
          const v = (e.target as HTMLSelectElement).value
          // 选项 value 是数字时保持数字类型(自动刷新间隔)
          const opt = (props.options || []).find((o: any) => String(o.value) === v)
          emit('update:value', opt ? opt.value : v || null)
        }
      }, (props.options || []).map((o: any) => h('option', { value: String(o.value) }, o.label)))
    }
  }),
  useMessage: () => ({ success: msgSuccess, warning: msgWarning, info: msgInfo, error: msgError })
}))

import HistoryPage from './HistoryPage.vue'

// jsdom 没有 URL.createObjectURL
beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})
// 每个测试后自动 unmount,清理防抖/刷新定时器
enableAutoUnmount(afterEach)

function mockMeta() {
  historyApiMock.keys.mockResolvedValue({
    data: [
      { key: 'pc.cpu', plot_kind: 'number' },
      { key: 'pc.flag', plot_kind: null },
      { key: 'server.uptime', plot_kind: 'duration' }
    ]
  } as any)
  historyApiMock.sources.mockResolvedValue({ data: [{ source: 'agent', display: 'agent' }] } as any)
  historyApiMock.stats.mockResolvedValue({
    data: {
      total_records: 123,
      max_changed_at: '2026-08-01 10:00:00',
      per_source: [{ source: 'agent', count: 123 }]
    }
  } as any)
}

function mockRecords() {
  historyApiMock.list.mockResolvedValue({
    data: {
      total: 3,
      items: [
        { id: 1, key: 'pc.cpu', value: '42', type: 'int', source: 'agent', updated_at: '2026-08-01 10:00:00', expire_seconds: null, retention_days: 180 },
        { id: 2, key: 'HA.temperature', value: '23.5', type: 'float', source: 'ha', updated_at: '2026-08-01 10:01:00', expire_seconds: null, retention_days: 180 },
        { id: 3, key: 'pc.flag', value: 'on', type: 'string', source: 'agent', updated_at: '2026-08-01 10:02:00', expire_seconds: null, retention_days: 180 }
      ]
    }
  } as any)
  historyApiMock.trend.mockResolvedValue({
    data: { points: [{ changed_at: '2026-08-01 10:00:00', value: 50, raw: '50' }] }
  } as any)
}

function mountPage() {
  return mount(HistoryPage, { global: { stubs: { 'ion-icon': true } } })
}

describe('HistoryPage.vue', () => {
  beforeEach(() => {
    Object.values(historyApiMock).forEach((m) => (m as any).mockReset())
    routerPushMock.mockReset()
    routeQueryMock.key = undefined
    msgSuccess.mockReset(); msgWarning.mockReset(); msgInfo.mockReset(); msgError.mockReset()
    mockMeta()
    historyApiMock.list.mockResolvedValue({ data: { total: 0, items: [] } })
    historyApiMock.trend.mockResolvedValue({ data: { points: [] } })
    historyApiMock.frequency.mockResolvedValue({ data: [] })
  })

  afterEach(() => { vi.useRealTimers() })

  it('挂载后加载元数据与记录,渲染统计与列表', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    expect(historyApiMock.keys).toHaveBeenCalled()
    expect(historyApiMock.sources).toHaveBeenCalled()
    expect(historyApiMock.stats).toHaveBeenCalled()
    // 首次加载:平铺视图 page 1 / 每页 20
    expect(historyApiMock.list).toHaveBeenCalledTimes(1)
    expect(historyApiMock.list.mock.calls[0][0]).toEqual(expect.objectContaining({ page: 1, page_size: 20 }))
    expect(wrapper.text()).toContain('总记录')
    expect(wrapper.text()).toContain('123')
    expect(wrapper.findAll('.rt-row')).toHaveLength(3)
    expect(wrapper.text()).toContain('共 3 条')
    // 未选中 key → 无趋势图
    expect(wrapper.find('.trend-chart').exists()).toBe(false)
  })

  it('空数据时显示空列表,不渲染趋势图', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.rt-row')).toHaveLength(0)
    expect(wrapper.text()).toContain('共 0 条')
    expect(wrapper.find('.trend-chart').exists()).toBe(false)
  })

  it('点击 key → 筛选该 key、显示趋势图并同步路由', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.rt-row')[0].trigger('click')  // pc.cpu
    await flushPromises()
    // key 工具条 + 趋势图出现
    expect(wrapper.find('.key-bar').exists()).toBe(true)
    expect(wrapper.find('.trend-chart').exists()).toBe(true)
    expect(wrapper.find('.tc-title').text()).toContain('pc.cpu 趋势')
    // 路由写入 URL
    expect(routerPushMock).toHaveBeenCalledWith({ query: { key: 'pc.cpu' } })
    // 防抖后重新拉取携带 key
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    expect(historyApiMock.list.mock.calls[1][0]).toEqual(expect.objectContaining({ key: 'pc.cpu' }))
  })

  it('点击无可绘图格式的 key → 不显示图表并警告', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    // pc.flag 没有 plot_kind
    const flagRow = wrapper.findAll('.rt-row').find((r) => r.text().includes('pc.flag'))
    await flagRow!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.key-bar').exists()).toBe(true)
    expect(wrapper.find('.trend-chart').exists()).toBe(false)
    expect(msgWarning).toHaveBeenCalled()
  })

  it('返回按钮清除 key 筛选,恢复完整列表', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.rt-row')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.key-bar').exists()).toBe(true)
    // 模拟 router.push 后 route.query.key 已同步为 pc.cpu
    routeQueryMock.key = 'pc.cpu'
    await wrapper.find('.key-bar button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.key-bar').exists()).toBe(false)
    expect(wrapper.find('.trend-chart').exists()).toBe(false)
    // URL 中 key 被移除
    expect(routerPushMock).toHaveBeenLastCalledWith({ query: { key: undefined } })
  })

  it('搜索筛选 → 防抖后重新加载并携带 search 参数', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    expect(historyApiMock.list).toHaveBeenCalledTimes(1)
    await wrapper.find('.fb-search').setValue('pc')
    // 300ms 防抖后触发
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    expect(historyApiMock.list).toHaveBeenCalledTimes(2)
    expect(historyApiMock.list.mock.calls[1][0]).toEqual(expect.objectContaining({ search: 'pc', page: 1 }))
  })

  it('分组模式:拉取全量并渲染分组卡片(按前缀排序)', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    const groupBtn = wrapper.findAll('button').find((b) => b.text().includes('分组'))
    await groupBtn!.trigger('click')
    await flushPromises()
    // 分组模式拉取 page_size = 50000,未筛选时间时自动带最近 24h start
    expect(historyApiMock.list.mock.calls[1][0]).toEqual(expect.objectContaining({ page_size: 50000, page: 1, start: expect.any(String) }))
    // 分组卡片按 localeCompare 排序:HA 在 pc 前
    const cards = wrapper.findAll('.group-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('HA')
    expect(cards[1].text()).toContain('pc')
    // 分组提示条可见
    expect(wrapper.find('.group-tip').exists()).toBe(true)
  })

  it('分组模式:超过展示上限的组可展开全部', async () => {
    historyApiMock.list.mockResolvedValue({
      data: {
        total: 12,
        items: Array.from({ length: 12 }, (_, i) => ({
          id: i, key: `pc.k${i}`, value: `${i}`, type: 'int', source: 'agent',
          updated_at: '2026-08-01 10:00:00', expire_seconds: null, retention_days: 180
        }))
      }
    } as any)
    historyApiMock.trend.mockResolvedValue({ data: { points: [] } } as any)
    const wrapper = mountPage()
    await flushPromises()
    const groupBtn = wrapper.findAll('button').find((b) => b.text().includes('分组'))
    await groupBtn!.trigger('click')
    await flushPromises()
    // 默认只展示前 10 条
    const card = wrapper.find('.group-card')
    expect(card.findAll('.rt-row')).toHaveLength(10)
    const expandBtn = card.findAll('button').find((b) => b.text().includes('展开全部 (12)'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await flushPromises()
    expect(card.findAll('.rt-row')).toHaveLength(12)
  })

  it('分组模式空数据 → 显示无匹配记录', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const groupBtn = wrapper.findAll('button').find((b) => b.text().includes('分组'))
    await groupBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.group-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('无匹配记录')
  })

  it('自动刷新:设置间隔后定时重载;手动翻页后自动刷新关闭', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    expect(historyApiMock.list).toHaveBeenCalledTimes(1)
    // 选择 10 秒自动刷新
    await wrapper.find('select').setValue('10')
    await vi.advanceTimersByTimeAsync(10000)
    expect(historyApiMock.list).toHaveBeenCalledTimes(2)
    // 手动翻页 → 自动刷新被关闭
    await wrapper.find('.rt-next').trigger('click')
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    const cnt = historyApiMock.list.mock.calls.length
    await vi.advanceTimersByTimeAsync(30000)
    expect(historyApiMock.list.mock.calls.length).toBe(cnt)
  })

  it('频率模式:点击图表切换 → 请求频率接口并按窗口粒度聚合', async () => {
    mockRecords()
    historyApiMock.frequency.mockResolvedValue({
      data: [{ minute: '2026-08-01 10:00', count: 3 }, { minute: '2026-08-01 10:01', count: 5 }]
    } as any)
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.rt-row')[0].trigger('click')
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    expect(wrapper.find('.tc-title').text()).toContain('pc.cpu 趋势')
    // 切到上报频率视图:携带当前缩放窗口
    await wrapper.find('.tc-switch').trigger('click')
    await flushPromises()
    expect(historyApiMock.frequency).toHaveBeenCalledWith({ key: 'pc.cpu', start: '2026-08-01 00:00:00', end: '2026-08-01 23:00:00' })
    // 23h 窗口 → 粒度 10 分钟
    expect(wrapper.find('.tc-title').text()).toContain('上报频率')
    expect(wrapper.find('.tc-title').text()).toContain('粒度10分钟')
    // 再切回值趋势
    await wrapper.find('.tc-switch').trigger('click')
    await flushPromises()
    expect(wrapper.find('.tc-title').text()).toContain('pc.cpu 趋势')
  })

  it('拖动到最早边界 → 自动多取 24 小时数据并拼接', async () => {
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.rt-row')[0].trigger('click')
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    expect(wrapper.find('.tc-count').text()).toContain('点数 1')
    // 点"更早" → 取最早点前 24h(终点为最早点前 1 秒)
    await wrapper.find('.tc-earlier').trigger('click')
    await flushPromises()
    expect(historyApiMock.trend).toHaveBeenLastCalledWith(expect.objectContaining({
      key: 'pc.cpu',
      start: '2026-07-31 10:00:00',
      end: '2026-08-01 09:59:59'
    }))
    // 新数据拼接到头部 → 点数 2
    expect(wrapper.find('.tc-count').text()).toContain('点数 2')
  })

  it('已到最早数据 → 提示并停止请求', async () => {
    mockRecords()
    historyApiMock.trend.mockReset()
    historyApiMock.trend
      .mockResolvedValueOnce({ data: { points: [{ changed_at: '2026-08-01 10:00:00', value: 50, raw: '50' }] } } as any)
      .mockResolvedValueOnce({ data: { points: [] } } as any)
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.rt-row')[0].trigger('click')
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    await wrapper.find('.tc-earlier').trigger('click')
    await flushPromises()
    expect(msgInfo).toHaveBeenCalledWith('已到最早的数据,没有更早的记录')
  })

  it('从 URL 恢复选中的 key', async () => {
    routeQueryMock.key = 'pc.cpu'
    mockRecords()
    const wrapper = mountPage()
    await flushPromises()
    // 挂载即选中 → key 工具条 + 趋势图
    expect(wrapper.find('.key-bar').exists()).toBe(true)
    expect(wrapper.find('.trend-chart').exists()).toBe(true)
    // 首次加载即携带该 key
    expect(historyApiMock.list.mock.calls[0][0]).toEqual(expect.objectContaining({ key: 'pc.cpu' }))
    // 挂载时不额外 push 路由
    expect(routerPushMock).not.toHaveBeenCalled()
  })

  it('加载失败 → 显示错误信息', async () => {
    historyApiMock.list.mockRejectedValue({ response: { data: { detail: 'boom' } } })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.error').exists()).toBe(true)
    expect(wrapper.text()).toContain('boom')
  })
})
