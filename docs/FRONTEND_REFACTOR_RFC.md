# 前端重构 RFC

| | |
|---|---|
| **状态** | Draft — 等待 review |
| **作者** | jiahuaCao + Kiro |
| **创建** | 2026-05-17 |
| **范围** | `static/index.html` / `static/nurse.html` / `static/billing.html` 及其依赖 |
| **不在范围** | 后端 API 契约、`sw.js` 缓存策略、设计系统 token、Python / 部署链路 |

> 本 RFC 是"先讨论再动代码"的前置文档。意图是**让团队在第一行重构代码合入前**,对方向、边界和回滚预案达成共识。
> RFC 合并不代表立刻开始重写——它只代表"当我们决定开始时,会按这个走"。

---

## 1. 背景

### 1.1 项目当前形态

智护银伴是一个面向养老院 / 基层医疗机构的本地化 AI 护理辅助系统。前端目前由三个独立 HTML 入口组成:

| 入口 | 文件 | 角色 | FastAPI 路由 |
|---|---|---|---|
| 管理端 | `static/index.html` | 院方管理员 / 护士长 | `/` |
| 护工端 | `static/nurse.html` | 一线护工(平板巡房) | `/nurse` |
| 缴费端 | `static/billing.html` | 财务 / 家属支付 | `/billing` |

设计系统层 `static/design/` 已经较成熟:

- `tokens.css` — 颜色 / 间距 / 圆角 / 动效曲线 / 阴影变量
- `glass.css` — 液态玻璃质感(orb-float、ambient-drift、rim-rotate 等环境动画)
- `ui.css` — 基础组件类(`.btn` / `.field` / `.toast` / `.dialog` / `.skel`,带 `prefers-reduced-motion` 兜底)
- `mobile.css` — 移动端 / sheet 弹层适配
- `dialog.js` / `evidence.js` / `icons.js` — 三个独立的 vanilla JS 工具
- `vendors.js` — GSAP / Lottie 的 CDN **懒加载器**(带超时和兜底)
- `pet/` — 桌面宠物动画(2.8 MB spritesheet,装饰性)

### 1.2 量化现状

`static/index.html` 单文件指标:

```
2612 行
 91 处函数定义
121 处 window. / document.getElementById 直接访问
 31 处 innerHTML = 字符串拼接
  5 条 CDN 依赖 (FontAwesome / AOS / Typed / QRCode + GSAP/Lottie 懒加载)
```

这些数字本身**不是**问题。问题是它们意味着:

1. 模块边界靠"在文件不同位置写"维持,改一处可能影响远处
2. 状态管理靠 `window.xxx = ...` 全局变量
3. 视图更新靠手写 DOM 字符串,字段重命名要全文搜索
4. 三个入口 HTML 各自重新引一遍 CSS、各自实现一份顶部栏

---

## 2. 我们到底在解决什么问题

> ⚠️ 这一节是 RFC 的核心,review 时**最重要先对齐这一节**。如果对"问题清单"不认同,后面的方案就没必要讨论。

### 2.1 真问题(我认为必须解决)

| # | 问题 | 现状证据 | 影响 |
|---|---|---|---|
| P1 | 单文件超长,无模块边界 | `index.html` 2612 行,`<script>` 内嵌 91 个函数 | 改一处碰一处;两人并行编辑必冲突 |
| P2 | 全局变量驱动状态 | 121 处 `window.*` / `getElementById`;tab 切换、AI 评估、未读告警靠全局变量 | 任何字段变化要手动同步多个 DOM;刷新即丢上下文 |
| P3 | 字符串拼接 DOM | 31 处 `innerHTML =` | 字段重命名靠全文搜索;XSS 隐患(目前数据全是后端可信源,但护工端有手输备注) |
| P4 | 三入口风格漂移 | 三份 HTML 各自引同一套 CSS,但布局结构、顶部栏、Toast 调用各写一份 | 一处改了 button 风格,另两处不知情 |
| P5 | 路由不在 URL | 8 个 tab 切换靠 className,刷新回首屏 | 无法分享链接;无法做"打开就到入院登记"的快捷入口 |
| P6 | CDN 抖动即白屏 | `index.html` 同步引 5 条 CDN | 院内网络偶发抖动会让 AOS / Typed / FA 加载失败,首屏功能受损;装机环境若完全离线,首屏直接坏 |

