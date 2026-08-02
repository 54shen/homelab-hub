<template>
  <n-modal
    :show="show"
    preset="card"
    :title="`📋 ${keyProp} 的历史`"
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

    <!-- 表格 -->
    <n-data-table
      :columns="columns"
      :data="items"
      :loading="loading"
      :bordered="false"
      size="small"
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
import type { KvHistory } from '../types'

const props = defineProps<{ show: boolean; keyProp: string }>()
defineEmits<{ 'update:show': [value: boolean] }>()

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
  if (props.keyProp?.endsWith('系统音量') && val === '-1') return '🔇 静音'
  return val
}

// ---- 列定义 ----
const columns = [
  {
    title: '时间', key: 'changed_at', width: 160,
    render(row: KvHistory) { return row.changed_at || '—' }
  },
  { title: 'Key', key: 'key', width: 180, ellipsis: { tooltip: true } },
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
    // 注册 WS 监听
    cleanupWs = on((event, data: any) => {
      if (event === 'kv.changed' && data.key === props.keyProp) {
        if (hasFilter.value || page.value !== 1) {
          newCount.value++
        } else {
          const id = `${data.key}|${data.changed_at}`
          if (seenKeys.has(id)) return  // 已存在，跳过
          seenKeys.add(id)
          items.value.push({
            id: 0,
            key: data.key,
            old_value: data.old_value ?? null,
            new_value: data.value,
            source: data.source || 'ws',
            retention_days: data.retention_days ?? 180,
            changed_at: data.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' ')
          })
          // 按时间倒序排列
          items.value.sort((a: any, b: any) => b.changed_at.localeCompare(a.changed_at))
          if (items.value.length > pageSize.value) {
            const removed = items.value.pop()!
            seenKeys.delete(`${removed.key}|${removed.changed_at}`)
          }
          // total 不递增 — 保持服务端权威计数
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
