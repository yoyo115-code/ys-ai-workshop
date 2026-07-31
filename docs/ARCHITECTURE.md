# Architecture

## 目标

Phase 5A 在不改变 Career Match、Resume Optimizer、Resume Export 和五个 AI Labs API 的前提下，把 v0.4 单机原型整理为可部署的邀请制 Private Beta。系统仍是模块化单体，不拆微服务，不引入异步队列。

## 运行结构

```text
Browser
  ├── frontend/index.html + /assets
  └── FastAPI API
          ↓
Router / Auth dependency
          ↓
Service layer
  ├── Career / Resume / Export
  ├── Invite / Privacy / Retention job
  ├── LLM Provider
  └── StorageProvider
          ↓
Repository + SQLAlchemy 2 adapter
  ├── SQLite (local/test)
  └── PostgreSQL (production)

StorageProvider
  ├── LocalStorageProvider (local/test)
  └── S3StorageProvider (production)
```

生产 schema 由 Alembic 管理；对象存储与数据库是外部资源。仓库只提供 Docker 镜像和运行说明，不创建云资源。

## 模块职责

- `app.main`：验证配置、装配依赖、lifespan、CORS、静态资源和 Router。
- `app.api.*`：HTTP 契约、鉴权依赖和响应，不直接编写 SQL。
- `app.core.config`：唯一环境变量入口，production fail-fast。
- `app.core.security`：密码 PBKDF2、Session token、邀请码 HMAC 和输入规则。
- `app.repositories.database`：SQLAlchemy engine、连接池、事务与 SQLite/PostgreSQL 参数/Row 兼容。
- `app.repositories.*`：显式 SQL、所有权查询和事务状态转换。
- `app.services.storage`：`put/get/delete/exists/generate_download_url` 存储契约。
- `app.services.privacy`：删除 Application、Resume、Account 前先清理导出对象。
- `app.services.resume_export`：结构化、渲染、对象写入、保留期、下载和幂等清理。
- `app.services.activity`：模型调用记录与确定性脱敏；文档型功能不保存正文预览。
- `app.cli.create_invite`：只允许现有管理员创建限次/限期邀请，明文只显示一次。
- `app.jobs.cleanup_expired_exports`：独立可调度、可重复运行的保留期清理任务。
- `backend/alembic`：production schema 基线与有序升级。

## 数据访问决策

SQLAlchemy 2 只替换连接与事务边界：Repository 现有显式 SQL 通过适配器转换参数绑定，并在 PostgreSQL 插入时显式取得 `RETURNING id`。没有同时改写成 ORM，原因是数据库可移植性和领域重构不应在同一阶段发生。

SQLite 启动时使用 `database/schema.sql` 做幂等本地初始化；production 启动只验证已迁移 schema，绝不自动创建 SQLite。部署必须先运行 `alembic upgrade head`。

## Private Beta 注册流

```text
管理员 CLI 生成高熵明文
  -> HMAC-SHA256(SESSION_SECRET)
  -> invite_codes(code_hash, max_uses, expires_at)
  -> 明文只显示一次

用户注册
  -> 校验 REGISTRATION_MODE
  -> 计算 code_hash
  -> 条件更新 used_count
  -> 同一事务创建 user
```

重复用户名导致整个事务回滚，不消耗邀请码。`disabled` 模式完全拒绝注册；production 默认且要求 `invite_only`。

## 导出与存储流

```text
confirmed ResumeVersion
  -> StructuredResume
  -> pending / expires_at UTC
  -> 临时文件渲染
  -> put(user-scoped random object key)
  -> ready + SHA-256
  -> authenticated local download OR short S3 presigned redirect
  -> user delete / scheduled expiry cleanup
```

object key 为 `users/{user_id}/resume-exports/{random}.{format}`。用户下载名只进入 `Content-Disposition`，不参与物理路径。主动删除对象会使已签发的 presigned URL 失效。

## 数据删除边界

对象存储无法与数据库组成单一 ACID 事务，因此删除采用隐私优先顺序：先幂等删除对象，再执行数据库级联。对象失败时保留数据库记录并返回稳定错误，便于重试；不会宣称删除成功。Application、Resume 和 Account 均遵循同一顺序。

## 健康与部署

- `/health/live` 只检查进程。
- `/health/ready` 检查数据库和 StorageProvider，失败返回 503 且不暴露配置值。
- Docker 镜像使用固定 Python 基线、固定依赖、Noto CJK 字体和非 root 用户。
- GitHub Actions 运行 SQLite 完整回归、PostgreSQL migration/integration、Playwright 浏览器验收和 Docker build。

## 仍保留的业务架构

Career Match 与 Resume Suggestion 的 LLM 输出继续经过严格 Pydantic Schema、原文证据验证和确定性风险检查。ResumeVersion、Diff、恢复、结构化导出、文件名、哈希和生命周期仍由普通代码完成。模型失败不删除用户已保存输入，也不会返回 Mock 结果。

## 当前边界

- 没有实际云资源、公开 URL、队列、worker 或多区域部署。
- Header Session 尚未迁移 Secure Cookie；没有 CSRF、限流和病毒扫描。
- cleanup job 需要外部 scheduler。
- 本机没有 PostgreSQL/Docker，真实 integration 由 CI/部署环境执行。
- 没有 OCR、原始版式还原、Cover Letter、面试或分享链接。

关键决策见 [ADR-005](decisions/ADR-005-production-beta-architecture.md)。
