import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import UserManagement from '../views/UserManagement.vue'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((b) => b.text() === text)
  if (button) return button
  const teleported = Array.from(document.body.querySelectorAll('button')).find(
    (b) => b.textContent?.trim() === text,
  )
  if (teleported) {
    return {
      trigger: async (event: string) => {
        if (event === 'click') teleported.click()
      },
    }
  }
  throw new Error(`button not found: ${text}`)
}

describe('UserManagement', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    vi.stubGlobal('confirm', vi.fn(() => true))
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn(() => Promise.resolve()) },
    })
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.startsWith('/auth/users')) {
        return {
          users: [
            {
              user_id: 'usr_1',
              username: 'admin',
              display_name: '管理员',
              role: 'admin',
              active: true,
            },
            {
              user_id: 'usr_2',
              username: 'old_nurse',
              display_name: '离职护工',
              role: 'nurse',
              active: false,
            },
          ],
        }
      }
      if (path.startsWith('/auth/roles')) {
        return {
          roles: [
            {
              role_key: 'admin',
              display_name: '管理员',
              system: true,
              permissions: ['users.manage', 'tokens.manage'],
            },
            {
              role_key: 'nurse',
              display_name: '护工',
              system: true,
              permissions: ['ehr.read'],
            },
          ],
        }
      }
      if (path.startsWith('/auth/tokens')) {
        return {
          keys: [
            {
              key_id: 'key_1',
              user_id: 'usr_1',
              username: 'admin',
              label: '管理后台',
              token_prefix: 'abcd1234',
              created_at: '2026-06-01 10:00:00',
              last_used_at: '',
              revoked_at: '',
            },
            {
              key_id: 'key_2',
              user_id: 'usr_2',
              username: 'old_nurse',
              label: '旧护工端',
              token_prefix: 'zzzz9999',
              created_at: '2026-05-01 10:00:00',
              last_used_at: '2026-05-02 10:00:00',
              revoked_at: '2026-06-01 11:00:00',
            },
          ],
        }
      }
      throw new Error(`unhandled GET ${path}`)
    })
    vi.mocked(api.post).mockResolvedValue({ token: 'plain-token-once' })
    vi.mocked(api.delete).mockResolvedValue({ code: 200 })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('loads inactive users and revoked tokens for admin audit', async () => {
    const wrapper = mount(UserManagement)
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/auth/users?include_inactive=true')
    expect(api.get).toHaveBeenCalledWith('/auth/tokens?include_revoked=true')
    expect(wrapper.text()).toContain('old_nurse')
    expect(wrapper.text()).toContain('已停用')
    expect(wrapper.text()).toContain('旧护工端')
    expect(wrapper.text()).toContain('已吊销')
  })

  it('revokes tokens and deactivates users from the management page', async () => {
    const wrapper = mount(UserManagement)
    await flushPromises()

    await buttonByText(wrapper, '吊销').trigger('click')
    await flushPromises()
    expect(api.delete).toHaveBeenCalledWith('/auth/tokens/key_1')

    await buttonByText(wrapper, '停用').trigger('click')
    await flushPromises()
    expect(api.delete).toHaveBeenCalledWith('/auth/users/usr_1')
  })

  it('shows the newly issued token once and offers copy', async () => {
    const wrapper = mount(UserManagement, {
      attachTo: document.body,
    })
    await flushPromises()

    await buttonByText(wrapper, '签发 Token').trigger('click')
    await flushPromises()
    await buttonByText(wrapper, '签发').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/auth/tokens', {
      user_id: 'usr_1',
      label: '默认',
    })
    expect(document.body.textContent).toContain('plain-token-once')

    await buttonByText(wrapper, '复制').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('plain-token-once')

    wrapper.unmount()
  })
})