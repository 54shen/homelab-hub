<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { TrendPoint } from '../types'

const props = defineProps<{
  points: TrendPoint[]
  title?: string
  plotKind?: string  // '' / 'number' / 'duration' / 'timestamp' / 'state' 决定 y 轴与 tooltip 展示
  zoom?: { start: string; end: string } | null  // 外部要恢复的 dataZoom 窗口(切模式时保持横轴比例)
  defaultSpanHours?: number  // 首次渲染的默认时间窗口(小时),之后用户缩放/拖动不再重置
}>()

// 单击图表 → 携带当前 dataZoom 可视时间窗口(供频率视图等使用)
// 缩放/拖动窗口变化 → 通知外部(频率视图按窗口跨度自适应粒度)
// 拖动到最早数据边界 → 通知外部加载更早数据(时间轴可继续向前扩展)
const emit = defineEmits<{
  click: [win: { start: string; end: string } | null]
  zoom: [win: { start: string; end: string } | null]
  'reach-start': []
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
// 首次渲染设置默认窗口(最近 N 小时),之后用户缩放/拖动不再重置
let initialZoomSet = false

// 当前可视窗口:由 dataZoom 百分比映射到数据点时间范围
function currentWindow(): { start: string; end: string } | null {
  if (!chart) return null
  const dz = (chart.getOption() as any)?.dataZoom?.[0]
  const s = dz?.start ?? 0
  const e = dz?.end ?? 100
  const n = props.points.length
  if (n === 0) return null
  const i0 = Math.max(0, Math.min(n - 1, Math.floor((s / 100) * n)))
  const i1 = Math.max(0, Math.min(n - 1, Math.ceil((e / 100) * n) - 1))
  return { start: props.points[i0].changed_at, end: props.points[i1].changed_at }
}

// 缩放/拖动窗口变化 → 通知外部(频率粒度自适应);到达最早数据边界 → 请求更早数据(节流 1s)
let reachLock = false
function onDataZoom() {
  if (props.points.length === 0) return  // 空数据不触发任何事件(与有数据时行为一致)
  emit('zoom', currentWindow())
  if (reachLock) return
  const dz = (chart?.getOption() as any)?.dataZoom?.[0]
  if (dz && dz.start <= 0.5) {
    // 窗口起点已到达(接近)最早数据点 → 请求更早数据
    reachLock = true
    emit('reach-start')
    setTimeout(() => { reachLock = false }, 1000)
  }
}

onMounted(async () => {
  await nextTick() // 防容器刚可见时 init 拿到 0 宽
  chart = echarts.init(el.value)
  window.addEventListener('resize', onResize)
  // 单击图表任意位置(含空白)→ 通知外部,并带上当前缩放窗口
  chart.getZr().on('click', () => emit('click', currentWindow()))
  // 拖动/缩放时间轴 → 检测是否到达最早边界
  chart.on('datazoom', onDataZoom)
  render()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})

// deep:WS 实时插入的新点走 splice 原地修改(引用不变),必须监听内容变化
watch(() => props.points, render, { deep: true })

// 模式切换时恢复缩放窗口(横轴比例不变);引用不变(如数据扩展)时不触发,避免拖动跳窗
watch(() => props.zoom, (z, old) => {
  if (z && z !== old && chart) {
    nextTick(() => {
      chart?.dispatchAction({ type: 'dataZoom', startValue: z.start, endValue: z.end })
    })
  }
})

function onResize() {
  chart && chart.resize()
}

// 时长(秒)→ 可读文本,如 1d 5h / 3h 25m / 12m
function formatDuration(sec: number): string {
  const s = Math.round(sec)
  if (s >= 86400) {
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600)
    return h > 0 ? `${d}d ${h}h` : `${d}d`
  }
  if (s >= 3600) {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
    return m > 0 ? `${h}h ${m}m` : `${h}h`
  }
  const m = Math.floor(s / 60), left = s % 60
  return m > 0 ? `${m}m ${left}s` : `${left}s`
}

