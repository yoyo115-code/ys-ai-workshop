# Testing

## 当前已实现

测试使用 Python `unittest`、FastAPI TestClient、系统临时目录中的独立 SQLite 文件和 mock LLM Provider。测试不读取真实 API Key，不调用 DeepSeek 或 Claude，不保留简历、JD 或模型响应。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

当前 58 项后端/静态交付自动化测试包含：

- 认证、权限、管理员隔离和五个 AI Labs 回归。
- Career Match 创建、PDF/DOCX 解析、结构化输出、证据、Prompt Injection、失败与隐私日志。
- Resume Suggestion 严格 Schema，原句、JD 证据和简历证据定位。
- 新数字与新技术名风险、clarification 和高风险接受阻断。
- 接受、拒绝、编辑、Undo、重新生成、幂等与非法状态转换。
- 版本内容、事务回滚、用户隔离、历史排序、Diff 和恢复。
- 前端接受、拒绝、Undo 和生成版本的静态交互契约。
- `GET /`、CSS、`config.js` 和 `app.js` 的状态码与 MIME。
- HTML 资源真实存在、HTTP/file URL 解析、无本地绝对路径，以及 `config.js -> app.js` 的 `defer` 顺序。

## 浏览器验收

`tests/browser/test_frontend_delivery_e2e.py` 提供 4 项可执行 Playwright 用例。Playwright 是可选依赖，未安装时用例会明确 skip，不会影响不需要浏览器二进制的 58 项测试。

```bash
pip install -r tests/browser/requirements.txt
python3 -m playwright install chromium
```

在另一个终端从 `backend/` 启动 `uvicorn app.main:app --reload`，然后执行：

```bash
YS_AI_E2E_BASE_URL=http://127.0.0.1:8000 \
python3 -m unittest tests.browser.test_frontend_delivery_e2e -v
```

浏览器测试覆盖：样式实际应用、SVG 尺寸上限、无横向溢出、登录/注册切换、Career Match 默认显示、Resume Optimizer 与 AI Labs 导航、静态资源失败和控制台阻断性错误。

## 质量检查

```bash
node --check frontend/assets/js/config.js
node --check frontend/assets/js/app.js
git diff --check
```

Python 源码用内置 `compile()` 执行不生成 `__pycache__` 的语法检查。SQLite 检查在内存数据库中执行完整 `schema.sql`，并对基线表依次执行 `0001` 和 `0002` 迁移。API 契约检查从 FastAPI OpenAPI 路径中确认新旧接口存在。

## 当前限制

- Playwright 框架已提供，但浏览器运行时需要开发者在本机单独安装；仓库不提交二进制、截图或报告。
- 模型语义质量在单元测试中由固定 mock 输出验证，不等于线上模型质量评测。
- SQLite 并发写入和大规模数据尚未压测。

## 后续计划

在 CI 中安装 Chromium 并执行已有浏览器用例，再增加 Provider 合约测试、数据库并发/恢复测试和隐私保留周期验证。
