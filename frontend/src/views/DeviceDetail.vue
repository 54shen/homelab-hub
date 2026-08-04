<template>
  <div class="page-container">
    <div class="back-row">
      <n-button text @click="$router.push('/devices')">
        <ion-icon name="arrow-back-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
        返回设备列表
      </n-button>
    </div>

    <n-spin :show="loading">
      <template v-if="device">
        <!-- 设备头部 -->
        <div class="detail-hero">
          <div class="hero-left">
            <span class="hero-icon">{{ iconForType(device.type) }}</span>
            <div>
              <h1 class="hero-name">{{ device.name }}</h1>
              <p class="hero-sub">{{ device.hostname || device.id }}</p>
            </div>
            <StatusBadge :online="device.online" style="margin-left:12px" />
            <span
              v-if="editingTimeout"
              class="timeout-tag"
              @click.stop
            >⏱<input
              ref="timeoutInputRef"
              v-model="timeoutInput"
              class="timeout-input-inline"
              @keydown.enter="saveTimeout()"
              @blur="editingTimeout = false"
            />s</span>
            <span
              v-else
              class="timeout-tag"
              @click.stop="startTimeoutEdit()"
            >⏱{{ device.heartbeat_timeout }}s</span>
          </div>
          <div style="display:flex;align-items:center;gap:12px">
            <n-tag size="small" :bordered="false" round>{{ device.group || '默认' }}</n-tag>
            <n-popconfirm
              @positive-click="deleteDevice"
              positive-text="确认删除"
              negative-text="取消"
            >
              <template #trigger>
                <n-button type="error" size="small" ghost>🗑 删除设备</n-button>
              </template>
              确定要删除设备 "{{ device.name }}" 吗？此操作不可撤销。
            </n-popconfirm>
          </div>
        </div>

        <!-- ======== HA 设备：子设备卡片视图 ======== -->
        <div v-if="device.type === 'ha'" style="margin-top:16px">
          <div v-if="subDevices.length === 0" style="text-align:center;padding:40px;color:var(--text-secondary)">
            暂无子设备数据 — 请确保 HA 自动化已正确配置
          </div>
          <div v-else class="subdevice-grid">
            <div v-for="sd in subDevices" :key="sd.name" class="subdevice-card">
              <div class="sd-header">
                <span class="sd-icon">{{ sd.icon }}</span>
                <span class="sd-name">{{ sd.name }}</span>
              </div>
              <div class="sd-props">
                <div v-for="p in sd.properties" :key="p.key" class="sd-prop">
                  <span class="sd-prop-label">{{ p.label }}</span>
                  <span
                    class="sd-prop-value"
                    :class="{ clickable: true, 'state-on': p.value === 'on', 'state-off': p.value === 'off' }"
                    @click.stop="openHistory(p.key)"
                  >
                    {{ p.display }}
                  </span>
                </div>
              </div>
              <div class="sd-footer">
                <span class="sd-time">{{ sd.updatedAt }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ======== 普通设备：资源指标 ======== -->
        <div v-if="device.type !== 'ha' && device.online" class="card-grid" style="margin-top:16px">
          <n-card size="small" title="CPU" class="metric-clickable" @click="openHistory(device.name + '.cpu')">
            <div class="metric-big">{{ device.cpu ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.cpu ?? 0" :color="device.cpu && device.cpu > 80 ? '#EF4444' : '#5B8DEF'" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="内存" class="metric-clickable" @click="openHistory(device.name + '.memory')">
            <div class="metric-big">{{ device.memory ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.memory ?? 0" color="#22C55E" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="磁盘" class="metric-clickable" @click="openHistory(device.name + '.disk')">
            <div class="metric-big">{{ device.disk ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.disk ?? 0" color="#F59E0B" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="音量" class="metric-clickable" @click="openHistory(device.name + '.volume')">
            <div class="metric-big">{{ (device.volume ?? 0) < 0 ? '🔇' : ((device.volume ?? '—') + '%') }}</div>
            <n-progress type="line" :percentage="(device.volume ?? 0) < 0 ? 0 : (device.volume ?? 0)" :color="(device.volume ?? 0) < 0 ? '#9CA3AF' : '#A855F7'" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="运行时长">
            <div class="metric-big-text">{{ device.uptime || '—' }}</div>
          </n-card>
        </div>

        <!-- ======== 普通设备：信息详情 ======== -->
        <div v-if="device.type !== 'ha'" class="card-grid-2" style="margin-top:16px">
          <n-card size="small" title="基本信息">
            <n-descriptions label-placement="left" :column="1" bordered size="small">
              <n-descriptions-item label="设备 ID">{{ device.id }}</n-descriptions-item>
              <n-descriptions-item label="名称">{{ device.name }}</n-descriptions-item>
              <n-descriptions-item label="主机名">{{ device.hostname || '—' }}</n-descriptions-item>
              <n-descriptions-item label="IP 地址">{{ device.ip || '—' }}</n-descriptions-item>
              <n-descriptions-item label="MAC 地址">{{ device.mac || '—' }}</n-descriptions-item>
              <n-descriptions-item label="操作系统">{{ device.os || '—' }}</n-descriptions-item>
            </n-descriptions>
          </n-card>
          <n-card size="small" title="运行信息">
            <n-descriptions label-placement="left" :column="1" bordered size="small">
              <n-descriptions-item label="类型">{{ device.type }}</n-descriptions-item>
              <n-descriptions-item label="分组">{{ device.group || '默认' }}</n-descriptions-item>
              <n-descriptions-item label="版本">v{{ device.version }}</n-descriptions-item>
              <n-descriptions-item label="注册时间">{{ device.registered_at || '—' }}</n-descriptions-item>
              <n-descriptions-item label="最后心跳">{{ device.last_heartbeat || '—' }}</n-descriptions-item>
              <n-descriptions-item label="备注">{{ device.notes || '无' }}</n-descriptions-item>
            </n-descriptions>
          </n-card>
        </div>

        <!-- 设备变量 -->
        <n-card title="设备变量" size="small" style="margin-top:16px">
          <template #header-extra>
            <span style="font-size:12px;color:var(--text-secondary)">{{ variables.length }} 个</span>
          </template>
          <n-empty v-if="variables.length === 0" description="该设备暂无变量数据" />
          <n-data-table v-else :columns="varColumns" :data="variables" :bordered="false" size="small" />
        </n-card>

        <!-- 历史记录弹窗 -->
        <HistoryModal v-model:show="showHistory" :key-prop="historyKey" />

        <!-- ======== 普通设备：心跳历史 ======== -->
        <n-card v-if="device.type !== 'ha'" title="心跳历史" size="small" style="margin-top:16px">
          <div ref="heartbeatChartRef" class="chart-box"></div>
        </n-card>
      </template>

      <n-empty v-else-if="!loading" description="设备不存在" style="margin-top:80px" />
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem,
  NEmpty, NPopconfirm, NProgress, NSpin, NTag, useMessage
} from 'naive-ui'
import * as echarts from 'echarts'
import StatusBadge from '../components/StatusBadge.vue'
import HistoryModal from '../components/HistoryModal.vue'
import { deviceApi, kvApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import { useFieldLabels } from '../composables/useFieldLabels'
import type { Device, KvEntry } from '../types'

const route = useRoute()
const router = useRouter()
const { labelOf } = useFieldLabels()
const deviceId = route.params.id as string

const loading = ref(true)
const device = ref<Device | null>(null)
const variables = ref<KvEntry[]>([])
const showHistory = ref(false)
const historyKey = ref('')
const heartbeatChartRef = ref<HTMLElement | null>(null)
let hbChart: echarts.ECharts | null = null
let cleanupWs: (() => void) | null = null
const cpuHistory = ref<[string, number][]>([])
const memHistory = ref<[string, number][]>([])

function updateChart() {
  if (!hbChart) return
  hbChart.setOption({
    xAxis: { data: cpuHistory.value.map(v => v[0]) },
    series: [
      { name: 'CPU', data: cpuHistory.value.map(v => v[1]) },
      { name: '内存', data: memHistory.value.map(v => v[1]) }
    ]
  })
}

// ---- 设备变量编辑 ----
const editingVarKey = ref<string | null>(null)
const editValue = ref('')

function startEdit(row: KvEntry) {
  editingVarKey.value = row.key
  editValue.value = row.value
  nextTick(() => {
    const input = document.querySelector<HTMLInputElement>('.var-edit-input')
    input?.focus()
    input?.select()
  })
}

async function saveEdit(row: KvEntry) {
  if (!editingVarKey.value) return
  const newVal = editValue.value
  editingVarKey.value = null
  if (newVal === row.value) return  // 未改动
  try {
    const username = localStorage.getItem('sc_username') || 'admin'
    await kvApi.set({ key: row.key, value: newVal, type: row.type, source: `${username}(Web)` })
    row.value = newVal
    row.updated_at = new Date().toLocaleString('sv-SE').replace('T', ' ')
    message.success('已修改')
  } catch { message.error('修改失败') }
}

function cancelEdit() {
  editingVarKey.value = null
}

async function deleteVar(key: string) {
  try {
    await kvApi.delete(key)
    variables.value = variables.value.filter(v => v.key !== key)
    message.success('已删除')
  } catch { message.error('删除失败') }
}

const varColumns = [
  {
    title: 'Key', key: 'key', width: 180, ellipsis: { tooltip: true },
    render(row: KvEntry) {
      const label = labelOf(row.key)
      const text = label === row.key ? row.key : label
      // 点击 key 直接弹窗查看历史
      return h('span', {
        class: 'key-link',
        title: `${row.key} (点击查看历史)`,
        onClick: () => { historyKey.value = row.key; showHistory.value = true }
      }, text)
    }
  },
  {
    title: 'Value', key: 'value', width: 160,
    render(row: KvEntry) {
      if (editingVarKey.value === row.key) {
        return h('input', {
          class: 'var-edit-input',
          value: editValue.value,
          onInput: (e: Event) => { editValue.value = (e.target as HTMLInputElement).value },
          onKeydown: (e: KeyboardEvent) => {
            if (e.key === 'Enter') saveEdit(row)
            if (e.key === 'Escape') cancelEdit()
          },
          onBlur: () => cancelEdit(),
          style: 'width:100%;padding:2px 6px;border:1px solid #5B8DEF;border-radius:4px;font-size:12px;outline:none;background:var(--bg-card)'
        })
      }
      return row.value
    }
  },
  { title: '类型', key: 'type', width: 70 },
  { title: '更新时间', key: 'updated_at', width: 150 },
  {
    title: '操作', key: 'actions', width: 130,
    render(row: KvEntry) {
      if (editingVarKey.value === row.key) {
        return h('span', { style: 'font-size:12px;color:var(--text-secondary)' }, 'Enter 保存')
      }
      return h('span', { style: 'display:flex;gap:4px' }, [
        // 历史(最常用)放在修改前面
        h(NButton, { size: 'tiny', quaternary: true,
          onClick: () => { historyKey.value = row.key; showHistory.value = true }
        }, { default: () => '历史' }),
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => startEdit(row) }, { default: () => '修改' }),
        h(NPopconfirm, {
          positiveText: '确认', negativeText: '取消',
          onPositiveClick: () => deleteVar(row.key)
        }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, style: 'color:#EF4444' }, { default: () => '删除' }),
          default: () => `确定要删除变量 "${row.key}" 吗？`
        })
      ])
    }
  }
]

function iconForType(type: string): string {
  const map: Record<string, string> = {
    computer: '🖥️', server: '📦', nas: '💾', iot: '🏠',
    cloud: '☁️', docker: '🐳', vm: '📀', router: '📡',
    ha: '🏠'
  }
  return map[type] || '📡'
}

// ---- HA 子设备分组 ----

interface SubDeviceProp {
  key: string
  label: string
  value: string
  display: string
}

interface SubDevice {
  name: string
  icon: string
  properties: SubDeviceProp[]
  updatedAt: string
}

// 常见属性后缀→用于从变量名中剥离属性部分，得到设备名
const PROP_SUFFIXES = [
  '设置温度', '当前温度', '目标温度', '目标湿度',
  '开关', '状态', '功率', '温度', '湿度', '浓度',
  '位置', '亮度', '电量', '模式', '风速', '速度',
  '质量', '等级', '人数', '距离', '剩余',
]

function splitDeviceAndProp(name: string): { device: string; prop: string } {
  for (const s of PROP_SUFFIXES) {
    if (name.endsWith(s) && name.length > s.length) {
      return { device: name.slice(0, -s.length), prop: s }
    }
  }
  return { device: name, prop: '' }
}

const SUB_DEVICE_ICONS: Record<string, string> = {
  开关: '🔘', 状态: '📋', 功率: '⚡', 温度: '🌡️', 设置温度: '🌡️',
  当前温度: '🌡️', 湿度: '💧', 浓度: '🌿', 质量: '🌿', 位置: '📍',
  亮度: '💡', 电量: '🔋', 模式: '⚙️', 风速: '💨', 速度: '💨',
  等级: '📊', 开关状态: '🔘',
}

const subDevices = computed<SubDevice[]>(() => {
  if (!device.value || device.value.type !== 'ha') return []

  const prefix = device.value.name + '.'
  const vars = variables.value.filter(v => v.key.startsWith(prefix))

  // 按设备名分组
  const groups: Record<string, { props: SubDeviceProp[]; updatedAt: string }> = {}

  for (const v of vars) {
    const rawName = v.key.slice(prefix.length)  // "显示器开关"
    const { device: devName, prop } = splitDeviceAndProp(rawName)

    if (!groups[devName]) {
      groups[devName] = { props: [], updatedAt: v.updated_at }
    }
    if (v.updated_at > groups[devName].updatedAt) {
      groups[devName].updatedAt = v.updated_at
    }

    const isOnOff = v.value === 'on' || v.value === 'off'
    groups[devName].props.push({
      key: v.key,
      label: prop || rawName,
      value: v.value,
      display: isOnOff ? (v.value === 'on' ? '已开启' : '已关闭') : v.value
    })
  }

  // 转为 SubDevice 数组
  return Object.entries(groups).map(([name, g]) => {
    // 找主属性决定图标（优先开关/状态）
    const mainProp = g.props.find(p => p.label === '开关' || p.label === '状态') || g.props[0]
    const icon = SUB_DEVICE_ICONS[mainProp?.label || ''] || '📊'

    const formatTime = (ts: string) => {
      if (!ts) return ''
      const d = new Date(ts)
      const now = new Date()
      const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
      if (diffMin < 1) return '刚刚'
      if (diffMin < 60) return `${diffMin} 分钟前`
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }

    return { name, icon, properties: g.props, updatedAt: formatTime(g.updatedAt) }
  })
})

const message = useMessage()
const timeoutInput = ref('')
const editingTimeout = ref(false)
const timeoutInputRef = ref<HTMLInputElement | null>(null)

function startTimeoutEdit() {
  editingTimeout.value = true
  timeoutInput.value = device.value?.heartbeat_timeout != null ? String(device.value.heartbeat_timeout) : ''
  setTimeout(() => timeoutInputRef.value?.focus(), 50)
}

async function saveTimeout() {
  const num = parseInt(timeoutInput.value)
  if (!num || num < 1 || !device.value) { editingTimeout.value = false; return }
  try {
    const username = localStorage.getItem('sc_username') || 'admin'
    await kvApi.set({ key: `${device.value.name}.心跳超时`, value: String(num), type: 'int', source: `${username}(Web)` })
    device.value.heartbeat_timeout = num
    message.success(`${device.value.name} → ${num}s`)
  } catch { message.error('保存失败') }
  editingTimeout.value = false
}

function openHistory(key: string) {
  historyKey.value = key
  showHistory.value = true
}

async function deleteDevice() {
  if (!device.value) return
  try {
    await deviceApi.unregister(device.value.id)
    message.success('设备已删除')
    router.push('/devices')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}

async function loadData() {
  loading.value = true
  try {
    const [dRes, vRes] = await Promise.all([
      deviceApi.get(deviceId),
      deviceApi.variables(deviceId)
    ])
    if (dRes.data) {
      device.value = dRes.data
    }
    if (vRes.data) {
      variables.value = vRes.data
    }
  } catch {
    device.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadData()
  await nextTick()
  if (heartbeatChartRef.value) {
    hbChart = echarts.init(heartbeatChartRef.value)
    hbChart.setOption({
      tooltip: { trigger: 'axis' as const },
      legend: { data: ['CPU', '内存'], top: 0, right: 0, textStyle: { fontSize: 11 } },
      grid: { top: 12, right: 50, bottom: 24, left: 40, containLabel: true },
      xAxis: { type: 'category' as const, data: [], axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value' as const, max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
      series: [
        {
          name: 'CPU', data: [], type: 'line' as const, smooth: true, symbol: 'none' as const,
          lineStyle: { color: '#5B8DEF', width: 2 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#5B8DEF30' }, { offset: 1, color: '#5B8DEF04' }]) }
        },
        {
          name: '内存', data: [], type: 'line' as const, smooth: true, symbol: 'none' as const,
          lineStyle: { color: '#22C55E', width: 2 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#22C55E30' }, { offset: 1, color: '#22C55E04' }]) }
        }
      ]
    })
    updateChart()
  }
  // WebSocket 实时更新 — 首次 API 后全部走 WS
  const { on } = useWebSocket()
  cleanupWs = on((event, data: any) => {
    if (!device.value) return

    const devName = device.value.name
    const nowStr = new Date().toLocaleString('sv-SE').replace('T', ' ')

    // ---- 辅助：同步心跳字段到变量表 ----
    function syncVar(suffix: string, value: string | number | null | undefined) {
      if (value === null || value === undefined) return
      const key = devName + '.' + suffix
      const v = variables.value.find(v => v.key === key)
      if (v) { v.value = String(value); v.updated_at = nowStr }
    }

    // ========== 1. 心跳 — 驱动整个页面 ==========
    if (event === 'device.heartbeat' && data.name === devName) {
      // 图表
      const ts = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      if (data.cpu != null) { cpuHistory.value.push([ts, data.cpu]); if (cpuHistory.value.length > 30) cpuHistory.value.shift() }
      if (data.memory != null) { memHistory.value.push([ts, data.memory]); if (memHistory.value.length > 30) memHistory.value.shift() }
      updateChart()

      // 设备对象 — 指标卡 + 基本信息 + 运行信息
      if (data.cpu != null) device.value.cpu = data.cpu
      if (data.memory != null) device.value.memory = data.memory
      if (data.disk != null) device.value.disk = data.disk
      if (data.volume != null) device.value.volume = data.volume
      if (data.uptime) device.value.uptime = data.uptime
      if (data.ip) device.value.ip = data.ip
      device.value.online = data.online
      device.value.last_heartbeat = nowStr

      // 变量表 — 同步心跳字段
      syncVar('uptime', data.uptime)
      syncVar('cpu', data.cpu)
      syncVar('memory', data.memory)
      syncVar('disk', data.disk)
      syncVar('volume', data.volume)
      syncVar('ip', data.ip)
    }

    // ========== 2. KV 变更 — 补刀心跳没覆盖的变量 ==========
    if (event === 'kv.changed') {
      const prefix = devName + '.'
      if (data.key.startsWith(prefix)) {
        const existing = variables.value.find(v => v.key === data.key)
        if (existing) {
          existing.value = data.value
          existing.updated_at = data.changed_at || nowStr
        } else {
          variables.value.unshift({
            id: 0,
            key: data.key,
            value: data.value,
            type: 'string',
            source: data.source || 'ws',
            updated_at: data.changed_at || nowStr,
            expire_seconds: null,
            retention_days: 180
          })
        }
      }
    }
  })
})

function onResize() { hbChart?.resize() }
window.addEventListener('resize', onResize)

onUnmounted(() => {
  cleanupWs?.()
  window.removeEventListener('resize', onResize)
  hbChart?.dispose()
})
</script>

<style scoped>
.back-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--gap-md); }
.chart-box { width: 100%; height: 220px; overflow: hidden; }
.timeout-tag {
  font-size: 12px; color: var(--text-secondary); cursor: pointer;
  background: #FFF3E0; color: #E65100; padding: 3px 10px; border-radius: 12px;
  font-variant-numeric: tabular-nums; white-space: nowrap;
  transition: all 0.15s; font-weight: 500;
}
.timeout-tag:hover { background: #FFE0B2; }
.timeout-input-inline {
  width: 48px; font-size: 12px; padding: 0 4px;
  border: none; border-bottom: 1.5px dashed #E65100;
  border-radius: 4px;
  text-align: center; outline: none;
  background: rgba(255,255,255,0.6); color: #E65100;
  font-weight: 500; font-family: inherit;
}
.detail-hero {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg-card); border: 1px solid var(--border-card);
  border-radius: var(--radius-lg); padding: 20px 24px;
  box-shadow: var(--shadow-card);
}
.hero-left { display: flex; align-items: center; gap: 14px; }
.hero-icon { font-size: 40px; }
.hero-name { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.hero-sub { font-size: 13px; color: var(--text-secondary); font-family: monospace; margin-top: 2px; }

.metric-clickable { cursor: pointer; }
.metric-big { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.metric-big .unit { font-size: 16px; font-weight: 400; color: var(--text-secondary); margin-left: 2px; }
.metric-big-text { font-size: 20px; font-weight: 600; color: var(--text-primary); }

/* ---- HA 子设备卡片 ---- */
.subdevice-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.subdevice-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}
.subdevice-card:hover {
  box-shadow: var(--shadow-card-hover);
}
.sd-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.sd-icon { font-size: 24px; }
.sd-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.sd-props {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sd-prop {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sd-prop-label {
  font-size: 12px;
  color: var(--text-secondary);
}
.sd-prop-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.sd-prop-value.clickable {
  cursor: pointer;
  padding: 1px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}
.sd-prop-value.clickable:hover {
  background: var(--border-light);
}
.sd-prop-value.state-on {
  color: #22C55E;
}
.sd-prop-value.state-off {
  color: #9CA3AF;
}
.sd-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}
.sd-time {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
