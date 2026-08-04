<!-- ============================================================
     Shared Center — 历史记录2
     前端代码与 kv-history-viewer 完全一致
     (FilterBar + TrendChart + RecordsTable,仅 API 层接本项目带认证的 historyApi)
     ============================================================ -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NSelect, useMessage } from 'naive-ui'
import { historyApi, type HistoryListParams } from '../api'
import FilterBar, { type HistoryFilters } from '../components/FilterBar.vue'
import RecordsTable from '../components/RecordsTable.vue'
import TrendChart from '../components/TrendChart.vue'
import { useFieldLabels } from '../composables/useFieldLabels'
import type { HistoryKeyInfo, HistorySource, HistoryStats, KvHistory, TrendPoint } from '../types'

// 字段映射:英文 key → 中文显示名
const { labelOf } = useFieldLabels()
function keyLabel(key: string | null): string {
  if (!key) return ''
  const label = labelOf(key)
  return label === key ? key : label
}

// 自动刷新选项:0 = 关闭
const REFRESH_OPTIONS = [
  { label: '关', value: 0 },
  { label: '10 秒', value: 10 },
  { label: '30 秒', value: 30 },
  { label: '60 秒', value: 60 },
]

const message = useMessage()
const route = useRoute()
const router = useRouter()

// 初始从 URL 恢复选中的 key(支持鼠标后退键返回)
const initialKey = (route.query.key as string | undefined) || null

const keys = ref<HistoryKeyInfo[]>([])
const sources = ref<HistorySource[]>([])
const stats = ref<HistoryStats | null>(null)
const filters = ref<HistoryFilters>({ search: null, key: initialKey, prefix: null, suffix: null, source: null, start: null, end: null })

// 分组模式:按 key 前缀分组(与变量管理一致),开启时拉全量
const groupByPrefix = ref(false)
// 分组模式下一次拉取上限(后端 page_size 上限 50000)
const GROUP_LIMIT = 50000
// 分组卡片默认最多展示条数(每组可独立展开全部)
const GROUP_SHOW = 10
// 分组提示条(可手动关闭)
const showGroupTip = ref(true)
// 每组独立展开状态
const expandedGroups = ref<Set<string>>(new Set())

