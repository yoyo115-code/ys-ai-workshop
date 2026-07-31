# Security

## 生产配置

- 环境变量只从 `backend/app/core/config.py` 读取。
- production 必须使用 PostgreSQL、S3-compatible 存储、`invite_only`、明确 CORS 和至少 32 字符的 `SESSION_SECRET`。
- 缺少关键配置时启动失败；错误只列变量名，不输出值。
- 初始管理员没有默认账号/密码，两项必须成对配置。
- `.env`、数据库、备份、导出、日志、虚拟环境、缓存和依赖目录不进入 Git 或 Docker build context。

## 认证与邀请

- 密码使用 PBKDF2-SHA256 和独立 salt。
- Session 使用高熵随机 token，不写业务日志。
- `REGISTRATION_MODE` 支持 `open`、`invite_only`、`disabled`；production 只允许邀请制。
- 邀请码使用 `SESSION_SECRET` 做 HMAC-SHA256，数据库只保存哈希、次数和到期时间。
- 邀请使用次数条件更新与用户创建同一事务；失败不会错误消耗。
- 明文邀请码由管理员 CLI 显示一次，不能进入 Issue、日志、测试或截图。

## 用户隔离

- Application、Resume、Version、Suggestion 和 Export 查询均反向校验当前用户。
- 越权资源返回 `404`，减少枚举信号。
- object key 强制 `users/{user_id}/resume-exports/{random}`；下载文件名不参与路径。
- S3 bucket 必须私有，下载使用短期 presigned URL；主动删除对象使 URL 失效。
- LocalStorageProvider 使用 key 哈希映射到受控根目录，拒绝跨用户和目录穿越。

## 日志最小化

- Career Match / Resume Optimizer 只记录资源 ID、状态、耗时、Provider、模型和 Prompt 版本。
- Resume、PDF、CSV 不保存输入/输出正文预览。
- 其他有限预览在入库前脱敏邮箱、电话、`sk-`、API Key、Token、Password 和 Secret。
- 不记录完整模型响应、Session、邀请码、API Key、对象存储凭据或 presigned URL。

## 数据删除与保留

- 导出默认保留 7 天，到期后拒绝下载。
- 清理 job 幂等删除对象并软删除记录；用户可立即删除导出。
- 删除 Application、Resume 或 Account 时先删除关联导出对象，再执行数据库级联。
- 对象删除失败返回 `data_deletion_incomplete` 并保留数据库记录，便于重试。
- 云端备份可能有独立保留窗口；真实邀请前必须公布并完成恢复/销毁演练。

## 容器与运行

- Docker 使用固定 Python 基线、固定 Python 依赖、非 root 用户和 readiness HEALTHCHECK。
- production migration 独立运行，应用不自动降级或创建 SQLite。
- live/ready 响应不暴露连接 URL、bucket 或路径。
- GitHub Actions 使用合成凭据、mock LLM 和临时 PostgreSQL；不调用真实 Provider。

## 已知风险

- Header Session 尚未迁移 Secure Cookie；公开互联网前需评估 CSRF、Cookie 属性和会话撤销。
- 尚未实现请求限流、恶意文件/病毒扫描、WAF、审计日志后端或安全告警平台。
- S3 contract 通过 fake client 测试，但尚未完成特定云厂商的权限/加密/生命周期验收。
- cleanup job 需要外部 scheduler；仓库不创建告警和备份资源。
- AI Provider 会接收用户主动提交的分析内容；邀请真实用户前需完成数据处理条款和区域评估。
- 当前没有公开部署或真实用户数据，不能把文档中的目标控制描述为已运行的云控制。

详细隐私边界见 [PRIVACY.md](PRIVACY.md)，故障流程见 [BETA_RUNBOOK.md](BETA_RUNBOOK.md)。
