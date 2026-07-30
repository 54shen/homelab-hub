<template>
  <header class="topbar">
    <div class="topbar-left">
      <span class="topbar-title">{{ pageTitle }}</span>
    </div>
    <div class="topbar-right">
      <span class="topbar-indicator">
        <span class="status-dot" :class="wsConnected ? 'online' : 'offline'"></span>
        {{ wsConnected ? 'WS 已连接' : 'WS 未连接' }}
      </span>
      <span class="topbar-time">{{ currentTime }}</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { wsConnected } from '../composables/useWebSocket'

const route = useRoute()
const currentTime = ref('')

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
}
.topbar-left { display: flex; align-items: center; }
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.topbar-indicator {
  font-size: 12px; color: var(--text-secondary);
  display: flex; align-items: center; gap: 6px;
  background: var(--bg-page); padding: 4px 12px;
  border-radius: var(--radius-full);
}
.topbar-time {
  font-size: 12px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
