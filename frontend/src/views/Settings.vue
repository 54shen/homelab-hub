<template>
  <div class="page-container">
    <h1 class="page-title">设置</h1>

    <!-- 修改密码 -->
    <n-card title="修改密码" size="small" style="margin-bottom:16px">
      <n-form label-placement="left" label-width="80px" style="max-width:400px">
        <n-form-item label="旧密码">
          <n-input v-model:value="pwForm.oldPassword" type="password" placeholder="输入旧密码" />
        </n-form-item>
        <n-form-item label="新密码">
          <n-input v-model:value="pwForm.newPassword" type="password" placeholder="至少4位" />
        </n-form-item>
        <n-button type="primary" size="small" :loading="pwLoading" @click="handleChangePassword">修改密码</n-button>
      </n-form>
    </n-card>

    <!-- 二次验证(TOTP) -->
    <n-card title="二次验证" size="small" style="margin-bottom:16px">
      <div v-if="!twofaEnabled" class="twofa-row">
        <div class="twofa-desc">
          <p>使用手机验证器 App(Google Authenticator / Microsoft Authenticator 等)扫码绑定后,登录除密码外还需输入 6 位动态验证码。</p>
          <n-button size="small" type="primary" :loading="twofaLoading" @click="startTwofaSetup">启用</n-button>
        </div>
        <div v-if="twofaSetupUri" class="twofa-setup">
          <img :src="twofaQr" alt="2FA 二维码" style="width:170px;height:170px;border:1px solid var(--border-card);border-radius:8px" />
          <div class="twofa-secret">
            <span style="font-size:12px;color:var(--text-secondary)">密钥(备选手动输入):</span>
            <code>{{ twofaSecret }}</code>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <n-input
              v-model:value="twofaConfirmCode"
              placeholder="输入 App 的 6 位验证码"
              maxlength="6"
              size="small"
              style="width:200px"
            />
            <n-button size="small" type="primary" :loading="twofaLoading" @click="confirmTwofa">确认启用</n-button>
          </div>
        </div>
      </div>
      <div v-else class="twofa-row">
        <span style="color:var(--color-success);font-size:13px">✅ 已启用 —— 登录时需要输入手机 App 的动态验证码</span>
        <n-button size="small" type="error" ghost @click="twofaDisableMode = !twofaDisableMode">关闭</n-button>
        <div v-if="twofaDisableMode" style="display:flex;gap:8px;align-items:center;margin-top:8px">
          <n-input
            v-model:value="twofaConfirmCode"
            placeholder="输入验证码确认关闭"
            maxlength="6"
            size="small"
            style="width:200px"
          />
          <n-button size="small" type="error" :loading="twofaLoading" @click="disableTwofa">确认关闭</n-button>
        </div>
      </div>
    </n-card>

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
      <!-- 用户管理 -->
      <n-card title="用户管理" size="small" style="margin-bottom:16px">
        <template #header-extra>
          <n-button size="tiny" type="primary" @click="openUserCreate">新增用户</n-button>
        </template>
        <n-data-table
          v-if="users.length > 0"
          :columns="userColumns"
          :data="users"
          :bordered="false"
          size="small"
          :pagination="false"
        />
        <n-empty v-else description="暂无用户" style="margin:20px 0" />
      </n-card>

      <n-card title="活跃会话" size="small">
        <template #header-extra>
          <n-popconfirm v-if="sessions.length > 1" @positive-click="handleKickAll">
            <template #trigger>
              <n-button size="tiny" type="error" quaternary>踢掉所有</n-button>
            </template>
            确定踢掉除自己之外的所有会话？
          </n-popconfirm>
        </template>
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
          <n-descriptions-item label="历史记录">已移除</n-descriptions-item>
        </n-descriptions>
        <n-space style="margin-top: 16px">
          <n-button size="small" @click="handleBackup">导出完整备份</n-button>
          <n-upload :show-file-list="false" accept=".json" @change="handleRestore">
            <n-button size="small">恢复备份</n-button>
          </n-upload>
        </n-space>
      </n-card>
    </div>

    <!-- 用户编辑弹窗 -->
    <n-modal v-model:show="userModalVisible" preset="card" :title="editingUserId ? '编辑用户' : '新增用户'" style="width:400px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="用户名" required>
          <n-input v-model:value="userForm.username" :disabled="!!editingUserId" placeholder="登录账号" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="userForm.password" type="password" :placeholder="editingUserId ? '留空不修改' : '至少4位'" />
        </n-form-item>
        <n-form-item label="权限">
          <n-select v-model:value="userForm.permission" :options="permissionOptions" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="userModalVisible = false">取消</n-button>
          <n-button type="primary" @click="handleUserSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>

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
  NForm, NFormItem, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NUpload,
  useMessage, type UploadFileInfo
} from 'naive-ui'
import { authApi, dashboardApi, settingsApi } from '../api'
import http from '../api'
import QRCode from 'qrcode'
import type { DbStatus } from '../types'

