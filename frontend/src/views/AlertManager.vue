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
            <ion-icon :name="actionIcon(r.action)" class="ac-action-icon"></ion-icon>
            <div>
              <span class="ac-name">{{ r.name }}</span>
              <span class="ac-desc">{{ r.description || '无描述' }}</span>
            </div>
          </div>
          <n-switch :value="r.enabled" @update:value="(v: boolean) => handleToggle(r.id, v)" size="small" />
        </div>

        <div class="ac-rule">
          <code class="ac-key">{{ r.trigger_key }}</code>
          <span class="ac-cond">{{ conditionLabel(r.condition) }}</span>
          <code class="ac-threshold">{{ r.threshold }}</code>
          <ion-icon name="arrow-forward-outline" class="ac-arrow"></ion-icon>
          <n-tag size="small" :bordered="false" round :type="actionTagType(r.action)">{{ actionLabel(r.action) }}</n-tag>
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
    <n-modal v-model:show="modalVisible" preset="card" :title="editingId ? '编辑规则' : '新增规则'" style="width:520px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="名称" required>
          <n-input v-model:value="form.name" placeholder="例如：PC离线通知" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" placeholder="规则描述" />
        </n-form-item>
        <n-form-item label="监控变量" required>
          <n-input v-model:value="form.trigger_key" placeholder="例如: pc.online" />
        </n-form-item>
        <n-form-item label="条件">
          <n-select v-model:value="form.condition" :options="conditionOptions" style="width:140px" />
          <n-input v-model:value="form.threshold" placeholder="阈值" style="width:120px;margin-left:8px" />
        </n-form-item>
        <n-form-item label="动作">
          <n-select v-model:value="form.action" :options="actionOptions" style="width:140px" />
          <n-input v-model:value="form.action_target" placeholder="目标（Webhook名称等）" style="width:160px;margin-left:8px" />
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
import { onMounted, ref } from 'vue'
import {
  NButton, NEmpty, NForm, NFormItem, NInput, NModal,
  NPopconfirm, NSelect, NSpace, NSwitch, NTag, useMessage
} from 'naive-ui'
import { alertApi } from '../api'
import type { AlertRule } from '../types'

const message = useMessage()
const rules = ref<AlertRule[]>([])
const modalVisible = ref(false)
const editingId = ref<number | null>(null)

const defaultForm = () => ({
  name: '', description: '', trigger_key: '', condition: 'eq' as AlertRule['condition'],
  threshold: '', action: 'notification' as AlertRule['action'], action_target: ''
})
const form = ref(defaultForm())

const conditionOptions = [
  { label: '等于 (==)', value: 'eq' },
  { label: '不等于 (!=)', value: 'neq' },
  { label: '大于 (>)', value: 'gt' },
  { label: '小于 (<)', value: 'lt' },
  { label: '值变化', value: 'changed' },
  { label: '设备离线', value: 'offline' }
]
const actionOptions = [
  { label: '通知', value: 'notification' },
  { label: 'Webhook', value: 'webhook' },
  { label: '记录日志', value: 'log' }
]

function conditionLabel(c: AlertRule['condition']) {
  return { eq: '=', neq: '≠', gt: '>', lt: '<', changed: '变更', offline: '离线' }[c] || c
}
function actionLabel(a: AlertRule['action']) {
  return { notification: '📢 通知', webhook: '🔗 Webhook', log: '📝 日志' }[a] || a
}
function actionIcon(a: AlertRule['action']) {
  return { notification: 'notifications-outline', webhook: 'link-outline', log: 'document-text-outline' }[a] || 'flash-outline'
}
function actionTagType(a: AlertRule['action']) {
  return { notification: 'warning', webhook: 'info', log: 'default' }[a] as 'warning' | 'info' | 'default'
}

function openCreate() {
  editingId.value = null
  form.value = defaultForm()
  modalVisible.value = true
}
function openEdit(r: AlertRule) {
  editingId.value = r.id
  form.value = { name: r.name, description: r.description, trigger_key: r.trigger_key, condition: r.condition, threshold: r.threshold, action: r.action, action_target: r.action_target }
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.trigger_key) return
  try {
    if (editingId.value) {
      await alertApi.update(editingId.value, form.value)
    } else {
      await alertApi.create(form.value)
    }
    modalVisible.value = false
    message.success('保存成功')
    await loadData()
  } catch { message.error('保存失败') }
}

async function handleToggle(id: number, enabled: boolean) {
  try {
    await alertApi.toggle(id, enabled)
    await loadData()
  } catch { /* */ }
}

async function handleDelete(id: number) {
  try {
    await alertApi.delete(id)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
}

async function loadData() {
  try {
    const res = await alertApi.list()
    if (res.data) rules.value = res.data
  } catch { rules.value = [] }
}

onMounted(loadData)
</script>

<style scoped>
.alert-grid {
  display: flex;
  flex-direction: column;
  gap: var(--gap-sm);
}

.alert-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}
.alert-card.disabled {
  opacity: 0.5;
}

.ac-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.ac-info {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.ac-action-icon {
  font-size: 22px;
  color: var(--color-info);
  margin-top: 2px;
}
.ac-name {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.ac-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.ac-rule {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.ac-key {
  font-family: monospace;
  font-size: 13px;
  color: var(--color-info);
  background: rgba(91, 141, 239, 0.08);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
}
.ac-cond {
  color: var(--text-secondary);
  font-weight: 600;
}
.ac-threshold {
  font-family: monospace;
  color: var(--color-warning);
}
.ac-arrow {
  color: var(--text-secondary);
}

.ac-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.ac-last {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
