# Migrations

当前版本以 `../schema.sql` 为完整结构基线。

1. `0001_career_match.sql`：Career Match 申请、简历来源、分析和匹配项。
2. `0002_resume_versioning.sql`：Resume 聚合、不可变版本、逐条建议和建议事件。

后续结构变更继续增加不可变迁移文件。当前尚未引入自动迁移工具。
