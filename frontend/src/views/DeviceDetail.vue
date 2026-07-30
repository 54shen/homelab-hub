<template>
  <div class="page-container">
    <div class="back-row">
      <n-button text @click="$router.push('/devices')">
        <ion-icon name="arrow-back-outline" style="margin-right:4px;vertical-align:-2px"></ion-icon>
        返回设备列表
      </n-button>
      <RefreshControl v-model="refreshInterval" />
    </div>

    <n-spin :show="loading">
      <template v-if="device">
        <!-- 设备头部 -->
        <div class="detail-hero">
          <div class="hero-left">
            <span class="hero-icon">{{ iconForType(device.type) }}</span>
            <div>
              <h1 class="hero-name">{{ device.name }}</h1>
              <p class="hero-sub">{{ device.hostname || device.id }}</p>
            </div>
            <StatusBadge :online="device.online" style="margin-left:12px" />
          </div>
          <n-tag size="small" :bordered="false" round>{{ device.group || '默认' }}</n-tag>
        </div>

        <!-- 资源指标 -->
        <div v-if="device.online" class="card-grid" style="margin-top:16px">
          <n-card size="small" title="CPU">
            <div class="metric-big">{{ device.cpu ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.cpu ?? 0" :color="device.cpu && device.cpu > 80 ? '#EF4444' : '#5B8DEF'" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="内存">
            <div class="metric-big">{{ device.memory ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.memory ?? 0" color="#22C55E" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="磁盘">
            <div class="metric-big">{{ device.disk ?? '—' }}<span class="unit">%</span></div>
            <n-progress type="line" :percentage="device.disk ?? 0" color="#F59E0B" :height="6" :border-radius="3" />
          </n-card>
          <n-card size="small" title="运行时长">
            <div class="metric-big-text">{{ device.uptime || '—' }}</div>
          </n-card>
        </div>

        <!-- 信息详情 -->
        <div class="card-grid-2" style="margin-top:16px">
          <n-card size="small" title="基本信息">
            <n-descriptions label-placement="left" :column="1" bordered size="small">
              <n-descriptions-item label="设备 ID">{{ device.id }}</n-descriptions-item>
              <n-descriptions-item label="名称">{{ device.name }}</n-descriptions-item>
              <n-descriptions-item label="主机名">{{ device.hostname || '—' }}</n-descriptions-item>
              <n-descriptions-item label="IP 地址">{{ device.ip || '—' }}</n-descriptions-item>
              <n-descriptions-item label="MAC 地址">{{ device.mac || '—' }}</n-descriptions-item>
              <n-descriptions-item label="操作系统">{{ device.os || '—' }}</n-descriptions-item>
            </n-descriptions>
          </n-card>
          <n-card size="small" title="运行信息">
            <n-descriptions label-placement="left" :column="1" bordered size="small">
              <n-descriptions-item label="类型">{{ device.type }}</n-descriptions-item>
              <n-descriptions-item label="分组">{{ device.group || '默认' }}</n-descriptions-item>
              <n-descriptions-item label="版本">v{{ device.version }}</n-descriptions-item>
              <n-descriptions-item label="注册时间">{{ device.registered_at || '—' }}</n-descriptions-item>
              <n-descriptions-item label="最后心跳">{{ device.last_heartbeat || '—' }}</n-descriptions-item>
              <n-descriptions-item label="备注">{{ device.notes || '无' }}</n-descriptions-item>
            </n-descriptions>
          </n-card>
        </div>

        <!-- 设备变量 -->
        <n-card title="设备变量" size="small" style="margin-top:16px">
          <template #header-extra>
            <span style="font-size:12px;color:var(--text-secondary)">{{ variables.length }} 个</span>
          </template>
          <n-empty v-if="variables.length === 0" description="该设备暂无变量数据" />
          <n-data-table v-else :columns="varColumns" :data="variables" :bordered="false" size="small" />
        </n-card>

        <!-- 心跳历史 -->
        <n-card title="心跳历史" size="small" style="margin-top:16px">
          <div ref="heartbeatChartRef" class="chart-box"></div>
        </n-card>
      </template>

      <n-empty v-else-if="!loading" description="设备不存在" style="margin-top:80px" />
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem,
  NEmpty, NProgress, NSpin, NTag
} from 'naive-ui'
import * as echarts from 'echarts'
import StatusBadge from '../components/StatusBadge.vue'
import RefreshControl from '../components/RefreshControl.vue'
import { useRefreshInterval } from '../composables/useRefreshInterval'
import { deviceApi } from '../api'
import type { Device, KvEntry } from '../types'

const route = useRoute()
const router = useRouter()
const deviceId = route.params.id as string

const loading = ref(true)
const device = ref<Device | null>(null)
const variables = ref<KvEntry[]>([])
const heartbeatChartRef = ref<HTMLElement | null>(null)
let hbChart: echarts.ECharts | null = null

const varColumns = [
  { title: 'Key', key: 'key', width: 200 },
  { title: 'Value', key: 'value', width: 200 },
  { title: '类型', key: 'type', width: 80 },
  { title: '更新时间', key: 'updated_at', width: 170 }
]

function iconForType(type: string): string {
  const map: Record<string, string> = {
    computer: '🖥️', server: '📦', nas: '💾', iot: '🏠',
    cloud: '☁️', docker: '🐳', vm: '📀', router: '📡'
  }
  return map[type] || '📡'
}

const refreshInterval = useRefreshInterval()

async function loadData() {
  loading.value = true
  try {
    const [dRes, vRes] = await Promise.all([
      deviceApi.get(deviceId),
      deviceApi.variables(deviceId)
    ])
    if (dRes.data) {
      device.value = dRes.data
    }
    if (vRes.data) {
      variables.value = vRes.data
    }
  } catch {
    device.value = null
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setInterval> | null = null
function startTimer(sec: number) {
  if (timer) { clearInterval(timer); timer = null }
  if (sec > 0) timer = setInterval(loadData, sec * 1000)
}
watch(refreshInterval, startTimer)

onMounted(async () => {
  await loadData()
  await nextTick()
  if (heartbeatChartRef.value) {
    hbChart = echarts.init(heartbeatChartRef.value)
    hbChart.setOption({
      grid: { top: 8, right: 12, bottom: 24, left: 40 },
      xAxis: { type: 'category' as const, data: [], axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value' as const, max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
      series: [{
        data: [], type: 'line' as const, smooth: true, symbol: 'none' as const,
        lineStyle: { color: '#5B8DEF', width: 2 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#5B8DEF30' }, { offset: 1, color: '#5B8DEF04' }]) }
      }]
    })
  }
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.back-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--gap-md); }
.detail-hero {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg-card); border: 1px solid var(--border-card);
  border-radius: var(--radius-lg); padding: 20px 24px;
  box-shadow: var(--shadow-card);
}
.hero-left { display: flex; align-items: center; gap: 14px; }
.hero-icon { font-size: 40px; }
.hero-name { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.hero-sub { font-size: 13px; color: var(--text-secondary); font-family: monospace; margin-top: 2px; }

.metric-big { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.metric-big .unit { font-size: 16px; font-weight: 400; color: var(--text-secondary); margin-left: 2px; }
.metric-big-text { font-size: 20px; font-weight: 600; color: var(--text-primary); }

.chart-box { width: 100%; height: 220px; }
</style>
