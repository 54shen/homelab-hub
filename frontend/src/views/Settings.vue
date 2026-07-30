<template>
  <div class="page-container">
    <h1 class="page-title">设置</h1>

    <!-- Token 管理 -->
    <n-card title="Token 管理" size="small" style="margin-bottom:16px">
      <template #header-extra>
        <n-button size="tiny" type="primary" @click="openTokenCreate">新增 Token</n-button>
      </template>
      <n-data-table
        v-if="tokens.length > 0"
        :columns="tokenColumns"
        :data="tokens"
        :bordered="false"
        size="small"
        :pagination="false"
      />
      <n-empty v-else description="暂无 Token" style="margin:20px 0" />
    </n-card>

    <div class="settings-grid">
      <!-- 系统设置 -->
      <n-card title="系统设置" size="small">
        <n-form label-placement="left" label-width="120px">
          <n-form-item label="清理间隔">
            <n-select v-model:value="sysSettings.cleanupInterval" :options="intervalOptions" style="width:160px" />
          </n-form-item>
          <n-form-item label="默认保留天数">
            <n-input-number v-model:value="sysSettings.defaultRetention" :min="1" :max="3650" style="width:160px" />
            <span style="margin-left:8px;font-size:12px;color:var(--text-secondary)">天</span>
          </n-form-item>
          <n-form-item label="心跳超时">
            <n-input-number v-model:value="sysSettings.heartbeatTimeout" :min="10" :max="600" style="width:160px" />
            <span style="margin-left:8px;font-size:12px;color:var(--text-secondary)">秒</span>
          </n-form-item>
          <n-button type="primary" size="small">保存设置</n-button>
        </n-form>
      </n-card>

      <!-- 会话管理 -->
      <n-card title="活跃会话" size="small">
        <n-data-table
          v-if="sessions.length > 0"
          :columns="sessionColumns"
          :data="sessions"
          :bordered="false"
          size="small"
          :pagination="false"
        />
        <n-empty v-else description="暂无活跃会话" style="margin:20px 0" />
      </n-card>

      <!-- 数据库维护 -->
      <n-card title="数据库维护" size="small">
        <n-descriptions label-placement="left" :column="1" bordered size="small">
          <n-descriptions-item label="文件大小">{{ dbStatus.file_size }}</n-descriptions-item>
          <n-descriptions-item label="总变量数">{{ dbStatus.total_keys }}</n-descriptions-item>
          <n-descriptions-item label="24h 活跃">{{ dbStatus.active_keys_24h }}</n-descriptions-item>
          <n-descriptions-item label="历史记录">{{ dbStatus.history_count }} 条</n-descriptions-item>
        </n-descriptions>
        <n-space style="margin-top: 16px">
          <n-button size="small" @click="handleCleanHistory">手动清理过期数据</n-button>
          <n-button size="small" @click="handleBackup">导出完整备份</n-button>
        </n-space>
      </n-card>
    </div>

    <!-- Token 编辑弹窗 -->
    <n-modal v-model:show="tokenModalVisible" preset="card" :title="editingTokenId ? '编辑 Token' : '新增 Token'" style="width:440px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="备注名" required>
          <n-input v-model:value="tokenForm.name" placeholder="描述用途，如 windows-agent" />
        </n-form-item>
        <n-form-item label="权限">
          <n-select v-model:value="tokenForm.permission" :options="permissionOptions" />
        </n-form-item>
        <n-form-item v-if="tokenForm.tokenStr" label="Token">
          <n-input v-model:value="tokenForm.tokenStr" readonly />
          <n-button size="tiny" style="margin-left:8px" @click="copyToken">复制</n-button>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="tokenModalVisible = false">取消</n-button>
          <n-button type="primary" @click="handleTokenSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import {
  NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem, NEmpty,
  NForm, NFormItem, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, useMessage
} from 'naive-ui'
import { dashboardApi, settingsApi } from '../api'
import axios from 'axios'
import type { DbStatus } from '../types'

const message = useMessage()
const base = import.meta.env.VITE_API_BASE || '/api'

// ---- Token ----
interface TokenEntry {
  id: number; name: string; token: string; token_full: string; permission: string; created_at: string
}
const tokens = ref<TokenEntry[]>([])
const tokenModalVisible = ref(false)
const editingTokenId = ref<number | null>(null)
const tokenForm = ref({ name: '', permission: 'read', tokenStr: '' })

const permissionOptions = [
  { label: 'read — 只读', value: 'read' },
  { label: 'write — 读写', value: 'write' },
  { label: 'admin — 管理', value: 'admin' }
]

