<h1 align="center">智护银伴 · ZhiHu YinBan</h1>

<p align="center">
  <b>本地优先的养老院 AI 护理辅助与运营系统</b><br>
  档案不出院、照片不上云、建议可追溯、任务可打卡，一台院内服务器 + 局域网即可试点运行。
</p>

<p align="center">
  <a href="./README.md">简体中文</a> · <a href="./README.en.md">English</a> · <a href="./LICENSE">License</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white">
  <img alt="ChromaDB" src="https://img.shields.io/badge/ChromaDB-0.6-3C1F85">
  <img alt="Ollama" src="https://img.shields.io/badge/Ollama-HuatuoGPT--o1--7B-000000?logo=ollama&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue">
</p>

<p align="center">
  <a href="#-为什么做这个">为什么做</a> ·
  <a href="#-功能总览">功能总览</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-本地大模型与远程-api">模型配置</a> ·
  <a href="#-使用指南">使用指南</a> ·
  <a href="#-api-参考">API 参考</a> ·
  <a href="#-系统架构">架构</a> ·
  <a href="#-生产部署">生产部署</a> ·
  <a href="#-常见部署问题">常见问题</a>
</p>

---

## 🌱 为什么做这个

基层养老院面对的真实矛盾不是“有没有 AI”，而是数据、流程和责任经常断在不同地方：

- 老人多、护工人均看护数高，专业经验很难均质化。
- 病历碎在纸上、U 盘里、微信群里，AI 想用却无从入手。
- 护理建议如果没有证据来源、执行记录和结果回填，很难被追责和复用。
- 院方最担心“数据上云 = 合规和责任风险”，很多云端 AI 方案天然过不了内控。
- 试点现场经常没有 GPU、网络不稳定、Docker 和模型下载都可能卡住。

智护银伴的目标是让养老院把“大模型 + RAG + 护理任务闭环”真正跑起来：档案、病历、照片、审计、任务卡和 AI 决策默认保存在本地，既能在院内服务器部署，也能接入远程 OpenAI 兼容模型。

它不是一个“聊天机器人套壳”。更准确地说，它是一套围绕养老照护现场设计的：

```text
本地数据底座 + 护理运营工作台 + RAG 护理建议 + 任务卡闭环
```

## ✨ 功能总览

### 核心业务功能

| 模块 | 功能 | 说明 |
| --- | --- | --- |
| 患者档案管理 | 增删改查、搜索、PDF 导出 | 支持老人基本信息、病史、过敏、床位、护理等级、联系人等字段。 |
| 独立录入页面 | `/ehr/new` | 档案录入不再挤在列表弹窗里，适合批量建档和前台登记。 |
| 病历照片 OCR | 上传 -> 本地识别 -> 写入检索库 | 图片保存在本地磁盘，OCR 文本进入本地 ChromaDB。 |
| AI 护理建议 | RAG 检索 + LLM 推理 | 基于患者档案、病历 OCR 和决策记忆生成建议，支持证据引用。 |
| SSE 流式输出 | 逐 token 推送 | 护理建议生成过程可实时显示，不必等完整回答。 |
| 决策记忆 | 自动写回 + 结果回填 | AI 能看到“上次同一老人怎么处理、效果如何”。 |
| 护理任务卡 | 结构化任务 + 复测计划 + 禁忌事项 | 把长建议拆成一线可执行、可打卡的护理动作。 |
| SBAR 交接 | 交接班记录与确认 | 把事件背景、评估、建议和责任交接结构化。 |
| 护理运营 | 床位、护理等级、异常事件、护理记录 | 管理端覆盖日常照护流程。 |
| 入住与缴费 | 入住申请、评估、合同、缴费、续费、提醒 | 支持收费标准、缴费记录、到期提醒和收据 PDF。 |
| 支付渠道 | 微信支付 + 模拟模式 | 可先跑通流程，再接生产商户配置。 |

### 安全与合规

| 模块 | 功能 | 说明 |
| --- | --- | --- |
| 用户身份认证 | 用户 + API Key + 角色权限 | bootstrap 管理员 Token，后续可创建用户和签发 Token。 |
| PII 字段加密 | Fernet 对称加密 | 姓名、身份证、联系方式、过敏史等敏感字段写入前加密。 |
| 操作审计 | 写操作与敏感读取留痕 | 记录谁在什么时间对哪个老人做了什么修改。 |
| 审计防泄密 | diff 中 PII 脱敏 | 审计日志用于追溯，不直接扩散明文隐私。 |
| 冷备份 | AES-256-GCM 加密备份 | 可按天备份本地数据目录到 NAS、USB 盘或安全目录。 |
| 边缘同步 | 脱敏聚合指标上报 | 可选同步空床率、欠费数、异常事件等指标，不上传底层 PII。 |

### 运维可观测

| 端点 | 返回 | 用途 |
| --- | --- | --- |
| `GET /health` | `auth_mode`、`rag_available`、`pii_encryption_enabled`、前端构建状态 | systemd、Docker、监控探针。 |
| `GET /api/ehr/audit` | 按患者、动作、时间筛选审计记录 | 管理员审计。 |
| `GET /api/backup/status` | 备份调度器状态与最近报告 | 生产备份巡检。 |

## 🧭 技术路线

智护银伴的技术路线不是“前端 + 后端 + 大模型”三段式，而是围绕养老院真实闭环拆成九层：入口、鉴权、业务域、检索、模型、事件、审计、存储、部署。每一层都服务一个具体问题。

