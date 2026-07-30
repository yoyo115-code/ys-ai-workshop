# Development

## 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

从仓库根目录维护 `.env`。禁止提交真实密钥、数据库、Session 或活动日志。

## 启动后端和页面

```bash
cd backend
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。FastAPI 同时提供页面、静态资源和 API。

## 分离运行前端

前端没有构建依赖，可使用任意静态服务器提供 `frontend/`。分离运行时：

1. 在 `frontend/index.html` 的 `api-base-url` meta 中配置本地 API 地址，或由部署环境在 `config.js` 前注入 `window.YS_AI_API_BASE_URL`。
2. 在根 `.env` 的 `CORS_ORIGINS` 中加入前端来源，多个来源用逗号分隔。
3. 不要把生产域名直接写入 `app.js`。

## 测试

```bash
pip install -r backend/requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

测试使用 mock LLM Provider 和临时 SQLite，不需要真实 API Key。

Career Match 测试不得调用真实 DeepSeek。结构化 Provider mock 必须返回符合 `MatchAnalysisPayload` 的 JSON；测试还会主动覆盖非法 JSON、超时、无证据 `covered` 和 Prompt Injection。

## 静态检查

```bash
python3 -m compileall -q backend/app tests/backend
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

## SQLite migration 检查

`database/schema.sql` 用于全新数据库，`database/migrations/0001_career_match.sql` 用于审查本阶段的增量。可以在系统临时目录创建空数据库，依次执行 schema 和 migration，确认两者均可重复执行；不要对仓库中的真实运行数据库做检查。
