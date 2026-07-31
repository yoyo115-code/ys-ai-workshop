# API

服务默认地址为 `http://127.0.0.1:8000`。除注册、登录、健康检查和首页外，业务接口使用请求头：

```text
X-Session-Token: <session token>
```

## System

### `GET /health`

兼容旧客户端的健康响应。local/test 返回 SQLite 文件名；production 只返回数据库类型，不暴露连接信息。

### `GET /health/live`

只确认应用进程可响应，成功返回 `200 {"status": "ok"}`。

### `GET /health/ready`

检查数据库和 StorageProvider。全部可用返回 `200`；任一不可用返回 `503`。响应只包含 `ok` / `unavailable`，不返回 URL、bucket、路径或 Secret。

### `GET /config/public`

返回前端可公开读取的环境标识、注册模式、导出保留天数和隐私说明锚点。响应不含内部连接信息或凭据。

## Authentication

### `POST /auth/register`

JSON：`username`、`password`、`display_name`、可选 `invite_code`。注册角色固定为普通用户：

- `open`：不要求邀请码；
- `invite_only`：必须提供有效、未到期且仍有次数的邀请码；
- `disabled`：返回 `403`。

邀请码明文不入库，使用次数更新与用户创建在同一事务中。成功返回 Session token 和用户信息。

### `POST /auth/login`

JSON：`username`、`password`。成功返回 Session token 和用户信息。

### `POST /auth/logout`

删除当前请求携带的 Session。

### `GET /auth/me`

返回当前 Session 对应的用户信息。

### `DELETE /auth/account`

JSON：`password`。验证当前密码后删除账号、Session、活动记录、全部 Application/Resume/Version/Suggestion/Export，并先清理导出对象。对象存储删除失败时返回 `503 data_deletion_incomplete`，数据库记录保留以便重试。

## AI Tools

### `POST /resume`

JSON：`text`、可选 `provider`。优化简历文本。

### `POST /copywrite`

JSON：`scene`、可选 `provider`。生成场景文案。

### `POST /translate`

JSON：`text`、可选 `provider`。自动判断中英文翻译方向。

### `POST /pdf-summary`

Multipart：`file`，可选查询参数 `provider`。仅接受 `.pdf`，单文件最大 20 MB。

### `POST /csv-preview`

Multipart：`file`，可选查询参数 `provider`。仅接受 `.csv`，单文件最大 20 MB。

五个工具默认使用 `deepseek`，也可传 `anthropic`。响应兼容原型，同时包含 `reply` 和 `result`。

## Career Match

以下接口均要求当前用户 Session。用户只能查询或删除自己的申请。

### `POST /career/applications`

Multipart fields：

- `resume_text`：简历文本；与 `resume_file` 二选一。
- `resume_file`：可选 `.pdf` 或 `.docx` 文件，最大 20 MB；不保存原始文件。
- `job_description`：必填的岗位 JD。
- `company_name`、`job_title`、`location`：可选岗位元数据。
- `language`：`zh`、`en` 或 `bilingual`，默认 `zh`。

成功返回 `201` 和已保存申请详情。扫描 PDF 或无文本文件返回 `422`，响应包含稳定错误码和已保存的 `application_id`，历史记录会标为 `parse_failed`。

### `GET /career/applications`

返回当前用户最近 50 条申请摘要，按更新时间倒序排列。

### `GET /career/applications/{application_id}`

返回当前用户自己的申请、提取后的简历文本、解析状态和最近一次成功分析。其他用户的记录统一返回 `404`。

### `POST /career/applications/{application_id}/analyze`

可选 JSON：`{"retry": false}`。

- 默认情况下，已有成功结果会直接复用，不再次调用模型。
- `retry: true` 显式创建新一次分析。
- 同一申请正在分析时返回 `409`。
- API Key 未配置返回 `503`；Provider 失败或超时返回 `502 provider_failure`；非法 JSON 或证据不符合原文约束返回 `502 invalid_model_output`。

成功响应包含：

- `overall_alignment`：仅为 `strong_alignment`、`partial_alignment`、`significant_gaps`、`insufficient_evidence` 之一。
- `covered_requirements`
- `partially_covered_requirements`
- `missing_requirements`
- `uncertain_requirements`
- `resume_expression_issues`
- `qualification_risks`
- `summary`
- `analysis_limitations`
- Provider、模型、Prompt 版本和创建时间。

每个匹配项包含 JD 原文、简历证据、解释与证据充分程度。接口不返回百分比或录用概率。

### `DELETE /career/applications/{application_id}`

删除当前用户自己的申请及其简历来源、分析、匹配项、Resume、Version、Suggestion、Export，并先清理关联导出对象，成功返回 `204`。

## Resume Optimizer & Versioning

以下接口均要求 Session，并从当前用户反向校验 Application、Resume、Version 和 Suggestion 所有权；越权资源统一返回 `404`。

### `POST /career/applications/{application_id}/resume-suggestions/generate`

可选 JSON：`{"retry": false}`。以当前 ResumeVersion、JD 和最新 Career Match 上下文生成逐条建议。已有活跃建议时默认复用；`retry: true` 会把旧活跃建议标记为 `superseded` 并新建一批。

每条包含原句、建议句、理由、JD/简历证据、风险、是否需要补充事实、状态、生成次数和 Prompt 版本。

### `GET /career/applications/{application_id}/resume-suggestions`

打开已保存工作区。如果该申请尚无 Resume，会从已提取的简历文本幂等初始化 Resume 和 v1，不会调用模型。

