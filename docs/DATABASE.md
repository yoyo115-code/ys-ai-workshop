# Database Design

## 环境策略

- local/test：SQLite，便于零依赖开发和快速隔离测试。
- production：PostgreSQL，必须通过 `DATABASE_URL` 显式配置。
- production 不支持静默回退 SQLite；缺少或错误方言会在启动前失败。

SQLAlchemy 2 提供 engine、连接池、事务与参数方言兼容；Repository 继续使用可审查的显式 SQL。production migration 使用 Alembic，SQLite 可读基线位于 `database/schema.sql`。

## 关系

```text
users 1 ── * sessions
users 1 ── * activity_logs
users(admin) 1 ── * invite_codes
users 1 ── * job_applications
job_applications 1 ── 1 resume_sources
job_applications 1 ── * match_analyses ── * match_items
users 1 ── * resumes ── * resume_versions
resume_versions 1 ── * resume_suggestions ── * resume_suggestion_events
users/resumes/resume_versions 1 ── * resume_exports
```

## Private Beta 变化

### `invite_codes`

- `code_hash`：唯一 HMAC-SHA256，不保存明文。
- `max_uses` / `used_count`：条件更新限制次数。
- `expires_at` / `is_active`：到期与人工禁用。
- `created_by_user_id`：关联创建时的管理员。
- `created_at` / `last_used_at`：UTC ISO 8601。

邀请码次数更新与用户插入在同一事务内；用户插入失败会回滚次数。

### `resume_exports`

现有 `expires_at` 正式进入生命周期：创建时由 `EXPORT_RETENTION_DAYS` 计算；到期记录拒绝下载，清理任务删除对象后软删除记录。数据库只保存随机 `object_key`，不保存 presigned URL 或本地绝对路径。

## 既有核心表

- `users` / `sessions`：密码哈希、角色和限时 Session。
- `activity_logs`：技术活动记录；简历/JD/文档正文不进入预览，其他预览先脱敏。
- `job_applications` / `resume_sources`：岗位元数据、JD、提取简历文本和解析状态，不保存上传原文件。
- `match_analyses` / `match_items`：结构化匹配、证据、Provider、模型和 Prompt 版本。
- `resumes` / `resume_versions`：用户聚合与不可变文本版本。
- `resume_suggestions` / `resume_suggestion_events`：建议状态、证据、风险和追加事件。
- `resume_exports`：结构化快照、模板/格式、哈希、对象 key、状态和生命周期。

## Migration

Alembic revision：

- `20260730_01`：v0.4 完整生产基线。
- `20260731_02`：Private Beta `invite_codes`。

执行：

```bash
cd backend
alembic current
alembic upgrade head
```

SQLite 历史增量仍保存在 `database/migrations/0001` 至 `0004`，用于本地审查和旧原型说明。production 只以 Alembic revision 为准。

时间戳由应用以 timezone-aware UTC ISO 8601 写入。排序和到期比较不得依赖主机本地时区。

## 删除与事务

- 删除 User 时数据库级联 Session、Activity、Application、Resume、Version、Suggestion 和 Export。
- 删除 Application 时级联 Resume 来源、分析、Resume 领域数据和 Export 记录。
- 删除 Resume 时保留 Application，但级联 Version、Suggestion 和 Export。
- 物理导出对象不属于数据库事务；PrivacyService 先删除对象，再提交数据库删除。对象失败则保留数据库记录以便重试。
- 版本创建、建议状态、邀请码使用和导出状态均在显式事务中执行。

## 测试

- 从空 SQLite 执行 Alembic 到 head 并核对 revision/table。
- PostgreSQL offline SQL 确认无 `PRAGMA` / `AUTOINCREMENT`。
- GitHub Actions PostgreSQL service 执行 migration，再完成注册和 Career Repository round-trip。
- 所有普通测试使用系统临时 SQLite 与合成数据。

本机当前没有 Docker/PostgreSQL 服务，因此 PostgreSQL integration 在本地明确 skip，在 CI 执行。
