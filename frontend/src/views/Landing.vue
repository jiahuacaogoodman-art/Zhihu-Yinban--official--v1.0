<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, useTemplateRef } from 'vue'
import { RouterLink } from 'vue-router'
import { animate, createTimeline, stagger, utils, createScope } from 'animejs'
import type { Scope } from 'animejs'
import { Btn, Chip, GlassPanel } from '../components'

/**
 * Landing — 项目主页(华丽版)
 *
 * 设计目标:
 *   - 一打开 /v2/ 就能看到产品定位 + 功能矩阵 + 路线图 + 数据看板
 *   - 用 anime.js v4 让每一屏都有"被设计过"的动效:
 *       1) Hero 标题逐字展开 + 渐变扫光
 *       2) 数字看板 onScroll 触发后从 0 滚到目标
 *       3) 功能卡 stagger 入场
 *       4) 路线图横向 timeline 联动
 *       5) Hero 区飘浮粒子(SVG 圆点 + anime spring + 永动循环)
 *
 *   - 全部用 createScope(),组件卸载时自动 revert,不留下幽灵动画
 *   - prefers-reduced-motion 用户:跳过装饰性动画,只保留入场淡入
 *
 * 参考:https://animejs.com/documentation/ —— v4 ESM API
 */

const root = useTemplateRef<HTMLElement>('root')
const heroTitle = useTemplateRef<HTMLElement>('heroTitle')
const features = ref([
  {
    icon: '🛏',
    title: '床位与档案',
    desc: '从入住、转床到出院,每张床的全生命周期都被记录。',
    accent: 'accent' as const,
    metric: '120+',
    metricLabel: '床位',
  },
  {
    icon: '📋',
    title: 'SBAR 交接',
    desc: '结构化交接班记录,五分钟交完一个班,白班夜班零信息差。',
    accent: 'success' as const,
    metric: '< 5min',
    metricLabel: '一次交接',
  },
  {
    icon: '⚠️',
    title: '异常事件',
    desc: '跌倒/误吸/走失,从上报到根因分析、改进措施全程可追溯。',
    accent: 'warning' as const,
    metric: '4 级',
    metricLabel: '风险分级',
  },
  {
    icon: '💊',
    title: '护理记录',
    desc: '生命体征/用药/饮食/活动,八大类自动归档,质控有迹可循。',
    accent: 'info' as const,
    metric: '8 类',
    metricLabel: '记录维度',
  },
  {
    icon: '🤖',
    title: 'AI 决策辅助',
    desc: '本地 RAG + HuatuoGPT,根据档案、症状给出循证建议(带引用)。',
    accent: 'accent' as const,
    metric: '100%',
    metricLabel: '本地推理',
  },
  {
    icon: '🔐',
    title: 'PII 加密',
    desc: 'Fernet 加密身份证/姓名/床位/病史等高敏字段,审计可追溯。',
    accent: 'danger' as const,
    metric: '10 字段',
    metricLabel: '默认加密',
  },
])

const stats = ref([
  { label: '已重构视图', value: 0, target: 7, suffix: '' },
  { label: '基础组件', value: 0, target: 6, suffix: '' },
  { label: '后端 API', value: 0, target: 60, suffix: '+' },
  { label: '已合并 PR', value: 0, target: 12, suffix: '' },
])

const phases = [
  { id: 1, name: 'Vite 骨架', status: 'done', desc: '工程脚手架 + CI 落地' },
  { id: 2, name: '设计系统', status: 'done', desc: '6 个基础原件零改动包装' },
  { id: 3, name: '试点视图', status: 'done', desc: 'router + pinia + 床位管理' },
  { id: 4, name: '全量迁移', status: 'done', desc: '5 个业务视图 + auth 守卫' },
  { id: 5, name: '护工端', status: 'done', desc: '多入口构建 + 移动端体验' },
  { id: 6, name: '旧版退役', status: 'done', desc: '/ 切到 v2，旧版降到 /legacy/' },
]

let scope: Scope | null = null
const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ============================================================
// Hero 标题逐字裂变
// ============================================================
function splitToChars(el: HTMLElement) {
  if (el.dataset.split === 'done') return
  const text = el.textContent ?? ''
  el.textContent = ''
  for (const ch of text) {
    const span = document.createElement('span')
    span.className = 'hero-char'
    span.textContent = ch === ' ' ? '\u00a0' : ch
    el.appendChild(span)
  }
  el.dataset.split = 'done'
}