### 2.2 假问题(看似要做但其实不该现在做)

| # | "看似要做" | 为什么先不做 |
|---|---|---|
| F1 | 加 anime.js / 更多动画 | 当前已有 4 个动画库(AOS / Typed / GSAP / Lottie),问题是过度堆叠不是不够 |
| F2 | 全局换暗色主题 | tokens.css 已经预留 `--ink-*`,加暗色是 1-2 小时活,不必牵进重构 |
| F3 | 立刻做 PWA 离线写入队列 | sw.js 当前对 `/api/*` 是网络优先 + 离线 503,**没有写入队列**;离线写入是独立的功能特性,有自己的 RFC,不应混进重构 |
| F4 | 加 ECharts / 趋势图 | 是真功能需求,但属于"重构完之后增量加",不是重构本身的目标 |

### 2.3 不在范围内的事(明确说"这次不做")

- ❌ 不重写后端 API
- ❌ 不修改 `/api/*` 路由契约或字段
- ❌ 不改 `sw.js` 的缓存策略(只增不改)
- ❌ 不动 `tokens.css` / `glass.css` / `ui.css` / `mobile.css` 任何变量值
- ❌ 不删除 `pet/`(虽然 2.8 MB 装饰资源,但属于品牌 / 情感设计,不是工程债)
- ❌ 不强求换语言(继续 JS,不引 TypeScript 也能做完;TS 是建议项不是强制项)

---

## 3. 候选方案

### 3.1 方案 A:Vite + Vue 3 SFC ✅ 推荐

**栈**:Vite 5 + Vue 3 Composition API + Pinia + Vue Router + VueUse

**核心思路**:

- 新建 `frontend/` 目录,Vite 项目独立维护
- `vite build` 输出到 `static/v2/`,FastAPI 静态托管
- **不需要在生产环境装 Node**,生产仍然只有 Python
- 旧版 `static/index.html` 通过 `/legacy/` 路径保留 1-2 个版本作为回滚

**收益对应 §2.1**:

| 解决 | 怎么解决 |
|---|---|
| P1 单文件超长 | 8 个 tab 各 1 个 `.vue`,每个 < 300 行 |
| P2 全局变量 | Pinia store 替代 `window.*`,reactive 自动同步 |
| P3 字符串拼接 | Vue template 编译,字段重命名 IDE 直接重构 |
| P4 三入口漂移 | 共用 `components/` + `composables/`,管理端 / 护工端 / 缴费端只是 router 入口 |
| P5 URL 路由 | `vue-router` 原生支持,刷新不丢 |
| P6 CDN 白屏 | Vite 把所有依赖打进本地 bundle,装机即用 |

**代价**:

- 开发者机器要装 Node 18+ (生产不需要)
- 学习曲线:团队若没人写过 Vue,需要 2-3 天上手时间
- 构建产物加进 git 还是 CI 产出?选 CI(见 §5)

**为什么选 Vue 不选 React**:

- 中文社区文档密度高(养老院后续要交接给信息科)
- SFC `<template>` 比 JSX 对设计师 / 兼职前端更友好
- Composition API 心智上和 vanilla 接近,迁移成本低

---

### 3.2 方案 B:htmx + Jinja2 + Alpine.js ❌ 否决

**栈**:FastAPI 增加 Jinja2 模板,htmx 做局部刷新,Alpine.js 做局部交互

**听起来很好**:零构建,后端渲染,vanilla 心智延续。

**为什么否决**:

