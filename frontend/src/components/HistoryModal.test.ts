// ============================================================
// HistoryModal 历史弹窗测试
// naive-ui / historyApi / useWebSocket / useFieldLabels / TrendChart 全 mock
// 测:打开加载 / 表格渲染 / 翻页 / WS 实时插入 / 导出 / 关闭清理
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const historyApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  trend: vi.fn(),
  exportCsv: vi.fn()
}))
// 捕获 useWebSocket 注册的 on 回调,模拟服务器推送
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))
const wsCleanupMock = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({ historyApi: historyApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => (k.endsWith('.cpu') ? 'CPU 使用率' : k) })
}))
vi.mock('../components/TrendChart.vue', () => ({
  default: defineComponent({
    name: 'TrendChart',
    props: ['points', 'title', 'plotKind'],
    template: '<div class="trend-chart-stub"></div>'
  })
}))

// ---- naive-ui 轻量 stub(参考 KvManager.test.ts 模式)----
vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-space' }, slots.default?.()) } }),
  NDatePicker: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(_, { emit }) {
      const ts1 = new Date('2026-08-01T00:00:00').getTime()
      const ts2 = new Date('2026-08-02T00:00:00').getTime()
      return () => h('div', { class: 'n-date-picker' }, [
        h('button', { class: 'set-start', onClick: () => emit('update:value', ts1) }, '设定开始'),
        h('button', { class: 'set-end', onClick: () => emit('update:value', ts2) }, '设定结束')
      ])
    }
  }),
  NModal: defineComponent({
    props: ['show', 'title'],
    emits: ['update:show'],
    setup(props, { slots, emit }) {
      // 注意:必须在 render 内求值 props.show
      return () =>
        props.show
          ? h('div', { class: 'n-modal' }, [
              h('div', { class: 'modal-title' }, props.title),
              slots.default?.(),
              h('button', { class: 'close-modal', onClick: () => emit('update:show', false) }, '关闭')
            ])
          : null
    }
  }),
  NDataTable: defineComponent({
    props: ['data', 'columns', 'loading', 'pagination'],
    emits: ['update:page', 'update:pageSize'],
    setup(props, { emit }) {
      return () => h('div', { class: 'n-data-table' }, [
        h('button', { class: 'go-page-2', onClick: () => emit('update:page', 2) }, '翻到第2页'),
        h('button', { class: 'go-page-size', onClick: () => emit('update:pageSize', 50) }, '每页50'),
        ...(props.data || []).map((r: any) =>
          h('div', { class: 'hm-row', 'data-key': r.key }, `${r.new_value} @ ${r.changed_at}`))
      ])
    }
  }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } })
}))

import HistoryModal from './HistoryModal.vue'

function mockList() {
  historyApiMock.list.mockResolvedValue({
    data: {
      total: 42,
      items: [
        { id: 1, key: 'pc.cpu', old_value: '10', new_value: '20', source: 'agent', retention_days: 180, changed_at: '2026-08-01 10:00:00' },
        { id: 2, key: 'pc.cpu', old_value: '20', new_value: '30', source: 'agent', retention_days: 180, changed_at: '2026-08-01 09:00:00' }
      ]
    }
  } as any)
}

function mountModal() {
  return mount(HistoryModal, {
    props: { show: false, keyProp: 'pc.cpu' },
    global: { stubs: { 'ion-icon': true } }
  })
}

/** 打开弹窗(show false → true 触发加载 + WS 注册) */
async function openModal(wrapper: ReturnType<typeof mountModal>) {
  await wrapper.setProps({ show: true })
  await flushPromises()
}

