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

## 静态检查

```bash
python3 -m compileall -q backend/app tests/backend
```

执行后清除本地 `__pycache__`；缓存已被 Git 忽略。

## 修改约束

- 不在 Router 中直接新增 SQL。
- 新增模型调用必须通过 LLM Provider 和 ActivityService。
- 新增 Prompt 放在 `app/prompts/`。
- API 路径变化需要同步 `docs/API.md` 和回归测试。
- Schema 变化需要新增 migration，而不是只修改运行数据库。
