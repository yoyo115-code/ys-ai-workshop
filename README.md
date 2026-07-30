# Y's AI Workshop

> AI-powered career and productivity workspace

Y's AI Workshop 是一个从 Group B Week 1 Nova AI 智能工作台原型继续演进的个人项目。当前版本保留五个可运行的 AI 工具、用户 Session 和管理员调用记录，并完成了 frontend、backend、database、docs、tests 的 monorepo 工程化整理。

当前仍是轻量原型，不是已经完成的 Career Studio，也没有实现“简历 + JD”岗位匹配。

## 当前功能

- Resume Optimizer：优化用户粘贴的简历片段。
- Copywriting：根据场景生成中文文案。
- Translation：自动判断中英文翻译方向。
- PDF Summary：提取 PDF 前 8 页文本并生成摘要。
- CSV Analysis：读取有限 CSV 样本并给出分析建议。
- 用户注册、登录、退出和 12 小时 Session。
- 管理员用户统计和 AI 工具活动日志。

## 项目结构

```text
ys-ai-workshop/
├── frontend/                  # 原生 HTML/CSS/JavaScript 页面
│   ├── assets/css/app.css
│   ├── assets/js/app.js
│   ├── assets/js/config.js
│   └── index.html
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI APIRouter
│   │   ├── core/              # 配置与密码安全
│   │   ├── models/            # 领域类型
│   │   ├── prompts/           # Prompt 定义
│   │   ├── repositories/      # SQLite 数据访问
│   │   ├── schemas/           # Pydantic 请求模型
│   │   ├── services/          # 认证、LLM、日志、PDF、CSV
│   │   └── main.py            # 应用装配与启动入口
│   ├── requirements.txt
│   └── requirements-dev.txt    # 测试额外依赖
├── database/                  # schema、迁移和 seed 约定
├── docs/                      # 架构、API、数据库和开发文档
├── tests/backend/             # 不访问真实模型的回归测试
├── .env.example
├── .gitignore
├── PROJECT_ORIGIN.md
└── README.md
```

## 技术栈

- Python 3.10+、FastAPI、Uvicorn、Pydantic
- 原生 HTML、CSS、JavaScript
- SQLite 与 Python `sqlite3`
- OpenAI SDK 兼容方式调用 DeepSeek
- Anthropic Python SDK 调用 Claude
- PyPDF、python-multipart、python-dotenv
- Python `unittest` 与 FastAPI TestClient

本阶段没有引入 SQLAlchemy；Repository 层继续使用 `sqlite3`，以避免结构拆分和数据库重写同时发生。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

在 `.env` 中填写至少一个 AI Provider 的密钥。需要管理员时，必须同时配置管理员账号和密码；未配置时不会创建默认管理员。

```bash
cd backend
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。后端会提供首页和 `/assets` 静态资源。

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API 凭据 |
| `ANTHROPIC_API_KEY` | Anthropic API 凭据 |
| `INITIAL_ADMIN_USERNAME` | 可选的首次管理员账号 |
| `INITIAL_ADMIN_PASSWORD` | 可选的首次管理员密码 |
| `DATABASE_URL` | SQLite URL，默认 `sqlite:///./platform.db` |
| `CORS_ORIGINS` | 逗号分隔的允许来源；同源运行可留空 |

真实 `.env`、数据库、Session、日志、虚拟环境和缓存均不得提交。

## API 路径

现有接口保持不变：

- `POST /resume`
- `POST /copywrite`
- `POST /translate`
- `POST /pdf-summary`
- `POST /csv-preview`
- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /admin/users`
- `GET /admin/logs`
- `GET /health`

完整契约见 `docs/API.md`。

## 前端 API 配置

默认使用同源 API。所有路径集中在 `frontend/assets/js/config.js`。部署时可通过以下任一方式设置 API base URL：

- 修改 `frontend/index.html` 的 `api-base-url` meta 配置；
- 在加载 `config.js` 前由部署环境注入 `window.YS_AI_API_BASE_URL`。

仓库不硬编码生产域名。

## 测试

测试使用临时 SQLite 文件和 mock LLM Provider，不会请求真实模型：

```bash
pip install -r backend/requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

## 当前限制

- Resume Optimizer 只处理粘贴文本，尚未结合完整简历文件和岗位 JD。
- PDF 不支持 OCR，且只读取前 8 页可提取文本。
- CSV 仅抽取有限样本，不是完整分析引擎。
- SQLite 和 Header Session 适合本地原型，不是最终生产方案。
- 活动日志仍保留有限输入输出预览，需要进一步完善隐私和保留周期。
- 前端仍是原生单页，尚未建立组件化构建和浏览器自动化测试。

## Career Studio 路线图

后续计划将 Resume Optimizer 升级为“简历 + Job Description”的求职工作流，包括结构化解析、岗位匹配、缺失关键词、逐条修改建议、版本管理、Cover Letter 和面试准备。这些能力尚未实现，本阶段只完成工程结构重构。

项目来源见 `PROJECT_ORIGIN.md`，开发说明见 `docs/DEVELOPMENT.md`。
