// ============================================================
// useFieldLabels 字段映射 composable 测试
// 模块是全局单例(labelMap/loaded),每个测试用 resetModules 重置
// ============================================================
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listMock = vi.hoisted(() => vi.fn())
vi.mock('../api', () => ({
  fieldMappingApi: { list: listMock }
}))

function mockMappings(mappings: Record<string, string>) {
  listMock.mockReset()
  listMock.mockResolvedValue({
    data: Object.entries(mappings).map(([field_key, display_name]) => ({
      id: 0, field_key, display_name
    }))
  } as any)
}

async function freshModule() {
  return await import('./useFieldLabels')
}

describe('useFieldLabels', () => {
  beforeEach(() => {
    vi.resetModules()
    mockMappings({ temperature: '温度', 'a.b': '整键', b: '后缀' })
  })

  it('后缀匹配:翻译 key 最后一段并保留前缀', async () => {
    const { useFieldLabels } = await freshModule()
    const { labelOf } = useFieldLabels()
    await Promise.resolve()
    expect(labelOf('HA.temperature')).toBe('HA.温度')
    expect(labelOf('PC.cpu.temperature')).toBe('PC.cpu.温度')
  })

  it('无映射的 key 原样返回', async () => {
    const { useFieldLabels } = await freshModule()
    const { labelOf } = useFieldLabels()
    await Promise.resolve()
    expect(labelOf('HA.unknown_key')).toBe('HA.unknown_key')
  })

  it('无点号的 key 直接按整键匹配', async () => {
    const { useFieldLabels } = await freshModule()
    const { labelOf } = useFieldLabels()
    await Promise.resolve()
    expect(labelOf('temperature')).toBe('温度')
  })

  it('后缀匹配优先于整键匹配', async () => {
    const { useFieldLabels } = await freshModule()
    const { labelOf } = useFieldLabels()
    await Promise.resolve()
    // a.b 同时有整键映射和后缀 b 映射,后缀优先
    expect(labelOf('a.b')).toBe('a.后缀')
  })

  it('refresh 后新映射生效', async () => {
    const { useFieldLabels } = await freshModule()
    const { labelOf, refresh } = useFieldLabels()
    await Promise.resolve()
    expect(labelOf('HA.temperature')).toBe('HA.温度')

    mockMappings({ temperature: '温度(新版)' })
    await refresh()
    expect(labelOf('HA.temperature')).toBe('HA.温度(新版)')
  })

  it('加载失败时保持空映射,不抛异常', async () => {
    listMock.mockRejectedValue(new Error('offline'))
    const { useFieldLabels } = await freshModule()
    const { labelOf, refresh } = useFieldLabels()
    await refresh()
    expect(labelOf('HA.temperature')).toBe('HA.temperature')
  })
})
