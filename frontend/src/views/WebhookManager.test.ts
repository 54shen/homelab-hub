// ============================================================
// WebhookManager Webhook 管理页测试
// 卡片列表/URL 芯片可视化/保存校验/测试发送/WS 刷新
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const webhookApiMock = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(),
  test: vi.fn(), previewUrl: vi.fn()
}))
const kvApiMock = vi.hoisted(() => ({ list: vi.fn() }))
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))

vi.mock('../api', () => ({ webhookApi: webhookApiMock, kvApi: kvApiMock }))
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
    props: ['value', 'placeholder', 'type', 'readonly'],
    emits: ['update:value', 'input'],
    setup(props, { emit }) {
      return () => h('input', {
        placeholder: props.placeholder,
        value: props.value,
        readonly: props.readonly,
        onInput: (e: any) => {
          emit('update:value', e.target.value)
          emit('input', e)
        }
      })
    }
  }),
  NSelect: defineComponent({
    // multiple 必须类型化声明,否则模板简写 multiple 不触发布尔转换
    props: { value: null, options: null, multiple: { type: Boolean, default: false } },
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        value: Array.isArray(props.value) ? props.value.join(',') : (props.value ?? ''),
        onChange: (e: any) => {
          const v = (e.target as HTMLSelectElement).value
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
  NFormItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', {}, [h('span', {}, props.label), slots.default?.()]) } }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NSwitch: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(props, { emit }) { return () => h('input', { class: 'n-switch', type: 'checkbox', checked: props.value, onChange: (e: any) => emit('update:value', (e.target as HTMLInputElement).checked) }) }
  }),
  NTag: defineComponent({ setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) } }),
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

import WebhookManager from './WebhookManager.vue'

let wrapper: ReturnType<typeof mount> | null = null

function wh(id: number, name: string, url: string, extra: Record<string, unknown> = {}) {
  return {
    id, name, url, method: 'POST', headers: {}, body: '', body_extra: '',
    event_types: [], enabled: true, last_sent: null, fail_count: 0, ...extra
  }
}

beforeEach(() => {
  Object.values(webhookApiMock).forEach((m) => (m as any).mockReset())
  Object.values(kvApiMock).forEach((m) => (m as any).mockReset())
  wsOnMock.mockReset()
  wsOnMock.mockReturnValue(() => {})
  webhookApiMock.list.mockResolvedValue({ data: [] })
  webhookApiMock.create.mockResolvedValue({ data: {} })
  webhookApiMock.update.mockResolvedValue({ data: {} })
  webhookApiMock.delete.mockResolvedValue({ data: {} })
  webhookApiMock.test.mockResolvedValue({ data: { success: true } })
  webhookApiMock.previewUrl.mockResolvedValue({ data: { url: 'http://192.168.1.1/hook' } })
  kvApiMock.list.mockResolvedValue({ data: [] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function mountPage() {
  wrapper = mount(WebhookManager, { global: { stubs: { 'ion-icon': true } } })
  return wrapper
}

function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

describe('WebhookManager.vue', () => {
  it('挂载后加载并渲染 Webhook 卡片', async () => {
    webhookApiMock.list.mockResolvedValue({
      data: [wh(1, '微信通知', 'http://localhost:9/hook', { event_types: ['kv.changed'], fail_count: 2 })]
    })
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('微信通知')
    expect(w.text()).toContain('kv.changed')
    expect(w.text()).toContain('失败 2 次')
  })

  it('无 Webhook 时显示空状态', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('.n-empty').text()).toContain('暂无 Webhook')
  })

  it('URL 模板芯片可视化:{{变量}} 渲染为芯片', async () => {
    webhookApiMock.list.mockResolvedValue({ data: [wh(1, '测试', 'http://x')] })
    kvApiMock.list.mockResolvedValue({ data: [{ id: 1, key: 'dev.ip', value: '1.2.3.4', type: 'string', source: '', retention_days: 180, updated_at: '', expire_seconds: null }] })
    const w = mountPage()
    await flushPromises()

    // 打开新增弹窗
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增 Webhook'))
    await addBtn!.trigger('click')
    await flushPromises()

    // 输入带 {{变量}} 的 URL
    const urlInput = w.findAll('.n-modal input')[1]
    await urlInput.setValue('http://{{dev.ip}}/hook')
    await flushPromises()

    // 芯片行渲染
    expect(w.find('.url-chip').exists()).toBe(true)
    expect(w.find('.url-chip').text()).toContain('dev.ip')
  })

  it('点击芯片 × 删除该变量', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增 Webhook'))
    await addBtn!.trigger('click')
    await flushPromises()

    const urlInput = w.findAll('.n-modal input')[1]
    await urlInput.setValue('http://{{a.b}}/{{c.d}}')
    await flushPromises()
    expect(w.findAll('.url-chip')).toHaveLength(2)

    await w.find('.chip-x').trigger('click')
    await flushPromises()
    expect(w.findAll('.url-chip')).toHaveLength(1)
  })

  it('保存:名称或 URL 为空不提交', async () => {
    const w = mountPage()
    const addBtn = w.findAll('button').find((b) => b.text().includes('新增 Webhook'))
    await addBtn!.trigger('click')
    await flushPromises()

    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(webhookApiMock.create).not.toHaveBeenCalled()
  })

  it('保存成功调用 create 并重新加载', async () => {
    webhookApiMock.list.mockResolvedValue({ data: [wh(1, '旧', 'http://old')] })
    const w = mountPage()
    await flushPromises()

    const addBtn = w.findAll('button').find((b) => b.text().includes('新增 Webhook'))
    await addBtn!.trigger('click')
    await flushPromises()

    const modalInputs = w.findAll('.n-modal input')
    await modalInputs[0].setValue('新Hook')
    await modalInputs[1].setValue('http://new/hook')
    const saveBtn = w.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(webhookApiMock.create).toHaveBeenCalledWith(expect.objectContaining({ name: '新Hook', url: 'http://new/hook' }))
    expect(webhookApiMock.list).toHaveBeenCalledTimes(2)  // 挂载 + 保存后
  })

  it('测试按钮:成功时提示已发送', async () => {
    webhookApiMock.list.mockResolvedValue({ data: [wh(1, '测试', 'http://x')] })
    const w = mountPage()
    await flushPromises()

    const testBtn = w.findAll('button').find((b) => b.text().includes('测试'))
    await testBtn!.trigger('click')
    await flushPromises()
    expect(webhookApiMock.test).toHaveBeenCalledWith(1)
  })

  it('开关切换调用 update', async () => {
    webhookApiMock.list.mockResolvedValue({ data: [wh(1, '开关', 'http://x')] })
    const w = mountPage()
    await flushPromises()

    await w.find('.n-switch').setValue(false)
    await flushPromises()
    expect(webhookApiMock.update).toHaveBeenCalledWith(1, { enabled: false })
  })

  it('WS webhook.* 事件触发重新加载', async () => {
    const w = mountPage()
    await flushPromises()
    expect(webhookApiMock.list).toHaveBeenCalledTimes(1)

    wsHandler()('webhook.created', { id: 1 })
    await flushPromises()
    expect(webhookApiMock.list).toHaveBeenCalledTimes(2)
  })
})
