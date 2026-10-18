/// <reference types="vitest/config" />
// 上面这行让 Vite 的 defineConfig 认识下面的 test 块；删掉它，test 会被当成未知字段报类型错。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// 版本与构建信息在构建期注入（docker build --build-arg，由发布流水线从 git tag 算出）。
// 宿主机直跑（npm run dev / 本地 npm run build）时退化成 dev / unknown——刻意的显式退化，
// 留空在界面上看不出来。
const APP_VERSION = process.env.APP_VERSION ?? 'dev'
const APP_COMMIT = process.env.APP_COMMIT ?? 'unknown'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // 单测（Vitest）复用这份配置：别名 @ 与生产构建同一套，不会两处各写一遍。
  // happy-dom 只提供 localStorage / document 这类基础能力，够纯逻辑测试用，比 jsdom 轻。
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.test.ts']
  },
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
    __APP_COMMIT__: JSON.stringify(APP_COMMIT)
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: ${FRONTEND_PORT},
    proxy: {
      // 本机开发：前端 dev server 把 /api 代理到后端；生产由反代做同一件事。
      '/api': {
        target: 'http://127.0.0.1:${BACKEND_PORT}',
        changeOrigin: true
      }
    }
  }
})
