# Testing

## 当前已实现

测试使用 Python `unittest`、FastAPI TestClient、系统临时目录中的独立 SQLite 文件和 mock LLM Provider。测试不读取真实 API Key，不调用 DeepSeek 或 Claude，不保留简历、JD 或模型响应。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/backend -v
```

当前 53 项自动化测试包含：

- 认证、权限、管理员隔离和五个 AI Labs 回归。
- Career Match 创建、PDF/DOCX 解析、结构化输出、证据、Prompt Injection、失败与隐私日志。
- Resume Suggestion 严格 Schema，原句、JD 证据和简历证据定位。
- 新数字与新技术名风险、clarification 和高风险接受阻断。
- 接受、拒绝、编辑、Undo、重新生成、幂等与非法状态转换。
- 版本内容、事务回滚、用户隔离、历史排序、Diff 和恢复。
- 前端接受、拒绝、Undo 和生成版本的静态交互契约。

## 质量检查

```bash
node --check frontend/assets/js/config.js
node --check frontend/assets/js/app.js
git diff --check
```

Python 源码用内置 `compile()` 执行不生成 `__pycache__` 的语法检查。SQLite 检查在内存数据库中执行完整 `schema.sql`，并对基线表依次执行 `0001` 和 `0002` 迁移。API 契约检查从 FastAPI OpenAPI 路径中确认新旧接口存在。

## 当前限制

- 前端目前只有静态交互契约和手工验收，尚无 Playwright 等真浏览器端到端测试。
- 模型语义质量在单元测试中由固定 mock 输出验证，不等于线上模型质量评测。
- SQLite 并发写入和大规模数据尚未压测。

## 后续计划

在部署前增加真浏览器端到端测试、Provider 合约测试、数据库并发/恢复测试和隐私保留周期验证。
