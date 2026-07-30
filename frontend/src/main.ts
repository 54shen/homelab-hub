// ============================================================
// Shared Center — 应用入口
// ============================================================
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initWebSocket } from './composables/useWebSocket'
import './styles/global.css'

const app = createApp(App)
app.use(router)
app.mount('#app')

// 全局启动 WebSocket 连接
initWebSocket()
