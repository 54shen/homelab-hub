<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">设备管理</h1>
      <n-space>
        <RefreshControl v-model="refreshInterval" />
        <n-select
          v-model:value="filterGroup"
          :options="groupFilterOptions"
          placeholder="按分组筛选"
          clearable
          size="small"
          style="width:140px"
        />
        <n-button-group>
          <n-button size="small" :type="viewMode === 'card' ? 'primary' : 'default'" @click="viewMode = 'card'">
            <ion-icon name="grid-outline"></ion-icon>
          </n-button>
          <n-button size="small" :type="viewMode === 'table' ? 'primary' : 'default'" @click="viewMode = 'table'">
            <ion-icon name="list-outline"></ion-icon>
          </n-button>
        </n-button-group>
      </n-space>
    </div>

    <n-empty v-if="filteredDevices.length === 0" description="暂无设备" style="margin-top:60px" />

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'card'" class="device-grid">
      <div
        v-for="d in filteredDevices"
        :key="d.id"
        class="device-card"
        @click="$router.push('/devices/' + d.id)"
      >
        <!-- 顶部 -->
        <div class="dc-top">
          <span class="dc-icon">{{ iconForType(d.type) }}</span>
          <div class="dc-identity">
            <span class="dc-name">{{ d.name }}</span>
            <span class="dc-hostname">{{ d.hostname || d.ip || '—' }}</span>
          </div>
          <div class="dc-status">
            <StatusBadge :online="d.online" />
            <span class="timeout-tag">⏱{{ d.heartbeat_timeout }}s</span>
          </div>
        </div>

        <!-- 标签 -->
        <div class="dc-tags">
          <n-tag size="tiny" :bordered="false" round>{{ d.group || '默认' }}</n-tag>
          <n-tag size="tiny" :bordered="false" round type="info">{{ d.type }}</n-tag>
          <n-tag v-if="d.version" size="tiny" :bordered="false" round>v{{ d.version }}</n-tag>
        </div>

        <!-- 指标：普通设备 -->
        <div v-if="d.online && d.type !== 'ha'" class="dc-metrics">
          <div v-if="d.cpu !== undefined && d.cpu !== null" class="dc-metric">
            <span class="dm-label">CPU</span>
            <div class="dm-bar"><div class="dm-fill cpu" :style="{ width: (d.cpu ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.cpu }}%</span>
          </div>
          <div v-if="d.memory !== undefined && d.memory !== null" class="dc-metric">
            <span class="dm-label">MEM</span>
            <div class="dm-bar"><div class="dm-fill mem" :style="{ width: (d.memory ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.memory }}%</span>
          </div>
          <div v-if="d.disk !== undefined && d.disk !== null" class="dc-metric">
            <span class="dm-label">DSK</span>
            <div class="dm-bar"><div class="dm-fill disk" :style="{ width: (d.disk ?? 0) + '%' }"></div></div>
            <span class="dm-val">{{ d.disk }}%</span>
          </div>
          <div v-if="d.volume !== undefined && d.volume !== null" class="dc-metric">
            <span class="dm-label">VOL</span>
            <div class="dm-bar">
              <div class="dm-fill vol" :class="{ muted: d.muted }" :style="{ width: d.muted ? '0%' : (d.volume ?? 0) + '%' }"></div>
            </div>
            <span class="dm-val" :class="{ 'muted-text': d.muted }">{{ d.muted ? '🔇' : '' }} {{ d.volume }}%</span>
          </div>
        </div>

        <!-- 指标：HA 智能家居设备 -->
        <div v-if="d.type === 'ha'" class="dc-ha-summary">
          <div class="ha-var-row">
            <span v-for="(icon, name) in haSubDeviceSummary[d.id] || {}" :key="name" class="ha-chip">
              {{ icon }} {{ name }}
            </span>
          </div>
          <div class="ha-count">共 {{ haVarCounts[d.id] || 0 }} 个变量</div>
        </div>

        <!-- 底部 -->
        <div class="dc-footer">
          <span class="dc-uptime" v-if="d.uptime">运行 {{ d.uptime }}</span>
          <span class="dc-heartbeat">{{ formatRelative(d.last_heartbeat) }}</span>
        </div>
      </div>
    </div>

    <!-- 列表视图 -->
    <n-data-table
      v-else
      :columns="columns"
      :data="filteredDevices"
      :bordered="false"
      size="small"
      :row-props="(row: Device) => ({ style: 'cursor:pointer', onClick: () => $router.push('/devices/' + row.id) })"
      style="background: var(--bg-card); border-radius: var(--radius-lg)"
    />

  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NButton, NButtonGroup, NDataTable, NEmpty, NInput, NSelect, NSpace, NTag
} from 'naive-ui'
import StatusBadge from '../components/StatusBadge.vue'
import RefreshControl from '../components/RefreshControl.vue'
import { useRefreshInterval } from '../composables/useRefreshInterval'
import { deviceApi } from '../api'
import type { Device } from '../types'

import { useUISetting } from '../composables/useUISetting'

