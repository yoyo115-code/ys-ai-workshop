# Y's AI Workshop

> AI-powered career and productivity workspace

Y's AI Workshop 是一个从 Group B Week 1 Nova AI 智能工作台原型继续演进的个人项目。当前版本以 Career Match、Resume Optimizer 和 Resume Export 为核心：用户可以保存简历与岗位 JD，获得引用原文证据的结构化匹配分析，逐条审阅建议并保存不可变版本，最后从确认内容生成可下载的 DOCX/PDF。原有五个工具继续作为 AI Labs 保留。

项目仍是本地优先的 MVP。当前已完成岗位匹配、版本化文本优化和两模板文档交付闭环，但不保留用户原始 PDF/DOCX 的像素级版式，也尚未实现 Cover Letter、面试模拟或分享协作。

## 当前功能

- Career Match：粘贴简历文本或上传 PDF/DOCX，保存目标岗位与 JD。
- 可解释匹配：按已覆盖、部分覆盖、缺失、信息不足、表达问题和岗位风险展示原文证据。
- 申请工作区：按用户保存、重开、重试和删除申请；模型失败不会丢失简历与 JD。
- 防编造校验：模型 JSON 先经过 Pydantic Schema，再验证 JD 与简历引用确实来自输入原文。
- Resume Optimizer：对当前版本生成可接受、拒绝、编辑、单条重新生成和 Undo 的句子级建议。
- 事实风险防护：确定性校验原句与双向证据，检测新数字、技术名和专有名词；高风险建议不能直接接受。
- 版本管理：将已接受/编辑建议事务化生成不可变文本快照，支持历史、Diff 和恢复。
- Resume Export：确定性结构化 ResumeVersion，用户可在导出前校对字段。
- 文档交付：提供 `professional` 和 `minimal_ats` 两个模板，支持 A4/Letter、中文/英文/双语标题、DOCX/PDF 生成、历史、重复下载和删除。
- 导出安全：文件名规范化、内部对象名隔离、路径穿越防护、原子写入、内容哈希和用户所有权校验。

- AI Labs / Resume Optimizer：保留原型的单次简历片段优化接口。
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
│   │   ├── repositories/      # SQLite 数据访问与 Career 仓储
│   │   ├── schemas/           # Pydantic 请求与结构化分析模型
│   │   ├── services/          # 认证、LLM、文件解析与匹配流程
│   │   └── main.py            # 应用装配与启动入口
│   ├── requirements.txt
│   └── requirements-dev.txt    # 测试额外依赖
├── database/                  # schema、迁移和 seed 约定
├── docs/                      # 架构、API、数据库和开发文档
├── tests/
│   ├── backend/             # mock Provider 与静态交付测试
│   └── browser/             # 可选 Playwright 浏览器验收
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
- PyPDF、标准库 DOCX XML 解析、python-docx、ReportLab、python-multipart、python-dotenv
- Python `unittest` 与 FastAPI TestClient

本阶段没有引入 SQLAlchemy；Repository 层继续使用 `sqlite3`，以避免结构拆分和数据库重写同时发生。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Career Match 第一版需要 `DEEPSEEK_API_KEY`；AI Labs 可使用 DeepSeek 或 Anthropic。需要管理员时，必须同时配置管理员账号和密码；未配置时不会创建默认管理员。

```bash
cd backend
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。后端会提供首页和 `/assets` 静态资源。

正式本地使用必须通过上述 HTTP 地址。双击 `frontend/index.html` 只是带样式的文件预览；页面会显示正确启动命令，登录、API 和业务功能不以 `file://` 为运行方式。

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API 凭据 |
| `ANTHROPIC_API_KEY` | Anthropic API 凭据 |
| `INITIAL_ADMIN_USERNAME` | 可选的首次管理员账号 |
| `INITIAL_ADMIN_PASSWORD` | 可选的首次管理员密码 |
| `DATABASE_URL` | SQLite URL，默认 `sqlite:///./platform.db` |
| `CORS_ORIGINS` | 逗号分隔的允许来源；同源运行可留空 |
| `LLM_TIMEOUT_SECONDS` | 模型请求超时秒数，安全示例为 `45` |
| `LLM_MAX_RETRIES` | Provider SDK 的有限重试次数，安全示例为 `2` |
| `RESUME_EXPORT_DIR` | 可选的私有导出目录；默认为 `backend/generated` |

