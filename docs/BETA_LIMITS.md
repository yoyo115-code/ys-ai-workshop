# Private Beta Limits

v0.5.0 面向第一轮 3–5 名受邀测试者。目标是验证 Career 工作流的真实可用性，不扩张功能数量，也不代表服务已经公开上线。

## Production 开放范围

- 邀请码注册、登录和注销；
- Career Match；
- Resume Optimizer 与不可变 Resume Version；
- DOCX/PDF Resume Export；
- Application、Resume、Export 和 Account 数据删除。

Production 设置 `AI_LABS_ENABLED=false`，前端隐藏 AI Labs，原有 `/resume`、`/copywrite`、`/translate`、`/pdf-summary`、`/csv-preview` 返回 `403 feature_disabled`。代码仍保留，local/test 可通过 `AI_LABS_ENABLED=true` 开启。

## 每日额度

额度按用户和 UTC 日期持久化到 PostgreSQL/SQLite。数据库使用 `(user_id, usage_date, usage_type)` 唯一主键和条件更新，确保并发请求不能突破上限。表单、文件解析、Schema 或输入长度校验失败时不扣减；真正发起模型调用或文件生成后，即使外部服务失败也计入当日用量。

| 操作 | 环境变量 | Production 默认 |
| --- | --- | ---: |
| Career Match 分析 | `CAREER_ANALYSIS_DAILY_LIMIT` | 2 |
| 批量生成简历建议 | `SUGGESTION_GENERATION_DAILY_LIMIT` | 2 |
| 单条建议重新生成 | `SUGGESTION_REGENERATION_DAILY_LIMIT` | 8 |
| Resume Export | `RESUME_EXPORT_DAILY_LIMIT` | 5 |

超额返回 `429 daily_limit_exceeded`，响应只包含额度类型、上限、剩余数和下次 UTC 重置时间。前端登录后显示 Career 分析与建议生成的今日剩余次数。

管理员默认同样受限。只有显式设置 `ADMIN_DAILY_LIMIT_EXEMPT=true` 才豁免管理员；Render Blueprint 固定为 `false`。

## 输入限制

| 输入 | 环境变量 | Production 默认 |
| --- | --- | ---: |
| 简历正文 | `MAX_RESUME_CHARACTERS` | 20,000 字符 |
| 岗位 JD | `MAX_JOB_DESCRIPTION_CHARACTERS` | 20,000 字符 |

超长输入在 Prompt 构造和模型调用前返回 `422 input_too_long`，不消耗额度。

## Session 与文件

- Production Session Cookie：`HttpOnly`、`Secure`、`SameSite=Lax`，默认 12 小时；Cookie 名称由 `SESSION_COOKIE_NAME` 配置。
- Production 不接受 Header Session，前端不把 Session Token 写入 `localStorage`。Header 兼容只保留在 local/test。
- 导出对象默认保留 7 天，R2 bucket 必须保持 Private；下载使用不超过 10 分钟的 presigned GET URL，Blueprint 默认 300 秒。
- 测试者应优先上传去标识化简历，并可随时使用页面内删除入口清理数据。

## Provider 范围

`PRIMARY_LLM_PROVIDER=deepseek`。Production 只要求 `DEEPSEEK_API_KEY`，不会在 DeepSeek 失败后隐式调用 Claude。`ANTHROPIC_API_KEY` 仅用于显式开启 AI Labs 的 local/test 环境。
