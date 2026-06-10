import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/login', component: Login },
      { path: '/beds', component: { template: '<div>beds-stub</div>' } },
      { path: '/:pathMatch(.*)*', redirect: '/beds' },
    ],
  })
}

describe('Login.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ username: 'admin' }),
        }),
      ),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('uses full-page navigation when redirecting back to the nurse SPA', async () => {
    const router = makeRouter()
    router.push('/login?redirect=/nurse/patient/001')
    await router.isReady()
    const replaceSpy = vi.spyOn(router, 'replace')
    const assignSpy = vi.spyOn(window.location, 'assign').mockImplementation(() => {})

    const wrapper = mount(Login, { global: { plugins: [router] } })
    await wrapper.find('input').setValue('token-1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(assignSpy).toHaveBeenCalledWith('/nurse/patient/001')
    expect(replaceSpy).not.toHaveBeenCalledWith('/nurse/patient/001')
    wrapper.unmount()
  })
})