# Changelog

All notable changes to Y's AI Workshop are documented in this file.

## [v0.2.0] - 2026-07-30

### Added

- Career Match 用户流程：保存简历与岗位 JD，生成分析，并在历史记录中重新打开、重试或删除申请。
- PDF 与 DOCX 简历文本解析；扫描版 PDF 无可提取文本时返回明确错误。
- 结构化岗位匹配分析，覆盖总体分级、已覆盖、部分覆盖、缺失、信息不足、表达问题、岗位风险与分析限制。
- JD 原始要求和简历证据引用，并由后端验证引用确实来自用户输入。
- `career_match_v1` Prompt Injection 防护与严格 Pydantic JSON Schema 校验。
- 基于当前用户的申请数据隔离，以及不记录完整简历、JD 或模型响应的 Career Match 活动日志。
- 28 项自动化后端测试，覆盖权限、文件解析、模型异常、证据约束、持久化和原有五个 AI 接口回归。
