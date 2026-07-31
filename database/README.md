# Database

Y's AI Workshop 在 local/test 使用 SQLite，在 production 使用 PostgreSQL。Router 不直接执行 SQL；SQLAlchemy 2 负责连接、事务和方言适配，Repository 保留显式 SQL。

## Schema

`schema.sql` 是新 SQLite 环境的完整结构，包含账号、Session、活动、Career Match、Resume Versioning、Resume Export 与哈希邀请码。SQLite 默认文件由 `DATABASE_URL` 控制，从 `backend/` 启动时为 `backend/platform.db`。

## Migrations

- `migrations/0001_career_match.sql`
- `migrations/0002_resume_versioning.sql`
- `migrations/0003_resume_exports.sql`
- `migrations/0004_private_beta.sql`

这些文件记录 SQLite 可读增量。production 使用 `backend/alembic/`：`20260730_01` 建立 v0.4 基线，`20260731_02` 增加 Private Beta 邀请表。

```bash
cd backend
alembic upgrade head
```

production 发布必须先显式迁移；应用不会静默创建 SQLite 替代 PostgreSQL。

## Seeds

`seeds/` 只允许保存不含账号密码的非敏感字典数据。初始管理员仅从成对的 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 创建；没有默认密码。邀请码由管理员 CLI 创建，数据库只保存哈希。

## 为什么不能提交数据库

数据库包含密码摘要、Session、简历、JD、分析、版本和结构化导出快照。`platform.db`、`*.db`、`*.sqlite*`、生产备份和导出文件都属于敏感运行数据，不能进入 Git，也不能复制到个人开发目录。测试只使用系统临时目录和合成数据。