1. **和 PWA 冲突**。护工拿平板巡房,网络抖时 htmx 每次都要回服务器拿片段 = 转圈。`sw.js` 已经存在,这条路是回退。
2. **三入口仍然分裂**。htmx 不解决组件复用,顶部栏还是要在三个模板里各写一遍。
3. **状态在 URL / 服务端**。表单交互复杂的页(如入院登记、AI 评估)反而更难做,htmx 擅长 CRUD 列表场景。
4. **后端要长出渲染层**。FastAPI 现在很干净,加 Jinja2 + 一堆模板部分是后端债换前端债。

---

### 3.3 方案 C:Svelte / SolidJS + Vite

**栈**:Vite + Svelte 5 (或 SolidJS) + 自己挑路由 / store

**优势**:产物最小、性能最好、心智模型最接近 vanilla。

**为什么不选**:

- 中文社区比 Vue 弱一档
- 招聘 / 交接成本:养老院信息科招到的开发更可能熟悉 Vue
- 生态(组件库 / Lint 规则 / 文档)不如 Vue 厚

**保留作为 V2**:如果未来人才储备改变,可以把 Vue 换成 Svelte——重构一次后,框架本身可替换。

---

### 3.4 方案 D:不重构,继续打补丁

**做法**:把 `index.html` 的 `<script>` 抽到独立的 `static/app.js`,继续 vanilla。

**唯一好处**:零学习成本。

**为什么不行**:

- 不能解决 P2(全局状态)、P3(innerHTML)、P5(URL 路由)中的任何一个
- 18 个月后规模再翻倍时,这条路彻底不可走
- "稍微抽一下"是技术债的最常见死法——它给"没在还债"的错觉

---

## 4. 选型决策

**采用方案 A**(Vite + Vue 3 SFC)。

理由排序:

1. 唯一能同时解决 §2.1 全部 6 个真问题的方案
2. 在中国大陆开发者市场上,**人才密度 / 文档质量**胜过 React 之外的所有方案
3. 与现有 `tokens.css` / `glass.css` / `ui.css` 设计系统 100% 兼容(Vue 不限制 CSS 写法,直接 import 即可)
4. 与 PWA / sw.js 兼容,不破坏离线能力
5. 产物是纯静态文件,不影响 FastAPI 部署链路
6. 可逆——任何阶段都可以保留 `/legacy/` 旧入口作为回滚

---

## 5. 目标架构

### 5.1 目录布局

