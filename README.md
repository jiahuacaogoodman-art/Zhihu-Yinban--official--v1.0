# 智护银伴 · ZhiHu YinBan

面向养老院、护理院和长期照护机构的本地优先护理运营系统。它不是一个“聊天机器人套壳”，而是一套围绕真实照护流程构建的内网应用：老人档案、病历上传、床位、交接班、异常事件、护理记录、缴费、审计和 AI 护理建议都围绕同一份本地数据运转。

> AI 护理建议只用于辅助初步判断、任务拆解和交接记录，不替代医生诊断、医嘱、处方或急救流程。任何危急症状都应立即联系医生或启动院内应急预案。

[English](./README.en.md) · [License](./LICENSE)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6-3C1F85)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue)

## 为什么做

养老照护现场最难的不是“有没有 AI”，而是数据、流程和责任经常断在不同地方：

| 现场需求 | 常见问题 | 智护银伴的处理方式 |
| --- | --- | --- |
| 老人信息要随手可查 | 纸质档案、照片、Excel 和口头交接分散，护工临场不知道病史和禁忌。 | 建立本地 EHR 档案、病历上传、OCR 文本和患者维度检索。 |
| 护理建议要可追溯 | 单次问答没有证据来源，也不知道上次类似事件最后有没有效果。 | RAG 检索患者档案和病历，输出证据引用，并把 AI 决策和执行结果写回记忆。 |
| 一线执行要落到任务 | 护理建议太长，交到护工手里仍然要靠经验拆动作。 | 生成护理任务卡、复测观察、禁忌事项和 SBAR 交接信息。 |
| 管理者要看到流程闭环 | 床位、交接、异常、护理记录、缴费和审计分散在不同工具里。 | 管理端统一处理床位、护理等级、交接班、事件、记录、缴费、用户和审计。 |
| 院内数据要守住边界 | 病历、身份证、联系人、支付配置等数据不能随便上云。 | 默认本地持久化，支持 Fernet PII 加密、API Key 鉴权、操作审计和冷备份。 |
| 试点部署要能跑起来 | 模型大、网络慢、GPU 不确定、Windows 用户不会命令行。 | 提供 Docker Compose、本地 API-only、Windows 双击启动器和降级模式。 |

## 项目定位

智护银伴适合三类场景：

| 场景 | 目标 |
| --- | --- |
| 养老院内网试点 | 在一台院内服务器或 Windows 电脑上运行，先把档案、床位、记录和 AI 建议跑起来。 |
| 护理流程原型 | 验证“患者上下文 + 任务卡 + 交接 + 审计”的闭环，而不是只展示一次性聊天。 |
| 本地优先 AI 应用样板 | 参考 FastAPI、Vue、多入口 SPA、ChromaDB、SQLite、Ollama/OpenAI 兼容后端的组合方式。 |

它暂时不追求成为医院 HIS/EMR 的完整替代品，也不直接承担医疗诊断责任。它更像是养老照护现场的“数据底座 + 任务工作台 + AI 辅助层”。

## 功能地图

| 模块 | 能力 |
| --- | --- |
| 患者档案 | 录入、检索、编辑、删除老人基本档案，支持 `/ehr/new` 独立录入页和档案 PDF 导出。 |
| 病历上传 | 上传图片病历，文件保存在本地磁盘，OCR 文本写入本地向量库供检索使用。 |
| AI 护理建议 | 基于患者档案、病历、护理决策记忆做 RAG 推理，支持 SSE 流式输出、证据引用和结果回填。 |
| 护理任务卡 | 将症状和建议拆成可执行任务、复测观察、禁忌事项和 SBAR 交接信息。 |
| 护理运营 | 床位、护理等级、交接班、异常事件、护理记录等日常业务留痕。 |
| 入住与缴费 | 入住申请、评估、合同、缴费记录、续费、到期提醒、收费标准和缴费收据 PDF。 |
| 支付配置 | 微信支付接口、支付渠道配置和模拟模式，方便先跑通业务流程再接生产商户。 |
| 用户与权限 | `AUTH_TOKEN` bootstrap 管理员、用户/API Key、角色和权限点管理。 |
| 安全与审计 | PII 字段 Fernet 加密、写操作审计、病历预览审计、冷备份和可选边缘同步。 |

