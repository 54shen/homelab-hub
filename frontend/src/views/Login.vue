<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <svg width="40" height="40" viewBox="0 0 30 30" fill="none">
          <rect width="30" height="30" rx="9" fill="#5B8DEF"/>
          <path d="M7 11h7v8H7zM13 15h4v4h-4zM19 9h4v10h-4z" fill="white" opacity="0.9"/>
        </svg>
        <h1>Shared Center</h1>
        <p>家庭实验室控制中心</p>
      </div>

      <n-form ref="formRef" :model="form" :rules="rules" size="large">
        <!-- 仅验证码模式(默认):只有 6 位验证码,免账号密码 -->
        <template v-if="codeOnly && !showPasswordMode">
          <n-form-item path="code" label="验证码登录">
            <n-input
              ref="codeInputRef"
              v-model:value="form.code"
              placeholder="输入手机 App 的 6 位验证码"
              maxlength="6"
              clearable
              @keyup.enter="handleTotpLogin"
              @input="onCodeInput"
            >
              <template #prefix>
                <ion-icon name="shield-checkmark-outline" style="color:var(--color-success)" />
              </template>
            </n-input>
          </n-form-item>
          <p class="mode-hint">已绑定验证码的账号,输入 6 位动态码即可登录</p>
        </template>

        <!-- 标准模式:账号 + 密码(第二步验证码) -->
        <template v-else>
          <n-form-item path="username" label="账号">
            <n-input v-model:value="form.username" placeholder="输入用户名" clearable :disabled="need2fa" />
          </n-form-item>
          <n-form-item path="password" label="密码">
            <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="输入密码" clearable :disabled="need2fa" @keyup.enter="handleLogin" />
          </n-form-item>
          <!-- 二次验证:第二步输入 6 位验证码 -->
          <n-form-item v-if="need2fa" path="code" label="二次验证码">
            <n-input
              ref="codeInputRef"
              v-model:value="form.code"
              placeholder="输入手机 App 的 6 位验证码"
              maxlength="6"
              clearable
              @keyup.enter="handleVerify2fa"
              @input="onCodeInput"
            >
              <template #prefix>
                <ion-icon name="shield-checkmark-outline" style="color:var(--color-success)" />
              </template>
            </n-input>
          </n-form-item>
        </template>
      </n-form>

      <n-button v-if="codeOnly && !showPasswordMode" type="primary" block size="large" :loading="loading" @click="handleTotpLogin">
        登 录
      </n-button>
      <n-button v-else-if="!need2fa" type="primary" block size="large" :loading="loading" @click="handleLogin">
        登 录
      </n-button>
      <n-button v-else type="primary" block size="large" :loading="loading" @click="handleVerify2fa">
        验 证
      </n-button>

      <p v-if="codeOnly && !showPasswordMode" class="mode-switch">
        未绑定验证码或需密码登录?
        <a @click="switchToPassword">使用 用户名+密码 登录</a>
      </p>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import axios from 'axios'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const errorMsg = ref('')
const need2fa = ref(false)  // 第二步:需要 6 位验证码
const codeInputRef = ref<InstanceType<typeof NInput> | null>(null)
const codeOnly = ref(false)          // 服务端开启"仅验证码登录"
const showPasswordMode = ref(false)  // 纯验证码模式下手动切到 用户名+密码
const loginTicket = ref('')          // B 路径:login 验密码后的一次性 ticket

const form = ref({ username: '', password: '', code: '' })
const rules = {
  username: [{ required: true, message: '请输入账号' }],
  password: [{ required: true, message: '请输入密码' }]
}

function finishLogin(data: any) {
  localStorage.setItem('sc_username', data.username)
  localStorage.setItem('sc_token', data.token)
  localStorage.setItem('sc_permission', data.permission)
  message.success('登录成功')
  router.replace('/dashboard')
}

// 登录页加载:查询登录模式(仅验证码模式 → 默认纯验证码表单)
onMounted(async () => {
  try {
    const base = import.meta.env.VITE_API_BASE || '/api'
    const resp = await axios.get(base + '/auth/login-mode')
    codeOnly.value = !!resp.data?.code_only
  } catch { /* 后端不可用,保持标准表单 */ }
})

function switchToPassword() {
  showPasswordMode.value = true
  errorMsg.value = ''
}

// 纯验证码登录(仅验证码模式):只有 6 位验证码,后端遍历匹配用户
async function handleTotpLogin() {
  const code = form.value.code.trim()
  if (code.length !== 6) {
    errorMsg.value = '请输入 6 位验证码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const base = import.meta.env.VITE_API_BASE || '/api'
    const resp = await axios.post(base + '/auth/totp-login', { code })
    if (resp.data?.success) {
      finishLogin(resp.data)
    } else {
      errorMsg.value = '登录失败'
    }
  } catch (e: any) {
    // 429 锁定 → 先自动切到 用户名+密码+验证码 表单(逃生通道),再显示原因
    if (e?.response?.status === 429) {
      switchToPassword()
    }
    errorMsg.value = e?.response?.data?.detail || '验证码错误或已过期'
  } finally {
    loading.value = false
  }
}

// 登录第一步:账号 + 密码
async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    errorMsg.value = '请填写账号和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const base = import.meta.env.VITE_API_BASE || '/api'
    const resp = await axios.post(base + '/auth/login', {
      username: form.value.username,
      password: form.value.password
    })
    if (resp.data?.need_2fa) {
      // 该账号已启用二次验证 → 进入第二步,保存一次性 ticket(密码已验证凭证)
      need2fa.value = true
      loginTicket.value = resp.data?.ticket || ''
      message.info('该账号已启用二次验证,请输入手机 App 的 6 位验证码')
      await nextTick()
      codeInputRef.value?.focus()
      return
    }
    if (resp.data?.success) {
      finishLogin(resp.data)
    } else {
      errorMsg.value = '登录失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '登录失败，请检查账号和密码'
  } finally {
    loading.value = false
  }
}

// 登录第二步:6 位 TOTP 验证码(带 ticket,证明密码已验证)
async function handleVerify2fa() {
  const code = form.value.code.trim()
  if (code.length !== 6) {
    errorMsg.value = '请输入 6 位验证码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const base = import.meta.env.VITE_API_BASE || '/api'
    const resp = await axios.post(base + '/auth/verify-2fa', {
      username: form.value.username,
      code,
      ticket: loginTicket.value || undefined
    })
    if (resp.data?.success) {
      finishLogin(resp.data)
    } else {
      errorMsg.value = '验证失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '验证码错误或已过期'
  } finally {
    loading.value = false
  }
}

// 输入满 6 位自动提交
function onCodeInput() {
  const code = form.value.code.replace(/\D/g, '').slice(0, 6)
  form.value.code = code
  if (code.length === 6) {
    if (codeOnly.value && !showPasswordMode.value) {
      handleTotpLogin()
    } else if (need2fa.value) {
      handleVerify2fa()
    }
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
}
.login-card {
  width: 400px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-xl);
  padding: 40px;
  box-shadow: var(--shadow-modal);
}
.login-brand {
  text-align: center;
  margin-bottom: 32px;
}
.login-brand h1 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 12px;
}
.login-brand p {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.error-msg {
  color: var(--color-danger);
  font-size: 13px;
  text-align: center;
  margin-top: 12px;
}
.mode-hint {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  margin-top: -4px;
}
.mode-switch {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  margin-top: 14px;
}
.mode-switch a {
  color: var(--color-info);
  cursor: pointer;
  text-decoration: underline;
}
</style>
