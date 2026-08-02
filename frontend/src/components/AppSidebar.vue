<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
          <rect width="30" height="30" rx="9" fill="#5B8DEF"/>
          <path d="M7 11h7v8H7zM13 15h4v4h-4zM19 9h4v10h-4z" fill="white" opacity="0.9"/>
        </svg>
      </div>
      <span class="brand-text">Shared Center</span>
    </div>

    <nav class="sidebar-nav">
      <template v-for="group in menuGroups" :key="group.label">
        <div class="nav-group-label">{{ group.label }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="onNavClick"
        >
          <ion-icon :name="item.icon" class="nav-icon"></ion-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </template>
    </nav>

    <div class="sidebar-footer">
      <span class="version">v1.0.0</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ toggle: [] }>()

const route = useRoute()

function onNavClick() {
  if (window.innerWidth < 768) {
    emit('toggle')
  }
}

const menuGroups = [
  {
    label: '概览',
    items: [
      { path: '/dashboard', label: '仪表盘', icon: 'grid-outline' }
    ]
  },
  {
    label: '数据',
    items: [
      { path: '/variables', label: '变量管理', icon: 'code-outline' },
      { path: '/mappings', label: '字段映射', icon: 'language-outline' }
    ]
  },
  {
    label: '设备',
    items: [
      { path: '/devices', label: '设备管理', icon: 'hardware-chip-outline' }
    ]
  },
  {
    label: '自动化',
    items: [
      { path: '/alerts', label: '告警规则', icon: 'notifications-outline' },
      { path: '/webhooks', label: 'Webhook', icon: 'link-outline' }
    ]
  },
  {
    label: '系统',
    items: [
      { path: '/logs', label: '系统日志', icon: 'document-text-outline' },
      { path: '/settings', label: '设置', icon: 'settings-outline' }
    ]
  }
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  z-index: 100;
  user-select: none;
  border-right: 1px solid var(--border-light);
  transition: transform 0.25s ease;
}

/* ---- Brand ---- */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  height: var(--topbar-height);
  border-bottom: 1px solid var(--border-light);
}
.brand-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.brand-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

/* ---- Nav ---- */
.sidebar-nav {
  flex: 1;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow-y: auto;
}

.nav-group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 14px 10px 6px;
}
.nav-group-label:first-child {
  padding-top: 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--text-sidebar);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
  position: relative;
}
.nav-item:hover {
  background: var(--bg-sidebar-hover);
  color: var(--text-primary);
}
.nav-item.active {
  background: var(--bg-sidebar-active);
  color: var(--text-sidebar-active);
  font-weight: 600;
}

.nav-icon {
  font-size: 20px;
  flex-shrink: 0;
  opacity: 0.7;
}
.nav-item.active .nav-icon {
  opacity: 1;
  color: var(--color-info);
}

/* ---- Collapsed ---- */
.sidebar.collapsed {
  transform: translateX(-100%);
}

/* ---- Footer ---- */
.sidebar-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border-light);
}
.version {
  font-size: 11px;
  color: var(--text-secondary);
}

/* ---- 移动端：侧边栏浮在内容上方 ---- */
@media (max-width: 767px) {
  .sidebar {
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.12);
  }
}
</style>
