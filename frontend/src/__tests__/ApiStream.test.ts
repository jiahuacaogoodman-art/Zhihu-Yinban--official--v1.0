import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, setOnUnauthorized } from '../api'

function mockStreamResponse(text: string) {
  const encoder = new TextEncoder()
  return {
    ok: true,
    status: 200,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(text))
        controller.close()
      },
    }),
  }
}

describe('api.streamJsonEvents', () => {
  beforeEach(() => {
    localStorage.clear()
    setOnUnauthorized(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setOnUnauthorized(null)
    localStorage.clear()
  })

  it('parses SSE JSON events and ignores bare DONE markers', async () => {
    localStorage.setItem('auth_token', 'token-1')
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          mockStreamResponse(
            [
              'event: evidence',
              'data: {"evidence":[{"source_type":"ehr"}]}',
              '',
              'event: token',
              'data: "请观察体温"',
              '',
              'event: done',
              'data: {"decision_id":"d1"}',
              '',
              'event: done',
              'data: [DONE]',
              '',
            ].join('\n'),
          ),
        ),
      ),
    )

    const events: string[] = []
    const payloads: unknown[] = []
    await api.streamJsonEvents('/nursing/decision/stream', { patient_id: 'P001' }, ({ event, data }) => {
      events.push(event)
      payloads.push(data)
    })

    expect(events).toEqual(['evidence', 'token', 'done'])
    expect(payloads[0]).toEqual({ evidence: [{ source_type: 'ehr' }] })
    expect(payloads[1]).toBe('请观察体温')
    expect(payloads[2]).toEqual({ decision_id: 'd1' })
    expect(fetch).toHaveBeenCalledWith(
      '/api/nursing/decision/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'X-Auth-Token': 'token-1' }),
      }),
    )
  })

  it('uses the global unauthorized handler for stream 401 responses', async () => {
    localStorage.setItem('auth_token', 'expired-token')
    const onUnauthorized = vi.fn()
    setOnUnauthorized(onUnauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: () => Promise.resolve({ detail: 'token expired' }),
        }),
      ),
    )

    await expect(
      api.streamJsonEvents('/nursing/decision/stream', { patient_id: 'P001' }, () => {}),
    ).rejects.toThrow('token expired')

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })
})