### 总体分层

```text
┌──────────────────────────────────────────────────────────────┐
│ Vue 3 多入口前端                                             │
│ 管理端 index.html：档案/床位/交接/缴费/审计                  │
│ 护工端 nurse.html：老人列表/症状输入/任务卡/执行打卡         │
└──────────────────────────────┬───────────────────────────────┘
                               │ fetch /api/* + X-Auth-Token
┌──────────────────────────────▼───────────────────────────────┐
│ FastAPI 应用入口 main.py                                      │
│ AuthTokenMiddleware / ReadAuditMiddleware / SPA fallback       │
│ /health 暴露 auth_mode、rag_available、pii_encryption_enabled │
└───────────┬──────────────┬──────────────┬────────────────────┘
            │              │              │
            ▼              ▼              ▼
┌────────────────┐ ┌────────────────┐ ┌───────────────────────┐
│ 业务路由层      │ │ AI 护理决策层   │ │ 运维安全层             │
│ EHR/Beds/Bill  │ │ RAG/SSE/TaskCard│ │ Auth/RBAC/Audit/Backup │
└───────┬────────┘ └───────┬────────┘ └──────────┬────────────┘
        │                  │                     │
        ▼                  ▼                     ▼
┌────────────────┐ ┌───────────────────────┐ ┌─────────────────┐
│ SQLite WAL     │ │ ChromaDB + Hybrid RAG  │ │ Fernet/AES-GCM  │
│ care/billing   │ │ Dense + BM25 + RRF     │ │ PII/backup key  │
│ auth/audit     │ │ Evidence + Memory      │ │ encrypted data  │
└────────────────┘ └───────────┬───────────┘ └─────────────────┘
                                │
                                ▼
                    Ollama 本地模型 / OpenAI 兼容接口
```

### 1. 多入口前端：按角色拆工作台

| 入口 | 技术 | 承载的复杂度 |
| --- | --- | --- |
| 管理端 | `frontend/index.html` + `src/main.ts` + Vue Router | 档案、录入、上传、床位、交接、异常、护理记录、缴费、支付渠道、用户、审计。 |
| 护工端 | `frontend/nurse.html` + `src/nurse-main.ts` + `createWebHistory('/nurse')` | 移动端优先，围绕老人详情、症状输入、任务卡、复测和打卡。 |
| 构建产物 | Vite 多入口 + `base: '/v2/'` + `static/dist/` | 后端统一托管两个 SPA，history 路由由 FastAPI fallback 到对应 HTML。 |

这让“院方管理”和“一线执行”不互相污染：管理端信息密度高，护工端流程更短、更适合巡房和平板。

### 2. 本地数据底座：ChromaDB + 多个 SQLite store + CAS 文件仓

| 数据类型 | 存储 | 技术点 |
| --- | --- | --- |
| 患者档案、OCR 文本、决策记忆 | ChromaDB PersistentClient | 同一个 collection 内用 `patient_id`、`doc_type`、`source_type` 区分档案、病历、决策日志。 |
| 病历原图 | Content-Addressable Storage | 文件名按 `sha256` 分桶，重复文件自动 dedup，写入先 `.tmp` 再 `os.replace`，可做完整性校验。 |
| 用户和 API Key | `local_auth/users.db` | Token 明文只返回一次，库里保存 hash 和前缀。 |
| 床位、护理等级、交接、异常、记录、入住 | `local_care/care.db` | SQLite WAL，本地单机部署足够轻。 |
| 缴费、收费标准、续费提醒 | `local_billing/billing.db` | 与护理业务库拆开，方便备份和权限隔离。 |
| 审计日志 | `local_audit_log/audit.db` | 写操作、病历预览和敏感导出留痕。 |
| 护理任务事件 | `local_nursing_events/events.db` | 任务卡、打卡、复测观察、归档和 SBAR 都是事件流。 |

SQLite 不是随便用：项目统一了 `PRAGMA journal_mode=WAL`、`synchronous=NORMAL`、`busy_timeout=5000ms`，并对关键写操作提供指数退避重试，避免多 worker 或高频打卡时直接抛 `database is locked`。

### 3. 混合检索：Dense + BM25 + RRF + source 权重

护理场景里，“语义相似”和“关键词精确命中”都重要：老人可能说“头晕”，病历里写的是“低血糖反应”；也可能必须精确命中“青霉素”“华法林”“餐前血糖 3.2”。所以检索不是单纯向量召回。

```text
输入：patient_id + symptom
  1. ChromaDB collection.get(where patient_id) 拉取该老人全部文档
  2. 按 source_type/include/exclude 做来源过滤
  3. 字符 bi-gram + 英文/数字 token 做 BM25 稀疏打分
  4. sentence-transformers encode 后做 ChromaDB dense query
  5. BM25 topK 和 Dense topK 用 RRF 融合
  6. 按来源加权：patient_profile / medical_record_upload / observation / decision_log
  7. 生成 Evidence：E1、E2、source_label、snippet、score、metadata
```

