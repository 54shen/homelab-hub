<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">历史记录</h1>
      <n-space>
        <n-button size="small" quaternary @click="exportCsv">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px" />
          导出 CSV
        </n-button>
      </n-space>
    </div>

    <!-- 筛选 -->
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
      <n-button size="small" quaternary @click="refresh">刷新</n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="items"
      :loading="loading"
      :bordered="false"
      size="small"
      :pagination="pagination"
      style="background:var(--bg-card);border-radius:var(--radius-lg)"
      @update:page="page = $event"
      @update:page-size="pageSize = $event; loadData()"
    />

    <n-empty v-if="!loading && items.length === 0" description="暂无历史记录" style="margin-top:60px" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NButton, NDataTable, NDatePicker, NEmpty, NInput, NSpace, useMessage
} from 'naive-ui'
import { historyApi } from '../api'
import { useFieldLabels } from '../composables/useFieldLabels'
import { useWebSocket } from '../composables/useWebSocket'
import type { KvHistory } from '../types'

const message = useMessage()
const { labelOf } = useFieldLabels()

const items = ref<KvHistory[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const searchKey = ref('')
const filterStart = ref<number | null>(null)
const filterEnd = ref<number | null>(null)
const seenKeys = new Set<string>()

const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  prefix: () => `共 ${total.value} 条`
}))

// ── 格式化音量 -1 → 🔇静音 ──
function fmtVol(val: string | null): string {
  if (val == null) return '(新增)'
  if (val === '-1') return '🔇 静音'
  return val
}

// ── 列定义 ──
const columns = [
  {
    title: '时间', key: 'changed_at', width: 160,
    render(row: KvHistory) { return row.changed_at || '—' }
  },
  {
    title: 'Key', key: 'key', width: 200, ellipsis: { tooltip: true },
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

// ── 加载 ──
function buildParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
  if (searchKey.value) params.search = searchKey.value
  if (filterStart.value) params.start = new Date(filterStart.value).toLocaleString('sv-SE').replace('T', ' ')
  if (filterEnd.value) params.end = new Date(filterEnd.value).toLocaleString('sv-SE').replace('T', ' ')
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await historyApi.list(buildParams())
    if (res.data) {
      items.value = res.data.items
      total.value = res.data.total
      seenKeys.clear()
      items.value.forEach(i => seenKeys.add(`${i.key}|${i.changed_at}`))
      console.log('[历史记录 API] 加载完成, 总数:', total.value,
        items.value.length > 0
          ? `最旧=${items.value[items.value.length - 1].changed_at} 最新=${items.value[0].changed_at}`
          : '空')
    }
  } catch { items.value = []; total.value = 0 }
  finally { loading.value = false }
}

function refresh() { page.value = 1; loadData() }

// ── 筛选变化 → 重载 ──
watch([searchKey, filterStart, filterEnd], () => { page.value = 1; loadData() })
watch(page, () => loadData())

// ── 导出 ──
async function exportCsv() {
  try {
    const res = await historyApi.exportCsv(buildParams())
    const blob = new Blob([res.data as BlobPart], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `history_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch { message.error('导出失败') }
}

// ── WS 实时 ──
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(() => {
  loadData()
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed') {
      // 如果页面有筛选条件或不在第一页，跳过实时插入
      if (searchKey.value || filterStart.value || filterEnd.value || page.value !== 1) return
      const id = `${data.key}|${data.changed_at}`
      if (seenKeys.has(id)) return
      seenKeys.add(id)
      const newItem: KvHistory = {
        id: -(Date.now() % 1000000),  // 负值确保与 DB 自增 ID 不冲突
        key: data.key,
        old_value: data.old_value ?? null,
        new_value: data.value,
        source: data.source || 'ws',
        retention_days: data.retention_days ?? 180,
        changed_at: data.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' ')
      }
      // 按时间倒序插入
      const ts = new Date(newItem.changed_at).getTime()
      console.log('[历史记录 WS] 新条目:', newItem.changed_at, 'ts:', ts)
      let idx = 0
      for (; idx < items.value.length; idx++) {
        if (new Date(items.value[idx].changed_at).getTime() < ts) break
      }
      console.log('[历史记录 WS] 插入位置:', idx, '/', items.value.length,
        '前5:', items.value.slice(0, 5).map((x: any) => `${x.changed_at} (${new Date(x.changed_at).getTime()})`))
      items.value.splice(idx, 0, newItem)
      total.value++
      // 保持 pageSize 限制
      if (items.value.length > pageSize.value) {
        const removed = items.value.pop()!
        seenKeys.delete(`${removed.key}|${removed.changed_at}`)
      }
    }
  })
})

onUnmounted(() => { cleanupWs?.() })
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
