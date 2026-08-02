<template>
  <div class="page-container">
    <div class="page-title-row">
      <h1 class="page-title">仪表盘</h1>
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

    <!-- 最近变更（历史记录功能已移除） -->
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NCard } from 'naive-ui'
import StatCard from '../components/StatCard.vue'
import { dashboardApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import type { DashboardStats } from '../types'

const stats = ref<DashboardStats>({
  total_devices: 0, online_devices: 0, total_services: 0,
  running_services: 0, network_status: 'offline', public_ip: '--', system_health: 100
})

async function loadData() {
  try {
    const sRes = await dashboardApi.stats()
    if (sRes.data) stats.value = sRes.data
  } catch {
    // 后端未响应，保持上次数据
  }
}

// ---- WebSocket 实时更新 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(async () => {
  await loadData()
  cleanupWs = on((event, _data: any) => {
    // 有变化时静默刷新统计数据
    if (event === 'heartbeat' || event === 'kv.changed' || event === 'device.heartbeat') {
      dashboardApi.stats().then(r => { if (r.data) stats.value = r.data }).catch(() => {})
    }
  })
})

onUnmounted(() => {
  cleanupWs?.()
})
</script>

<style scoped>
.page-title-row { display: flex; align-items: center; gap: 12px; }
.page-title-row .page-title { margin-bottom: 0; }
</style>
