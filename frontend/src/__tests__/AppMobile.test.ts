import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'

/**
 * App.vue 移动端冒烟测试 — Phase 7
 *
 * 通过 stub matchMedia 让 useIsTabletOrBelow() 返回 true,验证:
 *   - 渲染顶部 appbar(汉堡 + 标题)
 *   - 渲染底部 tab(床位 / 档案 / 交接 / 异常 / 更多)
 *   - 不再渲染桌面侧栏的 "组件展示" 等次要项
 */

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/beds' },
      { path: '/login', component: { template: '<div>login-stub</div>' } },
      { path: '/beds', component: { template: '<div>beds-stub</div>' } },
      { path: '/ehr', component: { template: '<div>ehr-stub</div>' }, meta: { title: '患者档案' } },
      { path: '/handovers', component: { template: '<div>handovers-stub</div>' } },
      { path: '/incidents', component: { template: '<div>incidents-stub</div>' } },
      { path: '/care-records', component: { template: '<div>care-records-stub</div>' } },
      { path: '/payment-channels', component: { template: '<div>payment-channels-stub</div>' } },
      { path: '/showcase', component: { template: '<div>showcase-stub</div>' } },
    ],
  })
}

describe('App.vue (mobile mode)', () => {
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

    // 让 useIsTabletOrBelow() 命中
    vi.stubGlobal('matchMedia', (q: string) => {
      const matches = q.includes('max-width: 960') || q.includes('max-width: 640')
      return {
        matches,
        media: q,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        onchange: null,
        dispatchEvent: () => true,
      } as unknown as MediaQueryList
    })
  })

  it('renders appbar with hamburger button on mobile', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.find('.v2-appbar').exists()).toBe(true)
    expect(wrapper.find('.v2-appbar-btn').exists()).toBe(true)
  })

  it('renders bottom tab navigation', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.find('.v2-bottom-nav').exists()).toBe(true)
    const text = wrapper.text()
    expect(text).toContain('床位')
    expect(text).toContain('档案')
    expect(text).toContain('交接')
    expect(text).toContain('异常')
    expect(text).toContain('更多')
  })

  it('does not render desktop sidebar on mobile', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.find('.v2-sidebar').exists()).toBe(false)
  })

  it('opens drawer when hamburger clicked', async () => {
    const router = makeRouter()
    router.push('/beds')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
    expect(document.body.querySelector('.v2-drawer--open')).toBeNull()
    await wrapper.find('.v2-appbar-btn').trigger('click')
    expect(document.body.querySelector('.v2-drawer--open')).not.toBeNull()
    wrapper.unmount()
  })
})
