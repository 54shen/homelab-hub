<!-- ============================================================
     Shared Center — 历史记录2
     前端代码与 kv-history-viewer 完全一致
     (FilterBar + TrendChart + RecordsTable,仅 API 层接本项目带认证的 historyApi)
     ============================================================ -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { historyApi } from '../api'
import FilterBar, { type HistoryFilters } from '../components/FilterBar.vue'
import RecordsTable from '../components/RecordsTable.vue'
import TrendChart from '../components/TrendChart.vue'
import type { HistoryKeyInfo, HistorySource, HistoryStats, KvHistory, TrendPoint } from '../types'

const keys = ref<HistoryKeyInfo[]>([])
const sources = ref<HistorySource[]>([])
const stats = ref<HistoryStats | null>(null)
const filters = ref<HistoryFilters>({ key: null, source: null, start: null, end: null })
const page = ref(1)
const pageSize = ref(20)
const records = ref<KvHistory[]>([])
const total = ref(0)
const pages = ref(0)
const points = ref<TrendPoint[]>([])
const loading = ref(false)
const error = ref('')
const refreshInterval = ref(0) // 0 = 关闭

let timer: ReturnType<typeof setInterval> | null = null
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const selectedKey = computed(() => keys.value.find(k => k.key === filters.value.key))
// 仅数值型 key 显示图表；非数值（uptime、on/off 等）只显示表格
const showChart = computed(() => Boolean(filters.value.key && selectedKey.value && selectedKey.value.is_numeric))

async function loadTrend() {
  if (!filters.value.key) {
    points.value = []
    return
  }
  const t = await historyApi.trend({
    key: filters.value.key,
    source: filters.value.source || undefined,
    start: filters.value.start || undefined,
    end: filters.value.end || undefined,
  })
  points.value = t.data.points
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const r = await historyApi.list({
      key: filters.value.key || undefined,
      source: filters.value.source || undefined,
      start: filters.value.start || undefined,
      end: filters.value.end || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    records.value = r.data.items
    total.value = r.data.total
    pages.value = Math.max(1, Math.ceil(r.data.total / pageSize.value))
    await loadTrend()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function scheduleLoad() {
  clearTimeout(debounceTimer as ReturnType<typeof setTimeout>)
  debounceTimer = setTimeout(loadAll, 300)
}

watch(filters, () => { page.value = 1; scheduleLoad() }, { deep: true })
watch([page, pageSize], scheduleLoad)

// 手动翻页/改每页条数 → 关闭自动刷新(避免刷新把表格状态打乱)
function onPageChange(p: number) {
  refreshInterval.value = 0
  page.value = p
}

function onPageSizeChange(ps: number) {
  refreshInterval.value = 0
  pageSize.value = ps
}

watch(refreshInterval, () => {
  clearInterval(timer as ReturnType<typeof setInterval>)
  timer = null
  if (refreshInterval.value > 0) {
    timer = setInterval(() => {
      if (!document.hidden) loadAll() // 页面不可见时暂停
    }, refreshInterval.value * 1000)
  }
})

onMounted(async () => {
  try {
    const [k, s, st] = await Promise.all([historyApi.keys(), historyApi.sources(), historyApi.stats()])
    keys.value = k.data
    sources.value = s.data
    stats.value = st.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  }
  await loadAll()
})

onBeforeUnmount(() => {
  clearInterval(timer as ReturnType<typeof setInterval>)
  clearTimeout(debounceTimer as ReturnType<typeof setTimeout>)
})
</script>

<template>
  <div class="app">
    <header class="top">
      <h1>历史记录</h1>
      <div class="stats" v-if="stats">
        <span class="stat">总记录 <b>{{ stats.total_records }}</b></span>
        <span class="stat">最近变更 <b>{{ stats.max_changed_at }}</b></span>
        <span class="stat">近24h <b>{{ stats.per_source.map(s => s.source + ':' + s.count).join(' · ') }}</b></span>
      </div>
      <label class="refresh">自动刷新
        <select v-model="refreshInterval">
          <option :value="0">关</option>
          <option :value="10">10 秒</option>
          <option :value="30">30 秒</option>
          <option :value="60">60 秒</option>
        </select>
      </label>
    </header>

    <FilterBar :keys="keys" :sources="sources" :filters="filters" @update:filters="filters = $event" />

    <p v-if="error" class="error">⚠ {{ error }}</p>

    <TrendChart v-if="showChart" :points="points" :title="`${filters.key} 数值趋势`" />

    <div class="table-zone">
      <RecordsTable
        :items="records"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :pages="pages"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
      <p v-if="loading" class="loading">加载中…</p>
    </div>
  </div>
</template>

<style scoped>
.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px;
}
.top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
h1 { font-size: 20px; margin: 0; color: var(--text-primary); }
.stats { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--text-secondary); }
.stat b { color: var(--text-primary); margin-left: 2px; }
.refresh { font-size: 13px; color: var(--text-secondary); margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.refresh select {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-xs);
  padding: 3px 6px;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
}
.error {
  color: var(--color-danger);
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
}
/* 加载中 → 覆盖在表格上的遮罩,不占文档流,翻页时表格不跳动 */
.table-zone { position: relative; }
.loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-md);
  z-index: 2;
}
</style>
