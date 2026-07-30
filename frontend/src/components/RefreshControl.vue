<template>
  <div class="refresh-control">
    <span
      v-for="opt in options"
      :key="opt.value"
      class="rc-btn"
      :class="{ active: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </span>
    <span v-if="modelValue > 0" class="rc-dot" :style="{ animationDuration: modelValue + 's' }"></span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: number }>()
defineEmits<{ 'update:modelValue': [value: number] }>()

const options = [
  { label: '关', value: 0 },
  { label: '1s', value: 1 },
  { label: '3s', value: 3 },
  { label: '5s', value: 5 },
]
</script>

<style scoped>
.refresh-control {
  display: inline-flex;
  align-items: center;
  gap: 0;
  background: var(--border-light, #EDF0F4);
  border-radius: 8px;
  padding: 2px;
}
.rc-btn {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary, #64748B);
  transition: all 0.15s;
  user-select: none;
  font-variant-numeric: tabular-nums;
}
.rc-btn:hover { color: var(--text-primary, #1E293B); }
.rc-btn.active {
  background: #fff;
  color: var(--color-primary, #5B8DEF);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.rc-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--color-success, #22C55E);
  margin-left: 6px;
  animation: rc-pulse 1s ease-in-out infinite;
}
@keyframes rc-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
</style>
