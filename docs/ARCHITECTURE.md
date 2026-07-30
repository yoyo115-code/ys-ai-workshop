# Architecture

## 目标

当前架构在 monorepo 基线上实现 Career Match MVP 和可版本化 Resume Optimizer，同时保持原有五个 AI 工具及其公开 API 路径不变。

## 运行结构

```text
Browser
  ├── GET /                  -> frontend/index.html
  ├── GET /assets/**         -> CSS、config.js、app.js
  └── HTTP API
          ↓
FastAPI app.main
  ├── api/                   -> Router、鉴权依赖
  ├── services/              -> Career、Resume 版本、LLM、文件与活动记录
  ├── prompts/               -> 版本化 Career/Resume Prompt 与旧工具 Prompt
  ├── repositories/          -> Career/Resume/用户 SQLite SQL 与连接
  └── core/                  -> 环境配置、密码与 Session 安全
          ↓
SQLite schema.sql / DeepSeek（Career Match）/ DeepSeek 或 Anthropic（AI Labs）
```

## 后端模块职责

- `app.main`：应用装配、lifespan、CORS、静态文件和 Router 注册。
- `app.api.auth`：登录、注册、退出和当前用户。
- `app.api.career`：Career Application CRUD、结构化分析与原有 `/resume`。
- `app.api.resume_optimizer`：建议生成/决策/Undo、版本创建、列表、Diff 和恢复。
- `app.api.labs`：文案、翻译、PDF 和 CSV 工具。
- `app.api.admin`：管理员用户统计和活动日志。
- `app.api.system`：健康检查。
- `app.api.dependencies`：Session 用户和管理员权限依赖。
- `app.core.config`：唯一环境变量读取入口。
- `app.core.security`：PBKDF2、密码校验、盐和 Session token。
- `app.repositories.database`：SQLite 连接和 `schema.sql` 初始化。
- `app.repositories.workshop`：用户、Session、活动日志和管理员查询 SQL。
- `app.repositories.career`：申请、简历来源、分析和匹配项 SQL。
- `app.repositories.resume`：Resume 聚合、不可变版本、建议状态/事件与版本生成事务。
- `app.services.auth`：认证流程和可选管理员初始化。
- `app.services.llm`：带超时和有限重试的 DeepSeek、Anthropic Provider 适配。
- `app.services.career_match`：保存优先、模型调用、结构校验、证据校验、失败状态与结果组装。
- `app.services.resume_parsing`：PDF 与 DOCX 的确定性解析；扫描 PDF 明确失败。
- `app.services.resume_optimizer`：建议输出 Schema/证据/新事实校验、状态约束、Diff 和用户所有权。
- `app.services.activity`：AI 调用、错误转换和调用记录。
- `app.services.pdf_processing`、`csv_processing`：确定性文件校验和解析。
- `app.prompts.catalog`：五个旧工具的 Prompt 定义。
- `app.prompts.career_match_v1`：版本化 Career Prompt、输入隔离规则与 JSON Schema。
- `app.prompts.resume_suggestion_v1`：句子级建议 Prompt、不可编造规则、非信任输入边界和 Schema 版本。

## 依赖方向

Router 只协调请求；业务规则进入 Service；SQL 只存在于 Repository；环境变量只在 Config 中读取。Service 不依赖具体 FastAPI Router，LLM Provider 可以在测试中替换。

## 前端结构

原生单页以 Career Match 为默认入口，Resume Optimizer 作为第二主流程，旧功能归入 AI Labs。Optimizer 桌面端为“当前文本/版本历史 + 建议卡片”双列布局，窄屏纵向排列，并包含 Loading、Empty、Error、Retry、Undo、保存提示与未保存离开确认。`config.js` 是唯一 API 地址表，`app.js` 不包含生产域名。

## Career Match 数据流

```text
创建申请
  -> 确定性校验与 PDF/DOCX 文本提取
  -> 保存 job_application + resume_source
  -> 创建 analyzing 记录
  -> career_match_v1 Prompt + DeepSeek
  -> Pydantic JSON Schema 校验
  -> JD/简历逐条原文证据校验
  -> 保存 analysis + match_items
```

模型失败只会把分析标记为失败，不删除已保存的申请输入。数据库部分唯一索引保证一个申请最多有一个 `analyzing` 记录；已有成功分析默认直接复用。

## Resume Optimizer 数据流

```text
打开已完成 Career Match 的申请
  -> 幂等初始化 Resume + parsed v1
  -> resume_suggestion_v1 + DeepSeek
  -> Pydantic 严格 Schema
  -> source/JD/resume 证据原文定位
  -> 新数字/技术名/专有名词风险标记
  -> 用户逐条接受 / 拒绝 / 编辑 / 重生成
  -> SQLite 事务应用建议为 optimized 完整快照
  -> 确定性 Diff 或以旧内容新建 restored 快照
```

LLM 只生成受约束的候选建议。证据定位、状态转换、文本替换、哈希、事务、Diff 和恢复均由普通代码完成。

## 数据与安全

- 无默认管理员和演示密码。
- 初始管理员仅在两个环境变量同时有效时创建。
- 密码使用 PBKDF2-SHA256 和独立盐。
- Session token 和密码不会写入应用日志。
- 本地数据库、`.env`、缓存和虚拟环境被 Git 忽略。
- Career Match 日志只记录申请 ID、状态、耗时、Provider、模型和 Prompt 版本，不保存简历、JD 或完整模型响应。
- Resume Optimizer 日志只记录资源 ID、技术状态和建议数量，不保存版本正文、JD、Prompt 或完整模型响应。
- AI Labs 仍保存最多 500 字符的业务输入输出预览，这是后续隐私治理项。

## 当前边界

当前不引入 SQLAlchemy、异步任务、PostgreSQL、前端框架、OCR、版式保真导出、Cover Letter 或面试模拟。Career Match 和建议生成第一版固定使用 DeepSeek，语义结论与事实风险仍需用户复核。
