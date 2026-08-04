// ============================================================
// Vitest 专用配置(vitest 优先读取本文件,不依赖 vite.config.ts)
// 独立文件的好处:服务器跑 vite dev 时不会因为缺 vitest 而启动失败
// ============================================================
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
  }
})
