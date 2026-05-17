<h1 align="center">智护银伴 · ZhiHu YinBan</h1>

<p align="center">
  <b>100% 本地运行的养老院 AI 护理辅助系统</b><br>
  档案不出院、照片不上云、断网也能给出可打卡的护理任务卡。
</p>

<p align="center">
  <b>简体中文</b> | <a href="./README.en.md">English</a>
</p>

<p align="center">
  <img alt="python"  src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="fastapi" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="vue"     src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="vite"    src="https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white">
  <img alt="ts"      src="https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white">
  <img alt="animejs" src="https://img.shields.io/badge/anime.js-4.4-F74F9E">
  <img alt="chroma"  src="https://img.shields.io/badge/ChromaDB-0.5-3C1F85">
  <img alt="ollama"  src="https://img.shields.io/badge/Ollama-HuatuoGPT__o1__7B-000000?logo=ollama&logoColor=white">
  <img alt="offline" src="https://img.shields.io/badge/Runtime-100%25%20Offline-10B981">
  <img alt="license" src="https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue">
</p>

<p align="center">
  <a href="#-功能总览">功能总览</a> ·
  <a href="#-前端架构-v2">前端架构</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-配置说明">配置说明</a> ·
  <a href="#-api-参考">API 参考</a> ·
  <a href="#-系统架构">架构</a> ·
  <a href="#-重构路线图">路线图</a>
</p>

---

## 🌱 为什么做这个

基层养老院面对的真实矛盾是：

- 老人多、护工人均看护数高，**专业经验很难均质化**；
- 病历碎在纸上、U 盘里、微信群里，**AI 想用却无从入手**；
- 院方最担心"**数据上云 = 合规和责任**"，所以很多云端 AI 方案直接被一票否决。

**智护银伴**的目标：让养老院把"大模型 + RAG"真正用起来，所有档案、照片、AI 决策全部保存在本机磁盘，一台普通服务器 + 局域网即可运行。

---

## ✨ 功能总览

### 核心业务

| 模块 | 功能 | 说明 |
|---|---|---|
| **老人档案管理** | 增删改查 | 21 个字段（姓名、年龄、病史、过敏、床位、护理等级等） |
| **床位管理** | 分配/释放/状态筛选 | 按楼栋/状态查看，实时统计空闲/占用 |
| **病历照片 OCR** | 上传 → 本地识别 → 向量化 | RapidOCR (ONNX) + Tesseract 双引擎，纯本地运行 |
| **AI 护理决策** | 混合检索 + LLM 推理 | Dense + BM25 + RRF 融合，带源类型加权和引用标注 |
| **护理任务卡** | 结构化 JSON 输出 | 可打卡清单 + 复测计划 + 禁止事项 + SBAR 交接单 |
| **SBAR 交接班** | 结构化记录 + 确认流程 | Situation / Background / Assessment / Recommendation |
| **异常事件上报** | 4 级严重度 + 全流程跟踪 | 跌倒/误吸/走失，从上报到根因分析全程可追溯 |
| **护理记录** | 8 大类留痕 | 生命体征/用药/饮食/活动/观察/特护 |
| **决策记忆 (L4)** | 自动写回 + 结果回填 | AI 看得到"上次对同一个老人怎么处理、效果如何" |
| **SSE 流式输出** | 逐 token 推送 | 护工端实时看到生成过程 |

### 安全与合规

| 模块 | 说明 |
|---|---|
| **多用户认证** | admin / nurse / caregiver 三种角色 + 多 API Key |
| **PII 字段加密** | Fernet 对称加密 10 个高敏字段（写入前自动加密） |
| **操作审计日志** | 全部写操作留痕，带 diff 且 PII 自动脱敏 |
| **占位符写回防御** | 密钥缺失时拒绝写入，防止解密失败污染数据库 |

---

## 🖥️ 前端架构 (v2)

