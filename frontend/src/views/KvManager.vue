<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">变量管理</h1>
      <n-space>
        <n-button size="small" quaternary @click="handleExport">
          <ion-icon name="download-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
          导出
        </n-button>
        <n-upload :show-file-list="false" accept=".json" @change="handleImport">
          <n-button size="small" quaternary>
            <ion-icon name="cloud-upload-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
            导入
          </n-button>
        </n-upload>
        <n-button v-if="checkedKeys.length > 0" size="small" type="error" quaternary @click="handleBatchDelete">
          <ion-icon name="trash-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
          删除选中 ({{ checkedKeys.length }})
        </n-button>
        <n-button type="primary" size="small" @click="openCreateModal">
          <ion-icon name="add-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
          新增变量
        </n-button>
      </n-space>
    </div>

    <!-- 搜索 -->
    <n-input
      v-model:value="searchKey"
      placeholder="搜索 key..."
      clearable
      size="large"
      style="margin-bottom: 16px"
    >
      <template #prefix>
        <ion-icon name="search-outline" style="color:var(--text-secondary)"></ion-icon>
      </template>
    </n-input>

    <!-- 表格 -->
    <n-data-table
      :columns="columns"
      :data="filteredData"
      :bordered="false"
      :single-line="false"
      size="small"
      :row-key="(r: KvEntry) => r.key"
      :checked-row-keys="checkedKeys"
      :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50] }"
      style="background: var(--bg-card); border-radius: var(--radius-lg)"
      @update:checked-row-keys="handleCheck"
    />

    <!-- 编辑弹窗 -->
    <n-modal v-model:show="modalVisible" preset="card" title="编辑变量" style="width:500px">
      <n-form label-placement="left" label-width="100px">
        <n-form-item label="Key" required>
          <n-input v-model:value="form.key" :disabled="isEditing" placeholder="例如: pc.cpu" size="large" />
        </n-form-item>
        <n-form-item label="Value" required>
          <n-input v-model:value="form.value" placeholder="变量值" size="large" />
        </n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="form.type" :options="typeOptions" placeholder="数据类型" />
        </n-form-item>
        <n-form-item label="来源">
          <n-input v-model:value="form.source" placeholder="例如: windows-agent" />
        </n-form-item>
        <n-form-item label="保留天数">
          <n-input-number v-model:value="form.retention_days" :min="1" :max="3650" placeholder="180" />
          <span style="margin-left:10px;font-size:12px;color:var(--text-secondary)">默认 180 天</span>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button size="large" @click="modalVisible = false">取消</n-button>
          <n-button size="large" type="primary" @click="handleSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton, NDataTable, NInput, NModal, NForm, NFormItem,
  NSelect, NInputNumber, NSpace, NPopconfirm, NUpload, useMessage
} from 'naive-ui'
import { kvApi } from '../api'
import type { KvEntry, KvSetRequest } from '../types'

const message = useMessage()
const data = ref<KvEntry[]>([])
const searchKey = ref('')
const checkedKeys = ref<string[]>([])
const modalVisible = ref(false)
const isEditing = ref(false)

const form = ref<KvSetRequest & { key: string; retention_days: number }>({
  key: '', value: '', type: 'string', source: '', retention_days: 180
})

const typeOptions = [
  { label: 'string', value: 'string' },
  { label: 'int', value: 'int' },
  { label: 'float', value: 'float' },
  { label: 'bool', value: 'bool' },
  { label: 'json', value: 'json' }
]

const filteredData = computed(() => {
  if (!searchKey.value) return data.value
  const q = searchKey.value.toLowerCase()
  return data.value.filter(r => r.key.toLowerCase().includes(q))
})

const columns = [
  { type: 'selection' as const, width: 40 },
  { title: 'Key', key: 'key', width: 180, ellipsis: { tooltip: true } },
  { title: 'Value', key: 'value', width: 220, ellipsis: { tooltip: true } },
  { title: '类型', key: 'type', width: 80 },
  { title: '来源', key: 'source', width: 140 },
  {
    title: '保留天数', key: 'retention_days', width: 90,
    render(row: KvEntry) {
      return row.retention_days || 180
    }
  },
  {
    title: '更新时间', key: 'updated_at', width: 170,
    render(row: KvEntry) {
      return row.updated_at || '—'
    }
  },
  {
    title: '操作', key: 'actions', width: 160,
    render(row: KvEntry) {
      return h('div', { style: 'display:flex;gap:4px' }, [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { default: () => '编辑' }),
        h(NPopconfirm, {
          onPositiveClick: () => handleDelete(row.key)
        }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除？此操作不可撤销'
        })
      ])
    }
  }
]

function handleCheck(keys: string[]) {
  checkedKeys.value = keys
}

function openCreateModal() {
  isEditing.value = false
  form.value = { key: '', value: '', type: 'string', source: '', retention_days: 180 }
  modalVisible.value = true
}

function openEditModal(row: KvEntry) {
  isEditing.value = true
  form.value = {
    key: row.key,
    value: row.value,
    type: row.type || 'string',
    source: row.source || '',
    retention_days: row.retention_days || 180
  }
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.key) return
  try {
    await kvApi.set({ key: form.value.key, value: form.value.value, type: form.value.type, source: form.value.source, retention_days: form.value.retention_days })
    modalVisible.value = false
    message.success('保存成功')
    await loadData()
  } catch { message.error('保存失败') }
}

async function handleDelete(key: string) {
  try {
    await kvApi.delete(key)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
}

async function handleBatchDelete() {
  try {
    await kvApi.batchDelete({ keys: checkedKeys.value })
    message.success(`已删除 ${checkedKeys.value.length} 个变量`)
    checkedKeys.value = []
    await loadData()
  } catch { message.error('批量删除失败') }
}

async function handleExport() {
  try {
    const res = await kvApi.exportJson()
    const blob = new Blob([res.data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `kv_export_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch { message.error('导出失败') }
}

async function handleImport({ file }: { file: File }) {
  try {
    await kvApi.importJson(file.file!)
    message.success('导入成功')
    await loadData()
  } catch { message.error('导入失败，请检查文件格式') }
}

async function loadData() {
  try {
    const res = await kvApi.list()
    if (res.data) data.value = res.data
  } catch { data.value = [] }
}

onMounted(loadData)
</script>

<style scoped>
:deep(.n-upload) {
  display: inline-flex;
}
</style>