const message = useMessage()

// ---- 二次验证(TOTP) ----
const twofaEnabled = ref(false)
const twofaLoading = ref(false)
const twofaSetupUri = ref('')
const twofaSecret = ref('')
const twofaQr = ref('')
const twofaConfirmCode = ref('')
const twofaDisableMode = ref(false)

async function loadTwofaStatus() {
  try {
    const res = await authApi.twofaStatus()
    twofaEnabled.value = !!res.data?.enabled
  } catch { /* 未登录等场景忽略 */ }
}

async function startTwofaSetup() {
  twofaLoading.value = true
  try {
    const res = await authApi.twofaSetup()
    twofaSetupUri.value = res.data?.uri ?? ''
    twofaSecret.value = res.data?.secret ?? ''
    twofaQr.value = await QRCode.toDataURL(res.data?.uri ?? '')
    twofaConfirmCode.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '生成失败')
  } finally {
    twofaLoading.value = false
  }
}

async function confirmTwofa() {
  if (twofaConfirmCode.value.length !== 6) {
    message.warning('请输入 6 位验证码')
    return
  }
  twofaLoading.value = true
  try {
    await authApi.twofaConfirm(twofaConfirmCode.value)
    message.success('二次验证已启用')
    twofaEnabled.value = true
    twofaSetupUri.value = ''
    twofaSecret.value = ''
    twofaQr.value = ''
    twofaConfirmCode.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '确认失败')
  } finally {
    twofaLoading.value = false
  }
}

async function disableTwofa() {
  if (twofaConfirmCode.value.length !== 6) {
    message.warning('请输入 6 位验证码')
    return
  }
  twofaLoading.value = true
  try {
    await authApi.twofaDisable(twofaConfirmCode.value)
    message.success('二次验证已关闭')
    twofaEnabled.value = false
    twofaDisableMode.value = false
    twofaConfirmCode.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '关闭失败')
  } finally {
    twofaLoading.value = false
  }
}

// ---- 用户管理 ----
interface UserEntry { id: number; username: string; permission: string; created_at: string }
const users = ref<UserEntry[]>([])
const userModalVisible = ref(false)
const editingUserId = ref<number | null>(null)
const userForm = ref({ username: '', password: '', permission: 'read' })

const userColumns = [
  { title: '用户名', key: 'username', width: 120 },
  { title: '权限', key: 'permission', width: 80 },
  { title: '创建时间', key: 'created_at', width: 160 },
  {
    title: '操作', key: 'actions', width: 120,
    render(row: UserEntry) {
      return h('div', { style: 'display:flex;gap:4px' }, [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openUserEdit(row) }, { default: () => '编辑' }),
        h(NPopconfirm, { onPositiveClick: () => handleUserDelete(row.id) }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除？将同时删除该用户的所有Token和会话'
        })
      ])
    }
  }
]

