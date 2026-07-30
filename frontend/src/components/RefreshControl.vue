<template>
  <div class="refresh-control">
    <!-- 预设按钮 -->
    <span
      v-for="opt in presets"
      :key="opt.value"
      class="rc-btn"
      :class="{ active: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >{{ opt.label }}</span>

    <!-- 自定义值按钮（非预设值时显示） -->
    <span
      v-if="!isPreset && !showCustomInput"
      class="rc-btn active"
      @click="startEdit()"
    >{{ formatValue(modelValue) }}</span>

    <!-- + 按钮 / 自定义输入 -->
    <template v-if="showCustomInput">
      <input
        ref="customInputRef"
        class="rc-input"
        v-model="customText"
        placeholder="0.5"
        @keydown.enter="onCustomConfirm"
        @blur="onCustomBlur"
      />
    </template>
    <span
      v-else
      class="rc-btn"
      :class="{ active: false }"
      @click="startEdit()"
    >+</span>

    <span v-if="modelValue > 0" class="rc-dot" :style="{ animationDuration: Math.max(modelValue, 0.1) + 's' }"></span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'

const props = defineProps<{ modelValue: number }>()

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const presets = [
  { label: '关', value: 0 },
  { label: '1s', value: 1 },
  { label: '3s', value: 3 },
  { label: '5s', value: 5 },
]

const isPreset = computed(() => presets.some(p => p.value === props.modelValue))

const showCustomInput = ref(false)
const customText = ref('')
const customInputRef = ref<HTMLInputElement | null>(null)

function formatValue(v: number): string {
  if (v >= 1) return `${v}s`
  return `${(v * 1000).toFixed(0)}ms`
}

function startEdit() {
  showCustomInput.value = true
  customText.value = props.modelValue > 0 ? String(props.modelValue) : ''
  nextTick(() => {
    customInputRef.value?.focus()
    customInputRef.value?.select()
  })
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
  white-space: nowrap;
}
.rc-btn:hover { color: var(--text-primary, #1E293B); }
.rc-btn.active {
  background: #fff;
  color: var(--color-primary, #5B8DEF);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.rc-input {
  width: 44px;
  font-size: 12px;
  padding: 4px 6px;
  border: 1px solid var(--color-primary, #5B8DEF);
  border-radius: 6px;
  text-align: center;
  outline: none;
  color: var(--text-primary);
  background: #fff;
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