// ============================================================
// 数字滚动 — anime.js v4 用 utils.set + targets object
// ============================================================
function animateNumber(targetIndex: number) {
  const obj = { v: 0 }
  animate(obj, {
    v: stats.value[targetIndex].target,
    duration: 1800,
    ease: 'out(3)',
    onUpdate: () => {
      stats.value[targetIndex].value = Math.round(obj.v)
    },
  })
}

// ============================================================
// 飘浮粒子 — Hero 区背景
// ============================================================
function spawnParticles(container: HTMLElement) {
  const N = 18
  for (let i = 0; i < N; i++) {
    const p = document.createElement('div')
    p.className = 'hero-particle'
    const size = utils.random(4, 14)
    p.style.width = `${size}px`
    p.style.height = `${size}px`
    p.style.left = `${utils.random(0, 100)}%`
    p.style.top = `${utils.random(0, 100)}%`
    p.style.opacity = String(utils.random(0.15, 0.45))
    container.appendChild(p)

    animate(p, {
      translateY: [0, utils.random(-40, -120)],
      translateX: [0, utils.random(-30, 30)],
      scale: [1, utils.random(0.6, 1.4)],
      duration: utils.random(4000, 8000),
      ease: 'inOutQuad',
      loop: true,
      alternate: true,
      delay: utils.random(0, 2000),
    })
  }
}

// ============================================================
// IntersectionObserver — 滚动到屏触发数字滚动 + section 进场
// ============================================================
let io: IntersectionObserver | null = null

function observeOnce(el: Element, fn: () => void) {
  if (!io) return
  ;(el as HTMLElement).dataset.observerCb = String(Math.random())
  ;(observers as Map<Element, () => void>).set(el, fn)
  io.observe(el)
}

const observers = new Map<Element, () => void>()

onMounted(() => {
  if (!root.value) return

  scope = createScope({ root: root.value }).add(() => {
    // 1) Hero 标题逐字展开
    if (heroTitle.value) splitToChars(heroTitle.value)
    const chars = root.value!.querySelectorAll('.hero-char')

    if (reducedMotion) {
      animate(chars, { opacity: [0, 1], duration: 200 })
      animate('.landing-section', { opacity: [0, 1], duration: 200 })
      return
    }

    // 用 timeline 让标题、副标题、按钮组按节奏接力出场
    const tl = createTimeline({ defaults: { ease: 'outExpo', duration: 900 } })
      .add(chars, {
        opacity: [0, 1],
        translateY: ['1.2em', 0],
        rotateX: ['-90deg', 0],
        duration: 1100,
        delay: stagger(38),
      })
      .add(
        '.hero-eyebrow, .hero-lede, .hero-cta',
        {
          opacity: [0, 1],
          translateY: [24, 0],
          duration: 700,
          delay: stagger(120),
        },
        '-=600',
      )
      .add(
        '.hero-stat',
        {
          opacity: [0, 1],
          translateY: [16, 0],
          scale: [0.94, 1],
          duration: 700,
          delay: stagger(80),
        },
        '-=400',
      )

    // 2) 数字看板:Hero 区可见时一次性滚动
    setTimeout(() => stats.value.forEach((_, i) => animateNumber(i)), 400)

    // 3) 标题渐变扫光循环
    animate('.hero-shine', {
      backgroundPosition: ['200% 0', '-200% 0'],
      duration: 4000,
      ease: 'linear',
      loop: true,
    })

    // 4) 飘浮粒子层
    const particleLayer = root.value!.querySelector('.hero-particles') as HTMLElement | null
    if (particleLayer) spawnParticles(particleLayer)

    // 5) IntersectionObserver:section 滚到视口时入场
    io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const fn = observers.get(entry.target)
          if (fn) {
            fn()
            io?.unobserve(entry.target)
            observers.delete(entry.target)
          }
        }
      },
      { threshold: 0.15 },
    )

    // 功能卡 stagger 入场
    const featureSection = root.value!.querySelector('.feature-section')
    if (featureSection) {
      observeOnce(featureSection, () => {
        animate('.feature-card', {
          opacity: [0, 1],
          translateY: [40, 0],
          scale: [0.92, 1],
          duration: 800,
          delay: stagger(100, { from: 'first' }),
          ease: 'outBack',
        })
      })
    }

    // 路线图 timeline:节点逐个亮起 + 连线宽度动画
    const phaseSection = root.value!.querySelector('.phase-section')
    if (phaseSection) {
      observeOnce(phaseSection, () => {
        animate('.phase-line-fill', {
          scaleX: [0, 1],
          transformOrigin: '0 50%',
          duration: 1600,
          ease: 'inOutCubic',
        })
        animate('.phase-node', {
          opacity: [0, 1],
          scale: [0, 1],
          duration: 600,
          delay: stagger(180),
          ease: 'outBack',
        })
        animate('.phase-label', {
          opacity: [0, 1],
          translateY: [12, 0],
          duration: 500,
          delay: stagger(180, { start: 200 }),
        })
      })
    }

    // CTA 区下方淡入
    const ctaSection = root.value!.querySelector('.cta-section')
    if (ctaSection) {
      observeOnce(ctaSection, () => {
        animate('.cta-section .cta-card', {
          opacity: [0, 1],
          translateY: [50, 0],
          duration: 900,
          ease: 'outExpo',
        })
      })
    }
  })
})

