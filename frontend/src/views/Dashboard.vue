<template>
  <div class="page-container">
    <div class="page-title-row">
      <h1 class="page-title">仪表盘</h1>
      <RefreshControl v-model="refreshInterval" />
    </div>

    <!-- 统计卡片 -->
    <div class="card-grid">
      <StatCard
        icon="hardware-chip-outline"
        icon-bg="rgba(91, 141, 239, 0.1)"
        icon-color="#5B8DEF"
        :primary="stats.online_devices"
        :secondary="stats.total_devices"
        label="在线设备"
        to="/devices"
      />
      <StatCard
        icon="server-outline"
        icon-bg="rgba(34, 197, 94, 0.1)"
        icon-color="#22C55E"
        :primary="stats.running_services"
        :secondary="stats.total_services"
        label="服务运行中"
        to="/variables"
      />
      <StatCard
        icon="wifi-outline"
        icon-bg="rgba(245, 158, 11, 0.1)"
        icon-color="#F59E0B"
        :primary="stats.network_status === 'online' ? '正常' : '异常'"
        :secondary="stats.public_ip"
        label="网络状态"
      />
      <StatCard
        icon="pulse-outline"
        icon-bg="rgba(34, 197, 94, 0.1)"
        icon-color="#22C55E"
        :primary="stats.system_health + '%'"
        label="系统健康度"
      />
    </div>

    <!-- 图表 -->
    <div class="card-grid-2" style="margin-top: 16px">
      <n-card title="CPU 使用率" size="small">
        <template #header-extra>
          <span style="font-size:12px;color:var(--text-secondary)">最近 1 小时</span>
        </template>
        <div ref="cpuChartRef" class="chart-box"></div>
      </n-card>
      <n-card title="内存使用率" size="small">
        <template #header-extra>
          <span style="font-size:12px;color:var(--text-secondary)">最近 1 小时</span>
        </template>
        <div ref="memChartRef" class="chart-box"></div>
      </n-card>
    </div>

    <!-- 最近变更 -->
    <n-card title="最近变更" size="small" style="margin-top: 16px">
      <template #header-extra>
        <span style="font-size:12px;color:var(--text-secondary)">最近 10 条</span>
      </template>
      <n-empty v-if="recentChanges.length === 0" description="暂无变更记录" />
      <div v-else class="change-list">
        <div v-for="item in recentChanges" :key="item.id" class="change-item">
          <span class="change-time">{{ formatTime(item.changed_at) }}</span>
          <code class="change-key">{{ item.key }}</code>
          <span class="change-values">
            <span v-if="item.old_value" class="old-val">{{ item.old_value }}</span>
            <span v-if="item.old_value" class="arrow">→</span>
            <span v-else class="tag-new">新增</span>
            <span class="new-val">{{ item.new_value }}</span>
          </span>
          <span class="change-source">{{ item.source }}</span>
        </div>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, watch } from 'vue'
import { NCard, NEmpty } from 'naive-ui'
import * as echarts from 'echarts'
import StatCard from '../components/StatCard.vue'
import RefreshControl from '../components/RefreshControl.vue'
import { dashboardApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import { useRefreshInterval } from '../composables/useRefreshInterval'
import type { DashboardStats, KvHistory } from '../types'

const stats = ref<DashboardStats>({
  total_devices: 0, online_devices: 0, total_services: 0,
  running_services: 0, network_status: 'offline', public_ip: '--', system_health: 100
})
const recentChanges = ref<KvHistory[]>([])
const refreshInterval = useRefreshInterval()

// ---- 定时刷新 ----
let timer: ReturnType<typeof setInterval> | null = null
function startTimer(sec: number) {
  if (timer) { clearInterval(timer); timer = null }
  if (sec > 0) timer = setInterval(loadData, sec * 1000)
}
watch(refreshInterval, startTimer)

const cpuChartRef = ref<HTMLElement | null>(null)
const memChartRef = ref<HTMLElement | null>(null)
let cpuChart: echarts.ECharts | null = null
let memChart: echarts.ECharts | null = null

const cpuData = ref<number[]>([15, 22, 30, 28, 35, 32, 32])
const memData = ref<number[]>([40, 42, 45, 48, 46, 45, 45])

function makeAreaOption(data: number[], color: string) {
  return {
    grid: { top: 8, right: 12, bottom: 24, left: 40 },
    xAxis: {
      type: 'category' as const,
      data: ['-60m', '-50m', '-40m', '-30m', '-20m', '-10m', '现在'],
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { fontSize: 10, color: '#94A3B8' }
    },
    yAxis: {
      type: 'value' as const, min: 0, max: 100,
      splitLine: { lineStyle: { color: '#EDF0F4', type: 'dashed' as const } },
      axisLabel: { fontSize: 10, color: '#94A3B8', formatter: '{value}%' }
    },
    series: [{
      data, type: 'line' as const, smooth: true, symbol: 'none' as const,
      lineStyle: { color, width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '30' },
          { offset: 1, color: color + '04' }
        ])
      }
    }]
  }
}

