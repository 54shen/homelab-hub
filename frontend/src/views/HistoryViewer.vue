<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">历史记录</h1>
      <n-space>
        <RefreshControl v-model="refreshInterval" />
        <n-button size="small" @click="exportCsv">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
          导出 CSV
        </n-button>
      </n-space>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <n-input
        v-model:value="filterKey"
        placeholder="按 key 筛选..."
        clearable
        style="width: 200px"
      >
        <template #prefix>
          <ion-icon name="search-outline" style="color:var(--text-secondary)"></ion-icon>
        </template>
      </n-input>
      <n-select
        v-model:value="filterPrefix"
        :options="prefixOptions"
        placeholder="按设备/前缀"
        clearable
        style="width: 160px"
      />
      <n-select
        v-model:value="filterSource"
        :options="sourceOptions"
        placeholder="按来源"
        clearable
        style="width: 140px"
      />
      <n-date-picker
        v-model:value="dateRange"
        type="daterange"
        clearable
        style="width: 240px"
        :default-value="[Date.now() - 30 * 86400000, Date.now()]"
      />
      <span class="filter-info">共 {{ total }} 条</span>
    </div>

    <!-- 表格 -->
    <n-data-table
      :columns="columns"
      :data="data"
      :bordered="false"
      :single-line="false"
      size="small"
      :pagination="{
        page: histPage,
        pageSize: histPageSize,
        showSizePicker: true,
        pageSizes: [20, 50, 100]
      }"
      style="background: var(--bg-card); border-radius: var(--radius-lg)"
      @update:page="histPage = $event"
      @update:page-size="histPageSize = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import { NButton, NDataTable, NDatePicker, NInput, NSelect, NSpace } from 'naive-ui'
import RefreshControl from '../components/RefreshControl.vue'
import { useRefreshInterval } from '../composables/useRefreshInterval'
import { historyApi, kvApi } from '../api'
import type { KvHistory, KvEntry } from '../types'

const data = ref<KvHistory[]>([])
const total = ref(0)
const filterKey = ref('')
const filterPrefix = ref<string | null>(null)
const filterSource = ref<string | null>(null)
const dateRange = ref<[number, number] | null>([Date.now() - 30 * 86400000, Date.now()])
const allKeys = ref<KvEntry[]>([])
const histPage = ref(1)
const histPageSize = ref(50)
const refreshInterval = useRefreshInterval()

// 前缀/来源选项（从现有 KV keys 提取）
const prefixOptions = computed(() => {
  const prefixes = new Set<string>()
  for (const r of allKeys.value) {
    const dot = r.key.indexOf('.')
    if (dot > 0) prefixes.add(r.key.slice(0, dot))
  }
  return [...prefixes].sort().map(p => ({ label: p, value: p }))
})

const sourceOptions = computed(() => {
  const sources = new Set<string>()
  for (const r of allKeys.value) {
    if (r.source) sources.add(r.source)
  }
  for (const h of data.value) {
    if (h.source) sources.add(h.source)
  }
  return [...sources].sort().map(s => ({ label: s, value: s }))
})

const columns = [
  {
    title: '时间',
    key: 'changed_at',
    width: 160,
    render(row: KvHistory) {
      return row.changed_at || '--'
    }
  },
  { title: 'Key', key: 'key', width: 160, ellipsis: { tooltip: true } },
  {
    title: '变更',
    key: 'change',
    width: 220,
    render(row: KvHistory) {
      if (!row.old_value) {
        return [h('span', { class: 'tag-new' }, '(新增) '), h('span', row.new_value)]
      }
      return [
        h('span', { class: 'old-val' }, row.old_value),
        h('span', { class: 'arrow' }, ' → '),
        h('span', { class: 'new-val' }, row.new_value)
      ]
    }
  },
  { title: '来源', key: 'source', width: 140 }
]

async function loadData() {
  try {
    const params: Record<string, unknown> = {}
    if (filterKey.value) params.key = filterKey.value
    if (dateRange.value) {
      params.start = new Date(dateRange.value[0]).toISOString()
      params.end = new Date(dateRange.value[1]).toISOString()
    }
    const res = await historyApi.list(params)
    if (res.data) {
      // 前端过滤前缀和来源
      let items = res.data.items
      if (filterPrefix.value) {
        items = items.filter(h => h.key.startsWith(filterPrefix.value! + '.'))
      }
      if (filterSource.value) {
        items = items.filter(h => h.source === filterSource.value)
      }
      data.value = items
      total.value = items.length
    }
  } catch {
    data.value = []
    total.value = 0
  }
}

async function exportCsv() {
  try {
    const params: Record<string, unknown> = {}
    if (filterKey.value) params.key = filterKey.value
    if (dateRange.value) {
      params.start = new Date(dateRange.value[0]).toISOString()
      params.end = new Date(dateRange.value[1]).toISOString()
    }
    const res = await historyApi.exportCsv(params)
    const blob = new Blob([res.data], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `history_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    console.error('导出失败')
  }
}

watch([filterKey, filterPrefix, filterSource, dateRange], () => loadData(), { deep: true })

async function loadKeys() {
  try {
    const res = await kvApi.list()
    if (res.data) allKeys.value = res.data
  } catch { allKeys.value = [] }
}

// 定时刷新
let timer: ReturnType<typeof setInterval> | null = null
function startTimer(sec: number) {
  if (timer) { clearInterval(timer); timer = null }
  if (sec > 0) timer = setInterval(loadData, sec * 1000)
}
watch(refreshInterval, startTimer)

onMounted(() => { loadData(); loadKeys() })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--gap-lg);
}
.page-header .page-title {
  margin-bottom: 0;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.filter-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
}

/* 复用变更样式 */
.old-val { color: var(--color-danger); text-decoration: line-through; font-size: 12px; }
.arrow { color: var(--text-secondary); font-size: 12px; }
.new-val { color: var(--color-success); font-weight: 500; font-size: 12px; }
.tag-new {
  font-size: 11px;
  background: rgba(16, 185, 129, 0.1);
  color: var(--color-success);
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 4px;
}
</style>