function openUserCreate() {
  editingUserId.value = null; userForm.value = { username: '', password: '', permission: 'read' }; userModalVisible.value = true
}
function openUserEdit(row: UserEntry) {
  editingUserId.value = row.id; userForm.value = { username: row.username, password: '', permission: row.permission }; userModalVisible.value = true
}
async function handleUserSave() {
  if (!userForm.value.username) { message.warning('请输入用户名'); return }
  if (!editingUserId.value && userForm.value.password.length < 4) { message.warning('密码至少4位'); return }
  try {
    if (editingUserId.value) {
      await http.put(`/users/${editingUserId.value}`, { password: userForm.value.password || undefined, permission: userForm.value.permission })
    } else {
      await http.post('/users', { username: userForm.value.username, password: userForm.value.password, permission: userForm.value.permission })
    }
    userModalVisible.value = false; message.success('已保存'); await loadUsers()
  } catch (e: any) { message.error(e?.response?.data?.detail || '操作失败') }
}
async function handleUserDelete(id: number) {
  try { await http.delete(`/users/${id}`); message.success('已删除'); await loadUsers() }
  catch { message.error('删除失败') }
}
async function loadUsers() {
  try { const resp = await http.get('/users'); users.value = resp.data } catch { users.value = [] }
}

// ---- 修改密码 ----
const pwForm = ref({ oldPassword: '', newPassword: '' })
const pwLoading = ref(false)

async function handleChangePassword() {
  if (!pwForm.value.oldPassword || !pwForm.value.newPassword) {
    message.warning('请填写旧密码和新密码'); return
  }
  if (pwForm.value.newPassword.length < 4) {
    message.warning('新密码至少 4 位'); return
  }
  pwLoading.value = true
  try {
    const username = localStorage.getItem('sc_username') || ''
    await http.put('/auth/password', {
      username,
      old_password: pwForm.value.oldPassword,
      new_password: pwForm.value.newPassword
    })
    message.success('密码已修改，下次登录生效')
    pwForm.value = { oldPassword: '', newPassword: '' }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '修改失败')
  } finally { pwLoading.value = false }
}

// ---- Token ----
interface TokenEntry {
  id: number; user_id: number | null; name: string; token: string; token_full: string; permission: string; created_at: string
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
      await http.put(`/tokens/${editingTokenId.value}`, {
        name: tokenForm.value.name,
        permission: tokenForm.value.permission
      })
      message.success('已更新')
    } else {
      const resp = await http.post('/tokens', {
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
    await http.delete(`/tokens/${id}`)
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
    const resp = await http.get('/tokens')
    tokens.value = resp.data
  } catch { tokens.value = [] }
}

// ---- 会话管理 ----
interface SessionEntry { id: number; username: string; permission: string; ip: string; created_at: string; last_active: string }
const sessions = ref<SessionEntry[]>([])

const sessionColumns = [
  { title: '用户', key: 'username', width: 100 },
  { title: 'IP', key: 'ip', width: 130 },
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
    await http.delete(`/sessions/${id}`)
    message.success('已踢掉')
    await loadSessions()
  } catch { message.error('操作失败') }
}

async function handleKickAll() {
  try {
    const resp = await http.post('/sessions/kick-all')
    message.success(`已踢掉 ${resp.data.deleted || 0} 个其他会话`)
    await loadSessions()
  } catch { message.error('操作失败') }
}

async function loadSessions() {
  try {
    const resp = await http.get('/sessions')
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

async function handleRestore({ file }: { file: UploadFileInfo }) {
  try {
    const res = await settingsApi.restoreBackup(file.file!)
    if (res.data?.success) {
      message.success(res.data.message || '恢复完成')
      await loadDbStatus()
      await loadUsers()
      await loadTokens()
    } else {
      message.error(res.data?.message || '恢复失败')
    }
  } catch { message.error('恢复失败，请检查文件格式') }
}

onMounted(() => { loadUsers(); loadTokens(); loadSessions(); loadDbStatus(); loadTwofaStatus() })
</script>

<style scoped>
.settings-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--gap-md); }

/* 二次验证 */
.twofa-row { display: flex; flex-direction: column; gap: 12px; }
.twofa-desc p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
  max-width: 560px;
  line-height: 1.6;
}
.twofa-setup { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.twofa-secret {
  display: flex;
  align-items: center;
  gap: 8px;
}
.twofa-secret code {
  font-size: 13px;
  background: var(--border-light);
  padding: 3px 8px;
  border-radius: 6px;
  color: var(--text-primary);
  user-select: all;
}
</style>