> 基于 [docs/FRONTEND_REFACTOR_RFC.md](./docs/FRONTEND_REFACTOR_RFC.md) (PR #8) 完成的 **6 阶段渐进式重构**。

### 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 构建 | **Vite 6** | 多入口 (管理端 + 护工端)，code-split，< 2s 冷启动 |
| 框架 | **Vue 3.5** + Composition API | `<script setup>` + TypeScript |
| 路由 | **vue-router 4** | history 模式，懒加载 |
| 状态 | **Pinia** | setup store 语法 |
| 类型 | **TypeScript 5.7** | vue-tsc strict typecheck |
| 动效 | **anime.js 4.4** | 逐字入场 / 数字滚动 / stagger / timeline / 粒子系统 |
| 设计系统 | `tokens.css` + `glass.css` + `ui.css` + `mobile.css` | 0 改动复用旧版 |
| 测试 | **Vitest** + @vue/test-utils | 15 个冒烟测试 |

### 目录结构

```
frontend/
├── index.html              ← 管理端入口
├── nurse.html              ← 护工端入口
├── vite.config.ts          ← 多入口 rollup 配置
├── vitest.config.ts
├── tsconfig.json
├── package.json            ← vue 3 + vue-router + pinia + animejs
└── src/
    ├── main.ts             ← 管理端 bootstrap
    ├── nurse-main.ts       ← 护工端 bootstrap
    ├── App.vue             ← 管理端 layout (sidebar + router-view)
    ├── router/index.ts     ← 管理端路由 (history mode)
    ├── nurse-router/       ← 护工端路由 (history mode, base=/nurse)
    ├── stores/             ← Pinia stores (beds, auth)
    ├── api/                ← typed fetch client + types
    ├── components/         ← 6 个基础组件 (GlassPanel/Btn/Field/Chip/Dialog/Toast)
    ├── composables/        ← useToast 等
    ├── views/              ← 管理端视图 (Landing/BedList/EhrList/Handovers/...)
    ├── nurse-views/        ← 护工端视图 (NurseApp/PatientList/PatientDetail)
    └── __tests__/          ← Vitest 冒烟测试
```

### 6 个基础组件

| 组件 | 对应 ui.css | Props |
|---|---|---|
| `GlassPanel` | 通用玻璃容器 | variant: panel / card |
| `Btn` | `.btn-*` | variant, size, loading, disabled |
| `Field` | `.field` + `.field-group` | v-model, label, type, hint, error |
| `Chip` | `.chip-*` | tone: neutral / accent / danger / warning / success / info |
| `Dialog` | `.dialog-ov` + `.dialog` | v-model, title, ESC/overlay close |
| `Toast` | `.toast-wrap` | `useToast().push({ tone, text })` |

### Landing 页动效 (anime.js v4)

打开 `/` 即可看到：

1. **Hero 标题**逐字 `rotateX(-90° → 0)` + 渐变扫光循环
2. **18 个飘浮粒子**随机路径 + spring 永动
3. **数字看板**从 0 滚动到目标值 (anime `onUpdate`)
4. **6 张功能卡** `outBack` stagger 入场 (IntersectionObserver)
5. **路线图** `scaleX` 连线 + 节点 pop-in
6. **CTA 卡片** `outExpo` 上浮

所有动画用 `createScope()` 管理，组件卸载时 `revert()` 清理；`prefers-reduced-motion` 用户仅淡入。

---

## 🚀 快速开始

### 一键部署（3 行搞定）

#### 🐧 Linux / 🍎 macOS

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

#### 🪟 Windows (PowerShell)

```powershell
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

约 10 分钟后看到 `部署成功！` + 管理员 Token。

| 页面 | 地址 | 说明 |
|---|---|---|
| 首页 (Landing) | http://localhost:8000/ | anime.js 动效展示页 |
| 管理端 | http://localhost:8000/#/beds | 登录后进入 |
| 护工端 | http://localhost:8000/nurse | 移动端优先 |
| 旧版 (fallback) | http://localhost:8000/legacy | 保留入口 |
| 健康检查 | http://localhost:8000/health | k8s/systemd 探针 |

### 前端开发

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173，api 自动 proxy 到 8000
npm run typecheck    # vue-tsc strict
npm run test         # vitest (15 cases)
npm run build        # 产物 → ../static/v2/ (index.html + nurse.html)
```

---

## ⚙️ 配置说明

所有配置通过 `.env` 或环境变量设置：

### 必须配置

| 变量 | 用途 | 生成方式 |
|---|---|---|
| `AUTH_TOKEN` | 管理员 bootstrap token | `openssl rand -hex 32` |
| `PII_ENCRYPTION_KEY` | PII 字段加密密钥 | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### 可选配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OLLAMA_MODEL_NAME` | `hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M` | 本地大模型 |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-zh-v1.5` | Embedding 模型 |
| `EMBEDDING_ALLOW_DEGRADED` | `true` | 模型加载失败时是否降级启动 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `MAX_UPLOAD_SIZE_MB` | `15` | 单张照片上限 |

---

## 🔌 API 参考

所有接口在 `/api/*` 下，请求头需带 `X-Auth-Token`。

### 认证 `/api/auth/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/auth/me` | 当前身份 |
| `POST` | `/api/auth/users` | 创建用户 (admin) |
| `POST` | `/api/auth/tokens` | 签发 API Key (admin) |

### 档案 `/api/ehr/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/ehr/patients` | 新增老人 |
| `GET` | `/api/ehr/patients` | 列出所有老人 |
| `POST` | `/api/ehr/records/upload` | 上传病历照片 (OCR) |
| `GET` | `/api/ehr/audit` | 审计日志 (admin) |

### 床位 `/api/beds`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/beds` | 列表 + 筛选 |
| `POST` | `/api/beds/{id}/assign` | 分配 |
| `POST` | `/api/beds/{id}/release` | 释放 |

### 护理决策 `/api/nursing/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/nursing/decision` | RAG 推理 (引用 + 记忆) |
| `POST` | `/api/nursing/decision/stream` | SSE 流式 |
| `POST` | `/api/nursing/taskcard` | 生成护理任务卡 |
| `PATCH` | `/api/nursing/decisions/{id}/outcome` | 回填执行结果 |

### 交接班 / 事件 / 记录

| 路径 | 说明 |
|---|---|
| `/api/handovers` | SBAR 交接班 |
| `/api/incidents` | 异常事件上报 |
| `/api/care-records` | 护理记录留痕 |
| `/api/care-levels` | 护理等级定义 |

---

## 🧱 系统架构

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │                     FastAPI + Uvicorn                        │
 管理端 (Vue 3 SPA)│  /api/auth/*  /api/ehr/*  /api/nursing/*  /api/beds/*       │
 护工端 (Vue 3 SPA)│  /api/handovers  /api/incidents  /api/care-records          │
 Landing (anime.js)│                                                              │
                    └─────────┬──────────────┬──────────────┬─────────────────────┘
                              │              │              │
                              ▼              ▼              ▼
                    ┌──────────────┐  ┌──────────┐  ┌──────────────────┐
                    │HybridRetriever│  │ OCR 服务  │  │  Ollama (本地)    │
                    │Dense+BM25+RRF│  │RapidOCR  │  │  HuatuoGPT-o1-7B │
                    └──────┬───────┘  │Tesseract │  │  JSON 任务卡      │
                           │          └────┬─────┘  └──────┬───────────┘
                           ▼               ▼               ▼
              ┌─────────────────────────────────────────────────────────┐
              │  ChromaDB (本地磁盘) — patient / medical / decision     │
              ├─────────────────────────────────────────────────────────┤
              │  SQLite (WAL)                                           │
              │    users.db · audit.db · events.db · care_store.db     │
              └─────────────────────────────────────────────────────────┘
                           ↑
                 PII 加密层 (Fernet) — 写入前加密 / 读出后解密

              ┌─────────────────────────────────────────────────────────┐
              │  前端构建 (Vite 6 多入口)                                │
              │    index.html → Vue 3 管理端 SPA                        │
              │    nurse.html → Vue 3 护工端 SPA                        │
              │    共享: vue / vue-router / pinia / components chunk    │
              │    动效: anime.js 4.4 (仅 Landing 页 code-split)        │
              └─────────────────────────────────────────────────────────┘
```

### 完整技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| **前端构建** | Vite 6 | 多入口 code-split，< 2s 冷构建 |
| **前端框架** | Vue 3.5 + TypeScript 5.7 | 组件化 SPA |
| **状态管理** | Pinia | setup store |
| **路由** | vue-router 4 | history mode |
| **动效** | anime.js 4.4 | Landing 页 5 层动画 |
| **测试** | Vitest + @vue/test-utils | 15 冒烟测试 |
| **后端框架** | FastAPI + Uvicorn | REST + SSE + 静态托管 |
| **数据校验** | Pydantic v2 | 请求/响应 Schema |
| **向量库** | ChromaDB | 档案 / 病历 / 决策日志 |
| **Embedding** | `BAAI/bge-small-zh-v1.5` | 中文轻量，CPU 可跑 |
| **OCR** | RapidOCR → Tesseract 兜底 | 病历照片文字识别 |
| **LLM** | Ollama + HuatuoGPT-o1-7B | 护理建议 / 任务卡 |
| **加密** | cryptography (Fernet) | PII 字段透明加密 |
| **存储** | SQLite WAL | 用户/审计/事件 |
| **容器** | Docker 多阶段构建 | node:20-alpine(前端) + python:3.11-slim(后端) |

---

## 📁 目录结构

```
.
├── frontend/                       # ← 新 v2 前端 (Vite + Vue 3 + TS)
│   ├── src/
│   │   ├── components/            # 6 个基础组件
│   │   ├── views/                 # 管理端 8 个视图 (Landing/Login/Beds/...)
│   │   ├── nurse-views/           # 护工端 3 个视图
│   │   ├── stores/                # Pinia (beds, auth)
│   │   ├── api/                   # typed fetch + types
│   │   ├── router/                # 管理端路由
│   │   ├── nurse-router/          # 护工端路由
│   │   └── composables/           # useToast
│   ├── index.html                 # 管理端入口
│   ├── nurse.html                 # 护工端入口
│   └── vite.config.ts             # 多入口构建
├── app/
│   ├── core/config.py             # 配置
│   ├── middleware/auth.py         # 三模式鉴权
│   ├── models/                    # Pydantic schemas
│   ├── routers/                   # 14 个路由模块
│   └── services/                  # 16 个服务模块
├── static/
│   ├── design/                    # 设计系统 (tokens/glass/ui/mobile.css)
│   ├── v2/                        # ← Vite 构建产物 (不进 git)
│   ├── index.html                 # 旧版管理端 → /legacy
│   ├── nurse.html                 # 旧版护工端 → /legacy/nurse
│   └── billing.html               # 旧版缴费端 → /legacy/billing
├── data/protocols.yaml            # 护理协议模板
├── docs/FRONTEND_REFACTOR_RFC.md  # 前端重构 RFC
├── main.py                        # 后端入口 (Phase 6 路由)
├── Dockerfile                     # 三阶段构建 (node → python → runtime)
├── docker-compose.yml
└── .env.example
```

---

## 🗺️ 重构路线图

基于 [FRONTEND_REFACTOR_RFC.md](./docs/FRONTEND_REFACTOR_RFC.md) (PR #8) 的 6 阶段计划，**全部完成**：

| Phase | PR | 内容 | 状态 |
|-------|----|----|------|
| 1 — Vite 骨架 | [#9](../../pull/9) | Vite + Vue 3 + TS + CI + `/v2/` 占位页 | ✅ |
| 2 — 设计系统 | [#10](../../pull/10) | 6 基础组件，0 改动包装 ui.css | ✅ |
| 3 — 试点视图 | [#11](../../pull/11) | vue-router + pinia + api client + 床位管理 | ✅ |
| 4 — 全量迁移 | [#12](../../pull/12) | EHR / 交接班 / 事件 / 护理记录 + auth 守卫 | ✅ |
| 5 — 护工端 | [#14](../../pull/14) | 多入口构建 + PatientList + PatientDetail + 任务卡 | ✅ |
| 6 — 旧版退役 | [#15](../../pull/15) | / → v2 SPA，旧版降到 /legacy/ | ✅ |
| 华丽 Landing | [#13](../../pull/13) | anime.js v4 动效展示页 | ✅ |

### 关键不变量 (贯穿 6 个阶段)

- ❌ 不重写后端、不动 API 契约
- ❌ 不修改 `sw.js` 缓存策略（只增不改）
- ❌ 不改设计系统任何 token
- ✅ 旧版在 `/legacy/` 永久保留
- ✅ 任意阶段都可以独立回滚 (`git revert` 单个 commit)

---

## 🏭 生产部署

### Docker Compose (推荐)

```bash
cp .env.example .env
# 编辑 .env 填入 AUTH_TOKEN + PII_ENCRYPTION_KEY
docker compose --profile ollama up -d
```

Dockerfile 使用三阶段构建：
1. `node:20-alpine` — `npm run build` 产出 `static/v2/`
2. `python:3.11-slim` — 安装 pip 依赖 + Tesseract
3. runtime — 合并两阶段产物 + 非 root 用户运行

### 数据备份

```bash
# Docker 卷备份
docker run --rm \
  -v zhihu-yinban_ehr_db:/src/ehr_db:ro \
  -v zhihu-yinban_auth_data:/src/auth_data:ro \
  -v zhihu-yinban_audit_log:/src/audit_log:ro \
  -v $(pwd):/dst alpine \
  tar czf /dst/yinban-backup-$(date +%F).tgz -C /src .
```

---

## 🤖 本地大模型

项目默认使用 **HuatuoGPT-o1-7B** (中文医疗大模型，Q4_K_M 约 4.8 GB)：

```bash
# 方式 A：Ollama 社区直拉
ollama pull cliu/HuatuoGPT-o1-7B:latest
ollama cp cliu/HuatuoGPT-o1-7B:latest huatuo_o1_7b

# 方式 B：换成其他模型
echo 'OLLAMA_MODEL_NAME=qwen2.5:7b' >> .env
```

| 量化 | 体积 | 内存需求 | 场景 |
|---|---|---|---|
| Q3_K_M | ~3.9 GB | 8 GB | 极省内存 |
| Q4_K_M | ~4.8 GB | 12 GB | **推荐** |
| Q5_K_M | ~5.5 GB | 14 GB | 质量优先 |
| Q8_0 | ~8.2 GB | 16+ GB | 接近无损 |

---

## ⚠️ 边界声明

AI 生成的护理建议**仅供护理参考，不替代医生诊断，不构成处方**。
涉及给药等敏感场景，系统只提示"请负责人核对医嘱"，不会直接生成剂量。
遇到严重症状请立即联系医生或启动急救流程。

---

## 📜 License

本项目采用 **[PolyForm Noncommercial License 1.0.0](./LICENSE)** 授权 —— 仅允许**非商业用途**。

- ✅ 允许：个人学习 / 研究、教学、公益、非营利医疗机构与养老机构内部使用
- ❌ 不允许：将本项目用于任何商业用途
- 📮 **商业授权合作**请联系：[@jiahuacaogoodman-art](https://github.com/jiahuacaogoodman-art)
- 🏥 **民营养老机构**如有商业合作意向：**jiahuacaogoodman@gmail.com**

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)

---

<p align="center">
  如果这个项目帮到了你，请给个 ⭐ — 这是我继续写下去的最大动力。
</p>
