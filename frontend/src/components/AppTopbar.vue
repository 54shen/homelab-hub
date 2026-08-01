<template>
  <header class="topbar" :class="{ collapsed: collapsed }">
    <div class="topbar-left">
      <button class="hamburger" @click="$emit('toggle')" :title="collapsed ? '展开菜单' : '收起菜单'">
        <ion-icon name="menu-outline" class="hamburger-icon"></ion-icon>
      </button>
      <span class="topbar-title">{{ pageTitle }}</span>
    </div>
    <div class="topbar-right">
      <span class="topbar-username">{{ username }}</span>
      <span class="topbar-indicator" @click="wsRealtime = !wsRealtime" title="点击切换实时推送">
        <span class="status-dot" :class="wsConnected ? (wsRealtime ? 'online' : 'idle') : 'offline'"></span>
        {{ wsConnected ? (wsRealtime ? '实时' : '暂停') : '断开' }}
      </span>
      <span class="topbar-time">{{ currentTime }}</span>
      <n-button text size="tiny" type="error" @click="handleLogout">退出</n-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { wsConnected, wsRealtime } from '../composables/useWebSocket'

defineProps<{ collapsed: boolean }>()
defineEmits<{ toggle: [] }>()

const route = useRoute()
const router = useRouter()
const currentTime = ref('')
const username = ref(localStorage.getItem('sc_username') || '')

function handleLogout() {
  localStorage.removeItem('sc_username')
  localStorage.removeItem('sc_token')
  localStorage.removeItem('sc_permission')
  router.replace('/login')
}

let timer: ReturnType<typeof setInterval>

const pageTitle = computed(() => {
  return (route.meta?.title as string) || 'Shared Center'
})

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false
  })
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.topbar {
  position: fixed;
  top: 0;
  left: var(--sidebar-width);
  right: 0;
  height: var(--topbar-height);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--gap-lg);
  z-index: 90;
  transition: left 0.25s ease;
}
.topbar.collapsed {
  left: 0;
}
.topbar-left { display: flex; align-items: center; gap: 8px; }
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }

/* ---- 汉堡菜单按钮 ---- */
.hamburger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  color: var(--text-primary);
  transition: background 0.15s ease;
  flex-shrink: 0;
}
.hamburger:hover {
  background: var(--bg-page);
}
.hamburger-icon {
  font-size: 22px;
}

@media (max-width: 767px) {
  .topbar {
    padding: 0 var(--gap-sm);
  }
}
.topbar-right { display: flex; align-items: center; gap: 16px; }
.topbar-username { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.topbar-indicator {
  font-size: 12px; color: var(--text-secondary);
  display: flex; align-items: center; gap: 6px;
  background: var(--bg-page); padding: 4px 12px;
  border-radius: var(--radius-full);
  cursor: pointer; user-select: none;
  transition: background 0.15s;
}
.topbar-indicator:hover {
  background: var(--border-light);
}
.topbar-time {
  font-size: 12px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
