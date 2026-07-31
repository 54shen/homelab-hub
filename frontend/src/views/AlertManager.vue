<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">告警规则</h1>
      <n-button type="primary" size="small" @click="openCreate">
        <ion-icon name="add-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
        新增规则
      </n-button>
    </div>

    <n-empty v-if="rules.length === 0" description="暂无告警规则" style="margin-top:60px" />

    <div v-else class="alert-grid">
      <div v-for="r in rules" :key="r.id" class="alert-card" :class="{ disabled: !r.enabled }">
        <div class="ac-header">
          <div class="ac-info">
            <ion-icon v-for="act in r.action.split(',')" :key="act" :name="actionIcon(act)" class="ac-action-icon"></ion-icon>
            <div>
              <span class="ac-name">{{ r.name }}</span>
              <span class="ac-desc">{{ r.description || '无描述' }}</span>
            </div>
          </div>
          <n-switch :value="r.enabled" @update:value="(v: boolean) => handleToggle(r.id, v)" size="small" />
        </div>

        <div class="ac-rule">
          <code class="ac-key">{{ displayKey(r.trigger_key) }}</code>
          <span class="ac-cond">{{ conditionLabel(r.condition) }}</span>
          <code v-if="r.threshold" class="ac-threshold">{{ r.threshold }}</code>
          <ion-icon name="arrow-forward-outline" class="ac-arrow"></ion-icon>
          <n-tag v-for="act in r.action.split(',')" :key="act" size="small" :bordered="false" round :type="actionTagType(act)">{{ actionLabel(act) }}</n-tag>
          <span v-if="r.action_target" class="ac-target">{{ resolveTargetName(r.action, r.action_target) }}</span>
        </div>

        <div class="ac-footer">
          <span v-if="r.last_triggered" class="ac-last">上次触发：{{ r.last_triggered }}</span>
          <span v-else class="ac-last">尚未触发</span>
          <n-space>
            <n-button size="tiny" quaternary @click="openEdit(r)">编辑</n-button>
            <n-popconfirm @positive-click="handleDelete(r.id)">
              <template #trigger><n-button size="tiny" quaternary type="error">删除</n-button></template>
              确定删除此规则？
            </n-popconfirm>
          </n-space>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <n-modal v-model:show="modalVisible" preset="card" :title="editingId ? '编辑规则' : '新增规则'" style="width:560px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="名称" required>
          <n-input v-model:value="form.name" placeholder="例如：CPU 高负载告警" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" placeholder="规则描述（选填）" />
        </n-form-item>

        <!-- 条件 -->
        <n-form-item label="条件" required>
          <n-select v-model:value="form.condition" :options="conditionOptions" style="width:200px" @update:value="onConditionChange" />
        </n-form-item>

        <!-- 监控变量 / 设备选择 -->
        <n-form-item v-if="form.condition !== 'offline'" label="监控变量" required>
          <div class="cascader-row">
            <n-select
              v-model:value="selectedPrefix"
              :options="prefixOptions"
              placeholder="选择设备/前缀"
              filterable
              clearable
              style="flex:1"
              @update:value="onPrefixChange"
            />
            <n-select
              v-model:value="selectedKey"
              :options="keyOptions"
              placeholder="选择变量"
              filterable
              style="flex:2"
              @update:value="onKeySelect"
            />
          </div>
          <template #feedback>
            <span style="font-size:11px;color:var(--text-secondary)">或直接在下方输入完整 key</span>
            <span v-if="form.condition === 'stale'" style="display:block;font-size:11px;color:var(--color-warning);margin-top:4px">
              ⚠ 该 key 的值需为 ISO 8601 时间格式，如 2000-01-01T00:00:00
            </span>
          </template>
        </n-form-item>
        <n-form-item v-if="form.condition !== 'offline'" label="完整 Key">
          <n-input v-model:value="form.trigger_key" placeholder="例如: 大爷的ROG.cpu" size="small" />
        </n-form-item>

        <!-- 离线条件：选设备 -->
        <n-form-item v-if="form.condition === 'offline'" label="监控设备" required>
          <n-select
            v-model:value="selectedDevice"
            :options="deviceOptions"
            placeholder="选择要监控的设备"
            filterable
            @update:value="onDeviceSelect"
          />
        </n-form-item>

        <!-- 阈值 -->
        <n-form-item v-if="form.condition !== 'changed' && form.condition !== 'offline'" :label="form.condition === 'stale' || form.condition === 'unchanged' ? '超时阈值' : '阈值'">
          <n-input v-model:value="form.threshold" :placeholder="form.condition === 'stale' || form.condition === 'unchanged' ? '例如: 3600' : '例如: 80'" style="width:120px" />
          <span v-if="form.condition === 'stale' || form.condition === 'unchanged'" style="margin-left:6px;font-size:13px;color:var(--text-secondary)">秒</span>
        </n-form-item>

        <!-- 动作 -->
        <n-form-item label="动作" class="action-form-item">
          <n-select v-model:value="form.action" :options="actionOptions" multiple style="width:240px" />
        </n-form-item>
        <n-form-item v-if="form.action.includes('webhook')" label="Webhook">
          <n-select
            v-model:value="form.action_target"
            :options="webhookOptions"
            placeholder="选择 Webhook"
            filterable
            style="flex:1"
          />
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
import { alertApi, deviceApi, kvApi, webhookApi } from '../api'
import type { AlertRule, Device, KvEntry, WebhookConfig } from '../types'

