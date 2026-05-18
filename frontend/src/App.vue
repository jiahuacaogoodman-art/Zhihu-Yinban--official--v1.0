<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { NetworkBanner, Toast } from './components'
import { useAuthStore } from './stores/auth'
import { useToast } from './composables/useToast'
import { useScrollLock } from './composables/useScrollLock'
import { useIsTabletOrBelow } from './composables/useMediaQuery'
import { useViewport } from './composables/useViewport'
import { useNetworkStatus } from './composables/useNetworkStatus'
import { useSwipeBack } from './composables/useSwipeBack'

/**
 * App.vue — 根布局
 *
 * Phase 7 移动端深度适配:
 *   桌面(> 960):  侧栏 220px + 主内容区(原结构,只小改)
 *   移动(≤ 960): 顶部 appbar(汉堡 + 标题 + 退出) + 抽屉 sidebar
 *                 + 底部 tab bar(5 个常用入口) + 安全区填充
 *
 * 行为:
 *   - 路由切换自动关闭抽屉
 *   - 抽屉支持点击 scrim 关闭、ESC 关闭、左滑(touchmove dx < -60)关闭
 *   - 抽屉打开时锁定背景滚动(useScrollLock)
 *   - meta.fullBleed = true(Landing / Login)时桌面端隐侧栏、移动端隐 appbar
 *     和 tab bar(让宣传页/登录页可以铺满)
 */

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { push: toast } = useToast()

const fullBleed = computed(() => route.meta.fullBleed === true)
const isMobile = useIsTabletOrBelow()

// ── 抽屉状态 ──
const drawerOpen = ref(false)
useScrollLock(drawerOpen)

// ── 软键盘 / 视口监听:键盘弹出时给 body 加 .kb-open 让 v2-mobile.css 收底栏 ──
const { keyboardOpen, keyboardHeight } = useViewport()
watch(
  keyboardOpen,
  (v) => {
    if (typeof document === 'undefined') return
    document.body.classList.toggle('kb-open', !!v)
  },
  { immediate: true },
)
watch(
  keyboardHeight,
  (h) => {
    if (typeof document === 'undefined') return
    document.documentElement.style.setProperty('--v2-keyboard-h', `${h}px`)
  },
  { immediate: true },
)

// ── 离线状态:出现网络条幅时给 body 加 .netbanner-on 让 appbar 下移让位 ──
const { offline } = useNetworkStatus()
watch(
  offline,
  (v) => {
    if (typeof document === 'undefined') return
    document.body.classList.toggle('netbanner-on', !!v)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.body.classList.remove('kb-open', 'netbanner-on')
})

// ── 移动端边缘右滑返回:仅在移动端 + 非首页/登录页生效 ──
const swipeBackEnabled = computed(
  () => isMobile.value && !fullBleed.value && route.fullPath !== '/',
)
useSwipeBack(
  () => {
    // 抽屉打开时优先关抽屉
    if (drawerOpen.value) {
      drawerOpen.value = false
      return
    }
    // 浏览器历史栈 > 1 → back;否则回首页
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
    } else {
      router.push('/')
    }
  },
  { enabled: swipeBackEnabled },
)

// ── ESC 关抽屉 ──
function onGlobalKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && drawerOpen.value) {
    drawerOpen.value = false
  }
}
onMounted(() => {
  if (typeof document === 'undefined') return
  document.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('keydown', onGlobalKey)
})

// 路由切换 → 自动收抽屉
watch(
  () => route.fullPath,
  () => {
    drawerOpen.value = false
  },
)

// 移动端切换回桌面尺寸时,如果抽屉还开着,自动关掉(避免遮罩残影)
watch(isMobile, (v) => {
  if (!v) drawerOpen.value = false
})

// ── 当前页标题(供顶栏展示) ──
const currentTitle = computed(() => {
  return (route.meta?.title as string | undefined) ?? '智护银伴'
})

// ── 退出登录 ──
function handleLogout() {
  auth.logout()
  toast({ tone: 'success', text: '已退出登录' })
  router.replace('/login')
}

// ── 抽屉左滑关闭手势 ──
let touchStartX = 0
let touchTracking = false
function onDrawerTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0].clientX
  touchTracking = true
}
function onDrawerTouchMove(e: TouchEvent) {
  if (!touchTracking) return
  const dx = e.touches[0].clientX - touchStartX
  if (dx < -60) {
    drawerOpen.value = false
    touchTracking = false
  }
}
function onDrawerTouchEnd() {
  touchTracking = false
}