## 技术路线

### 1. 本地优先，而不是云端优先

核心业务数据默认落在本机或院内服务器：

| 数据 | 默认位置 | 说明 |
| --- | --- | --- |
| 患者档案与 OCR 文本向量 | `local_ehr_db/` | ChromaDB 本地持久化。 |
| 病历原图与文件内容 | `local_ehr_uploads/` | 上传文件保存在本地磁盘，按 URL 受鉴权访问。 |
| 床位、交接、事件、护理记录、入住 | `local_care/` | SQLite WAL。 |
| 缴费与收费标准 | `local_billing/` | SQLite WAL。 |
| 用户、角色、API Key | `local_auth/` | Token 只保存 hash 和前缀。 |
| 操作审计 | `local_audit_log/` | 记录写操作、病历读取和敏感导出。 |
| 护理任务事件 | `local_nursing_events/` | AI 任务卡、执行状态、观察记录和归档。 |
| 冷备份与同步缓存 | `local_backups/`、`local_sync_outbox/` | 可选启用。 |

这些目录可能包含病历、Token、审计和业务数据，不应提交到 Git，也不应直接暴露到公网文件服务。

### 2. RAG 护理建议，而不是裸模型问答

护理建议接口不是把症状直接丢给模型，而是走闭环链路：

```text
患者症状
  -> 按 patient_id 取档案、病历 OCR、历史护理事件
  -> 检索证据与决策记忆
  -> 构造带证据编号的护理提示词
  -> Ollama 或 OpenAI 兼容 LLM 推理
  -> SSE 流式返回建议
  -> 写入决策记忆
  -> 护理人员回填执行结果
  -> 下一次类似事件可被检索引用
```

这样做的目标是让 AI 输出更贴近当前老人，而不是给出脱离病史的泛泛建议。降级模式下，系统仍可启动并处理基础业务；只是语义检索质量会下降。

### 3. 两个前端入口，服务两类用户

| 入口 | 文件 | 主要用户 | 地址 |
| --- | --- | --- | --- |
| 管理端 SPA | `frontend/index.html` -> `src/main.ts` | 院长、护士长、管理员 | `http://127.0.0.1:8000/` |
| 护工端 SPA | `frontend/nurse.html` -> `src/nurse-main.ts` | 一线护工、平板巡房 | `http://127.0.0.1:8000/nurse` |

管理端关注全流程管理，护工端关注患者列表、患者详情、症状输入、任务卡和执行打卡。两个入口共享同一套 API、鉴权和本地数据。

### 4. 部署分层：从演示到生产

项目提供四条部署路线：

| 路线 | 适合谁 | 特点 |
| --- | --- | --- |
| Docker + 本地 Ollama | 想要模型也在本地的部署 | 数据和模型都在院内；首次会下载较大模型权重。 |
| Docker + OpenAI 兼容 API | 有远程 GPU 或云模型的部署 | 应用本地运行，LLM 请求发往配置的兼容接口。 |
| API-only 本地开发 | 无 GPU、网络受限、只想快速跑业务 | 使用 `requirements-api.txt`，可禁用 embedding 模型加载。 |
| Windows 双击启动 | 非开发者试点 | `.bat` 和 PowerShell 向导生成配置、安装依赖、启动服务。 |

### 5. 可降级启动，避免部署死在模型上

现实部署里最容易失败的是模型下载、torch 安装、缓存权限和 GPU 环境。项目提供两个关键开关：

| 变量 | 作用 |
| --- | --- |
| `EMBEDDING_DISABLED=true` | 完全跳过 sentence-transformers/torch，不下载也不加载 embedding 模型。 |
| `EMBEDDING_ALLOW_DEGRADED=true` | embedding 加载失败时允许系统启动，基础业务和普通 LLM 调用仍可用。 |

