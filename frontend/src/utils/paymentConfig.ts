export interface PaymentConfigField {
  key: string
  type: 'text' | 'password'
}

export function buildPaymentConfigPatch(
  fields: PaymentConfigField[],
  values: Record<string, string>,
): Record<string, string> {
  const config: Record<string, string> = {}

  for (const field of fields) {
    const value = (values[field.key] || '').trim()
    if (!value) continue
    config[field.key] = value
  }

  return config
}