onBeforeUnmount(() => {
  scope?.revert()
  io?.disconnect()
  observers.clear()
})
</script>

<template>
  <div ref="root" class="landing">
    <!-- ════════════════════════════════════════════ Hero ═══ -->
    <section class="hero">
      <div class="hero-particles" aria-hidden="true"></div>
      <div class="hero-mesh" aria-hidden="true"></div>

      <div class="hero-inner">
        <p class="hero-eyebrow">
          <Chip tone="accent">v2 · 重构进行中</Chip>
          <span class="meta">基于 RFC #8 · Phase 4 / 6</span>
        </p>

        <h1 ref="heroTitle" class="hero-title hero-shine">智护银伴</h1>

        <p class="hero-lede">
          为基层养老院设计的 <strong>100% 本地化</strong> AI 护理辅助系统 ——
          床位、档案、交接班、异常事件、AI 决策一站式可视化。
        </p>

        <div class="hero-cta">
          <RouterLink to="/beds" custom v-slot="{ navigate }">
            <Btn variant="primary" @click="navigate">进入管理端</Btn>
          </RouterLink>
          <RouterLink to="/showcase" custom v-slot="{ navigate }">
            <Btn variant="outline" @click="navigate">查看组件库</Btn>
          </RouterLink>
          <Btn
            tag="a"
            variant="ghost"
            href="https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0"
          >
            GitHub →
          </Btn>
        </div>

        <div class="hero-stats">
          <div v-for="(s, i) in stats" :key="i" class="hero-stat">
            <div class="hero-stat-value">{{ s.value }}{{ s.suffix }}</div>
            <div class="hero-stat-label">{{ s.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════════════════════ Features ═══ -->
    <section class="landing-section feature-section">
      <header class="section-header">
        <Chip tone="accent">FEATURES</Chip>
        <h2 class="display display-2">六个能力,撑起一家养老院的日常</h2>
        <p class="body-l">
          每一项都对应一个真实班次场景。设计语言一致 —— 都来自同一份
          <code>tokens.css</code>,Phase 2 已经把它们封装成 6 个 Vue 组件。
        </p>
      </header>

      <div class="feature-grid">
        <GlassPanel
          v-for="(f, i) in features"
          :key="i"
          variant="card"
          class="feature-card"
        >
          <div class="feature-icon">{{ f.icon }}</div>
          <h3 class="title-m">{{ f.title }}</h3>
          <p class="body-s">{{ f.desc }}</p>
          <div class="feature-metric">
            <span class="feature-metric-value">{{ f.metric }}</span>
            <Chip :tone="f.accent">{{ f.metricLabel }}</Chip>
          </div>
        </GlassPanel>
      </div>
    </section>

    <!-- ═══════════════════════════════════════ Roadmap ═══ -->
    <section class="landing-section phase-section">
      <header class="section-header">
        <Chip tone="info">ROADMAP</Chip>
        <h2 class="display display-2">六个阶段,渐进式重构</h2>
        <p class="body-l">
          每个阶段独立合并 + 独立回滚。RFC §6 路线图原文,详见
          <a href="https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0/blob/main/docs/FRONTEND_REFACTOR_RFC.md">
            FRONTEND_REFACTOR_RFC.md
          </a>
          。
        </p>
      </header>

      <div class="phase-track">
        <div class="phase-line"></div>
        <div class="phase-line-fill"></div>
        <div class="phase-list">
          <div
            v-for="p in phases"
            :key="p.id"
            class="phase-item"
            :class="`phase-${p.status}`"
          >
            <div class="phase-node">{{ p.id }}</div>
            <div class="phase-label">
              <div class="title-s">{{ p.name }}</div>
              <div class="meta">{{ p.desc }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═════════════════════════════════════ CTA Footer ═══ -->
    <section class="landing-section cta-section">
      <GlassPanel variant="card" class="cta-card">
        <div class="cta-inner">
          <h2 class="display display-2">现在就试试</h2>
          <p class="body-l">
            把你的 AUTH_TOKEN 粘进登录页，马上看到床位卡片在屏上展开。
          </p>
          <div class="hero-cta" style="justify-content: center;">
            <RouterLink to="/login" custom v-slot="{ navigate }">
              <Btn variant="primary" @click="navigate">登录管理端</Btn>
            </RouterLink>
            <Btn tag="a" variant="ghost" href="/nurse">前往护工端 →</Btn>
            <Btn tag="a" variant="ghost" href="/legacy">回到旧版 →</Btn>
          </div>
        </div>
      </GlassPanel>
    </section>
  </div>
</template>

<style scoped>
.landing {
  --landing-w: min(1080px, calc(100% - 32px));
  position: relative;
  width: 100%;
  margin: 0 auto;
  padding: 0;
  overflow: hidden;
}

/* ───────── Hero ───────── */
.hero {
  position: relative;
  min-height: 78vh;
  padding: clamp(48px, 9vw, 96px) 0 clamp(40px, 6vw, 72px);
  display: flex;
  align-items: center;
  justify-content: center;
  isolation: isolate;
}
.hero-mesh {
  position: absolute;
  inset: -10%;
  background:
    radial-gradient(50% 50% at 25% 30%, rgba(94, 234, 212, 0.35), transparent 70%),
    radial-gradient(45% 45% at 80% 60%, rgba(129, 140, 248, 0.30), transparent 70%),
    radial-gradient(40% 40% at 50% 90%, rgba(56, 189, 248, 0.22), transparent 70%);
  filter: blur(20px);
  pointer-events: none;
  z-index: -2;
  animation: hero-mesh-drift 20s ease-in-out infinite alternate;
}
@keyframes hero-mesh-drift {
  to { transform: translate(-2%, -1%) scale(1.03); }
}
.hero-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: -1;
}
.hero-particles :deep(.hero-particle),
.hero-particles .hero-particle {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.95), rgba(94, 234, 212, 0.5) 60%, transparent);
  box-shadow: 0 0 16px rgba(94, 234, 212, 0.5);
}

