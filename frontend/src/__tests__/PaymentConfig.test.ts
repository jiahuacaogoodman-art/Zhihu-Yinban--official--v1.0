import { describe, expect, it } from 'vitest'
import { buildPaymentConfigPatch } from '../utils/paymentConfig'

describe('payment config patch builder', () => {
  const fields = [
    { key: 'merchant_id', type: 'text' as const },
    { key: 'api_key', type: 'password' as const },
    { key: 'notify_url', type: 'text' as const },
  ]

  it('skips blank password and text fields so existing config is preserved', () => {
    expect(
      buildPaymentConfigPatch(fields, {
        merchant_id: '',
        api_key: '   ',
        notify_url: '',
      }),
    ).toEqual({})
  })

  it('trims and sends only explicitly provided values', () => {
    expect(
      buildPaymentConfigPatch(fields, {
        merchant_id: '  mch_001  ',
        api_key: '  secret-key  ',
        notify_url: '',
      }),
    ).toEqual({
      merchant_id: 'mch_001',
      api_key: 'secret-key',
    })
  })
})