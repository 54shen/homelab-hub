<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { TrendPoint } from '../types'

const props = defineProps<{
  points: TrendPoint[]
  title?: string
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

watch(() => props.points, render)

function onResize() {
  chart && chart.resize()
}

function render() {
  if (!chart) return
  chart.setOption({
    title: { text: props.title, left: 'center', textStyle: { fontSize: 14, color: '#1A1D26' } },
    tooltip: { trigger: 'axis' },
    grid: { left: 55, right: 25, top: 42, bottom: 32 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'line',
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2, color: '#5B8DEF' },
      itemStyle: { color: '#5B8DEF' },
      data: props.points.map(p => [p.changed_at.replace(' ', 'T'), p.value]),
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
