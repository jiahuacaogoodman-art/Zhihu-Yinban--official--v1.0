import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import Landing from '../views/Landing.vue'

/**
 * Landing 视图冒烟测试
 *
 * anime.js 在 happy-dom 里能 import 但 IntersectionObserver 默认没实现 ——
 * 所以测试主要验证渲染结构,动画相关副作用通过 stub IO 跳过。
 */

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

// happy-dom 没有 IntersectionObserver,stub 一下
class IOStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: Landing },
      { path: '/beds', component: { template: '<div>beds-stub</div>' } },
      { path: '/showcase', component: { template: '<div>showcase-stub</div>' } },
      { path: '/login', component: { template: '<div>login-stub</div>' } },
    ],
  })
}

describe('Landing.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('IntersectionObserver', IOStub)
    // matchMedia stub(prefers-reduced-motion)
    vi.stubGlobal('matchMedia', () => ({ matches: false, addListener: () => {}, removeListener: () => {} }))
  })

  it('renders the hero title', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(Landing, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('智护银伴')
    expect(wrapper.text()).toContain('100% 本地化')
  })

  it('renders all 6 feature cards', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(Landing, { global: { plugins: [router] } })
    const expectedFeatures = [
      '床位与档案',
      'SBAR 交接',
      '异常事件',
      '护理记录',
      'AI 决策辅助',
      'PII 加密',
    ]
    for (const f of expectedFeatures) {
      expect(wrapper.text()).toContain(f)
    }
  })

  it('renders the 6 phase roadmap', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(Landing, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Vite 骨架')
    expect(wrapper.text()).toContain('设计系统')
    expect(wrapper.text()).toContain('护工端')
    expect(wrapper.text()).toContain('旧版退役')
  })

  it('renders CTA buttons linking to legacy and v2', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(Landing, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('进入管理端')
    expect(wrapper.text()).toContain('查看组件库')
    expect(wrapper.text()).toContain('登录管理端')
  })
})
