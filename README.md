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
  <img alt="chroma"  src="https://img.shields.io/badge/ChromaDB-0.5-3C1F85">
  <img alt="ollama"  src="https://img.shields.io/badge/Ollama-HuatuoGPT__o1__7B-000000?logo=ollama&logoColor=white">
  <img alt="offline" src="https://img.shields.io/badge/Runtime-100%25%20Offline-10B981">
  <img alt="license" src="https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue">
</p>

---

## 功能总览

| 模块 | 说明 |
|---|---|
| **AI 护理决策** | Dense + BM25 + RRF 混合检索 → HuatuoGPT-o1-7B 推理，SSE 流式输出，带引用标注 + 决策记忆回填 |
| **护理任务卡** | 结构化 JSON（可打卡清单 + 复测计划 + 禁止事项 + SBAR 交接单） |
| **老人档案** | 21 字段 CRUD，全文搜索 |
| **病历 OCR** | RapidOCR + Tesseract 双引擎，上传即识别即向量化 |
| **床位管理** | 分配 / 释放 / 按楼栋状态筛选 |
| **SBAR 交接班** | 结构化记录 + 确认流程 |
| **异常事件** | 4 级严重度 + 全流程跟踪 |
| **护理记录** | 8 大类留痕 |
| **缴费管理** | 总览 / 记录 / 到期提醒 / 收费标准 / 续费 |
| **用户 & 权限** | admin / nurse / caregiver + 自定义角色 + 多 API Key |
| **审计日志** | 全部写操作留痕，带 diff + PII 脱敏 |
| **PII 加密** | Fernet 对称加密 10 个高敏字段 |

---

## 前端架构（双端）

两个独立 SPA 入口，分别面向不同角色：

| 入口 | 文件 | 面向 | 地址 |
|---|---|---|---|
| **管理端** | `frontend/index.html` → `main.ts` | 院方管理员 / 护士长 | `http://host:8000/` |
| **护工端** | `frontend/nurse.html` → `nurse-main.ts` | 一线护工（平板巡房） | `http://host:8000/nurse` |

### 管理端页面

| 路径 | 功能 |
|---|---|
| `/nursing-decision` | AI 护理建议（SSE 流式 + 决策记忆 + 结果回填） |
| `/ehr/add` | 录入老人档案（21 字段表单） |
| `/ehr` | 患者档案列表 + 详情 + 导出 |
| `/ehr/upload` | 病历上传 OCR |
| `/beds` | 床位管理 |
| `/handovers` | 交接班 |
| `/incidents` | 异常事件 |
| `/care-records` | 护理记录 |
| `/billing` | 缴费管理 |
| `/payment-channels` | 支付渠道配置 |
| `/users` | 用户管理 + 角色权限 |
| `/audit` | 审计日志 |

### 护工端页面

| 路径 | 功能 |
|---|---|
| `/nurse/` | 老人列表（移动端优先） |
| `/nurse/patient/:id` | 患者详情 + 症状输入 + 任务卡生成 + 打卡执行 |

### 技术栈

Vite 6 · Vue 3.5 · TypeScript 5.7 · vue-router 4 · Pinia · anime.js 4.4（Landing 页动效）

---

## 快速开始

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

约 10 分钟后看到 `部署成功！` + 管理员 Token。

