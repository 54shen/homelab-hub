// ============================================================
// DeviceManager 设备管理页测试
// 卡片/列表视图、分组筛选、HA 摘要、WS 实时更新
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const deviceApiMock = vi.hoisted(() => ({ list: vi.fn(), variables: vi.fn() }))
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))

vi.mock('../api', () => ({ deviceApi: deviceApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))
vi.mock('../composables/useUISetting', async () => {
  // 必须返回真正的 ref:组件里 viewMode 是 computed(get/set 依赖 viewModeStr),
  // 普通对象没有响应式追踪,赋值后 computed 不会重新计算
  const { ref } = await import('vue')
  return { useUISetting: (key: string, def: string) => ref(def) }
})
vi.mock('../components/StatusBadge.vue', () => ({
  default: defineComponent({
    props: ['online'],
    setup(props) { return () => h('span', { class: 'status-badge' }, props.online ? '在线' : '离线') }
  })
}))
vi.mock('../components/HistoryModal.vue', () => ({
  default: defineComponent({ template: '<div class="history-modal-stub"></div>' })
}))

vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) }
  }),
  NButtonGroup: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-button-group' }, slots.default?.()) } }),
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', {}, slots.default?.()) } }),
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
  NDataTable: defineComponent({
    props: ['data'],
    setup(props) {
      return () => h('div', { class: 'n-data-table' },
        (props.data || []).map((r: any) => h('div', { class: 'table-row' }, r.name)))
    }
  }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NTag: defineComponent({ props: ['type'], setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) } }),
  useMessage: () => ({ success: vi.fn(), error: vi.fn() })
}))

import DeviceManager from './DeviceManager.vue'

let wrapper: ReturnType<typeof mount> | null = null

function device(id: string, name: string, extra: Record<string, unknown> = {}) {
  return {
    id, name, hostname: '', type: 'pc', group: '默认', version: '1.0', ip: '',
    mac: '', os: '', online: false, cpu: null, memory: null, disk: null,
    volume: null, muted: false, uptime: '', notes: '', heartbeat_timeout: 180,
    last_heartbeat: new Date().toISOString(), registered_at: '',
    ...extra
  }
}

beforeEach(() => {
  Object.values(deviceApiMock).forEach((m) => (m as any).mockReset())
  wsOnMock.mockReset()
  wsOnMock.mockReturnValue(() => {})
  deviceApiMock.list.mockResolvedValue({ data: [] })
  deviceApiMock.variables.mockResolvedValue({ data: [] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function mountPage() {
  wrapper = mount(DeviceManager, {
    global: {
      stubs: { 'ion-icon': true },
      mocks: { $router: { push: vi.fn() } }
    }
  })
  return wrapper
}

function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

describe('DeviceManager.vue', () => {
  it('挂载后加载并渲染设备卡片', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [device('a1', '书房电脑', { online: true, cpu: 42 })] })
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('书房电脑')
    expect(w.text()).toContain('42%')
    expect(w.text()).toContain('在线')
  })

  it('无设备时显示空状态', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('.n-empty').text()).toContain('暂无设备')
  })

  it('按分组筛选设备', async () => {
    deviceApiMock.list.mockResolvedValue({
      data: [
        device('a1', '电脑A', { group: '书房' }),
        device('a2', '电脑B', { group: '客厅' })
      ]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.device-card')).toHaveLength(2)

    await w.find('.page-header select').setValue('书房')
    await flushPromises()
    const cards = w.findAll('.device-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('电脑A')
  })

  it('视图切换:卡片 → 列表', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [device('a1', '电脑A')] })
    const w = mountPage()
    await flushPromises()
    expect(w.find('.device-card').exists()).toBe(true)

    // 点列表视图按钮(第二个图标按钮)
    const listBtn = w.findAll('.n-button-group button')[1]
    await listBtn.trigger('click')
    await flushPromises()
    expect(w.find('.device-card').exists()).toBe(false)
    expect(w.find('.n-data-table').exists()).toBe(true)
    expect(w.find('.table-row').text()).toContain('电脑A')
  })

  it('离线设备不显示指标条', async () => {
    deviceApiMock.list.mockResolvedValue({
      data: [device('a1', '离线机', { online: false, cpu: 99 })]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('离线机')
    expect(w.text()).not.toContain('99%')   // 离线时不渲染指标
  })

  it('HA 设备加载变量统计', async () => {
    deviceApiMock.list.mockResolvedValue({
      data: [device('ha1', 'HA', { type: 'ha', group: '智能家居' })]
    })
    deviceApiMock.variables.mockResolvedValue({
      data: [
        { id: 1, key: 'HA.客厅温度', value: '23', type: 'float', source: 'homeassistant', retention_days: 180, updated_at: '2026-08-01 10:00:00', expire_seconds: null },
        { id: 2, key: 'HA.客厅湿度', value: '50', type: 'int', source: 'homeassistant', retention_days: 180, updated_at: '2026-08-01 10:00:00', expire_seconds: null }
      ]
    })
    const w = mountPage()
    await flushPromises()
    expect(deviceApiMock.variables).toHaveBeenCalledWith('ha1')
    expect(w.text()).toContain('共 2 个变量')
  })

  it('WS device.heartbeat 更新设备指标', async () => {
    deviceApiMock.list.mockResolvedValue({
      data: [device('a1', '监控机', { online: true, cpu: 10, memory: 20 })]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('10%')

    wsHandler()('device.heartbeat', { name: '监控机', online: true, cpu: 88, memory: 99 })
    await flushPromises()
    expect(w.text()).toContain('88%')
    expect(w.text()).toContain('99%')
  })

  it('WS heartbeat 未知设备不报错', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [device('a1', '监控机')] })
    const w = mountPage()
    await flushPromises()
    wsHandler()('device.heartbeat', { name: '不存在的设备', online: true })
    await flushPromises()
    expect(w.findAll('.device-card')).toHaveLength(1)
  })

  it('WS device.unregistered 触发重新加载', async () => {
    deviceApiMock.list.mockResolvedValue({ data: [device('a1', '将被删除')] })
    const w = mountPage()
    await flushPromises()
    expect(deviceApiMock.list).toHaveBeenCalledTimes(1)

    wsHandler()('device.unregistered', { id: 'a1', name: '将被删除' })
    await flushPromises()
    expect(deviceApiMock.list).toHaveBeenCalledTimes(2)
  })
})