const tokenColumns = [
  { title: '备注', key: 'name', width: 160 },
  { title: 'Token', key: 'token', width: 160 },
  { title: '权限', key: 'permission', width: 80 },
  { title: '创建时间', key: 'created_at', width: 160 },
  {
    title: '操作', key: 'actions', width: 120,
    render(row: TokenEntry) {
      return h('div', { style: 'display:flex;gap:4px' }, [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openTokenEdit(row) }, { default: () => '编辑' }),
        h(NPopconfirm, { onPositiveClick: () => handleTokenDelete(row.id) }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除？'
        })
      ])
    }
  }
]

function openTokenCreate() {
  editingTokenId.value = null
  tokenForm.value = { name: '', permission: 'read', tokenStr: '' }
  tokenModalVisible.value = true
}

function openTokenEdit(row: TokenEntry) {
  editingTokenId.value = row.id
  tokenForm.value = { name: row.name, permission: row.permission, tokenStr: '' }
  tokenModalVisible.value = true
}

async function handleTokenSave() {
  try {
    if (editingTokenId.value) {
      await axios.put(`${base}/tokens/${editingTokenId.value}`, {
        name: tokenForm.value.name,
        permission: tokenForm.value.permission
      })
      message.success('已更新')
    } else {
      const resp = await axios.post(`${base}/tokens`, {
        name: tokenForm.value.name,
        permission: tokenForm.value.permission
      })
      tokenForm.value.tokenStr = resp.data.token
      message.success('Token 已生成，请复制保存！')
      // 不关闭弹窗，让用户复制
      return
    }
    tokenModalVisible.value = false
    await loadTokens()
  } catch { message.error('操作失败') }
}

async function handleTokenDelete(id: number) {
  try {
    await axios.delete(`${base}/tokens/${id}`)
    message.success('已删除')
    await loadTokens()
  } catch { message.error('删除失败') }
}

function copyToken() {
  navigator.clipboard.writeText(tokenForm.value.tokenStr)
  message.success('已复制到剪贴板')
}

async function loadTokens() {
  try {
    const resp = await axios.get(`${base}/tokens`)
    tokens.value = resp.data
  } catch { tokens.value = [] }
}

// ---- 会话管理 ----
interface SessionEntry { id: number; username: string; permission: string; ip: string; created_at: string; last_active: string }
const sessions = ref<SessionEntry[]>([])

const sessionColumns = [
  { title: '用户', key: 'username', width: 120 },
  { title: '权限', key: 'permission', width: 70 },
  { title: '登录时间', key: 'created_at', width: 160 },
  { title: '最后活跃', key: 'last_active', width: 160 },
  {
    title: '操作', key: 'actions', width: 80,
    render(row: SessionEntry) {
      return h(NPopconfirm, { onPositiveClick: () => handleKickSession(row.id) }, {
        trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '踢掉' }),
        default: () => '确定踢掉该会话？'
      })
    }
  }
]

async function handleKickSession(id: number) {
  try {
    await axios.delete(`${base}/sessions/${id}`)
    message.success('已踢掉')
    await loadSessions()
  } catch { message.error('操作失败') }
}

async function loadSessions() {
  try {
    const resp = await axios.get(`${base}/sessions`)
    sessions.value = resp.data
  } catch { sessions.value = [] }
}

// ---- 数据库 ----
const sysSettings = ref({ cleanupInterval: '24h', defaultRetention: 180, heartbeatTimeout: 60 })
const intervalOptions = [
  { label: '每 1 小时', value: '1h' }, { label: '每 6 小时', value: '6h' },
  { label: '每 12 小时', value: '12h' }, { label: '每天', value: '24h' }
]

const dbStatus = ref<DbStatus>({ file_size: '--', total_keys: 0, active_keys_24h: 0, history_count: 0 })

async function loadDbStatus() {
  try {
    const res = await dashboardApi.dbStatus()
    if (res.data) dbStatus.value = res.data
  } catch { /* */ }
}

async function handleCleanHistory() {
  try { await settingsApi.cleanHistory(); await loadDbStatus(); message.success('清理完成') } catch { /* */ }
}

async function handleBackup() {
  try {
    const res = await settingsApi.exportBackup()
    const blob = new Blob([res.data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `backup_${new Date().toISOString().slice(0, 10)}.json`
    a.click(); URL.revokeObjectURL(url)
  } catch { /* */ }
}

onMounted(() => { loadTokens(); loadSessions(); loadDbStatus() })
</script>

<style scoped>
.settings-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--gap-md); }
</style>
