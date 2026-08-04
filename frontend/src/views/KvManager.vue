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

    <!-- 搜索 + 分类 -->
    <div class="filter-row">
      <n-input
        v-model:value="searchKey"
        placeholder="搜索 key..."
        clearable
        size="large"
        style="flex: 1; min-width: 200px"
      >
        <template #prefix>
          <ion-icon name="search-outline" style="color:var(--text-secondary)"></ion-icon>
        </template>
      </n-input>
      <n-select
        v-model:value="filterPrefix"
        :options="prefixOptions"
        placeholder="按设备/前缀"
        clearable
        size="large"
        style="width: 180px"
      />
      <n-select
        v-model:value="filterSource"
        :options="sourceOptions"
        placeholder="按来源"
        clearable
        size="large"
        style="width: 150px"
      />
      <n-button size="large" quaternary @click="groupByPrefix = !groupByPrefix" :type="groupByPrefix ? 'primary' : 'default'">
        <ion-icon name="layers-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
        分组
      </n-button>
    </div>

    <!-- 分组视图 -->
    <div v-if="groupByPrefix" class="grouped-view">
      <n-card v-for="[prefix, items] in groupedData" :key="prefix" size="small" :title="`${prefix} (${items.length})`" class="group-card">
        <n-data-table
          :columns="groupColumns"
          :data="items"
          :bordered="false"
          :single-line="false"
          size="small"
          :row-key="(r: KvEntry) => r.key"
          :pagination="false"
        />
      </n-card>
      <n-empty v-if="groupedData.length === 0" description="无匹配变量" style="margin-top:60px" />
    </div>

    <!-- 平铺视图 -->
    <n-data-table
      v-else
      :columns="columns"
      :data="filteredData"
      :bordered="false"
      :single-line="false"
      size="small"
      :row-key="(r: KvEntry) => r.key"
      :checked-row-keys="checkedKeys"
      :pagination="{
        page: kvPage,
        pageSize: kvPageSize,
        showSizePicker: true,
        pageSizes: [10, 20, 50, 100]
      }"
      style="background: var(--bg-card); border-radius: var(--radius-lg)"
      @update:page="kvPage = $event"
      @update:page-size="kvPageSize = $event"
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

    <!-- 历史记录弹窗 -->
    <HistoryModal v-model:show="showHistory" :key-prop="historyKey" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import {
  NButton, NCard, NDataTable, NEmpty, NInput, NModal, NForm, NFormItem,
  NSelect, NInputNumber, NSpace, NPopconfirm, NUpload, useMessage
} from 'naive-ui'
import { useWebSocket } from '../composables/useWebSocket'
import { useFieldLabels } from '../composables/useFieldLabels'
import { kvApi } from '../api'
import HistoryModal from '../components/HistoryModal.vue'
import type { KvEntry, KvSetRequest } from '../types'

const message = useMessage()
const { labelOf } = useFieldLabels()
const data = ref<KvEntry[]>([])
const showHistory = ref(false)
const historyKey = ref('')
const searchKey = ref('')
const filterPrefix = ref<string | null>(null)
const filterSource = ref<string | null>(null)
const groupByPrefix = ref(false)
const checkedKeys = ref<(string | number)[]>([])
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
  let rows = data.value
  if (searchKey.value) {
    const q = searchKey.value.toLowerCase()
    rows = rows.filter(r => r.key.toLowerCase().includes(q))
  }
  if (filterPrefix.value) {
    rows = rows.filter(r => r.key.startsWith(filterPrefix.value! + '.'))
  }
  if (filterSource.value) {
    rows = rows.filter(r => r.source === filterSource.value)
  }
  return rows
})

// 自动提取前缀列表（key 中第一个 . 之前的部分）
const prefixOptions = computed(() => {
  const prefixes = new Set<string>()
  for (const r of data.value) {
    const dot = r.key.indexOf('.')
    if (dot > 0) prefixes.add(r.key.slice(0, dot))
  }
  return [...prefixes].sort().map(p => ({ label: p, value: p }))
})

