// ============================================================
// Dashboard 仪表盘页测试
// 覆盖:统计卡片 / 设备卡片 / 变更动态(WS kv.changed 实时,去重与 20 条上限)/
//      设备心跳更新 / 设备注册事件 / 路由跳转 / 历史弹窗
// naive-ui 与子组件(StatCard/StatusBadge/HistoryModal)全部 stub
// ============================================================
import { defineComponent, h } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const dashboardApiMock = vi.hoisted(() => ({ stats: vi.fn(), recentChanges: vi.fn() }))
const deviceApiMock = vi.hoisted(() => ({ list: vi.fn(), variables: vi.fn() }))
// 捕获 useWebSocket 注册的 on 回调,用于模拟 WS 消息
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({ dashboardApi: dashboardApiMock, deviceApi: deviceApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))

// ---- 子组件 stub ----
vi.mock('../components/StatCard.vue', () => ({
  default: defineComponent({
    props: ['icon', 'iconBg', 'iconColor', 'primary', 'secondary', 'label', 'trend', 'to'],
    setup(props) {
      return () => h('div', { class: 'stat-card' }, [
        h('span', { class: 'stat-label' }, props.label),
        h('span', { class: 'stat-primary' }, String(props.primary)),
        props.secondary !== undefined ? h('span', { class: 'stat-secondary' }, `/ ${props.secondary}`) : null
      ])
    }
  })
}))
vi.mock('../components/StatusBadge.vue', () => ({
  default: defineComponent({
    props: ['online'],
    setup(props) { return () => h('span', { class: 'status-badge' }, props.online ? '在线' : '离线') }
  })
}))
vi.mock('../components/HistoryModal.vue', () => ({
  default: defineComponent({
    props: ['show', 'keyProp'],
    emits: ['update:show'],
    // 必须在 render 内求值 props.show,弹窗打开后才会重新渲染
    setup(props) {
      return () => (props.show ? h('div', { class: 'history-modal-stub' }, props.keyProp) : null)
    }
  })
}))
// 剪切板面板 stub:自包含组件(拉数据+订阅 WS),Dashboard 集成后只需验证渲染
vi.mock('../components/ClipboardPanel.vue', () => ({
  default: defineComponent({
    name: 'ClipboardPanelStub',
    setup() { return () => h('div', { class: 'clipboard-panel-stub' }, '剪切板面板') }
  })
}))

// ---- naive-ui 轻量 stub ----
vi.mock('naive-ui', () => ({
  // 表格 stub:对每行调用 columns 的 render 渲染单元格(变更动态内容可见)
  NDataTable: defineComponent({
    props: ['data', 'columns'],
    setup(props, { slots }) {
      return () => h('div', { class: 'n-data-table' }, [
        ...(props.data || []).map((r: any, i: number) =>
          h('div', { class: 'table-row', key: i }, [
            ...(props.columns || []).map((c: any, j: number) =>
              h('div', { class: `cell-${c.key}`, key: j }, c.render ? [c.render(r)] : [String(r[c.key] ?? '')])
            )
          ])
        ),
        (props.data || []).length === 0 ? slots.empty?.() : null
      ])
    }
  }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NTag: defineComponent({ props: ['size', 'bordered', 'round', 'type'], setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) } })
}))

import Dashboard from './Dashboard.vue'

beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})
enableAutoUnmount(afterEach)

const DEFAULT_STATS = {
  total_devices: 5, online_devices: 3, total_services: 2, running_services: 1,
  total_keys: 120, network_status: 'online', public_ip: '1.2.3.4', system_health: 98
}

function pcDevice(overrides: Record<string, unknown> = {}) {
  return {
    id: 'pc-1', name: 'pc', hostname: 'pc-host', type: 'computer', group: '办公室',
    version: '2.1', ip: '192.168.1.10', mac: '', os: 'windows', online: true,
    cpu: 42, memory: 60, disk: 30, volume: 80, notes: '', uptime: '1h',
    heartbeat_timeout: 60, last_heartbeat: '2026-08-04 10:00:00', registered_at: '2026-01-01',
    ...overrides
  }
}

function haDevice() {
  return {
    id: 'ha-1', name: 'home', hostname: 'ha-host', type: 'ha', group: '智能家居',
    version: '1.0', ip: '192.168.1.20', mac: '', os: 'homeassistant', online: true,
    notes: '', uptime: '24h', heartbeat_timeout: 60, last_heartbeat: '2026-08-04 09:00:00', registered_at: '2026-01-01'
  }
}