这意味着你可以先把业务流程、前端、鉴权、档案、缴费和任务卡跑起来，再逐步补齐高质量语义检索。

## 访问入口

后端默认监听 `http://127.0.0.1:8000` 或容器内的 `0.0.0.0:8000`。

| 页面 | 地址 | 说明 |
| --- | --- | --- |
| 管理端 | `http://127.0.0.1:8000/` | 登录后默认进入床位管理，侧边栏可进入所有管理模块。 |
| 登录页 | `http://127.0.0.1:8000/login` | 使用管理员 Token 或已签发的用户 API Key 登录。 |
| AI 护理建议 | `http://127.0.0.1:8000/nursing-decision` | 患者选择、症状输入、流式建议、执行结果回填。 |
| 患者档案 | `http://127.0.0.1:8000/ehr` | 档案列表、检索、详情、编辑和导出。 |
| 录入档案 | `http://127.0.0.1:8000/ehr/new` | 独立档案录入页面。 |
| 病历上传 | `http://127.0.0.1:8000/ehr/upload` | 图片上传、本地 OCR、病历记录管理。 |
| 护工端 | `http://127.0.0.1:8000/nurse` | 面向一线护工的移动端优先工作台。 |
| 健康检查 | `http://127.0.0.1:8000/health` | 返回鉴权、RAG、加密和前端构建状态。 |

业务 API 统一在 `/api/*` 下。生产安全考虑下，当前后端不暴露 Swagger `/docs` 和 ReDoc `/redoc` 页面。

## 部署路线怎么选

| 你的情况 | 推荐路线 |
| --- | --- |
| 只想最快看系统页面和业务流程 | Docker + OpenAI 兼容 API，或 Windows 双击启动。 |
| 没有 GPU，不想装 PyTorch | `requirements-api.txt` + `EMBEDDING_DISABLED=true`。 |
| 网络慢，HuggingFace 下载不稳定 | 先用 API-only 路线；后续用 `EMBEDDING_MODEL_LOCAL_PATH` 指向已下载模型。 |
| 希望模型也不出院 | Docker Compose 启用 `--profile ollama`。 |
| 有 NVIDIA GPU | 叠加 `docker-compose.gpu.yml`。 |
| 交给非开发者试点 | 使用 `启动智护银伴.bat` 和 `配置向导.bat`。 |
| 准备生产内网部署 | Docker Compose + 强 Token + PII 加密 + 备份 + 内网访问控制。 |

## 快速部署：Docker Compose

推荐使用 Docker Compose 进行演示、试点和内网部署。

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
cp .env.example .env
```

生成管理员 Token 和 PII 加密密钥：

```bash
AUTH_TOKEN="$(openssl rand -hex 32)"
PII_ENCRYPTION_KEY="$(python3 -c 'import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
printf 'AUTH_TOKEN=%s\nPII_ENCRYPTION_KEY=%s\n' "$AUTH_TOKEN" "$PII_ENCRYPTION_KEY"
```

把上面输出写入 `.env`。生产环境不要使用短密码、默认值或示例值。

### 方案 A：本地 Ollama

适合希望模型和数据都在本机或院内服务器运行的部署。首次启动会下载模型权重，默认 Q4_K_M 约 4.8 GB。

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL_NAME=hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M
EMBEDDING_ALLOW_DEGRADED=true
```

```bash
docker compose --profile ollama up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

有 NVIDIA GPU 且已安装 nvidia-container-toolkit 时，可叠加 GPU 配置：

```bash
docker compose --profile ollama \
  -f docker-compose.yml \
  -f docker-compose.gpu.yml \
  up -d --build
