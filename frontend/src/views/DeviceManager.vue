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
            <!-- 心跳超时 -->
            <input
              v-if="editingTimeoutId === d.id"
              ref="timeoutInputRef"
              v-model="timeoutInput"
              class="timeout-input"
              @keydown.enter="saveTimeout(d)"
              @blur="cancelTimeoutEdit"
              @click.stop
            />
            <span
              v-else
              class="timeout-tag"
              @click.stop="startTimeoutEdit(d)"
            >⏱{{ d.heartbeat_timeout || 180 }}s</span>
          </div>
        </div>

        <!-- 标签 -->
        <div class="dc-tags">
          <n-tag size="tiny" :bordered="false" round>{{ d.group || '默认' }}</n-tag>
          <n-tag size="tiny" :bordered="false" round type="info">{{ d.type }}</n-tag>
          <n-tag v-if="d.version" size="tiny" :bordered="false" round>v{{ d.version }}</n-tag>
        </div>

        <!-- 指标 -->
        <div v-if="d.online" class="dc-metrics">
          <div v-if="d.cpu !== undefined" class="dc-metric">
            <span class="dm-label">CPU</span>
            <div class="dm-bar"><div class="dm-fill cpu" :style="{ width: d.cpu + '%' }"></div></div>
            <span class="dm-val">{{ d.cpu }}%</span>
          </div>
          <div v-if="d.memory !== undefined" class="dc-metric">
            <span class="dm-label">MEM</span>
            <div class="dm-bar"><div class="dm-fill mem" :style="{ width: d.memory + '%' }"></div></div>
            <span class="dm-val">{{ d.memory }}%</span>
          </div>
          <div v-if="d.disk !== undefined" class="dc-metric">
            <span class="dm-label">DSK</span>
            <div class="dm-bar"><div class="dm-fill disk" :style="{ width: d.disk + '%' }"></div></div>
            <span class="dm-val">{{ d.disk }}%</span>
          </div>
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
  NButton, NButtonGroup, NDataTable, NEmpty, NInput, NSelect, NSpace, NTag, useMessage
} from 'naive-ui'
import StatusBadge from '../components/StatusBadge.vue'
import RefreshControl from '../components/RefreshControl.vue'
import { useRefreshInterval } from '../composables/useRefreshInterval'
import { deviceApi, kvApi } from '../api'
import type { Device } from '../types'

const timeoutInput = ref('')
const editingTimeoutId = ref<string | null>(null)
const timeoutInputRef = ref<HTMLInputElement | null>(null)
const message = useMessage()

function startTimeoutEdit(d: Device) {
  editingTimeoutId.value = d.id
  timeoutInput.value = String(d.heartbeat_timeout || 180)
  setTimeout(() => timeoutInputRef.value?.focus(), 50)
}

function cancelTimeoutEdit() {
  editingTimeoutId.value = null
}

async function saveTimeout(d: Device) {
  const num = parseInt(timeoutInput.value)
  if (!num || num < 1) { cancelTimeoutEdit(); return }
  try {
    const username = localStorage.getItem('sc_username') || 'admin'
    await kvApi.set({ key: `${d.name}.心跳超时`, value: String(num), type: 'int', source: `${username}(Web)` })
    d.heartbeat_timeout = num
    message.success(`${d.name} → ${num}s`)
    cancelTimeoutEdit()
    await loadData()
  } catch { message.error('保存失败') }
}

import { useUISetting } from '../composables/useUISetting'

const viewModeStr = useUISetting('device_view_mode', 'card')
const viewMode = computed<'card' | 'table'>({
  get: () => viewModeStr.value as 'card' | 'table',
  set: (v) => { viewModeStr.value = v }
})
const filterGroup = ref<string | null>(null)
const devices = ref<Device[]>([])
const refreshInterval = useRefreshInterval()

const groupFilterOptions = computed(() => {
  const groups = [...new Set(devices.value.map(d => d.group).filter(Boolean))]
  return groups.map(g => ({ label: g, value: g }))
})

const filteredDevices = computed(() => {
  if (!filterGroup.value) return devices.value
  return devices.value.filter(d => d.group === filterGroup.value)
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
      return h('span', { style: 'color:#E65100;font-weight:500;font-variant-numeric:tabular-nums' }, `${row.heartbeat_timeout || 180}s`)
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
    cloud: '☁️', docker: '🐳', vm: '📀', router: '📡'
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
.timeout-tag {
  font-size: 11px; color: var(--text-secondary); cursor: pointer;
  background: #FFF3E0; color: #E65100; padding: 2px 8px; border-radius: 10px;
  font-variant-numeric: tabular-nums; white-space: nowrap;
  transition: all 0.15s; font-weight: 500;
}
.timeout-tag:hover { background: #FFE0B2; }
.timeout-input {
  width: 52px; font-size: 11px; padding: 2px 6px; background: #FFF3E0; color: #E65100;
  border: 1px solid var(--color-primary); border-radius: 8px;
  text-align: center; outline: none; background: #fff; color: var(--text-primary);
}
</style>
