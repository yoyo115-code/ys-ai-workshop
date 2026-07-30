# Y's AI Workshop

> AI-powered career and productivity workspace

Y's AI Workshop 是一个基于 Group B Week 1 Nova AI 智能工作台原型继续维护的个人项目。当前版本提供五个可运行的 AI 工具，并带有本地用户登录、Session 和管理员调用记录。它仍是轻量原型，不是已经完成的求职申请管理产品。

## 当前功能

- Resume Optimizer：优化粘贴的简历片段，强化行动和结果表达。
- Copywriting：根据场景生成中文文案。
- Translation：在中文和英文之间自动判断方向并翻译。
- PDF Summary：提取 PDF 文本并生成摘要。
- CSV Analysis：读取 CSV 样本并给出字段、质量和趋势分析。
- 用户注册、登录、退出和 12 小时 Session。
- 管理员用户统计和 AI 工具调用日志。

五个 AI 工具的接口路径保持为：

| 功能 | 接口 |
| --- | --- |
| Resume Optimizer | `POST /resume` |
| Copywriting | `POST /copywrite` |
| Translation | `POST /translate` |
| PDF Summary | `POST /pdf-summary` |
| CSV Analysis | `POST /csv-preview` |

## 技术栈

- Python、FastAPI、Uvicorn、Pydantic
- 原生 HTML、CSS 和 JavaScript
- SQLite
- OpenAI SDK 兼容方式调用 DeepSeek
- Anthropic Python SDK 调用 Claude
- PyPDF、python-multipart、python-dotenv

## 本地运行

需要 Python 3.10 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在本地 `.env` 中填写需要使用的 AI Provider 密钥。原 Codeup 原型中的旧密钥已经失效或应被撤销，不能继续使用。

如需初始化管理员账号，同时配置 `INITIAL_ADMIN_USERNAME` 和 `INITIAL_ADMIN_PASSWORD`。两者未配置时，程序不会自动创建默认管理员，也没有仓库内置密码。

启动服务：

```bash
uvicorn main:app --reload --port 8001
```

然后访问 `http://127.0.0.1:8001`。首次启动会在本地生成 `platform.db`；该运行数据库已被 Git 忽略。

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API 凭据 |
| `ANTHROPIC_API_KEY` | Anthropic API 凭据 |
| `INITIAL_ADMIN_USERNAME` | 可选的首次管理员账号 |
| `INITIAL_ADMIN_PASSWORD` | 可选的首次管理员密码 |
| `DATABASE_PATH` | 可选的 SQLite 数据库路径 |

不要提交 `.env`、数据库、Session、调用记录或任何真实凭据。

## 当前限制

- Resume Optimizer 当前只接收用户粘贴的文本，还没有解析完整简历并结合岗位 JD。
- PDF 只处理前 8 页可提取文本，不支持扫描件 OCR。
- CSV Analysis 只把有限样本交给模型分析，不是完整数据分析引擎。
- SQLite、Header Session 和单文件前端适合本地原型，不是生产级部署方案。
- 调用日志会保存有限的输入输出预览；正式部署前需要进一步完善隐私和保留策略。
- 仓库暂未提供自动化测试套件，历史测试结果见 `TEST_REPORT.md`。

## 后续方向

下一阶段重点是把 Resume Optimizer 升级为“简历 + Job Description”的求职工作流，包括结构化解析、岗位匹配、缺失关键词、逐条修改建议、简历版本、Cover Letter 和面试准备。上述能力尚未在当前版本实现。

项目来源和基线见 `PROJECT_ORIGIN.md`。