| 组件 | 设计 |
| --- | --- |
| 中文分词 | 字符 bi-gram + 单字 + 英文/数字 token，不引入词典依赖。 |
| 稀疏检索 | 纯 Python BM25，适合单个老人几十到几百条档案的规模。 |
| 稠密检索 | ChromaDB `query_embeddings` + `where={"patient_id": ...}`。 |
| 融合策略 | RRF（Reciprocal Rank Fusion），避免单一路径召回偏差。 |
| 来源权重 | `patient_profile`、`medical_record_upload`、`observation`、`decision_log` 分别加权。 |
| 证据格式 | `[E1] 来源：病历OCR·时间` + snippet，直接进入 prompt。 |
| 性能优化 | BM25 索引按 `(patient_id, frozenset(doc_ids))` 做进程级 LRU 缓存。 |
| async 保护 | `retrieve_async()` 用 `asyncio.to_thread`，避免 RAG 阻塞 event loop。 |

### 4. 决策记忆：AI 建议不是一次性回答

每次 AI 决策会写入 ChromaDB，`doc_type=decision_log`。它本身也会成为下次检索的证据。

```text
AI 建议生成
  -> 保存 decision_id、symptom、advice_preview、evidence_refs、risk_level、event_id
  -> outcome_status 初始 pending
  -> 护理人员回填 effective / partial / ineffective
  -> record_outcome 更新 metadata + 把实际执行结果追加到可检索文本
  -> 下次同一患者类似症状检索时，过去决策自然进入 Evidence
```

这里的关键不是“存聊天记录”，而是把“当时建议什么 + 引用了哪些证据 + 后来实际如何”变成可检索、可追溯、可回填的护理经验。

### 5. 护理任务卡：从建议到事件闭环

任务卡不是普通文本回答，而是一个可以执行的事件对象。

```text
POST /api/nursing/task-card
  -> RAG 拉取患者上下文
  -> AI 生成严格 JSON：风险等级、护理建议、即时任务、禁忌、复测、SBAR
  -> normalize/sanitize：任务字段、风险等级、输入项、复测计划
  -> EventStore 保存为 nursing event
  -> DecisionMemory 同步写入一次 task-card 决策
  -> 护工逐项 PATCH complete/abnormal/skipped
  -> 观察记录 POST observations
  -> SBAR GET /sbar
  -> archive 归档为结构化护理记录
```

| 子系统 | 技术点 |
| --- | --- |
| 风险分级 | `red/orange/yellow/green`，同时保留 label、title、color。 |
| AI JSON | provider 支持 `format=json`，OpenAI 兼容端转为 `response_format=json_object`。 |
| JSON 防御 | 支持从 markdown code fence 或混杂文本中提取 JSON，解析失败返回 502 和原始输出片段。 |
| 任务状态 | `pending/done/abnormal/skipped`，保留 `completed_at`、`completed_by`、`note`、`value`。 |
| 审计轨迹 | 每条任务有 `audit_trail`，事件有 `execution_logs`。 |
| 协议模板 | `data/protocols.yaml` 热加载，可扩展跌倒、低血糖、误吸、发热等护理流程。 |

### 6. LLM Provider 抽象：Ollama 与 OpenAI 兼容协议共用一套上层逻辑

| Provider | 适用场景 | 实现细节 |
| --- | --- | --- |
| `ollama` | 本地模型、离线优先、院内服务器 | 调 `/api/generate`，支持普通和 stream，兼容 Ollama options。 |
| `openai` | vLLM/TGI/SGLang/DeepSeek/智谱/Qwen/LM Studio | 调 `/chat/completions`，把 Ollama options 映射为 OpenAI 参数。 |

OpenAI 兼容层还处理了高频部署坑：如果用户把 `OPENAI_API_BASE` 写成 `/chat/completions` 完整路径，服务层会自动剥离后缀并提示，避免拼出双重路径 404。

### 7. 安全路线：三模式鉴权 + RBAC + PII 透明加密 + 审计脱敏

| 层 | 机制 |
| --- | --- |
| 鉴权入口 | `AuthTokenMiddleware` 保护 `/api/*` 和 `/uploads/*`。 |
| Token 传递 | 支持 `X-Auth-Token`，也支持 `?token=` 供病历文件预览。 |
| 鉴权模式 | `user_store`、`legacy_token`、`disabled` 三模式自动切换。 |
| 权限控制 | 路由通过 `require_permission("xxx")` 声明权限点，不硬编码角色名。 |
| PII 加密 | 10 个高敏字段写入 ChromaDB metadata 前 Fernet 加密，密文带 `enc:` 前缀防双重加密。 |
| PII 解密 | 读取时透明解密；密钥缺失时返回占位符，不把密文泄露给前端。 |
| 审计脱敏 | audit diff 中 PII 字段只显示“有变化”，不写明文也不写密文。 |
| 健康可观测 | `/health` 暴露 `auth_mode`、`pii_encryption_enabled`、`rag_available`。 |

### 8. 备份与灾备：不是简单 tar

冷备份模块会打包七类本地数据：ChromaDB、上传病历、缴费库、护理业务库、用户库、审计库、护理事件流。备份文件不是裸 tar，而是：

```text
magic b"ZYBAK\x01"
  + 12-byte nonce
  + AES-256-GCM(ciphertext + tag)

plaintext = tar.gz(目录树 + _manifest.json)
```

| 能力 | 说明 |
| --- | --- |
| 完整性 | AES-GCM 是认证加密，文件被篡改 1 字节也会解密失败。 |
| manifest | 记录 created_at、hostname、每个源目录文件数和字节数。 |
| 调度 | 不引 APScheduler，lifespan 里启动纯 asyncio task，每天指定时间跑。 |
| 立即备份 | `POST /api/backup/run` 可手动触发。 |
| 保留策略 | `BACKUP_RETENTION_DAYS` 自动清理旧备份。 |
| 部署友好 | `BACKUP_DIR` 可指向 NAS、USB 加密盘或院内安全目录。 |

