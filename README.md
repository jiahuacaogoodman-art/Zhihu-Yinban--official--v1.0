# 智护银伴 · ZhiHu YinBan

面向养老院和长期照护机构的本地优先护理运营系统。项目把老人档案、床位、交接班、异常事件、护理记录、缴费、审计和 AI 护理建议放在同一套内网应用里，方便一线护理人员、护士长和院方管理者围绕同一份数据协作。

> AI 护理建议只用于辅助初步判断和任务拆解，不替代医生诊断、医嘱或急救流程。任何危急症状都应立即联系医生或启动院内应急预案。

[English](./README.en.md) · [License](./LICENSE)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6-3C1F85)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue)

## 项目能做什么

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

## 系统结构

```text
frontend/                 Vue 3 + Vite 多入口 SPA
  index.html              管理端入口
  nurse.html              护工端入口
  src/
    views/                管理端页面
    nurse-views/          护工端页面
    api/                  HTTP client 与错误处理

app/                      FastAPI 应用模块
  routers/                /api/* 业务路由
  services/               ChromaDB、SQLite store、LLM、OCR、PDF、备份等
  middleware/             鉴权和审计中间件

main.py                   后端入口，挂载 API、静态资源、SPA fallback、健康检查
static/design/            前端设计资源
data/protocols.yaml       护理协议模板
scripts/                  部署、启动、诊断、Windows 向导脚本
tests/                    后端 pytest 测试
```

运行时数据默认保存在项目根目录的本地目录中：`local_ehr_db/`、`local_ehr_uploads/`、`local_care/`、`local_billing/`、`local_auth/`、`local_audit_log/`、`local_nursing_events/`、`local_backups/` 和 `local_sync_outbox/`。这些目录可能包含病历、Token、审计和业务数据，不应提交到 Git。

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

业务 API 统一在 `/api/*` 下，生产安全考虑下当前后端不暴露 Swagger `/docs` 和 ReDoc `/redoc` 页面。

## 快速部署：Docker Compose

推荐使用 Docker Compose 进行演示、试点和内网部署。首次本地 Ollama 模式会下载约 4.8 GB 的模型权重，请预留时间和磁盘空间。

```bash
git clone https://github.com/jiahuacaogoodman-art/Zhihu-Yinban--official--v1.0.git
cd Zhihu-Yinban--official--v1.0
cp .env.example .env
```

至少填写 `.env` 中的两个安全变量：

```bash
AUTH_TOKEN="$(openssl rand -hex 32)"
PII_ENCRYPTION_KEY="$(python3 -c 'import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
```

把上面生成的值写入 `.env` 后，选择一种 LLM 后端。

### 方案 A：本地 Ollama

适合希望模型和数据都在本机或院内服务器运行的部署。

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

`EMBEDDING_DISABLED=true` 会使用确定性哈希向量占位，应用能快速启动，但语义 RAG 召回质量会下降。需要完整语义检索时，请改回 `false` 并准备 `sentence-transformers` 依赖和 embedding 模型缓存。

## 本地开发

### 后端

轻量 API-only 开发方式：

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

完整本地 RAG/OCR 开发方式：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 该脚本会检查本地 Ollama 是否运行；OCR 需要系统 tesseract 和中文语言包
./scripts/run.sh
```

如果完整依赖下仍想使用 OpenAI 兼容服务，可在 `.env` 中配置 `LLM_PROVIDER=openai` 后直接运行 `uvicorn main:app --host 127.0.0.1 --port 8000`。

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

### 后端测试

```bash
pytest
```

常用验证组合：

```bash
pytest
cd frontend && npm run typecheck && npm run test && npm run build
```

## Windows 本地应用化启动

面向非开发者试点时，可直接使用仓库根目录的双击入口：

```text
启动智护银伴.bat
配置向导.bat
```

配置向导会生成 `AUTH_TOKEN`、`PII_ENCRYPTION_KEY`，填写 LLM 后端和端口，并把配置写入 `.env`。更多说明见 [docs/LOCAL_APP_DEPLOYMENT.md](./docs/LOCAL_APP_DEPLOYMENT.md)。

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

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 页面返回“新版前端未构建” | 运行 `cd frontend && npm run build`，确认 `static/dist/index.html` 和 `static/dist/nurse.html` 存在。 |
| API 返回 401 | 确认浏览器登录 Token 正确，或请求头带 `X-Auth-Token`。 |
| `/health` 中 `auth_mode=disabled` | 没有配置 `AUTH_TOKEN` 且用户库为空。生产环境必须补齐 Token。 |
| `/health` 中 `rag_available=false` | embedding 未加载或被禁用。演示可接受；需要语义 RAG 时检查模型、本地路径和缓存权限。 |
| AI 接口 503 或超时 | 检查 Ollama 是否运行、模型名是否存在，或检查 `OPENAI_API_BASE`、`OPENAI_MODEL` 和网络连通性。 |
| OCR 不生效 | `requirements-api.txt` 不包含 OCR 图片依赖；完整 OCR 需要 `requirements.txt`、Tesseract 和中文语言包。 |
| Docker 首次启动很慢 | 本地 Ollama profile 会下载模型权重，默认 Q4_K_M 约 4.8 GB。 |

## 安全边界

- 本项目是本地优先系统，但可配置远程 OpenAI 兼容 LLM。若使用云端模型，请自行确认数据合规和脱敏策略。
- `.env`、`local_*` 数据目录、上传病历、备份文件和模型权重都不应提交到 Git。
- `PII_ENCRYPTION_KEY` 和 `BACKUP_ENCRYPTION_KEY` 丢失后，已加密数据或备份可能无法恢复。
- 不建议把 8000 端口直接暴露到公网；生产环境请放在内网、VPN 或受控反向代理之后。

## License

[PolyForm Noncommercial License 1.0.0](./LICENSE)。本仓库仅允许非商业用途。商业授权请联系：jiahuacaogoodman@gmail.com。

Copyright (c) 2026 [jiahuaCao](https://github.com/jiahuacaogoodman-art)