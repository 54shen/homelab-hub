<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">字段映射</h1>
      <n-space>
        <n-button size="small" quaternary @click="exportTemplate">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px" />
          导出空白模板
        </n-button>
        <n-upload
          :show-file-list="false"
          accept=".csv"
          @change="onImport"
        >
          <n-button size="small" quaternary>
            <ion-icon name="cloud-upload-outline" style="margin-right:4px;vertical-align:-2px" />
            导入 CSV
          </n-button>
        </n-upload>
        <n-button size="small" type="primary" @click="startAdd">
          <ion-icon name="add-outline" style="margin-right:4px;vertical-align:-2px" />
          新增
        </n-button>
      </n-space>
    </div>

    <!-- 统计条 -->
    <div class="stats-bar">
      <span>已配置映射 <b>{{ items.length }}</b></span>
      <span class="unmapped-stat">未映射 Key <b>{{ unmappedKeys.length }}</b></span>
      <span v-if="search">匹配 <b>{{ filtered.length }}</b> 条</span>
    </div>

    <!-- 搜索 -->
    <n-input
      v-model:value="search"
      placeholder="搜索 field_key 或 display_name..."
      clearable
      size="small"
      style="max-width:360px;margin-bottom:12px"
    >
      <template #prefix><ion-icon name="search-outline" style="vertical-align:-2px" /></template>
    </n-input>

    <n-data-table
      :columns="columns"
      :data="filtered"
      :bordered="false"
      size="small"
      style="background:var(--bg-card);border-radius:var(--radius-lg)"
    >
      <!-- 空状态统一在表格内部,纯文字无图片 -->
      <template #empty>
        <span class="table-empty">{{ emptyText }}</span>
      </template>
    </n-data-table>

    <!-- 未映射的 key -->
    <div v-if="unmappedKeys.length > 0" class="unmapped-section">
      <div class="unmapped-header">
        <h3>未映射的 Key <span class="badge">{{ unmappedKeys.length }}</span></h3>
        <n-button size="tiny" quaternary @click="addAllUnmapped">
          <ion-icon name="add-outline" style="margin-right:4px;vertical-align:-2px" />
          一键全部添加
        </n-button>
      </div>
      <div class="unmapped-chips">
        <span v-for="k in unmappedKeys" :key="k" class="unmapped-chip" @click="quickAdd(k)">
          {{ k }} <ion-icon name="add-circle-outline" style="font-size:14px;vertical-align:-2px;margin-left:2px" />
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref, nextTick } from 'vue'
import {
  NButton, NDataTable, NInput, NPopconfirm, NSpace, NUpload, useMessage
} from 'naive-ui'
import { fieldMappingApi, type FieldMapping } from '../api'
import { useFieldLabels } from '../composables/useFieldLabels'

const message = useMessage()
const { refresh } = useFieldLabels()

const items = ref<FieldMapping[]>([])
const unmappedKeys = ref<string[]>([])
const search = ref('')
const loading = ref(false)

// 新增/编辑状态
const editingId = ref<number | null>(null)
const editingKey = ref('')
const editingName = ref('')

// 新增用的临时行（id=0, 不在真实数据中）
const GHOST: FieldMapping = { id: 0, field_key: '', display_name: '' }

const filtered = computed(() => {
  let list = items.value
  if (search.value) {
    const s = search.value.toLowerCase()
    list = list.filter(m =>
      m.field_key.toLowerCase().includes(s) || m.display_name.toLowerCase().includes(s)
    )
  }
  // 新增模式且无搜索结果时，在顶部插入临时行
  if (editingId.value === -1) {
    return [GHOST, ...list]
  }
  return list
})

// 空状态提示:确实无映射 / 有数据但搜索无匹配
const emptyText = computed(() =>
  items.value.length === 0
    ? '暂无映射 — 点击「导出空白模板」获取 CSV 模板'
    : '无匹配映射'
)

// ---- 新增 ----
function startAdd() {
  editingId.value = -1  // -1 = 新增行
  editingKey.value = ''
  editingName.value = ''
  nextTick(() => {
    document.querySelector<HTMLInputElement>('.edit-key-input')?.focus()
  })
}

async function saveAdd() {
  const key = editingKey.value.trim()
  const name = editingName.value.trim()
  if (!key || !name) { editingId.value = null; return }
  try {
    await fieldMappingApi.create({ field_key: key, display_name: name })
    await loadData()
    await refresh()
    message.success('已添加')
  } catch { message.error('添加失败') }
  editingId.value = null
}

// ---- 行内编辑 ----
function startEdit(row: FieldMapping) {
  editingId.value = row.id
  editingKey.value = row.field_key
  editingName.value = row.display_name
  nextTick(() => {
    document.querySelector<HTMLInputElement>('.edit-key-input')?.focus()
  })
}

async function saveEdit(row: FieldMapping) {
  const key = editingKey.value.trim()
  const name = editingName.value.trim()
  if (!key || !name || (key === row.field_key && name === row.display_name)) {
    editingId.value = null; return
  }
  try {
    await fieldMappingApi.update(row.id, { field_key: key, display_name: name })
    await loadData()
    await refresh()
    message.success('已更新')
  } catch { message.error('更新失败') }
  editingId.value = null
}

function cancelEdit() {
  editingId.value = null
}

// ---- 删除 ----
async function deleteMapping(row: FieldMapping) {
  try {
    await fieldMappingApi.delete(row.id)
    await loadData()
    await refresh()
    message.success('已删除')
  } catch { message.error('删除失败') }
}

