<script setup lang="ts">
// ============================================================
// 剪切板面板 — 仪表盘专用:左侧输入(主题可选+内容),右侧实时历史(最近 20 条)
// 多端共享:任一端发送 → 后端广播 kv.changed → 所有端实时更新
// ============================================================
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { NButton, NEmpty, NInput, NTag, useMessage } from 'naive-ui'
import { historyApi, kvApi } from '../api'
import { useWebSocket } from '../composables/useWebSocket'
import {
  CLIPBOARD_KEY, CLIPBOARD_RETENTION_DAYS, decodeClipboard, encodeClipboard,
} from '../utils/clipboard'

const MAX_HISTORY = 20
const MAX_SEARCH = 50  // 搜索结果上限(全部历史中匹配的前 50 条)

const message = useMessage()
const topic = ref('')
const content = ref('')
const sending = ref(false)
const contentInput = ref<HTMLTextAreaElement | null>(null)

// ---- 搜索:防抖 300ms,空关键词 = 实时模式(最近 20 条) ----
const searchQuery = ref('')
const searchTotal = ref(0)
const isSearching = computed(() => searchQuery.value.trim().length > 0)

interface ClipItem {
  uid: string
  topic: string
  content: string
  changed_at: string
  source: string
}

const items = ref<ClipItem[]>([])

// uid = changed_at|value:秒级精度,同秒同值必为同一事件(值未变则静默,无重复推送)
function uidOf(value: string, changedAt: string): string {
  return `${changedAt}|${value}`
}

function toItem(value: string, changedAt: string, source: string): ClipItem {
  const { topic: t, content: c } = decodeClipboard(value)
  return { uid: uidOf(value, changedAt), topic: t, content: c, changed_at: changedAt, source: source || '' }
}

function pushItem(item: ClipItem) {
  if (items.value.some(i => i.uid === item.uid)) return  // 去重(含发送后与 WS 回显竞态)
  items.value.unshift(item)
  while (items.value.length > MAX_HISTORY) items.value.pop()  // 超上限淘汰最旧
}

async function loadData() {
  try {
    const r = await historyApi.list({ key: CLIPBOARD_KEY, page_size: MAX_HISTORY })
    items.value = (r.data?.items ?? []).map(row => toItem(row.new_value, row.changed_at, row.source))
  } catch { /* 后端未响应,保持上次数据 */ }
}

async function doSearch(q: string) {
  try {
    const r = await historyApi.list({ key: CLIPBOARD_KEY, value_search: q, page_size: MAX_SEARCH })
    items.value = (r.data?.items ?? []).map(row => toItem(row.new_value, row.changed_at, row.source))
    searchTotal.value = r.data?.total ?? 0
  } catch { /* 后端未响应 */ }
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    const t = q.trim()
    if (t) await doSearch(t)
    else await loadData()  // 清空搜索 → 恢复实时最近 20 条
  }, 300)
})

// 发送后拉最新 1 条合并:覆盖 WS 断开、值未变静默、与 WS 回显竞态三种场景
async function loadLatestAndMerge() {
  try {
    const r = await historyApi.list({ key: CLIPBOARD_KEY, page_size: 1 })
    const row = r.data?.items?.[0]
    if (row) pushItem(toItem(row.new_value, row.changed_at, row.source))
  } catch { /* 忽略 */ }
}

async function send() {
  const c = content.value.trim()
  if (!c || sending.value) return
  sending.value = true
  try {
    const username = localStorage.getItem('sc_username') || 'admin'
    await kvApi.set({
      key: CLIPBOARD_KEY,
      value: encodeClipboard(topic.value, c),
      type: 'string',
      source: `${username}(Web)`,
      retention_days: CLIPBOARD_RETENTION_DAYS,
    })
    // 搜索模式下不合并(新条目未必匹配当前关键词),仅实时模式合并
    if (!isSearching.value) await loadLatestAndMerge()
    topic.value = ''
    content.value = ''
    await nextTick()
    contentInput.value?.focus()
  } catch {
    message.error('发送失败')
  } finally {
    sending.value = false
  }
}

