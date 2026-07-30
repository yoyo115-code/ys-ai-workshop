# Database Design

当前数据库基线位于 `database/schema.sql`，详细运行约定见 `database/README.md`。

## 关系

```text
users 1 ── * sessions
users 1 ── * activity_logs
```

- 删除用户时，其 Session 和活动日志通过外键级联删除。
- `sessions.token` 是主键，服务只按 token 和有效期查询。
- `activity_logs` 对 `user_id, created_at DESC` 建索引。
- `metadata` 当前以 JSON 字符串保存，保持 SQLite 原型简单。

## 数据生命周期

应用启动时会执行幂等 schema，并删除已过期 Session。不会自动创建演示用户；只有明确配置初始化管理员时才会创建管理员。

数据库文件属于本地运行数据，不进入 Git。测试使用系统临时目录中的独立 SQLite 文件。

## 后续迁移

Career Studio 进入多用户部署前，将评估 PostgreSQL、正式迁移工具、连接池和事务边界。本阶段不进行该迁移。