```

### 方案 B：OpenAI 兼容远程 API

适合使用 vLLM、TGI、SGLang、DeepSeek、智谱、Qwen 或其他 OpenAI 兼容服务的部署。受限网络或不想安装 PyTorch 时，建议同时使用轻量依赖和禁用 embedding 模型加载。

```env
LLM_PROVIDER=openai
OPENAI_API_BASE=http://your-llm-host:8000/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
OPENAI_API_KEY=
EMBEDDING_DISABLED=true
PY_REQUIREMENTS=requirements-api.txt
```

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

`OPENAI_API_BASE` 必须是兼容服务根地址，例如 `http://host:8000/v1`，不要写成 `/chat/completions` 完整路径。

## 本地开发

### 后端：轻量 API-only

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-api.txt

cp .env.example .env
# 编辑 .env：设置 AUTH_TOKEN、PII_ENCRYPTION_KEY、LLM_PROVIDER=openai、
# OPENAI_API_BASE、OPENAI_MODEL、EMBEDDING_DISABLED=true

./scripts/run-api-local.sh
```

### 后端：完整 RAG/OCR

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 该脚本会检查本地 Ollama 是否运行；OCR 需要系统 tesseract 和中文语言包
./scripts/run.sh
```

如果完整依赖下仍想使用 OpenAI 兼容服务，可在 `.env` 中配置 `LLM_PROVIDER=openai` 后直接运行：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

后端启动后，健康检查应返回 `status: ok`：

```bash
curl http://127.0.0.1:8000/health
```

### 前端

项目主线使用 `npm` 和 `frontend/package-lock.json`。

```bash
cd frontend
npm install
npm run dev        # Vite dev server，/api、/uploads、/health 代理到本地 8000
npm run typecheck  # vue-tsc --noEmit
npm run test       # vitest run
npm run build      # 输出到 ../static/dist/
```

生产后端只会从 `static/dist/` 提供新版前端。如果访问页面时看到“新版前端未构建”，请先执行 `cd frontend && npm run build`。

## Windows 本地应用化启动

面向非开发者试点时，可直接使用仓库根目录的双击入口：

```text
启动智护银伴.bat
配置向导.bat
```

配置向导会生成 `AUTH_TOKEN`、`PII_ENCRYPTION_KEY`，填写 LLM 后端和端口，并把配置写入 `.env`。更多说明见 [docs/LOCAL_APP_DEPLOYMENT.md](./docs/LOCAL_APP_DEPLOYMENT.md)。

## 部署前检查清单

| 检查项 | 建议 |
| --- | --- |
| 端口 | 默认 8000，确认没有被占用；局域网访问时确认防火墙允许入站。 |
| Token | 生产必须设置长随机 `AUTH_TOKEN`，并妥善保存。 |
| PII 加密 | 生产必须设置 `PII_ENCRYPTION_KEY`，密钥丢失会导致已加密数据不可解密。 |
| 前端构建 | Docker 会自动构建；裸机部署需要先运行 `cd frontend && npm run build`。 |
| LLM 后端 | `ollama` 需要模型存在或可下载；`openai` 需要 base、model、key 配置正确。 |
| Embedding | 无 GPU、无 torch 或网络差时先设 `EMBEDDING_DISABLED=true`。 |
| OCR | 需要 `requirements.txt`、Tesseract 和中文语言包；API-only 依赖不包含 OCR 图片能力。 |
| 数据目录 | 确认 `local_*` 目录可写，并纳入备份策略。 |
| 备份 | 生产建议配置 `BACKUP_ENABLED=true`、`BACKUP_ENCRYPTION_KEY` 和外部 `BACKUP_DIR`。 |
| 外网暴露 | 不建议直接暴露 8000；使用内网、VPN 或受控反向代理。 |

## 关键环境变量

