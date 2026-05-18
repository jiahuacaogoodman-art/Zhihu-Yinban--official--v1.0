import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import NurseApp from '../nurse-views/NurseApp.vue'

/**
 * NurseApp 冒烟测试 — 验证护工端布局渲染
 */

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div>patient-list-stub</div>' } },
      { path: '/patient/:id', component: { template: '<div>patient-detail-stub</div>' } },
    ],
  })
}

describe('NurseApp.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        }),
      ),
    )
  })

  it('renders the nurse header with brand', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(NurseApp, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('智护银伴')
    expect(wrapper.text()).toContain('护工端')
  })

  it('renders management link', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(NurseApp, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('管理端')
  })

  it('renders router-view content', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(NurseApp, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('patient-list-stub')
  })
})
