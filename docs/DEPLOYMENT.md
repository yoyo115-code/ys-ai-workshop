# Deployment

本文定义 Y's AI Workshop Private Beta 的可部署边界。Phase 5A 只提供可复现部署能力，不代表已经创建公开环境或处理真实用户数据。

## 环境矩阵

| 环境 | 数据库 | 文件存储 | 注册模式 | 用途 |
| --- | --- | --- | --- | --- |
| local | SQLite | LocalStorageProvider | open | 本地开发与手动验收 |
| test | 临时 SQLite / CI PostgreSQL | 临时本地目录 | open | 自动化测试 |
| production | Render PostgreSQL | Cloudflare R2 / S3-compatible | invite_only | 3–5 人邀请制 Beta |

生产环境不得静默退回 SQLite 或本地文件系统。缺少生产必需变量时应用应在启动阶段失败，错误只列出变量名，不输出变量值。

## Render Blueprint

根目录 `render.yaml` 按当前 [Render Blueprint 规范](https://render.com/docs/blueprint-spec) 定义：

- `ys-ai-workshop`：Singapore Starter Docker Web Service，跟踪 `main`；
- `ys-ai-workshop-db`：Singapore `basic-256mb` Render PostgreSQL 17，禁止公网 IP 白名单；
- `DATABASE_URL` 由 `fromDatabase.connectionString` 注入；
- `alembic upgrade head` 作为 pre-deploy command；
- `/health/ready` 作为 HTTP health check；
- `autoDeployTrigger: checksPass`，只在 GitHub Checks 通过后触发。

Render 的 pre-deploy command 只适用于付费 Web Service，因此 Blueprint 不使用 Free Web plan。创建前应在 Dashboard 确认费用。仓库只提供 Blueprint，不代表已创建云资源、域名或公开 URL。

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
INITIAL_ADMIN_USERNAME=
INITIAL_ADMIN_PASSWORD=
REGISTRATION_MODE=invite_only
AI_LABS_ENABLED=false
PRIMARY_LLM_PROVIDER=deepseek
EXPORT_RETENTION_DAYS=7
CORS_ORIGINS=
SESSION_SECRET=
SESSION_COOKIE_NAME=ys_ai_session
SESSION_COOKIE_SECURE=true
CAREER_ANALYSIS_DAILY_LIMIT=2
SUGGESTION_GENERATION_DAILY_LIMIT=2
SUGGESTION_REGENERATION_DAILY_LIMIT=8
RESUME_EXPORT_DAILY_LIMIT=5
MAX_RESUME_CHARACTERS=20000
MAX_JOB_DESCRIPTION_CHARACTERS=20000
```

Blueprint 中 `SESSION_SECRET` 使用 `generateValue: true`，`DATABASE_URL` 由 Render 数据库引用生成。以下值使用 `sync: false`，首次创建 Blueprint 时必须人工填写：

- `S3_ENDPOINT_URL`、`S3_BUCKET_NAME`、`S3_REGION`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`；
- `DEEPSEEK_API_KEY`；
- `INITIAL_ADMIN_USERNAME`、`INITIAL_ADMIN_PASSWORD`；
- `CORS_ORIGINS`。

`INITIAL_ADMIN_*` 只在两项同时存在时创建初始管理员；不得提供默认密码。Production 只要求 DeepSeek，不要求 `ANTHROPIC_API_KEY`，也不会隐式 fallback 到 Claude。

## Cloudflare R2

R2 bucket 必须保持 Private，不得开启公开 bucket URL。手动 Secret 使用：

```dotenv
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_REGION=auto
```

R2 凭据只注入后端运行环境，不返回前端。导出下载使用 presigned GET，`S3_PRESIGNED_URL_SECONDS` 默认 300，配置超过 600 时应用拒绝启动。

## 数据库迁移

开发和测试可以继续使用 SQLite；生产使用 PostgreSQL。部署新版本前执行：

```bash
cd backend
alembic upgrade head
```

Render 由 `preDeployCommand` 在新镜像启动前运行迁移。失败时停止发布，不允许应用回退到空 SQLite。

## 容器运行

从仓库根目录构建：

```bash
docker build -t ys-ai-workshop:v0.5.0-beta .
docker run --rm -p 8000:8000 --env-file /secure/path/ys-ai.env ys-ai-workshop:v0.5.0-beta
```

环境文件路径仅作示例，不能位于仓库或镜像中。容器使用非 root 用户运行，监听 `0.0.0.0:${PORT:-8000}`。

## 发布验收

1. 运行数据库迁移并确认没有 pending revision。
2. 检查 `GET /health/live` 为 `200`。
3. 检查 `GET /health/ready` 为 `200`，且只返回组件状态。
4. 用新生成的邀请码注册一个测试账号。
5. 使用去标识化简历完成 Career Match、Resume Optimizer 和一次 DOCX/PDF 导出。
6. 下载并删除导出，确认再次下载失败。
7. 执行一次 dry-run/空集合的过期清理任务。
8. 查看日志，确认没有简历正文、JD、密码、Token 或完整模型响应。
9. 确认 AI Labs 导航隐藏，直接调用返回 `403 feature_disabled`。
10. 确认页面显示当日 Career 分析和建议生成剩余次数。

回滚、故障和日常操作见 [BETA_RUNBOOK.md](BETA_RUNBOOK.md) 与 [OPERATIONS.md](OPERATIONS.md)。
