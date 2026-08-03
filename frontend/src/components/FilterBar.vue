<script setup lang="ts">
import { ref } from 'vue'
import type { HistoryKeyInfo, HistorySource } from '../types'
import { useFieldLabels } from '../composables/useFieldLabels'

// 字段映射:英文 key 后缀 → 中文显示名(无映射时返回原 key)
const { labelOf } = useFieldLabels()
function keyLabel(key: string): string {
  const label = labelOf(key)
  return label === key ? key : label
}

export interface HistoryFilters {
  key: string | null
  source: string | null
  start: string | null
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

const local = ref({
  key: props.filters.key ?? '',
  source: props.filters.source ?? '',
  start: props.filters.start ?? '',
  end: props.filters.end ?? '',
})

// datetime-local 输出 'YYYY-MM-DDTHH:mm'（无秒），转后端要求的 'YYYY-MM-DD HH:MM:SS'
function toDb(v: string): string | null {
  return v ? v.replace('T', ' ') + ':00' : null
}

function apply() {
  emit('update:filters', {
    key: local.value.key || null,
    source: local.value.source || null,
    start: toDb(local.value.start),
    end: toDb(local.value.end),
  })
}

function reset() {
  local.value = { key: '', source: '', start: '', end: '' }
  apply()
}
</script>

<template>
  <div class="filter-bar">
    <select v-model="local.key" @change="apply">
      <option value="">全部键</option>
      <option v-for="k in keys" :key="k.key" :value="k.key" :title="k.key">
        {{ keyLabel(k.key) }} ({{ k.count }}){{ k.is_numeric ? ' 📈' : '' }}
      </option>
    </select>
    <select v-model="local.source" @change="apply">
      <option value="">全部来源</option>
      <option v-for="s in sources" :key="s.source ?? ''" :value="s.source ?? ''">
        {{ s.source }} ({{ s.count }})
      </option>
    </select>
    <label>开始 <input type="datetime-local" v-model="local.start" @change="apply" /></label>
    <label>结束 <input type="datetime-local" v-model="local.end" @change="apply" /></label>
    <button @click="apply">筛选</button>
    <button @click="reset">重置</button>
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
label { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-secondary); }
select, input[type="datetime-local"] {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-xs);
  padding: 4px 8px;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
}
select:focus, input[type="datetime-local"]:focus { border-color: var(--color-info); }
button {
  background: var(--bg-sidebar);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
}
button:hover { background: var(--bg-sidebar-hover); }
</style>
