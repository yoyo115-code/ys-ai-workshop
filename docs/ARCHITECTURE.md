# Architecture

## 目标

本阶段把单文件 FastAPI 与内联单页整理为 monorepo，同时保持页面、模型、Prompt 语义、SQLite 数据结构和所有公开 API 路径不变。

## 运行结构

```text
Browser
  ├── GET /                  -> frontend/index.html
  ├── GET /assets/**         -> CSS、config.js、app.js
  └── HTTP API
          ↓
FastAPI app.main
  ├── api/                   -> Router、鉴权依赖
  ├── services/              -> 业务流程、LLM、PDF、CSV、活动记录
  ├── prompts/               -> Prompt 定义
  ├── repositories/          -> SQLite SQL 与连接
  └── core/                  -> 环境配置、密码与 Session 安全
          ↓
SQLite schema.sql / DeepSeek / Anthropic
```

## 后端模块职责

- `app.main`：应用装配、lifespan、CORS、静态文件和 Router 注册。
- `app.api.auth`：登录、注册、退出和当前用户。
- `app.api.career`：现有 `/resume` 简历文本优化。
- `app.api.labs`：文案、翻译、PDF 和 CSV 工具。
- `app.api.admin`：管理员用户统计和活动日志。
- `app.api.system`：健康检查。
- `app.api.dependencies`：Session 用户和管理员权限依赖。
- `app.core.config`：唯一环境变量读取入口。
- `app.core.security`：PBKDF2、密码校验、盐和 Session token。
- `app.repositories.database`：SQLite 连接和 `schema.sql` 初始化。
- `app.repositories.workshop`：用户、Session、活动日志和管理员查询 SQL。
- `app.services.auth`：认证流程和可选管理员初始化。
- `app.services.llm`：DeepSeek、Anthropic Provider 适配。
- `app.services.activity`：AI 调用、错误转换和调用记录。
- `app.services.pdf_processing`、`csv_processing`：确定性文件校验和解析。
- `app.prompts.catalog`：五个工具的 Prompt 定义。

## 依赖方向

Router 只协调请求；业务规则进入 Service；SQL 只存在于 Repository；环境变量只在 Config 中读取。Service 不依赖具体 FastAPI Router，LLM Provider 可以在测试中替换。

## 前端结构

原有视觉 CSS 和交互 JavaScript 已原样提取到独立资源文件。`config.js` 是唯一 API 地址表，`app.js` 不包含生产域名。默认同源请求，也支持部署环境注入 API base URL。

## 数据与安全

- 无默认管理员和演示密码。
- 初始管理员仅在两个环境变量同时有效时创建。
- 密码使用 PBKDF2-SHA256 和独立盐。
- Session token 和密码不会写入应用日志。
- 本地数据库、`.env`、缓存和虚拟环境被 Git 忽略。
- 活动日志仍保存最多 500 字符的业务输入输出预览，这是后续隐私治理项。

## 当前边界

本阶段不引入 SQLAlchemy、异步任务、PostgreSQL、前端框架、Prompt 版本系统或新的 Career Studio 功能。
