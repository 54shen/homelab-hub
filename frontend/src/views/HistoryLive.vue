<!-- ============================================================
     Shared Center — 变更动态(实时模式)
     不通过 API 请求任何数据 —— 全部由 WebSocket kv.changed 实时推送
     搜索 / 时间筛选 / 分页 / CSV 导出均为前端本地实现
     ============================================================ -->
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">变更动态</h1>
      <n-space>
        <span class="ws-status">
          <span class="dot"></span>实时监听中 · 已接收 {{ receivedCount }} 条
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
      <span class="local-note">本地实时数据 · 无 API 请求</span>
    </div>

    <n-data-table
      :columns="columns"
      :data="displayItems"
      :bordered="false"
      size="small"
      :pagination="pagination"
      style="background:var(--bg-card);border-radius:var(--radius-lg)"
      @update:page="onPageChange"
      @update:page-size="onPageSizeChange"
    />

    <n-empty v-if="!items.length" description="等待实时数据…(页面打开后, KV 变更会实时出现在这里)" style="margin-top:60px" />
    <n-empty v-else-if="!displayItems.length" description="无匹配记录" style="margin-top:60px" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NButton, NDataTable, NDatePicker, NEmpty, NInput, NSpace
} from 'naive-ui'
import { useFieldLabels } from '../composables/useFieldLabels'
import { useWebSocket } from '../composables/useWebSocket'
import type { KvHistory } from '../types'

const { labelOf } = useFieldLabels()

// ---- 内存数据(全部来自 WS,时间倒序) ----
const items = ref<KvHistory[]>([])
const receivedCount = ref(0)   // 累计接收条数
const MAX_ITEMS = 1000         // 内存上限,超出丢弃最旧
const seenKeys = new Set<string>()

// 给每行生成全局序号 + 唯一 key，避免 Naive UI 把 KV key 名当作行标识导致 duplicate key
interface RowItem extends KvHistory { kv_key: string; _idx: number }

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

// ---- 前端本地分页 ----
const page = ref(1)
const pageSize = ref(20)

const displayItems = computed<RowItem[]>(() => {
  const filtered = filteredItems.value
  const start = (page.value - 1) * pageSize.value
  return filtered.slice(start, start + pageSize.value).map((item, i) => ({
    ...item,
    kv_key: item.key,
    key: String(item.id),
    _idx: start + i + 1
  }))
})

const pagination = computed(() => {
  return {
    page: page.value,
    pageSize: pageSize.value,
    itemCount: filteredItems.value.length,
    showSizePicker: true,
    pageSizes: [10, 20, 50],
    prefix: () => `共 ${filteredItems.value.length} 条`,
    onUpdatePage: (p: number) => onPageChange(p),
    onUpdatePageSize: (ps: number) => onPageSizeChange(ps)
  }
})

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
    seenKeys.delete(`${removed.key}|${removed.changed_at}`)
  }
}

onMounted(() => {
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed') {
      receivedCount.value++
      const id = `${data.key}|${data.changed_at}`
      if (seenKeys.has(id)) return
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
    }
  })
})

onUnmounted(() => { cleanupWs?.() })

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

function onPageChange(p: number) { page.value = p }
function onPageSizeChange(ps: number) { pageSize.value = ps; page.value = 1 }

// 筛选变化 → 回到第一页
watch([searchKey, filterStart, filterEnd], () => { page.value = 1 })
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
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