// 复制内容(主题是标签,不参与复制);非 https 下 clipboard API 不可用 → execCommand 降级
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch { /* 权限/非安全上下文 */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

async function copyContent(item: ClipItem) {
  if (await copyText(item.content)) message.success('已复制')
  else message.error('复制失败')
}

// ---- WS 实时更新 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(async () => {
  await loadData()
  cleanupWs = on((event, data: any) => {
    if (event === 'kv.changed' && data?.key === CLIPBOARD_KEY) {
      // 搜索模式下忽略实时推送(新条目未必匹配当前关键词,避免污染搜索结果)
      if (isSearching.value) return
      pushItem(toItem(String(data.value ?? ''), data.changed_at || '', data.source))
    }
  })
})

onUnmounted(() => {
  cleanupWs?.()
})
</script>

<template>
  <div class="clipboard-card">
    <!-- 左侧:输入 -->
    <div class="cp-input-area">
      <h2 class="cp-title">剪切板</h2>
      <n-input
        v-model:value="topic"
        placeholder="主题（可选）"
        clearable
        size="small"
      />
      <n-input
        ref="contentInput"
        v-model:value="content"
        type="textarea"
        :rows="10"
        placeholder="要复制的内容…"
        @keydown.enter.exact.prevent="send"
      />
      <div class="cp-actions">
        <span class="cp-hint">Enter 发送 · Ctrl/⌘ + Enter 换行</span>
        <n-button size="small" type="primary" :loading="sending" @click="send">
          发送
        </n-button>
      </div>
    </div>

    <!-- 右侧:实时历史(支持内容搜索) -->
    <div class="cp-history-area">
      <div class="cp-search-row">
        <n-input
          v-model:value="searchQuery"
          size="small"
          placeholder="搜索主题/内容…"
          clearable
          class="cp-search-input"
        />
        <span v-if="isSearching" class="cp-search-info">
          共 {{ searchTotal }} 条结果
        </span>
      </div>
      <h2 class="cp-title">
        剪切板历史
        <span class="cp-live">
          {{ isSearching ? `搜索「${searchQuery.trim()}」` : `实时 · ${items.length}/${MAX_HISTORY}` }}
        </span>
      </h2>
      <n-empty v-if="items.length === 0" description="暂无剪切板记录" class="cp-empty" />
      <div v-else class="cp-list">
        <div
          v-for="it in items"
          :key="it.uid"
          class="cp-item"
          title="点击复制内容"
          @click="copyContent(it)"
        >
          <n-tag v-if="it.topic" size="tiny" :bordered="false" round type="info" class="cp-topic">
            {{ it.topic }}
          </n-tag>
          <span class="cp-content">{{ it.content }}</span>
          <span class="cp-time">{{ it.changed_at }}</span>
          <n-button size="tiny" quaternary class="cp-copy" @click.stop="copyContent(it)">
            <ion-icon name="copy-outline"></ion-icon>
          </n-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.clipboard-card {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: var(--gap-md);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-card);
  align-items: start;
}

.cp-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.cp-live {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 8px;
}

.cp-input-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cp-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.cp-hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.cp-history-area {
  min-width: 0;
  border-left: 1px solid var(--border-light);
  padding-left: var(--gap-md);
}

.cp-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.cp-search-input {
  flex: 1;
}

.cp-search-info {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.cp-empty {
  padding: 30px 0;
}

.cp-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cp-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s;
}

.cp-item:hover {
  background: var(--border-light);
}

.cp-topic {
  flex-shrink: 0;
}

.cp-content {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cp-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: monospace;
}

.cp-copy {
  flex-shrink: 0;
}

@media (max-width: 1100px) {
  .clipboard-card {
    grid-template-columns: 1fr;
  }
  .cp-history-area {
    border-left: none;
    border-top: 1px solid var(--border-light);
    padding-left: 0;
    padding-top: var(--gap-md);
  }
}
</style>
