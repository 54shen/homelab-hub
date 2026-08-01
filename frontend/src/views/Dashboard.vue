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
import { onMounted, onUnmounted, ref } from 'vue'
import { NCard, NEmpty } from 'naive-ui'
import StatCard from '../components/StatCard.vue'
import { dashboardApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import type { DashboardStats, KvHistory } from '../types'

const stats = ref<DashboardStats>({
  total_devices: 0, online_devices: 0, total_services: 0,
  running_services: 0, network_status: 'offline', public_ip: '--', system_health: 100
})
const recentChanges = ref<KvHistory[]>([])

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
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed') {
      recentChanges.value.unshift({
        id: Date.now(), key: data.key,
        old_value: null, new_value: data.value,
        source: data.source || 'ws', changed_at: new Date().toISOString()
      })
      if (recentChanges.value.length > 10) recentChanges.value.pop()
    }
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
