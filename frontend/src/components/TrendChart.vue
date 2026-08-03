<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { TrendPoint } from '../types'

const props = defineProps<{
  points: TrendPoint[]
  title?: string
  plotKind?: string  // '' / 'number' / 'duration' / 'timestamp' 决定 y 轴与 tooltip 展示
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

onMounted(async () => {
  await nextTick() // 防容器刚可见时 init 拿到 0 宽
  chart = echarts.init(el.value)
  window.addEventListener('resize', onResize)
  render()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})

// deep:WS 实时插入的新点走 splice 原地修改(引用不变),必须监听内容变化
watch(() => props.points, render, { deep: true })

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

function yAxisFormatter(v: number): string {
  if (props.plotKind === 'duration') return formatDuration(v)
  if (props.plotKind === 'timestamp') return formatStamp(v)
  return String(v)
}

function render() {
  if (!chart) return
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
      return `${String(t).replace('T', ' ')}<br/>${raw ?? _v}`
    },
  }
  chart.setOption({
    title: { text: props.title, left: 'center', textStyle: { fontSize: 14, color: '#1A1D26' } },
    tooltip,
    grid: { left: 70, right: 25, top: 42, bottom: 32 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: yAxisFormatter } },
    // 时间轴缩放/平移:滚轮与双指缩放,拖拽平移,时间轴上滚动同样生效
    dataZoom: [{ type: 'inside', xAxisIndex: 0, filterMode: 'none' }],
    series: [{
      type: 'line',
      showSymbol: false,
      smooth: 0.15,  // 小曲率:只在变化瞬间圆滑,保持段不弯曲
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
