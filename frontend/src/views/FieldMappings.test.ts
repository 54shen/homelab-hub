// ============================================================
// FieldMappings 字段映射页测试
// 覆盖:列表/未映射 key 加载、搜索过滤、行内编辑、新增(GHOST 临时行)、
//      删除(确认)、未映射 chip 快速添加、一键全部添加、CSV 导入导出
// 列是 render 函数渲染的行内 input/按钮,通过 find 元素触发
// ============================================================
import { defineComponent, h } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const fieldMappingApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  exportTemplate: vi.fn(),
  importCsv: vi.fn(),
  unmapped: vi.fn()
}))
const refreshMock = vi.hoisted(() => vi.fn(() => Promise.resolve()))
const msgSuccess = vi.hoisted(() => vi.fn())
const msgError = vi.hoisted(() => vi.fn())
const msgWarning = vi.hoisted(() => vi.fn())
const msgInfo = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({ fieldMappingApi: fieldMappingApiMock }))
vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => k, refresh: refreshMock })
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
  // 表格 stub:对每行调用 columns 的 render 渲染单元格(行内 input/按钮可交互)
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
  NPopconfirm: defineComponent({
    emits: ['positive-click'],
    setup(_, { slots, emit }) {
      return () => h('div', { class: 'n-popconfirm' }, [
        slots.trigger?.(),
        h('button', { class: 'confirm-btn', onClick: () => emit('positive-click') }, '确定')
      ])
    }
  }),
  NUpload: defineComponent({
    props: ['showFileList'],
    emits: ['change'],
    setup(_, { emit, slots }) {
      return () => h('div', { class: 'n-upload' }, [
        slots.default?.(),
        h('button', {
          class: 'upload-trigger',
          onClick: () => emit('change', { file: { file: new File(['a,b'], 'mappings.csv', { type: 'text/csv' }) } })
        }, '选择CSV文件')
      ])
    }
  }),
  useMessage: () => ({ success: msgSuccess, error: msgError, warning: msgWarning, info: msgInfo })
}))

import FieldMappings from './FieldMappings.vue'

// jsdom 没有 URL.createObjectURL,导出模板需要 stub
beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
})
enableAutoUnmount(afterEach)

const MAPPINGS = [
  { id: 1, field_key: 'pc.cpu', display_name: 'CPU 使用率' },
  { id: 2, field_key: 'ha.temp', display_name: '温度' }
]

function mockDefaultData() {
  fieldMappingApiMock.list.mockResolvedValue({ data: MAPPINGS })
  fieldMappingApiMock.unmapped.mockResolvedValue({ data: ['new.key1', 'new.key2'] })
}

function mountPage() {
  return mount(FieldMappings, { global: { stubs: { 'ion-icon': true } } })
}