// ── 导航条目(桌面侧栏 + 抽屉共用) ──
type NavItem = {
  to: string
  label: string
  icon: string
  short?: string // 底部 tab 的简短标签
  bottomBar?: boolean
}
const navItems: NavItem[] = [
  { to: '/nursing-decision', label: 'AI 护理建议', icon: '✨', short: 'AI', bottomBar: true },
  { to: '/ehr/add', label: '录入档案', icon: '➕', short: '录入', bottomBar: false },
  { to: '/ehr', label: '患者档案', icon: '📋', short: '档案', bottomBar: true },
  { to: '/ehr/upload', label: '病历上传', icon: '📷', short: '病历', bottomBar: false },
  { to: '/beds', label: '床位管理', icon: '🛏', short: '床位', bottomBar: true },
  { to: '/handovers', label: '交接班', icon: '🔁', short: '交接', bottomBar: true },
  { to: '/incidents', label: '异常事件', icon: '⚠️', short: '异常', bottomBar: false },
  { to: '/care-records', label: '护理记录', icon: '💊', short: '护理', bottomBar: false },
  { to: '/billing', label: '缴费管理', icon: '💰', short: '缴费', bottomBar: false },
  { to: '/payment-channels', label: '支付渠道', icon: '💳', short: '支付', bottomBar: false },
  { to: '/users', label: '用户管理', icon: '👥', short: '用户', bottomBar: false },
  { to: '/audit', label: '审计日志', icon: '🛡', short: '审计', bottomBar: false },
]

// 底部 tab 优先取 bottomBar:true,最多 4 个 + 1 个"更多"
const bottomTabs = computed(() => navItems.filter((n) => n.bottomBar))
</script>

