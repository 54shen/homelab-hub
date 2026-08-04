<!-- ============================================================
     Shared Center — 变更动态(实时模式)
     初始通过 API 加载最近 20 条,之后全部由 WebSocket kv.changed
     实时推送续流;内存上限 1000 条,超出丢弃最旧
     搜索 / 时间筛选 / CSV 导出均为前端本地实现
     ============================================================ -->
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">变更动态</h1>
      <n-space>
        <span class="ws-status">
          <span class="dot"></span>实时监听中 · 已接收 {{ receivedCount }} 条 · 当前 {{ items.length }} 条
        </span>
        <n-button size="small" quaternary @click="clearItems">
          <ion-icon name="trash-outline" style="margin-right:4px;vertical-align:-2px" />
          清空
        </n-button>
        <n-button size="small" quaternary @click="exportCsv">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px" />
          导出 CSV
        </n-button>
      </n-space>
    </div>

    <!-- 前端本地筛选 -->
    <div class="filter-bar">
      <n-input
        v-model:value="searchKey"
        placeholder="搜索 Key..."
        clearable
        size="small"
        style="width:200px"
      />
      <n-date-picker
        v-model:value="filterStart"
        type="datetime"
        placeholder="开始时间"
        clearable
        size="small"
        style="width:170px"
      />
      <n-date-picker
        v-model:value="filterEnd"
        type="datetime"
        placeholder="结束时间"
        clearable
        size="small"
        style="width:170px"
      />
      <span class="local-note">初始加载最近 {{ INITIAL_COUNT }} 条 · 后续 WS 实时续流 · 上限 {{ MAX_ITEMS }} 条</span>
    </div>

    <!-- 每小时变量更新数折线图:时间筛选联动,拖到左边界自动向前扩展 -->
    <div v-if="chartPoints.length > 0" style="margin-bottom:12px">
      <TrendChart :points="chartPoints" title="每小时变量更新数" plot-kind="number" @reach-start="onChartReachStart" />
    </div>

    <n-data-table
      :columns="columns"
      :data="displayItems"
      :bordered="false"
      size="small"
      style="background:var(--bg-card);border-radius:var(--radius-lg)"
    >
      <!-- 空状态统一在表格内部,纯文字无图片 -->
      <template #empty>
        <span class="table-empty">{{ emptyText }}</span>
      </template>
    </n-data-table>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NButton, NDataTable, NDatePicker, NInput, NSpace, useMessage
} from 'naive-ui'
import { useFieldLabels } from '../composables/useFieldLabels'
import { useWebSocket } from '../composables/useWebSocket'
import { dashboardApi, historyApi } from '../api'
import TrendChart from '../components/TrendChart.vue'
import type { KvHistory, TrendPoint } from '../types'

const message = useMessage()
const { labelOf } = useFieldLabels()

// ---- 每小时变更数折线图:可查看超过 24h 的历史(拖动到左边界自动扩展) ----
// 时间筛选联动:筛了时间 → 图表按筛选范围加载;未筛 → 最近 24h,可向前扩展
const chartPoints = ref<TrendPoint[]>([])
const MAX_CHART_POINTS = 720  // 上限 30 天(小时点),超出丢最旧
let chartTimer: ReturnType<typeof setInterval> | null = null

