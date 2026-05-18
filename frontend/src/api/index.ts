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
 *
 * Phase 7 增强(401 自动登出):
 *   - 任何 401 → 清 localStorage.auth_token + 通知应用层(setOnUnauthorized)
 *   - 应用层在 main.ts 里挂 router.replace('/login?redirect=...')
 *   - login 页保留 redirect query,登录成功后跳回原页
 *
 *   这里不直接 import router/store —— 避免 api 层环绕依赖 + 让 ssr/单测更轻。
 */

const BASE = '/api'

function getToken(): string | null {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem('auth_token')
}

// ── 401 全局处理钩子 ─────────────────────────────────────
type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null
let unauthorizedNotifying = false // 防止短时间内 N 个并发 401 触发 N 次跳转

export function setOnUnauthorized(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler
}

function notifyUnauthorized() {
  // 立即清掉 token,避免后续请求继续用废 token
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('auth_token')
  }
  if (unauthorizedNotifying) return
  unauthorizedNotifying = true
  try {
    unauthorizedHandler?.()
  } finally {
    // 下一个 tick 解锁,这样如果 handler 没立刻跳路由,后续 401 仍能触发一次
    setTimeout(() => {
      unauthorizedNotifying = false
    }, 800)
  }
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
    if (res.status === 401) {
      notifyUnauthorized()
    }
    throw new ApiError(res.status, detail || `请求失败 (${res.status})`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

/**
 * 解析 Content-Disposition 里的 filename / filename* (RFC 5987)。
 * 后端 export.py 同时给两种字段:
 *   filename="档案卡_xxx_xxx.pdf"; filename*=UTF-8''%E6%A1%A3%E6%A1%88...
 * 现代浏览器走 filename*,这里也优先它,失败再退回 filename。
 */
function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback
  // RFC 5987: filename*=UTF-8''<percent-encoded>
  const star = disposition.match(/filename\*\s*=\s*([^']*)''([^;]+)/i)
  if (star) {
    try {
      return decodeURIComponent(star[2].trim().replace(/^"|"$/g, ''))
    } catch {
      /* fall through */
    }
  }
  const plain = disposition.match(/filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/i)
  if (plain) {
    return (plain[1] ?? plain[2] ?? '').trim() || fallback
  }
  return fallback
}

/**
 * download — 触发浏览器下载二进制响应(主要是 PDF)。
 *
 * 为什么不用 <a download> 直接挂 href:
 *   - 需要带 X-Auth-Token,只能 fetch
 *   - 需要从 Content-Disposition 拿中文文件名(RFC 5987 编码)
 *   - 401/404 时给统一 toast,而不是浏览器空白页
 */
async function download(path: string, fallbackName = 'download.bin'): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['X-Auth-Token'] = token

  const res = await fetch(`${BASE}${path}`, { method: 'GET', headers })
  if (!res.ok) {
    let detail = ''
    try {
      const json = await res.json()
      detail = json.message ?? json.detail ?? ''
    } catch {
      detail = res.statusText
    }
    if (res.status === 401) {
      notifyUnauthorized()
    }
    throw new ApiError(res.status, detail || `下载失败 (${res.status})`)
  }

  const blob = await res.blob()
  const filename = parseFilename(res.headers.get('Content-Disposition'), fallbackName)
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    // 给浏览器一点时间触发下载再回收 ObjectURL
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  download,
}
