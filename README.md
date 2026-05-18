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
  <a href="#-前端架构">前端架构</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-配置说明">配置说明</a> ·
  <a href="#-api-参考">API 参考</a> ·
  <a href="#-系统架构">架构</a>
</p>

---

## 为什么做这个

基层养老院面对的真实矛盾是：

- 老人多、护工人均看护数高，**专业经验很难均质化**；
- 病历碎在纸上、U 盘里、微信群里，**AI 想用却无从入手**；
- 院方最担心"**数据上云 = 合规和责任**"，所以很多云端 AI 方案直接被一票否决。

**智护银伴**的目标：让养老院把"大模型 + RAG"真正用起来，所有档案、照片、AI 决策全部保存在本机磁盘，一台普通服务器 + 局域网即可运行。

---

## 功能总览

### 核心业务

| 模块 | 功能 | 说明 |
|---|---|---|
| **AI 护理决策** | 混合检索 + LLM 推理 | Dense + BM25 + RRF 融合，带源类型加权和引用标注 |
| **护理任务卡** | 结构化 JSON 输出 | 可打卡清单 + 复测计划 + 禁止事项 + SBAR 交接单 |
| **老人档案管理** | 增删改查 | 21 个字段（姓名、年龄、病史、过敏、床位、护理等级等） |
| **病历照片 OCR** | 上传 → 本地识别 → 向量化 | RapidOCR (ONNX) + Tesseract 双引擎，纯本地运行 |
| **床位管理** | 分配/释放/状态筛选 | 按楼栋/状态查看，实时统计空闲/占用 |
| **SBAR 交接班** | 结构化记录 + 确认流程 | Situation / Background / Assessment / Recommendation |
| **异常事件上报** | 4 级严重度 + 全流程跟踪 | 跌倒/误吸/走失，从上报到根因分析全程可追溯 |
| **护理记录** | 8 大类留痕 | 生命体征/用药/饮食/活动/观察/特护 |
| **缴费管理** | 总览/记录/到期提醒/收费标准 | 续费 + 微信扫码收款 |
| **决策记忆 (L4)** | 自动写回 + 结果回填 | AI 看得到"上次对同一个老人怎么处理、效果如何" |
| **SSE 流式输出** | 逐 token 推送 | 实时看到 AI 生成过程 |

### 安全与合规

| 模块 | 说明 |
|---|---|
| **多用户认证** | admin / nurse / caregiver 三种角色 + 自定义角色 + 多 API Key |
| **PII 字段加密** | Fernet 对称加密 10 个高敏字段（写入前自动加密） |
| **操作审计日志** | 全部写操作留痕，带 diff 且 PII 自动脱敏 |
| **用户/角色管理** | 可视化配置角色与权限点 |

---

## 前端架构

统一的单页应用（SPA），管理端和护工端合并在同一个入口，不再分散。

### 技术栈

| 层 | 选型 |
|---|---|
| 构建 | Vite 6 — 单入口 code-split，< 2s 冷构建 |
| 框架 | Vue 3.5 + Composition API + TypeScript 5.7 |
| 路由 | vue-router 4 (history mode，懒加载) |
| 状态 | Pinia (setup store) |
| 动效 | anime.js 4.4（仅 Landing 页） |
| 设计系统 | tokens.css + glass.css + ui.css + mobile.css |
| 测试 | Vitest + @vue/test-utils (16 个冒烟测试) |

### 页面清单

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | Landing | 首页（anime.js 动效） |
| `/login` | Login | Token 登录 |
| `/nursing-decision` | AI 护理建议 | 选老人 → 输入症状 → SSE 流式建议 + 决策记忆 + 结果回填 |
| `/ehr/add` | 录入档案 | 21 字段完整表单 |
| `/ehr` | 患者档案 | 老人列表 + 详情 + 导出 |
| `/ehr/upload` | 病历上传 | 多图 OCR 上传 + 已上传列表管理 |
| `/beds` | 床位管理 | 分配/释放/状态筛选 |
| `/handovers` | 交接班 | SBAR 结构化记录 |
| `/incidents` | 异常事件 | 上报 + 跟踪 |
| `/care-records` | 护理记录 | 8 大类留痕 |
| `/billing` | 缴费管理 | 总览/记录/到期提醒/收费标准/续费 |
| `/payment-channels` | 支付渠道 | 微信支付配置 |
| `/users` | 用户管理 | 创建用户 + 签发 Token + 角色权限 |
| `/audit` | 审计日志 | 按操作类型/patient_id 筛选 |
| `/nurse` | 护工端-老人列表 | 移动端优先的老人列表 |
| `/nurse/patient/:id` | 护工端-患者详情 | 症状输入 + 任务卡生成 + 打卡执行 |

