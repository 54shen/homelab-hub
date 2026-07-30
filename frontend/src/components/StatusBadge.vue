<template>
  <span class="status-badge" :class="status">
    <span class="status-dot" :class="status"></span>
    {{ text }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  online: boolean
  size?: 'small' | 'default'
}>()

const status = computed(() => (props.online ? 'online' : 'offline'))
const text = computed(() => (props.online ? '在线' : '离线'))
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: var(--radius-full);
}
.status-badge.online {
  color: var(--color-success);
  background: rgba(34, 197, 94, 0.08);
}
.status-badge.offline {
  color: var(--color-danger);
  background: rgba(239, 68, 68, 0.06);
}
</style>
