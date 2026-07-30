<template>
  <div class="stat-card" :class="{ clickable: !!to }" @click="to && $router.push(to)">
    <div class="stat-icon" :style="{ background: iconBg }">
      <ion-icon :name="icon" :style="{ color: iconColor }"></ion-icon>
    </div>
    <div class="stat-body">
      <div class="stat-value">
        <span class="value-highlight">{{ primary }}</span>
        <span v-if="secondary !== undefined" class="value-total"> / {{ secondary }}</span>
      </div>
      <div class="stat-label">{{ label }}</div>
    </div>
    <div v-if="trend !== undefined" class="stat-trend" :class="trend >= 0 ? 'up' : 'down'">
      <ion-icon :name="trend >= 0 ? 'trending-up-outline' : 'trending-down-outline'" style="font-size:14px;vertical-align:-2px"></ion-icon>
      {{ Math.abs(trend) }}%
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  iconBg: string
  iconColor: string
  primary: string | number
  secondary?: string | number
  label: string
  trend?: number
  to?: string
}>()
</script>

<style scoped>
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}
.stat-card.clickable {
  cursor: pointer;
}
.stat-card.clickable:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-1px);
}

.stat-icon {
  width: 46px; height: 46px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}
.stat-body { flex: 1; min-width: 0; }
.value-highlight {
  font-size: 28px; font-weight: 700; color: var(--text-primary);
  letter-spacing: -0.5px;
}
.value-total { font-size: 16px; font-weight: 400; color: var(--text-secondary); }
.stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; font-weight: 500; }

.stat-trend {
  font-size: 12px; font-weight: 600; flex-shrink: 0; padding-top: 4px;
  display: flex; align-items: center; gap: 2px;
}
.stat-trend.up { color: var(--color-success); }
.stat-trend.down { color: var(--color-danger); }
</style>