describe('HistoryModal.vue', () => {
  beforeAll(() => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  beforeEach(() => {
    Object.values(historyApiMock).forEach(m => (m as any).mockReset())
    wsOnMock.mockReset()
    wsOnMock.mockReturnValue(wsCleanupMock)
    wsCleanupMock.mockReset()
    historyApiMock.list.mockResolvedValue({ data: { total: 0, items: [] } })
    historyApiMock.trend.mockResolvedValue({ data: { points: [], kind: '' } })
    historyApiMock.exportCsv.mockResolvedValue({ data: 'csv' })
  })

  it('show=false → 不渲染弹窗,不发请求', () => {
    const wrapper = mountModal()
    expect(wrapper.find('.n-modal').exists()).toBe(false)
    expect(historyApiMock.list).not.toHaveBeenCalled()
  })

  it('打开弹窗 → 渲染标题并加载列表与趋势', async () => {
    mockList()
    historyApiMock.trend.mockResolvedValue({
      data: { points: [{ changed_at: '2026-08-01 10:00:00', value: 20 }], kind: 'number' }
    })
    const wrapper = mountModal()
    await openModal(wrapper)

    // 标题用字段映射后的中文
    expect(wrapper.find('.modal-title').text()).toContain('CPU 使用率 的历史')
    // 列表请求:key + 默认分页
    expect(historyApiMock.list).toHaveBeenCalledWith(
      expect.objectContaining({ key: 'pc.cpu', page: 1, page_size: 20 })
    )
    // 趋势请求:默认最近 24h
    const trendParams = historyApiMock.trend.mock.calls[0][0]
    expect(trendParams.key).toBe('pc.cpu')
    expect(trendParams.limit).toBe(5000)
    expect(trendParams.start).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
    expect(trendParams.end).toBeUndefined()

    // 表格行渲染 + 总数
    expect(wrapper.findAll('.hm-row')).toHaveLength(2)
    expect(wrapper.text()).toContain('共 42 条')
    // 有可绘图数据 → 趋势图出现
    expect(wrapper.find('.trend-chart-stub').exists()).toBe(true)
  })

  it('打开弹窗时注册 WS 监听', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wsOnMock).toHaveBeenCalledTimes(1)
  })

  it('无历史数据 → 显示占位', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wrapper.find('.n-empty').text()).toContain('暂无历史记录')
    expect(wrapper.find('.trend-chart-stub').exists()).toBe(false)
  })

  it('WS 新变更 → 按时间倒序插入新行', async () => {
    mockList()
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wrapper.findAll('.hm-row')).toHaveLength(2)

    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'pc.cpu', value: '99', old_value: '30', source: 'agent', changed_at: '2026-08-01 10:30:00' })
    await flushPromises()

    const rows = wrapper.findAll('.hm-row')
    expect(rows).toHaveLength(3)
    // 新行插入头部(时间最新)
    expect(rows[0].text()).toContain('99')
    expect(rows[0].text()).toContain('10:30:00')
  })

  it('WS 重复事件(已存在的 key|changed_at)→ 不重复插入', async () => {
    mockList()
    const wrapper = mountModal()
    await openModal(wrapper)

    const wsHandler = wsOnMock.mock.calls[0][0]
    const evt = { key: 'pc.cpu', value: '99', changed_at: '2026-08-01 10:30:00' }
    wsHandler('kv.changed', evt)
    wsHandler('kv.changed', evt)
    await flushPromises()
    expect(wrapper.findAll('.hm-row')).toHaveLength(3)
  })

  it('列表超过 pageSize → 弹出最旧行', async () => {
    // 服务端按时间倒序返回:第 0 条最新('19:00:00'),最后一条最旧('00:00:00')
    historyApiMock.list.mockResolvedValue({
      data: { total: 5, items: Array.from({ length: 20 }, (_, i) => ({
        id: i + 1, key: 'pc.cpu', old_value: null, new_value: String(i), source: 'agent',
        retention_days: 180, changed_at: `2026-08-01 ${String(19 - i).padStart(2, '0')}:00:00`
      })) }
    } as any)
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wrapper.findAll('.hm-row')).toHaveLength(20)

    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'pc.cpu', value: '999', changed_at: '2026-08-02 10:00:00' })
    await flushPromises()
    const rows = wrapper.findAll('.hm-row')
    expect(rows).toHaveLength(20)
    // 头部是新行,尾部最旧行('00:00:00')被弹出
    expect(rows[0].text()).toContain('999')
    expect(wrapper.text()).not.toContain('00:00:00')
  })

  it('有筛选条件时 WS 变更 → 计数徽章,点击后刷新', async () => {
    mockList()
    const wrapper = mountModal()
    await openModal(wrapper)
    // 设定开始时间 → 触发 watch → 重新加载(带 start 参数)
    await wrapper.find('.set-start').trigger('click')
    await flushPromises()
    expect(historyApiMock.list.mock.calls.at(-1)![0].start).toBe('2026-08-01 00:00:00')
    const callsAfterFilter = historyApiMock.list.mock.calls.length

    // 有筛选 → 新变更只计数不插入
    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'pc.cpu', value: '88', changed_at: '2026-08-02 10:00:00' })
    await flushPromises()
    expect(wrapper.findAll('.hm-row')).toHaveLength(2)
    const badge = wrapper.find('.hm-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('有 1 条新变更')

    // 点击徽章 → refresh(重置计数 + 重新加载)
    await badge.trigger('click')
    await flushPromises()
    expect(historyApiMock.list.mock.calls.length).toBeGreaterThan(callsAfterFilter)
    expect(wrapper.find('.hm-badge').exists()).toBe(false)
  })

  it('翻页 → 用游标(before_id)重新加载,不重复', async () => {
    mockList()
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(historyApiMock.list).toHaveBeenCalledTimes(1)

    await wrapper.find('.go-page-2').trigger('click')
    await flushPromises()
    expect(historyApiMock.list).toHaveBeenCalledTimes(2)
    // 游标分页:传上一页最后一条 id,不传 page(实时写入下翻页不重复)
    expect(historyApiMock.list.mock.calls[1][0]).toEqual(
      expect.objectContaining({ key: 'pc.cpu', before_id: expect.any(Number), page_size: 20 })
    )
    expect(historyApiMock.list.mock.calls[1][0].page).toBeUndefined()
  })

  it('切换每页条数 → 以新 pageSize 重新加载', async () => {
    mockList()
    const wrapper = mountModal()
    await openModal(wrapper)

    await wrapper.find('.go-page-size').trigger('click')
    await flushPromises()
    expect(historyApiMock.list.mock.calls.at(-1)![0].page_size).toBe(50)
  })

  it('导出 CSV → 调用 exportCsv 并触发下载', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    const exportBtn = wrapper.findAll('button').find(b => b.text().includes('导出 CSV'))!
    await exportBtn.trigger('click')
    await flushPromises()
    expect(historyApiMock.exportCsv).toHaveBeenCalledWith(expect.objectContaining({ key: 'pc.cpu' }))
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled()
  })

  it('带筛选导出 → 参数携带 start/end', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    // 两个日期选择器:第一个绑 filterStart,第二个绑 filterEnd,需分别操作
    const pickers = wrapper.findAll('.n-date-picker')
    await pickers[0].find('.set-start').trigger('click')   // filterStart = 开始时间
    await pickers[1].find('.set-end').trigger('click')     // filterEnd = 结束时间
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text().includes('导出 CSV'))!.trigger('click')
    await flushPromises()
    const params = historyApiMock.exportCsv.mock.calls.at(-1)![0]
    expect(params.start).toBe('2026-08-01 00:00:00')
    expect(params.end).toBe('2026-08-02 00:00:00')
  })

  it('关闭弹窗 → emit update:show 并清理 WS 监听', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wsCleanupMock).not.toHaveBeenCalled()

    await wrapper.find('.close-modal').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('update:show')![0]).toEqual([false])
    // 组件自身 show 由父级 v-model 控制,不因 emit 而改变
    expect(wrapper.find('.n-modal').exists()).toBe(true)

    // 父级把 show 置 false → 弹窗消失并清理 WS 监听
    await wrapper.setProps({ show: false })
    expect(wrapper.find('.n-modal').exists()).toBe(false)
    expect(wsCleanupMock).toHaveBeenCalled()
  })

  it('重新打开 → 重新注册 WS 并加载数据', async () => {
    const wrapper = mountModal()
    await openModal(wrapper)
    await wrapper.find('.close-modal').trigger('click')
    await flushPromises()
    await wrapper.setProps({ show: false })
    await flushPromises()

    await wrapper.setProps({ show: true })
    await flushPromises()
    expect(wsOnMock).toHaveBeenCalledTimes(2)
    expect(historyApiMock.list.mock.calls.length).toBe(2)
  })

  it('WS 变更(可绘图格式)→ 实时插入趋势图数据点', async () => {
    historyApiMock.trend.mockResolvedValue({ data: { points: [], kind: 'duration' } })
    const wrapper = mountModal()
    await openModal(wrapper)
    // 无数据点时趋势图不渲染
    expect(wrapper.find('.trend-chart-stub').exists()).toBe(false)

    // WS 推送时长值 → 解析为秒并插入(plotKind 相同才插入)
    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'pc.cpu', value: '3h 25m', changed_at: '2026-08-01 10:30:00' })
    await flushPromises()

    // find() 返回 DOMWrapper 没有 props(),需用 findComponent 按名称查找
    const chart = wrapper.findComponent({ name: 'TrendChart' })
    expect(chart.exists()).toBe(true)
    const pts = (chart.props('points') as any[])
    expect(pts).toHaveLength(1)
    expect(pts[0]).toEqual({ changed_at: '2026-08-01 10:30:00', value: 12300, raw: '3h 25m' })
  })

  it('WS 推送与 plotKind 不匹配的值(如 number 视图收到时长)→ 不插入趋势点', async () => {
    historyApiMock.trend.mockResolvedValue({ data: { points: [], kind: 'number' } })
    const wrapper = mountModal()
    await openModal(wrapper)

    const wsHandler = wsOnMock.mock.calls[0][0]
    // '17h' 会被解析为 duration,与当前 number 视图不匹配 → 不插入
    wsHandler('kv.changed', { key: 'pc.cpu', value: '17h', changed_at: '2026-08-01 10:30:00' })
    await flushPromises()
    expect(wrapper.find('.trend-chart-stub').exists()).toBe(false)
  })

  it('列表加载失败 → 不崩溃,显示占位', async () => {
    historyApiMock.list.mockRejectedValue(new Error('offline'))
    const wrapper = mountModal()
    await openModal(wrapper)
    expect(wrapper.find('.n-empty').text()).toContain('暂无历史记录')
  })
})
