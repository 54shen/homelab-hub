// ============================================================
// TrendChart 趋势图测试
// echarts 整体 mock(init 返回可注入的 chart 假对象),测渲染 / 事件 / 清理
// ============================================================
import { nextTick } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// 可注入的 echarts chart 假对象:getOption 可改 → 模拟不同缩放窗口
const zrOnMock = vi.hoisted(() => vi.fn())
const chartMock = vi.hoisted(() => ({
  setOption: vi.fn(),
  dispose: vi.fn(),
  resize: vi.fn(),
  getOption: vi.fn(() => ({ dataZoom: [{ start: 0, end: 100 }] })),
  on: vi.fn(),
  getZr: vi.fn(() => ({ on: zrOnMock })),
  dispatchAction: vi.fn()
}))
const echartsInitMock = vi.hoisted(() => vi.fn(() => chartMock))

vi.mock('echarts', () => ({ init: echartsInitMock }))

import TrendChart from './TrendChart.vue'

const points = [
  { changed_at: '2026-08-01 10:00:00', value: 10 },
  { changed_at: '2026-08-01 11:00:00', value: 20 }
] as any

// 每个测试挂载的 wrapper 统一在 afterEach 卸载,避免 window resize 监听跨测试泄漏
let mountedWrapper: VueWrapper | null = null

function mountChart(props: Record<string, unknown> = {}) {
  mountedWrapper = mount(TrendChart, { props: { points, ...props } })
  return mountedWrapper
}

// 取最近一次 setOption 的完整配置
function lastOption() {
  return chartMock.setOption.mock.calls.at(-1)![0] as any
}

