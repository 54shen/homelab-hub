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

    <!-- 设备卡片 -->
    <h2 style="margin:24px 0 12px;font-size:16px;font-weight:600;color:var(--text-primary)">设备状态</h2>
    <div v-if="devices.length > 0" class="device-grid">
      <div
        v-for="d in devices"
        :key="d.id"
        class="device-card"
        @click="$router.push('/devices/' + d.id)"
      >
        <div class="dc-top">
          <span class="dc-icon">{{ iconForType(d.type) }}</span>
          <div class="dc-identity">
            <span class="dc-name">{{ d.name }}</span>
            <span class="dc-hostname">{{ d.hostname || d.ip || '—' }}</span>
          </div>
          <div class="dc-status">
            <StatusBadge :online="d.online" />
          </div>
        </div>
        <div class="dc-tags">
          <n-tag size="tiny" :bordered="false" round>{{ d.group || '默认' }}</n-tag>
          <n-tag size="tiny" :bordered="false" round type="info">{{ d.type }}</n-tag>
          <n-tag v-if="d.version" size="tiny" :bordered="false" round>v{{ d.version }}</n-tag>
        </div>
        <!-- 指标 -->
        <div v-if="d.online && d.type !== 'ha'" class="dc-metrics">
          <div v-if="d.cpu != null" class="dc-metric metric-clickable" @click.stop="openHistory(d.name + '.cpu')">
            <span class="dm-label">CPU</span>
            <div class="dm-bar"><div class="dm-fill cpu" :style="{ width: (d.cpu ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.cpu }}%</span>
          </div>
          <div v-if="d.memory != null" class="dc-metric metric-clickable" @click.stop="openHistory(d.name + '.memory')">
            <span class="dm-label">MEM</span>
            <div class="dm-bar"><div class="dm-fill mem" :style="{ width: (d.memory ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.memory }}%</span>
          </div>
          <div v-if="d.disk != null" class="dc-metric metric-clickable" @click.stop="openHistory(d.name + '.disk')">
            <span class="dm-label">DSK</span>
            <div class="dm-bar"><div class="dm-fill disk" :style="{ width: (d.disk ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.disk }}%</span>
          </div>
          <div v-if="d.volume != null" class="dc-metric metric-clickable" @click.stop="openHistory(d.name + '.volume')">
            <span class="dm-label">VOL</span>
            <div class="dm-bar">
              <div class="dm-fill vol" :class="{ muted: (d.volume ?? 0) < 0 }" :style="{ width: (d.volume ?? 0) < 0 ? '0%' : (d.volume ?? 0) + '%' }"></div>
            </div>
            <span class="dm-val" :class="{ 'muted-text': (d.volume ?? 0) < 0 }">{{ (d.volume ?? 0) < 0 ? '🔇' : d.volume + '%' }}</span>
          </div>
        </div>
        <!-- HA 设备 -->
        <div v-if="d.type === 'ha'" class="dc-ha-summary">
          <div class="ha-var-row">
            <span v-for="(icon, name) in haSubDeviceSummary[d.id] || {}" :key="name" class="ha-chip">
              {{ icon }} {{ name }}
            </span>
          </div>
          <div class="ha-count">共 {{ haVarCounts[d.id] || 0 }} 个变量</div>
        </div>
        <div class="dc-footer">
          <span class="dc-heartbeat">{{ formatRelative(d.last_heartbeat) }}</span>
        </div>
      </div>
    </div>
    <n-empty v-else description="暂无设备" style="margin-top:20px" />

    <!-- 历史记录弹窗 -->
    <HistoryModal v-model:show="showHistory" :key-prop="historyKey" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NEmpty, NTag } from 'naive-ui'
