<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Webhook</h1>
      <n-button type="primary" size="small" @click="openCreate">
        <ion-icon name="add-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
        新增 Webhook
      </n-button>
    </div>

    <n-empty v-if="webhooks.length === 0" description="暂无 Webhook" style="margin-top:60px" />

    <div v-else class="webhook-grid">
      <div v-for="w in webhooks" :key="w.id" class="webhook-card" :class="{ disabled: !w.enabled }">
        <div class="wc-header">
          <div class="wc-info">
            <span class="wc-name">{{ w.name }}</span>
            <span class="wc-method">
              <n-tag size="tiny" :bordered="false" round :type="methodType(w.method)">{{ w.method }}</n-tag>
            </span>
          </div>
          <n-switch :value="w.enabled" @update:value="(v: boolean) => handleToggle(w.id, v)" size="small" />
        </div>

        <code class="wc-url">{{ w.url }}</code>

        <div class="wc-events">
          <n-tag v-for="ev in w.event_types" :key="ev" size="tiny" :bordered="false" round>{{ ev }}</n-tag>
          <span v-if="!w.event_types.length" class="no-events">所有事件</span>
        </div>

        <div class="wc-footer">
          <div class="wc-stats">
            <span v-if="w.last_sent">上次发送：{{ w.last_sent }}</span>
            <span v-else>尚未发送</span>
            <span v-if="w.fail_count > 0" class="fail-count">失败 {{ w.fail_count }} 次</span>
          </div>
          <n-space>
            <n-button size="tiny" quaternary @click="handleTest(w.id)">测试</n-button>
            <n-button size="tiny" quaternary @click="openEdit(w)">编辑</n-button>
            <n-popconfirm @positive-click="handleDelete(w.id)">
              <template #trigger><n-button size="tiny" quaternary type="error">删除</n-button></template>
              确定删除此 Webhook？
            </n-popconfirm>
          </n-space>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <n-modal v-model:show="modalVisible" preset="card" :title="editingId ? '编辑 Webhook' : '新增 Webhook'" style="width:520px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="名称" required>
          <n-input v-model:value="form.name" placeholder="例如：微信通知" />
        </n-form-item>
        <n-form-item label="URL" required>
          <n-input v-model:value="form.url" placeholder="https://..." />
        </n-form-item>
        <n-form-item label="方法">
          <n-select v-model:value="form.method" :options="methodOptions" style="width:120px" />
        </n-form-item>
        <n-form-item label="事件类型">
          <n-select
            v-model:value="form.event_types"
            :options="eventTypeOptions"
            multiple
            placeholder="选择事件类型（留空=全部）"
          />
        </n-form-item>
        <n-form-item label="Headers">
          <n-input v-model:value="headersText" type="textarea" placeholder='{"Content-Type": "application/json"}' :autosize="{ minRows: 2, maxRows: 4 }" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="modalVisible = false">取消</n-button>
          <n-button type="primary" @click="handleSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton, NEmpty, NForm, NFormItem, NInput, NModal,
  NPopconfirm, NSelect, NSpace, NSwitch, NTag, useMessage
} from 'naive-ui'
import { webhookApi } from '../api'
import type { WebhookConfig } from '../types'

const message = useMessage()
const webhooks = ref<WebhookConfig[]>([])
const modalVisible = ref(false)
const editingId = ref<number | null>(null)
const headersText = ref('')

const defaultForm = () => ({
  name: '', url: '', method: 'POST' as WebhookConfig['method'],
  event_types: [] as string[], headers: {} as Record<string, string>
})
const form = ref(defaultForm())

const methodOptions = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' }
]
const eventTypeOptions = [
  { label: '设备上线', value: 'device.online' },
  { label: '设备离线', value: 'device.offline' },
  { label: '变量变更', value: 'kv.changed' },
  { label: '变量新增', value: 'kv.created' },
  { label: '变量删除', value: 'kv.deleted' },
  { label: '告警触发', value: 'alert.triggered' }
]

function methodType(m: string) {
  return { GET: 'info', POST: 'success', PUT: 'warning' }[m] as 'info' | 'success' | 'warning'
}

const headersParsed = computed(() => {
  try { return JSON.parse(headersText.value) }
  catch { return {} }
})

function openCreate() {
  editingId.value = null
  form.value = defaultForm()
  headersText.value = ''
  modalVisible.value = true
}

function openEdit(w: WebhookConfig) {
  editingId.value = w.id
  form.value = {
    name: w.name, url: w.url, method: w.method,
    event_types: [...w.event_types], headers: { ...w.headers }
  }
  headersText.value = JSON.stringify(w.headers, null, 2)
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.url) return
  try {
    const data = { ...form.value, headers: headersParsed.value }
    if (editingId.value) {
      await webhookApi.update(editingId.value, data)
    } else {
      await webhookApi.create(data)
    }
    modalVisible.value = false
    message.success('保存成功')
    await loadData()
  } catch { message.error('保存失败') }
}

async function handleToggle(id: number, enabled: boolean) {
  try {
    await webhookApi.update(id, { enabled } as Partial<WebhookConfig>)
    await loadData()
  } catch { /* */ }
}

async function handleTest(id: number) {
  try {
    await webhookApi.test(id)
    message.success('测试请求已发送')
  } catch { message.error('测试失败') }
}

async function handleDelete(id: number) {
  try {
    await webhookApi.delete(id)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
}

async function loadData() {
  try {
    const res = await webhookApi.list()
    if (res.data) webhooks.value = res.data
  } catch { webhooks.value = [] }
}

onMounted(loadData)
</script>

<style scoped>
.webhook-grid {
  display: flex;
  flex-direction: column;
  gap: var(--gap-sm);
}

.webhook-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}
.webhook-card.disabled {
  opacity: 0.5;
}

.wc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wc-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wc-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.wc-url {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  font-family: monospace;
  padding: 8px 12px;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
  margin-top: 10px;
  word-break: break-all;
}

.wc-events {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.no-events {
  font-size: 11px;
  color: var(--text-secondary);
}

.wc-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.wc-stats {
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  gap: 12px;
}
.fail-count {
  color: var(--color-danger);
  font-weight: 600;
}
</style>