describe('TrendChart.vue', () => {
  beforeEach(() => {
    Object.values(chartMock).forEach(m => (m as any).mockClear())
    echartsInitMock.mockClear()
    zrOnMock.mockClear()
    chartMock.getOption.mockReturnValue({ dataZoom: [{ start: 0, end: 100 }] })
  })

  afterEach(() => {
    // 卸载组件 → 移除 window resize 监听,避免影响后续测试
    mountedWrapper?.unmount()
    mountedWrapper = null
  })

  it('挂载后 init 图表并渲染 setOption', async () => {
    const wrapper = mountChart()
    await flushPromises()
    expect(echartsInitMock).toHaveBeenCalledWith(wrapper.find('.trend-chart').element)
    expect(chartMock.setOption).toHaveBeenCalled()
  })

  it('渲染数据:多个变更点展开为阶梯数据(2 点 → 3 段)', async () => {
    const wrapper = mountChart()
    await flushPromises()
    const opt = lastOption()
    expect(opt.series[0].data).toEqual([
      ['2026-08-01T10:00:00', 10, null],
      ['2026-08-01T11:00:00', 10, null],   // 旧值保持到跳变时刻
      ['2026-08-01T11:00:00', 20, null]    // 跳变后的新值
    ])
    // 标题与基础配置
    expect(opt.title.text).toBeUndefined()  // 未传 title 时不显示
    expect(opt.xAxis.type).toBe('time')
    expect(opt.dataZoom[0].filterMode).toBe('none')
    expect(wrapper.find('.hint').exists()).toBe(false)
  })

  it('单个点 → 数据只含一个段', async () => {
    const wrapper = mountChart({ points: [{ changed_at: '2026-08-01 10:00:00', value: 5, raw: '5' }] })
    await flushPromises()
    expect(lastOption().series[0].data).toEqual([['2026-08-01T10:00:00', 5, '5']])
  })

  it('无数据 → 显示提示文案', async () => {
    const wrapper = mountChart({ points: [] })
    await flushPromises()
    expect(wrapper.find('.hint').text()).toContain('暂无数值数据')
  })

  it('points 变化(深监听)→ 重新 setOption', async () => {
    const wrapper = mountChart()
    await flushPromises()
    const callsBefore = chartMock.setOption.mock.calls.length
    await wrapper.setProps({ points: [{ changed_at: '2026-08-02 10:00:00', value: 1 }] })
    await flushPromises()
    expect(chartMock.setOption.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  it('duration 类型 → y 轴 formatter 输出可读时长', async () => {
    const wrapper = mountChart({ plotKind: 'duration' })
    await flushPromises()
    const fmt = lastOption().yAxis.axisLabel.formatter
    expect(fmt(90000)).toBe('1d 1h')
    expect(fmt(86400)).toBe('1d')
    expect(fmt(12900)).toBe('3h 35m')
    expect(fmt(7200)).toBe('2h')
    expect(fmt(75)).toBe('1m 15s')
    expect(fmt(45)).toBe('45s')
  })

  it('timestamp 类型 → y 轴 formatter 输出 MM-DD HH:MM,且 y 轴不强制从 0 起', async () => {
    const wrapper = mountChart({ plotKind: 'timestamp' })
    await flushPromises()
    const opt = lastOption()
    expect(opt.yAxis.scale).toBe(true)
    expect(opt.yAxis.min).toBeUndefined()
    const sec = new Date(2026, 0, 2, 14, 5).getTime() / 1000
    expect(opt.yAxis.axisLabel.formatter(sec)).toBe('01-02 14:05')
  })

  it('非 timestamp 类型 → y 轴从 0 起、不压缩', async () => {
    const wrapper = mountChart({ plotKind: 'number' })
    await flushPromises()
    const opt = lastOption()
    expect(opt.yAxis.scale).toBe(false)
    expect(opt.yAxis.min).toBe(0)
  })

  it('点击图表 → 携带当前缩放窗口 emit click', async () => {
    const wrapper = mountChart()
    await flushPromises()
    // getZr().on('click', handler) → 处理器是第二个参数
    const clickHandler = zrOnMock.mock.calls[0][1]
    clickHandler()
    expect(wrapper.emitted('click')![0]).toEqual([
      { start: '2026-08-01 10:00:00', end: '2026-08-01 11:00:00' }
    ])
  })

  it('datazoom → emit zoom;窗口起点在最早数据时 emit reach-start', async () => {
    const wrapper = mountChart()
    await flushPromises()
    const zoomHandler = chartMock.on.mock.calls.find(c => c[0] === 'datazoom')![1]

    zoomHandler()
    expect(wrapper.emitted('zoom')).toBeTruthy()
    expect(wrapper.emitted('reach-start')).toHaveLength(1)
  })

  it('窗口未到最早边界 → 只 emit zoom 不触发 reach-start', async () => {
    chartMock.getOption.mockReturnValue({ dataZoom: [{ start: 50, end: 100 }] })
    const wrapper = mountChart()
    await flushPromises()
    const zoomHandler = chartMock.on.mock.calls.find(c => c[0] === 'datazoom')![1]

    zoomHandler()
    expect(wrapper.emitted('zoom')).toBeTruthy()
    expect(wrapper.emitted('reach-start')).toBeUndefined()
  })

  it('reach-start 有 1 秒节流:连续触发只发一次', async () => {
    const wrapper = mountChart()
    await flushPromises()
    const zoomHandler = chartMock.on.mock.calls.find(c => c[0] === 'datazoom')![1]

    zoomHandler()
    zoomHandler()
    expect(wrapper.emitted('reach-start')).toHaveLength(1)
  })

  it('无数据时 datazoom 不触发任何事件(修复后行为)', async () => {
    const wrapper = mountChart({ points: [] })
    await flushPromises()
    const zoomHandler = chartMock.on.mock.calls.find(c => c[0] === 'datazoom')![1]
    zoomHandler()
    // 修复:空数据时 zoom 与 reach-start 都不发出,避免向外部传 null 窗口
    expect(wrapper.emitted('zoom')).toBeUndefined()
    expect(wrapper.emitted('reach-start')).toBeUndefined()
  })

  it('plotKind=state 时渲染开关阶梯图(y 轴 0/1 + 垂直阶梯)', async () => {
    const wrapper = mountChart({
      points: [{ changed_at: '2026-08-01 10:00:00', value: 1, raw: 'on' }],
      plotKind: 'state'
    })
    await flushPromises()
    const opt = lastOption()
    // y 轴固定 0/1 两档
    expect(opt.yAxis.min).toBe(0)
    expect(opt.yAxis.max).toBe(1)
    expect(opt.yAxis.interval).toBe(1)
    // 垂直阶梯线(开关切换一目了然)
    expect(opt.series[0].step).toBe('end')
    expect(opt.series[0].smooth).toBe(false)
    // y 轴标签:0 → 关,1 → 开
    expect(opt.yAxis.axisLabel.formatter(0)).toBe('关')
    expect(opt.yAxis.axisLabel.formatter(1)).toBe('开')
  })

  it('plotKind=number 时保持平滑曲线(不受 state 影响)', async () => {
    const wrapper = mountChart({ plotKind: 'number' })
    await flushPromises()
    const opt = lastOption()
    expect(opt.series[0].step).toBeUndefined()
    expect(opt.series[0].smooth).toBe(0.15)
  })

  it('外部传入 zoom → dispatchAction 恢复缩放窗口', async () => {
    const wrapper = mountChart()
    await flushPromises()
    await wrapper.setProps({ zoom: { start: '2026-08-01 10:00:00', end: '2026-08-01 12:00:00' } })
    await nextTick()
    await nextTick()
    expect(chartMock.dispatchAction).toHaveBeenCalledWith({
      type: 'dataZoom',
      startValue: '2026-08-01 10:00:00',
      endValue: '2026-08-01 12:00:00'
    })
  })

  it('窗口 resize → chart.resize', async () => {
    mountChart()
    await flushPromises()
    window.dispatchEvent(new Event('resize'))
    expect(chartMock.resize).toHaveBeenCalled()
  })

  it('卸载 → dispose 并移除 resize 监听', async () => {
    const wrapper = mountChart()
    await flushPromises()
    wrapper.unmount()
    expect(chartMock.dispose).toHaveBeenCalled()
    // 卸载后再 resize 不再触发
    window.dispatchEvent(new Event('resize'))
    const count = chartMock.resize.mock.calls.length
    expect(count).toBe(0)
  })
})
