import { ApiError } from './types'

/**
 * Typed API client — Phase 3 起
 *
 * 设计取舍:
 *   - 不引 axios;原生 fetch 足够,减少 bundle。Vite proxy 在 dev 时已经
 *     把 /api 转发到 localhost:8000,生产里同源,也不需要配 baseURL。
 *   - X-Auth-Token 从 localStorage 读(Phase 4 的 auth store 负责写入)。
 *   - 全局错误由 interceptor 抛 ApiError;业务侧 try/catch 或让 store 统一处理。
 *   - 不做请求取消(AbortController);Phase 4 对长列表加分页时再加。
 */

const BASE = '/api'

function getToken(): string | null {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem('auth_token')
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = getToken()
  if (token) {
    headers['X-Auth-Token'] = token
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = ''
    try {
      const json = await res.json()
      detail = json.message ?? json.detail ?? ''
    } catch {
      detail = res.statusText
    }
    throw new ApiError(res.status, detail || `请求失败 (${res.status})`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