完整配置见 [.env.example](./.env.example)。生产环境至少应显式设置鉴权、加密、LLM 和备份相关变量。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AUTH_TOKEN` | 空 | bootstrap 管理员 Token。留空且用户库为空时会关闭鉴权，仅限开发测试。 |
| `PII_ENCRYPTION_KEY` | 空 | Fernet 密钥，用于加密姓名、身份证、联系方式、过敏史等敏感字段。生产必须设置。 |
| `PAYMENT_CONFIG_ENCRYPTION_KEY` | 复用 PII 密钥 | 支付渠道敏感配置加密密钥。 |
| `LLM_PROVIDER` | `ollama` | `ollama` 或 `openai`。`openai` 表示任何 OpenAI 兼容接口。 |
| `OLLAMA_API_URL` | `http://localhost:11434/api/generate` | Ollama generate 接口地址。Docker Compose 中默认指向 `http://ollama:11434/api/generate`。 |
| `OLLAMA_MODEL_NAME` | `huatuo_o1_7b` | Ollama 模型名或 HuggingFace GGUF tag。 |
| `OPENAI_API_BASE` | 空 | OpenAI 兼容服务根地址，不要带 `/chat/completions`。 |
| `OPENAI_MODEL` | 空 | 远程服务模型名。 |
| `OPENAI_API_KEY` | 空 | 云端 API 通常必填，自建服务可留空。 |
| `EMBEDDING_DISABLED` | `false` | `true` 时不加载 torch/sentence-transformers，使用哈希向量占位。 |
| `EMBEDDING_ALLOW_DEGRADED` | `true` | embedding 加载失败时是否允许降级启动。 |
| `EMBEDDING_MODEL_LOCAL_PATH` | 空 | 离线部署时可指向本地 embedding 模型目录。 |
| `PY_REQUIREMENTS` | `requirements.txt` | Docker 构建参数，可改成 `requirements-api.txt` 构建轻量镜像。 |
| `MAX_UPLOAD_SIZE_MB` | `15` | 单个病历图片最大上传大小。 |
| `BACKUP_ENABLED` | `false` | 是否启用每日冷备份调度。 |
| `BACKUP_ENCRYPTION_KEY` | 空 | AES-256-GCM 备份加密密钥。 |
| `BACKUP_DIR` | `local_backups/` | 备份目标目录，生产建议指向 NAS、USB 加密盘或其他院内安全存储。 |
| `SYNC_ENABLED` | `false` | 是否启用边缘同步守护进程。 |
| `WECHAT_PAY_*` | 空 | 微信支付商户配置。全部留空时使用模拟模式。 |

## API 模块

所有业务接口都带 `/api` 前缀，除微信支付回调外，鉴权开启时都需要请求头：

```http
X-Auth-Token: <AUTH_TOKEN 或用户 API Key>
```

| 模块 | 代表路径 |
| --- | --- |
| 认证与权限 | `/api/auth/me`、`/api/auth/users`、`/api/auth/tokens`、`/api/auth/roles`、`/api/auth/permissions` |
| 患者档案 | `/api/ehr/patients`、`/api/ehr/records/upload`、`/api/ehr/audit` |
| 护理决策 | `/api/nursing/decision`、`/api/nursing/decision/stream`、`/api/nursing/task-card`、`/api/nursing/decisions` |
| 护理事件 | `/api/nursing/events`、`/api/nursing/events/{event_id}/tasks/{task_id}/complete`、`/api/nursing/events/{event_id}/sbar` |
| 床位与等级 | `/api/beds`、`/api/care-levels` |
| 交接与记录 | `/api/handovers`、`/api/incidents`、`/api/care-records` |
| 入住流程 | `/api/admissions`、`/api/admissions/{id}/assess`、`/api/admissions/{id}/contract`、`/api/admissions/{id}/move-in` |
| 缴费 | `/api/billing/fee-standards`、`/api/billing/records`、`/api/billing/renew`、`/api/billing/overview`、`/api/billing/alerts` |
| 支付 | `/api/payment/channels`、`/api/pay/wechat/native`、`/api/pay/wechat/query/{out_trade_no}` |
| PDF 导出 | `/api/export/patient/{patient_id}/pdf`、`/api/export/billing/receipt/{record_id}/pdf`、`/api/export/handover/{handover_id}/pdf` |
| 备份 | `/api/backup/run`、`/api/backup/list`、`/api/backup/status` |

