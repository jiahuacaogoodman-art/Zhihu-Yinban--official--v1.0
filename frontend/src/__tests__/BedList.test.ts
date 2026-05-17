import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import BedList from '../views/BedList.vue'

/**
 * BedList 视图冒烟测试
 */

;(globalThis as any).__BUILD_TIME__ = '2026-05-17T00:00:00Z'

const MOCK_BEDS = [
  {
    bed_id: 'b1',
    bed_number: 'A-101',
    floor: '1F',
    building: 'A栋',
    room: '101',
    bed_type: 'standard',
    status: 'available',
    patient_id: null,
    patient_name: null,
    assigned_at: null,
    notes: null,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
  {
    bed_id: 'b2',
    bed_number: 'A-102',
    floor: '1F',
    building: 'A栋',
    room: '102',
    bed_type: 'standard',
    status: 'occupied',
    patient_id: 'p1',
    patient_name: '张奶奶',
    assigned_at: '2026-03-15',
    notes: null,
    created_at: '2026-01-01',
    updated_at: '2026-03-15',
  },
]

function makeRouter() {
  return createRouter({
    history: createWebHashHistory(),
    routes: [{ path: '/', component: BedList }],
  })
}

describe('BedList.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ beds: MOCK_BEDS, total: 2 }),
        }),
      ),
    )
  })

  it('renders bed cards after fetch', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(BedList, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('A-101')
    expect(wrapper.text()).toContain('A-102')
  })

  it('shows patient name for occupied beds', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(BedList, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('张奶奶')
  })

  it('shows status chips with counts', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(BedList, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('空闲 1')
    expect(wrapper.text()).toContain('占用 1')
    expect(wrapper.text()).toContain('总计 2')
  })

  it('renders assign button for available beds', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()
    const wrapper = mount(BedList, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('分配')
    expect(wrapper.text()).toContain('释放')
  })
})
