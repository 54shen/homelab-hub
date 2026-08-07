// ============================================================
// DeviceDetail 设备详情页测试
// naive-ui / vue-router / echarts / API / useWebSocket 全部 mock
// 覆盖:设备渲染 / 空状态 / 变量增删改 / 心跳超时 / 删除设备 / WS 实时更新 / HA 子设备
// ============================================================
import { defineComponent, h, nextTick } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const deviceApiMock = vi.hoisted(() => ({ get: vi.fn(), unregister: vi.fn(), variables: vi.fn() }))
const kvApiMock = vi.hoisted(() => ({ set: vi.fn(), delete: vi.fn() }))
const routerPushMock = vi.hoisted(() => vi.fn())
// 捕获 useWebSocket 注册的 on 回调,用于模拟 WS 消息
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))
// echarts 实例桩:断言 setOption 被调用(图表更新)
const chartMock = vi.hoisted(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
const echartsInitMock = vi.hoisted(() => vi.fn(() => chartMock))
const msgSuccess = vi.hoisted(() => vi.fn())
const msgError = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({ deviceApi: deviceApiMock, kvApi: kvApiMock }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'dev-1' }, query: {} }),
  useRouter: () => ({ push: routerPushMock })
}))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))
vi.mock('echarts', () => ({
  init: echartsInitMock,
  graphic: { LinearGradient: class {} }
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
    setup(props) {
      // 必须在 render 内求值 props.show,弹窗打开后才重新渲染
      return () => props.show
        ? h('div', { class: 'history-modal-stub' }, [h('span', { class: 'hm-key' }, props.keyProp)])
        : null
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
  NCard: defineComponent({
    props: ['title', 'size'],
    setup(props, { slots }) {
      return () => h('div', { class: 'n-card' }, [
        h('div', { class: 'n-card-title' }, props.title),
        slots['header-extra']?.(),
        slots.default?.()
      ])
    }
  }),
  // 表格 stub:对每行调用 columns 的 render 渲染单元格(编辑/删除/历史按钮可点)
  NDataTable: defineComponent({
    props: ['data', 'columns'],
    setup(props) {
      return () => h('div', { class: 'n-data-table' }, [
        ...(props.data || []).map((r: any, i: number) =>
          h('div', { class: 'table-row', key: i }, [
            ...(props.columns || []).map((c: any, j: number) =>
              h('div', { class: `cell-${c.key}`, key: j }, c.render ? [c.render(r)] : [String(r[c.key] ?? '')])
            )
          ])
        )
      ])
    }
  }),
  NDescriptions: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-descriptions' }, slots.default?.()) } }),
  NDescriptionsItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', { class: 'n-descriptions-item' }, [h('span', {}, props.label), slots.default?.()]) } }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NPopconfirm: defineComponent({
    emits: ['positive-click'],
    setup(_, { slots, emit }) {
      return () => h('div', { class: 'n-popconfirm' }, [
        slots.trigger?.(),
        h('button', { class: 'confirm-btn', onClick: () => emit('positive-click') }, '确定')
      ])
    }
  }),
  NProgress: defineComponent({ props: ['percentage'], setup(props) { return () => h('div', { class: 'n-progress' }, `进度${props.percentage}`) } }),
  NSpin: defineComponent({ props: ['show'], setup(_, { slots }) { return () => h('div', { class: 'n-spin' }, slots.default?.()) } }),
  NTag: defineComponent({ props: ['bordered', 'round'], setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) } }),
  useMessage: () => ({ success: msgSuccess, error: msgError })
}))

import DeviceDetail from './DeviceDetail.vue'

// jsdom 没有 URL.createObjectURL
beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})
// 每个测试后自动 unmount(清理 WS 监听/resize 监听/图表)
enableAutoUnmount(afterEach)

const deviceData = {
  id: 'dev-1', name: 'PC1', hostname: 'pc-01', type: 'computer',
  cpu: 42, memory: 60, disk: 30, volume: 50, uptime: '3天',
  group: '办公', online: true, version: '1.0.0',
  ip: '192.168.1.10', mac: 'AA:BB:CC', os: 'Windows 11',
  registered_at: '2026-01-01 10:00:00', last_heartbeat: '2026-08-01 10:00:00',
  notes: '主电脑', heartbeat_timeout: 60
}