```
项目根/
├── frontend/                          ← 新增:Vite 项目
│   ├── src/
│   │   ├── main.ts                    ← 应用入口
│   │   ├── App.vue                    ← 根组件
│   │   ├── router/
│   │   │   └── index.ts               ← 替代 tab className 切换
│   │   ├── stores/                    ← Pinia
│   │   │   ├── auth.ts                ← Token / 用户 / 权限
│   │   │   ├── patients.ts            ← 住户列表 + 增删改
│   │   │   ├── care.ts                ← 护理记录
│   │   │   ├── billing.ts             ← 账单 / 收款
│   │   │   └── ui.ts                  ← Toast / 全局对话框 / 降级提示
│   │   ├── api/
│   │   │   ├── client.ts              ← fetch 封装,统一加 X-Auth-Token
│   │   │   ├── patients.ts
│   │   │   ├── care.ts
│   │   │   ├── billing.ts
│   │   │   └── nursing.ts             ← AI 评估 / RAG 检索
│   │   ├── composables/               ← 跨视图复用逻辑
│   │   │   ├── useToast.ts
│   │   │   ├── useDialog.ts
│   │   │   ├── useDegradedMode.ts     ← /health 探活 + RAG 状态
│   │   │   └── useTyped.ts            ← 替代 Typed.js,~30 行 vanilla
│   │   ├── components/                ← 通用 UI(< 200 行 / 个)
│   │   │   ├── GlassPanel.vue
│   │   │   ├── PatientCard.vue
│   │   │   ├── RiskBadge.vue
│   │   │   ├── SkeletonList.vue
│   │   │   ├── NumberCounter.vue
│   │   │   └── ...
│   │   ├── views/                     ← 每个 tab 一个文件
│   │   │   ├── DashboardView.vue
│   │   │   ├── PatientsView.vue
│   │   │   ├── AdmissionsView.vue
│   │   │   ├── BillingView.vue
│   │   │   ├── CareRecordsView.vue
│   │   │   ├── HandoversView.vue
│   │   │   ├── IncidentsView.vue
│   │   │   └── EhrView.vue
│   │   ├── nurse/                     ← 护工端独立 entry
│   │   │   ├── NurseApp.vue
│   │   │   └── views/...
│   │   └── styles/
│   │       └── index.ts               ← 直接 import 现有 4 个 CSS,零改动
│   ├── public/
│   │   ├── icons/                     ← 复制自 static/icons
│   │   └── design/ambient.svg         ← 引用现有装饰
│   ├── vite.config.ts
│   ├── tsconfig.json                  ← 可选 TS;允许 .js 共存
│   └── package.json
│
├── static/                            ← 保留旧版,作为 /legacy/ 回滚
│   ├── index.html                     ← 不删,迁完后改名 legacy/index.html
│   ├── nurse.html                     ← 同上
│   ├── billing.html
│   ├── design/                        ← Vite 通过相对路径 import
│   ├── pet/
│   └── v2/                            ← Vite build 产出物
│       ├── index.html
│       └── assets/                    ← 带 hash 的 JS / CSS
│
├── main.py                            ← 仅新增 3 个路由,见 §5.2
└── docs/
    └── FRONTEND_REFACTOR_RFC.md       ← 本文档
```

### 5.2 后端改动(最小化)

`main.py` 仅追加,不修改:

```python
# 旧版保持不变
@app.get("/", include_in_schema=False)            # 现有
@app.get("/nurse", include_in_schema=False)       # 现有
@app.get("/billing", include_in_schema=False)     # 现有

# 新增:v2 入口(灰度阶段)
V2_DIR = STATIC_DIR / "v2"
if V2_DIR.is_dir():
    app.mount("/v2", StaticFiles(directory=str(V2_DIR), html=True), name="v2")

# Phase 6 切换默认时,改成:
# @app.get("/")        return FileResponse(V2_DIR / "index.html")
# @app.get("/legacy")  return FileResponse(STATIC_DIR / "index.html")
```

### 5.3 构建产物管理

**选 CI 产出,不进 git**:

- `frontend/dist/` 加进 `.gitignore`
- GitHub Actions 增加 `npm run build` 步骤
- 构建产物拷贝到 `static/v2/`,后端镜像把 `static/v2/` 一起打包
- Dockerfile 多阶段构建:`node:18-alpine` 阶段跑 build,`python:3.11-slim` 阶段只拷产物

**为什么不进 git**:产物是 hash 命名的,每次 build 变化大;PR diff 会被构建产物淹没;团队成员 npm 版本不一致会导致产物不一致。

---

## 6. 渐进式路线图

> 原则:每个 phase 都可以独立合并、独立回滚。不追求一次合并完成。

| Phase | 内容 | 工时 | 风险 | 可独立合并 |
|---|---|---|---|---|
| **0** | 本 RFC 合并(只改 1 个文档) | 0.5 天 | 无 | ✅ |
| **1** | `frontend/` Vite 骨架 + 空 `/v2/` 占位页 + CI 跑通 | 1 天 | 低 | ✅ |
| **2** | 设计系统迁移:6 个基础组件 + 4 份 CSS import + Storybook(可选) | 2 天 | 低 | ✅ |
| **3** | **试点迁移:住户管理 view**(最复杂,先打通完整链路) | 3 天 | 中 — 暴露选型问题最早 | ✅ |
| **4** | 批量迁移其余 7 个管理端 tab,可两人并行 | 7 天 | 中 | 每 tab 单独合 |
| **5** | 护工端 nurse.html 迁移到 `/v2/nurse` | 3 天 | 中 | ✅ |
| **6** | `/` 默认指向 `/v2/`,旧版降到 `/legacy/`,试运行 3 周后清理 | 0.5 天 | 低 | ✅ |

