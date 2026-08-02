// ============================================================
// Shared Center — WebSocket 连接管理
// 全局单例：所有页面通过 useWebSocket() 获取 on/off 控制
// ============================================================
import { ref, onMounted, getCurrentInstance } from 'vue'

type WsCallback = (event: string, data: unknown) => void

const listeners = new Map<symbol, WsCallback>()
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
let reconnectAttempts = 0

export const wsConnected = ref(false)

/** 全局 WS 实时开关（localStorage 持久化） */
export const wsRealtime = ref(
  (() => { try { return localStorage.getItem('ws_realtime') !== '0' } catch { return true } })()
)

// 监听 wsRealtime 变化写入 localStorage
import { watch } from 'vue'
watch(wsRealtime, (v) => { try { localStorage.setItem('ws_realtime', v ? '1' : '0') } catch {} } )

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
    pingTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
  }

  ws.onmessage = (ev) => {
    if (!wsRealtime.value) return  // 开关关闭时忽略所有事件
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
  const id = Symbol('ws')

  const on = (cb: WsCallback) => {
    listeners.set(id, cb)
    return () => listeners.delete(id)
  }

  if (getCurrentInstance()) {
    onMounted(() => connect())
  } else {
    connect()
  }

  return { wsConnected, wsRealtime, on }
}

// 全局初始化（在 main.ts 中调用一次）
export function initWebSocket() {
  connect()
  window.addEventListener('beforeunload', disconnect)
}
