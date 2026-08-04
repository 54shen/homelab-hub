// ============================================================
// useSorter 排序 composable 测试
// ============================================================
import { describe, expect, it } from 'vitest'
import { ref } from 'vue'

import { useSorter } from './useSorter'

describe('useSorter', () => {
  it('未排序时返回原数组', () => {
    const data = ref([{ name: 'b' }, { name: 'a' }])
    const { sorted } = useSorter(data)
    expect(sorted.value.map((x) => x.name)).toEqual(['b', 'a'])
  })

  it('数字列升序/降序', () => {
    const data = ref([{ v: 3 }, { v: 1 }, { v: 2 }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'v', order: 'ascend', sorter: false })
    expect(sorted.value.map((x) => x.v)).toEqual([1, 2, 3])
    onSorter({ columnKey: 'v', order: 'descend', sorter: false })
    expect(sorted.value.map((x) => x.v)).toEqual([3, 2, 1])
  })

  it('字符串列按 localeCompare 排序', () => {
    const data = ref([{ name: 'b' }, { name: 'a' }, { name: 'c' }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'name', order: 'ascend', sorter: false })
    expect(sorted.value.map((x) => x.name)).toEqual(['a', 'b', 'c'])
  })

  it('空值参与字符串比较,排在前面', () => {
    const data = ref([{ v: 2 }, { v: null }, { v: 1 }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'v', order: 'ascend', sorter: false })
    // null → '' 排在 '1' 前面
    expect(sorted.value.map((x) => x.v)).toEqual([null, 1, 2])
  })

  it('自定义 sorter 函数优先于列 key', () => {
    const data = ref([{ a: 2, b: 1 }, { a: 1, b: 9 }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'a', order: 'ascend', sorter: (x, y) => x.b - y.b })
    expect(sorted.value.map((x) => x.a)).toEqual([2, 1])
  })

  it('取消排序后恢复原数组顺序', () => {
    const data = ref([{ v: 3 }, { v: 1 }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'v', order: 'ascend', sorter: false })
    onSorter(null)
    expect(sorted.value.map((x) => x.v)).toEqual([3, 1])
  })

  it('排序不修改原数组', () => {
    const data = ref([{ v: 3 }, { v: 1 }])
    const { sorted, onSorter } = useSorter(data)
    onSorter({ columnKey: 'v', order: 'descend', sorter: false })
    expect(sorted.value.map((x) => x.v)).toEqual([3, 1])
    expect(data.value.map((x) => x.v)).toEqual([3, 1])
  })
})