### 目录结构

```
frontend/
├── index.html               ← 唯一入口
├── vite.config.ts           ← 单入口构建
├── src/
│   ├── main.ts              ← bootstrap
│   ├── App.vue              ← 统一 layout (侧栏 + 底部 tab + 抽屉)
│   ├── router/index.ts      ← 全部路由
│   ├── stores/              ← Pinia stores (beds, auth)
│   ├── api/                 ← typed fetch client
│   ├── components/          ← 6 个基础组件
│   ├── composables/         ← useToast / useMediaQuery / useViewport ...
│   ├── views/               ← 14 个页面视图
│   ├── nurse-views/         ← 护工端视图 (PatientList + PatientDetail)
│   └── __tests__/           ← Vitest 冒烟测试
└── package.json
```

---

## 快速开始

### 一键部署

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

Windows PowerShell：

```powershell
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

约 10 分钟后看到 `部署成功！` + 管理员 Token。

| 页面 | 地址 |
|---|---|
| 首页 | http://localhost:8000/ |
| AI 护理建议 | http://localhost:8000/nursing-decision |
| 护工端 | http://localhost:8000/nurse |
| 健康检查 | http://localhost:8000/health |

### 前端开发

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173，api 自动 proxy 到 8000
npm run typecheck    # vue-tsc strict
npm run test         # vitest (16 cases)
npm run build        # 产物 → ../static/v2/index.html
```

---

## 配置说明

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

## API 参考

