# 从原型仓库迁移到 Official v1.0

本文档定义如何在不修改原型仓库的前提下，将 `Zhihu-Yinban` 中已经验证过的能力迁移到 `Zhihu-Yinban--official--v1.0`。

---

## 1. 迁移原则

1. 原型仓库保持不变。
2. Official v1.0 不做简单复制，而做产品化重构。
3. 迁移时优先保留业务能力，重构模块边界和命名体系。
4. 原型中的 `patient_id` 在新仓库逐步升级为 `resident_id`。
5. 原型中的 AI 功能进入 `local-ai` 辅助层，不再以“AI 决策”作为主业务入口。
6. 所有可运行代码迁入后必须配套测试、健康检查、备份恢复和部署说明。

---

## 2. 原型仓库能力盘点

### 2.1 直接迁移但需重构

| 原型能力 | Official v1.0 归属 | 迁移动作 |
|---|---|---|
| FastAPI 主入口 | apps/backend | 改为模块化 app factory |
| EHR 老人档案 | Resident Center | patient_id → resident_id，统一 profile doc_type |
| 病历照片上传 | Document Center | 保留本地文件存储，增加文档分类 |
| OCR 服务 | Local AI / Document Center | 保留 RapidOCR/Tesseract 链路，增加结构化抽取 |
| ChromaDB 向量库 | Local AI Retrieval | 保留，但从业务库解耦 |
| RAG 护理问答 | Local AI Assist | 改名为护理辅助，不叫决策系统 |
| AI 任务卡 | Incident / Care Task | 改为协议模板主导，AI 只生成草稿 |
| SBAR 生成 | Handover Center | 作为交接草稿能力保留 |
| 决策记忆 | Risk / AI Memory | 改名为事件记忆/护理记忆 |
| 入住流程 | Admission Center | 保留状态机，补前端看板 |
| 床位管理 | Bed Center | 扩展楼栋/楼层/房间 |
| 护理等级 | Care Level Center | 绑定护理计划和收费项目 |
| 护理记录 | Care Record Center | 扩展为每日护理流水 |
| 交接班 | Handover Center | 扩展为班次工作台 |
| 异常事件 | Incident Center | 扩展标准事件协议库 |
| UserStore/RBAC | Auth Center | 保留，补岗位角色模板 |
| 审计日志 | Audit Center | 保留，扩展全业务事件日志 |
| PII 加密 | Security Center | 保留，补密钥备份提示 |
| Docker/Windows 脚本 | Deployment Center | 保留，升级为服务控制台与安装包 |

---

## 3. 不直接迁移的内容

以下内容不应原样搬入 official v1.0：

1. 大量单文件 HTML 内联样式和脚本；
2. 依赖 CDN 的前端资源；
3. 直接 `from main import app_state` 的跨模块调用；
4. 以 `patient` 为核心命名的新业务接口；
5. AI prompt 直接决定高风险护理任务的逻辑；
6. 缺少版本号的护理协议；
7. 仅用于演示的 UI 动效；
8. 无迁移版本管理的 SQLite schema 变更方式。

---

## 4. 目标目录结构

```text
apps/backend/
  app/
    main.py
    core/
    domains/
      residents/
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
      vector/
      storage/
      llm/
      ocr/
      backup/

apps/web-admin/
apps/web-caregiver/
apps/ops-console/
packages/local-ai/
packages/deployment/
```

---

## 5. 第一批迁移清单

### P0：仓库地基

- [ ] 初始化 backend app factory；
- [ ] 初始化统一配置系统；
- [ ] 初始化统一日志；
- [ ] 初始化 SQLite 迁移版本表；
- [ ] 初始化健康检查接口；
- [ ] 初始化备份目录约定；
- [ ] 初始化 `.env.example`；
- [ ] 初始化 Docker Compose；
- [ ] 初始化 Windows 本地启动器。

### P1：主数据

- [ ] 迁移老人档案模型；
- [ ] 新增 resident_id；
- [ ] 兼容 patient_id；
- [ ] 迁移家属联系人；
- [ ] 迁移床位模型；
- [ ] 扩展楼栋/楼层/房间；
- [ ] 迁移护理等级。

### P2：入住流程

- [ ] 迁移 admissions；
- [ ] 保留状态机；
- [ ] 修复 doc_type 统一问题；
- [ ] 入住后创建 resident profile；
- [ ] 入住后生成初始护理计划；
- [ ] 离院释放床位；
- [ ] 记录全流程 timeline。

### P3：护理执行

- [ ] 迁移 care_records；
- [ ] 新增 care_plans；
- [ ] 新增 daily_care_tasks；
- [ ] 新增 task_reviews；
- [ ] 护工端任务打卡；
- [ ] 护士审核。

### P4：风险事件

- [ ] 迁移 nursing events；
- [ ] 迁移 task-card 结构；
- [ ] 新增 incident protocol version；
- [ ] AI 任务卡改为协议模板主导；
- [ ] 红橙事件强制护士审核；
- [ ] 事件关闭与归档。

### P5：本地 AI

- [ ] 迁移 OCR 服务；
- [ ] 迁移 LLM provider；
- [ ] 迁移 HybridRetriever；
- [ ] 迁移 DecisionMemory 并改名为 CareMemory；
- [ ] 新增 ProtocolEngine；
- [ ] 新增 AI 输出校验器；
- [ ] 新增模型状态健康检查。

### P6：运维交付

- [ ] 一键备份；
- [ ] 一键恢复；
- [ ] 日志打包；
- [ ] 服务控制台；
- [ ] 升级前自动备份；
- [ ] 升级失败回滚；
- [ ] 授权文件；
- [ ] 远程诊断报告。

---

## 6. 命名替换规范

| 原型命名 | Official v1.0 命名 |
|---|---|
| patient | resident |
| EHR | Resident Health Record / Document |
| nursing decision | care assist / nursing assist |
| decision memory | care memory / event memory |
| task card | care task card / incident task card |
| medical record upload | health document upload |
| admin page | nurse station / admin console |
| nurse page | caregiver workspace |

---

## 7. 数据迁移注意事项

1. 原型 ChromaDB 中的 metadata 字段要做兼容导入；
2. `doc_type=profile`、`doc_type=patient_profile`、空 doc_type 都要识别为旧版老人基本档案；
3. 旧版 `patient_id` 导入时生成 `resident_id`；
4. PII 密文字段导入前必须确认 `PII_ENCRYPTION_KEY`；
5. 上传文件路径导入时要重新映射到 official v1.0 的 storage 目录；
6. 旧版护理事件 JSON/SQLite 要导入为 Incident + CareTask + CareRecord 三类数据；
7. 旧版 decision log 要导入 CareMemory。

---

## 8. 迁移完成判定

迁移不是文件复制完成，而是满足以下验收：

- [ ] 新仓库可以一键启动；
- [ ] 可以创建老人；
- [ ] 可以办理入住；
- [ ] 可以分配床位；
- [ ] 可以上传病历照片并 OCR；
- [ ] 可以生成护理计划；
- [ ] 可以生成今日任务；
- [ ] 护工可以打卡；
- [ ] 异常事件可以生成任务卡；
- [ ] 红橙风险需要护士审核；
- [ ] 可以生成 SBAR 交接；
- [ ] 可以归档护理记录；
- [ ] 可以备份恢复；
- [ ] 可以查看系统健康状态；
- [ ] 不依赖外部 CDN；
- [ ] 原型仓库未被修改。
