# Changelog

All notable changes to Y's AI Workshop are documented in this file.

## [v0.4.0-draft] - 2026-07-30

### Added

- Deterministic `StructuredResume` preview traced to an immutable ResumeVersion.
- Editable export snapshot without changing the source ResumeVersion.
- `professional` and `minimal_ats` templates for A4 or Letter documents.
- Direct DOCX generation with stable headings, bullets, margins and bilingual content.
- Direct PDF generation from the same confirmed schema, including explicit CJK font capability errors.
- Authenticated export history, repeat download, deletion and clear failed states.
- Safe download filenames, private random object keys, atomic writes, hashes and traversal checks.

### Testing

- 86 backend and static-delivery automated tests, including 28 Resume Export tests.
- 5 optional Playwright browser regression tests.
- Live HTTP browser acceptance for login, preview, DOCX/PDF generation, download UI, desktop and 390 px layouts.
- Parsed DOCX/PDF content checks and manual document rendering review for both templates and Chinese/English content.

### Known limitations

- Export does not reproduce the original uploaded DOCX/PDF layout, columns, images or typography.
- No OCR, Cover Letter, interview workflow, public sharing or deployment.
- Export storage is local and synchronous; automatic expiry cleanup and object storage are not implemented.
- CJK PDF rendering requires a supported Unicode font in the runtime environment.

## [v0.3.0] - 2026-07-30

### Added

- Evidence-grounded resume suggestions
- Accept, reject, edit, regenerate and undo workflow
- Immutable resume version history
- Version diff and restore
- Deterministic hallucination-risk checks
- Browser delivery and static asset validation

### Testing

- 58 automated tests
- Browser acceptance validation
- Static resource delivery tests

### Known limitations

- No layout-preserving DOCX/PDF export
- No OCR
- No public deployment
- Playwright runtime remains optional

## [v0.2.0] - 2026-07-30

### Added

- Career Match 用户流程：保存简历与岗位 JD，生成分析，并在历史记录中重新打开、重试或删除申请。
- PDF 与 DOCX 简历文本解析；扫描版 PDF 无可提取文本时返回明确错误。
- 结构化岗位匹配分析，覆盖总体分级、已覆盖、部分覆盖、缺失、信息不足、表达问题、岗位风险与分析限制。
- JD 原始要求和简历证据引用，并由后端验证引用确实来自用户输入。
- `career_match_v1` Prompt Injection 防护与严格 Pydantic JSON Schema 校验。
- 基于当前用户的申请数据隔离，以及不记录完整简历、JD 或模型响应的 Career Match 活动日志。
- 28 项自动化后端测试，覆盖权限、文件解析、模型异常、证据约束、持久化和原有五个 AI 接口回归。
