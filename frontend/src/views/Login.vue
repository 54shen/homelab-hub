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
        <n-form-item path="username" label="账号">
          <n-input v-model:value="form.username" placeholder="输入用户名" clearable />
        </n-form-item>
        <n-form-item path="password" label="密码">
          <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="输入密码" clearable @keyup.enter="handleLogin" />
        </n-form-item>
      </n-form>

      <n-button type="primary" block size="large" :loading="loading" @click="handleLogin">
        登 录
      </n-button>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import axios from 'axios'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const errorMsg = ref('')

const form = ref({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号' }],
  password: [{ required: true, message: '请输入密码' }]
}

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
    if (resp.data?.success) {
      localStorage.setItem('sc_username', resp.data.username)
      localStorage.setItem('sc_token', resp.data.token)
      localStorage.setItem('sc_permission', resp.data.permission)
      message.success('登录成功')
      router.replace('/dashboard')
    } else {
      errorMsg.value = '登录失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '登录失败，请检查账号和密码'
  } finally {
    loading.value = false
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
</style>