function pad2(n: number): string { return String(n).padStart(2, '0') }
function hourKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}`
}
function fmtDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}
function nowStr(): string {
  return fmtDate(new Date())
}

// 按时间范围加载小时数据并补齐连续小时点(空小时补 0)
async function loadChart() {
  try {
    let start: string | undefined
    let end: string | undefined
    if (filterStart.value) start = fmtDate(new Date(filterStart.value))
    if (filterEnd.value) end = fmtDate(new Date(filterEnd.value))
    if (!start) {
      const d = new Date(Date.now() - 24 * 3600 * 1000)
      start = fmtDate(d)
    }
    const res = await historyApi.hourly({ start, end })
    const byHour = new Map((res.data ?? []).map(h => [h.hour, h.count]))
    // 补齐 start ~ end 的连续小时
    const points: TrendPoint[] = []
    const cur = new Date(start.replace(' ', 'T'))
    cur.setMinutes(0, 0, 0)
    const stop = new Date((end ?? nowStr()).replace(' ', 'T'))
    while (cur <= stop) {
      const hk = hourKey(cur)
      const count = byHour.get(hk) ?? 0
      points.push({ changed_at: `${hk}:00`, value: count, raw: `${count} 条` })
      cur.setHours(cur.getHours() + 1)
    }
    chartPoints.value = points
    console.log('[变更动态图表] 加载:', points.length, '点 | 首:', points[0]?.changed_at, '| 末:', points[points.length - 1]?.changed_at)
  } catch (e) {
    console.error('[变更动态图表] 加载失败:', e)
  }
}

// 拖动到左边界 → 再向前扩展 24h
const chartEarlierLoading = ref(false)

async function onChartReachStart() {
  if (chartEarlierLoading.value || chartPoints.value.length === 0) return
  const earliest = chartPoints.value[0].changed_at
  const endD = new Date(earliest.replace(' ', 'T'))
  endD.setSeconds(endD.getSeconds() - 1)
  const startD = new Date(endD)
  startD.setHours(startD.getHours() - 24)
  chartEarlierLoading.value = true
  try {
    const res = await historyApi.hourly({ start: fmtDate(startD), end: fmtDate(endD) })
    const byHour = new Map((res.data ?? []).map(h => [h.hour, h.count]))
    const pts: TrendPoint[] = []
    const cur = new Date(startD)
    cur.setMinutes(0, 0, 0)
    while (cur <= endD) {
      const hk = hourKey(cur)
      const count = byHour.get(hk) ?? 0
      pts.push({ changed_at: `${hk}:00`, value: count, raw: `${count} 条` })
      cur.setHours(cur.getHours() + 1)
    }
    if (pts.length === 0) {
      message.info('已到最早的数据,没有更早的记录')
    } else {
      chartPoints.value = [...pts, ...chartPoints.value]
      if (chartPoints.value.length > MAX_CHART_POINTS) {
        chartPoints.value = chartPoints.value.slice(-MAX_CHART_POINTS)
      }
      console.log('[变更动态图表] 向前扩展 24h:', pts.length, '点 | 总:', chartPoints.value.length)
    }
  } catch (e) {
    console.error('[变更动态图表] 扩展失败:', e)
  } finally {
    chartEarlierLoading.value = false
  }
}

// 每分钟轮询:刷新当前小时累计数,跨小时自动补新点(仅未筛时间时)
async function fetchMinuteCount() {
  if (filterStart.value || filterEnd.value) return  // 筛选了时间 → 图表静态
  const now = new Date()
  const hk = hourKey(now)
  try {
    const res = await historyApi.list({ start: `${hk}:00`, end: nowStr(), page: 1, page_size: 1 })
    const count = res.data?.total ?? 0
    const pts = chartPoints.value
    const last = pts[pts.length - 1]
    if (last && last.changed_at.startsWith(hk)) {
      // 同一小时:原地更新最后一点的累计数(deep watch 触发重绘)
      last.value = count
      last.raw = `${count} 条`
      console.log('[变更动态图表] 轮询刷新当前小时:', hk, '→', count, '条')
    } else {
      // 跨小时:追加新点,超出上限丢最旧
      pts.push({ changed_at: `${hk}:00`, value: count, raw: `${count} 条` })
      if (pts.length > MAX_CHART_POINTS) pts.shift()
      console.log('[变更动态图表] 跨小时追加新点:', hk, '→', count, '条 | 点数:', pts.length)
    }
  } catch (e) {
    console.error('[变更动态图表] 轮询失败:', e)
  }
}

// ---- 内存数据(初始 API 20 条,之后 WS 实时续流,时间倒序) ----
const items = ref<KvHistory[]>([])
const receivedCount = ref(0)   // WS 累计接收条数
const MAX_ITEMS = 1000         // 内存上限,超出丢弃最旧
const INITIAL_COUNT = 20       // 初始 API 拉取条数
const seenKeys = new Set<string>()

// ---- 初始加载最近 20 条(API),之后的变更全部走 WS ----
async function loadInitial() {
  try {
    const res = await dashboardApi.recentChanges(INITIAL_COUNT)
    if (!res.data || res.data.length === 0) return
    const rows: KvHistory[] = res.data.map(r => ({ ...r, retention_days: r.retention_days ?? 180 }))
    // 预填去重表:WS 到达的同一变更直接跳过
    rows.forEach(r => seenKeys.add(`${r.key}|${r.changed_at}`))
    items.value = rows
    const times = rows.map(r => r.changed_at)
    const sorted = [...times].sort().reverse()
    console.log('[变更动态] 初始 API 加载:', rows.length, '条 | 首行(最新):', times[0], '| 末行(最旧):', times[times.length - 1], '| 时间逆序正确:', JSON.stringify(times) === JSON.stringify(sorted))
  } catch (e) {
    console.error('[变更动态] 初始 API 加载失败(降级为纯 WS):', e)
  }
}

// 给每行生成唯一 key，避免 Naive UI 把 KV key 名当作行标识导致 duplicate key
interface RowItem extends KvHistory { kv_key: string }

// ---- 前端本地筛选 ----
const searchKey = ref('')
const filterStart = ref<number | null>(null)
const filterEnd = ref<number | null>(null)

function fmtTime(ts: number | null): string | null {
  if (!ts) return null
  return new Date(ts).toLocaleString('sv-SE').replace('T', ' ')
}

const filteredItems = computed<KvHistory[]>(() => {
  let list = items.value
  const q = searchKey.value.trim().toLowerCase()
  if (q) list = list.filter(i => i.key.toLowerCase().includes(q))
  const start = fmtTime(filterStart.value)
  if (start) list = list.filter(i => i.changed_at >= start)
  const end = fmtTime(filterEnd.value)
  if (end) list = list.filter(i => i.changed_at <= end)
  return list
})

// ---- 无分页:WS 数据持续追加,表格无限长 ----
const displayItems = computed<RowItem[]>(() =>
  filteredItems.value.map(item => ({
    ...item,
    kv_key: item.key,
    key: String(item.id)
  }))
)

// 空状态提示:未收到数据 / 有数据但筛选无匹配
const emptyText = computed(() =>
  items.value.length === 0
    ? '等待实时数据…(页面打开后, KV 变更会实时出现在这里)'
    : '无匹配记录'
)

// ---- 格式化音量 -1 → 🔇静音 ----
function fmtVol(val: string | null): string {
  if (val == null) return '(新增)'
  if (val === '-1') return '🔇 静音'
  return val
}

// ---- 列定义 ----
const columns = [
  {
    title: '时间', key: 'changed_at', width: 160,
    render(row: RowItem) { return row.changed_at || '—' }
  },
  {
    title: 'Key', key: 'kv_key', width: 200, ellipsis: { tooltip: true },
    render(row: RowItem) {
      const label = labelOf(row.kv_key)
      if (label === row.kv_key) return row.kv_key
      return h('span', { title: row.kv_key }, label)
    }
  },
  {
    title: '旧值 → 新值', key: 'change', width: 240,
    render(row: RowItem) {
      if (!row.old_value) {
        return h('span', { style: 'color:#10B981;font-size:12px' }, `(新增) → ${fmtVol(row.new_value)}`)
      }
      return [
        h('span', { style: 'color:#EF4444;text-decoration:line-through;font-size:12px' }, fmtVol(row.old_value)),
        h('span', { style: 'color:var(--text-secondary);margin:0 6px' }, '→'),
        h('span', { style: 'color:#10B981;font-weight:500;font-size:12px' }, fmtVol(row.new_value))
      ]
    }
  },
  { title: '来源', key: 'source', width: 120 }
]

// ---- WS 实时推送(唯一数据来源) ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

function insertItem(newItem: KvHistory) {
  const ts = new Date(newItem.changed_at).getTime()
  let idx = 0
  for (; idx < items.value.length; idx++) {
    if (new Date(items.value[idx].changed_at).getTime() < ts) break
  }
  items.value.splice(idx, 0, newItem)
  // 内存上限:超出丢弃最旧
  if (items.value.length > MAX_ITEMS) {
    const removed = items.value.pop()!
    console.log('[变更动态] 超上限淘汰最旧:', removed.changed_at, removed.key)
    seenKeys.delete(`${removed.key}|${removed.changed_at}`)
  }
}

onMounted(() => {
  loadInitial()
  // 初始按筛选范围加载小时分布 + 每分钟轮询刷新当前小时累计
  loadChart()
  fetchMinuteCount()
  chartTimer = setInterval(fetchMinuteCount, 60 * 1000)
  // 时间筛选变化 → 图表按筛选范围重新加载
  watch([filterStart, filterEnd], () => loadChart())
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed') {
      receivedCount.value++
      console.log('[变更动态] WS kv.changed 收到:', { key: data.key, value: data.value, old_value: data.old_value, source: data.source, changed_at: data.changed_at })
      const id = `${data.key}|${data.changed_at}`
      if (seenKeys.has(id)) {
        console.log('[变更动态] 与已有数据重复跳过:', id)
        return
      }
      seenKeys.add(id)
      insertItem({
        id: -(Date.now() % 1000000),  // 负值确保与 DB 自增 ID 不冲突
        key: data.key,
        old_value: data.old_value ?? null,
        new_value: data.value,
        source: data.source || 'ws',
        retention_days: data.retention_days ?? 180,
        changed_at: data.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' ')
      })
      console.log('[变更动态] 插入后:', items.value.length, '条 | 最新(第1行):', items.value[0]?.changed_at, '| 最旧(最后1行):', items.value[items.value.length - 1]?.changed_at)
    }
  })
})

onUnmounted(() => {
  cleanupWs?.()
  if (chartTimer) clearInterval(chartTimer)
  chartTimer = null
})

// ---- 本地操作 ----
function clearItems() {
  items.value = []
  seenKeys.clear()
}

function exportCsv() {
  const rows = filteredItems.value.map(r =>
    [r.id, r.key, r.old_value ?? '(新增)', r.new_value, r.source, r.changed_at]
  )
  const esc = (c: string | number) => `"${String(c ?? '').replace(/"/g, '""')}"`
  const csv = [
    '﻿ID,Key,Old Value,New Value,Source,Changed At',
    ...rows.map(r => r.map(esc).join(','))
  ].join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `history_live_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// 筛选为纯前端过滤(computed 自动生效),无需翻页逻辑
</script>

<style scoped>
.ws-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 10px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.25);
  border-radius: var(--radius-full);
}
.ws-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.local-note {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 4px;
}
.table-empty {
  color: var(--text-secondary);
  font-size: 13px;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
