// ============================================================
// Shared Center — 通用表格排序 composable
// 手动排序，支持列级自定义 sorter 函数，不依赖 Naive UI 内置行为
// ============================================================
import { computed, ref, type Ref } from 'vue'

type SortOrder = 'ascend' | 'descend' | false
type CustomSorter<T> = (a: T, b: T) => number

export function useSorter<T extends Record<string, any>>(data: Ref<T[]>) {
  const sorterFn = ref<CustomSorter<T> | null>(null)
  const sortOrder = ref<SortOrder>(false)

  const sorted = computed(() => {
    if (!sorterFn.value || !sortOrder.value) return data.value
    const sorted = [...data.value].sort(sorterFn.value)
    return sortOrder.value === 'descend' ? sorted.reverse() : sorted
  })

  function onSorter(s: { columnKey: string; order: SortOrder; sorter: CustomSorter<T> | boolean | 'default' } | null) {
    if (!s || !s.order) {
      sorterFn.value = null
      sortOrder.value = false
    } else {
      sortOrder.value = s.order
      // 优先用列定义的 sorter 函数，否则用 key 默认比较
      if (typeof s.sorter === 'function') {
        sorterFn.value = s.sorter
      } else {
        const key = s.columnKey
        sorterFn.value = (a: T, b: T) => {
          const va = a[key]; const vb = b[key]
          if (typeof va === 'number' && typeof vb === 'number') return va - vb
          return String(va ?? '').localeCompare(String(vb ?? ''))
        }
      }
    }
  }

  return { sorted, onSorter }
}
