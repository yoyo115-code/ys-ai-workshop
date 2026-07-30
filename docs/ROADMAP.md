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

## Next — Layout-preserving export

状态：未开始

- 将结构化文本版本导出为 PDF/DOCX。
- 保留可控的段落层级和基础版式。
- 增加导出文件的内容、隐私和浏览器验收测试。

## Later — Application package

状态：未开始

- Cover Letter。
- 面试准备与 STAR 框架。
- PostgreSQL、异步任务和浏览器测试 CI 集成。

分享链接、OCR、新后台和新 AI Labs 当前不在 Phase 3 范围内。
