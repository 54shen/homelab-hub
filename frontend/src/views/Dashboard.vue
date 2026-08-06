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
        icon="cube-outline"
        icon-bg="rgba(34, 197, 94, 0.1)"
        icon-color="#22C55E"
        :primary="stats.total_devices"
        :secondary="stats.total_keys"
        label="设备 / 变量"
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

    <!-- 剪切板 + 变更动态 并排(窄屏折叠为单列) -->
    <div class="lower-grid">
      <ClipboardPanel />

      <!-- 变更动态:WS 实时,最多 20 条,旧数据直接抛弃 -->
      <div class="lower-right">
        <h2 style="margin:0 0 12px;font-size:16px;font-weight:600;color:var(--text-primary)">
          变更动态
          <span style="font-size:12px;font-weight:400;color:var(--text-secondary);margin-left:8px">
            <span class="live-dot"></span> 实时 · {{ liveChanges.length }}/{{ MAX_LIVE }}
          </span>
        </h2>
        <n-data-table
          :columns="liveColumns"
          :data="liveChanges"
          :row-key="(row: any) => row.uid"
          :bordered="false"
          size="small"
          style="background:var(--bg-card);border-radius:var(--radius-lg);box-shadow:var(--shadow-card)"
        >
          <template #empty>
            <span style="color:var(--text-secondary);font-size:13px">等待实时数据…(KV 变更会实时出现在这里)</span>
          </template>
        </n-data-table>
      </div>
    </div>

    <!-- 历史记录弹窗 -->
    <HistoryModal v-model:show="showHistory" :key-prop="historyKey" />
  </div>
</template>

<script setup lang="ts">
import { h, onMounted, onUnmounted, ref } from 'vue'
import { NDataTable, NEmpty, NTag } from 'naive-ui'
import StatCard from '../components/StatCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import HistoryModal from '../components/HistoryModal.vue'
import ClipboardPanel from '../components/ClipboardPanel.vue'
import { dashboardApi, deviceApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import { useFieldLabels } from '../composables/useFieldLabels'
import { isClipboardKey } from '../utils/clipboard'
import type { DashboardStats, Device, KvHistory } from '../types'

const stats = ref<DashboardStats>({
  total_devices: 0, online_devices: 0, total_services: 0,
  running_services: 0, total_keys: 0, network_status: 'offline', public_ip: '--', system_health: 100
})
const devices = ref<Device[]>([])
const showHistory = ref(false)
const historyKey = ref('')
const haVarCounts = ref<Record<string, number>>({})
const haSubDeviceSummary = ref<Record<string, Record<string, string>>>({})

// ---- 变更动态:实时展示最近 KV 变更,最多 20 条,超出丢弃最旧 ----
const { labelOf } = useFieldLabels()
function keyLabel(key: string): string {
  const label = labelOf(key)
  return label === key ? key : label
}
const MAX_LIVE = 20
const liveChanges = ref<Array<KvHistory & { uid: string }>>([])
const liveSeen = new Set<string>()

function pushLive(data: any) {
  // 剪切板写入不进变更动态(面板自带实时历史,原始 JSON 在这里是噪音)
  if (isClipboardKey(data.key)) return
  const uid = `${data.key}|${data.changed_at}`
  console.log('[变更动态] WS kv.changed 收到:', { key: data.key, value: data.value, old_value: data.old_value, source: data.source, changed_at: data.changed_at })
  if (liveSeen.has(uid)) {
    console.log('[变更动态] 重复跳过:', uid)
    return
  }
  liveSeen.add(uid)
  liveChanges.value.unshift({
    uid,
    id: Date.now(),
    key: data.key,
    old_value: data.old_value ?? null,
    new_value: data.value,
    source: data.source || '',
    retention_days: data.retention_days ?? 180,
    changed_at: data.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' '),
  })
  // 旧数据直接抛弃,保持最多 20 条
  while (liveChanges.value.length > MAX_LIVE) {
    const removed = liveChanges.value.pop()!
    console.log('[变更动态] 淘汰最旧:', removed.changed_at, removed.key)
    liveSeen.delete(removed.uid)
  }
  console.log('[变更动态] 插入后:', liveChanges.value.length, '条 | 最新(第1行):', liveChanges.value[0]?.changed_at, '| 最旧(最后1行):', liveChanges.value[liveChanges.value.length - 1]?.changed_at)
}

const liveColumns = [
  {
    title: '时间', key: 'changed_at', width: 150,
    render(row: KvHistory) { return row.changed_at }
  },
  {
    title: '键', key: 'key', width: 200, ellipsis: { tooltip: true },
    render(row: KvHistory) {
      return h('span', { title: row.key }, keyLabel(row.key))
    }
  },
  {
    title: '来源', key: 'source', width: 110,
    render(row: KvHistory) { return row.source || '—' }
  },
  {
    title: '变更', key: 'change', minWidth: 220,
    render(row: KvHistory) {
      if (!row.old_value) {
        return h('span', { style: 'color:#22C55E;font-size:12px' }, `(新增) → ${row.new_value}`)
      }
      return [
        h('span', { style: 'color:var(--text-secondary);text-decoration:line-through;font-size:12px' }, row.old_value),
        h('span', { style: 'color:var(--text-secondary);margin:0 6px' }, '→'),
        h('span', { style: 'color:#22C55E;font-weight:500;font-size:12px' }, row.new_value),
      ]
    }
  },
]

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
    const [sRes, dRes, rRes] = await Promise.all([
      dashboardApi.stats(),
      deviceApi.list(),
      dashboardApi.recentChanges(MAX_LIVE)
    ])
    if (sRes.data) stats.value = sRes.data
    // 初始填充最近变更(旧数据直接抛弃,最多 MAX_LIVE 条)
    if (rRes.data) {
      liveChanges.value = rRes.data.map(r => ({ ...r, uid: `${r.key}|${r.changed_at}` }))
      liveSeen.clear()
      liveChanges.value.forEach(r => liveSeen.add(r.uid))
      const times = liveChanges.value.map(r => r.changed_at)
      const sorted = [...times].sort().reverse()
      console.log('[变更动态] 初始加载:', liveChanges.value.length, '条 | 首行:', times[0], '| 末行:', times[times.length - 1], '| 时间逆序正确:', JSON.stringify(times) === JSON.stringify(sorted))
    }
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
    if (event === 'kv.changed') {
      pushLive(data)  // 实时插入变更动态
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

/* ── 剪切板 + 变更动态 并排 ── */
.lower-grid {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: var(--gap-md);
  margin-top: 24px;
  align-items: start;
}
@media (max-width: 1100px) {
  .lower-grid { grid-template-columns: 1fr; }
}

/* ── 变更动态 ── */
.live-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  margin-right: 4px;
  vertical-align: 1px;
  animation: live-pulse 1.6s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
