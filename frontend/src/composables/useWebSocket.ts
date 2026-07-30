// ============================================================
// Shared Center — WebSocket 连接管理
// ============================================================
import { ref, onMounted, onUnmounted } from 'vue'

type WsCallback = (event: string, data: unknown) => void

const listeners = new Set<WsCallback>()
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
let reconnectAttempts = 0

export const wsConnected = ref(false)

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

  const url = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`

  try {
    ws = new WebSocket(url)
  } catch {
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    wsConnected.value = true
    reconnectAttempts = 0
    // 心跳
    pingTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
  }

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      listeners.forEach((cb) => cb(msg.event, msg.data))
    } catch { /* */ }
  }

  ws.onclose = () => {
    wsConnected.value = false
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
    scheduleReconnect()
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
  reconnectAttempts += 1
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connect()
  }, delay)
}

function disconnect() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
  ws?.close()
  ws = null
  wsConnected.value = false
}

export function useWebSocket() {
  const on = (cb: WsCallback) => {
    listeners.add(cb)
    return () => listeners.delete(cb)
  }

  onMounted(() => connect())
  onUnmounted(() => {
    // 仅在组件卸载时移除监听器，不断开全局连接
    return () => {}
  })

  return { wsConnected, on }
}

// 全局初始化（在 main.ts 中调用一次）
export function initWebSocket() {
  connect()
  window.addEventListener('beforeunload', disconnect)
}