## 部署问题排查

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| 页面返回“新版前端未构建” | `static/dist/` 不存在。 | 运行 `cd frontend && npm run build`。Docker 部署则重新 `docker compose up -d --build`。 |
| 浏览器能打开但登录失败 | Token 错误或 localStorage 中保存了旧 Token。 | 重新粘贴 `.env` 中的 `AUTH_TOKEN`，必要时清空浏览器 localStorage。 |
| API 返回 401 | 请求头缺少 `X-Auth-Token`。 | 为 curl、脚本或前端登录配置正确 Token。 |
| `/health` 中 `auth_mode=disabled` | 没有配置 `AUTH_TOKEN` 且用户库为空。 | 生产环境必须补齐 `AUTH_TOKEN` 并重启。 |
| `/health` 中 `frontend_dist_exists=false` | 前端未构建或构建产物路径不对。 | 确认 `static/dist/index.html` 和 `static/dist/nurse.html` 存在。 |
| `/health` 中 `rag_available=false` | embedding 未加载、被禁用或降级启动。 | 演示可接受；需要语义检索时检查模型路径、缓存权限、torch 和网络。 |
| AI 接口 503 | LLM 服务不可达。 | Ollama 模式检查 `ollama list` 和模型名；OpenAI 模式检查 `OPENAI_API_BASE`、`OPENAI_MODEL`、`OPENAI_API_KEY`。 |
| OpenAI 兼容接口报 404 | `OPENAI_API_BASE` 写成了完整接口路径。 | 改为服务根地址，例如 `http://host:8000/v1`。 |
| Docker 首次启动很慢 | 正在下载 Ollama 模型或安装依赖。 | 查看 `docker compose logs -f model-puller app`。 |
| Docker app 反复重启 | `.env` 缺少必填变量或依赖构建失败。 | 先看 `docker compose logs app`，确认 `AUTH_TOKEN`、`PII_ENCRYPTION_KEY`、`PY_REQUIREMENTS`。 |
| OCR 不生效 | 使用了 API-only 依赖，或系统没有 Tesseract/中文语言包。 | 使用 `requirements.txt`，并安装 Tesseract 和 `chi_sim` 语言包。 |
| 上传文件失败 | 文件过大或扩展名不允许。 | 检查 `MAX_UPLOAD_SIZE_MB`，支持 jpg、jpeg、png、webp、bmp、tif、tiff。 |
| ChromaDB 或 SQLite 权限错误 | `local_*` 目录不可写。 | 检查运行用户、挂载卷权限和磁盘空间。 |
| 局域网其他电脑访问不到 | 监听地址、防火墙或端口映射问题。 | 使用 `HOST=0.0.0.0`，开放 8000 入站，并用部署机器内网 IP 访问。 |

## 质量验证

```bash
pytest
cd frontend
npm run typecheck
npm run test
npm run build
```

文档或部署脚本变更至少建议跑：

```bash
git diff --check
```

## 生产安全边界

- 本项目是本地优先系统，但可配置远程 OpenAI 兼容 LLM。若使用云端模型，请自行确认数据合规、脱敏和网络边界。
- `.env`、`local_*` 数据目录、上传病历、备份文件和模型权重都不应提交到 Git。
- `PII_ENCRYPTION_KEY` 和 `BACKUP_ENCRYPTION_KEY` 丢失后，已加密数据或备份可能无法恢复。
- 不建议把 8000 端口直接暴露到公网；生产环境请放在内网、VPN 或受控反向代理之后。
- AI 建议必须由具备资质的护理或医疗人员结合现场情况判断，不能自动执行给药、治疗或急救决策。

## License

[PolyForm Noncommercial License 1.0.0](./LICENSE)。本仓库仅允许非商业用途。商业授权请联系：jiahuacaogoodman@gmail.com。

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)