合计 **约 17 工日**,可拆 6+ 个 PR。

### 6.1 每个 phase 的 Done 定义

- **Phase 1 完成的标志**:`/v2/` 能打开一个写着"Hello v2"的页面;CI 上 `npm run build` 通过;Dockerfile 能正常构建镜像
- **Phase 2 完成的标志**:6 个基础组件可在 Storybook 单独预览;视觉对比与旧版差异 < 5%
- **Phase 3 完成的标志**:`/v2/patients` 功能与 `/#patients` 一致(增删改查、详情、导出),并且代码量 < 旧版 1/3
- **Phase 4 / 5 完成的标志**:每个 tab 通过 §6.2 的 acceptance checklist
- **Phase 6 完成的标志**:`/` 默认走 v2,生产监控 7 天无新增前端报错

### 6.2 每个 view 的 Acceptance Checklist

迁移一个 view 时,该 view 必须满足以下全部条件才能合并:

- [ ] 视觉与旧版差异 < 5%(玻璃质感、间距、字体、色彩 token 完全沿用)
- [ ] 功能与旧版 1:1(列表、详情、表单、上传、导出)
- [ ] 移动端(< 600px 视口)布局正常,无横向滚动
- [ ] `/health` 报告 RAG 不可用时,该 view 进入降级态(灰条 + 文案,不崩)
- [ ] 离线状态下首屏可用(走 sw.js 缓存),`/api/*` 失败有明确提示
- [ ] Lighthouse 得分:Performance ≥ 80, Accessibility ≥ 90
- [ ] 至少 1 个 e2e 测试覆盖该 view 主流程(可选,Phase 4 末期补)

---

## 7. 回滚预案

| Phase | 怎么退 | 后果 |
|---|---|---|
| 0 | 直接 revert RFC PR | 无 |
| 1 | 删 `frontend/`,移除 `/v2` 路由挂载 | 无 |
| 2 | 同上 | 无 |
| 3 | 把 `/v2` 路由摘掉,旧版 `/` 不动 | 无 — 旧版完全独立 |
| 4 | 部分 tab 出问题:把 `/v2/patients` 路由临时 redirect 到 `/#patients` 旧版 | 单 tab 退,其它 tab 正常 |
| 5 | 同上,`/v2/nurse` redirect 回 `/nurse` | 护工端退回旧版 |
| 6 | 改回 `/` 指向 `static/index.html` | 全量退,但旧版仍可工作 |

**关键不变量**:`static/index.html` / `static/nurse.html` / `static/billing.html` 在 Phase 6 之前**任何时刻都不删除**,作为永久 fallback。

---

## 8. 与现有架构的兼容性

| 现有组件 | 兼容性 | 处理方式 |
|---|---|---|
| `tokens.css` / `glass.css` / `ui.css` / `mobile.css` | ✅ 完全兼容 | 在 Vue 入口直接 `import '../../static/design/tokens.css'` |
| `dialog.js` / `evidence.js` / `icons.js` | ⚠️ 部分兼容 | Phase 2 重写为 Vue composable;旧文件保留给 `/legacy/` |
| `vendors.js`(GSAP / Lottie 懒加载) | ✅ 兼容 | Phase 2 改为 Vite 动态 `import()`;懒加载语义不变 |
| `pet/` 桌面宠物 | ✅ 兼容 | 作为 Vue 组件挂载;spritesheet 路径不变 |
| `sw.js` | ✅ 完全兼容 | Phase 1 起把 `/v2/` 加进缓存清单;策略不动 |
| `manifest.json` | ✅ 兼容 | start_url 在 Phase 6 切到 `/v2/` |
| `/api/*` 后端契约 | ✅ 完全不动 | 只在 `frontend/src/api/` 包一层 |
| `X-Auth-Token` 鉴权 | ✅ 完全不动 | `client.ts` 拦截器统一注入 |
| `/health` 健康探活 | ✅ 完全不动 | `useDegradedMode` 直接消费 |

