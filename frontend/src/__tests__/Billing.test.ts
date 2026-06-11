import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Billing from '../views/Billing.vue'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    download: vi.fn(),
  },
}))

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((b) => b.text() === text)
  if (!button) throw new Error(`button not found: ${text}`)
  return button
}

describe('Billing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === '/billing/overview') {
        return {
          residents: [],
          summary: { normal: 0, expiring_soon: 0, overdue: 0 },
        }
      }
      if (path === '/admissions?limit=500') {
        return { admissions: [] }
      }
      if (path === '/billing/records') {
        return {
          records: [
            {
              record_id: 'bill_1',
              admission_id: 'adm_1',
              patient_name: '张奶奶',
              fee_category: 'care',
              amount: 3800,
              billing_cycle: 'monthly',
              period_start: '2026-06-01',
              period_end: '2026-06-30',
              payment_method: 'cash',
              receipt_number: 'R-001',
              paid_at: '2026-06-01 10:00:00',
              created_at: '2026-06-01 10:00:00',
            },
          ],
        }
      }
      throw new Error(`unhandled GET ${path}`)
    })
    vi.mocked(api.download).mockResolvedValue(undefined)
  })

  it('exports a billing receipt PDF from the records tab', async () => {
    const wrapper = mount(Billing)
    await flushPromises()

    await buttonByText(wrapper, '缴费记录').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('张奶奶')

    await buttonByText(wrapper, '收据').trigger('click')
    await flushPromises()

    expect(api.download).toHaveBeenCalledWith(
      '/export/billing/receipt/bill_1/pdf',
      '收据_R-001.pdf',
    )
  })
})