# Development

## 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

从仓库根目录维护 `.env`。禁止提交真实密钥、数据库、Session 或活动日志。

Resume Export 默认把运行文件写到 `backend/generated/`，可用 `RESUME_EXPORT_DIR` 切换到受控私有目录。不要把用户导出的 DOCX/PDF 放入源码或 Git。local 默认 `STORAGE_BACKEND=local`、`REGISTRATION_MODE=open`；不要在开发环境伪装 production 配置。

## 数据库模式

本地默认 SQLite：

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./platform.db
```

production 只允许 PostgreSQL，并要求先执行：

```bash
cd backend
alembic upgrade head
```

SQLAlchemy 2 只作为连接/事务适配器，新增 SQL 仍应放在 Repository。Alembic revision 是 production schema 的唯一升级入口；`database/schema.sql` 用于本地 SQLite 基线。

## Private Beta 本地配置

邀请码流程需要非空 `SESSION_SECRET` 和 `REGISTRATION_MODE=invite_only`。管理员 CLI：

```bash
cd backend
python -m app.cli.create_invite --max-uses 5 --expires-in-days 14
```

数据库有多个管理员时增加 `--admin-username`。CLI 输出的明文邀请码只能通过私密渠道传递，不得写入测试 fixture、日志或截图。

过期导出清理可本地执行：

```bash
python -m app.jobs.cleanup_expired_exports
```

production 需要外部 scheduler 调用；应用进程不会自行启动隐藏定时器。

## 启动后端和页面

```bash
cd backend
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。FastAPI 同时提供页面、静态资源和 API。

不要把双击 `frontend/index.html` 当作完整运行方式。`file://` 没有 FastAPI 服务器、Session API 和可靠的 HTTP origin，因此只支持带样式的静态预览。文件模式会在页面顶部显示启动命令和正确地址。

## 静态资源交付

`backend/app/main.py` 将 `frontend/assets/` mount 到 `/assets`，并在 `GET /` 返回 `frontend/index.html`。HTML 使用唯一一组相对引用：

```text
./assets/css/app.css
./assets/js/config.js
./assets/js/app.js
```

在 `http://127.0.0.1:8000/` 下，这些路径解析为 FastAPI 的 `/assets/...`；在文件预览中，它们解析为 `frontend/assets/...`。`config.js` 和 `app.js` 都使用 `defer`，且配置文件必须排在业务脚本之前。

## 分离运行前端

前端没有构建依赖，可使用任意静态服务器提供 `frontend/`。分离运行时：

1. 在 `frontend/index.html` 的 `api-base-url` meta 中配置本地 API 地址，或由部署环境在 `config.js` 前注入 `window.YS_AI_API_BASE_URL`。
2. 在根 `.env` 的 `CORS_ORIGINS` 中加入前端来源，多个来源用逗号分隔。
3. 不要把生产域名直接写入 `app.js`。

API base URL 只能通过下列任一入口设置：

- `frontend/index.html` 的 `meta[name="api-base-url"]`；
- 加载 `config.js` 前由部署环境注入 `window.YS_AI_API_BASE_URL`。

`app.js` 只使用 `window.YS_AI_CONFIG`，不包含本地绝对路径或生产域名。

## 测试

```bash
pip install -r backend/requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

测试使用 mock LLM Provider 和临时 SQLite，不需要真实 API Key。

Career Match 测试不得调用真实 DeepSeek。结构化 Provider mock 必须返回符合 `MatchAnalysisPayload` 的 JSON；测试还会主动覆盖非法 JSON、超时、无证据 `covered` 和 Prompt Injection。

### 浏览器测试

Playwright 是独立测试依赖，不进入默认后端依赖，浏览器二进制、报告和截图也不提交。GitHub Actions 会在临时 runner 安装 Chromium 并执行。

```bash
pip install -r tests/browser/requirements.txt
python3 -m playwright install chromium
```

先按本文启动 Uvicorn，再从仓库根目录执行：

```bash
YS_AI_E2E_BASE_URL=http://127.0.0.1:8000 \
python3 -m unittest tests.browser.test_frontend_delivery_e2e -v
```

用例检查主样式、邀请制认证面板、Private Beta/隐私提示、Career Match 默认页、Resume Optimizer/AI Labs 导航、Resume Export、SVG 尺寸、390px 横向溢出、资源失败和控制台 error。

Resume Export 的手动验收顺序：

1. 登录后打开一条已完成 Career Match 的 Resume Optimizer。
2. 选择任意 ResumeVersion，点击 `Export`。
3. 核对结构化字段、预览、模板、格式、纸张和语言。
4. 分别生成 DOCX 和 PDF，确认状态为 `ready`，可重复下载，文件名含姓名/公司/岗位/版本。
5. 用 Word、WPS 或 LibreOffice 打开 DOCX，并用 PDF 阅读器核对中英文、项目符号和分页。
6. 删除测试导出，确认历史和物理文件同步清理。

## 排查 CSS / JavaScript 404

1. 确认浏览器地址是 `http://127.0.0.1:8000`，不是 `file://.../index.html`。
2. 直接打开 `/assets/css/app.css`、`/assets/js/config.js` 和 `/assets/js/app.js`，确认均为 `200`。
3. 检查 CSS 的 `Content-Type` 为 `text/css`，JavaScript 为 `text/javascript`。
4. 检查启动目录是 `backend/`，且 `frontend_dir` 指向仓库的 `frontend/`。
5. 如使用分离静态服务器，再核对 API base URL 和 `CORS_ORIGINS`。

## 静态检查

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -c "from pathlib import Path; [compile(p.read_text(), str(p), 'exec') for p in Path('backend').rglob('*.py')]"
node --check frontend/assets/js/config.js
node --check frontend/assets/js/app.js
```

执行后清除本地 `__pycache__`；缓存已被 Git 忽略。

## 修改约束

- 不在 Router 中直接新增 SQL。
- 新增模型调用必须通过 LLM Provider 和 ActivityService。
- 新增 Prompt 放在 `app/prompts/`。
- Career Match Prompt 必须保留版本常量，修改语义约束时新增版本而不是静默覆盖历史含义。
- API 路径变化需要同步 `docs/API.md` 和回归测试。
- Schema 变化需要新增 migration，而不是只修改运行数据库。
- Career Match 活动日志只允许记录申请 ID 和技术元数据，禁止传入简历、JD 或模型完整响应。
- 文档渲染只能使用确认后 `StructuredResume`；导出不得调用 LLM 补全或润色。
- 下载名不得作为内部路径；文件读写必须限定在 `RESUME_EXPORT_DIR`。

## Migration 检查

测试从空 SQLite 执行 Alembic 到 head，并离线编译 PostgreSQL SQL，确认没有 `PRAGMA` / `AUTOINCREMENT`。GitHub Actions 使用真实 PostgreSQL service 执行 migration 和 Repository round-trip。不要对真实运行数据库做实验性 migration。

## Production 配置排查

- `/health/live` 失败：应用进程或端口问题。
- `/health/ready` 返回 503：检查数据库和存储资源；响应不会给出连接值。
- 启动提示配置不完整：只按提示的变量名到 Secret Manager 检查，不要打印 `.env`。
- production 禁止 SQLite、本地存储、开放注册和通配 CORS；不得临时放宽来掩盖资源故障。