const message = useMessage()
const rules = ref<AlertRule[]>([])
const modalVisible = ref(false)
const editingId = ref<number | null>(null)

// ---- 外部数据源 ----
const allKeys = ref<KvEntry[]>([])
const allDevices = ref<Device[]>([])
const allWebhooks = ref<WebhookConfig[]>([])

// ---- 级联选择器状态 ----
const selectedPrefix = ref<string | null>(null)
const selectedKey = ref<string | null>(null)
const selectedDevice = ref<string | null>(null)

// 前缀列表（从 KV keys 提取第一段）
const prefixOptions = computed(() => {
  const prefixes = new Set<string>()
  for (const r of allKeys.value) {
    const dot = r.key.indexOf('.')
    if (dot > 0) prefixes.add(r.key.slice(0, dot))
  }
  return [...prefixes].sort().map(p => ({ label: p, value: p }))
})

// 选中前缀后的变量列表
const keyOptions = computed(() => {
  const pfx = selectedPrefix.value
  if (!pfx) return []
  return allKeys.value
    .filter(r => r.key.startsWith(pfx + '.'))
    .map(r => ({ label: r.key.slice(pfx.length + 1), value: r.key }))
})

// 设备选项
const deviceOptions = computed(() =>
  allDevices.value.map(d => ({ label: d.name, value: `__device__:${d.name}` }))
)

// Webhook 选项（存 ID 到 value，显示只显示名称）
const webhookOptions = computed(() =>
  allWebhooks.value
    .filter(w => w.enabled)
    .map(w => ({ label: w.name, value: `webhook:${w.id}` }))
)

// ---- 表单 ----
const defaultForm = () => ({
  name: '', description: '', trigger_key: '', condition: 'eq' as AlertRule['condition'],
  threshold: '', action: [] as string[], action_target: ''
})
const form = ref(defaultForm())

const conditionOptions = [
  { label: '等于 (==)', value: 'eq' },
  { label: '不等于 (!=)', value: 'neq' },
  { label: '大于 (>)', value: 'gt' },
  { label: '小于 (<)', value: 'lt' },
  { label: '值变化', value: 'changed' },
  { label: '设备离线', value: 'offline' },
  { label: '值超时 (ISO 8601)', value: 'stale' },
  { label: '久未更新', value: 'unchanged' }
]
const actionOptions = [
  { label: 'Webhook', value: 'webhook' },
  { label: '记录日志', value: 'log' }
]

// ---- 级联选择逻辑 ----
function onPrefixChange() {
  selectedKey.value = null
}

function onKeySelect(key: string) {
  form.value.trigger_key = key
}

function onDeviceSelect(val: string) {
  form.value.trigger_key = val
}

function onConditionChange(cond: string) {
  if (cond === 'offline') {
    selectedPrefix.value = null
    selectedKey.value = null
    form.value.trigger_key = ''
    form.value.threshold = ''
  } else {
    selectedDevice.value = null
  }
}

// 初始化级联选择器（编辑时回填）
function initSelectors(rule: Partial<AlertRule>) {
  const key = rule.trigger_key || ''
  if (key.startsWith('__device__:')) {
    selectedDevice.value = key
    selectedPrefix.value = null
    selectedKey.value = null
  } else {
    selectedDevice.value = null
    const dot = key.indexOf('.')
    if (dot > 0) {
      selectedPrefix.value = key.slice(0, dot)
      selectedKey.value = key
    } else {
      selectedPrefix.value = null
      selectedKey.value = null
    }
  }
}

// ---- 显示辅助 ----
function displayKey(key: string): string {
  if (key.startsWith('__device__:')) return key.slice(11)
  return key
}

function resolveTargetName(action: string, target: string): string {
  if (!target) return ''
  if (target.startsWith('webhook:')) {
    const id = parseInt(target.split(':')[1])
    const wh = allWebhooks.value.find(w => w.id === id)
    return wh ? `→ ${wh.name}` : `→ ⚠ 已删除 (ID:${id})`
  }
  return target ? `→ ${target}` : ''
}