### 9. 部署路线：同一代码适配四种现实环境

| 环境 | 技术路线 |
| --- | --- |
| 标准试点 | Docker Compose 构建前端和后端，`--profile ollama` 启动本地模型和 model-puller。 |
| GPU 服务器 | 叠加 `docker-compose.gpu.yml`，让 Ollama 使用 NVIDIA runtime。 |
| 无 GPU / 网络差 | `requirements-api.txt` + `EMBEDDING_DISABLED=true`，先跑业务和远程 LLM。 |
| 非开发者 macOS | `.command` + 本地浏览器单页向导生成密钥、写 `.env`、启动 Docker 部署。 |
| 非开发者 Windows | `.bat` + PowerShell 向导生成密钥、写 `.env`、启动服务、打开浏览器。 |
| 中国大陆网络 | `setup-cn.sh` / `setup-cn.ps1` 使用镜像源和 `hf-mirror.com`。 |

这也是项目复杂度的一部分：不是只在开发者电脑上能跑，而是要尽量覆盖养老院现场真正会遇到的部署条件。

## 🚀 快速开始

### 一键部署向导（推荐）

只需要先装好 Docker。向导会自动生成密钥、选择模型、写入 `.env`、启动服务并等待健康检查。

#### macOS 图形向导

Finder 中双击：

```text
配置向导.command
```

它会打开一个只监听 `127.0.0.1` 的本地浏览器单页表单：选择本地 Ollama 或远程 OpenAI 兼容 API、生成管理员 Token、生成 PII 加密密钥、写入 `.env`，然后打开 Terminal 执行 Docker Compose 部署。

日常启动或调试可以双击：

```text
启动智护银伴.command
```

启动菜单可选择图形部署向导、Docker 启动、API-only、本地后端运行或只打开浏览器。

#### Linux / macOS 命令行

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
chmod +x scripts/setup.sh
./scripts/setup.sh
```

#### Windows PowerShell

```powershell
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Windows 用户也可以直接双击：

```text
启动智护银伴.bat
配置向导.bat
```

更多本地应用化说明见 [docs/LOCAL_APP_DEPLOYMENT.md](./docs/LOCAL_APP_DEPLOYMENT.md)。

### 国内网络部署

仓库内置中国大陆网络友好的脚本，会使用镜像源、`hf-mirror.com` 等加速路径。

#### Linux / macOS

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
chmod +x scripts/setup-cn.sh
./scripts/setup-cn.sh
```

#### Windows PowerShell

```powershell
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
powershell -ExecutionPolicy Bypass -File .\scripts\setup-cn.ps1
```

### 访问地址

| 页面 | 地址 |
| --- | --- |
| 管理端 | `http://localhost:8000/` |
| 登录页 | `http://localhost:8000/login` |
| 护工端 | `http://localhost:8000/nurse` |
| AI 护理建议 | `http://localhost:8000/nursing-decision` |
| 患者档案 | `http://localhost:8000/ehr` |
| 录入档案 | `http://localhost:8000/ehr/new` |
| 健康检查 | `http://localhost:8000/health` |

第一次登录使用 `.env` 里的 `AUTH_TOKEN`。后续可在用户管理里创建用户并签发 API Key。

## 🤖 本地大模型与远程 API

项目支持两类 LLM 后端：

| Provider | 适合场景 |
| --- | --- |
| `ollama` | 模型也要在本地或院内服务器运行。 |
| `openai` | 使用 vLLM、TGI、SGLang、DeepSeek、智谱、Qwen 或其他 OpenAI 兼容接口。 |

### 方式 A：Docker Compose + 本地 Ollama

```bash
cp .env.example .env
```

至少填写：

```env
# 用下方“配置说明”里的命令生成后填入，不要使用示例值或短密码
AUTH_TOKEN=
PII_ENCRYPTION_KEY=
LLM_PROVIDER=ollama
OLLAMA_MODEL_NAME=hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M
EMBEDDING_ALLOW_DEGRADED=true
```

启动：

```bash
docker compose --profile ollama up -d --build
docker compose logs -f model-puller
docker compose logs -f app
curl http://localhost:8000/health
```

默认模型是 HuatuoGPT-o1-7B GGUF Q4_K_M，约 4.8 GB。首次下载取决于网络速度。

有 NVIDIA GPU 时叠加：

```bash
docker compose --profile ollama \
  -f docker-compose.yml \
  -f docker-compose.gpu.yml \
  up -d --build
docker exec yinban-ollama nvidia-smi
```

### 方式 B：裸机 Ollama

如果不用 Docker，而是在宿主机手动跑 Ollama，需要确认模型名和 `.env` 一致：

```bash
ollama list
ollama run huatuo_o1_7b "请用一句话介绍自己"
```

如果你拉的是别的模型，可以直接改 `.env`：

```env
OLLAMA_MODEL_NAME=qwen2.5:7b
```

或者给现有模型起别名：

```bash
ollama pull qwen2.5:7b
ollama cp qwen2.5:7b huatuo_o1_7b
ollama list | grep huatuo_o1_7b
```

常见模型选择：