// ---- 导出空白模板 ----
async function exportTemplate() {
  try {
    const res = await fieldMappingApi.exportTemplate()
    const blob = new Blob([res.data as BlobPart], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'field_mappings_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch { message.error('导出失败') }
}

// ---- 导入 CSV ----
async function onImport(data: any) {
  const file = data.file?.file as File | null
  if (!file) return
  try {
    const res = await fieldMappingApi.importCsv(file)
    if (res.data?.success) {
      message.success(res.data.message || '导入完成')
      await loadData()
      await refresh()
    } else {
      message.warning(res.data?.message || '导入失败')
    }
  } catch { message.error('导入失败') }
}

async function loadData() {
  loading.value = true
  try {
    const [listRes, unmappedRes] = await Promise.all([
      fieldMappingApi.list(),
      fieldMappingApi.unmapped()
    ])
    if (listRes.data) items.value = listRes.data
    if (unmappedRes.data) unmappedKeys.value = unmappedRes.data
  } catch { items.value = []; unmappedKeys.value = [] }
  finally { loading.value = false }
}

// ---- 快速添加单个 ----
async function quickAdd(key: string) {
  try {
    await fieldMappingApi.create({ field_key: key, display_name: key })
    await loadData()
    await refresh()
    message.success(`已添加 "${key}"，请编辑显示名`)
  } catch { message.error(`添加 "${key}" 失败`) }
}

// ---- 一键全部添加 ----
async function addAllUnmapped() {
  let count = 0
  for (const key of unmappedKeys.value) {
    try {
      await fieldMappingApi.create({ field_key: key, display_name: key })
      count++
    } catch { /* 已存在则跳过 */ }
  }
  if (count > 0) {
    await loadData()
    await refresh()
    message.success(`已添加 ${count} 个映射`)
  } else {
    message.info('没有需要添加的')
  }
}

// ---- 列定义 ----
const editInputStyle = 'width:100%;padding:6px 10px;border:1.5px solid #5B8DEF;border-radius:6px;font-size:13px;outline:none;background:var(--bg-card);color:var(--text-primary);box-shadow:0 0 0 2px #5B8DEF18'
const columns = [
  {
    title: '字段 Key', key: 'field_key', width: 200, ellipsis: { tooltip: true },
    render(row: FieldMapping) {
      if (editingId.value === row.id || row.id === 0) {
        return h('input', {
          class: 'edit-key-input',
          value: editingKey.value,
          placeholder: '英文 key',
          onInput: (e: Event) => { editingKey.value = (e.target as HTMLInputElement).value },
          onKeydown: (e: KeyboardEvent) => {
            if (e.key === 'Enter') editingId.value === -1 ? saveAdd() : saveEdit(row)
            if (e.key === 'Escape') cancelEdit()
          },
          style: editInputStyle
        })
      }
      return h('span', { style: 'font-family:monospace' }, row.field_key)
    }
  },
  {
    title: '显示名', key: 'display_name', width: 200, ellipsis: { tooltip: true },
    render(row: FieldMapping) {
      if (editingId.value === row.id || row.id === 0) {
        return h('input', {
          value: editingName.value,
          placeholder: '中文显示名',
          onInput: (e: Event) => { editingName.value = (e.target as HTMLInputElement).value },
          onKeydown: (e: KeyboardEvent) => {
            if (e.key === 'Enter') editingId.value === -1 ? saveAdd() : saveEdit(row)
            if (e.key === 'Escape') cancelEdit()
          },
          style: editInputStyle
        })
      }
      return row.display_name
    }
  },
  {
    title: '操作', key: 'actions', width: 130,
    render(row: FieldMapping) {
      // 新增行（GHOST id=0）
      if (row.id === 0) {
        return h('span', { style: 'display:flex;gap:4px' }, [
          h(NButton, { size: 'tiny', quaternary: true, onClick: saveAdd }, { default: () => '保存' }),
          h(NButton, { size: 'tiny', quaternary: true, onClick: cancelEdit }, { default: () => '取消' })
        ])
      }
      // 编辑行
      if (editingId.value === row.id) {
        return h('span', { style: 'display:flex;gap:4px' }, [
          h(NButton, { size: 'tiny', quaternary: true, onClick: () => saveEdit(row) }, { default: () => '保存' }),
          h(NButton, { size: 'tiny', quaternary: true, onClick: cancelEdit }, { default: () => '取消' })
        ])
      }
      return h('span', { style: 'display:flex;gap:4px' }, [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => startEdit(row) }, { default: () => '编辑' }),
        h(NPopconfirm, {
          positiveText: '确认', negativeText: '取消',
          onPositiveClick: () => deleteMapping(row)
        }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          default: () => `确定要删除映射 "${row.field_key}" 吗？`
        })
      ])
    }
  }
]

onMounted(() => { loadData() })
</script>

<style scoped>
/* ── 统计条 ── */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: 10px 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.stats-bar b {
  color: var(--text-primary);
  font-weight: 600;
  margin-left: 2px;
}
.stats-bar .unmapped-stat b {
  color: var(--color-warning);
}

/* ── 未映射区域 ── */
.unmapped-section {
  margin-top: 24px;
  padding: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.unmapped-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.unmapped-header h3 {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.unmapped-header .badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--color-warning);
  border-radius: var(--radius-full);
}
.unmapped-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.unmapped-chip {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-family: monospace;
  background: var(--border-light);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.unmapped-chip:hover {
  background: #5B8DEF20;
  color: #5B8DEF;
}

/* ── 表格空状态 ── */
.table-empty {
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
