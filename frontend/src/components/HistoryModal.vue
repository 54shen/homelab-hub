<template>
  <n-modal
    :show="show"
    preset="card"
    :title="`📋 ${titleLabel} 的历史`"
    size="huge"
    style="max-width:900px"
    @update:show="$emit('update:show', $event)"
  >
    <!-- 工具栏 -->
    <div class="hm-toolbar">
      <n-space>
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
        <n-button size="small" quaternary @click="exportCsv">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px" />
          导出 CSV
        </n-button>
      </n-space>
      <div style="display:flex;align-items:center;gap:12px">
        <span
          v-if="newCount > 0 && hasFilter"
          class="hm-badge"
          @click="refresh"
        >有 {{ newCount }} 条新变更，点击刷新</span>
        <span class="hm-total">共 {{ total }} 条</span>
      </div>
    </div>

    <!-- 趋势图:可绘图格式(数值/时长/时间戳)时显示,WS 新数据实时更新 -->
    <div v-if="chartable" class="hm-chart">
      <TrendChart :points="trendPoints" :title="`${titleLabel} 趋势`" :plot-kind="plotKind" />
    </div>

    <!-- 表格 -->
    <n-data-table
      :columns="columns"
      :data="items"
      :loading="loading"
      :bordered="false"
      size="small"
      :row-key="rowKey"
      :pagination="pagination"
      @update:page="page = $event"
      @update:page-size="pageSize = $event; loadData()"
    />

    <n-empty v-if="!loading && items.length === 0" description="暂无历史记录" style="margin-top:40px" />
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onUnmounted, ref, watch } from 'vue'
import { NButton, NDataTable, NDatePicker, NEmpty, NModal, NSpace } from 'naive-ui'
import { historyApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import { useFieldLabels } from '../composables/useFieldLabels'
import TrendChart from './TrendChart.vue'
import type { KvHistory, TrendPoint } from '../types'

const props = defineProps<{ show: boolean; keyProp: string }>()
defineEmits<{ 'update:show': [value: boolean] }>()
const { labelOf } = useFieldLabels()

// 字段映射后的标题(悬停显示原始 key)
const titleLabel = computed(() => {
  const label = labelOf(props.keyProp)
  return label === props.keyProp ? props.keyProp : label
})

function rowKey(row: KvHistory): number { return row.id }

// ---- 数据 ----
const items = ref<KvHistory[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filterStart = ref<number | null>(null)
const filterEnd = ref<number | null>(null)
const newCount = ref(0)
const seenKeys = new Set<string>()  // 追踪已显示的 key+changed_at，防止重复
const hasFilter = computed(() => !!(filterStart.value || filterEnd.value))

// ---- 趋势图 ----
const trendPoints = ref<TrendPoint[]>([])
const plotKind = ref('')
const chartable = computed(() => Boolean(plotKind.value) && trendPoints.value.length > 0)

// 解析值为可绘图数值(与后端 _parse_value 规则一致:数值/时长/时间戳)
function parsePlotValue(v: unknown): { kind: string; value: number } | null {
  if (v == null) return null
  const s = String(v).trim()
  if (s === '') return null
  // 纯数值(严格匹配,避免 '17h' 被 Number 误判)
  if (/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(s)) return { kind: 'number', value: Number(s) }
  // 时长:Nd Xh Ym Zs
  const dm = s.match(/^(?:(\d+)d\s*)?(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s\s*)?$/)
  if (dm && (dm[1] || dm[2] || dm[3] || dm[4])) {
    const secs = (parseInt(dm[1] || '0', 10) * 86400)
      + (parseInt(dm[2] || '0', 10) * 3600)
      + (parseInt(dm[3] || '0', 10) * 60)
      + parseInt(dm[4] || '0', 10)
    return { kind: 'duration', value: secs }
  }
  // 时间戳
  const tm = s.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?$/)
  if (tm) {
    const ts = new Date(`${tm[1]}T${tm[2]}`).getTime() / 1000
    if (Number.isFinite(ts)) return { kind: 'timestamp', value: ts }
  }
  return null
}

async function loadTrend() {
  trendPoints.value = []
  plotKind.value = ''
  try {
    const params: { key: string; limit: number; start?: string; end?: string } = { key: props.keyProp, limit: 5000 }
    // 未特意筛选时间时,默认只取最近 24 小时(避免全量传输)
    if (filterStart.value) {
      params.start = new Date(filterStart.value).toLocaleString('sv-SE').replace('T', ' ')
    } else {
      const d = new Date(Date.now() - 24 * 3600 * 1000)
      const p = (n: number) => String(n).padStart(2, '0')
      params.start = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
    }
    if (filterEnd.value) params.end = new Date(filterEnd.value).toLocaleString('sv-SE').replace('T', ' ')
    const res = await historyApi.trend(params)
    if (res.data) {
      trendPoints.value = res.data.points
      plotKind.value = res.data.kind || ''
    }
  } catch { /* 无趋势数据 */ }
}

const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  prefix: () => `共 ${total.value} 条`
}))

// ---- 格式化：系统音量的 -1 显示为 🔇 静音 ----
function formatVolVal(val: string | null): string {
  if (val == null) return '(新增)'
  if ((props.keyProp?.endsWith('.volume') || props.keyProp?.endsWith('volume')) && val === '-1') return '🔇 静音'
  return val
}

