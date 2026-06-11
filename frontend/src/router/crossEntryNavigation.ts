import type { Router } from 'vue-router'

type FullPageNavigate = (target: string) => void

export function requiresFullPageNavigation(target: string): boolean {
  return (
    target === '/nurse' ||
    target.startsWith('/nurse/') ||
    target.startsWith('/nurse?') ||
    target.startsWith('/nurse#')
  )
}

function defaultFullPageNavigate(target: string) {
  if (typeof window === 'undefined') return
  window.location.assign(target)
}

export async function navigateAfterAuth(
  router: Pick<Router, 'replace'>,
  target: string,
  fullPageNavigate: FullPageNavigate = defaultFullPageNavigate,
): Promise<void> {
  if (requiresFullPageNavigation(target)) {
    fullPageNavigate(target)
    return
  }
  await router.replace(target)
}