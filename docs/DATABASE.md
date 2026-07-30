# Database Design

当前数据库基线位于 `database/schema.sql`，详细运行约定见 `database/README.md`。

## 关系

```text
users 1 ── * sessions
users 1 ── * activity_logs
users 1 ── * job_applications
job_applications 1 ── 1 resume_sources
job_applications 1 ── * match_analyses
match_analyses 1 ── * match_items
users 1 ── * resumes
job_applications 1 ── 0..1 resumes
resumes 1 ── * resume_versions
resume_versions 1 ── * resume_suggestions
resume_suggestions 1 ── * resume_suggestion_events
users 1 ── * resume_exports
resumes 1 ── * resume_exports
resume_versions 1 ── * resume_exports
```

- 删除用户时，其 Session、活动日志和申请工作区通过外键级联删除。
- `sessions.token` 是主键，服务只按 token 和有效期查询。
- `activity_logs` 对 `user_id, created_at DESC` 建索引。
- `metadata` 当前以 JSON 字符串保存，保持 SQLite 原型简单。
- `job_applications` 保存岗位元数据、JD、语言和处理状态。
- `resume_sources` 保存文本/PDF/DOCX 来源、提取文本、内容哈希和解析状态；不保存上传原文件。
- `match_analyses` 保存整体结论、摘要、Provider、模型、Prompt 版本、状态和错误码。
- `match_items` 保存六类匹配项的 JD 原文、简历证据、解释与证据充分程度。
- 部分唯一索引限制同一申请最多一个 `analyzing` 分析，防止重复点击无限创建并行记录。
- `resumes` 保存用户所有权、来源申请和当前版本指针；`source_application_id` 唯一保证初始化幂等。
- `resume_versions` 保存不可变完整文本快照、父版本、连续版本号、来源和 SHA-256 哈希。
- `resume_suggestions` 固定关联生成时的 Application 和 ResumeVersion，保存证据、风险、状态、生成次数和 Prompt 版本。
- `resume_suggestion_events` 追加保存状态/文本变更的 JSON 前后值，用于审计和最近操作 Undo。
- `resume_exports` 保存用户与 ResumeVersion 所有权、模板/格式/纸张/语言、状态、安全下载名、随机内部对象名、确认后结构化快照、源/结构/输出哈希、错误码和生命周期时间。
- 导出记录与物理文件一一对应；相同版本可重复生成独立记录，不覆盖历史。用户和版本索引支持所有权查询与时间倒序历史。

## 数据生命周期

应用启动时会执行幂等 schema，并删除已过期 Session。`database/migrations/0001_career_match.sql` 记录 Career Match 增量，`0002_resume_versioning.sql` 记录 Resume Optimizer 四表与索引，`0003_resume_exports.sql` 记录 Resume Export 表与索引。不会自动创建演示用户；只有明确配置初始化管理员时才会创建管理员。

删除申请会通过外键级联删除其简历来源、分析和匹配项。Career Match 活动日志不保存简历正文、JD 或完整模型响应。

优化版本创建在单个显式事务中校验当前版本、替换文本、插入快照并更新指针；任意失败全部回滚。恢复会新建 `restored` 快照，不覆盖旧版本。ResumeVersion 与建议中均可能含简历个人信息，不得进入 activity log 预览或 Git。

导出先插入 `pending`，再转为 `generating`。文件从专用目录内临时路径原子移动到随机对象名后，记录才转为 `ready`；失败转为 `failed` 且不保留不完整文件。删除会清理文件并软删除记录。`expires_at` 已为后续保留周期预留，当前未实现自动过期任务。

数据库文件属于本地运行数据，不进入 Git。测试使用系统临时目录中的独立 SQLite 文件。

## 后续迁移

进入多用户部署前，将评估 PostgreSQL、正式迁移工具、连接池、行级访问策略和更严格的事务边界。当前 migration 是可审查的 SQL 文件，尚未引入自动迁移框架。
