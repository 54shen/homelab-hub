<template>
  <div class="refresh-control">
    <template v-for="opt in resolvedOptions" :key="opt.value">
      <span
        class="rc-btn"
        :class="{ active: modelValue === opt.value || (opt.value === -1 && showCustomInput) }"
        @click="opt.value === -1 ? toggleCustom() : $emit('update:modelValue', opt.value)"
      >{{ opt.label }}</span>
    </template>
    <!-- 自定义输入 -->
    <input
      v-if="showCustomInput"
      ref="customInputRef"
      class="rc-input"
      v-model="customText"
      placeholder="秒"
      @keydown.enter="onCustomConfirm"
      @blur="onCustomBlur"
    />
    <span v-if="modelValue > 0" class="rc-dot" :style="{ animationDuration: Math.max(modelValue, 0.1) + 's' }"></span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  modelValue: number
  /** 自定义额外的选项，如 [{ label: '0.5s', value: 0.5 }] */
  customOptions?: { label: string; value: number }[]
}>()

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const showCustomInput = ref(false)
const customText = ref('')
const customInputRef = ref<HTMLInputElement | null>(null)

const baseOptions = [
  { label: '关', value: 0 },
  { label: '1s', value: 1 },
  { label: '3s', value: 3 },
  { label: '5s', value: 5 },
  { label: '+', value: -1 },
]

const resolvedOptions = computed(() => {
  const opts = props.customOptions ? [...props.customOptions] : []
  for (const b of baseOptions) {
    if (!opts.some(o => o.value === b.value)) {
      opts.push(b)
    }
  }
  return opts
})

function toggleCustom() {
  showCustomInput.value = !showCustomInput.value
  if (showCustomInput.value) {
    customText.value = ''
    setTimeout(() => customInputRef.value?.focus(), 50)
  }
}

function onCustomBlur() {
  setTimeout(() => {
    if (document.activeElement !== customInputRef.value) {
      showCustomInput.value = false
    }
  }, 150)
}

function onCustomConfirm() {
  const val = parseFloat(customText.value)
  if (!isNaN(val) && val >= 0) {
    emit('update:modelValue', val)
    showCustomInput.value = false
    customText.value = ''
  }
}
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
.rc-input {
  width: 52px;
  font-size: 12px;
  padding: 4px 6px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  text-align: center;
  outline: none;
  color: var(--text-primary);
  background: #fff;
}
.rc-input:focus {
  border-color: var(--color-primary, #5B8DEF);
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