.hero-inner {
  width: var(--landing-w);
  max-width: 1080px;
  text-align: center;
  display: grid;
  gap: var(--sp-4, 16px);
}
.hero-eyebrow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3, 12px);
  flex-wrap: wrap;
  margin-bottom: var(--sp-2);
}
.hero-title {
  margin: 0;
  font-family: var(--font-display, serif);
  font-weight: 700;
  font-size: clamp(56px, 11vw, 132px);
  line-height: 1;
  letter-spacing: -0.04em;
  background-image: linear-gradient(
    100deg,
    #14b8a6 0%,
    #5eead4 25%,
    #818cf8 50%,
    #38bdf8 75%,
    #14b8a6 100%
  );
  background-size: 200% 100%;
  background-position: 0 0;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 12px 40px rgba(20, 184, 166, 0.25));
}
.hero-title :deep(.hero-char),
.hero-title .hero-char {
  display: inline-block;
  transform-origin: 50% 100%;
  will-change: transform, opacity;
}
.hero-lede {
  margin: 0 auto;
  max-width: 640px;
  font-size: clamp(15px, 1.6vw, 19px);
  line-height: 1.7;
  color: var(--ink-2);
}
.hero-lede strong {
  color: var(--accent-ink, #0f766e);
  font-weight: 700;
}
.hero-cta {
  display: flex;
  justify-content: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-top: var(--sp-3);
}
.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--sp-3);
  max-width: 760px;
  margin: var(--sp-5) auto 0;
  padding: var(--sp-4);
  border-radius: var(--r-l, 24px);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: var(--shadow-2, 0 4px 16px rgba(15, 23, 42, 0.06));
}
.hero-stat {
  text-align: center;
}
.hero-stat-value {
  font: 700 clamp(28px, 4vw, 44px) / 1 var(--font-display, serif);
  background: linear-gradient(135deg, #14b8a6, #818cf8);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.02em;
}
.hero-stat-label {
  margin-top: 4px;
  font: 500 12px / 1.4 var(--font-ui, sans-serif);
  color: var(--ink-3);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* ───────── Sections ───────── */
.landing-section {
  width: var(--landing-w);
  margin: 0 auto;
  padding: clamp(60px, 8vw, 110px) 0;
}
.section-header {
  text-align: center;
  display: grid;
  gap: var(--sp-3);
  margin-bottom: var(--sp-6, 32px);
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}
.section-header h2 {
  margin: 0;
  letter-spacing: -0.02em;
}
.section-header .body-l {
  margin: 0;
  color: var(--ink-3);
}

/* ───────── Features ───────── */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-3, 12px);
}
.feature-card {
  opacity: 0;
  display: grid;
  gap: var(--sp-3, 12px);
  transition: transform 240ms var(--ease, ease), box-shadow 240ms var(--ease, ease);
}
.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-3, 0 18px 48px rgba(20, 184, 166, 0.10));
}
.feature-icon {
  font-size: 32px;
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  border-radius: var(--r-m, 16px);
  background: linear-gradient(135deg, rgba(94, 234, 212, 0.4), rgba(129, 140, 248, 0.3));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
.feature-card h3 {
  margin: 0;
}
.feature-card .body-s {
  color: var(--ink-3);
}
.feature-metric {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
}
.feature-metric-value {
  font: 700 22px / 1 var(--font-mono, monospace);
  background: linear-gradient(135deg, #14b8a6, #0f766e);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* ───────── Roadmap ───────── */
.phase-track {
  position: relative;
  padding: var(--sp-5) 0 var(--sp-3);
}
.phase-line {
  position: absolute;
  left: 4%;
  right: 4%;
  top: calc(var(--sp-5) + 22px);
  height: 4px;
  background: rgba(15, 23, 42, 0.08);
  border-radius: 999px;
}
.phase-line-fill {
  position: absolute;
  left: 4%;
  right: 4%;
  top: calc(var(--sp-5) + 22px);
  height: 4px;
  background: linear-gradient(90deg, #14b8a6 0%, #818cf8 70%, rgba(129, 140, 248, 0.3) 100%);
  border-radius: 999px;
  box-shadow: 0 0 18px rgba(94, 234, 212, 0.6);
  transform: scaleX(0);
  transform-origin: 0 50%;
}
.phase-list {
  position: relative;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--sp-2);
}
.phase-item {
  display: grid;
  gap: var(--sp-2);
  text-align: center;
}
.phase-node {
  width: 44px;
  height: 44px;
  margin: 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font: 700 16px / 1 var(--font-mono, monospace);
  border: 2px solid rgba(255, 255, 255, 0.95);
  opacity: 0;
}
.phase-done .phase-node {
  background: linear-gradient(135deg, #2dd4bf, #0f766e);
  color: #fff;
  box-shadow: 0 8px 22px rgba(20, 184, 166, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.5);
}
.phase-todo .phase-node {
  background: rgba(255, 255, 255, 0.85);
  color: var(--ink-4);
  border-color: rgba(15, 23, 42, 0.1);
}
.phase-label {
  opacity: 0;
}
.phase-label .meta {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.4;
  margin-top: 2px;
}

@media (max-width: 720px) {
  .phase-list {
    grid-template-columns: 1fr;
    gap: var(--sp-3);
  }
  .phase-line,
  .phase-line-fill {
    display: none;
  }
}

/* ───────── CTA ───────── */
.cta-section {
  padding-bottom: clamp(80px, 10vw, 140px);
}
.cta-card {
  opacity: 0;
  text-align: center;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(94, 234, 212, 0.18));
  border: 1px solid rgba(94, 234, 212, 0.3);
}
.cta-card .cta-inner {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-5) 0;
}
.cta-card h2 {
  margin: 0;
}

/* ───────── Reduced motion ───────── */
@media (prefers-reduced-motion: reduce) {
  .hero-mesh { animation: none; }
}

/* ───────── 移动端 ───────── */
@media (max-width: 640px) {
  .landing { --landing-w: calc(100% - 24px); }
  .hero {
    min-height: auto;
    padding: clamp(32px, 12vw, 56px) 0 clamp(24px, 8vw, 36px);
  }
  .hero-inner {
    gap: 14px;
    padding: 0 4px;
  }
  .hero-title {
    font-size: clamp(40px, 13vw, 64px) !important;
    letter-spacing: -0.03em;
  }
  .hero-lede {
    font-size: 14px;
    line-height: 1.65;
  }
  .hero-cta {
    flex-direction: column;
    gap: 10px;
    width: 100%;
  }
  .hero-cta > * {
    width: 100%;
  }
  .hero-stats {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    padding: 14px;
    margin-top: 20px;
  }
  .hero-stat-value {
    font-size: 24px;
  }

  .landing-section { padding: 56px 0; }
  .section-header { margin-bottom: 18px; }
  .section-header h2 { font-size: 22px !important; }
  .section-header .body-l { font-size: 14px; }

  .feature-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .feature-card {
    padding: 16px !important;
  }
  .feature-icon {
    width: 44px;
    height: 44px;
    font-size: 24px;
  }

  .cta-card { padding: 22px 14px !important; }
  .cta-card h2 { font-size: 22px !important; }
  .cta-card .body-l { font-size: 14px; }
}

</style>
