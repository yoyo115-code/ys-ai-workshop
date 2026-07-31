# Deployment

本文定义 Y's AI Workshop Private Beta 的可部署边界。Phase 5A 只提供可复现部署能力，不代表已经创建公开环境或处理真实用户数据。

## 环境矩阵

| 环境 | 数据库 | 文件存储 | 注册模式 | 用途 |
| --- | --- | --- | --- | --- |
| local | SQLite | LocalStorageProvider | open | 本地开发与手动验收 |
| test | 临时 SQLite / CI PostgreSQL | 临时本地目录 | open | 自动化测试 |
| production | PostgreSQL | S3-compatible | invite_only | 小规模邀请制 Beta |

生产环境不得静默退回 SQLite 或本地文件系统。缺少生产必需变量时应用应在启动阶段失败，错误只列出变量名，不输出变量值。

## 生产资源

部署前需要人工创建和保管：

- 一个受限网络访问的 PostgreSQL 数据库；
- 一个默认私有、禁用公开列表的 S3-compatible bucket；
- 应用运行环境及 HTTPS 入口；
- Secret Manager 中的数据库、对象存储、Session 与 AI Provider 凭据；
- 定时执行过期导出清理任务的 scheduler。

Phase 5A 不自动创建任何云资源，也不包含真实生产域名。

## 必需配置

生产环境至少配置：

```dotenv
APP_ENV=production
DATABASE_URL=
STORAGE_PROVIDER=s3
S3_ENDPOINT_URL=
S3_BUCKET_NAME=
S3_REGION=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
DEEPSEEK_API_KEY=
ANTHROPIC_API_KEY=
INITIAL_ADMIN_USERNAME=
INITIAL_ADMIN_PASSWORD=
REGISTRATION_MODE=invite_only
EXPORT_RETENTION_DAYS=7
CORS_ORIGINS=
SESSION_SECRET=
```

`INITIAL_ADMIN_*` 只在两项同时存在时创建初始管理员；不得提供默认密码。部署后应撤下初始化密码并轮换相关 Secret。AI 功能实际使用的 Provider Key 必须存在，未启用的备用 Provider 可留空。

## 数据库迁移

开发和测试可以继续使用 SQLite；生产使用 PostgreSQL。部署新版本前执行：

```bash
cd backend
alembic upgrade head
```

迁移必须在单一 release job 中运行一次，成功后再滚动应用实例。迁移脚本使用 UTC 时间语义，禁止依赖主机本地时区。失败时停止发布，不允许应用回退到空 SQLite。

## 容器运行

从仓库根目录构建：

```bash
docker build -t ys-ai-workshop:v0.5.0-beta .
docker run --rm -p 8000:8000 --env-file /secure/path/ys-ai.env ys-ai-workshop:v0.5.0-beta
```

环境文件路径仅作示例，不能位于仓库或镜像中。容器使用非 root 用户运行，运行时只需网络访问 PostgreSQL、对象存储和选定 AI Provider。

## 发布验收

1. 运行数据库迁移并确认没有 pending revision。
2. 检查 `GET /health/live` 为 `200`。
3. 检查 `GET /health/ready` 为 `200`，且只返回组件状态。
4. 用新生成的邀请码注册一个测试账号。
5. 使用去标识化简历完成 Career Match、Resume Optimizer 和一次 DOCX/PDF 导出。
6. 下载并删除导出，确认再次下载失败。
7. 执行一次 dry-run/空集合的过期清理任务。
8. 查看日志，确认没有简历正文、JD、密码、Token 或完整模型响应。

回滚、故障和日常操作见 [BETA_RUNBOOK.md](BETA_RUNBOOK.md) 与 [OPERATIONS.md](OPERATIONS.md)。
