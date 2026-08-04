<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { KvHistory } from '../types'
import { useFieldLabels } from '../composables/useFieldLabels'

// 注意:showPager 必须默认 true —— 否则调用方不传时 Vue 给 Boolean prop
// 填 false,分页器永远不渲染(历史记录平铺视图将无法翻页)
const props = withDefaults(defineProps<{
  items: KvHistory[]
  total: number
  page: number
  pageSize: number
  pages: number
  showPager?: boolean  // 分组视图等场景显式传 false 隐藏分页器
}>(), {
  showPager: true
})

// 字段映射:英文 key 后缀 → 中文显示名(无映射时返回原 key)
const { labelOf } = useFieldLabels()
function keyLabel(key: string): string {
  const label = labelOf(key)
  return label === key ? key : label
}

const emit = defineEmits<{
  'update:page': [p: number]
  'update:pageSize': [ps: number]
  'select-key': [key: string]  // 点击 key → 顶部展示趋势图
}>()

// 页码列表:1 … 当前页前后2个 … N(超过窗口用省略号折叠)
function pageItems(): Array<number | '…'> {
  const total = props.pages
  const cur = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const items: Array<number | '…'> = []
  const start = Math.max(1, cur - 2)
  const end = Math.min(total, cur + 2)
  if (start > 1) {
    items.push(1)
    if (start > 2) items.push('…')
  }
  for (let i = start; i <= end; i++) items.push(i)
  if (end < total) {
    if (end < total - 1) items.push('…')
    items.push(total)
  }
  return items
}

function goTo(p: number | '…') {
  if (p !== '…') emit('update:page', p)
}
</script>

<template>
  <div class="table-wrap">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>键</th>
            <th>来源</th>
            <th>旧值 → 新值</th>
            <th>保留(天)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in items" :key="r.id">
            <td class="nowrap">{{ r.changed_at }}</td>
            <td class="key nowrap" :title="r.key">
              <span class="key-link" @click="emit('select-key', r.key)">{{ keyLabel(r.key) }}</span>
            </td>
            <td class="nowrap">{{ r.source }}</td>
            <td>
              <span class="old" :class="{ changed: r.old_value !== r.new_value }">{{ r.old_value ?? '' }}</span>
              <span class="arrow">→</span>
              <span class="new" :class="{ changed: r.old_value !== r.new_value }">{{ r.new_value }}</span>
            </td>
            <td class="nowrap">{{ r.retention_days }}</td>
          </tr>
          <tr v-if="items.length === 0">
            <td colspan="5" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="showPager !== false" class="pager">
      <span class="info">共 {{ total }} 条 · 第 {{ page }}/{{ pages }} 页</span>
      <button :disabled="page <= 1" @click="emit('update:page', page - 1)">上一页</button>
      <button
        v-for="(p, i) in pageItems()"
        :key="i"
        class="page-num"
        :class="{ active: p === page }"
        :disabled="p === '…' || p === page"
        @click="goTo(p)"
      >{{ p }}</button>
      <button :disabled="page >= pages" @click="emit('update:page', page + 1)">下一页</button>
      <n-select
        :value="pageSize"
        size="small"
        style="width:100px"
        :options="[
          { label: '20 条/页', value: 20 },
          { label: '50 条/页', value: 50 },
          { label: '100 条/页', value: 100 },
        ]"
        @update:value="(v: number) => emit('update:pageSize', v)"
      />
    </div>
  </div>
</template>

<style scoped>
.table-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.table-scroll { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th, td {
  text-align: left;
  padding: 7px 12px;
  border-bottom: 1px solid var(--border-light);
  white-space: normal;
  word-break: break-all;
}
th {
  background: var(--bg-sidebar);
  font-weight: 600;
  color: var(--text-secondary);
  position: sticky;
  top: 0;
}
tbody tr:hover { background: var(--bg-sidebar-hover); }
.nowrap { white-space: nowrap; }
.key { color: var(--color-info); font-weight: 500; }
.key-link { cursor: pointer; transition: opacity 0.15s; }
.key-link:hover { opacity: 0.75; text-decoration: underline; }
.old.changed { text-decoration: line-through; color: var(--text-secondary); }
.new.changed { color: var(--color-success); font-weight: 600; }
.empty { text-align: center; color: var(--text-secondary); padding: 24px 0; }
.pager {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border-light);
}
.info { margin-right: auto; font-size: 13px; color: var(--text-secondary); }
.pager button {
  background: var(--bg-sidebar);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
}
.pager button:hover:not(:disabled) { background: var(--bg-sidebar-hover); }
.pager button:disabled { opacity: 0.5; cursor: default; }
.pager button.page-num { min-width: 28px; padding: 4px 6px; text-align: center; }
.pager button.page-num.active {
  background: var(--color-info);
  border-color: var(--color-info);
  color: #fff;
  opacity: 1;
}
</style>