const viewModeStr = useUISetting('device_view_mode', 'card')
const viewMode = computed<'card' | 'table'>({
  get: () => viewModeStr.value as 'card' | 'table',
  set: (v) => { viewModeStr.value = v }
})
const filterGroup = ref<string | null>(null)
const devices = ref<Device[]>([])
const refreshInterval = useRefreshInterval()
const haVarCounts = ref<Record<string, number>>({})
const haSubDeviceSummary = ref<Record<string, Record<string, string>>>({})

// HA 子设备图标映射
const HA_SUB_ICONS: Record<string, string> = {
  开关: '🔘', 状态: '📋', 功率: '⚡', 温度: '🌡️', 湿度: '💧',
  浓度: '🌿', 质量: '🌿', 位置: '📍', 亮度: '💡', 电量: '🔋',
  模式: '⚙️', 风速: '💨', 速度: '💨', 等级: '📊',
}

const groupFilterOptions = computed(() => {
  const groups = [...new Set(devices.value.map(d => d.group).filter(Boolean))]
  return groups.map(g => ({ label: g, value: g }))
})

const filteredDevices = computed(() => {
  const list = devices.value
  if (!filterGroup.value) return list
  return list.filter(d => d.group === filterGroup.value)
})

const columns = [
  { title: '名称', key: 'name', width: 160 },
  { title: '主机名', key: 'hostname', width: 140 },
  { title: 'IP', key: 'ip', width: 150 },
  { title: 'MAC', key: 'mac', width: 150 },
  { title: '类型', key: 'type', width: 80 },
  { title: '分组', key: 'group', width: 80 },
  { title: '版本', key: 'version', width: 70 },
  { title: '最后心跳', key: 'last_heartbeat', width: 160 },
  {
    title: '超时', key: 'heartbeat_timeout', width: 85,
    render(row: Device) {
      return h('span', { style: 'color:#E65100;font-weight:500;font-variant-numeric:tabular-nums' }, `${row.heartbeat_timeout}s`)
    }
  },
  {
    title: '状态', key: 'online', width: 80,
    render(row: Device) {
      return h(StatusBadge, { online: row.online })
    }
  }
]

function iconForType(type: string): string {
  const map: Record<string, string> = {
    computer: '🖥️', server: '📦', nas: '💾', iot: '🏠',
    cloud: '☁️', docker: '🐳', vm: '📀', router: '📡',
    'ha-device': '🏠'
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
    const res = await deviceApi.list()
    if (res.data) devices.value = res.data
  } catch { devices.value = [] }

  // 加载 HA 设备的变量统计
  for (const d of devices.value) {
    if (d.type === 'ha') {
      try {
        const vRes = await deviceApi.variables(d.id)
        const vars = vRes.data || []
        haVarCounts.value[d.id] = vars.length

        // 提取子设备名和图标
        const prefix = d.name + '.'
        const summary: Record<string, string> = {}
        const seen = new Set<string>()
        for (const v of vars) {
          const raw = v.key.startsWith(prefix) ? v.key.slice(prefix.length) : v.key
          // 尝试分离属性后缀
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
            // 找图标
            const propSuffix = raw.slice(devName.length)
            summary[devName] = HA_SUB_ICONS[propSuffix] || '📊'
          }
        }
        haSubDeviceSummary.value[d.id] = summary
      } catch { /* ignore */ }
    }
  }
}

let timer: ReturnType<typeof setInterval> | null = null

function startTimer(sec: number) {
  stopTimer()
  if (sec > 0) {
    timer = setInterval(loadData, sec * 1000)
  }
}

function stopTimer() {
  if (timer) { clearInterval(timer); timer = null }
}

watch(refreshInterval, startTimer, { immediate: true })

onMounted(() => loadData())
onUnmounted(() => stopTimer())
</script>

<style scoped>
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--gap-md);
}

/* ---- 设备卡片 ---- */
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
.dc-icon {
  font-size: 32px;
  flex-shrink: 0;
  line-height: 1;
}
.dc-identity {
  flex: 1;
  min-width: 0;
}
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

/* ---- 标签 ---- */
.dc-tags {
  display: flex;
  gap: 6px;
  margin-top: 12px;
  flex-wrap: wrap;
}

/* ---- 指标 ---- */
.dc-metrics {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dc-metric {
  display: flex;
  align-items: center;
  gap: 8px;
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
.dm-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.5s ease;
}
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

/* ---- 底部 ---- */
.dc-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}
.dc-uptime, .dc-heartbeat {
  font-size: 11px;
  color: var(--text-secondary);
}

.dc-status { display: flex; align-items: center; gap: 8px; }

/* HA 设备卡片 */
.dc-ha-summary {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}
.ha-var-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.ha-chip {
  font-size: 12px;
  background: var(--border-light);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.ha-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.timeout-tag {
  font-size: 11px;
  background: #FFF3E0; color: #E65100; padding: 2px 8px; border-radius: 10px;
  font-variant-numeric: tabular-nums; white-space: nowrap;
  font-weight: 500;
}
</style>