| 模型 | 说明 |
| --- | --- |
| `hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q3_K_M` | 更省内存。 |
| `hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M` | 默认平衡档。 |
| `hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q5_K_M` | 质量更好，内存占用更高。 |
| `qwen2.5:7b` | 通用中文模型，可用于对比。 |
| `qwen2.5:3b` | 机器较弱时的轻量替代。 |

### 方式 C：OpenAI 兼容 API

适合已经有远程 GPU 服务、云端模型或自建推理服务的情况。

```env
LLM_PROVIDER=openai
OPENAI_API_BASE=http://your-llm-host:8000/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
OPENAI_API_KEY=
EMBEDDING_DISABLED=true
PY_REQUIREMENTS=requirements-api.txt
```

启动：

```bash
docker compose up -d --build
curl http://localhost:8000/health
```

注意：`OPENAI_API_BASE` 是根地址，例如 `http://host:8000/v1`，不要写成 `/chat/completions` 完整路径。

## ⚙️ 配置说明

完整模板见 [.env.example](./.env.example)。

### 必须配置（生产环境）

| 变量 | 用途 | 生成方式 |
| --- | --- | --- |
| `AUTH_TOKEN` | 首次管理员 bootstrap Token | `openssl rand -hex 32` |
| `PII_ENCRYPTION_KEY` | PII 字段加密密钥 | `python3 -c 'import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'` |

### 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | 监听地址。 |
| `PORT` | `8000` | 监听端口。 |
| `LLM_PROVIDER` | `ollama` | `ollama` 或 `openai`。 |
| `OLLAMA_API_URL` | `http://localhost:11434/api/generate` | Ollama generate 接口。 |
| `OLLAMA_MODEL_NAME` | `huatuo_o1_7b` | 裸机默认模型名；Compose 会覆盖为 HuggingFace GGUF tag。 |
| `OPENAI_API_BASE` | 空 | OpenAI 兼容服务根地址。 |
| `OPENAI_MODEL` | 空 | 远程模型名。 |
| `OPENAI_API_KEY` | 空 | 云端 API 通常必填，自建服务可留空。 |
| `EMBEDDING_DISABLED` | `false` | 不加载 torch/sentence-transformers，走哈希向量占位。 |
| `EMBEDDING_ALLOW_DEGRADED` | `true` | embedding 加载失败时允许降级启动。 |
| `EMBEDDING_MODEL_LOCAL_PATH` | 空 | 离线部署时指向本地 embedding 模型目录。 |
| `MAX_UPLOAD_SIZE_MB` | `15` | 单个病历图片大小上限。 |
| `PY_REQUIREMENTS` | `requirements.txt` | Docker 构建参数，可改成 `requirements-api.txt`。 |
| `BACKUP_ENABLED` | `false` | 是否启用每日冷备份。 |
| `BACKUP_ENCRYPTION_KEY` | 空 | AES-256-GCM 备份密钥。 |
| `BACKUP_DIR` | `local_backups/` | 备份目录，生产建议指向 NAS 或安全外置盘。 |
| `WECHAT_PAY_*` | 空 | 微信支付配置；全空时走模拟模式。 |

### 鉴权模式

| 条件 | 模式 | 说明 |
| --- | --- | --- |
| UserStore 有用户 | `user_store` | 正常运行模式。 |
| UserStore 空 + `AUTH_TOKEN` 非空 | `legacy_token` | 首次启动过渡模式，bootstrap 后进入 `user_store`。 |
| 两者都空 | `disabled` | 仅限开发测试，生产禁止。 |

## 📖 使用指南

### 1. 登录

打开 `http://localhost:8000/`，把 `.env` 里的 `AUTH_TOKEN` 粘贴到登录页。登录后 Token 会保存在浏览器 localStorage。

### 2. 创建护工账号

```bash
curl -X POST http://localhost:8000/api/auth/users \
  -H "X-Auth-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"wang_nurse","display_name":"王护士","role":"nurse"}'
```

### 3. 为护工签发 API Key

```bash
curl -X POST http://localhost:8000/api/auth/tokens \
  -H "X-Auth-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"usr_xxxxxxxx","label":"护工端平板"}'
```

Token 只会返回一次，请立即保存。

### 4. 录入老人档案

```bash
curl -X POST http://localhost:8000/api/ehr/patients \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "p001",
    "name": "张奶奶",
    "age": 82,
    "gender": "女",
    "bed_number": "A-205",
    "care_level": "二级",
    "medical_history": "高血压20年、2型糖尿病15年，长期服用缬沙坦和二甲双胍",
    "allergy": "青霉素",
    "emergency_contact": "张明",
    "emergency_phone": "13800138000",
    "emergency_relation": "儿子"
  }'
```

网页端也可以直接进入 `http://localhost:8000/ehr/new` 录入。

### 5. 上传病历照片

```bash
curl -X POST http://localhost:8000/api/ehr/records/upload \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -F "patient_id=p001" \
  -F "record_type=出院小结" \
  -F "files=@/path/to/discharge_summary.jpg"
```

支持扩展名：jpg、jpeg、png、webp、bmp、tif、tiff。

### 6. AI 护理建议

普通模式：

```bash
curl -X POST http://localhost:8000/api/nursing/decision \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"p001","symptom":"今天下午血压180/110，头痛头晕，手心出汗"}'
```

流式模式：

```bash
curl -N -X POST http://localhost:8000/api/nursing/decision/stream \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"p001","symptom":"餐前血糖3.2，手抖冒汗"}'
```

SSE 事件：

