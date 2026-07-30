import { ref, watch } from 'vue'
import http from '../api'

const cache = new Map<string, string>()
let loaded = false
let saveTimer: ReturnType<typeof setTimeout> | null = null
const pending: Record<string, string> = {}

async function loadFromServer() {
  try {
    const res = await http.get<Record<string, string>>('/settings/ui')
    if (res.data) {
      for (const [k, v] of Object.entries(res.data)) {
        cache.set(k, v)
      }
    }
  } catch { /* server offline, use cache */ }
  loaded = true
}

function flushToServer() {
  if (Object.keys(pending).length === 0) return
  const settings = { ...pending }
  // 清空 pending
  for (const k of Object.keys(pending)) delete pending[k]
  http.put('/settings/ui', { settings }).catch(() => {})
}

function markDirty(key: string, value: string) {
  pending[key] = value
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(flushToServer, 500)
}

/**
 * UI 设置 hook — localStorage 即时生效 + 500ms 防抖同步到服务端
 */
export function useUISetting(key: string, defaultValue: string) {
  // 先读 localStorage（即时可用）
  const stored = (() => {
    try { return localStorage.getItem(`ui_${key}`) }
    catch { return null }
  })()

  const val = ref(stored ?? defaultValue)

  // 异步从服务端加载（覆盖 localStorage）
  if (!loaded) {
    loadFromServer().then(() => {
      const serverVal = cache.get(key)
      if (serverVal !== undefined) {
        val.value = serverVal
      }
    })
  } else {
    const serverVal = cache.get(key)
    if (serverVal !== undefined) val.value = serverVal
  }

  // 变更时：localStorage + 服务端双写
  watch(val, (v) => {
    try { localStorage.setItem(`ui_${key}`, v) } catch {}
    markDirty(key, v)
  })

  return val
}

/** 读取数字型设置 */
export function useUINumber(key: string, defaultValue: number): ReturnType<typeof ref<number>> {
  const str = useUISetting(key, String(defaultValue))
  const num = ref<number>(parseFloat(str.value) || defaultValue)

  // 外部通过 num.value 读写，内部自动转换
  watch(num, (v) => { str.value = String(v) })
  watch(str, (v) => {
    const n = parseFloat(v)
    if (!isNaN(n) && n !== num.value) num.value = n
  })

  return num
}