function mockVars() {
  const rows = [
    { id: 1, key: 'PC1.cpu', value: '42', type: 'int', source: 'agent', updated_at: '2026-08-01 10:00:00', expire_seconds: null, retention_days: 180 },
    { id: 2, key: 'PC1.memory', value: '60', type: 'int', source: 'agent', updated_at: '2026-08-01 10:00:00', expire_seconds: null, retention_days: 180 },
    { id: 3, key: 'PC1.uptime', value: '3天', type: 'string', source: 'agent', updated_at: '2026-08-01 10:00:00', expire_seconds: null, retention_days: 180 }
  ]
  // 深拷贝:组件内修改 row.value 等不得污染后续测试共享的 mock 数据
  deviceApiMock.variables.mockResolvedValue({ data: rows.map((r) => ({ ...r })) } as any)
}

function mockDevice() {
  // 深拷贝:WS 更新会直接改 device 对象,不得污染后续测试
  deviceApiMock.get.mockResolvedValue({ data: { ...deviceData } })
  mockVars()
}

function mountPage() {
  // 模板里用的是全局 $router(vue-router 插件注入),需要单独提供
  return mount(DeviceDetail, {
    global: {
      mocks: { $router: { push: routerPushMock } },
      stubs: { 'ion-icon': true }
    }
  })
}

