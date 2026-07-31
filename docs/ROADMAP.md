# Product Roadmap

本文只记录已实现能力和当前计划，不把后续功能描述为已经完成。

## v0.1 — Sanitized prototype

状态：已完成

- 保留五个 Nova AI 原型工具。
- 清理密钥、运行数据库和本地依赖。
- 建立个人仓库来源说明和安全基线。

## v0.2 — Career Match MVP

状态：已完成

- 简历文本/PDF/DOCX 与岗位 JD 保存。
- 可解释的结构化匹配分析和原文证据校验。
- 用户申请历史、重试、删除和数据隔离。
- Prompt Injection 防护、28 项自动化测试和版本化发布文档。

## v0.3 — Resume Optimizer & Versioning

状态：已完成

- 逐条简历建议与事实风险。
- 接受、拒绝、编辑、单条重新生成和 Undo。
- 不可变 ResumeVersion、版本比较和恢复。
- 响应式 Resume Optimizer 工作区与持久化状态。
- 稳定的静态资源交付与桌面/小屏浏览器验收。
- 58 项 mock Provider/静态交付自动化测试，包含事务回滚和旧接口回归。

验收以 [Resume Optimizer 规划](features/RESUME_OPTIMIZER.md) 和 [ADR-003](decisions/ADR-003-versioned-resume-model.md) 为准。

## v0.4 — Resume Export & Delivery

状态：Completed

- 从确认的 ResumeVersion 生成结构化预览。
- `professional` 与 `minimal_ats` 两个稳定模板。
- DOCX/PDF 生成、历史、下载、删除和文件安全。
- 保留可控段落层级，不承诺还原原始文件像素级版式。
- 增加内容一致性、隐私、路径安全和浏览器验收测试。
- 以确定性 Schema 驱动 DOCX/PDF，不使用 LLM 补全缺失信息。
- 导出历史、重复下载、删除、失败记录和用户数据隔离已完成。

设计以 [Resume Export 规划](features/RESUME_EXPORT.md) 和 [ADR-004](decisions/ADR-004-resume-document-rendering.md) 为准。

## Next — Production Beta & User Validation

状态：Next

- 小规模真实用户验证和反馈闭环。
- 部署前安全加固、隐私保留周期和运行监控。
- 对象存储抽象、异步导出与浏览器/文档 CI 矩阵。

## Planned — Cover Letter / Interview Preparation

状态：Planned

- 基于确认简历与 JD 生成可审阅 Cover Letter。
- 生成岗位问题、简历追问和 STAR 回答框架。

分享链接、OCR、新后台和新 AI Labs 当前没有开始。