// ---- 标签/图标 ----
function conditionLabel(c: AlertRule['condition']) {
  return { eq: '=', neq: '≠', gt: '>', lt: '<', changed: '变更', offline: '离线', stale: '值超时', unchanged: '久未更新' }[c] || c
}
function actionLabel(a: string) {
  return { notification: '🔗 Webhook', webhook: '🔗 Webhook', log: '📝 日志' }[a] || a
}
function actionIcon(a: string) {
  return { notification: 'link-outline', webhook: 'link-outline', log: 'document-text-outline' }[a] || 'flash-outline'
}
function actionTagType(a: string) {
  return { notification: 'info', webhook: 'info', log: 'default' }[a] as 'info' | 'default'
}

// ---- CRUD ----
function openCreate() {
  editingId.value = null
  form.value = defaultForm()
  selectedPrefix.value = null
  selectedKey.value = null
  selectedDevice.value = null
  modalVisible.value = true
}
function openEdit(r: AlertRule) {
  editingId.value = r.id
  form.value = {
    name: r.name, description: r.description,
    trigger_key: r.trigger_key, condition: r.condition,
    threshold: r.threshold, action: r.action ? r.action.split(',') : [],
    action_target: r.action_target
  }
  initSelectors(r)
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.name) return
  if (form.value.condition !== 'offline' && !form.value.trigger_key) return
  if (form.value.condition === 'offline' && !form.value.trigger_key) return
  if (form.value.action.length === 0) return
  const payload = { ...form.value, action: form.value.action.join(',') }
  try {
    if (editingId.value) {
      await alertApi.update(editingId.value, payload)
    } else {
      await alertApi.create(payload)
    }
    modalVisible.value = false
    message.success('保存成功')
    await loadData()
  } catch { message.error('保存失败') }
}

async function handleToggle(id: number, enabled: boolean) {
  try { await alertApi.toggle(id, enabled); await loadData() } catch { /* */ }
}
async function handleDelete(id: number) {
  try { await alertApi.delete(id); message.success('已删除'); await loadData() } catch { message.error('删除失败') }
}

// ---- 数据加载 ----
async function loadData() {
  try {
    const [aRes, kRes, dRes, wRes] = await Promise.all([
      alertApi.list(),
      kvApi.list(),
      deviceApi.list(),
      webhookApi.list()
    ])
    if (aRes.data) rules.value = aRes.data
    if (kRes.data) allKeys.value = kRes.data
    if (dRes.data) allDevices.value = dRes.data
    if (wRes.data) allWebhooks.value = wRes.data
  } catch {
    rules.value = []
  }
}

onMounted(loadData)
</script>

<style scoped>
.action-form-item :deep(.n-base-selection-tags) {
  display: flex; flex-wrap: wrap; gap: 4px;
}
.action-form-item :deep(.n-base-selection-tags .n-tag) {
  max-width: none; margin: 0;
}
.alert-grid { display: flex; flex-direction: column; gap: var(--gap-sm); }

.alert-card {
  background: var(--bg-card); border: 1px solid var(--border-card);
  border-radius: var(--radius-lg); padding: 16px 20px;
  box-shadow: var(--shadow-card); transition: all 0.2s ease;
}
.alert-card.disabled { opacity: 0.5; }

.ac-header { display: flex; align-items: flex-start; justify-content: space-between; }
.ac-info { display: flex; align-items: flex-start; gap: 10px; }
.ac-action-icon { font-size: 22px; color: var(--color-info); margin-top: 2px; }
.ac-name { display: block; font-size: 15px; font-weight: 600; color: var(--text-primary); }
.ac-desc { display: block; font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

.ac-rule {
  display: flex; align-items: center; gap: 8px; margin-top: 12px;
  padding: 10px 14px; background: var(--bg-page); border-radius: var(--radius-sm); font-size: 13px;
  flex-wrap: wrap;
}
.ac-key {
  font-family: monospace; font-size: 13px; color: var(--color-info);
  background: rgba(91, 141, 239, 0.08); padding: 2px 8px; border-radius: var(--radius-xs);
}
.ac-cond { color: var(--text-secondary); font-weight: 600; }
.ac-threshold { font-family: monospace; color: var(--color-warning); }
.ac-arrow { color: var(--text-secondary); }
.ac-target { font-size: 12px; color: var(--text-secondary); margin-left: 4px; }

.ac-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.ac-last { font-size: 11px; color: var(--text-secondary); }

.cascader-row { display: flex; gap: 8px; width: 100%; }
</style>