// 时间戳(epoch 秒)→ 'MM-DD HH:MM' / 'HH:MM'
function formatStamp(sec: number): string {
  const d = new Date(sec * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  const hm = `${p(d.getHours())}:${p(d.getMinutes())}`
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${hm}`
}

// 状态值(on/off 等原始字符串)→ 中文展示
function stateLabel(raw: string | null): string {
  if (raw == null) return ''
  const v = raw.trim().toLowerCase()
  const on = ['on', 'true', 'open', 'locked', 'home', 'playing', 'active']
  const off = ['off', 'false', 'closed', 'unlocked', 'not_home', 'paused', 'idle']
  if (on.includes(v)) return '开'
  if (off.includes(v)) return '关'
  return raw
}

function yAxisFormatter(v: number): string {
  if (props.plotKind === 'state') return v >= 0.5 ? '开' : '关'
  if (props.plotKind === 'duration') return formatDuration(v)
  if (props.plotKind === 'timestamp') return formatStamp(v)
  return String(v)
}

// 时间轴缩放选项;首次渲染:默认窗口 = 最后 N 小时(defaultSpanHours,默认 48),
// 之后用户缩放/拖动不再重置(可继续滚轮/拖动看更早)
function dataZoomOpt(): any {
  const dz: any = { type: 'inside', xAxisIndex: 0, filterMode: 'none' }
  if (!initialZoomSet && props.points.length > 0) {
    const span = (props.defaultSpanHours ?? 48) * 3600 * 1000
    const lastT = new Date(props.points[props.points.length - 1].changed_at.replace(' ', 'T')).getTime()
    dz.startValue = lastT - span
    dz.endValue = lastT
    initialZoomSet = true
  }
  return dz
}

function render() {
  if (!chart) return
  const isState = props.plotKind === 'state'
  // 阶梯数据:每个变更点展开为「保持段终点(t, 旧值) + 跳变点(t, 新值)」。
  // 水平段严格水平(表示值一直未变),只有真正变化的瞬间由小曲率平滑过渡。
  // 数据带原始值,供 tooltip 展示(时长/时间戳等非纯数值格式)。
  const data: Array<[string, number, string | null]> = []
  if (props.points.length === 1) {
    const p = props.points[0]
    const t = p.changed_at.replace(' ', 'T')
    data.push([t, p.value, p.raw ?? null])
  } else {
    for (let i = 0; i < props.points.length; i++) {
      const p = props.points[i]
      const t = p.changed_at.replace(' ', 'T')
      if (i > 0) {
        const prev = props.points[i - 1]
        data.push([t, prev.value, prev.raw ?? null])  // 旧值保持到本变更时刻
      }
      data.push([t, p.value, p.raw ?? null])          // 变更瞬间的新值
    }
  }
  // 同一时刻存在新旧两点时,tooltip 取最后一项(变更后的新值,客观)
  const tooltip = {
    trigger: 'axis',
    formatter: (params: any) => {
      const last = params[params.length - 1]
      if (!last?.data) return ''
      const [t, _v, raw] = last.data
      const label = isState ? stateLabel(raw ?? String(_v)) : (raw ?? _v)
      return `${String(t).replace('T', ' ')}<br/>${label}`
    },
  }
  chart.setOption({
    title: { text: props.title, left: 'center', textStyle: { fontSize: 14, color: '#1A1D26' } },
    tooltip,
    grid: { left: 70, right: 25, top: 42, bottom: 32 },
    xAxis: { type: 'time' },
    // 非时间戳型从 0 开始(值趋势/频率切换时 y 轴不跳);时间戳型保持压缩轴;
    // 状态图固定 0/1 双档(开/关)
    yAxis: {
      type: 'value',
      scale: props.plotKind === 'timestamp',
      min: isState ? 0 : (props.plotKind === 'timestamp' ? undefined : 0),
      max: isState ? 1 : undefined,
      interval: isState ? 1 : undefined,
      axisLabel: { formatter: yAxisFormatter },
    },
    // 时间轴缩放/平移:滚轮与双指缩放,拖拽平移,时间轴上滚动同样生效
    dataZoom: [dataZoomOpt()],
    series: [{
      type: 'line',
      showSymbol: false,
      // 状态图:垂直阶梯线(开/关切换一目了然);其余保持小曲率平滑
      step: isState ? 'end' : undefined,
      smooth: isState ? false : 0.15,
      lineStyle: { width: 2, color: '#5B8DEF' },
      itemStyle: { color: '#5B8DEF' },
      data,
    }],
  })
}
</script>

<template>
  <div class="chart-box">
    <div ref="el" class="trend-chart"></div>
    <p v-if="points.length === 0" class="hint">所选范围内暂无数值数据</p>
  </div>
</template>

<style scoped>
.chart-box {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  margin-bottom: 12px;
}
.trend-chart { height: 380px; width: 100%; }
.hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.7);
}
</style>
