<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NDatePicker, NInput, NSelect } from 'naive-ui'
import type { HistoryKeyInfo, HistorySource } from '../types'
import { useFieldLabels } from '../composables/useFieldLabels'

// 字段映射:英文 key 后缀 → 中文显示名(无映射时返回原 key)
const { labelOf } = useFieldLabels()
function keyLabel(key: string): string {
  const label = labelOf(key)
  return label === key ? key : label
}

export interface HistoryFilters {
  search: string | null   // 模糊搜索 key
  key: string | null      // 精确 key(趋势图入口)
  prefix: string | null   // key 前缀(设备)
  suffix: string | null   // key 后缀(指标)
  source: string | null   // 来源
  start: string | null    // YYYY-MM-DD HH:MM:SS
  end: string | null
}

const props = defineProps<{
  keys: HistoryKeyInfo[]
  sources: HistorySource[]
  filters: HistoryFilters
}>()

const emit = defineEmits<{
  'update:filters': [f: HistoryFilters]
}>()

// ---- 本地状态 ----
const local = ref({
  search: props.filters.search ?? '',
  key: props.filters.key ?? null,
  prefix: props.filters.prefix ?? null,
  suffix: props.filters.suffix ?? null,
  source: props.filters.source ?? null,
})

// 时间范围:毫秒时间戳 ↔ 'YYYY-MM-DD HH:MM:SS'
function strToTs(v: string | null): number | null {
  if (!v) return null
  const t = new Date(v.replace(' ', 'T')).getTime()
  return Number.isNaN(t) ? null : t
}
function tsToStr(ts: number | undefined | null): string | null {
  if (!ts) return null
  const d = new Date(ts)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
const timeRange = ref<[number, number] | null>(
  (() => {
    const s = strToTs(props.filters.start)
    const e = strToTs(props.filters.end)
    return s && e ? [s, e] : null
  })()
)

function apply() {
  emit('update:filters', {
    search: local.value.search.trim() || null,
    key: local.value.key,
    prefix: local.value.prefix,
    suffix: local.value.suffix,
    source: local.value.source,
    start: tsToStr(timeRange.value?.[0]),
    end: tsToStr(timeRange.value?.[1]),
  })
}

function reset() {
  local.value = { search: '', key: null, prefix: null, suffix: null, source: null }
  timeRange.value = null
  apply()
}

// 外部修改 filters(如点击表格 key)→ 同步本地控件显示
watch(() => props.filters, f => {
  local.value = {
    search: f.search ?? '',
    key: f.key ?? null,
    prefix: f.prefix ?? null,
    suffix: f.suffix ?? null,
    source: f.source ?? null,
  }
  const s = strToTs(f.start)
  const e = strToTs(f.end)
  timeRange.value = s && e ? [s, e] : null
}, { deep: true })

// ---- 选项 ----
// 精确 key(filterable 可输入过滤),保留字段映射显示 + 可绘图标记
const PLOT_ICONS: Record<string, string> = {
  number: '📈',
  duration: '⏱️',
  timestamp: '🕐',
}
const keyOptions = computed(() =>
  props.keys.map(k => ({
    label: `${keyLabel(k.key)} (${k.count})${PLOT_ICONS[k.plot_kind] ?? ''}`,
    value: k.key,
  }))
)

// 前缀 = key 第一段(设备),带计数
const prefixOptions = computed(() => {
  const m = new Map<string, number>()
  for (const k of props.keys) {
    const dot = k.key.indexOf('.')
    const p = dot > 0 ? k.key.slice(0, dot) : '(无前缀)'
    m.set(p, (m.get(p) ?? 0) + k.count)
  }
  return [...m.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([p, c]) => ({ label: `${p} (${c})`, value: p }))
})

// 后缀 = key 最后一段(指标),带计数
const suffixOptions = computed(() => {
  const m = new Map<string, number>()
  for (const k of props.keys) {
    const dot = k.key.lastIndexOf('.')
    const s = dot > 0 ? k.key.slice(dot + 1) : '(无后缀)'
    m.set(s, (m.get(s) ?? 0) + k.count)
  }
  return [...m.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([s, c]) => ({ label: `${s} (${c})`, value: s }))
})

const sourceOptions = computed(() =>
  props.sources.map(s => ({ label: `${s.source ?? '(未知)'} (${s.count})`, value: s.source ?? '(未知)' }))
)
</script>

<template>
  <div class="filter-bar">
    <n-input
      v-model:value="local.search"
      placeholder="模糊搜索 key..."
      clearable
      size="small"
      style="flex:1;min-width:180px"
      @update:value="apply"
    >
      <template #prefix>
        <ion-icon name="search-outline" style="color:var(--text-secondary)" />
      </template>
    </n-input>

    <n-select
      v-model:value="local.key"
      :options="keyOptions"
      placeholder="全部键(精确)"
      clearable
      filterable
      size="small"
      style="width:220px"
      @update:value="apply"
    />

    <n-select
      v-model:value="local.prefix"
      :options="prefixOptions"
      placeholder="按设备前缀"
      clearable
      filterable
      size="small"
      style="width:170px"
      @update:value="apply"
    />

    <n-select
      v-model:value="local.suffix"
      :options="suffixOptions"
      placeholder="按指标后缀"
      clearable
      filterable
      size="small"
      style="width:150px"
      @update:value="apply"
    />

    <n-select
      v-model:value="local.source"
      :options="sourceOptions"
      placeholder="按来源"
      clearable
      filterable
      size="small"
      style="width:170px"
      @update:value="apply"
    />

    <n-date-picker
      v-model:value="timeRange"
      type="datetimerange"
      placeholder="时间范围"
      clearable
      size="small"
      style="width:300px"
      @update:value="apply"
    />

    <n-button size="small" type="primary" @click="apply">
      <ion-icon name="funnel-outline" style="margin-right:4px;vertical-align:-2px" />
      筛选
    </n-button>
    <n-button size="small" quaternary @click="reset">重置</n-button>

    <!-- 附加按钮(分组等)由页面注入 -->
    <slot name="extra" />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  margin-bottom: 12px;
}
</style>
