# Database

Y's AI Workshop 当前使用 SQLite 保存本地原型数据。后端从 `schema.sql` 初始化数据库结构，不在 Python Router 中执行建表 SQL。

## 当前表结构

- `users`：账号、PBKDF2-SHA256 密码摘要、盐、显示名、角色和启用状态。
- `sessions`：Session token、所属用户及创建和过期时间。
- `activity_logs`：五个 AI 工具的调用功能、状态、耗时、有限输入输出预览和元数据。
- `job_applications`：用户的公司、岗位、地点、JD、语言和流程状态。
- `resume_sources`：简历来源、提取文本、哈希与解析状态；不保存上传原文件。
- `match_analyses`：结构化匹配分析的状态、摘要、Provider、模型和 Prompt 版本。
- `match_items`：六类可解释匹配项及其原文证据。
- `resumes`：用户简历聚合、来源申请和当前版本指针。
- `resume_versions`：不可变的结构化文本快照、父版本和哈希。
- `resume_suggestions`：句子级建议、双向证据、风险、决策状态和 Prompt 版本。
- `resume_suggestion_events`：建议决策和手工编辑的追加审计事件。

所有 Session 和调用日志都属于运行数据。默认数据库路径由 `DATABASE_URL` 控制；未配置时，从 `backend/` 运行会使用 `backend/platform.db`。

## Migrations 和 Seeds

- `migrations/0001_career_match.sql` 记录 Career Match 增量，`migrations/0002_resume_versioning.sql` 记录版本化简历增量；`schema.sql` 始终代表新环境的完整结构。
- `seeds/` 只允许保存不含账号密码的非敏感字典数据；当前没有必须的 seed。
- 初始管理员只通过 `INITIAL_ADMIN_USERNAME` 和 `INITIAL_ADMIN_PASSWORD` 创建，不进入 SQL 文件。

## 为什么不能提交数据库文件

SQLite 文件可能包含密码摘要、Session token、用户输入、模型输出预览和调用错误。提交 `platform.db`、`*.db`、`*.sqlite` 或 `*.sqlite3` 会泄露运行数据并制造不可审计的环境差异，因此这些文件必须保持在 Git 之外。

## PostgreSQL 计划

后续进入多用户部署阶段时，再引入正式迁移工具和 PostgreSQL。迁移将优先保持 API 契约不变，补充连接池、事务、索引、数据保留和备份策略；本阶段不引入 SQLAlchemy，也不改变现有 SQLite 行为。
