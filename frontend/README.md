# 智护银伴 · 前端 (v2)

> 这是 RFC `docs/FRONTEND_REFACTOR_RFC.md` (PR #8) 落地的 **Phase 1** 骨架。
> 当前只是占位项目,实际功能视图会在 Phase 3+ 逐步迁移。

## 快速开始

```bash
# 需要 Node 18+ (推荐 20)
npm install
npm run dev      # http://localhost:5173,api 自动转发到本地 8000 后端
npm run build    # 产物输出到 ../static/v2/
npm run typecheck
npm run test
```

## 目录约定

```
frontend/
├── src/
│   ├── main.ts           ← 应用入口
│   ├── App.vue           ← Phase 1 仅放占位页
│   ├── env.d.ts
│   └── styles/
│       └── phase1.css    ← 占位页临时样式;Phase 2 起删除
├── public/               ← 静态资源(目前为空)
├── vite.config.ts
├── tsconfig.json
├── index.html
└── package.json
```

后续阶段会按 RFC §5.1 逐步加 `router/`、`stores/`、`api/`、`composables/`、
`components/`、`views/`、`nurse/`。

## 与后端的契约

- `vite.config.ts` 把 `@design` 别名指向 `../static/design`,所以可以 `import '@design/tokens.css'`
  直接复用现有设计系统(见 RFC §8 兼容性矩阵,**0 改动**)。
- `npm run build` 输出到 `../static/v2/`,被根 `.gitignore` 忽略;
  生产容器在 Docker builder 阶段产出,不进 git。
- 后端 `main.py` 仅在 `static/v2/` 存在时挂载 `/v2/`,缺失则没影响 —— Phase 1 PR
  在仅有后端的环境下(没装 Node)依旧不会让现有 `/`、`/nurse`、`/billing` 出问题。

## 不做的事

- 不引 TypeScript 严格之外的 lint / format(留给 Phase 2 配合 Storybook)
- 不接入 vue-router / Pinia(留给 Phase 3 试点 view 时一起加)
- 不打包 GSAP / Lottie(沿用 `static/design/vendors.js` 的 CDN 懒加载)
