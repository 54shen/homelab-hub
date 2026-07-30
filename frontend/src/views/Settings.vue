<template>
  <div class="page-container">
    <h1 class="page-title">设置</h1>

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

      <!-- Token 管理 -->
      <n-card title="Token 管理" size="small">
        <template #header-extra>
          <n-button size="tiny" type="primary" @click="showTokenModal = true">新增</n-button>
        </template>
        <n-empty v-if="tokens.length === 0" description="暂无 Token" style="margin:20px 0" />
        <div v-else class="token-list">
          <div v-for="(t, i) in tokens" :key="t.name" class="token-item">
            <div class="token-info">
              <span class="token-name">{{ t.name }}</span>
              <code class="token-value">{{ t.masked }}</code>
            </div>
            <n-button size="tiny" type="error" quaternary @click="tokens.splice(i, 1)">删除</n-button>
          </div>
        </div>
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

    <!-- 新增 Token 弹窗 -->
    <n-modal v-model:show="showTokenModal" preset="card" title="新增 Token" style="width:400px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="名称" required>
          <n-input v-model:value="newTokenName" placeholder="例如: windows-agent" />
        </n-form-item>
        <n-form-item label="权限">
          <n-select
            v-model:value="newTokenPermission"
            :options="permissionOptions"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showTokenModal = false">取消</n-button>
          <n-button type="primary" @click="handleAddToken">生成</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NButton, NCard, NDescriptions, NDescriptionsItem, NEmpty, NForm,
  NFormItem, NInput, NInputNumber, NModal, NSelect, NSpace
} from 'naive-ui'
import { dashboardApi, settingsApi } from '../api'
import type { DbStatus } from '../types'

// ---- 系统设置 ----
const sysSettings = ref({
  cleanupInterval: '24h',
  defaultRetention: 180,
  heartbeatTimeout: 60
})

const intervalOptions = [
  { label: '每小时', value: '1h' },
  { label: '每 6 小时', value: '6h' },
  { label: '每 12 小时', value: '12h' },
  { label: '每天', value: '24h' }
]

// ---- Token ----
interface TokenEntry {
  name: string
  masked: string
  permission: string
}
const tokens = ref<TokenEntry[]>([])
const showTokenModal = ref(false)
const newTokenName = ref('')
const newTokenPermission = ref('read')

const permissionOptions = [
  { label: 'read — 只读', value: 'read' },
  { label: 'write — 读写', value: 'write' },
  { label: 'admin — 管理', value: 'admin' }
]

function handleAddToken() {
  if (!newTokenName.value) return
  tokens.value.push({
    name: newTokenName.value,
    masked: 'sk-' + '•'.repeat(32),
    permission: newTokenPermission.value
  })
  newTokenName.value = ''
  showTokenModal.value = false
}

// ---- 数据库 ----
const dbStatus = ref<DbStatus>({
  file_size: '--',
  total_keys: 0,
  active_keys_24h: 0,
  history_count: 0
})

async function loadDbStatus() {
  try {
    const res = await dashboardApi.dbStatus()
    if (res.data) dbStatus.value = res.data
  } catch { /* 后端未启动 */ }
}

async function handleCleanHistory() {
  try {
    await settingsApi.cleanHistory()
    await loadDbStatus()
  } catch { /* */ }
}

async function handleBackup() {
  try {
    const res = await settingsApi.exportBackup()
    const blob = new Blob([res.data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `backup_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch { /* */ }
}

onMounted(loadDbStatus)
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--gap-md);
}

.token-list {
  display: flex;
  flex-direction: column;
}
.token-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
}
.token-item:last-child {
  border-bottom: none;
}
.token-name {
  font-weight: 500;
  font-size: 13px;
}
.token-value {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
  letter-spacing: 1px;
}
</style>
