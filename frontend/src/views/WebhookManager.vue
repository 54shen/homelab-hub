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
          <template #feedback>
            <div class="body-help" style="margin-top:4px">
              <span class="body-help-title">支持变量拼接：</span>
              <code>{<!-- -->{ip}}</code>触发设备IP
              <code>{<!-- -->{device}}</code>触发设备名
              <code>{<!-- -->{ip:设备名}}</code>指定设备IP
              <code>{<!-- -->{mac:设备名}}</code>指定设备MAC
            </div>
          </template>
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
        <n-form-item label="Body">
          <n-input v-model:value="bodyText" type="textarea"
            placeholder="留空 = 默认格式。用 {{rule_body}} 接收规则的 Body+ 内容"
            :autosize="{ minRows: 6, maxRows: 14 }"
          />
          <template #feedback>
            <div class="body-help">
              <div class="body-help-title">JSON 合并：Body + Body+ → 拼成一个 JSON 发送</div>
            </div>
          </template>
        </n-form-item>
        <n-form-item>
          <template #label>
            Body+<br />(默认)
          </template>
          <n-input v-model:value="bodyExtraText" type="textarea"
            placeholder="留空 = 无默认内容。规则未填 Body+ 时使用此模板，支持全部告警变量"
            :autosize="{ minRows: 3, maxRows: 8 }"
          />
          <template #feedback>
            <div class="body-help" style="margin-top:2px">
              <span class="body-help-title">与 Body 合并发送。规则未配 Body+ 时使用此默认</span>
            </div>
              <div class="body-help" style="margin-top:6px">
              <div class="body-help-title">通用变量</div>
              <code>{<!-- -->{event}}</code> 事件类型
              <code>{<!-- -->{timestamp}}</code> 时间戳
              <code>{<!-- -->{webhook}}</code> Webhook名称
              <code>{<!-- -->{data}}</code> 格式化事件文本
            </div>
            <div class="body-help" style="margin-top:6px">
              <div class="body-help-title">告警字段（独立变量）</div>
              <code>{<!-- -->{alert}}</code> 告警规则
              <code>{<!-- -->{key}}</code> 监控变量
              <code>{<!-- -->{condition}}</code> 触发条件
              <code>{<!-- -->{threshold}}</code> 阈值
              <code>{<!-- -->{old_value}}</code> 旧值
              <code>{<!-- -->{new_value}}</code> 新值
              <code>{<!-- -->{elapsed_seconds}}</code> 已过秒数
              <code>{<!-- -->{device}}</code> 设备名称
              <code>{<!-- -->{status}}</code> 设备状态
              <code>{<!-- -->{通知时间}}</code> 通知时间
            </div>
          </template>
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
const bodyText = ref('')
const bodyExtraText = ref('')

const defaultForm = () => ({
  name: '', url: '', method: 'POST' as WebhookConfig['method'],
  event_types: [] as string[], headers: {} as Record<string, string>, body: '', body_extra: ''
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
  bodyText.value = ''
  bodyExtraText.value = ''
  modalVisible.value = true
}

function openEdit(w: WebhookConfig) {
  editingId.value = w.id
  form.value = {
    name: w.name, url: w.url, method: w.method,
    event_types: [...w.event_types], headers: { ...w.headers }, body: w.body || '', body_extra: w.body_extra || ''
  }
  headersText.value = JSON.stringify(w.headers, null, 2)
  bodyText.value = w.body || ''
  bodyExtraText.value = w.body_extra || ''
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.url) return
  try {
    const data = { ...form.value, headers: headersParsed.value, body: bodyText.value, body_extra: bodyExtraText.value }
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

// ---- Body 预设示例 ----
const BODY_EXAMPLES: Record<string, string> = {
  feishu: JSON.stringify({
    msg_type: "interactive",
    card: {
      header: { title: { tag: "plain_text", content: "Shared Center 通知" } },
      elements: [
        { tag: "div", text: { tag: "lark_md", content: "**事件：**{{event}}\n**时间：**{{timestamp}}\n**详情：**{{data}}" } }
      ]
    }
  }, null, 2),
  wecom: JSON.stringify({
    msgtype: "markdown",
    markdown: { content: `## Shared Center 通知\n> 事件：<font color="info">{{event}}</font>\n> 时间：{{timestamp}}\n> 详情：{{data}}` }
  }, null, 2),
  dingtalk: JSON.stringify({
    msgtype: "markdown",
    markdown: { title: "Shared Center", text: `### 通知\n- 事件：{{event}}\n- 时间：{{timestamp}}\n- 详情：{{data}}` }
  }, null, 2),
  bark: JSON.stringify({
    title: "Shared Center",
    body: "事件：{{event}}\n时间：{{timestamp}}\n详情：{{data}}",
    group: "SharedCenter",
    sound: "bell"
  }, null, 2),
  pushdeer: JSON.stringify({
    text: "Shared Center",
    desp: `### 通知\n\n**事件：**{{event}}\n\n**时间：**{{timestamp}}\n\n**详情：**\n\`\`\`json\n{{data}}\n\`\`\``,
    type: "markdown"
  }, null, 2),
  clear: ""
}

function setBodyExample(key: string) {
  bodyText.value = BODY_EXAMPLES[key] || ''
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

.body-help {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.8;
}
.body-help code {
  background: #F1F5F9;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  margin-right: 6px;
}
.body-help-title {
  font-weight: 600;
  margin-right: 4px;
}
</style>
