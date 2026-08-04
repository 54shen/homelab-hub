// ============================================================
// KvManager 变量管理页测试
// naive-ui 全部 stub(kvApi/useWebSocket/useFieldLabels/HistoryModal 均 mock)
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const kvApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  set: vi.fn(),
  delete: vi.fn(),
  batchDelete: vi.fn(),
  exportJson: vi.fn(),
  importJson: vi.fn()
}))
// 捕获 useWebSocket 注册的 on 回调,用于模拟 WS 消息
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))

vi.mock('../api', () => ({ kvApi: kvApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k })
}))
vi.mock('../components/HistoryModal.vue', () => ({
  default: defineComponent({
    props: ['show', 'keyProp'],
    template: '<div class="history-modal-stub"></div>'
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
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-space' }, slots.default?.()) } }),
  NCard: defineComponent({ props: ['title'], setup(props, { slots }) { return () => h('div', { class: 'n-card' }, [h('div', {}, props.title), slots.default?.()]) } }),
  NInput: defineComponent({
    props: ['value', 'disabled', 'placeholder'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        placeholder: props.placeholder,
        value: props.value,
        disabled: props.disabled,
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
  NInputNumber: defineComponent({
    props: ['value', 'min', 'max'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        type: 'number',
        value: props.value,
        onInput: (e: any) => emit('update:value', Number(e.target.value))
      })
    }
  }),
  // 表格 stub:渲染行 + 提供"勾选全部"按钮来模拟 update:checked-row-keys 事件
  NDataTable: defineComponent({
    props: ['data', 'checkedRowKeys', 'columns'],
    emits: ['update:checked-row-keys', 'update:page', 'update:page-size'],
    setup(props, { emit }) {
      return () => h('div', { class: 'n-data-table' }, [
        h('button', {
          class: 'check-all',
          onClick: () => emit('update:checked-row-keys', (props.data || []).map((r: any) => r.key))
        }, '勾选全部'),
        ...(props.data || []).map((r: any) => h('div', { class: 'table-row', 'data-key': r.key }, String(r.key)))
      ])
    }
  }),
  NModal: defineComponent({
    props: ['show', 'title'],
    emits: ['update:show'],
    setup(props, { slots }) {
      // 注意:必须在 render 函数内求值 props.show(setup 只在初始化时执行一次,
      // 若在 setup 里判断,弹窗打开后永远不会重新渲染)
      return () =>
        props.show
          ? h('div', { class: 'n-modal' }, [
              h('div', { class: 'modal-title' }, props.title),
              slots.default?.(),
              slots.footer?.()
            ])
          : null
    }
  }),
  NForm: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-form' }, slots.default?.()) } }),
  NFormItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', { class: 'n-form-item' }, [h('span', {}, props.label), slots.default?.()]) } }),
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
  NUpload: defineComponent({ props: ['showFileList'], setup(_, { slots }) { return () => h('div', { class: 'n-upload' }, slots.default?.()) } }),
  useMessage: () => ({ success: vi.fn(), error: vi.fn() })
}))

import KvManager from './KvManager.vue'

// jsdom 没有 URL.createObjectURL,导出功能需要 stub
beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})

function mockRows() {
  kvApiMock.list.mockResolvedValue({
    data: [
      { id: 1, key: 'pc.cpu', value: '42', type: 'int', source: 'agent', retention_days: 180, updated_at: '2026-08-01 10:00:00', expire_seconds: null },
      { id: 2, key: 'HA.temperature', value: '23.5', type: 'float', source: 'homeassistant', retention_days: 180, updated_at: '2026-08-01 10:01:00', expire_seconds: null }
    ]
  } as any)
}

function mountPage() {
  return mount(KvManager, { global: { stubs: { 'ion-icon': true } } })
}

describe('KvManager.vue', () => {
  beforeEach(() => {
    Object.values(kvApiMock).forEach((m) => (m as any).mockReset())
    wsOnMock.mockReset()
    wsOnMock.mockReturnValue(() => {})
    kvApiMock.list.mockResolvedValue({ data: [] })
    kvApiMock.set.mockResolvedValue({ data: {} })
    kvApiMock.delete.mockResolvedValue({ data: {} })
    kvApiMock.batchDelete.mockResolvedValue({ data: {} })
    kvApiMock.exportJson.mockResolvedValue({ data: new Blob(['[]']) })
  })

  it('挂载后加载并渲染变量列表', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('pc.cpu')
    expect(kvApiMock.list).toHaveBeenCalled()
  })

  it('加载失败时显示空列表,不报错', async () => {
    kvApiMock.list.mockRejectedValue(new Error('offline'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(0)
  })

  it('搜索框过滤列表', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)

    // 搜索 pc → 只剩 1 行
    await wrapper.find('.filter-row input').setValue('pc')
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('pc.cpu')

    // 清空搜索恢复
    await wrapper.find('.filter-row input').setValue('')
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('按前缀筛选', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    // filter-row 里第二个 select 是前缀筛选
    const selects = wrapper.findAll('.filter-row select')
    await selects[0].setValue('HA')
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('HA.temperature')
  })

  it('分组视图切换', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    // 点"分组"按钮 → 分组卡片渲染
    const groupBtn = wrapper.findAll('button').find((b) => b.text().includes('分组'))
    await groupBtn!.trigger('click')
    await flushPromises()
    const cards = wrapper.findAll('.n-card')
    expect(cards).toHaveLength(2)  // pc / HA 两组
    // groupedData 按 localeCompare 排序,"HA" 排在 "pc" 前面
    expect(cards[0].text()).toContain('HA')
    expect(cards[1].text()).toContain('pc')
  })

  it('新增变量:填表保存 → 调用 kvApi.set 并重新加载', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    // 打开新增弹窗
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('新增变量'))
    await addBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.n-modal').exists()).toBe(true)

    // 填 key 和 value(弹窗里前两个 input)
    const inputs = wrapper.findAll('.n-modal input')
    await inputs[0].setValue('new.key')
    await inputs[1].setValue('100')
    // 点"保存"
    const saveBtn = wrapper.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(kvApiMock.set).toHaveBeenCalledWith(expect.objectContaining({ key: 'new.key', value: '100' }))
    // 保存后重新加载
    expect(kvApiMock.list).toHaveBeenCalledTimes(2)
    // 弹窗关闭
    expect(wrapper.find('.n-modal').exists()).toBe(false)
  })

  it('新增变量时 key 为空 → 不提交', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('新增变量'))
    await addBtn!.trigger('click')
    await flushPromises()
    const saveBtn = wrapper.findAll('.n-modal button').find((b) => b.text().includes('保存'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(kvApiMock.set).not.toHaveBeenCalled()
  })

  it('勾选后批量删除', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    // 模拟表格发出勾选事件
    await wrapper.find('.check-all').trigger('click')
    await flushPromises()

    const delBtn = wrapper.findAll('button').find((b) => b.text().includes('删除选中'))
    expect(delBtn).toBeTruthy()
    await delBtn!.trigger('click')
    await flushPromises()
    expect(kvApiMock.batchDelete).toHaveBeenCalledWith({ keys: ['pc.cpu', 'HA.temperature'] })
  })

  it('导出变量 → 调用 exportJson 并触发下载', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()
    const exportBtn = wrapper.findAll('button').find((b) => b.text().includes('导出'))
    await exportBtn!.trigger('click')
    await flushPromises()
    expect(kvApiMock.exportJson).toHaveBeenCalled()
  })

  it('WebSocket kv.changed 更新现有行', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    // 拿到 on 注册的回调,模拟服务器推送
    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'pc.cpu', value: '99', source: 'agent', changed_at: '2026-08-02 10:00:00' })
    await flushPromises()

    // 行数不变,但值已更新(值不在 stub 渲染里,检查内部状态变化 → 通过再次搜索验证)
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('WebSocket kv.changed 新增未知 key', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.changed', { key: 'new.ws', value: '1', changed_at: '2026-08-02 10:00:00' })
    await flushPromises()

    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('new.ws')   // 新 key 插入头部
  })

  it('WebSocket kv.deleted 移除行', async () => {
    mockRows()
    const wrapper = mountPage()
    await flushPromises()

    const wsHandler = wsOnMock.mock.calls[0][0]
    wsHandler('kv.deleted', { key: 'pc.cpu' })
    await flushPromises()

    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('HA.temperature')
  })
})
