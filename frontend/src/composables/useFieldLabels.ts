// ============================================================
// 字段映射缓存 — 全局单例，英文 key → 中文显示名
// ============================================================
import { ref } from 'vue'
import { fieldMappingApi, type FieldMapping } from '../api'

const labelMap = ref<Record<string, string>>({})
let loaded = false
let loadPromise: Promise<void> | null = null

async function ensureLoaded() {
  if (loaded) return
  if (loadPromise) { await loadPromise; return }
  loadPromise = (async () => {
    try {
      const res = await fieldMappingApi.list()
      const map: Record<string, string> = {}
      if (res.data) {
        for (const m of res.data as FieldMapping[]) {
          map[m.field_key] = m.display_name
        }
      }
      labelMap.value = map
      loaded = true
    } catch {
      // 加载失败，保持空映射
      loaded = true
    }
  })()
  await loadPromise
}

export function useFieldLabels() {
  // 触发加载（可多次调用，内部防重）
  ensureLoaded()

  function labelOf(key: string): string {
    // 翻译 key 的最后一段（后缀），保留前缀
    const dot = key.lastIndexOf('.')
    const suffix = dot >= 0 ? key.slice(dot + 1) : key
    const prefix = dot >= 0 ? key.slice(0, dot + 1) : ''
    const mapped = labelMap.value[suffix] || labelMap.value[key]
    if (!mapped) return key
    return prefix + mapped
  }

  /** 刷新映射缓存（映射变更后调用） */
  async function refresh() {
    loaded = false
    loadPromise = null
    await ensureLoaded()
  }

  return { labelOf, labelMap, refresh }
}
