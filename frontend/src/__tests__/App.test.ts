import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/beds' },
      { path: '/login', component: { template: '<div>login-stub</div>' } },
      { path: '/nursing-decision', component: { template: '<div>nd-stub</div>' } },
      { path: '/ehr/add', component: { template: '<div>ehr-add-stub</div>' } },
      { path: '/ehr', component: { template: '<div>ehr-stub</div>' } },
      { path: '/ehr/upload', component: { template: '<div>ehr-upload-stub</div>' } },
      { path: '/beds', component: { template: '<div>beds-stub</div>' } },
      { path: '/handovers', component: { template: '<div>handovers-stub</div>' } },
      { path: '/incidents', component: { template: '<div>incidents-stub</div>' } },
      { path: '/care-records', component: { template: '<div>care-records-stub</div>' } },
      { path: '/billing', component: { template: '<div>billing-stub</div>' } },
      { path: '/payment-channels', component: { template: '<div>payment-channels-stub</div>' } },
      { path: '/users', component: { template: '<div>users-stub</div>' } },
      { path: '/audit', component: { template: '<div>audit-stub</div>' } },
    ],
  })
}

describe('App.vue layout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ status: 'ok' }) })))
  })

  it('renders the sidebar with brand name', async () => {
    const router = makeRouter(); router.push('/beds'); await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('智护银伴')
  })

  it('renders core navigation links', async () => {
    const router = makeRouter(); router.push('/beds'); await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('AI 护理建议')
    expect(wrapper.text()).toContain('床位管理')
    expect(wrapper.text()).toContain('患者档案')
    expect(wrapper.text()).toContain('用户管理')
  })

  it('renders router-view content', async () => {
    const router = makeRouter(); router.push('/beds'); await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('beds-stub')
  })

  it('has nurse link in sidebar footer', async () => {
    const router = makeRouter(); router.push('/beds'); await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('护工端')
  })
})
