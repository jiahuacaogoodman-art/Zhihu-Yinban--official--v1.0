import { describe, expect, it, vi } from 'vitest'
import { navigateAfterAuth, requiresFullPageNavigation } from '../router/crossEntryNavigation'

describe('cross entry navigation', () => {
  it('uses a full page navigation for nurse entry redirects', async () => {
    const router = { replace: vi.fn(() => Promise.resolve()) }
    const fullPageNavigate = vi.fn()

    await navigateAfterAuth(router, '/nurse/patient/001', fullPageNavigate)

    expect(fullPageNavigate).toHaveBeenCalledWith('/nurse/patient/001')
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('keeps manager redirects inside the manager router', async () => {
    const router = { replace: vi.fn(() => Promise.resolve()) }
    const fullPageNavigate = vi.fn()

    await navigateAfterAuth(router, '/beds', fullPageNavigate)

    expect(router.replace).toHaveBeenCalledWith('/beds')
    expect(fullPageNavigate).not.toHaveBeenCalled()
  })

  it('recognizes nurse root URLs with query or hash fragments', () => {
    expect(requiresFullPageNavigation('/nurse')).toBe(true)
    expect(requiresFullPageNavigation('/nurse?tab=today')).toBe(true)
    expect(requiresFullPageNavigation('/nurse#today')).toBe(true)
    expect(requiresFullPageNavigation('/nursing-decision')).toBe(false)
  })
})