// 自动提取来源列表
const sourceOptions = computed(() => {
  const sources = new Set<string>()
  for (const r of data.value) {
    if (r.source) sources.add(r.source)
  }
  return [...sources].sort().map(s => ({ label: s, value: s }))
})

// 按前缀分组
const groupedData = computed(() => {
  const groups = new Map<string, KvEntry[]>()
  for (const r of filteredData.value) {
    const dot = r.key.indexOf('.')
    const prefix = dot > 0 ? r.key.slice(0, dot) : '(无前缀)'
    if (!groups.has(prefix)) groups.set(prefix, [])
    groups.get(prefix)!.push(r)
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})

const columns = [
  { type: 'selection' as const, width: 40 },
  {
    title: 'Key', key: 'key', width: 180, ellipsis: { tooltip: true },
    render(row: KvEntry) {
      const label = labelOf(row.key)
      const text = label === row.key ? row.key : label
      // 点击 key 直接弹窗查看历史
      return h('span', {
        class: 'key-link',
        title: `${row.key} (点击查看历史)`,
        onClick: () => { historyKey.value = row.key; showHistory.value = true }
      }, text)
    }
  },
  { title: 'Value', key: 'value', width: 160, ellipsis: { tooltip: true } },
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
        // 历史(最常用)放在修改前面
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => { historyKey.value = row.key; showHistory.value = true } }, { default: () => '历史' }),
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

// 分组视图列（无 checkbox，前缀已在标题显示）
const groupColumns = columns.filter(c => c.type !== 'selection')

function handleCheck(keys: (string | number)[]) {
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
    const username = localStorage.getItem('sc_username') || 'admin'
    const src = form.value.source || `${username}(Web)`
    await kvApi.set({ key: form.value.key, value: form.value.value, type: form.value.type, source: src, retention_days: form.value.retention_days })
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
    await kvApi.batchDelete({ keys: checkedKeys.value as string[] })
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function handleImport(data: any) {
  try {
    const f = data?.file?.file as File | undefined
    if (!f) return
    await kvApi.importJson(f)
    message.success('导入成功')
    await loadData()
  } catch { message.error('导入失败，请检查文件格式') }
}

const kvPage = ref(1)
const kvPageSize = ref(20)

async function loadData() {
  try {
    const res = await kvApi.list()
    if (res.data) data.value = res.data
  } catch { data.value = [] }
}

// ---- WebSocket 实时更新 ----
const { on } = useWebSocket()
let cleanupWs: (() => void) | null = null

onMounted(async () => {
  await loadData()
  cleanupWs = on((event, payload: any) => {
    if (event === 'kv.changed') {
      const idx = data.value.findIndex((r: KvEntry) => r.key === payload.key)
      if (idx >= 0) {
        data.value[idx] = {
          ...data.value[idx],
          value: payload.value,
          source: payload.source || data.value[idx].source,
          updated_at: payload.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' ')
        }
      } else {
        // 新变量，插入头部
        data.value.unshift({
          id: 0,
          key: payload.key,
          value: payload.value,
          type: 'string',
          source: payload.source || 'ws',
          updated_at: payload.changed_at || new Date().toLocaleString('sv-SE').replace('T', ' '),
          expire_seconds: null,
          retention_days: 180
        })
      }
    }
    if (event === 'kv.deleted') {
      data.value = data.value.filter(r => r.key !== payload.key)
    }
  })
})

onUnmounted(() => {
  cleanupWs?.()
})
</script>

<style scoped>
:deep(.n-upload) {
  display: inline-flex;
}
.filter-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.grouped-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.group-card {
  background: var(--bg-card);
}
.group-card :deep(.n-card-header) {
  font-size: 13px;
  font-weight: 600;
}
</style>
