# Y's AI Workshop

![Y's AI Workshop logo](frontend/assets/brand/logo-lockup.svg)

Project Website:
https://yoyo115-code.github.io/ys-ai-workshop/

> AI-powered career and productivity workspace

Y's AI Workshop 是一个以求职材料为核心的 AI 工作台。用户可以保存简历与岗位 JD，获得引用原文证据的匹配分析，逐条审阅简历建议，保存不可变版本，并从确认内容生成 DOCX/PDF。五个原型 AI Labs 仍保留在代码中，但 Production Private Beta 默认关闭。

当前版本是 **Deployable Private Beta**：应用具备 PostgreSQL、Cloudflare R2/S3-compatible 私有对象存储、邀请制注册、数据删除、日额度、Secure Cookie、Render Blueprint、健康检查和 CI 能力。仓库不会自动代表已经上线，当前没有公开 URL 或真实用户研究结果。

## Brand Identity

几何化的 **Y** 代表项目品牌，上扬的 **Check** 代表岗位匹配、简历优化和可交付结果；蓝紫色表达可信、智能与职业成长。使用规范见 [Brand Guidelines](docs/BRAND_GUIDELINES.md)。

## 已实现功能

- Career Match：粘贴简历或上传 PDF/DOCX，保存公司、岗位和 JD。
- 可解释匹配：输出已覆盖、部分覆盖、缺失、信息不足、表达问题和岗位风险，并引用输入证据。
- Resume Optimizer：逐条接受、拒绝、编辑、重新生成和 Undo；高风险建议不能直接接受。
- Resume Versioning：不可变文本快照、历史、Diff 和恢复。
- Resume Export：确定性结构化预览，`professional` / `minimal_ats` 两模板，DOCX/PDF、A4/Letter 和中英文内容。
- Private Beta：`open` / `invite_only` / `disabled` 注册模式，邀请码只保存哈希并限制次数与有效期。
- 数据生命周期：导出默认保留 7 天，可幂等清理；用户可删除导出、Resume、Application 或整个账号。
- 生产数据边界：本地/测试使用 SQLite 与本地存储；production 只允许 PostgreSQL 与 S3-compatible 私有存储。
- 运维：live/ready 探针、Alembic migration、非 root Docker 镜像和 PostgreSQL/浏览器/容器 CI。
- Launch guardrails：四类按用户/UTC 日期持久化额度、20,000 字符输入上限、Production Secure Cookie 和 DeepSeek-only 默认路径。
- Render Blueprint：Singapore Docker Web Service、Render PostgreSQL、Alembic pre-deploy migration、readiness 检查和手动 Secret 注入。
- AI Labs：Resume Optimizer 原型接口、Copywriting、Translation、PDF Summary、CSV Analysis；local/test 可开启，Production 返回 `feature_disabled`。

## 项目结构

```text
ys-ai-workshop/
├── frontend/                  # 原生 HTML/CSS/JavaScript 单页
├── backend/
│   ├── alembic/               # PostgreSQL/SQLite 有序 migration
│   ├── app/
│   │   ├── api/               # FastAPI Router
│   │   ├── cli/               # 管理员邀请码 CLI
│   │   ├── core/              # 配置与安全
│   │   ├── jobs/              # 幂等保留期清理任务
│   │   ├── prompts/           # 版本化 Prompt
│   │   ├── repositories/      # 显式 SQL 数据访问
│   │   ├── schemas/           # Pydantic 契约
│   │   └── services/          # 业务、LLM、存储、隐私与文档渲染
│   ├── alembic.ini
│   ├── requirements.txt
│   └── requirements-dev.txt
├── database/                  # SQLite schema 与可读增量 SQL
├── docs/                      # 产品、架构、部署、隐私和运维文档
├── tests/
│   ├── backend/               # mock Provider、迁移和生产就绪测试
│   └── browser/               # Playwright 浏览器验收
├── .github/workflows/ci.yml
├── Dockerfile
└── .env.example
```

## 技术栈

- Python 3.12、FastAPI、Uvicorn、Pydantic
- SQLAlchemy 2 连接/事务适配、Alembic migration
- SQLite（local/test）、PostgreSQL（production）
- LocalStorageProvider、S3-compatible StorageProvider、boto3
- OpenAI-compatible SDK / DeepSeek、Anthropic SDK / Claude
- PyPDF、python-docx、ReportLab
- 原生 HTML、CSS、JavaScript
- `unittest`、FastAPI TestClient、Playwright、GitHub Actions、Docker

SQLAlchemy 仅用于数据库可移植性、连接池和事务边界；现有 Repository 仍使用显式 SQL，没有在同一阶段重写成 ORM。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env
cd backend
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。双击 `frontend/index.html` 只提供带样式的静态提示页，登录和业务流程必须通过 HTTP 服务。

本地默认配置：

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./platform.db
STORAGE_PROVIDER=local
REGISTRATION_MODE=open
EXPORT_RETENTION_DAYS=7
AI_LABS_ENABLED=true
SESSION_COOKIE_SECURE=false
```

Career Match 和 Resume Suggestion 默认使用 DeepSeek；选择 Anthropic 的 AI Labs 需要本地显式开启并配置对应 Key。Production 不要求 `ANTHROPIC_API_KEY`，DeepSeek 失败后不会隐式调用 Claude。

## 生产配置

production 必须使用 PostgreSQL、S3-compatible 私有存储和邀请制注册；缺少关键配置会在启动阶段失败，且错误不显示变量值。完整变量见 [.env.example](.env.example) 与 [Deployment](docs/DEPLOYMENT.md)。

主要变量：

| 变量 | 用途 |
| --- | --- |
| `APP_ENV` | `development`、`test` 或 `production` |
| `DATABASE_URL` | 本地 SQLite 或生产 PostgreSQL URL |
| `STORAGE_PROVIDER` | `local` 或 `s3`；兼容旧名 `STORAGE_BACKEND` |
| `S3_BUCKET_NAME` / `S3_*` | 私有 bucket、区域、endpoint 和访问凭据；bucket 兼容旧名 `S3_BUCKET` |
| `DEEPSEEK_API_KEY` | Production 唯一默认 AI Provider 凭据 |
| `PRIMARY_LLM_PROVIDER` / `AI_LABS_ENABLED` | Production 分别为 `deepseek` / `false` |
| `INITIAL_ADMIN_*` | 可选的一次性初始管理员；必须成对配置，无默认密码 |
| `REGISTRATION_MODE` | `open`、`invite_only` 或 `disabled` |
| `EXPORT_RETENTION_DAYS` | 导出保留天数，默认 7 |
| `CORS_ORIGINS` | 逗号分隔的明确来源；production 禁止 `*` |
| `SESSION_SECRET` | 邀请码 HMAC Secret；production 至少 32 字符 |
| `SESSION_COOKIE_NAME` / `SESSION_COOKIE_SECURE` | Production Session Cookie 名称与 HTTPS-only 开关 |
| `*_DAILY_LIMIT` | Career 分析、建议生成/重生成和导出的 UTC 日额度 |
| `MAX_*_CHARACTERS` | 简历与 JD 模型调用前字符上限 |

Production Session 使用 `HttpOnly; Secure; SameSite=Lax` Cookie，默认 12 小时。前端不将 Session Token 写入 `localStorage`；`X-Session-Token` 只保留给 local/test 兼容。

生产部署先运行：

```bash
cd backend
alembic upgrade head
```

再启动应用。production 不会静默回退到 SQLite 或本地文件存储。

## Render Blueprint

根目录 [render.yaml](render.yaml) 定义 Singapore 区域的 Starter Docker Web Service 和 `basic-256mb` Render PostgreSQL。选择 Render Dashboard 的 **New → Blueprint** 并连接此 Private GitHub 仓库后，先填写 Blueprint 提示的 Secret，再创建资源。`preDeployCommand` 执行 `alembic upgrade head`，容器监听 `0.0.0.0:$PORT`。

Cloudflare R2 使用 `S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` 和 `S3_REGION=auto`；bucket 必须保持 Private。下载由短时 presigned GET URL 完成，默认 300 秒且代码限制不超过 600 秒。详见 [Deployment](docs/DEPLOYMENT.md) 与 [Beta Limits](docs/BETA_LIMITS.md)。

## 管理员邀请与清理任务

数据库中已有唯一可识别的 active admin 时：

```bash
cd backend
python -m app.cli.create_invite --max-uses 5 --expires-in-days 14
```

若有多个管理员，增加 `--admin-username <username>`。明文邀请码只显示一次，数据库只保存哈希。

过期导出清理：

```bash
cd backend
python -m app.jobs.cleanup_expired_exports
```

任务可重复执行；production 应由平台 scheduler 定时调用。

## Docker

```bash
docker build -t ys-ai-workshop:private-beta .
docker run --rm -p 8000:8000 --env-file /secure/path/ys-ai.env ys-ai-workshop:private-beta
```

镜像使用固定 Python 基线和固定 Python 依赖，安装 CJK 字体，并以非 root 用户运行。迁移应作为独立 release job 先执行。

## API

既有 Career Match、Resume Optimizer、Resume Export 和五个 AI Labs 路径保持不变。Private Beta 新增：

- `GET /health/live`
- `GET /health/ready`
- `GET /config/public`
- `GET /usage/daily`
- `DELETE /auth/account`
- `DELETE /career/resumes/{resume_id}`

`POST /auth/register` 新增可选 `invite_code`；是否必填由 `REGISTRATION_MODE` 决定。完整契约见 [API](docs/API.md)。

## 测试

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend \
python3 -m unittest discover -s tests/backend -v

node --check frontend/assets/js/config.js
node --check frontend/assets/js/app.js
```

当前后端发现 147 项：本地 146 通过，1 项需要 PostgreSQL service 的 integration test 如实跳过；GitHub Actions 使用 PostgreSQL 17 service 先执行 Alembic migration，再在完整套件中运行该用例。测试使用合成数据和 mock LLM，不调用真实模型。

浏览器测试覆盖 Private Beta 标识、邀请码表单、隐私/保留提示、核心导航、静态资源、控制台错误和 390px 响应式布局。运行方式见 [Testing](docs/TESTING.md)。

## 当前限制

- Render Blueprint 已定义云数据库和 Web Service，但仍需人工授权 Private GitHub、填写 Secret、确认付费计划并点击创建；目前没有公开部署 URL。
- 尚未进行真实 Beta 用户研究、可用性访谈或求职结果评估。
- 已有持久化每日额度和 Secure Cookie，但仍没有通用 IP 级流量清洗、恶意文件扫描或完整 CSRF 策略。
- 过期清理 job 已实现，但需要部署平台配置 scheduler；没有自动验证云端备份恢复。
- S3-compatible 实现已通过 mock contract test；本机没有 Docker/PostgreSQL，因此真实 PostgreSQL 用例由 CI 执行。
- Resume Export 不还原原始 PDF/DOCX 像素级版式；没有 OCR。
- 中文 PDF 需要运行环境具有 CJK 字体；Docker 镜像已安装 Noto CJK，本地环境缺失时会明确失败。
- 没有 Cover Letter、面试模拟、公开分享链接、异步队列或新 AI Labs。

项目来源见 [PROJECT_ORIGIN.md](PROJECT_ORIGIN.md)，部署和隐私边界见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) 与 [docs/PRIVACY.md](docs/PRIVACY.md)。