所有接口在 `/api/*` 下，请求头需带 `X-Auth-Token`。

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 认证 | `GET` | `/api/auth/me` | 当前身份 |
| 认证 | `POST` | `/api/auth/users` | 创建用户 (admin) |
| 认证 | `POST` | `/api/auth/tokens` | 签发 API Key |
| 认证 | `GET` | `/api/auth/roles` | 角色列表 |
| 认证 | `GET` | `/api/auth/permissions` | 权限点清单 |
| 档案 | `POST` | `/api/ehr/patients` | 新增老人 |
| 档案 | `GET` | `/api/ehr/patients` | 列出所有老人 |
| 档案 | `PUT` | `/api/ehr/patients/{id}` | 编辑老人 |
| 档案 | `DELETE` | `/api/ehr/patients/{id}` | 删除老人 |
| 档案 | `POST` | `/api/ehr/records/upload` | 上传病历照片 (OCR) |
| 档案 | `GET` | `/api/ehr/records/{pid}` | 查看已上传病历 |
| 档案 | `GET` | `/api/ehr/audit` | 审计日志 (admin) |
| 床位 | `GET` | `/api/beds` | 列表 + 筛选 |
| 床位 | `POST` | `/api/beds` | 新增床位 |
| 床位 | `POST` | `/api/beds/{id}/assign` | 分配 |
| 床位 | `POST` | `/api/beds/{id}/release` | 释放 |
| 护理 | `POST` | `/api/nursing/decision` | RAG 推理 |
| 护理 | `POST` | `/api/nursing/decision/stream` | SSE 流式 |
| 护理 | `POST` | `/api/nursing/taskcard` | 生成护理任务卡 |
| 护理 | `GET` | `/api/nursing/decisions` | 决策记忆列表 |
| 护理 | `PATCH` | `/api/nursing/decisions/{id}/outcome` | 回填执行结果 |
| 交接 | `POST/GET` | `/api/handovers` | SBAR 交接班 |
| 事件 | `POST/GET` | `/api/incidents` | 异常事件上报 |
| 记录 | `POST/GET` | `/api/care-records` | 护理记录 |
| 缴费 | `GET` | `/api/billing/overview` | 缴费总览 |
| 缴费 | `GET` | `/api/billing/records` | 缴费记录 |
| 缴费 | `GET` | `/api/billing/alerts` | 到期提醒 |
| 缴费 | `POST` | `/api/billing/renew` | 续费 |
| 支付 | `GET` | `/api/payment/channels` | 支付渠道配置 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│              Vue 3 统一 SPA (Vite 6 构建)                │
│   管理端 14 页 + 护工端 2 页  │  anime.js Landing 动效   │
└──────────────────────┬──────────────────────────────────┘
                       │ fetch /api/*
                       ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI + Uvicorn (main.py)                  │
│   14 个 Router 模块  │  Auth 中间件  │  SSE 流式         │
└───────┬──────────────┬──────────────┬───────────────────┘
        │              │              │
        ▼              ▼              ▼
┌────────────┐  ┌──────────┐  ┌──────────────────┐
│  检索引擎   │  │ OCR 服务  │  │  Ollama (本地)    │
│Dense+BM25  │  │RapidOCR  │  │  HuatuoGPT-o1-7B │
│+RRF 融合   │  │Tesseract │  │  JSON 任务卡      │
└─────┬──────┘  └────┬─────┘  └──────┬───────────┘
      │               │               │
      ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│  ChromaDB (本地磁盘) — patient / medical / decision      │
├─────────────────────────────────────────────────────────┤
│  SQLite (WAL) — users / audit / events / care_store      │
└─────────────────────────────────────────────────────────┘
                 ↑
       PII 加密层 (Fernet)
```

### 后端目录

```
app/
├── core/config.py             # 环境变量 → 配置常量
├── middleware/auth.py         # 三模式鉴权 (token / user / disabled)
├── models/                    # Pydantic v2 请求/响应 Schema
├── routers/                   # 14 个路由模块 (每个模块 < 120 行)
└── services/                  # 业务逻辑层 (DB / OCR / LLM / 加密 / 检索)
```

---

## 生产部署

### Docker Compose

```bash
cp .env.example .env
# 编辑 .env 填入 AUTH_TOKEN + PII_ENCRYPTION_KEY
docker compose --profile ollama up -d
```

Dockerfile 使用三阶段构建：
1. `node:20-alpine` — 前端 `npm run build` → `static/v2/`
2. `python:3.11-slim` — 后端依赖 + Tesseract
3. runtime — 合并产物 + 非 root 运行

### GPU 加速

```bash
docker compose -f docker-compose.gpu.yml up -d
```

---

## 本地大模型

默认使用 **HuatuoGPT-o1-7B**（中文医疗大模型，Q4_K_M 约 4.8 GB）：

```bash
ollama pull cliu/HuatuoGPT-o1-7B:latest
```

| 量化 | 体积 | 内存需求 | 场景 |
|---|---|---|---|
| Q4_K_M | ~4.8 GB | 12 GB | **推荐** |
| Q8_0 | ~8.2 GB | 16+ GB | 质量优先 |

换模型只需改环境变量：

```bash
echo 'OLLAMA_MODEL_NAME=qwen2.5:7b' >> .env
```

---

## 边界声明

AI 生成的护理建议**仅供护理参考，不替代医生诊断，不构成处方**。
涉及给药等敏感场景，系统只提示"请负责人核对医嘱"，不会直接生成剂量。
遇到严重症状请立即联系医生或启动急救流程。

---

## License

**[PolyForm Noncommercial License 1.0.0](./LICENSE)** — 仅允许非商业用途。

- 允许：个人学习 / 研究、教学、公益、非营利医疗机构与养老机构内部使用
- 不允许：将本项目用于任何商业用途
- 商业授权合作请联系：**jiahuacaogoodman@gmail.com**

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)

---

<p align="center">
  如果这个项目帮到了你，请给个 Star — 这是我继续写下去的最大动力。
</p>