---

## 9. 开放问题(等 review 拍板)

> 这一节是给 reviewer 留下的"我们还没决定的事"。回答这些问题前,Phase 1 不会启动。

### Q1. 是否引入 TypeScript?

- **A. 引入**:类型安全,IDE 重构稳;代价是上手陡 1 度
- **B. 不引入**:`.vue` 写 vanilla JS,纯靠 Vue 的 reactive 自带 DX

**默认建议**:**引入**。养老院领域字段多(15+ 个住户字段、20+ 计费项目),无类型容易出生产事故。

### Q2. UI 组件库?

- **A. 自建**(基于现有 `ui.css`):工作量大,但完全贴合现有设计
- **B. Naive UI / Element Plus 二次开发**:快但视觉一致性差
- **C. shadcn-vue 风格**:复制粘贴源码改,折中

**默认建议**:**A 自建**。`ui.css` 已经把基础组件 token 化了,只是缺 Vue 包装。Phase 2 写 6 个核心组件足够;真正缺组件再增量加。

### Q3. 测试策略?

- 单元测试:Vitest(Vite 内置)
- e2e:Playwright(中文社区文档好)
- 覆盖率目标:**关键 store / composable 80%,view 不强制**(view 频繁改,e2e 比单测有价值)

**默认建议**:Phase 1 起 Vitest,Phase 4 末加 Playwright。

### Q4. 团队 Node 工具链熟悉度?

- 影响 Phase 1 的"开发环境搭建"附录详细程度
- 不熟:RFC Appendix 要写完整 Node 安装、淘宝镜像、pnpm 选型等
- 熟:Phase 1 PR 里只写一行 `nvm use && pnpm i && pnpm dev` 即可

**待 review 时确认**。

### Q5. 护工端离线写入队列(IndexedDB + Background Sync)?

不在重构范围内,但护工端迁移(Phase 5)是加这个特性的最佳时机——成本边际很低。

- **加**:Phase 5 工时从 3 天 → 5 天
- **不加**:Phase 5 维持 3 天,离线写入留给后续独立 RFC

**待 review 时确认**。

---

## 10. 决策记录(等 review 后填)

| 日期 | 决策 | 决策人 | 备注 |
|---|---|---|---|
| 2026-05-17 | RFC Draft 创建 | jiahuaCao + Kiro | 等待 review |
| | 是否引入 TypeScript? | | |
| | UI 组件库选型? | | |
| | 离线写入是否进 Phase 5? | | |
| | RFC 合并 → Phase 1 启动 | | |

---

## 11. 附录

### A. 为什么不是 React

- 同等场景下产出代码量更大
- JSX 对兼职前端 / 设计师不友好
- 中文社区文档密度低于 Vue
- React 生态选择多但选错代价大(状态管理 5 种、CSS 方案 8 种)

### B. 为什么不是 Nuxt(Vue 全栈)

- 我们后端是 FastAPI,不需要 Nuxt 的 SSR / 服务端
- Nuxt 引入新的部署形态(Node 进生产),违反 §2.3 不在范围

### C. 名词速查

- **SFC**:Single-File Component,Vue 的 `.vue` 文件
- **Pinia**:Vue 官方推荐的状态管理库,替代 Vuex
- **Composition API**:Vue 3 的函数式组件写法,替代 Vue 2 的 Options API
- **VueUse**:Vue 生态的 composable 工具集,类似 React 的 react-use
- **FLIP 动画**:First-Last-Invert-Play,列表元素位置变化时的高性能动画策略
- **降级模式**:`/health` 报告 `rag_available=false` 时,前端隐藏 RAG 检索入口,显示提示
