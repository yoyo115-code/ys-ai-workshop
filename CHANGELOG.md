# Changelog

All notable changes to Y's AI Workshop are documented in this file.

## [v0.5.0] - 2026-07-31

### Added

- PostgreSQL production compatibility through a SQLAlchemy 2 connection/transaction adapter and Alembic migrations.
- Local and S3-compatible storage providers with user-scoped random object keys and short-lived presigned downloads.
- Invitation-only registration with hashed, expiring, usage-limited codes and an administrator CLI.
- Seven-day default export retention, expired-download rejection and an idempotent cleanup job.
- Job Application, Resume, export and account deletion with physical export-object cleanup.
- Log minimization and deterministic contact/credential redaction.
- Liveness/readiness probes, non-root Docker image and PostgreSQL/browser/container CI.
- Private Beta badge, de-identification warning, retention notice, invite field and account deletion entry.
- Production AI Labs feature gate and a DeepSeek-only primary Provider path without implicit Claude fallback.
- Persistent per-user UTC daily limits for Career analysis, suggestion generation/regeneration and Resume Export.
- Pre-model 20,000-character resume/JD limits and an authenticated remaining-quota view.
- Production `HttpOnly; Secure; SameSite=Lax` Session Cookie with configurable name/expiry; browser Token storage removed.
- Render Blueprint for a Singapore Docker Web Service, Render PostgreSQL, Alembic pre-deploy migration and Cloudflare R2 secrets.

### Testing

- 145 discovered backend tests: 144 pass locally and one PostgreSQL integration test runs when a PostgreSQL service is available.
- SQLite and PostgreSQL-offline migration validation.
- Browser acceptance for Private Beta UI, assets, console and 390px responsive layout.
- Launch guardrail validation for AI Labs closure, Provider selection, all four quotas, UTC reset, concurrency, input limits, Secure Cookie and `render.yaml`.

### Known limitations

- The Blueprint is ready for manual creation, but no cloud environment, public URL, managed backup or monitoring resource has been created by this repository.
- S3 contract is locally mocked; live object-store and PostgreSQL execution are delegated to controlled deployment/CI environments.
- Retention cleanup requires an external scheduler.
- No real-user Beta research has been performed yet.

## [v0.4.0] - 2026-07-31

### Added

- Structured Resume Schema
- Professional and Minimal ATS templates
- DOCX and PDF generation
- Resume preview and export history
- Secure download and deletion
- Atomic file generation and path-traversal protection

### Testing

- 86 automated tests
- 28 Resume Export tests
- Browser and responsive regression

### Known limitations

- No original-layout preservation
- No OCR
- No cloud object storage
- No public deployment
- No automatic retention cleanup

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
