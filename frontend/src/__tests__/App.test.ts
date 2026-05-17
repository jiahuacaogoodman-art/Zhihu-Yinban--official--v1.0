import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import App from '../App.vue'

/**
 * Phase 1 冒烟测试 — 唯一目的:让 CI 能跑 `npm run test` 并通过。
 * Phase 4 末期开始按 RFC §6.2 加 e2e。
 */

// 让 App.vue 中 import 的 __BUILD_TIME__ 在测试环境里有值
;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

describe('App.vue (Phase 1 placeholder)', () => {
  beforeEach(() => {
    // 测试环境 fetch 默认 mock 成 unreachable;不连真实后端
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ status: 'ok' }),
        }),
      ),
    )
  })

  it('renders the Hello v2 banner', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('Hello v2')
    expect(wrapper.text()).toContain('Phase 1')
  })

  it('shows the build time injected by vite define', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('2026-05-17T00:00:00Z')
  })

  it('probes /health and reflects the status', async () => {
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('ok')
  })
})
