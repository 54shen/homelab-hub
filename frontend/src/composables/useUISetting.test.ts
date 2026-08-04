// ============================================================
// useUISetting composable 测试
// localStorage 即时生效 + 500ms 防抖同步服务端
// 注意:模块是全局单例(cache/loaded/pending),每个测试用 resetModules 重置
// ============================================================
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

const httpMock = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }))
vi.mock('../api', () => ({ default: httpMock }))

async function freshModule() {
  return await import('./useUISetting')
}

describe('useUISetting', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    httpMock.get.mockReset()
    httpMock.put.mockReset()
    httpMock.put.mockResolvedValue({ data: {} })   // 避免 flushToServer 里 .catch 拿到 undefined
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('无任何存储时使用默认值', async () => {
    httpMock.get.mockResolvedValue({ data: {} })
    const { useUISetting } = await freshModule()
    const val = useUISetting('theme', 'light')
    expect(val.value).toBe('light')
  })

  it('localStorage 已有值时立即生效(无需等网络)', async () => {
    localStorage.setItem('ui_theme', 'dark')
    httpMock.get.mockResolvedValue({ data: {} })
    const { useUISetting } = await freshModule()
    const val = useUISetting('theme', 'light')
    expect(val.value).toBe('dark')
  })

  it('服务端值异步覆盖 localStorage', async () => {
    localStorage.setItem('ui_theme', 'dark')
    httpMock.get.mockResolvedValue({ data: { theme: 'server-theme' } })
    const { useUISetting } = await freshModule()
    const val = useUISetting('theme', 'light')
    expect(val.value).toBe('dark')
    await flushPromises()
    expect(val.value).toBe('server-theme')
  })

  it('修改值 → 写入 localStorage 并防抖同步服务端', async () => {
    vi.useFakeTimers()
    httpMock.get.mockResolvedValue({ data: {} })
    const { useUISetting } = await freshModule()
    const val = useUISetting('theme', 'light')

    val.value = 'dark'
    await nextTick()
    expect(localStorage.getItem('ui_theme')).toBe('dark')

    // 500ms 内再次修改 → 只同步一次(防抖)
    val.value = 'black'
    await nextTick()
    expect(httpMock.put).not.toHaveBeenCalled()
    vi.advanceTimersByTime(500)
    expect(httpMock.put).toHaveBeenCalledTimes(1)
    expect(httpMock.put).toHaveBeenCalledWith('/settings/ui', { settings: { theme: 'black' } })
  })

  it('useUINumber:解析数字,非法值回退默认', async () => {
    httpMock.get.mockResolvedValue({ data: { poll: '42' } })
    const { useUINumber } = await freshModule()
    const n = useUINumber('poll', 10)
    await flushPromises()
    expect(n.value).toBe(42)
  })

  it('useUINumber:非法字符串回退默认值', async () => {
    httpMock.get.mockResolvedValue({ data: {} })
    const { useUINumber } = await freshModule()
    const n = useUINumber('poll', 10)
    expect(n.value).toBe(10)
  })
})