真实 `.env`、数据库、Session、日志、虚拟环境和缓存均不得提交。

## API 路径

Career Match 新增：

- `POST /career/applications`
- `GET /career/applications`
- `GET /career/applications/{application_id}`
- `POST /career/applications/{application_id}/analyze`
- `DELETE /career/applications/{application_id}`

Resume Optimizer & Versioning 新增：

- `POST /career/applications/{application_id}/resume-suggestions/generate`
- `GET /career/applications/{application_id}/resume-suggestions`
- `PATCH /career/resume-suggestions/{suggestion_id}`
- `POST /career/resume-suggestions/{suggestion_id}/regenerate`
- `POST /career/resume-suggestions/{suggestion_id}/undo`
- `POST /career/applications/{application_id}/resume-versions`
- `GET /career/resumes/{resume_id}/versions`
- `GET /career/resume-versions/{version_id}`
- `GET /career/resume-versions/{version_id}/compare/{other_version_id}`
- `POST /career/resume-versions/{version_id}/restore`

Resume Export & Delivery 新增：

- `GET /career/resume-versions/{version_id}/preview`
- `POST /career/resume-versions/{version_id}/exports`
- `GET /career/resume-exports`
- `GET /career/resume-exports/{export_id}`
- `GET /career/resume-exports/{export_id}/download`
- `DELETE /career/resume-exports/{export_id}`

原有接口保持不变：

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

测试使用临时 SQLite 文件和 mock LLM Provider，不会请求真实模型。当前覆盖 86 项后端/静态交付自动化测试，包括原有匹配与版本回归，以及 DOCX/PDF 内容、分页、中英文、两个模板、事务、文件状态、下载响应、所有权和路径安全：

```bash
pip install -r backend/requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

`tests/browser/` 另提供 5 项可执行 Playwright 验收，并保留真实 HTTP 浏览器验收步骤；浏览器依赖和二进制不进入仓库。命令见 `docs/TESTING.md`。

## 当前限制

- Career Match 只分析用户主动提供的简历和 JD，不验证经历真实性，也不预测录用概率。
- Career Match 不支持 OCR；扫描版 PDF 会明确返回无法提取文字。
- 第一版 Career Match 固定使用 DeepSeek，不进行双模型比较。
- 匹配依赖模型对原始要求的拆分；引用经过原文校验，但语义判断仍可能需要用户复核。
- Resume Optimizer 目前对结构化纯文本工作，不保留原 PDF/DOCX 版式，且精确重复原句会因歧义阻止生成版本。
- Resume Export 只渲染确认后的结构化文本，不恢复原始文件的字体、双栏、照片或像素级版式。
- PDF 与 DOCX 内容来自同一 Schema；中文 PDF 需要运行环境具有可用的 CJK 字体，缺失时会明确失败。
- 导出当前为同步本地文件存储；没有对象存储、自动过期清理、公开分享或多实例任务队列。
- 新事实风险检测为保守启发式，可能误报，不替代用户核查。
- AI Labs 的 PDF Summary 不支持 OCR，且只读取前 8 页可提取文本。
- CSV 仅抽取有限样本，不是完整分析引擎。
- SQLite 和 Header Session 适合本地原型，不是最终生产方案。
- Career Match 活动日志不保存简历、JD 或模型完整响应；旧 AI Labs 仍保留有限预览，需要继续完善保留周期。
- 前端仍是原生单页，尚未建立组件化构建；Playwright 浏览器测试为可选开发依赖，仓库不提交浏览器二进制。

## Career Studio 路线图

Career Match、可版本化 Resume Optimizer 和两模板 Resume Export 已组成本地求职主流程。原始文件版式完全还原、Cover Letter、面试准备、分享与公开部署仍是后续计划。

项目来源见 `PROJECT_ORIGIN.md`，开发说明见 `docs/DEVELOPMENT.md`。
