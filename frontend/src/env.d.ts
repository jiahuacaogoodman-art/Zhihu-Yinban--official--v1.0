/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// 由 vite.config.ts 的 define 注入(Phase 1 占位页用来显示构建时间)
declare const __BUILD_TIME__: string