// 取出 useWebSocket.on 注册的 WS 处理器
function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

function mountPage() {
  return mount(Dashboard, {
    global: { mocks: { $router: { push: routerPush } }, stubs: { 'ion-icon': true } }
  })
}

describe('Dashboard.vue', () => {
  beforeEach(() => {
    Object.values(dashboardApiMock).forEach((m) => (m as any).mockReset())
    Object.values(deviceApiMock).forEach((m) => (m as any).mockReset())
    wsOnMock.mockReset()
    wsOnMock.mockReturnValue(() => {})
    routerPush.mockReset()
    dashboardApiMock.stats.mockResolvedValue({ data: DEFAULT_STATS })
    deviceApiMock.list.mockResolvedValue({ data: [] })
    deviceApiMock.variables.mockResolvedValue({ data: [] })
    dashboardApiMock.recentChanges.mockResolvedValue({ data: [] })
  })

  it('挂载后加载统计并渲染 4 张统计卡片', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [pcDevice()] })
    const wrapper = mountPage()
    await flushPromises()

    expect(dashboardApiMock.stats).toHaveBeenCalled()
    expect(deviceApiMock.list).toHaveBeenCalled()
    expect(dashboardApiMock.recentChanges).toHaveBeenCalledWith(20)

    const cards = wrapper.findAll('.stat-card')
    expect(cards).toHaveLength(4)
    expect(cards[0].text()).toContain('在线设备')
    expect(cards[0].text()).toContain('3')
    expect(cards[0].text()).toContain('/ 5')
    expect(cards[1].text()).toContain('设备 / 变量')
    expect(cards[2].text()).toContain('网络状态')
    expect(cards[2].text()).toContain('正常')
    expect(cards[3].text()).toContain('系统健康度')
    expect(cards[3].text()).toContain('98%')
  })

  it('无设备时显示空状态', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.n-empty').text()).toContain('暂无设备')
    expect(wrapper.findAll('.device-card')).toHaveLength(0)
  })

  it('设备卡片渲染名称/标签/心跳与四项指标', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [pcDevice()] })
    const wrapper = mountPage()
    await flushPromises()

    const card = wrapper.find('.device-card')
    expect(card.text()).toContain('pc')
    expect(card.text()).toContain('pc-host')
    expect(card.text()).toContain('办公室')
    expect(card.text()).toContain('computer')
    expect(card.text()).toContain('v2.1')
    expect(card.text()).toContain('在线')
    expect(card.findAll('.dc-metric')).toHaveLength(4)
    const vals = card.findAll('.dm-val').map((v) => v.text())
    expect(vals).toEqual(['42%', '60%', '30%', '80%'])
  })

  it('HA 设备加载变量统计:显示数量与子设备图标', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [haDevice()] })
    deviceApiMock.variables.mockResolvedValue({
      data: [
        { id: 1, key: 'home.客厅温度', value: '26', type: 'float', source: 'homeassistant', updated_at: '2026-08-04 10:00:00', expire_seconds: null, retention_days: 180 },
        { id: 2, key: 'home.客厅湿度', value: '60', type: 'float', source: 'homeassistant', updated_at: '2026-08-04 10:00:00', expire_seconds: null, retention_days: 180 },
        { id: 3, key: 'home.书房亮度', value: '80', type: 'int', source: 'homeassistant', updated_at: '2026-08-04 10:00:00', expire_seconds: null, retention_days: 180 }
      ]
    } as any)
    const wrapper = mountPage()
    await flushPromises()

    expect(deviceApiMock.variables).toHaveBeenCalledWith('ha-1')
    const card = wrapper.find('.device-card')
    expect(card.find('.ha-count').text()).toBe('共 3 个变量')
    const chips = card.findAll('.ha-chip')
    expect(chips).toHaveLength(2)  // 客厅(温度/湿度去重)、书房(亮度)
    expect(chips[0].text()).toContain('客厅')
    expect(chips[1].text()).toContain('书房')
  })

  it('后端全部未响应时保持默认空数据,不报错', async () => {
    dashboardApiMock.stats.mockRejectedValue(new Error('offline'))
    deviceApiMock.list.mockRejectedValue(new Error('offline'))
    dashboardApiMock.recentChanges.mockRejectedValue(new Error('offline'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.device-card')).toHaveLength(0)
    expect(wrapper.findAll('.table-row')).toHaveLength(0)
  })

  it('初始 recentChanges 填充变更动态,WS 推送同一条被去重跳过', async () => {
    dashboardApiMock.recentChanges.mockResolvedValue({
      data: [
        { id: 1, key: 'old.key', old_value: '1', new_value: '2', source: 'agent', retention_days: 180, changed_at: '2026-08-04 10:00:00' }
      ]
    } as any)
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(1)

    // WS 推送与初始数据同 uid(key|changed_at) → 跳过
    wsHandler()('kv.changed', { key: 'old.key', value: '2', old_value: '1', source: 'agent', changed_at: '2026-08-04 10:00:00' })
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(1)
  })

  it('WS kv.changed 实时插入变更动态到第一行', async () => {
    const wrapper = mountPage()
    await flushPromises()

    wsHandler()('kv.changed', { key: 'new.key', value: '42', source: 'agent', changed_at: '2026-08-04 12:00:00' })
    await flushPromises()

    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('new.key')
    expect(rows[0].text()).toContain('agent')
    expect(rows[0].text()).toContain('(新增) → 42')
    // kv.changed 同时刷新统计
    expect(dashboardApiMock.stats).toHaveBeenCalledTimes(2)
  })

  it('WS kv.changed 同 uid 推送两次只保留一条', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const data = { key: 'dup.key', value: '1', source: 'agent', changed_at: '2026-08-04 11:00:00' }
    const h = wsHandler()
    h('kv.changed', data)
    h('kv.changed', data)
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(1)
  })

  it('变更动态超过 20 条淘汰最旧,被淘汰的 uid 可再次加入', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const h = wsHandler()

    // 连续推 21 条
    for (let i = 1; i <= 21; i++) {
      h('kv.changed', { key: `k${i}`, value: String(i), changed_at: `2026-08-04 00:${String(i).padStart(2, '0')}:00` })
    }
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(20)  // 上限 20 条
    expect(rows[0].text()).toContain('k21')   // 最新在前
    expect(rows[19].text()).toContain('k2')   // k1 已被淘汰

    // 被淘汰的最旧一条重新推送 → 淘汰时已从 liveSeen 移除,可再次加入
    h('kv.changed', { key: 'k1', value: '1', changed_at: '2026-08-04 00:01:00' })
    await flushPromises()
    const rows2 = wrapper.findAll('.table-row')
    expect(rows2).toHaveLength(20)
    expect(rows2[0].text()).toContain('k1')
  })

  it('WS device.heartbeat 更新设备指标,离线后隐藏指标区', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [pcDevice()] })
    const wrapper = mountPage()
    await flushPromises()
    const h = wsHandler()

    // 心跳推入新指标
    h('device.heartbeat', { name: 'pc', cpu: 88, memory: 55, online: true })
    await flushPromises()
    const card = wrapper.find('.device-card')
    const vals = card.findAll('.dm-val').map((v) => v.text())
    expect(vals[0]).toBe('88%')
    expect(vals[1]).toBe('55%')

    // 心跳上报离线 → 指标区隐藏
    h('device.heartbeat', { name: 'pc', online: false })
    await flushPromises()
    expect(card.findAll('.dc-metric')).toHaveLength(0)
  })

  it('WS heartbeat 事件刷新统计数据', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(dashboardApiMock.stats).toHaveBeenCalledTimes(1)
    wsHandler()('heartbeat', {})
    await flushPromises()
    expect(dashboardApiMock.stats).toHaveBeenCalledTimes(2)
  })

  it('WS device.registered 事件重新拉取设备列表', async () => {
    deviceApiMock.list
      .mockResolvedValueOnce({ data: [pcDevice()] })
      .mockResolvedValueOnce({ data: [pcDevice(), haDevice()] })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.device-card')).toHaveLength(1)

    wsHandler()('device.registered', { name: 'home' })
    await flushPromises()
    expect(deviceApiMock.list).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.device-card')).toHaveLength(2)
  })

  it('点击设备卡片跳转到设备详情页', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [pcDevice()] })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.device-card').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/devices/pc-1')
  })

  it('点击 CPU 指标打开历史记录弹窗', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [pcDevice()] })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.history-modal-stub').exists()).toBe(false)
    await wrapper.findAll('.dc-metric')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.history-modal-stub').exists()).toBe(true)
    expect(wrapper.find('.history-modal-stub').text()).toBe('pc.cpu')
  })

  it('渲染剪切板面板(与变更动态并排)', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.clipboard-panel-stub').exists()).toBe(true)
    expect(wrapper.find('.lower-grid').exists()).toBe(true)
  })
})