async function loadData() {
  try {
    const [sRes, rRes] = await Promise.all([
      dashboardApi.stats(),
      dashboardApi.recentChanges(10)
    ])
    if (sRes.data) stats.value = sRes.data
    if (rRes.data) recentChanges.value = rRes.data
  } catch {
    // 后端未响应，保持上次数据
  }
}

function formatTime(ts: string): string {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// ---- WebSocket 实时更新 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(async () => {
  await loadData()
  // WebSocket 事件监听
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed') {
      // 变量变更时刷新最近变更列表
      recentChanges.value.unshift({
        id: Date.now(), key: data.key,
        old_value: null, new_value: data.value,
        source: data.source || 'ws', changed_at: new Date().toISOString()
      })
      if (recentChanges.value.length > 10) recentChanges.value.pop()
    }
    if (event === 'device.heartbeat') {
      // 设备心跳更新 CPU/MEM 图表数据
      if (data.cpu !== undefined && data.cpu !== null) {
        cpuData.value.push(data.cpu)
        cpuData.value.shift()
        cpuChart?.setOption(makeAreaOption(cpuData.value, '#5B8DEF'))
      }
      if (data.memory !== undefined && data.memory !== null) {
        memData.value.push(data.memory)
        memData.value.shift()
        memChart?.setOption(makeAreaOption(memData.value, '#22C55E'))
      }
    }
    if (event === 'heartbeat' || event === 'kv.changed' || event === 'device.heartbeat') {
      // 有变化时静默刷新统计数据
      dashboardApi.stats().then(r => { if (r.data) stats.value = r.data }).catch(() => {})
    }
  })

  // 初始化图表
  await nextTick()
  if (cpuChartRef.value) {
    cpuChart = echarts.init(cpuChartRef.value)
    cpuChart.setOption(makeAreaOption(cpuData.value, '#5B8DEF'))
  }
  if (memChartRef.value) {
    memChart = echarts.init(memChartRef.value)
    memChart.setOption(makeAreaOption(memData.value, '#22C55E'))
  }
})

onUnmounted(() => {
  cleanupWs?.()
  if (timer) clearInterval(timer)
  cpuChart?.dispose()
  memChart?.dispose()
})
</script>

<style scoped>
.page-title-row { display: flex; align-items: center; gap: 12px; }
.page-title-row .page-title { margin-bottom: 0; }
.chart-box { width: 100%; height: 200px; }
.change-list { display: flex; flex-direction: column; }
.change-item {
  display: flex; align-items: center; gap: 16px;
  padding: 10px 0; border-bottom: 1px solid var(--border-light); font-size: 13px;
}
.change-item:last-child { border-bottom: none; }
.change-time { color: var(--text-secondary); font-size: 12px; flex-shrink: 0; width: 50px; }
.change-key {
  font-size: 12px; background: #F1F5F9; padding: 2px 8px;
  border-radius: 6px; color: var(--color-info); font-family: monospace; flex-shrink: 0;
}
.change-values { flex: 1; display: flex; align-items: center; gap: 8px; }
.old-val { color: var(--color-danger); text-decoration: line-through; font-size: 12px; }
.arrow { color: var(--text-secondary); font-size: 12px; }
.new-val { color: var(--color-success); font-weight: 500; font-size: 12px; }
.tag-new {
  font-size: 11px; background: rgba(34, 197, 94, 0.1);
  color: var(--color-success); padding: 1px 6px; border-radius: 4px;
}
.change-source { color: var(--text-secondary); font-size: 11px; flex-shrink: 0; }
</style>
