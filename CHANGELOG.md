# Changelog

All notable changes to Y's AI Workshop are documented in this file.

## [v0.3.0] - Draft

### Added

- Resume Optimizer 工作区：从 Career Match 申请生成句子级建议，展示原句、建议句、原因、JD/简历证据与事实风险。
- 建议接受、拒绝、手工编辑、单条重新生成、最近操作 Undo 和持久化事件审计。
- `resume_suggestion_v1` 严格 Schema，以及原句/证据定位、新数字/技术名/专有名词风险检测和高风险接受阻断。
- 不可变 ResumeVersion 完整文本快照，支持事务化生成、历史、确定性 Diff 和以新快照恢复。
- Resume、Version、Suggestion 和 SuggestionEvent 四个 SQLite 表及 `0002_resume_versioning.sql`。
- 58 项 mock Provider/静态交付自动化测试，包含建议状态机、事务回滚、用户隔离、版本操作、静态资源路径/MIME 和旧功能回归。
- Phase 3.1 前端交付修复：CSS/JavaScript 使用相对路径、`config.js` 先于 `app.js` 延迟执行、SVG 内建尺寸与样式化 `file://` 预览提示。
- 4 项可选 Playwright 浏览器测试，覆盖样式、认证面板、Career/Optimizer/AI Labs 导航、静态资源和控制台错误。

### Current limitations

- 当前版本仅保留结构化文本和段落顺序，不保留 PDF/DOCX 版式。
- 事实风险检测为保守启发式，需要用户最终核查。
- Cover Letter、面试准备、分享链接和 OCR 仍未实现。

## [v0.2.0] - 2026-07-30

### Added

- Career Match 用户流程：保存简历与岗位 JD，生成分析，并在历史记录中重新打开、重试或删除申请。
- PDF 与 DOCX 简历文本解析；扫描版 PDF 无可提取文本时返回明确错误。
- 结构化岗位匹配分析，覆盖总体分级、已覆盖、部分覆盖、缺失、信息不足、表达问题、岗位风险与分析限制。
- JD 原始要求和简历证据引用，并由后端验证引用确实来自用户输入。
- `career_match_v1` Prompt Injection 防护与严格 Pydantic JSON Schema 校验。
- 基于当前用户的申请数据隔离，以及不记录完整简历、JD 或模型响应的 Career Match 活动日志。
- 28 项自动化后端测试，覆盖权限、文件解析、模型异常、证据约束、持久化和原有五个 AI 接口回归。
