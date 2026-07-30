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
- `413`：上传超过 20 MB。
- `502`：外部模型调用失败。
- `503`：所选 Provider 的 API Key 未配置。
