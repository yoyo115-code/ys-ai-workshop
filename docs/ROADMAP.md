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

## v0.5 — Deployable Private Beta

状态：Completed

- PostgreSQL production 数据层与可重复 migration。
- Local/S3-compatible 存储抽象、限时下载与过期清理。
- 邀请制注册、生产配置校验和 live/ready 探针。
- 用户数据删除、日志最小化、Docker 与 PostgreSQL CI。
- Production 关闭 AI Labs，DeepSeek-only 默认 Provider 路径。
- 四类持久化 UTC 日额度、简历/JD 输入上限和管理员显式豁免规则。
- Production Secure Cookie，前端不保存 Session Token。
- Render Blueprint 定义 Singapore Docker Web Service、PostgreSQL、pre-deploy migration 和手动 Secret。
- 本阶段交付可部署配置，不声称已创建云资源或处理真实用户数据。

设计以 [ADR-005](decisions/ADR-005-production-beta-architecture.md)、[Deployment](DEPLOYMENT.md) 和 [Privacy](PRIVACY.md) 为准。

## Next — Production Beta & User Validation

状态：Next

- 在人工创建的受控环境进行小规模邀请测试。
- 先以 3–5 名测试者验证完整 Career 流程、额度提示、删除和 7 天保留策略。
- 完成 Provider 数据处理条款、备份窗口和告警负责人确认。
- 收集去标识化的流程反馈和可靠性指标，不扩张功能范围。

## Planned — Cover Letter / Interview Preparation

状态：Planned

- 基于确认简历与 JD 生成可审阅 Cover Letter。
- 生成岗位问题、简历追问和 STAR 回答框架。

分享链接、OCR、新后台和新 AI Labs 当前没有开始。
