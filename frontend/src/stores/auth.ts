import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * useAuthStore — 登录 token 管理
 *
 * Phase 4 起:
 *   - token 存 localStorage (key: auth_token)
 *   - api/index.ts 已经从 localStorage 读 token 放进 X-Auth-Token
 *   - 路由守卫检查 isAuthenticated;未登录跳 /login
 *
 * 不做的事:
 *   - 不做完整注册/改密 UI(通过 /api/auth/users 管理,Phase 5 或后续加)
 *   - 不做 refresh token(后端用静态 token / API key,不过期)
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null,
  )

  const isAuthenticated = computed(() => !!token.value)

  function login(newToken: string) {
    token.value = newToken
    localStorage.setItem('auth_token', newToken)
  }

  function logout() {
    token.value = null
    localStorage.removeItem('auth_token')
  }

  return { token, isAuthenticated, login, logout }
})
