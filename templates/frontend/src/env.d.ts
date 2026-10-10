/// <reference types="vite/client" />

// 构建期注入的版本与构建信息，值在 vite.config.ts 的 define 里生成，
// 源头是 docker build 的 --build-arg。宿主机直跑时分别是 dev / unknown。
declare const __APP_VERSION__: string
declare const __APP_COMMIT__: string

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