### `PATCH /career/resume-suggestions/{suggestion_id}`

JSON：

- `{"action": "accept"}`
- `{"action": "reject"}`
- `{"action": "edit", "suggested_text": "...", "confirm_risk": false}`

相同的接受/拒绝操作幂等。非法状态转换返回 `409`。`high` 风险或 `clarification_required` 的模型建议不能直接接受，必须手工编辑并显式确认。

### `POST /career/resume-suggestions/{suggestion_id}/regenerate`

只重新生成该原句建议。新建议的 `generation_number` 递增，旧建议变为 `superseded`，旧记录和事件保留。

### `POST /career/resume-suggestions/{suggestion_id}/undo`

撤销该建议最近一次可撤销的接受、拒绝或编辑事件，并追加 Undo 事件。

### `POST /career/applications/{application_id}/resume-versions`

将当前版本上的 `accepted` 和经用户确认的 `edited` 建议应用为新的 `optimized` 完整文本快照。插入版本和更新当前指针位于同一 SQLite 事务，冲突或失败不保留半成品。

### `GET /career/resumes/{resume_id}/versions`

按 `version_number` 倒序返回当前用户该 Resume 的不可变完整文本快照。

### `DELETE /career/resumes/{resume_id}`

删除当前用户的 Resume、全部 Version/Suggestion/Export 和关联导出对象，但保留原 Job Application。成功返回 `204`。

### `GET /career/resume-versions/{version_id}`

返回版本内容、哈希、来源、父版本和创建时间。

### `GET /career/resume-versions/{version_id}/compare/{other_version_id}`

使用确定性文本 Diff 返回 `added`、`deleted` 或 `modified` 变更，不调用 LLM。两个版本必须属于同一 Resume。

### `POST /career/resume-versions/{version_id}/restore`

以目标历史内容创建新的 `restored` 快照，不删除历史或移动指针到旧行。

## Resume Export & Delivery

以下接口均要求 Session，并通过 ResumeVersion 反向校验当前用户。响应不返回本地绝对路径或内部 `object_key`。

### `GET /career/resume-versions/{version_id}/preview`

对归属当前用户的 ResumeVersion 做确定性结构化，返回：

- 版本、Resume、公司和岗位元数据；
- `source_content_hash`；
- `parse_status`: `structured` 或 `needs_review`；
- 可编辑的 `StructuredResume` 与解析警告。

Schema 保留 `original_text`，不调用 LLM，不推断缺失事实。无可导出文本时返回 `422 structure_unavailable`。

### `POST /career/resume-versions/{version_id}/exports`

JSON：

```json
{
  "template_key": "professional",
  "format": "docx",
  "paper_size": "a4",
  "language": "bilingual"
}
```

- `template_key`: `professional` 或 `minimal_ats`。
- `format`: `docx` 或 `pdf`。
- `paper_size`: `a4` 或 `letter`。
- `language`: `zh`、`en` 或 `bilingual`。
- `resume`: 可选的用户确认 Schema；未传时使用当前确定性解析结果。`original_text` 必须与源版本一致。

成功返回 `201` 和 `ready` 记录，并写入由 `EXPORT_RETENTION_DAYS` 计算的 UTC `expires_at`。渲染失败保留 `failed` 记录并清理不完整文件；缺少渲染依赖或 CJK 字体时返回稳定错误码。

### `GET /career/resume-exports?version_id={version_id}`

返回当前用户最近 50 条未删除导出，可按归属当前用户的 `version_id` 过滤。

### `GET /career/resume-exports/{export_id}`

返回导出元数据、状态、文件名、内容哈希和可用的 `download_url`。已到期但尚未清理的 ready 记录以计算状态 `expired` 返回。

### `GET /career/resume-exports/{export_id}/download`

只允许下载当前用户未到期的 `ready` 文件。DOCX 返回 Open XML `Content-Type`，PDF 返回 `application/pdf`；`Content-Disposition` 使用已清理的姓名_公司_岗位_版本文件名。本地存储由鉴权 API 返回字节；S3-compatible 存储返回短期 presigned redirect。到期文件返回 `410 export_expired`。

### `DELETE /career/resume-exports/{export_id}`

校验用户命名空间后删除本地/S3 对象，并将记录软删除为 `deleted`。成功返回 `204`。对象已不存在时操作仍可幂等收敛。

## Admin

### `GET /admin/users`

仅管理员可访问，返回用户和调用次数汇总。

### `GET /admin/logs?limit=100`

仅管理员可访问，返回最近活动记录；`limit` 被限制在 1–500。

## 主要错误

- `400`：请求、Provider 或文件无效。
- `401`：未登录或 Session 失效。
- `403`：普通用户访问管理员接口。
- `403`：注册关闭、邀请码无效/到期/用尽，或账号删除密码错误。
- `409`：用户名重复。
- `409`：Career Match 正在分析，拒绝重复任务。
- `409`：建议状态转换非法、高风险未确认，或版本无可用建议/原句冲突。
- `409`：导出预览的 `original_text` 与源 ResumeVersion 不一致，或文件尚未就绪。
- `422`：Career Match 输入、简历格式或文本提取无效。
- `422`：结构化简历无可渲染内容，或文档渲染输入无效。
- `413`：上传超过 20 MB。
- `502`：外部模型调用失败。
- `503`：所选 Provider 的 API Key 未配置。
- `503`：DOCX/PDF 渲染依赖或必需的 CJK 字体不可用。
- `503`：readiness 依赖不可用或数据对象删除未完成。
- `410`：导出已到期或物理对象已不存在。
