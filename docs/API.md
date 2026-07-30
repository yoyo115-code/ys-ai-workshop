# API

服务默认地址为 `http://127.0.0.1:8000`。除注册、登录、健康检查和首页外，业务接口使用请求头：

```text
X-Session-Token: <session token>
```

## System

### `GET /health`

返回服务状态和当前 SQLite 文件名。

## Authentication

### `POST /auth/register`

JSON：`username`、`password`、`display_name`。注册角色固定为普通用户，成功返回 Session token 和用户信息。

### `POST /auth/login`

JSON：`username`、`password`。成功返回 Session token 和用户信息。

### `POST /auth/logout`

删除当前请求携带的 Session。

### `GET /auth/me`

返回当前 Session 对应的用户信息。

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

删除当前用户自己的申请及其简历来源、分析和匹配项，成功返回 `204`。

## Admin

### `GET /admin/users`

仅管理员可访问，返回用户和调用次数汇总。

### `GET /admin/logs?limit=100`

仅管理员可访问，返回最近活动记录；`limit` 被限制在 1–500。

## 主要错误

- `400`：请求、Provider 或文件无效。
- `401`：未登录或 Session 失效。
- `403`：普通用户访问管理员接口。
- `409`：用户名重复。
- `409`：Career Match 正在分析，拒绝重复任务。
- `422`：Career Match 输入、简历格式或文本提取无效。
- `413`：上传超过 20 MB。
- `502`：外部模型调用失败。
- `503`：所选 Provider 的 API Key 未配置。
