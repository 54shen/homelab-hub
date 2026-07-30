<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">系统日志</h1>
      <n-space>
        <n-button size="small" quaternary @click="exportCsv">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
          导出 CSV
        </n-button>
        <n-popconfirm @positive-click="handleClear">
          <template #trigger>
            <n-button size="small" quaternary type="error">
              <ion-icon name="trash-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
              清空日志
            </n-button>
          </template>
          确定清空所有日志？此操作不可撤销
        </n-popconfirm>
      </n-space>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <n-select
        v-model:value="filterLevel"
        :options="levelOptions"
        placeholder="日志级别"
        clearable
        size="small"
        style="width:130px"
      />
      <n-input
        v-model:value="filterModule"
        placeholder="按模块筛选..."
        clearable
        size="small"
        style="width:180px"
      >
        <template #prefix>
          <ion-icon name="cube-outline" style="color:var(--text-secondary)"></ion-icon>
        </template>
      </n-input>
      <span class="filter-info">共 {{ total }} 条</span>
    </div>

    <!-- 日志列表 -->
    <n-empty v-if="logs.length === 0" description="暂无日志" style="margin-top:40px" />
    <div v-else class="log-list">
      <div
        v-for="l in logs"
        :key="l.id"
        class="log-item"
        :class="'level-' + l.level"
        @click="toggleDetail(l)"
      >
        <div class="log-main">
          <span class="log-level-tag" :class="l.level">{{ levelLabel(l.level) }}</span>
          <span class="log-time">{{ formatTime(l.created_at) }}</span>
          <span class="log-module">{{ l.module }}</span>
          <span class="log-msg">{{ l.message }}</span>
          <ion-icon
            v-if="l.detail"
            :name="expandedId === l.id ? 'chevron-up-outline' : 'chevron-down-outline'"
            class="log-expand"
          ></ion-icon>
        </div>
        <div v-if="expandedId === l.id && l.detail" class="log-detail">
          <pre>{{ l.detail }}</pre>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <n-pagination
      v-if="total > 50"
      :page="page"
      :page-size="50"
      :item-count="total"
      :on-update:page="(p: number) => { page = p; loadData() }"
      style="margin-top:16px;justify-content:flex-end"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  NButton, NEmpty, NInput, NPagination, NPopconfirm,
  NSelect, NSpace, useMessage
} from 'naive-ui'
import { logApi } from '../api'
import type { SystemLog } from '../types'

const message = useMessage()
const logs = ref<SystemLog[]>([])
const total = ref(0)
const page = ref(1)
const filterLevel = ref<string | null>(null)
const filterModule = ref('')
const expandedId = ref<number | null>(null)

const levelOptions = [
  { label: '🔵 Debug', value: 'debug' },
  { label: '⚪ Info', value: 'info' },
  { label: '🟡 Warn', value: 'warn' },
  { label: '🔴 Error', value: 'error' }
]

function levelLabel(level: string) {
  return { debug: 'DEBUG', info: 'INFO', warn: 'WARN', error: 'ERROR' }[level] || level.toUpperCase()
}

function formatTime(ts: string): string {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false
  })
}

function toggleDetail(l: SystemLog) {
  expandedId.value = expandedId.value === l.id ? null : l.id
}

async function loadData() {
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 50 }
    if (filterLevel.value) params.level = filterLevel.value
    if (filterModule.value) params.module = filterModule.value
    const res = await logApi.list(params)
    if (res.data) {
      logs.value = res.data.items
      total.value = res.data.total
    }
  } catch { logs.value = []; total.value = 0 }
}

async function exportCsv() {
  try {
    const params: Record<string, unknown> = {}
    if (filterLevel.value) params.level = filterLevel.value
    const res = await logApi.exportCsv(params)
    const blob = new Blob([res.data], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch { message.error('导出失败') }
}

async function handleClear() {
  try {
    await logApi.clear()
    message.success('日志已清空')
    await loadData()
  } catch { message.error('清空失败') }
}

watch([filterLevel, filterModule], () => { page.value = 1; loadData() })
onMounted(loadData)
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.filter-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
}

/* ---- 日志列表 ---- */
.log-list {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.log-item {
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background 0.1s ease;
}
.log-item:last-child {
  border-bottom: none;
}
.log-item:hover {
  background: #F9FAFB;
}
.log-item.level-error {
  border-left: 3px solid var(--color-danger);
}
.log-item.level-warn {
  border-left: 3px solid var(--color-warning);
}

.log-main {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  font-size: 13px;
}

.log-level-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  flex-shrink: 0;
  min-width: 48px;
  text-align: center;
}
.log-level-tag.debug { background: #F1F5F9; color: #64748B; }
.log-level-tag.info { background: rgba(91, 141, 239, 0.1); color: var(--color-info); }
.log-level-tag.warn { background: rgba(245, 158, 11, 0.1); color: var(--color-warning); }
.log-level-tag.error { background: rgba(239, 68, 68, 0.08); color: var(--color-danger); }

.log-time {
  color: var(--text-secondary);
  font-size: 11px;
  font-family: monospace;
  flex-shrink: 0;
  min-width: 130px;
}
.log-module {
  color: var(--color-info);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 70px;
  background: rgba(91, 141, 239, 0.06);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  text-align: center;
}
.log-msg {
  flex: 1;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.log-expand {
  color: var(--text-secondary);
  flex-shrink: 0;
  font-size: 14px;
}

/* ---- 展开详情 ---- */
.log-detail {
  padding: 0 16px 12px 16px;
}
.log-detail pre {
  background: var(--bg-page);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
  max-height: 200px;
  overflow-y: auto;
}
</style>