| 事件 | 说明 |
| --- | --- |
| `context` | 检索到的病史上下文。 |
| `evidence` | 结构化证据 + 决策记忆。 |
| `token` | 逐 token 生成内容。 |
| `done` | 完成，包含 `decision_id`。 |
| `error` | 错误信息。 |

### 7. 回填决策执行结果

```bash
curl -X PATCH http://localhost:8000/api/nursing/decisions/dec_xxxxx/outcome \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "outcome_status": "effective",
    "note": "复测血糖5.6，症状缓解",
    "recorded_by": "王护士"
  }'
```

`outcome_status` 可选：`effective`、`partial`、`ineffective`。

### 8. 生成护理任务卡

```bash
curl -X POST http://localhost:8000/api/nursing/task-card \
  -H "X-Auth-Token: NURSE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"p001","symptom":"饭后胸闷，出冷汗，需要观察"}'
```

任务卡会生成护理建议、可打卡任务、复测计划、禁止事项和 SBAR 交接信息。

### 9. 查看审计日志

```bash
curl "http://localhost:8000/api/ehr/audit?patient_id=p001&limit=20" \
  -H "X-Auth-Token: YOUR_ADMIN_TOKEN"
```

### 网页端工作流

```text
早班交接 -> 打开护工端 -> 查看老人列表和昨日未完成事项
  -> 发现异常 -> 输入症状 -> 生成护理建议或任务卡
  -> 按任务卡测量、观察、通知护士、逐条打卡
  -> 复测后回填有效/部分有效/无效
  -> 下次同一老人类似症状时，AI 自动参考历史处理结果
```

## 🔌 API 参考

所有接口都在 `/api/*` 下，鉴权开启时请求头需要：

```http
X-Auth-Token: <AUTH_TOKEN 或用户 API Key>
```

### 认证管理 `/api/auth/*`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/auth/me` | 当前身份、权限和鉴权模式。 |
| `GET` | `/api/auth/users` | 列出用户。 |
| `POST` | `/api/auth/users` | 创建用户。 |
| `DELETE` | `/api/auth/users/{user_id}` | 停用用户。 |
| `POST` | `/api/auth/tokens` | 为用户签发 API Key。 |
| `GET` | `/api/auth/tokens` | 查看 Token 列表，不含明文。 |
| `DELETE` | `/api/auth/tokens/{key_id}` | 吊销 Token。 |
| `GET` | `/api/auth/roles` | 查看角色。 |
| `POST` | `/api/auth/roles` | 创建自定义角色。 |
| `GET` | `/api/auth/permissions` | 查看权限点清单。 |

### 档案管理 `/api/ehr/*`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/ehr/patients` | 新增老人档案。 |
| `GET` | `/api/ehr/patients` | 列出老人档案。 |
| `GET` | `/api/ehr/patients/{patient_id}` | 查询单个档案。 |
| `PUT` | `/api/ehr/patients/{patient_id}` | 修改档案。 |
| `DELETE` | `/api/ehr/patients/{patient_id}` | 删除档案。 |
| `POST` | `/api/ehr/records/upload` | 上传病历照片并 OCR。 |
| `GET` | `/api/ehr/records/{patient_id}` | 查询某老人全部病历照片。 |
| `DELETE` | `/api/ehr/records/{doc_id}` | 删除单份病历。 |
| `GET` | `/api/ehr/audit` | 查询审计日志。 |

### 护理决策 `/api/nursing/*`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/nursing/patient/{patient_id}` | 护工端患者摘要。 |
| `POST` | `/api/nursing/decision` | RAG 推理。 |
| `POST` | `/api/nursing/decision/stream` | SSE 流式 RAG 推理。 |
| `POST` | `/api/nursing/optimize_prompt` | 口语症状优化。 |
| `GET` | `/api/nursing/decisions` | 查询决策记忆。 |
| `GET` | `/api/nursing/decisions/{decision_id}` | 查询单条决策。 |
| `PATCH` | `/api/nursing/decisions/{decision_id}/outcome` | 回填执行结果。 |
| `POST` | `/api/nursing/task-card` | 生成护理任务卡。 |
| `GET` | `/api/nursing/events` | 查询护理事件。 |
| `PATCH` | `/api/nursing/events/{event_id}/tasks/{task_id}/complete` | 更新任务执行状态。 |
| `GET` | `/api/nursing/events/{event_id}/sbar` | 获取 SBAR 交接单。 |

### 运营管理

| 模块 | 代表路径 |
| --- | --- |
| 床位 | `/api/beds`、`/api/beds/{bed_id}/assign`、`/api/beds/{bed_id}/release` |
| 护理等级 | `/api/care-levels`、`/api/care-levels/assign` |
| 交接班 | `/api/handovers`、`/api/handovers/{handover_id}/acknowledge` |
| 异常事件 | `/api/incidents`、`/api/incidents/stats` |
| 护理记录 | `/api/care-records`、`/api/care-records/patient/{patient_id}` |
| 入住流程 | `/api/admissions`、`/api/admissions/{id}/assess`、`/api/admissions/{id}/move-in` |
| 缴费 | `/api/billing/fee-standards`、`/api/billing/records`、`/api/billing/renew`、`/api/billing/alerts` |
| 支付 | `/api/payment/channels`、`/api/pay/wechat/native`、`/api/pay/wechat/query/{out_trade_no}` |
| PDF 导出 | `/api/export/patient/{patient_id}/pdf`、`/api/export/billing/receipt/{record_id}/pdf` |
| 备份 | `/api/backup/run`、`/api/backup/list`、`/api/backup/status` |