import StatCard from '../components/StatCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import HistoryModal from '../components/HistoryModal.vue'
import { dashboardApi, deviceApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import type { DashboardStats, Device } from '../types'

const stats = ref<DashboardStats>({
  total_devices: 0, online_devices: 0, total_services: 0,
  running_services: 0, network_status: 'offline', public_ip: '--', system_health: 100
})
const devices = ref<Device[]>([])
const showHistory = ref(false)
const historyKey = ref('')
const haVarCounts = ref<Record<string, number>>({})
const haSubDeviceSummary = ref<Record<string, Record<string, string>>>({})

const HA_SUB_ICONS: Record<string, string> = {
  开关: '🔘', 状态: '📋', 功率: '⚡', 温度: '🌡️', 湿度: '💧',
  浓度: '🌿', 质量: '🌿', 位置: '📍', 亮度: '💡', 电量: '🔋',
  模式: '⚙️', 风速: '💨', 速度: '💨', 等级: '📊',
}

function openHistory(key: string) {
  historyKey.value = key
  showHistory.value = true
}

function iconForType(type: string): string {
  const map: Record<string, string> = {
    computer: '🖥️', server: '📦', nas: '💾', iot: '🏠',
    cloud: '☁️', docker: '🐳', vm: '📀', router: '📡', ha: '🏠'
  }
  return map[type] || '📡'
}

function formatRelative(ts: string): string {
  if (!ts) return '—'
  const diff = Date.now() - new Date(ts).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return `${Math.floor(sec / 86400)} 天前`
}

async function loadData() {
  try {
    const [sRes, dRes] = await Promise.all([
      dashboardApi.stats(),
      deviceApi.list()
    ])
    if (sRes.data) stats.value = sRes.data
    if (dRes.data) {
      devices.value = dRes.data
      // 加载 HA 设备的变量统计
      for (const d of devices.value) {
        if (d.type === 'ha') {
          try {
            const vRes = await deviceApi.variables(d.id)
            const vars = vRes.data || []
            haVarCounts.value[d.id] = vars.length
            const prefix = d.name + '.'
            const summary: Record<string, string> = {}
            const seen = new Set<string>()
            for (const v of vars) {
              const raw = v.key.startsWith(prefix) ? v.key.slice(prefix.length) : v.key
              let devName = raw
              const suffixes = ['设置温度','当前温度','开关','状态','功率','温度','湿度','浓度','位置','亮度','电量','模式','风速','速度','质量','等级']
              for (const s of suffixes) {
                if (raw.endsWith(s) && raw.length > s.length) {
                  devName = raw.slice(0, -s.length)
                  break
                }
              }
              if (!seen.has(devName) && seen.size < 8) {
                seen.add(devName)
                const propSuffix = raw.slice(devName.length)
                summary[devName] = HA_SUB_ICONS[propSuffix] || '📊'
              }
            }
            haSubDeviceSummary.value[d.id] = summary
          } catch { /* ignore */ }
        }
      }
    }
  } catch {
    // 后端未响应，保持上次数据
  }
}

// ---- WebSocket 实时更新 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(async () => {
  await loadData()
  cleanupWs = on((event, data: any) => {
    if (event === 'device.heartbeat') {
      const dev = devices.value.find(d => d.name === data.name)
      if (dev) {
        if (data.cpu != null) dev.cpu = data.cpu
        if (data.memory != null) dev.memory = data.memory
        if (data.disk != null) dev.disk = data.disk
        if (data.volume != null) dev.volume = data.volume
        dev.online = data.online
        dev.last_heartbeat = new Date().toLocaleString('sv-SE').replace('T', ' ')
      }
    }
    if (event === 'device.registered' || event === 'device.unregistered') {
      deviceApi.list().then(r => { if (r.data) devices.value = r.data }).catch(() => {})
    }
    if (event === 'heartbeat' || event === 'kv.changed') {
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

/* ── 设备卡片 ── */
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--gap-md);
}
.device-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: all 0.2s ease;
}
.device-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.dc-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.dc-icon { font-size: 32px; flex-shrink: 0; line-height: 1; }
.dc-identity { flex: 1; min-width: 0; }
.dc-name {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dc-hostname {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  margin-top: 2px;
}
.dc-tags { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
.dc-metrics { margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
.dc-metric { display: flex; align-items: center; gap: 8px; }
.dc-metric.metric-clickable {
  cursor: pointer;
  padding: 2px 4px;
  margin: -2px -4px;
  border-radius: 4px;
  transition: background 0.15s;
}
.dc-metric.metric-clickable:hover {
  background: var(--border-light);
}
.dm-label {
  font-size: 10px;
  color: var(--text-secondary);
  width: 28px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.dm-bar {
  flex: 1;
  height: 5px;
  background: var(--border-light);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dm-fill { height: 100%; border-radius: var(--radius-full); transition: width 0.5s ease; }
.dm-fill.cpu { background: var(--color-info); }
.dm-fill.mem { background: var(--color-success); }
.dm-fill.disk { background: var(--color-warning); }
.dm-fill.vol { background: #A855F7; }
.dm-fill.vol.muted { background: #9CA3AF; }
.muted-text { color: #9CA3AF; }
.dm-val {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.dc-footer { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.dc-heartbeat { font-size: 11px; color: var(--text-secondary); }
.dc-status { display: flex; align-items: center; gap: 8px; }
.dc-ha-summary { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.ha-var-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.ha-chip {
  font-size: 12px;
  background: var(--border-light);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.ha-count { font-size: 12px; color: var(--text-secondary); }
</style>
