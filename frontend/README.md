# 智护银伴 · 前端

Vite + Vue 3 + Pinia + vue-router 多入口 SPA。
管理端入口 `index.html`,护工端入口 `nurse.html`,共享同一份 `src/`。

## 快速开始

```bash
# 需要 Node 18+ (推荐 20)
npm install
npm run dev      # http://localhost:5173,api 自动转发到本地 8000 后端
npm run build    # 产物输出到 ../static/dist/
npm run typecheck
npm run test
```

## 目录约定

```
frontend/
├── src/
│   ├── main.ts                ← 管理端 SPA 入口
│   ├── nurse-main.ts          ← 护工端 SPA 入口
│   ├── App.vue                ← 管理端根布局
│   ├── nurse-views/
│   │   └── NurseApp.vue       ← 护工端根布局
│   ├── router/                ← 管理端路由
│   ├── nurse-router/          ← 护工端路由
│   ├── views/                 ← 管理端业务视图
│   ├── nurse-views/           ← 护工端业务视图
│   ├── components/            ← 共享 UI 原件
│   ├── composables/           ← Vue 组合式 hooks
│   ├── stores/                ← Pinia 状态管理
│   ├── api/                   ← HTTP client + 错误拦截
│   └── styles/
│       ├── app-shell.css      ← 应用壳层移动端样式
│       └── views-mobile.css   ← 子页面移动端样式
├── index.html                 ← 管理端入口 HTML
├── nurse.html                 ← 护工端入口 HTML
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## 与后端的契约

- `vite.config.ts` 把 `@design` 别名指向 `../static/design`,所以可以
  `import '@design/tokens.css'` 直接复用现有设计系统(0 改动)。
- `npm run build` 输出到 `../static/dist/`,被根 `.gitignore` 忽略;
  生产容器在 Docker builder 阶段产出,不进 git。
- 后端 `main.py` 在 `static/dist/` 存在时:
  - `/` → `static/dist/index.html`(管理端)
  - `/nurse` → `static/dist/nurse.html`(护工端)
  - `/dist/*` → 静态资源(JS / CSS / sourcemap)

未构建时这两个入口会返回 404 提示需要先 build。
