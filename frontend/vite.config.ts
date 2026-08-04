// 注意:此文件只从 'vite' import —— 测试配置在 vitest.config.ts(vitest 优先读取),
// 这样服务器没装 vitest 时 vite dev/build 也能正常启动
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag.startsWith('ion-')
        }
      }
    })
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    open: true,
    allowedHosts: ['sc.54shen.cn', '.54shen.cn'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'http://127.0.0.1:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
