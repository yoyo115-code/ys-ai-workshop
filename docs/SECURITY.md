# Security

## 当前边界

Y's AI Workshop 是本地优先原型。它保存账号、Session、简历、JD、AI 分析、简历版本和导出文件，这些均应视为私密求职数据。当前安全控制不等价于公网多租户部署方案。

## 凭据与认证

- API Key、初始管理员和数据库路径只从 `backend/app/core/config.py` 读取。
- 仓库不含默认管理员密码或演示账号密码。只在 `INITIAL_ADMIN_USERNAME` 和 `INITIAL_ADMIN_PASSWORD` 同时有效时初始化管理员。
- 密码使用 PBKDF2-SHA256 与独立盐值；Session token 不写入业务日志。
- `.env`、SQLite 文件、虚拟环境、缓存、日志和 `backend/generated/` 被 Git 忽略。`.env.example` 只保存变量名或安全非密钥示例。

## 用户数据隔离

- Career Application、Resume、ResumeVersion、Suggestion 和 Resume Export 均从当前 Session 用户反向校验所有权。
- 越权资源统一返回 `404`，减少资源枚举信号。
- Career Match 和 Resume Optimizer 活动日志不保存完整简历、JD、Prompt 或模型完整响应。导出服务不把简历内容写入 activity log preview。

## Resume Export 文件安全

- 对外下载名会规范 Unicode，删除路径分隔符、控制字符和非法字符，折叠连续分隔符并限制长度。
- 内部文件使用 export ID 和随机后缀，不使用用户文件名，不向 API 暴露 `object_key` 或本地绝对路径。
- 所有读写路径在解析后必须仍属于 `RESUME_EXPORT_DIR`，否则拒绝，用于防止目录穿越。
- 渲染先写入专用目录中的临时文件，校验非空后原子移动。失败会清理临时/最终路径并把记录标记为 `failed`。
- 模板只渲染用户确认的 `StructuredResume`，不包含 API Key、Prompt、风险分析、内部 ID 或数据库路径。
- DOCX 和 PDF 响应使用准确 `Content-Type` 和受控 `Content-Disposition`。

## 数据清理

- 用户可删除导出记录；服务会先校验路径再清理对应文件并软删除记录。
- `expires_at` 已为保留周期预留，但本地原型尚无定时清理任务。用户应手动删除不再需要的文件。
- 开发和测试使用合成简历与系统临时目录；不得把真实简历、JD、模型响应或导出文件提交 Git。

## 已知风险

- SQLite、Header Session 和本地文件存储只适合单机原型。公网部署前需要 HTTPS、安全 Cookie 或标准 token 流程、PostgreSQL、对象存储、私有网络、配额/限流、恶意文件扫描和自动保留周期。
- AI Labs 历史行为仍保存有限输入/输出预览，后续需要统一隐私级别与删除策略。
- 文档生成库与系统字体应持续更新并在目标平台测试。包含 CJK 的 PDF 找不到可用 Unicode 字体时会明确失败，不生成缺字文件。