// ---- 列定义 ----
const columns = [
  {
    title: '时间', key: 'changed_at', width: 160,
    render(row: KvHistory) { return row.changed_at || '—' }
  },
  {
    title: 'Key', key: 'key', width: 180, ellipsis: { tooltip: true },
    render(row: KvHistory) {
      const label = labelOf(row.key)
      if (label === row.key) return row.key
      return h('span', { title: row.key }, label)
    }
  },
  {
    title: '旧值 → 新值', key: 'change', width: 240,
    render(row: KvHistory) {
      if (!row.old_value) {
        return h('span', { style: 'color:#10B981;font-size:12px' }, `(新增) → ${formatVolVal(row.new_value)}`)
      }
      return [
        h('span', { style: 'color:#EF4444;text-decoration:line-through;font-size:12px' }, formatVolVal(row.old_value)),
        h('span', { style: 'color:var(--text-secondary);margin:0 6px' }, '→'),
        h('span', { style: 'color:#10B981;font-weight:500;font-size:12px' }, formatVolVal(row.new_value))
      ]
    }
  },
  { title: '来源', key: 'source', width: 120 }
]

// ---- 加载 ----
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      key: props.keyProp,
      page: page.value,
      page_size: pageSize.value
    }
    if (filterStart.value) {
      params.start = new Date(filterStart.value).toLocaleString('sv-SE').replace('T', ' ')
    }
    if (filterEnd.value) {
      params.end = new Date(filterEnd.value).toLocaleString('sv-SE').replace('T', ' ')
    }
    const res = await historyApi.list(params)
    if (res.data) {
      items.value = res.data.items
      total.value = res.data.total
      seenKeys.clear()
      items.value.forEach(i => seenKeys.add(`${i.key}|${i.changed_at}`))
      console.log('[History API] 加载完成, 总数:', total.value, '首页时间范围:',
        items.value.length > 0
          ? `最旧=${items.value[items.value.length-1].changed_at} 最新=${items.value[0].changed_at}`
          : '空')
    }
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function refresh() {
  newCount.value = 0
  page.value = 1
  loadData()
  loadTrend()
}

// ---- 导出 ----
async function exportCsv() {
  try {
    const params: Record<string, unknown> = { key: props.keyProp }
    if (filterStart.value) params.start = new Date(filterStart.value).toLocaleString('sv-SE').replace('T', ' ')
    if (filterEnd.value) params.end = new Date(filterEnd.value).toLocaleString('sv-SE').replace('T', ' ')
    const res = await historyApi.exportCsv(params)
    const blob = new Blob([res.data as BlobPart], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `history_${props.keyProp}_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch { /* */ }
}

// ---- watch 筛选条件 & 翻页 ----
watch([filterStart, filterEnd], () => { page.value = 1; refresh() })
watch(page, () => loadData())  // 翻页时重新请求

// ---- WS 实时 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

watch(() => props.show, (visible) => {
  if (visible) {
    page.value = 1
    filterStart.value = null
    filterEnd.value = null
    newCount.value = 0
    loadData()
    loadTrend()
    // 注册 WS 监听
    cleanupWs = on((event, data: any) => {
      if (event === 'kv.changed' && data.key === props.keyProp) {
        if (hasFilter.value || page.value !== 1) {
          newCount.value++
        } else {
          const id = `${data.key}|${data.changed_at}`
          if (seenKeys.has(id)) return  // 已存在，跳过
          seenKeys.add(id)
          const newItem = {
            id: -(Date.now() % 1000000),
            key: data.key,
            old_value: data.old_value ?? null,
            new_value: data.value,
            source: data.source || 'ws',
            retention_days: data.retention_days ?? 180,
            changed_at: data.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' ')
          }
          // 按时间倒序插入到正确位置
          const ts = new Date(newItem.changed_at).getTime()
          console.log('[History WS] 新条目:', newItem.changed_at, 'ts:', ts)
          let idx = 0
          for (; idx < items.value.length; idx++) {
            const existing = (items.value[idx] as any).changed_at
            const existingTs = new Date(existing).getTime()
            if (existingTs < ts) break
          }
          console.log('[History WS] 插入位置:', idx, '/', items.value.length, '当前列表:',
            items.value.slice(0, 5).map((x: any) => `${x.changed_at} (${new Date(x.changed_at).getTime()})`))
          items.value.splice(idx, 0, newItem)
          if (items.value.length > pageSize.value) {
            const removed = items.value.pop()!
            seenKeys.delete(`${removed.key}|${removed.changed_at}`)
          }
          // total 不递增 — 保持服务端权威计数
        }
        // 趋势图实时更新:解析新值为数值点插入(时间升序,按 changed_at 去重)
        const parsed = parsePlotValue(data.value)
        if (parsed && parsed.kind === plotKind.value) {
          const pts = trendPoints.value
          const ts = new Date(data.changed_at).getTime()
          if (!pts.some(p => new Date(p.changed_at).getTime() === ts)) {
            let i = 0
            for (; i < pts.length; i++) {
              if (new Date(pts[i].changed_at).getTime() > ts) break
            }
            pts.splice(i, 0, {
              changed_at: data.changed_at,
              value: parsed.value,
              raw: String(data.value),
            })
          }
        }
      }
    })
  } else {
    // 弹窗关闭 → 清理 WS
    cleanupWs?.()
    cleanupWs = null
  }
})

onUnmounted(() => {
  cleanupWs?.()
})
</script>

<style scoped>
.hm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.hm-total {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.hm-chart { margin-bottom: 12px; }
.hm-badge {
  font-size: 12px;
  background: #FFF3E0;
  color: #E65100;
  padding: 4px 12px;
  border-radius: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}
.hm-badge:hover {
  background: #FFE0B2;
}
</style>