<template>
  <div class="v2-layout" :class="{ 'v2-layout--full': fullBleed }">
    <!-- ───── 移动端顶部 appbar(fullBleed 页面隐藏) ───── -->
    <header
      v-if="!fullBleed && isMobile"
      class="v2-appbar"
      role="banner"
    >
      <button
        type="button"
        class="v2-appbar-btn"
        aria-label="打开导航菜单"
        @click="drawerOpen = true"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <line x1="4" y1="7" x2="20" y2="7" />
          <line x1="4" y1="12" x2="20" y2="12" />
          <line x1="4" y1="17" x2="20" y2="17" />
        </svg>
      </button>
      <div class="v2-appbar-title">
        <span class="mark">♥</span>
        <span class="ttl">{{ currentTitle }}</span>
      </div>
      <a href="/nurse" class="v2-appbar-link" aria-label="切换到护工端">护工</a>
    </header>

    <!-- ───── 桌面侧栏(fullBleed 隐藏) ───── -->
    <aside v-if="!fullBleed && !isMobile" class="v2-sidebar">
      <div class="v2-sidebar-brand">
        <span class="mark">♥</span>
        <span class="title-s">智护银伴</span>
        <span class="meta">v2</span>
      </div>
      <nav class="v2-nav" aria-label="主导航">
        <RouterLink
          v-for="n in navItems"
          :key="n.to"
          :to="n.to"
          class="v2-nav-item"
          active-class="v2-nav-active"
        >
          <span class="v2-nav-icon">{{ n.icon }}</span>
          <span>{{ n.label }}</span>
        </RouterLink>
      </nav>
      <div class="v2-sidebar-footer">
        <a href="/nurse" class="v2-nav-item">
          <span class="v2-nav-icon">👩‍⚕️</span>
          <span>护工端 →</span>
        </a>
        <a href="/legacy" class="v2-nav-item v2-nav-item--muted">
          <span class="v2-nav-icon">🗂</span>
          <span>旧版入口 →</span>
        </a>
        <button
          v-if="auth.isAuthenticated"
          type="button"
          class="v2-nav-item v2-nav-item--logout"
          @click="handleLogout"
        >
          <span class="v2-nav-icon">⏻</span>
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <!-- ───── 移动端抽屉 + 遮罩 ───── -->
    <Teleport to="body">
      <div
        v-if="!fullBleed && isMobile"
        class="v2-scrim"
        :class="{ 'v2-scrim--show': drawerOpen }"
        @click="drawerOpen = false"
      />
      <aside
        v-if="!fullBleed && isMobile"
        class="v2-drawer"
        :class="{ 'v2-drawer--open': drawerOpen }"
        :aria-hidden="!drawerOpen"
        @touchstart.passive="onDrawerTouchStart"
        @touchmove.passive="onDrawerTouchMove"
        @touchend.passive="onDrawerTouchEnd"
      >
        <div class="v2-drawer-brand">
          <span class="mark">♥</span>
          <div>
            <div class="title-s" style="color: #fff;">智护银伴</div>
            <div class="meta" style="color: rgba(226,232,240,0.6);">v2 · 管理端</div>
          </div>
          <button
            type="button"
            class="v2-drawer-close"
            aria-label="关闭菜单"
            @click="drawerOpen = false"
          >
            ✕
          </button>
        </div>
        <nav class="v2-drawer-nav" aria-label="主导航">
          <RouterLink
            v-for="n in navItems"
            :key="n.to"
            :to="n.to"
            class="v2-drawer-item"
            active-class="v2-drawer-item--active"
          >
            <span class="ic">{{ n.icon }}</span>
            <span>{{ n.label }}</span>
          </RouterLink>
        </nav>
        <div class="v2-drawer-footer">
          <a href="/nurse" class="v2-drawer-item">
            <span class="ic">👩‍⚕️</span>
            <span>切换到护工端 →</span>
          </a>
          <a href="/legacy" class="v2-drawer-item v2-drawer-item--muted">
            <span class="ic">🗂</span>
            <span>旧版入口 →</span>
          </a>
          <button
            v-if="auth.isAuthenticated"
            type="button"
            class="v2-drawer-item v2-drawer-item--logout"
            @click="handleLogout"
          >
            <span class="ic">⏻</span>
            <span>退出登录</span>
          </button>
        </div>
      </aside>
    </Teleport>

    <!-- ───── 主内容 ───── -->
    <main class="v2-main" :class="{ 'v2-main--full': fullBleed }">
      <router-view />
    </main>

    <!-- ───── 移动端底部 tab(fullBleed 隐藏) ───── -->
    <nav
      v-if="!fullBleed && isMobile"
      class="v2-bottom-nav"
      aria-label="主要功能"
    >
      <RouterLink
        v-for="n in bottomTabs"
        :key="n.to"
        :to="n.to"
        class="v2-bottom-item"
        active-class="v2-bottom-item--active"
      >
        <span class="ic">{{ n.icon }}</span>
        <span class="lb">{{ n.short ?? n.label }}</span>
      </RouterLink>
      <button
        type="button"
        class="v2-bottom-item"
        :class="{ 'v2-bottom-item--active': drawerOpen }"
        aria-label="更多"
        @click="drawerOpen = true"
      >
        <span class="ic">≡</span>
        <span class="lb">更多</span>
      </button>
    </nav>

    <NetworkBanner />
    <Toast />
  </div>
</template>

<style scoped>
.v2-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
  min-height: 100dvh;
}
.v2-layout--full {
  grid-template-columns: 1fr;
}

/* ─── 桌面侧栏 ─── */
.v2-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: var(--sp-4, 16px);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
  border-right: 1px solid rgba(15, 23, 42, 0.06);
  z-index: 5;
}
.v2-sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
  margin-bottom: var(--sp-4, 16px);
  padding-bottom: var(--sp-3, 12px);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.v2-sidebar-brand .mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent, #14b8a6), var(--accent-ink, #0f766e));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
}

