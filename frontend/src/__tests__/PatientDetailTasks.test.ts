import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import PatientDetail from '../nurse-views/PatientDetail.vue'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((b) => b.text() === text)
  if (!button) throw new Error(`button not found: ${text}`)
  return button
}

describe('PatientDetail task execution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockResolvedValue({
      patient_id: 'P001',
      name: '张三',
      age: 82,
      gender: '女',
    })
    vi.mocked(api.post).mockResolvedValue({
      task_card: {
        event_id: 'evt_1',
        decision_id: 'dec_1',
        event_type: '护理观察',
        risk_level: 'yellow',
        immediate_tasks: [{ task_id: 't1', text: '复测血压', status: 'pending' }],
      },
    })
    vi.mocked(api.patch).mockResolvedValue({
      code: 200,
      event: {
        immediate_tasks: [{ task_id: 't1', text: '复测血压', status: 'done' }],
      },
    })
  })

  it('persists task status to the nursing event task endpoint', async () => {
    const router = makeRouter()
    router.push('/')
    await router.isReady()

    const wrapper = mount(PatientDetail, {
      props: { id: 'P001' },
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.find('textarea').setValue('头晕')
    await buttonByText(wrapper, '生成护理任务卡').trigger('click')
    await flushPromises()

    await buttonByText(wrapper, '完成').trigger('click')
    await flushPromises()

    expect(api.patch).toHaveBeenCalledWith(
      '/nursing/events/evt_1/tasks/t1/complete',
      expect.objectContaining({
        status: 'done',
        completed_by: '护工端',
      }),
    )
  })
})