## 🧱 系统架构

```text
 管理端 index.html              护工端 nurse.html
        │                              │
        └──────────────┬───────────────┘
                       ▼
              FastAPI + Uvicorn
     /api/auth/* /api/ehr/* /api/nursing/*
     /api/beds/* /api/billing/* /api/backup/*
                       │
        ┌──────────────┼────────────────┬────────────────┐
        ▼              ▼                ▼                ▼
  Auth/RBAC       EHR + OCR        Nursing RAG       Billing/Ops
  UserStore       Uploads          DecisionMemory    CareStore
        │              │                │                │
        ▼              ▼                ▼                ▼
  SQLite WAL      Local files      ChromaDB           SQLite WAL
  local_auth      local_uploads    local_ehr_db       local_care
  local_audit                     local_events       local_billing
        │
        ▼
 PII 加密层 Fernet + 操作审计 + 冷备份
        │
        ▼
 Ollama 本地模型 或 OpenAI 兼容远程推理服务
```

### 技术栈

| 层 | 选型 | 用途 |
| --- | --- | --- |
| Web 框架 | FastAPI + Uvicorn | REST、SSE、静态托管、健康检查。 |
| 前端 | Vue 3 + Vite + TypeScript + Pinia | 管理端和护工端两个 SPA。 |
| 数据校验 | Pydantic v2 | 请求/响应 Schema。 |
| 向量库 | ChromaDB PersistentClient | 档案、病历、决策日志。 |
| 结构化存储 | SQLite WAL | 用户、审计、护理事件、缴费、床位等。 |
| Embedding | BAAI/bge-small-zh-v1.5 或哈希降级 | 中文语义检索。 |
| OCR | Tesseract，RapidOCR 可选增强 | 病历照片文字识别。 |
| LLM | Ollama 或 OpenAI 兼容接口 | 护理建议、任务卡、提示词优化。 |
| 加密 | cryptography Fernet | PII 字段透明加密。 |
| PDF | reportlab | 档案卡、收据、交接单、护理记录导出。 |
| 日志 | loguru | 启动、模型、检索、业务错误日志。 |

### 目录结构

```text
.
├── app/
│   ├── core/config.py              # 环境变量、路径、模型名、Prompt 模板
│   ├── middleware/auth.py          # 鉴权与读取审计中间件
│   ├── models/                     # Pydantic Schema
│   ├── routers/                    # /api/* 业务路由
│   └── services/                   # LLM、OCR、检索、审计、备份、PDF、存储
├── data/protocols.yaml             # 护理协议模板
├── frontend/                       # Vue 3 多入口 SPA
│   ├── index.html                  # 管理端入口
│   ├── nurse.html                  # 护工端入口
│   └── src/
├── static/design/                  # 设计资源
├── tests/                          # pytest 测试
├── scripts/                        # setup、run、diagnose、backup、Windows/macOS 向导
├── 配置向导.command                 # macOS 图形化配置/部署入口
├── 启动智护银伴.command             # macOS 双击启动器
├── main.py                         # FastAPI 应用入口
├── requirements.txt                # 完整依赖，含 torch/OCR
├── requirements-api.txt            # 轻量依赖，不含 torch/OCR 图片依赖
├── Dockerfile
├── docker-compose.yml
├── docker-compose.gpu.yml
└── .env.example
```

### 本机数据目录

```text
local_ehr_db/              # ChromaDB 向量库
local_ehr_uploads/         # 病历原图与 OCR 文件
local_auth/users.db        # 用户 + API Key
local_audit_log/audit.db   # 操作审计
local_care/care.db         # 床位、交接、事件、护理记录、入住
local_billing/billing.db   # 缴费、收费标准、提醒
local_nursing_events/      # 护理任务卡与执行事件
local_backups/             # 冷备份
local_sync_outbox/         # 边缘同步 outbox
```

## 🏭 生产部署

### 方式 0：一键部署向导

推荐先跑向导。它会处理密钥、Docker、模型、`.env` 和健康检查。

```bash
./scripts/setup.sh       # Linux / macOS
```

```powershell
.\scripts\setup.ps1      # Windows
```

### 方式 A：Docker Compose 手动部署

```bash
cp .env.example .env

export AUTH_TOKEN="$(openssl rand -hex 32)"
export PII_KEY="$(python3 -c 'import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

python3 - <<'PY'
from pathlib import Path
import os, re
p = Path(".env")
txt = p.read_text() if p.exists() else ""
def upsert(text, key, value):
    pat = re.compile(rf"^{key}=.*$", re.M)
    return pat.sub(f"{key}={value}", text) if pat.search(text) else text.rstrip() + f"\n{key}={value}\n"
txt = upsert(txt, "AUTH_TOKEN", os.environ["AUTH_TOKEN"])
txt = upsert(txt, "PII_ENCRYPTION_KEY", os.environ["PII_KEY"])
p.write_text(txt)
PY

docker compose --profile ollama up -d --build
docker compose ps
```

常用运维命令：

```bash
docker compose logs -f app
docker compose logs -f model-puller
docker compose restart app
docker compose down       # 停服务，保留数据卷
docker compose down -v    # 危险：连数据卷一起删除
```

### 方式 B：API-only 轻量部署

适合无 GPU、受限网络、只接远程模型：

