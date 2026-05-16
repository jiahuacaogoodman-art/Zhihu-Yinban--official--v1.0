# 智护银伴 Official v1.0

> Local-first Care Operating System for nursing homes.  
> 面向养老机构的本地优先院务与护理操作系统。

本仓库是 `智护银伴` 的 official v1.0 产品化仓库，用于承接原型仓库中已经验证过的本地护理 AI、老人档案、入住流程、床位护理、交接班、异常事件、审计与部署能力，并在此基础上扩充为完整的养老院管理系统产品。

## 1. 产品定位

智护银伴 official v1.0 不再被定义为单一的 AI Demo，而是一个面向中小型养老机构的本地优先产品：

- 院内数据本地存储，不以云端 SaaS 作为运行前提；
- 局域网可用，断网可完成核心业务；
- 云端只承担授权、版本、模板、远程诊断与升级管理；
- AI 只作为护理辅助层，不替代护士、医生或机构管理决策；
- 以老人全生命周期、护理执行闭环、异常事件追溯、交接班协同为核心。

## 2. v1.0 产品边界

Official v1.0 的目标不是一次性替代所有大型养老院 SaaS，而是先形成可独立交付的本地院内系统底座：

1. 院务主数据中心：老人、家属、员工、床位、房间、护理等级、服务项目。
2. 入住流转中心：咨询、评估、签约、缴费、床位分配、入住、转床、转级、离院。
3. 护理执行中心：护理计划、每日任务、护工打卡、生命体征、护理记录、护士审核。
4. 风险事件中心：跌倒、发热、低血糖、误吸、胸闷、走失、压疮等事件闭环。
5. 交接协同中心：SBAR 交接、班次交接、未完成任务流转、接班确认。
6. 本地 AI 辅助中心：OCR、RAG、风险摘要、任务卡草稿、SBAR 草稿、决策记忆。
7. 运维交付中心：本地启动器、服务控制台、备份恢复、健康诊断、离线升级、轻 SaaS 管控。

## 3. 与原型仓库的关系

原型仓库保持不变，本仓库作为 official v1.0 新仓库承接产品化重构。

原型仓库中可迁移的能力包括：

- FastAPI 后端入口与模块化路由；
- EHR 老人档案、本地 OCR、ChromaDB 向量入库；
- 护理 RAG、SSE 流式输出、AI 任务卡、SBAR、决策记忆；
- 入住流程、床位、护理等级、护理记录、交接班、异常事件；
- UserStore、API Key、RBAC 权限、审计日志、PII 加密；
- Docker Compose、Windows 启动器、诊断脚本、部署文档。

迁移策略见：[`docs/MIGRATION_FROM_PROTOTYPE.md`](docs/MIGRATION_FROM_PROTOTYPE.md)。

## 4. 目录规划

```text
apps/
  backend/             # FastAPI official v1.0 后端
  web-admin/           # 护士站/院长端管理后台
  web-caregiver/       # 护工端移动/平板工作台
  ops-console/         # 本地运维控制台
packages/
  care-domain/         # 护理、入住、床位、交接等领域模型
  local-ai/            # OCR / RAG / LLM provider / protocol engine
  shared-ui/           # 通用 UI 组件与设计系统
  deployment/          # 安装、升级、备份、诊断脚本
docs/
  architecture/        # 架构设计
  product/             # 产品方案
  migration/           # 从原型迁移到 official v1.0
```

## 5. 当前仓库状态

本仓库目前处于 official v1.0 初始化阶段，已经建立产品级文档骨架。下一步应按迁移清单逐步从原型仓库迁入代码，并在迁入过程中完成领域重构、数据模型统一、前端工作台重构和交付体系补齐。

## 6. 核心原则

- 原型仓库不动；
- official v1.0 只承接经过筛选和重构后的能力；
- 先业务闭环，后 AI 增强；
- 先本地可交付，后云端轻管控；
- AI 输出必须可审计、可解释、可人工复核；
- 数据备份、恢复、升级、回滚是产品功能，不是运维附属品。

## 7. 关键文档

- [`docs/PRODUCT_BLUEPRINT.md`](docs/PRODUCT_BLUEPRINT.md)：完整产品版图。
- [`docs/CARE_OS_MODULES.md`](docs/CARE_OS_MODULES.md)：养老院管理系统与本地护理 AI 的模块集成方案。
- [`docs/MIGRATION_FROM_PROTOTYPE.md`](docs/MIGRATION_FROM_PROTOTYPE.md)：从原型仓库迁移到 official v1.0 的具体清单。
- [`docs/ROADMAP_V1.md`](docs/ROADMAP_V1.md)：v1.0 产品开发路线图。
