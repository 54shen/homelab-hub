// ============================================================
// ClipboardPanel 剪切板面板测试
// 覆盖:渲染/空态 / 发送(编码+清空+合并最新一条) / 值未变不产生幻影行 /
//      WS 实时更新(去重/淘汰/其它 key 忽略) / 复制(降级) / Ctrl+Enter 快捷发送
// naive-ui 与 ion-icon stub,api 与 useWebSocket mock
// ============================================================
import { nextTick } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const historyApiMock = vi.hoisted(() => ({ list: vi.fn() }))
const kvApiMock = vi.hoisted(() => ({ set: vi.fn() }))
const wsOnMock = vi.hoisted(() => vi.fn(() => () => {}))
const msgMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('../api', () => ({ historyApi: historyApiMock, kvApi: kvApiMock }))
vi.mock('../composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: wsOnMock, wsConnected: { value: false }, wsRealtime: { value: true } })
}))
vi.mock('naive-ui', async () => {
  const { h } = await import('vue')
  return {
    NInput: {
      props: ['value', 'type', 'rows', 'placeholder', 'clearable', 'size'],
      emits: ['update:value'],
      setup(props, { emit, attrs }) {
        return () => {
          const tag = props.type === 'textarea' ? 'textarea' : 'input'
          return h(tag, {
            class: 'n-input',
            placeholder: props.placeholder,
            value: props.value,
            onInput: (e: any) => emit('update:value', e.target.value),
            ...attrs
          })
        }
      }
    },
    NButton: {
      props: ['size', 'type', 'loading', 'quaternary'],
      emits: ['click'],
      setup(props, { emit, slots }) {
        return () => h('button', {
          class: 'n-button',
          disabled: props.loading,
          // 透传真实事件对象,让 @click.stop 真正阻止冒泡(否则按钮点击会冒泡到整行)
          onClick: (e: any) => emit('click', e)
        }, slots.default?.())
      }
    },
    NTag: {
      props: ['size', 'bordered', 'round', 'type'],
      setup(_, { slots }) { return () => h('span', { class: 'n-tag' }, slots.default?.()) }
    },
    NEmpty: {
      props: ['description'],
      setup(props) { return () => h('div', { class: 'n-empty' }, props.description) }
    },
    useMessage: () => msgMock
  }
})

import ClipboardPanel from './ClipboardPanel.vue'
import { CLIPBOARD_KEY } from '../utils/clipboard'

enableAutoUnmount(afterEach)

function histRow(overrides: Record<string, unknown> = {}) {
  return {
    id: 1, key: CLIPBOARD_KEY, old_value: null, new_value: '{"t":"","c":"hi"}',
    source: 'admin(Web)', retention_days: 3650, changed_at: '2026-08-06 10:00:00',
    ...overrides
  }
}

function mountPanel() {
  return mount(ClipboardPanel, { global: { stubs: { 'ion-icon': true } } })
}

function wsHandler() {
  return wsOnMock.mock.calls[0][0]
}

