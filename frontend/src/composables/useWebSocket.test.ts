// ============================================================
// useWebSocket composable 测试(模块级单例,每个测试重置)
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const WsMock = vi.hoisted(() => {
  class MockWebSocket {
    // 标准 WebSocket 静态常量(模块代码会引用 WebSocket.OPEN,缺失会导致判断永远不成立)
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3
    static instances: MockWebSocket[] = []
    readyState = 0  // CONNECTING
    onopen: any = null
    onmessage: any = null
    onclose: any = null
    onerror: any = null
    send = vi.fn()
    close = vi.fn(function (this: MockWebSocket) {
      this.readyState = 3
      this.onclose?.()
    })
    constructor(public url: string) {
      MockWebSocket.instances.push(this)
    }
  }
  return { MockWebSocket }
})

vi.stubGlobal('WebSocket', WsMock.MockWebSocket)

async function freshModule() {
  return await import('./useWebSocket')
}

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useFakeTimers()
    localStorage.clear()
    WsMock.MockWebSocket.instances = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('调用 useWebSocket 即建立连接', async () => {
    const { useWebSocket } = await freshModule()
    const { wsConnected } = useWebSocket()
    expect(WsMock.MockWebSocket.instances).toHaveLength(1)
    expect(wsConnected.value).toBe(false)
  })

  it('连接建立后 wsConnected 变 true,并启动 25s 心跳 ping', async () => {
    const { useWebSocket, wsConnected } = await freshModule()
    useWebSocket()
    const ws = WsMock.MockWebSocket.instances[0]
    ws.readyState = 1
    ws.onopen?.()
    expect(wsConnected.value).toBe(true)

    vi.advanceTimersByTime(25000)
    expect(ws.send).toHaveBeenCalledWith('ping')
  })

  it('onmessage 解析 JSON 并分发给监听器', async () => {
    const { useWebSocket } = await freshModule()
    const cb = vi.fn()
    const { on } = useWebSocket()
    on(cb)
    const ws = WsMock.MockWebSocket.instances[0]
    ws.readyState = 1
    ws.onopen?.()

    ws.onmessage?.({ data: '{"event":"kv.changed","data":{"key":"a"}}' })
    expect(cb).toHaveBeenCalledWith('kv.changed', { key: 'a' })
  })

  it('wsRealtime 关闭时忽略所有事件', async () => {
    const { useWebSocket, wsRealtime } = await freshModule()
    const cb = vi.fn()
    const { on } = useWebSocket()
    on(cb)
    const ws = WsMock.MockWebSocket.instances[0]
    ws.readyState = 1
    ws.onopen?.()

    wsRealtime.value = false
    ws.onmessage?.({ data: '{"event":"kv.changed","data":{}}' })
    expect(cb).not.toHaveBeenCalled()

    wsRealtime.value = true
    ws.onmessage?.({ data: '{"event":"x","data":{}}' })
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('无效 JSON 不报错', async () => {
    const { useWebSocket } = await freshModule()
    const cb = vi.fn()
    const { on } = useWebSocket()
    on(cb)
    const ws = WsMock.MockWebSocket.instances[0]
    ws.readyState = 1
    ws.onopen?.()
    ws.onmessage?.({ data: 'not-json' })
    expect(cb).not.toHaveBeenCalled()
  })

  it('断开后按指数退避自动重连', async () => {
    const { useWebSocket } = await freshModule()
    useWebSocket()
    const ws = WsMock.MockWebSocket.instances[0]
    // 用 close() 而不是直接调 onclose:close 会先把 readyState 置为 CLOSED,
    // 否则 connect() 里 "已连接就跳过" 的判断会拦住重连
    ws.close()
    // 第一次重连:1s 后
    vi.advanceTimersByTime(1000)
    expect(WsMock.MockWebSocket.instances).toHaveLength(2)
    // 再次断开:2s 后(指数退避)
    WsMock.MockWebSocket.instances[1].close()
    vi.advanceTimersByTime(2000)
    expect(WsMock.MockWebSocket.instances).toHaveLength(3)
  })

  it('监听器卸载后不再收到事件', async () => {
    const { useWebSocket } = await freshModule()
    const cb = vi.fn()
    const { on } = useWebSocket()
    const off = on(cb)
    const ws = WsMock.MockWebSocket.instances[0]
    ws.readyState = 1
    ws.onopen?.()

    ws.onmessage?.({ data: '{"event":"a","data":{}}' })
    expect(cb).toHaveBeenCalledTimes(1)
    off()
    ws.onmessage?.({ data: '{"event":"b","data":{}}' })
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('wsRealtime 初始值读 localStorage', async () => {
    localStorage.setItem('ws_realtime', '0')
    const { wsRealtime } = await freshModule()
    expect(wsRealtime.value).toBe(false)
  })
})