describe('DeviceDetail.vue', () => {
  beforeEach(() => {
    Object.values(deviceApiMock).forEach((m) => (m as any).mockReset())
    Object.values(kvApiMock).forEach((m) => (m as any).mockReset())
    routerPushMock.mockReset()
    wsOnMock.mockReset()
    wsOnMock.mockReturnValue(() => {})
    echartsInitMock.mockReset()
    chartMock.setOption.mockReset()
    chartMock.resize.mockReset()
    chartMock.dispose.mockReset()
    msgSuccess.mockReset(); msgError.mockReset()
    deviceApiMock.get.mockResolvedValue({ data: null })
    deviceApiMock.variables.mockResolvedValue({ data: [] })
    kvApiMock.set.mockResolvedValue({ data: {} })
    kvApiMock.delete.mockResolvedValue({ data: {} })
  })

  it('挂载后加载设备与变量,渲染详情、指标与心跳图', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    await nextTick()
    expect(deviceApiMock.get).toHaveBeenCalledWith('dev-1')
    expect(deviceApiMock.variables).toHaveBeenCalledWith('dev-1')
    expect(wrapper.find('.hero-name').text()).toBe('PC1')
    expect(wrapper.text()).toContain('pc-01')
    expect(wrapper.text()).toContain('在线')
    // 指标卡显示 CPU 值
    expect(wrapper.text()).toContain('42%')
    // 变量表 3 行
    expect(wrapper.findAll('.table-row')).toHaveLength(3)
    // 心跳图初始化并设置 option
    expect(echartsInitMock).toHaveBeenCalled()
    expect(chartMock.setOption).toHaveBeenCalled()
  })

  it('设备不存在 → 显示空状态', async () => {
    deviceApiMock.get.mockRejectedValue(new Error('404'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.n-empty').text()).toContain('设备不存在')
  })

  it('点击返回 → 跳转设备列表', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.back-row button').trigger('click')
    expect(routerPushMock).toHaveBeenCalledWith('/devices')
  })

  it('点击指标卡 → 打开该指标的历史弹窗', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    // 第一张指标卡是 CPU
    await wrapper.findAll('.card-grid .n-card')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.history-modal-stub').exists()).toBe(true)
    expect(wrapper.find('.hm-key').text()).toBe('PC1.cpu')
  })

  it('点击变量表的 key → 打开历史弹窗', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.table-row')[0].find('.key-link').trigger('click')
    await flushPromises()
    expect(wrapper.find('.hm-key').text()).toBe('PC1.cpu')
  })

  it('修改变量值:Enter 保存 → 调用 kvApi.set 并更新单元格', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[0]
    await row.findAll('button').find((b) => b.text().includes('修改'))!.trigger('click')
    await flushPromises()
    // 值单元格变为输入框
    const input = wrapper.find('.var-edit-input')
    expect(input.exists()).toBe(true)
    await input.setValue('99')
    // 注意:手写 onKeydown 比较的是大写 'Enter'(vue-test-utils 的 keydown.enter 生成小写,不匹配)
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(kvApiMock.set).toHaveBeenCalledWith(expect.objectContaining({
      key: 'PC1.cpu', value: '99', type: 'int', source: expect.stringContaining('Web')
    }))
    expect(msgSuccess).toHaveBeenCalled()
    // 单元格显示新值
    expect(row.find('.cell-value').text()).toContain('99')
  })

  it('修改时值未改动 → 不调用 kvApi.set', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[0]
    await row.findAll('button').find((b) => b.text().includes('修改'))!.trigger('click')
    await flushPromises()
    await wrapper.find('.var-edit-input').setValue('42')  // 与原值相同
    await wrapper.find('.var-edit-input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(kvApiMock.set).not.toHaveBeenCalled()
  })

  it('Escape 取消编辑,恢复原值显示', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[0]
    await row.findAll('button').find((b) => b.text().includes('修改'))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.var-edit-input').exists()).toBe(true)
    await wrapper.find('.var-edit-input').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.find('.var-edit-input').exists()).toBe(false)
    expect(row.find('.cell-value').text()).toContain('42')
  })

  it('删除变量 → 确认后调用 kvApi.delete 并移除行', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(3)
    const row = wrapper.findAll('.table-row')[0]
    await row.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(kvApiMock.delete).toHaveBeenCalledWith('PC1.cpu')
    expect(msgSuccess).toHaveBeenCalled()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('删除设备 → 确认后 unregister 并跳回设备列表', async () => {
    mockDevice()
    deviceApiMock.unregister.mockResolvedValue({ data: {} })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.detail-hero .confirm-btn').trigger('click')
    await flushPromises()
    expect(deviceApiMock.unregister).toHaveBeenCalledWith('dev-1')
    expect(msgSuccess).toHaveBeenCalledWith('设备已删除')
    expect(routerPushMock).toHaveBeenCalledWith('/devices')
  })

  it('WebSocket device.heartbeat → 更新指标卡并重绘图表', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    await nextTick()
    const wsHandler = wsOnMock.mock.calls[0][0]
    const callsBefore = chartMock.setOption.mock.calls.length
    wsHandler('device.heartbeat', { name: 'PC1', cpu: 99, memory: 88, disk: 70, online: true })
    await nextTick()
    // 指标卡更新为新值
    expect(wrapper.text()).toContain('99%')
    expect(wrapper.text()).toContain('88%')
    // 变量表同步心跳字段
    expect(wrapper.findAll('.table-row')[0].find('.cell-value').text()).toContain('99')
    // 图表重绘
    expect(chartMock.setOption.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  it('WebSocket kv.changed → 未知变量插入列表头部', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'PC1.disk', value: '20', source: 'ws', changed_at: '2026-08-01 10:05:00' })
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(4)
    expect(rows[0].find('.cell-key').text()).toContain('PC1.disk')
  })

  it('WebSocket 心跳设备名不匹配 → 忽略', async () => {
    mockDevice()
    const wrapper = mountPage()
    await flushPromises()
    await nextTick()
    const wsHandler = wsOnMock.mock.calls[0][0]
    const callsBefore = chartMock.setOption.mock.calls.length
    wsHandler('device.heartbeat', { name: 'OtherDevice', cpu: 1, online: true })
    await nextTick()
    expect(chartMock.setOption.mock.calls.length).toBe(callsBefore)
    expect(wrapper.text()).toContain('42%')
  })

  it('HA 设备:按属性后缀分组渲染子设备卡片,点击属性打开历史', async () => {
    deviceApiMock.get.mockResolvedValue({
      data: { ...deviceData, id: 'ha-1', name: '客厅', type: 'ha', hostname: '' }
    })
    const ts = new Date(Date.now() - 5 * 60000).toISOString()
    deviceApiMock.variables.mockResolvedValue({
      data: [
        { id: 1, key: '客厅.空调开关', value: 'on', type: 'string', source: 'ha', updated_at: ts, expire_seconds: null, retention_days: 180 },
        { id: 2, key: '客厅.空调当前温度', value: '26', type: 'string', source: 'ha', updated_at: ts, expire_seconds: null, retention_days: 180 },
        { id: 3, key: '客厅.灯亮度', value: '80', type: 'string', source: 'ha', updated_at: ts, expire_seconds: null, retention_days: 180 }
      ]
    } as any)
    const wrapper = mountPage()
    await flushPromises()
    // 空调(开关+当前温度)/ 灯(亮度)两张卡片
    const cards = wrapper.findAll('.subdevice-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('空调')
    expect(cards[0].text()).toContain('已开启')
    expect(cards[1].text()).toContain('灯')
    // 点击属性 → 打开该变量历史弹窗
    await cards[0].find('.sd-prop-value').trigger('click')
    await flushPromises()
    expect(wrapper.find('.hm-key').text()).toBe('客厅.空调开关')
  })

  it('HA 设备无子设备数据 → 显示空提示', async () => {
    deviceApiMock.get.mockResolvedValue({
      data: { ...deviceData, id: 'ha-1', name: '客厅', type: 'ha', hostname: '' }
    })
    deviceApiMock.variables.mockResolvedValue({ data: [] })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无子设备数据')
  })
})