describe('ClipboardPanel.vue', () => {
  beforeEach(() => {
    historyApiMock.list.mockReset()
    kvApiMock.set.mockReset()
    wsOnMock.mockClear()
    msgMock.success.mockClear()
    msgMock.error.mockClear()
    // 默认:初始加载返回空列表
    historyApiMock.list.mockResolvedValue({ data: { items: [], total: 0 } })
    kvApiMock.set.mockResolvedValue({ data: { success: true } })
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
  })

  it('渲染:加载历史并展示主题标签 + 内容 + 时间', async () => {
    historyApiMock.list.mockResolvedValue({
      data: { items: [
        histRow({ id: 2, new_value: '{"t":"购物","c":"买牛奶"}', changed_at: '2026-08-06 10:05:00' }),
        histRow({ id: 1, new_value: '{"t":"","c":"纯文本"}', changed_at: '2026-08-06 10:00:00' }),
      ], total: 2 }
    })
    const wrapper = mountPanel()
    await flushPromises()
    expect(historyApiMock.list).toHaveBeenCalledWith({ key: CLIPBOARD_KEY, page_size: 20 })
    const contents = wrapper.findAll('.cp-content').map(e => e.text())
    expect(contents).toEqual(['买牛奶', '纯文本'])
    expect(wrapper.findAll('.n-tag').length).toBe(1)  // 只有"购物"有主题标签
    expect(wrapper.text()).toContain('10:05:00')
  })

  it('渲染:空历史 → 显示空态', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('.n-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无剪切板记录')
  })

  it('发送:内容+主题编码为 JSON,成功后清空输入并合并最新一条', async () => {
    // 初始 1 条;发送后最新一条变为新值
    historyApiMock.list
      .mockResolvedValueOnce({ data: { items: [histRow({ new_value: '{"t":"旧","c":"old"}' })], total: 1 } })
      .mockResolvedValueOnce({ data: { items: [histRow({ id: 2, new_value: '{"t":"主题","c":"新内容"}', changed_at: '2026-08-06 11:00:00' })], total: 2 } })
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.n-input').setValue('主题')          // 第一个 input = 主题
    await wrapper.findAll('.n-input')[1].setValue('新内容')   // 第二个 = 内容
    await wrapper.find('.n-button').trigger('click')
    await flushPromises()

    expect(kvApiMock.set).toHaveBeenCalledWith({
      key: CLIPBOARD_KEY,
      value: '{"t":"主题","c":"新内容"}',
      type: 'string',
      source: 'admin(Web)',
      retention_days: 3650,
    })
    // 清空输入框
    expect((wrapper.findAll('.n-input')[1].element as HTMLInputElement).value).toBe('')
    // 合并最新一条
    expect(historyApiMock.list).toHaveBeenLastCalledWith({ key: CLIPBOARD_KEY, page_size: 1 })
    const contents = wrapper.findAll('.cp-content').map(e => e.text())
    expect(contents).toEqual(['新内容', 'old'])
  })

  it('发送:内容为空 → 不调用 set', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('.n-button').trigger('click')
    await flushPromises()
    expect(kvApiMock.set).not.toHaveBeenCalled()
  })

  it('发送:值未变(最新历史仍为旧值)→ 不产生幻影行', async () => {
    // 发送后最新一条仍是旧值(后端静默) → 列表保持 1 条
    historyApiMock.list.mockResolvedValue({ data: { items: [histRow({ new_value: '{"t":"","c":"same"}' })], total: 1 } })
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.findAll('.n-input')[1].setValue('same')
    await wrapper.find('.n-button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.cp-content').length).toBe(1)
  })

  it('WS:kv.changed 剪切板 key → 实时插入;去重;超 20 条淘汰最旧', async () => {
    // 初始 20 条,按后端 desc 顺序返回(最新在前):旧19(09:19) … 旧0(09:00)
    const old20 = Array.from({ length: 20 }, (_, i) => histRow({
      id: i + 1, new_value: `{"t":"","c":"旧${19 - i}"}`,
      changed_at: `2026-08-06 09:${String(19 - i).padStart(2, '0')}:00`,
    }))
    historyApiMock.list.mockResolvedValue({ data: { items: old20, total: 20 } })
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.findAll('.cp-content').length).toBe(20)

    const handler = wsHandler()
    handler('kv.changed', { key: CLIPBOARD_KEY, value: '{"t":"实时","c":"新条目"}', source: 'phone(Web)', changed_at: '2026-08-06 12:00:00' })
    await nextTick()
    expect(wrapper.findAll('.cp-content')[0].text()).toBe('新条目')

    // 同 changed_at|value 重复推送 → 去重不重复插入
    handler('kv.changed', { key: CLIPBOARD_KEY, value: '{"t":"实时","c":"新条目"}', source: 'phone(Web)', changed_at: '2026-08-06 12:00:00' })
    await nextTick()
    expect(wrapper.findAll('.cp-content').length).toBe(20)  // 去重后仍 20 条

    // 再插一条 → 21 条淘汰最旧 → 20 条;最旧的 旧0/旧1 被淘汰,最后一条为 旧2
    handler('kv.changed', { key: CLIPBOARD_KEY, value: '{"t":"","c":"再来"}', source: 'x(Web)', changed_at: '2026-08-06 12:01:00' })
    await nextTick()
    expect(wrapper.findAll('.cp-content').length).toBe(20)
    expect(wrapper.findAll('.cp-content').at(-1)!.text()).toBe('旧2')
    const texts = wrapper.findAll('.cp-content').map(e => e.text())
    expect(texts).not.toContain('旧0')
    expect(texts).not.toContain('旧1')
  })

  it('WS:其它 key 的 kv.changed → 忽略', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    wsHandler()('kv.changed', { key: 'HA.temp', value: '1', changed_at: '2026-08-06 12:00:00' })
    await nextTick()
    expect(wrapper.find('.n-empty').exists()).toBe(true)
  })

  it('复制:点击整条复制内容(而非 JSON/主题);按钮不冒泡双触发', async () => {
    historyApiMock.list.mockResolvedValue({
      data: { items: [histRow({ new_value: '{"t":"主题X","c":"要复制的内容"}' })], total: 1 }
    })
    const wrapper = mountPanel()
    await flushPromises()

    // 点击整条 → 复制内容部分
    await wrapper.find('.cp-item').trigger('click')
    await flushPromises()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('要复制的内容')
    expect(msgMock.success).toHaveBeenCalledWith('已复制')

    // 点击复制按钮 → 也只复制一次(阻止冒泡)
    ;(navigator.clipboard.writeText as any).mockClear()
    msgMock.success.mockClear()
    await wrapper.find('.cp-copy').trigger('click')
    await flushPromises()
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1)
  })

  it('复制:clipboard API 失败 → execCommand 降级', async () => {
    historyApiMock.list.mockResolvedValue({ data: { items: [histRow()], total: 1 } })
    ;(navigator.clipboard.writeText as any).mockRejectedValue(new Error('denied'))
    document.execCommand = vi.fn(() => true)
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('.cp-item').trigger('click')
    await flushPromises()
    expect(document.execCommand).toHaveBeenCalledWith('copy')
    expect(msgMock.success).toHaveBeenCalledWith('已复制')
  })

  it('快捷键:Ctrl+Enter 触发发送', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.findAll('.n-input')[1].setValue('快捷键内容')
    await wrapper.findAll('.n-input')[1].trigger('keydown', { ctrlKey: true, key: 'Enter' })
    await flushPromises()
    expect(kvApiMock.set).toHaveBeenCalledTimes(1)
    expect(kvApiMock.set).toHaveBeenCalledWith(expect.objectContaining({ value: '{"t":"","c":"快捷键内容"}' }))
  })
})