const groupedData = computed(() => {
  const groups = new Map<string, KvHistory[]>()
  for (const r of records.value) {
    const dot = r.key.indexOf('.')
    const prefix = dot > 0 ? r.key.slice(0, dot) : '(无前缀)'
    if (!groups.has(prefix)) groups.set(prefix, [])
    groups.get(prefix)!.push(r)
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})

function toggleGroup() {
  groupByPrefix.value = !groupByPrefix.value
  loadAll()
}

// 分组卡片展开/收起(每组独立)
function toggleGroupExpand(prefix: string) {
  const s = new Set(expandedGroups.value)
  if (s.has(prefix)) s.delete(prefix)
  else s.add(prefix)
  expandedGroups.value = s
}

// 点击表格中的 key → 顶部展示趋势图 + 表格筛到该 key
function onSelectKey(key: string) {
  filters.value.key = key
  const k = keys.value.find(x => x.key === key)
  if (k && !k.plot_kind) {
    message.warning(`「${key}」无可绘图格式,无趋势图`)
  }
}

// 返回:清除 key 筛选,恢复完整列表(其他筛选条件保留)
function clearChartKey() {
  filters.value.key = null
}

// ---- 路由同步:选中 key 写入 URL,鼠标后退键可返回 ----
// key 变化 → push 到 URL(产生历史记录,后退键才能回到上一步)
watch(() => filters.value.key, (k) => {
  const qk = route.query.key as string | undefined
  if ((k || undefined) !== qk) {
    router.push({ query: { ...route.query, key: k || undefined } })
  }
})
// URL 变化(后退键/侧键)→ 同步回筛选状态
watch(() => route.query.key, (k) => {
  const nk = (k as string | undefined) || null
  if (nk !== filters.value.key) filters.value.key = nk
})

// ---- 图表模式:值趋势 ⇄ 上报频率折线(单击切换,横轴窗口保持) ----
const chartMode = ref<'value' | 'frequency'>('value')
// 频率原始数据(分钟粒度,前端按窗口跨度自适应聚合展示)
const freqMinutePoints = ref<TrendPoint[]>([])
// 各模式保存自己的缩放窗口,切换时恢复(时间轴比例不变)
const valueZoom = ref<{ start: string; end: string } | null>(null)
const freqZoom = ref<{ start: string; end: string } | null>(null)

// 频率粒度:按可视窗口跨度自适应(1 → 5 → 10 → 30 → 60 分钟)
const freqStep = ref(1)
function pickStep(win: { start: string; end: string } | null): number {
  if (!win) return 1
  const spanH = (new Date(win.end).getTime() - new Date(win.start).getTime()) / 3600000
  if (spanH <= 3) return 1
  if (spanH <= 12) return 5
  if (spanH <= 24) return 10
  if (spanH <= 48) return 30
  return 60
}

// 分钟数据 → 按粒度聚合(前端本地计算,无需重新请求)
function aggregateByStep(minutes: TrendPoint[], step: number): TrendPoint[] {
  if (step <= 1) return minutes
  const map = new Map<number, number>()
  for (const p of minutes) {
    const t = new Date(p.changed_at.replace(' ', 'T'))
    const epoch = Math.floor(t.getTime() / 1000)
    const block = Math.floor(epoch / (step * 60)) * (step * 60)
    map.set(block, (map.get(block) ?? 0) + p.value)
  }
  const pad = (n: number) => String(n).padStart(2, '0')
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([block, count]) => {
      const d = new Date(block * 1000)
      return {
        changed_at: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:00`,
        value: count,
        raw: `${count} 次`,
      }
    })
}

const freqPoints = computed(() => aggregateByStep(freqMinutePoints.value, freqStep.value))

// 缩放/拖动窗口变化 → 重算频率粒度(computed 自动重新聚合)
function onChartZoom(win: { start: string; end: string } | null) {
  freqStep.value = pickStep(win)
}

async function onChartClick(win: { start: string; end: string } | null) {
  if (!filters.value.key) return
  if (chartMode.value === 'value') {
    // 值趋势 → 上报频率折线:请求当前缩放窗口内按分钟聚合的数据
    valueZoom.value = win
    freqZoom.value = win
    freqStep.value = pickStep(win)
    chartMode.value = 'frequency'
    try {
      const res = await historyApi.frequency({
        key: filters.value.key,
        start: win?.start,
        end: win?.end,
      })
      freqMinutePoints.value = (res.data ?? []).map(r => ({
        changed_at: `${r.minute}:00`,
        value: r.count,
        raw: `${r.count} 次`,
      }))
    } catch {
      freqMinutePoints.value = []
    }
  } else {
    // 上报频率 → 值趋势:恢复保存的窗口
    freqZoom.value = win
    chartMode.value = 'value'
  }
}

// 拖动时间轴到最早数据边界 → 自动多取 24 小时数据并缓存,时间轴可继续向前扩展
const earlierLoading = ref(false)
const earliestReached = ref(false)  // 已到数据真实起点,不再请求

function fmtTime(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function onNeedEarlier() {
  if (earlierLoading.value || earliestReached.value || !filters.value.key) return
  const isFreq = chartMode.value === 'frequency'
  const pts = isFreq ? freqMinutePoints.value : points.value
  if (pts.length === 0) return
  const earliest = pts[0].changed_at
  // 再往前 24 小时(终点取最早点前 1 秒,避免重复)
  const startD = new Date(earliest.replace(' ', 'T'))
  startD.setHours(startD.getHours() - 24)
  const endD = new Date(earliest.replace(' ', 'T'))
  endD.setSeconds(endD.getSeconds() - 1)
  earlierLoading.value = true
  try {
    if (isFreq) {
      const res = await historyApi.frequency({ key: filters.value.key, start: fmtTime(startD), end: fmtTime(endD) })
      const newPts = (res.data ?? []).map(r => ({ changed_at: `${r.minute}:00`, value: r.count, raw: `${r.count} 次` }))
      if (newPts.length === 0) {
        earliestReached.value = true
        message.info('已到最早的数据,没有更早的记录')
      } else {
        freqMinutePoints.value = [...newPts, ...freqMinutePoints.value]
        console.log('[历史记录] 频率模式向前扩展 24h:', newPts.length, '个分钟, 总:', freqMinutePoints.value.length)
      }
    } else {
      const res = await historyApi.trend({ key: filters.value.key, start: fmtTime(startD), end: fmtTime(endD) })
      if (res.data.points.length === 0) {
        earliestReached.value = true
        message.info('已到最早的数据,没有更早的记录')
      } else {
        points.value = [...res.data.points, ...points.value]
        console.log('[历史记录] 值趋势向前扩展 24h:', res.data.points.length, '点, 总:', points.value.length)
      }
    }
  } catch {
    /* 加载失败保持现状 */
  } finally {
    earlierLoading.value = false
  }
}
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
// 可绘图 key 显示图表:数值 / 时长 / 时间戳都支持;纯字符串(on/off 等)不显示
const showChart = computed(() => Boolean(filters.value.key && selectedKey.value && selectedKey.value.plot_kind))

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
    const params: HistoryListParams = {
      key: filters.value.key || undefined,
      search: filters.value.search || undefined,
      prefix: filters.value.prefix || undefined,
      suffix: filters.value.suffix || undefined,
      source: filters.value.source || undefined,
      start: filters.value.start || undefined,
      end: filters.value.end || undefined,
    }
    if (groupByPrefix.value) {
      // 分组模式:未特意筛选时间时,默认只拉最近 24 小时(避免全量传输)
      if (!params.start) {
        const d = new Date(Date.now() - 24 * 3600 * 1000)
        const p = (n: number) => String(n).padStart(2, '0')
        params.start = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
      }
      const r = await historyApi.list({ ...params, page: 1, page_size: GROUP_LIMIT })
      records.value = r.data.items
      total.value = r.data.total
    } else {
      const r = await historyApi.list({ ...params, page: page.value, page_size: pageSize.value })
      records.value = r.data.items
      total.value = r.data.total
      pages.value = Math.max(1, Math.ceil(r.data.total / pageSize.value))
    }
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

watch(filters, () => {
  page.value = 1
  scheduleLoad()
  earliestReached.value = false  // 筛选条件变化 → 重新允许向前扩展
}, { deep: true })
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
        <n-select
          v-model:value="refreshInterval"
          size="small"
          :options="REFRESH_OPTIONS"
          style="width:100px"
        />
      </label>
      <!-- 分组切换:页面最右侧 -->
      <n-button size="small" quaternary @click="toggleGroup">
        <ion-icon name="layers-outline" style="margin-right:4px;vertical-align:-2px" />
        分组
      </n-button>
    </header>

    <FilterBar :keys="keys" :sources="sources" :filters="filters" @update:filters="filters = $event" />

    <p v-if="error" class="error">⚠ {{ error }}</p>

    <!-- 已选中 key 的工具条:左侧返回键(无论是否有趋势图都显示) -->
    <div v-if="filters.key" class="key-bar">
      <n-button size="tiny" quaternary @click="clearChartKey">
        <ion-icon name="arrow-back-outline" style="margin-right:2px;vertical-align:-2px" />
        返回
      </n-button>
      <span class="key-bar-label" :title="filters.key">{{ keyLabel(filters.key) }}</span>
    </div>

    <div v-if="showChart" class="chart-wrap">
      <TrendChart
        :points="chartMode === 'frequency' ? freqPoints : points"
        :title="chartMode === 'frequency' ? `${keyLabel(filters.key)} 上报频率(粒度${freqStep}分钟)` : `${keyLabel(filters.key)} 趋势`"
        :plot-kind="chartMode === 'frequency' ? 'number' : (selectedKey?.plot_kind || '')"
        :zoom="chartMode === 'frequency' ? freqZoom : valueZoom"
        @click="onChartClick"
        @zoom="onChartZoom"
        @reach-start="onNeedEarlier"
      />
    </div>

    <!-- 分组视图:按前缀分组,每组一个卡片,默认展示前 N 条可展开 -->
    <div v-if="groupByPrefix" class="grouped-view">
      <div v-if="showGroupTip && !filters.start" class="group-tip">
        <span class="tip-text">
          <ion-icon name="information-circle-outline" style="vertical-align:-2px;margin-right:4px" />
          未筛选时间时,分组仅展示最近 24 小时数据;设置时间范围可查看更多
        </span>
        <ion-icon name="close-outline" class="tip-close" @click="showGroupTip = false" />
      </div>
      <div v-for="[prefix, groupItems] in groupedData" :key="prefix" class="group-card">
        <div class="group-title">
          <span class="group-name">{{ prefix }}</span>
          <span class="group-count">{{ groupItems.length }}</span>
          <span v-if="groupItems.length > GROUP_SHOW" class="group-actions">
            <n-button size="tiny" quaternary @click="toggleGroupExpand(prefix)">
              <ion-icon
                :name="expandedGroups.has(prefix) ? 'chevron-up-outline' : 'chevron-down-outline'"
                style="margin-right:2px;vertical-align:-2px"
              />
              {{ expandedGroups.has(prefix) ? '收起' : `展开全部 (${groupItems.length})` }}
            </n-button>
          </span>
        </div>
        <RecordsTable
          :items="expandedGroups.has(prefix) ? groupItems : groupItems.slice(0, GROUP_SHOW)"
          :total="groupItems.length"
          :page="1"
          :page-size="groupItems.length"
          :pages="1"
          :show-pager="false"
          @select-key="onSelectKey"
        />
      </div>
      <div v-if="groupedData.length === 0" class="group-empty">无匹配记录</div>
    </div>

    <!-- 平铺视图:分页表格 -->
    <div v-else class="table-zone">
      <RecordsTable
        :items="records"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :pages="pages"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
        @select-key="onSelectKey"
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
.refresh { font-size: 13px; color: var(--text-secondary); margin-left: auto; display: inline-flex; align-items: center; gap: 8px; }
.error {
  color: var(--color-danger);
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
}
/* 已选中 key 的工具条(返回键在左) */
.key-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: 8px 12px;
  margin-bottom: 12px;
}
.key-bar-label {
  font-size: 13px;
  color: var(--color-info);
  font-family: monospace;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 分组视图:与变量管理一致的卡片式 */
.grouped-view { display: flex; flex-direction: column; gap: 12px; }
.group-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(91, 141, 239, 0.08);
  border: 1px solid rgba(91, 141, 239, 0.2);
  border-radius: var(--radius-md);
  padding: 8px 12px;
}
.tip-text { flex: 1; }
.tip-close {
  font-size: 14px;
  cursor: pointer;
  color: var(--text-secondary);
  opacity: 0.7;
  transition: opacity 0.15s;
}
.tip-close:hover { opacity: 1; color: var(--color-danger); }
.group-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-light);
}
.group-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.group-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #5B8DEF;
  background: rgba(91, 141, 239, 0.1);
  border-radius: var(--radius-full);
}
.group-actions { margin-left: auto; display: inline-flex; align-items: center; }
.group-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
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
