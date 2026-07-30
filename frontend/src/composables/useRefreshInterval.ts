import { ref, watch } from 'vue'

const STORAGE_KEY = 'sc_refresh_interval'

/** 全局共享的刷新间隔（localStorage 持久化，跨页面同步） */
const globalInterval = ref(loadFromStorage())

function loadFromStorage(): number {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored !== null) {
      const val = parseFloat(stored)
      if (!isNaN(val) && val >= 0) return val
    }
  } catch { /* localStorage 不可用 */ }
  // 回退到 .env 配置
  const env = parseFloat(import.meta.env.VITE_REFRESH_INTERVAL || '0')
  return isNaN(env) ? 0 : env
}

function saveToStorage(val: number) {
  try {
    localStorage.setItem(STORAGE_KEY, String(val))
  } catch { /* localStorage 不可用 */ }
}

// 任何页面修改时，同步到 localStorage
watch(globalInterval, saveToStorage)

/**
 * 全局自动刷新间隔 hook
 * 所有页面共享同一个值，修改后 localStorage 持久化 + 切换页面保持
 */
export function useRefreshInterval() {
  return globalInterval
}
