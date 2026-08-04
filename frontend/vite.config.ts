import { defineConfig } from 'vitest/config'
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
  test: {
    environment: 'jsdom',
    coverage: {
      // Node 18 不支持 v8 覆盖率所需的 node:inspector/promises,用 istanbul
      provider: 'istanbul'
    }
  },
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
