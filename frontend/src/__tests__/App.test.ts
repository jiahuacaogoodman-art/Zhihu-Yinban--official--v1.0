import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from '../App.vue'

/**
 * Phase 3 冒烟测试 — App.vue 是 layout + router-view
 */

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

// 最小 router 配置(覆盖所有 Phase 4 路由,避免 Vue Router 警告)
function makeRouter() {
  return createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: '/', redirect: '/beds' },
      { path: '/login', component: { template: '<div>login-stub</div>' } },
      { path: '/beds', component: { template: '<div>beds-stub</div>' } },
      { path: '/ehr', component: { template: '<div>ehr-stub</div>' } },
      { path: '/handovers', component: { template: '<div>handovers-stub</div>' } },
      { path: '/incidents', component: { template: '<div>incidents-stub</div>' } },
      { path: '/care-records', component: { template: '<div>care-records-stub</div>' } },
      { path: '/showcase', component: { template: '<div>showcase-stub</div>' } },
    ],
  })
}

describe('App.vue (Phase 3 layout)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
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

  it('renders the sidebar with brand name', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('智护银伴')
    expect(wrapper.text()).toContain('v2')
  })

  it('renders navigation links', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('床位管理')
    expect(wrapper.text()).toContain('组件展示')
  })

  it('renders router-view content', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('beds-stub')
  })

  it('has a link back to legacy version', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('返回旧版')
  })
})
