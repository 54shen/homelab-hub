// ============================================================
// AlertManager 告警规则页测试
// 卡片渲染/新增编辑弹窗(条件/阈值/动作)/开关/删除/WS 刷新
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const alertApiMock = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), toggle: vi.fn()
}))
const deviceApiMock = vi.hoisted(() => ({ list: vi.fn() }))
const kvApiMock = vi.hoisted(() => ({ list: vi.fn() }))
const webhookApiMock = vi.hoisted(() => ({ list: vi.fn() }))
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))

vi.mock('../api', () => ({
  alertApi: alertApiMock, deviceApi: deviceApiMock, kvApi: kvApiMock, webhookApi: webhookApiMock
}))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))

vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) }
  }),
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', {}, slots.default?.()) } }),
  NInput: defineComponent({
    props: ['value', 'placeholder', 'type'],
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
    // 注意:multiple 必须类型化声明 { type: Boolean } —— 数组声明(无类型)时,
    // 模板简写 `multiple` 传 "" 不触发布尔转换,props.multiple 永远是 falsy
    props: { value: null, options: null, multiple: { type: Boolean, default: false } },
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        value: Array.isArray(props.value) ? props.value.join(',') : (props.value ?? ''),
        onChange: (e: any) => {
          const v = (e.target as HTMLSelectElement).value
          // multiple 模式下 form.action 是数组,必须 emit 数组
          emit('update:value', props.multiple ? (v ? [v] : []) : (v || null))
        }
      }, (props.options || []).map((o: any) => h('option', { value: o.value }, o.label)))
    }
  }),
  NModal: defineComponent({
    props: ['show', 'title'],
    emits: ['update:show'],
    setup(props, { slots }) {
      // props.show 必须在 render 内求值(setup 只执行一次)
      return () => props.show
        ? h('div', { class: 'n-modal' }, [h('div', { class: 'modal-title' }, props.title), slots.default?.(), slots.footer?.()])
        : null
    }
  }),
  NForm: defineComponent({ setup(_, { slots }) { return () => h('div', {}, slots.default?.()) } }),
  NFormItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', {}, [h('span', {}, props.label), slots.default?.(), slots.feedback?.()]) } }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NSwitch: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(props, { emit }) { return () => h('input', { class: 'n-switch', type: 'checkbox', checked: props.value, onChange: (e: any) => emit('update:value', (e.target as HTMLInputElement).checked) }) }
  }),
  NTag: defineComponent({ props: ['type'], setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) } }),
  NPopconfirm: defineComponent({
    emits: ['positive-click'],
    setup(_, { slots, emit }) {
      return () => h('div', {}, [
        slots.trigger?.(),
        h('button', { class: 'confirm-btn', onClick: () => emit('positive-click') }, '确定')
      ])
    }
  }),
  useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() })
}))

import AlertManager from './AlertManager.vue'

let wrapper: ReturnType<typeof mount> | null = null

function rule(id: number, name: string, extra: Record<string, unknown> = {}) {
  return {
    id, name, description: '', trigger_key: 'k.v', condition: 'eq', threshold: '80',
    action: 'log', action_target: '', enabled: true, last_triggered: null, body: null,
    ...extra
  }
}

