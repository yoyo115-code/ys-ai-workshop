# Private Beta Runbook

本文面向第一轮 3–5 人邀请制 Private Beta 的发布与值守。仓库提供 Render Blueprint，但不声称已实际上线。

## 发布前

1. 确认目标 commit 已通过完整测试、PostgreSQL 集成测试和容器构建。
2. 确认镜像中没有 `.env`、SQLite、用户文件、测试截图或浏览器二进制。
3. 在 Render Dashboard 选择 **New → Blueprint**，授权访问 Private GitHub 仓库并选择根目录 `render.yaml`。
4. 确认 Starter Web Service 与 `basic-256mb` PostgreSQL 费用、Singapore 区域和 `main` 分支。
5. 在首次 Blueprint 创建界面填写 [Deployment](DEPLOYMENT.md) 列出的 9 个 `sync: false` Secret。R2 使用 account endpoint、`S3_REGION=auto` 且 bucket 保持 Private。
6. 由 pre-deploy command 执行 `alembic upgrade head`，不手工并发执行第二份 migration。
7. 检查 live/ready 探针和对象存储访问，不在输出中显示连接串或 bucket 凭据。

## 创建邀请

在具备数据库访问权限的受控管理终端执行：

```bash
cd backend
python -m app.cli.create_invite --max-uses 5 --expires-in-days 14
```

CLI 校验执行者为现有管理员，明文邀请码只显示一次。通过私密渠道发送；不要放入 Issue、日志、截图或分析工具。

## Smoke test

1. 用邀请码注册临时测试账号并登录。
2. 确认非邀请注册被拒绝，失败提示不暴露邀请码状态细节。
3. 用去标识化材料完成 Career Match。
4. 接受一条安全建议并创建 ResumeVersion。
5. 生成、下载并删除 DOCX/PDF。
6. 确认另一个账号无法读取上述资源。
7. 确认活动日志中没有简历/JD 正文。
8. 确认前端隐藏 AI Labs，后端返回 `feature_disabled`。
9. 确认登录响应设置 `HttpOnly; Secure; SameSite=Lax` Cookie，前端 Storage 中没有 Session Token。
10. 将 Career 分析用完后确认第 3 次返回 `429`，且页面剩余数为 0。

## 日常值守

- 每日观察 readiness、错误率、AI Provider 超时和导出失败。
- 额度按 UTC 日期重置；不直接修改 `daily_usage`，如需临时政策变更则调整环境变量并重启。
- 每日至少一次执行 `python -m app.jobs.cleanup_expired_exports`。
- 邀请异常时禁用对应 code hash，不公开明文。
- 只使用资源 ID 定位问题；需要用户内容时先取得明确授权并限制访问人员。

## 故障处理

### readiness 失败

先区分数据库、存储或配置状态；检查服务权限和资源可达性。不得修改为 SQLite 或本地存储来掩盖生产故障。

### AI Provider 失败

保留用户原始申请和版本，返回可重试错误。不要用 Mock 结果冒充分析，也不要在 DeepSeek 失败后临时开启 Claude fallback。

### 额度异常

先确认 Render 配置的上限与 [BETA_LIMITS.md](BETA_LIMITS.md) 一致，再检查 UTC `usage_date`和对应资源 ID。不记录或复制简历、JD、Prompt 或模型完整响应。

### 导出失败

确认记录为 `failed` 而非 `ready`，检查临时对象是否清除。修复后由用户重新生成，不手工拼接伪文件。

### 数据删除失败

停止宣称删除完成，记录不含正文的资源 ID，重试幂等删除；对象与数据库状态必须最终一致。

## 回滚

1. 停止新流量或将应用置于维护状态。
2. 回滚到已验证镜像；数据库迁移默认只向前修复，不自动 downgrade。
3. 如果新代码依赖迁移，先评估旧版本是否兼容当前 schema。
4. 验证 live/ready、登录、读取自有历史和下载已有未过期导出。

任何包含破坏性数据库操作的回滚都需单独审批和可恢复备份，不在本仓库脚本中自动执行。
