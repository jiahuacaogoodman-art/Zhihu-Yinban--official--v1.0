# Official v1.0 目标架构

## 1. 架构定位

Official v1.0 采用 **模块化单体 + 本地优先部署 + 轻云端管控** 架构。

不在 v1.0 阶段拆微服务，原因：

- 目标客户多为中小型养老机构；
- 部署环境不可控；
- 本地化交付优先于分布式扩展；
- SQLite/PostgreSQL + 模块化边界足够支撑 v1.0；
- 降低维护、升级、备份、排障复杂度。

---

## 2. 总体架构

```text
┌────────────────────────────────────────────┐
│ UI Layer                                   │
│ web-admin / web-caregiver / ops-console    │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│ API Layer                                  │
│ FastAPI routers / schemas / auth / errors  │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│ Domain Layer                               │
│ residents / admissions / beds / care       │
│ incidents / handovers / billing / family   │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│ Application Services                       │
│ workflow / task generation / review / AI    │
│ audit / backup / health / migration         │
└────────────────────────────────────────────┘
                    │
┌────────────────────────────────────────────┐
│ Infrastructure Layer                       │
│ SQLite/PostgreSQL / ChromaDB / file store  │
│ OCR / LLM provider / local storage         │
└────────────────────────────────────────────┘
```

---

## 3. 后端目标目录

```text
apps/backend/app/
  main.py
  core/
    config.py
    logging.py
    errors.py
    security.py
  domains/
    residents/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    admissions/
    beds/
    care_plans/
    care_tasks/
    care_records/
    incidents/
    handovers/
    billing/
    family/
    documents/
    ai/
    auth/
    audit/
    system/
  infrastructure/
    db/
      connection.py
      migrations.py
      sqlite.py
      postgres.py
    vector/
      chroma.py
      retriever.py
    storage/
      local_files.py
    ocr/
      local_ocr.py
    llm/
      provider.py
      ollama.py
      openai_compatible.py
    backup/
      backup_service.py
      restore_service.py
```

---

## 4. 数据存储

### 4.1 结构化业务库

默认 SQLite WAL，后续可选 PostgreSQL。

用于：

- 老人；
- 家属；
- 员工；
- 入住；
- 床位；
- 护理计划；
- 护理任务；
- 护理记录；
- 异常事件；
- 交接班；
- 合同费用；
- 权限角色；
- 审计事件。

### 4.2 文档库

本地文件系统。

用于：

- 病历照片；
- OCR 文本；
- 合同扫描件；
- 评估表；
- 家属授权文件；
- 协议模板；
- 备份包。

### 4.3 向量库

默认 ChromaDB。

用于：

- 病历 OCR 文本向量；
- 老人摘要向量；
- 护理事件向量；
- 交接记录向量；
- 护理协议向量；
- 护理记忆向量。

---

## 5. AI 架构

AI 层不直接写业务最终状态，所有 AI 输出进入草稿态。

```text
Business Context
↓
Retrieval / Protocol Match
↓
LLM Draft
↓
Schema Validation
↓
Risk Boundary Check
↓
Human Review if required
↓
Business Record Archive
```

### 5.1 Provider

支持：

- Ollama 本地模型；
- OpenAI-compatible API；
- vLLM/TGI/SGLang；
- 云端 API 作为可选配置。

### 5.2 AI 输出必须保存

- prompt version；
- model name；
- provider；
- protocol version；
- retrieved evidence；
- output JSON；
- validation result；
- reviewer；
- final accepted content。

---

## 6. 权限与审计

### 6.1 默认岗位

- 系统管理员；
- 院长；
- 护士长；
- 责任护士；
- 护工；
- 财务/行政；
- 只读督导；
- 运维人员。

### 6.2 审计范围

必须记录：

- 登录/Token 使用；
- 老人档案读写；
- 病历照片访问；
- PII 字段变更；
- 护理任务执行；
- 异常事件处置；
- 护士审核；
- 交接确认；
- 备份恢复；
- 系统升级。

---

## 7. 部署架构

### 7.1 单机版

```text
Windows PC / Mac mini / 小型服务器
├─ backend
├─ web static
├─ SQLite
├─ ChromaDB
├─ local files
└─ Ollama optional
```

### 7.2 局域网版

```text
院内服务器
├─ backend: 0.0.0.0:8000
├─ admin/caregiver web
├─ local DB / file storage
└─ LAN clients via browser/tablet
```

### 7.3 云管控本地运行版

```text
Local Site
├─ business data local only
├─ AI local or configured provider
└─ sync diagnostics/license/version metadata only

Cloud Control Plane
├─ license
├─ version
├─ protocol template
├─ update package
└─ support ticket
```

---

## 8. 健康检查

`/api/system/status` 应返回：

- app version；
- auth mode；
- DB writable；
- vector DB writable；
- upload directory writable；
- OCR available；
- LLM available；
- embedding available；
- disk free；
- latest backup；
- schema version；
- protocol version；
- uptime。
