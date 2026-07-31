# ADR-005: Production beta architecture

- 状态：Accepted for Phase 5A implementation
- 日期：2026-07-31

## 背景

v0.4 是单实例 SQLite 与本地导出目录上的可运行原型。邀请制 Private Beta 需要在不重写业务 Router/Service 的前提下支持 PostgreSQL、私有对象存储、可重复迁移、邀请码、数据删除和运行探针。当前 raw `sqlite3` 连接、SQLite 占位符、`lastrowid` 和本地绝对路径不能直接用于多实例生产部署。

## 决策

### 1. 保持模块化单体，引入 SQLAlchemy 2 连接层

继续使用现有 FastAPI Router、Service、Repository 边界，不拆微服务。引入 SQLAlchemy 2 负责连接池、事务和 SQLite/PostgreSQL 方言兼容；Repository 保持显式 SQL，避免同时改写为 ORM 领域模型。

数据库适配层负责统一参数绑定、行映射、事务和插入 ID 返回。SQLite 继续用于本地与快速测试，PostgreSQL 是 production 唯一允许的数据库。

选择 SQLAlchemy 而不是继续扩展 `sqlite3`，因为后者无法连接 PostgreSQL；选择 Core/显式 SQL而不是全面 ORM，是为了降低 Phase 5A 对已验证业务语义的影响。

### 2. Alembic 管理生产 schema

生产 schema 通过有序 Alembic revision 创建和升级。新部署先运行 migration，再启动应用。现有 `database/schema.sql` 继续作为 SQLite 可读基线和本地初始化参考，但不作为生产变更机制。

迁移使用 UTC 语义、可重复执行流程和明确失败；应用不会在 production 自动创建一套空 SQLite。Phase 5A 只包含向前 migration，不自动执行破坏性 downgrade。

### 3. StorageProvider 隔离文件系统和对象存储

定义 `put/get/delete/exists/generate_download_url` 契约：

- `LocalStorageProvider` 服务本地开发和测试；
- `S3StorageProvider` 服务 production，并兼容自定义 endpoint；
- object key 使用 `users/{user_id}/resume-exports/{random}`，下载文件名不参与物理路径；
- S3 下载使用短期 presigned URL，本地下载由受鉴权 API 流式返回。

数据库只保存 object key，不暴露本地绝对路径。删除先清理对象再收敛数据库状态，幂等任务允许对象已不存在。

### 4. 同步请求与独立清理 job

Private Beta 规模下，导出仍在请求内同步生成，以避免过早引入队列。过期清理是可单独调度、幂等的 CLI job。若生成延迟或并发成为瓶颈，再引入 worker/queue，不在 Phase 5A 预先实现。

### 5. 邀请制注册与生产失败即停

`REGISTRATION_MODE` 支持 `open`、`invite_only`、`disabled`；production 默认且要求 `invite_only`。邀请码只保存带 `SESSION_SECRET` 的哈希，明文由管理员 CLI 生成并只显示一次。使用次数更新与创建用户位于同一数据库事务。

启动时校验 production 的 PostgreSQL、S3、Session、CORS 和必要 Provider 配置。错误仅列出缺失的变量名。readiness 对数据库和存储做无敏感信息的探测。

## 备选方案

- **继续 raw sqlite3 并为 PostgreSQL 复制 Repository**：两套 SQL/事务会迅速漂移，拒绝。
- **一次性全面迁移 ORM 和领域模型**：改动面过大，会把部署工程与业务重构耦合，拒绝。
- **始终保存到容器本地磁盘**：滚动部署和多实例会丢文件，production 禁止。
- **公开 bucket 或永久下载 URL**：无法满足用户隔离和删除失效，拒绝。
- **立即引入 Celery/Redis**：当前规模没有证据需要，延后。

## 后果

优点：在保留已测试业务层的同时获得 PostgreSQL、连接池、迁移和对象存储；本地开发仍轻量；生产配置错误不会被静默掩盖。

代价：显式 SQL适配层需要严格的跨数据库测试；同步导出限制并发；S3 与 PostgreSQL 增加运维资源；`SESSION_SECRET` 轮换需要邀请码过渡方案。

## 验证

- SQLite 完整回归与 PostgreSQL CI integration test；
- migration 从空库升级到 head；
- Local/S3 mock 存储契约、跨用户访问、路径和删除测试；
- 邀请并发使用、到期、禁用和事务回滚测试；
- production 配置失败、live/ready、清理幂等与隐私删除测试；
- Docker 非 root、healthcheck 和 Git 跟踪内容检查。
