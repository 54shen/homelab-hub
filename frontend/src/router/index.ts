// ============================================================
// Shared Center — 路由配置
// ============================================================
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
      meta: { title: '登录', public: true }
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('../views/Dashboard.vue'),
          meta: { title: '仪表盘', icon: 'grid-outline', group: '概览' }
        },
        {
          path: 'variables',
          name: 'Variables',
          component: () => import('../views/KvManager.vue'),
          meta: { title: '变量管理', icon: 'code-outline', group: '数据' }
        },
        {
          path: 'history',
          name: 'History',
          component: () => import('../views/HistoryViewer.vue'),
          meta: { title: '历史记录', icon: 'time-outline', group: '数据' }
        },
        {
          path: 'devices',
          name: 'Devices',
          component: () => import('../views/DeviceManager.vue'),
          meta: { title: '设备管理', icon: 'hardware-chip-outline', group: '设备' }
        },
        {
          path: 'devices/:id',
          name: 'DeviceDetail',
          component: () => import('../views/DeviceDetail.vue'),
          meta: { title: '设备详情', icon: 'hardware-chip-outline', group: '设备' }
        },
        {
          path: 'alerts',
          name: 'Alerts',
          component: () => import('../views/AlertManager.vue'),
          meta: { title: '告警规则', icon: 'notifications-outline', group: '自动化' }
        },
        {
          path: 'webhooks',
          name: 'Webhooks',
          component: () => import('../views/WebhookManager.vue'),
          meta: { title: 'Webhook', icon: 'link-outline', group: '自动化' }
        },
        {
          path: 'logs',
          name: 'Logs',
          component: () => import('../views/SystemLogs.vue'),
          meta: { title: '系统日志', icon: 'document-text-outline', group: '系统' }
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('../views/Settings.vue'),
          meta: { title: '设置', icon: 'settings-outline', group: '系统' }
        }
      ]
    }
  ]
})

// ---- 路由守卫：未登录强制跳转登录页 ----
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('sc_token')
  if (to.meta.public) {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router
