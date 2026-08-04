// ============================================================
// RecordsTable 历史记录表格测试
// naive-ui NSelect / useFieldLabels 均 mock,测渲染 + 分页 + 事件
// ============================================================
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('naive-ui', () => ({
  NSelect: defineComponent({
    props: ['value', 'options'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        class: 'page-size-select',
        value: props.value ?? '',
        onChange: (e: any) => emit('update:value', Number((e.target as HTMLSelectElement).value))
      }, (props.options || []).map((o: any) => h('option', { value: o.value }, o.label)))
    }
  })
}))

vi.mock('../composables/useFieldLabels', () => ({
  useFieldLabels: () => ({ labelOf: (k: string) => (k.endsWith('.temperature') ? '温度' : k) })
}))

import RecordsTable from './RecordsTable.vue'

function mockItems() {
  return [
    { id: 1, key: 'pc.cpu', old_value: '10', new_value: '20', source: 'agent', retention_days: 180, changed_at: '2026-08-01 10:00:00' },
    { id: 2, key: 'HA.temperature', old_value: '23', new_value: '25', source: 'homeassistant', retention_days: 90, changed_at: '2026-08-01 09:00:00' }
  ] as any
}

// 注意:showPager 是 Boolean prop,未传时 Vue 默认 false,而模板是 v-if="showPager !== false",
// 所以测分页逻辑必须显式传 showPager: true(生产代码平铺视图未传 → 分页器实际不渲染,属已知 bug)
function mountTable(props: Record<string, unknown> = {}) {
  return mount(RecordsTable, {
    props: {
      items: mockItems(),
      total: 42,
      page: 1,
      pageSize: 20,
      pages: 3,
      showPager: true,
      ...props
    }
  })
}

describe('RecordsTable.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染数据行与表头', () => {
    const wrapper = mountTable()
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('2026-08-01 10:00:00')
    expect(rows[0].text()).toContain('pc.cpu')
    expect(rows[0].text()).toContain('agent')
    expect(rows[0].text()).toContain('180')
  })

  it('旧值≠新值时渲染 旧→新 两段', () => {
    const wrapper = mountTable()
    const firstRow = wrapper.findAll('tbody tr')[0]
    expect(firstRow.text()).toContain('10')
    expect(firstRow.text()).toContain('20')
    expect(firstRow.text()).toContain('→')
    // 变化的行加 changed 类(旧值划线、新值高亮)
    expect(firstRow.find('.old').classes()).toContain('changed')
    expect(firstRow.find('.new').classes()).toContain('changed')
  })

  it('key 经字段映射显示中文(无映射保留原 key)', () => {
    const wrapper = mountTable()
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0].text()).toContain('pc.cpu')      // 无映射 → 原 key
    expect(rows[1].find('.key').text()).toBe('温度') // 映射为中文
  })

  it('点击 key → 触发 select-key 事件', async () => {
    const wrapper = mountTable()
    await wrapper.findAll('.key-link')[0].trigger('click')
    expect(wrapper.emitted('select-key')![0]).toEqual(['pc.cpu'])
  })

  it('空数据 → 显示 "暂无数据" 占位行', () => {
    const wrapper = mountTable({ items: [] })
    expect(wrapper.find('.empty').text()).toContain('暂无数据')
  })

  it('渲染分页信息与页码', () => {
    const wrapper = mountTable({ page: 2, pages: 5, total: 42 })
    expect(wrapper.find('.info').text()).toContain('共 42 条')
    expect(wrapper.find('.info').text()).toContain('第 2/5 页')
    const nums = wrapper.findAll('.page-num').map(b => b.text())
    expect(nums).toEqual(['1', '2', '3', '4', '5'])
    // 当前页高亮
    expect(wrapper.findAll('.page-num')[1].classes()).toContain('active')
  })

  it('页码超 7 页时折叠省略号', () => {
    // 第 1 页 → 1 2 3 … 20
    let wrapper = mountTable({ page: 1, pages: 20 })
    expect(wrapper.findAll('.page-num').map(b => b.text())).toEqual(['1', '2', '3', '…', '20'])
    // 中间页 → 1 … 8 9 10 11 12 … 20
    wrapper = mountTable({ page: 10, pages: 20 })
    expect(wrapper.findAll('.page-num').map(b => b.text())).toEqual(['1', '…', '8', '9', '10', '11', '12', '…', '20'])
    // 末页 → 1 … 18 19 20
    wrapper = mountTable({ page: 20, pages: 20 })
    expect(wrapper.findAll('.page-num').map(b => b.text())).toEqual(['1', '…', '18', '19', '20'])
  })

  it('点击页码 → 触发 update:page;省略号不可点', async () => {
    const wrapper = mountTable({ page: 10, pages: 20 })
    const nums = wrapper.findAll('.page-num')
    // 点 "12"
    await nums[6].trigger('click')
    expect(wrapper.emitted('update:page')![0]).toEqual([12])
    // 省略号按钮 disabled,点击无事件
    await nums[1].trigger('click')
    expect(wrapper.emitted('update:page')).toHaveLength(1)
  })

  it('上一页/下一页按钮 → 触发 update:page 并在边界禁用', async () => {
    const wrapper = mountTable({ page: 2, pages: 3 })
    const buttons = wrapper.findAll('.pager button')
    const prev = buttons[0]
    const next = buttons[buttons.length - 1]
    await prev.trigger('click')
    await next.trigger('click')
    expect(wrapper.emitted('update:page')).toEqual([[1], [3]])

    // 首页 → 上一页禁用
    const first = mountTable({ page: 1, pages: 3 })
    expect(first.findAll('.pager button')[0].attributes('disabled')).toBeDefined()
    // 末页 → 下一页禁用
    const last = mountTable({ page: 3, pages: 3 })
    const lastNext = last.findAll('.pager button').find(b => b.text() === '下一页')!
    expect(lastNext.attributes('disabled')).toBeDefined()
  })

  it('切换每页条数 → 触发 update:pageSize', async () => {
    const wrapper = mountTable()
    await wrapper.find('.page-size-select').setValue('50')
    expect(wrapper.emitted('update:pageSize')![0]).toEqual([50])
  })

  it('showPager=false → 隐藏分页器', () => {
    const wrapper = mountTable({ showPager: false })
    expect(wrapper.find('.pager').exists()).toBe(false)
  })
})