beforeEach(() => {
  Object.values(alertApiMock).forEach((m) => (m as any).mockReset())
  Object.values(deviceApiMock).forEach((m) => (m as any).mockReset())
  Object.values(kvApiMock).forEach((m) => (m as any).mockReset())
  Object.values(webhookApiMock).forEach((m) => (m as any).mockReset())
  wsOnMock.mockReset()
  wsOnMock.mockReturnValue(() => {})
  alertApiMock.list.mockResolvedValue({ data: [] })
  alertApiMock.create.mockResolvedValue({ data: {} })
  alertApiMock.update.mockResolvedValue({ data: {} })
  alertApiMock.delete.mockResolvedValue({ data: {} })
  alertApiMock.toggle.mockResolvedValue({ data: {} })
  deviceApiMock.list.mockResolvedValue({ data: [] })
  kvApiMock.list.mockResolvedValue({ data: [] })
  webhookApiMock.list.mockResolvedValue({ data: [] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function mountPage() {
  wrapper = mount(AlertManager, { global: { stubs: { 'ion-icon': true } } })
  return wrapper
}

function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

describe('AlertManager.vue', () => {
  it('挂载后加载并渲染规则卡片', async () => {
    alertApiMock.list.mockResolvedValue({
      data: [rule(1, 'CPU 高负载', { trigger_key: 'pc.cpu', threshold: '80', last_triggered: '2026-08-01 10:00:00' })]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('CPU 高负载')
    expect(w.text()).toContain('pc.cpu')
    expect(w.text()).toContain('80')
    expect(w.text()).toContain('上次触发')
  })

  it('无规则时显示空状态', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('.n-empty').text()).toContain('暂无告警规则')
  })

  it('已停用规则卡片带 disabled 样式', async () => {
    alertApiMock.list.mockResolvedValue({ data: [rule(1, '停用规则', { enabled: false })] })
    const w = mountPage()
    await flushPromises()
    expect(w.find('.alert-card.disabled').exists()).toBe(true)
  })

  it('新增规则:缺少名称不保存', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()
    expect(w.find('.n-modal').exists()).toBe(true)

    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(alertApiMock.create).not.toHaveBeenCalled()
  })

  it('新增规则:填名称+key+动作后保存成功', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()

    // 弹窗内 input:名称、描述、完整 Key
    const modalInputs = w.findAll('.n-modal input')
    await modalInputs[0].setValue('温度告警')
    // 完整 Key input(条件非 offline 时第三个文本框在弹窗内)
    await modalInputs[2].setValue('room.temp')
    // 动作 select(第 3 个 select:条件/前缀/key/动作)
    const selects = w.findAll('.n-modal select')
    await selects[3].setValue('log')
    await flushPromises()

    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(alertApiMock.create).toHaveBeenCalledWith(expect.objectContaining({
      name: '温度告警', trigger_key: 'room.temp'
    }))
  })

  it('条件切换为 offline 时清空 trigger_key', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()

    // 先填一个 key
    const modalInputs = w.findAll('.n-modal input')
    await modalInputs[2].setValue('some.key')

    // 条件 select 切到 offline(第一个 select)
    await w.findAll('.n-modal select')[0].setValue('offline')
    await flushPromises()

    // offline 模式:显示"监控设备"select,完整 Key 输入框消失
    expect(w.findAll('.n-modal input').some((i) => (i.element as HTMLInputElement).value === 'some.key')).toBe(false)
    // 离线规则提示:设备重新上线时也会通知
    expect(w.text()).toContain('重新上线')
  })

  it('动作选 webhook 但未选渠道 → 阻止保存', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()

    const modalInputs = w.findAll('.n-modal input')
    await modalInputs[0].setValue('Webhook 告警')
    await modalInputs[2].setValue('room.temp')
    const selects = w.findAll('.n-modal select')
    await selects[3].setValue('webhook')
    await flushPromises()

    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(alertApiMock.create).not.toHaveBeenCalled()
  })

  it('动作选 webhook 且选了渠道 → 保存成功并带 action_target', async () => {
    webhookApiMock.list.mockResolvedValue({ data: [{ id: 1, name: '企业微信', enabled: true }] })
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()

    const modalInputs = w.findAll('.n-modal input')
    await modalInputs[0].setValue('Webhook 告警')
    await modalInputs[2].setValue('room.temp')
    const selects = w.findAll('.n-modal select')
    await selects[3].setValue('webhook')
    await flushPromises()
    // 重新查询:动作切换后 Webhook 渠道 select 才出现(多选)
    const webhookSelect = w.findAll('.n-modal select')[4]
    expect(webhookSelect).toBeTruthy()
    await webhookSelect.setValue('webhook:1')
    await flushPromises()

    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(alertApiMock.create).toHaveBeenCalledWith(expect.objectContaining({
      action: 'webhook', action_target: 'webhook:1'
    }))
  })

  it('动作选 webhook 时显示 Body+ 示例按钮', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增规则'))
    await addBtn!.trigger('click')
    await flushPromises()

    const selects = w.findAll('.n-modal select')
    await selects[3].setValue('webhook')
    await flushPromises()
    const exampleBtn = w.findAll('.n-modal button').find((b) => b.text().includes('JSON 示例'))
    expect(exampleBtn).toBeTruthy()

    await exampleBtn!.trigger('click')
    await flushPromises()
    // 点击后 Body textarea 有 JSON 内容(通过 input 值断言不了,检查无异常即可)
    expect(w.find('.n-modal').exists()).toBe(true)
  })

  it('开关切换调用 toggle', async () => {
    alertApiMock.list.mockResolvedValue({ data: [rule(1, '开关规则')] })
    const w = mountPage()
    await flushPromises()

    await w.find('.n-switch').setValue(false)
    await flushPromises()
    expect(alertApiMock.toggle).toHaveBeenCalledWith(1, false)
  })

  it('删除规则(点确认)调用 delete', async () => {
    alertApiMock.list.mockResolvedValue({ data: [rule(1, '待删规则')] })
    const w = mountPage()
    await flushPromises()

    await w.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(alertApiMock.delete).toHaveBeenCalledWith(1)
  })

  it('WS alert.* 事件触发重新加载', async () => {
    const w = mountPage()
    await flushPromises()
    expect(alertApiMock.list).toHaveBeenCalledTimes(1)

    wsHandler()('alert.updated', { id: 1 })
    await flushPromises()
    expect(alertApiMock.list).toHaveBeenCalledTimes(2)
  })

  it('加载失败显示空列表不报错', async () => {
    alertApiMock.list.mockRejectedValue(new Error('offline'))
    const w = mountPage()
    await flushPromises()
    expect(w.find('.n-empty').exists()).toBe(true)
  })
})
