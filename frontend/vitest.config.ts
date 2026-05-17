import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

/**
 * 单独 vitest 配置 —— 不和 vite.config.ts 合并 test 字段。
 *
 * 原因:vitest 2.x 内部 bundle 了自己的 vite 副本,如果在 vite.config.ts 里
 * 直接写 test:{...},vue-tsc 会拿到两套互不兼容的 vite 类型定义,出现
 * 巨长的 "Type 'Plugin<Api>' is not assignable to type 'PluginOption'" 报错。
 *
 * 用 vitest 自己的 defineConfig + mergeConfig 跑过它自己的 vite,
 * 类型一致,vue-tsc 也不会扫到本文件(它只在 npm test 时被读)。
 */
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'happy-dom',
      globals: true,
    },
  }),
)
