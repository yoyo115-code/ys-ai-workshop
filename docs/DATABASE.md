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

## 数据生命周期

应用启动时会执行幂等 schema，并删除已过期 Session。`database/migrations/0001_career_match.sql` 记录本阶段增量结构。不会自动创建演示用户；只有明确配置初始化管理员时才会创建管理员。

删除申请会通过外键级联删除其简历来源、分析和匹配项。Career Match 活动日志不保存简历正文、JD 或完整模型响应。

数据库文件属于本地运行数据，不进入 Git。测试使用系统临时目录中的独立 SQLite 文件。

## 后续迁移

进入多用户部署前，将评估 PostgreSQL、正式迁移工具、连接池、行级访问策略和更严格的事务边界。当前 migration 是可审查的 SQL 文件，尚未引入自动迁移框架。
