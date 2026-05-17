import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import App from '../App.vue'

/**
 * Phase 2 冒烟测试 — 验证 App.vue(组件 showcase)能正常渲染。
 * Phase 4 末期开始按 RFC §6.2 加 e2e。
 */

// 让 App.vue 中 import 的 __BUILD_TIME__ 在测试环境里有值
;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

describe('App.vue (Phase 2 component showcase)', () => {
  beforeEach(() => {
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

  it('renders the Phase 2 showcase headline', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('基础组件已落地')
    expect(wrapper.text()).toContain('Phase 2')
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

  it('renders all 6 base component names in chips', () => {
    const wrapper = mount(App)
    const names = ['GlassPanel', 'Btn', 'Field', 'Chip', 'Dialog', 'Toast']
    for (const name of names) {
      expect(wrapper.text()).toContain(name)
    }
  })

  it('renders Btn variants', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('主按钮')
    expect(wrapper.text()).toContain('Outline')
    expect(wrapper.text()).toContain('Ghost')
    expect(wrapper.text()).toContain('删除')
  })
})