### 前端开发

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, api proxy → 8000
npm run typecheck    # vue-tsc strict
npm run test         # vitest
npm run build        # → ../static/v2/ (index.html + nurse.html)
```

---

## 配置

`.env` 或环境变量：

| 变量 | 必须 | 说明 |
|---|---|---|
| `AUTH_TOKEN` | 是 | 管理员 bootstrap token |
| `PII_ENCRYPTION_KEY` | 是 | PII 字段加密密钥 |
| `OLLAMA_MODEL_NAME` | 否 | 默认 HuatuoGPT-o1-7B Q4_K_M |
| `EMBEDDING_MODEL_NAME` | 否 | 默认 BAAI/bge-small-zh-v1.5 |
| `EMBEDDING_ALLOW_DEGRADED` | 否 | 默认 true（模型加载失败降级启动） |
| `PORT` | 否 | 默认 8000 |

---

## API 参考

所有接口 `/api/*`，请求头带 `X-Auth-Token`。

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 认证 | GET | `/api/auth/me` | 当前身份 |
| 认证 | POST | `/api/auth/users` | 创建用户 |
| 认证 | POST | `/api/auth/tokens` | 签发 Token |
| 认证 | GET | `/api/auth/roles` | 角色列表 |
| 档案 | POST | `/api/ehr/patients` | 新增老人 |
| 档案 | GET | `/api/ehr/patients` | 列出老人 |
| 档案 | PUT | `/api/ehr/patients/{id}` | 编辑 |
| 档案 | DELETE | `/api/ehr/patients/{id}` | 删除 |
| 档案 | POST | `/api/ehr/records/upload` | 病历上传 OCR |
| 档案 | GET | `/api/ehr/records/{pid}` | 已上传病历 |
| 档案 | GET | `/api/ehr/audit` | 审计日志 |
| 床位 | GET/POST | `/api/beds` | 列表 / 新增 |
| 床位 | POST | `/api/beds/{id}/assign` | 分配 |
| 床位 | POST | `/api/beds/{id}/release` | 释放 |
| 护理 | POST | `/api/nursing/decision` | RAG 推理 |
| 护理 | POST | `/api/nursing/decision/stream` | SSE 流式 |
| 护理 | POST | `/api/nursing/taskcard` | 任务卡 |
| 护理 | GET | `/api/nursing/decisions` | 决策记忆 |
| 护理 | PATCH | `/api/nursing/decisions/{id}/outcome` | 结果回填 |
| 交接 | POST/GET | `/api/handovers` | SBAR 交接班 |
| 事件 | POST/GET | `/api/incidents` | 异常事件 |
| 记录 | POST/GET | `/api/care-records` | 护理记录 |
| 缴费 | GET | `/api/billing/overview` | 总览 |
| 缴费 | GET | `/api/billing/alerts` | 到期提醒 |
| 缴费 | POST | `/api/billing/renew` | 续费 |
| 支付 | GET | `/api/payment/channels` | 渠道配置 |

---

## 系统架构

```
┌───────────────────────────────────────────────────┐
│  管理端 SPA (index.html)  │  护工端 SPA (nurse.html) │
│  14 页 · Vite 6 构建      │  2 页 · 移动端优先        │
└────────────────┬──────────┴─────────┬─────────────┘
                 │  fetch /api/*      │
                 ▼                    ▼
┌───────────────────────────────────────────────────┐
│           FastAPI + Uvicorn (main.py)              │
│  14 Router · Auth 中间件 · SSE 流式               │
└─────┬──────────────┬──────────────┬───────────────┘
      │              │              │
      ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│ 检索引擎  │  │ OCR 服务  │  │ Ollama 本地   │
│Dense+BM25│  │RapidOCR  │  │HuatuoGPT-o1 │
│+RRF 融合 │  │Tesseract │  │7B Q4_K_M    │
└─────┬────┘  └────┬─────┘  └──────┬───────┘
      ▼            ▼               ▼
┌───────────────────────────────────────────────────┐
│ ChromaDB (向量) + SQLite WAL (结构化)              │
│ PII 加密层 (Fernet) — 写入前加密 / 读出后解密      │
└───────────────────────────────────────────────────┘
```

---

## 部署

```bash
cp .env.example .env   # 填 AUTH_TOKEN + PII_ENCRYPTION_KEY
docker compose up -d
```

三阶段 Dockerfile：node:20-alpine(前端构建) → python:3.11-slim(后端) → runtime。

---

## 边界声明

AI 生成的护理建议**仅供参考，不替代医生诊断，不构成处方**。
遇到严重症状请立即联系医生或启动急救流程。

---

## License

**[PolyForm Noncommercial License 1.0.0](./LICENSE)** — 仅允许非商业用途。
商业授权请联系：**jiahuacaogoodman@gmail.com**

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)