.v2-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.v2-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--r-s, 10px);
  font: 500 var(--fz-sm, 13px) / 1.4 var(--font-ui, sans-serif);
  color: var(--ink-2, rgba(15, 23, 42, 0.75));
  text-decoration: none;
  background: transparent;
  border: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background var(--dur-fast, 120ms) var(--ease, ease);
}
.v2-nav-item:hover {
  background: rgba(15, 23, 42, 0.04);
}
.v2-nav-active {
  background: rgba(20, 184, 166, 0.1);
  color: var(--accent-ink, #0f766e);
  font-weight: 600;
}
.v2-nav-icon {
  font-size: 16px;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}
.v2-nav-item--muted { color: var(--ink-4, #94a3b8); }
.v2-nav-item--logout { color: var(--red, #dc2626); }
.v2-nav-item--logout:hover { background: rgba(239, 68, 68, 0.08); }

.v2-sidebar-footer {
  margin-top: auto;
  padding-top: var(--sp-3, 12px);
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  display: grid;
  gap: 2px;
}

/* ─── 主内容 ─── */
.v2-main {
  padding: var(--sp-5, 20px);
  max-width: 1200px;
  width: 100%;
}
.v2-main--full {
  padding: 0;
  max-width: none;
}

/* ============ 移动端 (≤ 960) ============ */
@media (max-width: 960px) {
  .v2-layout {
    grid-template-columns: 1fr;
  }

  /* 顶部 appbar */
  .v2-appbar {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: calc(var(--v2-sat) + 8px) 12px 8px;
    background: rgba(11, 18, 32, 0.86);
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    color: #fff;
  }
  .v2-appbar-btn {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
  }
  .v2-appbar-btn:active {
    background: rgba(255, 255, 255, 0.14);
  }
  .v2-appbar-title {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    font: 600 15px/1.2 var(--font-ui);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .v2-appbar-title .mark {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    background: linear-gradient(135deg, var(--accent), var(--accent-ink));
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 13px;
    flex-shrink: 0;
  }
  .v2-appbar-link {
    color: rgba(226, 232, 240, 0.85);
    text-decoration: none;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(255, 255, 255, 0.06);
    font: 500 13px/1 var(--font-ui);
    flex-shrink: 0;
  }
  .v2-appbar-link:active {
    background: rgba(255, 255, 255, 0.16);
  }

  .v2-main {
    padding: 12px 14px var(--v2-bottom-pad);
    max-width: 100%;
  }
  .v2-main--full {
    padding: 0;
  }
}

/* ─── 抽屉(在 Teleport 到 body 之后,样式不能被 scoped 切到子树。
       这部分用 :global() 写) ─── */
</style>

<style>
/* ─── 全局样式：抽屉 / scrim / 底部 tab(都 Teleport 到 body) ─── */

.v2-scrim {
  position: fixed;
  inset: 0;
  z-index: 55;
  background: rgba(11, 18, 32, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 280ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.v2-scrim--show {
  opacity: 1;
  pointer-events: auto;
}

.v2-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 280px;
  max-width: 82vw;
  height: 100dvh;
  z-index: 60;
  background: rgba(11, 18, 32, 0.92);
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border-right: 1px solid rgba(255, 255, 255, 0.10);
  box-shadow: 12px 0 40px rgba(15, 23, 42, 0.35);
  padding: calc(env(safe-area-inset-top, 0px) + 16px) 16px
    calc(env(safe-area-inset-bottom, 0px) + 16px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transform: translateX(-102%);
  transition: transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}
.v2-drawer--open {
  transform: translateX(0);
}

.v2-drawer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}
.v2-drawer-brand .mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), var(--accent-ink));
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.v2-drawer-close {
  margin-left: auto;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.14);
  font-size: 16px;
  cursor: pointer;
}

.v2-drawer-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow-y: auto;
}
.v2-drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  font: 500 15px/1.3 var(--font-ui);
  color: rgba(226, 232, 240, 0.85);
  background: transparent;
  border: none;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
  width: 100%;
  min-height: 46px;
}
.v2-drawer-item .ic {
  font-size: 18px;
  width: 22px;
  text-align: center;
  flex-shrink: 0;
}
.v2-drawer-item:active {
  background: rgba(255, 255, 255, 0.10);
}
.v2-drawer-item--active {
  background: rgba(20, 184, 166, 0.18);
  color: #5eead4;
  font-weight: 600;
}
.v2-drawer-item--muted {
  color: rgba(226, 232, 240, 0.55);
}
.v2-drawer-item--logout {
  color: #fca5a5;
}
.v2-drawer-item--logout:active {
  background: rgba(239, 68, 68, 0.18);
}

.v2-drawer-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.10);
  padding-top: 8px;
  display: grid;
  gap: 2px;
}

/* ─── 底部 tab ─── */
.v2-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 25;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-top: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 -4px 18px rgba(15, 23, 42, 0.06);
  padding: 6px 4px calc(env(safe-area-inset-bottom, 0px) + 4px);
}
.v2-bottom-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 6px 4px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: var(--ink-3, #475569);
  text-decoration: none;
  font: 500 11px/1.2 var(--font-ui);
  cursor: pointer;
  min-height: 50px;
}
.v2-bottom-item .ic {
  font-size: 20px;
  line-height: 1;
}
.v2-bottom-item:active {
  background: rgba(20, 184, 166, 0.08);
}
.v2-bottom-item--active {
  color: var(--accent-ink, #0f766e);
}
.v2-bottom-item--active .ic {
  filter: drop-shadow(0 2px 4px rgba(20, 184, 166, 0.35));
}
</style>