```env
LLM_PROVIDER=openai
OPENAI_API_BASE=http://your-llm-host:8000/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
EMBEDDING_DISABLED=true
PY_REQUIREMENTS=requirements-api.txt
```

```bash
docker compose up -d --build
```

### 方式 C：裸机开发/部署

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-api.txt

cp .env.example .env
./scripts/run-api-local.sh
```

完整 RAG/OCR：

```bash
pip install -r requirements.txt
./scripts/run.sh
```

`scripts/run.sh` 会检查本地 Ollama 是否运行；如果用 OpenAI 兼容接口，可直接：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 前端开发

项目主线使用 `npm` 和 `frontend/package-lock.json`：

```bash
cd frontend
npm install
npm run dev
npm run typecheck
npm run test
npm run build
```

生产后端只会从 `static/dist/` 提供新版前端。若页面提示“新版前端未构建”，运行：

```bash
cd frontend && npm run build
```

### 备份

生产环境至少备份：

```text
local_ehr_db/
local_ehr_uploads/
local_auth/
local_audit_log/
local_care/
local_billing/
local_nursing_events/
```

冷备份功能可通过 `BACKUP_ENABLED=true`、`BACKUP_ENCRYPTION_KEY`、`BACKUP_DIR` 启用。

## 🛠️ 常见部署问题

| 现象 | 常见原因 | 解决 |
| --- | --- | --- |
| 页面返回“新版前端未构建” | `static/dist/` 不存在。 | 运行 `cd frontend && npm run build`，或 Docker 重新 `up -d --build`。 |
| 登录失败 | Token 错误或浏览器保存了旧 Token。 | 重新粘贴 `.env` 中的 `AUTH_TOKEN`，必要时清空 localStorage。 |
| API 返回 401 | 请求头缺少 `X-Auth-Token`。 | curl、脚本或前端登录都要配置 Token。 |
| `/health` 中 `auth_mode=disabled` | 没有配置 `AUTH_TOKEN` 且用户库为空。 | 生产环境必须补齐 `AUTH_TOKEN` 并重启。 |
| `/health` 中 `rag_available=false` | embedding 未加载或降级启动。 | 演示可接受；需要语义检索时检查模型路径、torch、缓存权限和网络。 |
| AI 接口 503 | LLM 服务不可达。 | Ollama 模式检查 `ollama list` 和模型名；OpenAI 模式检查 base/model/key。 |
| OpenAI 兼容接口 404 | `OPENAI_API_BASE` 写成完整接口路径。 | 改为 `http://host:8000/v1` 这种根地址。 |
| Docker 首次启动很慢 | 正在拉模型或构建依赖。 | 看 `docker compose logs -f model-puller app`。 |
| Docker app 反复重启 | `.env` 缺变量或构建依赖失败。 | 看 `docker compose logs app`。 |
| OCR 不生效 | 使用 API-only 依赖或缺 Tesseract。 | 使用 `requirements.txt` 并安装 Tesseract 中文语言包。 |
| 上传文件失败 | 文件太大或扩展名不允许。 | 检查 `MAX_UPLOAD_SIZE_MB`，使用支持的图片扩展名。 |
| 数据库权限错误 | `local_*` 目录不可写。 | 检查运行用户、挂载卷权限和磁盘空间。 |
| 局域网访问不到 | 监听地址、防火墙或端口映射问题。 | 设置 `HOST=0.0.0.0`，开放 8000 入站，用部署机内网 IP 访问。 |
| Docker Hub 慢 | 镜像拉取慢。 | 配置 Docker registry mirror 后重启 Docker。 |
| HuggingFace 慢 | 模型下载慢。 | 使用 `setup-cn.sh` 或设置 `HF_ENDPOINT=https://hf-mirror.com`。 |

## 🧪 测试

后端：

```bash
pytest
```

前端：

```bash
cd frontend
npm run typecheck
npm run test
npm run build
```

文档或部署脚本变更至少建议跑：

```bash
git diff --check
```

## 🗺️ 路线图

- [x] 本地 EHR 档案 CRUD 与病历上传。
- [x] RAG 护理建议、SSE 流式输出、决策记忆和结果回填。
- [x] 管理端与护工端双入口 SPA。
- [x] 床位、交接班、异常事件、护理记录、入住和缴费模块。
- [x] 用户、角色、API Key、PII 加密和审计日志。
- [x] Docker Compose、本地部署脚本、Windows 双击启动器。
- [ ] 备份/恢复图形化操作。
- [ ] 更完整的院内多终端权限体验。
- [ ] 对接更多本地模型和机构内部知识库。
- [ ] 商业交付安装包、自动升级和回滚。

## ⚠️ 医疗与安全边界

- AI 建议只用于辅助护理判断，不替代医生诊断、医嘱、处方或急救流程。
- 使用云端或远程 LLM 时，请自行确认数据合规、脱敏策略和网络边界。
- `.env`、`local_*` 数据目录、上传病历、备份文件和模型权重都不应提交到 Git。
- `PII_ENCRYPTION_KEY` 和 `BACKUP_ENCRYPTION_KEY` 丢失后，已加密数据或备份可能无法恢复。
- 不建议把 8000 端口直接暴露到公网；生产环境请放在内网、VPN 或受控反向代理之后。

## License

[PolyForm Noncommercial License 1.0.0](./LICENSE)。本仓库仅允许非商业用途。商业授权请联系：jiahuacaogoodman@gmail.com。

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)