describe('FieldMappings.vue', () => {
  beforeEach(() => {
    Object.values(fieldMappingApiMock).forEach((m) => (m as any).mockReset())
    refreshMock.mockReset()
    refreshMock.mockResolvedValue()
    msgSuccess.mockReset(); msgError.mockReset(); msgWarning.mockReset(); msgInfo.mockReset()
    mockDefaultData()
    fieldMappingApiMock.create.mockResolvedValue({ data: { id: 9, field_key: 'x', display_name: 'y' } })
    fieldMappingApiMock.update.mockResolvedValue({ data: {} })
    fieldMappingApiMock.delete.mockResolvedValue({ data: {} })
    fieldMappingApiMock.exportTemplate.mockResolvedValue({ data: new Blob(['a,b']) })
    fieldMappingApiMock.importCsv.mockResolvedValue({ data: { success: true, message: '导入完成' } })
  })

  it('挂载后加载映射列表与未映射 key 并渲染', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(fieldMappingApiMock.list).toHaveBeenCalled()
    expect(fieldMappingApiMock.unmapped).toHaveBeenCalled()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('pc.cpu')
    expect(rows[0].text()).toContain('CPU 使用率')
    // 统计条
    expect(wrapper.text()).toContain('已配置映射')
    expect(wrapper.text()).toContain('未映射 Key')
    // 未映射 chips
    const chips = wrapper.findAll('.unmapped-chip')
    expect(chips).toHaveLength(2)
    expect(chips[0].text()).toContain('new.key1')
  })

  it('无映射时显示空状态提示', async () => {
    fieldMappingApiMock.list.mockResolvedValue({ data: [] })
    fieldMappingApiMock.unmapped.mockResolvedValue({ data: [] })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.n-data-table').text()).toContain('暂无映射')
    expect(wrapper.findAll('.unmapped-chip')).toHaveLength(0)
  })

  it('搜索过滤映射,显示匹配条数与无匹配提示', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)

    // 搜索 temp → 只剩 ha.temp
    await wrapper.find('input[placeholder="搜索 field_key 或 display_name..."]').setValue('temp')
    await flushPromises()
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('ha.temp')
    expect(wrapper.text()).toContain('匹配 1 条')

    // 无匹配 → 空状态提示"无匹配映射"
    await wrapper.find('input[placeholder="搜索 field_key 或 display_name..."]').setValue('zzz')
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(0)
    expect(wrapper.find('.n-data-table').text()).toContain('无匹配映射')

    // 清空搜索恢复
    await wrapper.find('input[placeholder="搜索 field_key 或 display_name..."]').setValue('')
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('新增:点击新增出现临时行,填写后保存调用 create 并重新加载', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('新增'))!
    await addBtn.trigger('click')
    await flushPromises()
    // GHOST 临时行(id=0)插到表格顶部
    const rows = wrapper.findAll('.table-row')
    expect(rows).toHaveLength(3)
    const firstRow = rows[0]
    expect(firstRow.find('.edit-key-input').exists()).toBe(true)

    const inputs = firstRow.findAll('input')
    await inputs[0].setValue('new.key')
    await inputs[1].setValue('新变量')
    await firstRow.findAll('button').find((b) => b.text() === '保存')!.trigger('click')
    await flushPromises()

    expect(fieldMappingApiMock.create).toHaveBeenCalledWith({ field_key: 'new.key', display_name: '新变量' })
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)  // 保存后重新加载
    expect(refreshMock).toHaveBeenCalled()
    expect(msgSuccess).toHaveBeenCalledWith('已添加')
    // 保存后临时行消失
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('新增:key 或显示名为空时不提交', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('新增'))!
    await addBtn.trigger('click')
    await flushPromises()
    const firstRow = wrapper.findAll('.table-row')[0]
    await firstRow.findAll('button').find((b) => b.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.create).not.toHaveBeenCalled()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)  // 临时行已撤销
  })

  it('新增:按 Enter 提交,按 Escape 取消', async () => {
    const wrapper = mountPage()
    await flushPromises()

    // Enter 提交
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('新增'))!
    await addBtn.trigger('click')
    await flushPromises()
    const firstRow = wrapper.findAll('.table-row')[0]
    const inputs = firstRow.findAll('input')
    await inputs[0].setValue('enter.key')
    await inputs[1].setValue('回车新增')
    await firstRow.find('.edit-key-input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(fieldMappingApiMock.create).toHaveBeenCalledWith({ field_key: 'enter.key', display_name: '回车新增' })

    // Escape 取消
    await addBtn.trigger('click')
    await flushPromises()
    await wrapper.findAll('.table-row')[0].find('.edit-key-input').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.findAll('.table-row')).toHaveLength(2)
  })

  it('行内编辑:点击编辑预填表单,修改后保存调用 update', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const row = wrapper.findAll('.table-row')[1]  // ha.temp
    await row.findAll('button').find((b) => b.text() === '编辑')!.trigger('click')
    await flushPromises()

    // 预填原值
    expect((row.find('.edit-key-input').element as HTMLInputElement).value).toBe('ha.temp')

    const inputs = row.findAll('input')
    await inputs[0].setValue('ha.temperature')
    await inputs[1].setValue('室内温度')
    await row.findAll('button').find((b) => b.text() === '保存')!.trigger('click')
    await flushPromises()

    expect(fieldMappingApiMock.update).toHaveBeenCalledWith(2, { field_key: 'ha.temperature', display_name: '室内温度' })
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)
    expect(msgSuccess).toHaveBeenCalledWith('已更新')
  })

  it('行内编辑:内容未变化时不提交', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[1]
    await row.findAll('button').find((b) => b.text() === '编辑')!.trigger('click')
    await flushPromises()
    await row.findAll('button').find((b) => b.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.update).not.toHaveBeenCalled()
  })

  it('删除:点删除按钮后确认,调用 delete 并重新加载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[0]
    await row.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.delete).toHaveBeenCalledWith(1)
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)
    expect(msgSuccess).toHaveBeenCalledWith('已删除')
  })

  it('点击未映射 chip 快速添加:display_name 默认等于 key', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('.unmapped-chip')[0].trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.create).toHaveBeenCalledWith({ field_key: 'new.key1', display_name: 'new.key1' })
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)
    expect(msgSuccess).toHaveBeenCalledWith('已添加 "new.key1"，请编辑显示名')
  })

  it('一键全部添加:每个未映射 key 逐个 create 并提示数量', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('一键全部添加'))!
    await btn.trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.create).toHaveBeenCalledTimes(2)
    expect(fieldMappingApiMock.create).toHaveBeenCalledWith({ field_key: 'new.key1', display_name: 'new.key1' })
    expect(fieldMappingApiMock.create).toHaveBeenCalledWith({ field_key: 'new.key2', display_name: 'new.key2' })
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)
    expect(msgSuccess).toHaveBeenCalledWith('已添加 2 个映射')
  })

  it('一键全部添加:全部失败时提示"没有需要添加的"且不重新加载', async () => {
    fieldMappingApiMock.create.mockRejectedValue(new Error('exists'))
    const wrapper = mountPage()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('一键全部添加'))!
    await btn.trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.create).toHaveBeenCalledTimes(2)
    expect(msgInfo).toHaveBeenCalledWith('没有需要添加的')
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(1)  // 未重新加载
  })

  it('导出空白模板:调用接口并触发下载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('导出空白模板'))!
    await btn.trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.exportTemplate).toHaveBeenCalled()
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled()
  })

  it('导入 CSV 成功:调用 importCsv 并提示、重新加载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.upload-trigger').trigger('click')
    await flushPromises()
    expect(fieldMappingApiMock.importCsv).toHaveBeenCalledWith(expect.any(File))
    expect(msgSuccess).toHaveBeenCalledWith('导入完成')
    expect(fieldMappingApiMock.list).toHaveBeenCalledTimes(2)
    expect(refreshMock).toHaveBeenCalled()
  })

  it('导入 CSV 失败:success=false 提示警告,异常提示错误', async () => {
    const wrapper = mountPage()
    await flushPromises()

    // 后端返回 success=false
    fieldMappingApiMock.importCsv.mockResolvedValue({ data: { success: false, message: '格式错误' } })
    await wrapper.find('.upload-trigger').trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('格式错误')

    // 请求抛异常
    fieldMappingApiMock.importCsv.mockRejectedValue(new Error('bad'))
    await wrapper.find('.upload-trigger').trigger('click')
    await flushPromises()
    expect(msgError).toHaveBeenCalledWith('导入失败')
  })
})
