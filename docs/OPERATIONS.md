# Operations

## 健康检查

- `GET /health/live`：进程可响应，不检查外部依赖。
- `GET /health/ready`：检查生产配置、数据库查询和存储可用性。

探针响应只返回组件名称、状态和稳定错误码，不返回数据库 URL、bucket、路径、Secret 或 Provider Key。负载均衡只向 readiness 成功的实例转发流量。

## 数据库

生产变更通过 Alembic revision 管理：

```bash
cd backend
alembic current
alembic upgrade head
```

每次迁移前先使用基础设施快照/备份能力并验证恢复流程。应用时间戳统一写入 UTC；展示层再转换时区。数据库账号只授予当前 schema 的必要 DML 与迁移权限，日常应用账号和迁移账号宜分离。

## 导出生命周期

手动或 scheduler 执行：

```bash
cd backend
python -m app.jobs.cleanup_expired_exports
```

任务可重复执行：只选择已到期、未删除记录，删除对象后标记删除；对象已不存在视为可收敛状态。退出码非零表示仍有失败项，需要告警与重试。

## 对象存储

- bucket 默认私有，关闭匿名读写和目录列表。
- object key 由服务端随机生成并包含用户隔离前缀，不使用下载文件名。
- 下载使用短期 presigned URL；主动删除对象会使地址失效。
- 生命周期规则可作为清理任务的第二道保障，但不能代替数据库状态更新。

## 日志与指标

建议采集：请求计数/状态/延迟、ready 状态、数据库与存储错误、AI Provider 延迟和错误码、导出成功率、清理任务数量。不得采集请求正文、响应正文、签名 URL、密码、Session、邀请码或 API Key。

## Secret 轮换

1. 在 Secret Manager 创建新值。
2. 更新应用并滚动重启。
3. 验证 readiness 和核心流程。
4. 撤销旧凭据。

`SESSION_SECRET` 轮换会影响邀请码哈希校验；轮换前应使旧邀请码到期或重新签发。数据库与对象存储凭据应支持短暂重叠以实现无中断切换。

## 备份与恢复

生产 PostgreSQL 使用托管备份和时间点恢复；对象存储按隐私保留策略配置版本/生命周期。至少演练一次从备份恢复到隔离环境，确认用户隔离和删除策略仍生效。不得把生产备份下载到仓库或个人开发目录。

## 最小告警

- readiness 连续失败；
- 数据库或存储错误持续出现；
- AI Provider 错误率突增；
- 清理任务退出非零或过期积压；
- 导出失败率异常；
- 邀请码使用量异常。

Private Beta 初期可人工值守，但必须明确负责人、响应渠道和暂停邀请的权限。
