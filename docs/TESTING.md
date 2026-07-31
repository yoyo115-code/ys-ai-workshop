# Testing

## 后端套件

测试使用合成数据、mock LLM Provider 和系统临时目录，不读取真实 Key，不调用 DeepSeek/Claude，不保留用户材料。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend \
python3 -m unittest discover -s tests/backend -v
```

当前发现 122 项：本机 121 通过，1 项需要 PostgreSQL service 的 integration test 明确 skip。GitHub Actions 提供 PostgreSQL 并执行该用例。

覆盖范围：

- 既有 86 项认证、Career Match、Resume Optimizer、Resume Export、AI Labs 和静态资源回归。
- production 配置 fail-fast、SQLite 禁止回退、错误不泄露配置值。
- SQLAlchemy 参数适配、SQLite round-trip 和 PostgreSQL Repository integration。
- Alembic SQLite upgrade、PostgreSQL offline SQL 和 Private Beta revision。
- Local/S3 storage contract、用户命名空间、随机 key、目录穿越和 presigned URL。
- 邀请必填/无效/过期/用尽/成功、明文不落库和重复用户名事务回滚。
- 导出到期、410 响应、7 天默认保留和清理幂等。
- Application、Resume、Account 删除及物理对象清理。
- 文档日志不保留正文，其他预览脱敏邮箱、电话和凭据。
- live/ready、Storage 故障 503 和公开配置无 Secret。

## PostgreSQL

本地有 PostgreSQL 时：

```bash
cd backend
APP_ENV=test DATABASE_URL="$TEST_POSTGRES_URL" alembic upgrade head
cd ..
PYTHONPATH=backend python3 -m unittest tests.backend.test_postgresql_integration -v
```

不要把真实生产连接串用于测试。CI 使用一次性 `postgres:17-alpine` service 和合成账号。

## Browser

```bash
pip install -r tests/browser/requirements.txt
python3 -m playwright install chromium
```

启动测试服务后：

```bash
YS_AI_E2E_BASE_URL=http://127.0.0.1:8000 \
python3 -m unittest tests.browser.test_frontend_delivery_e2e -v
```

7 项 Playwright 用例覆盖样式、图标边界、邀请注册、Private Beta 标识、隐私/保留提示、账号删除入口、Career/Optimizer/AI Labs 导航、Resume Export、静态资源、控制台 error 和 390px 响应式。

本轮还通过 in-app Browser 对真实 HTTP 页面人工验收：CSS/config.js/app.js 均 200；桌面 1280px 和小屏 390px 无横向溢出，最大 SVG 32px，控制台没有 error。

## 静态与安全检查

```bash
node --check frontend/assets/js/config.js
node --check frontend/assets/js/app.js
git diff --check
git ls-files
```

Python 语法检查应避免保留 `__pycache__`；检查后删除生成缓存。敏感扫描只报告文件和类型，绝不输出完整值。Git 跟踪检查必须拒绝 `.env`、数据库、导出 DOCX/PDF、用户材料、浏览器二进制、截图和依赖目录。

## Docker / CI

CI 分为：

1. 固定 Python 依赖安装；
2. SQLite 完整测试；
3. PostgreSQL migration/integration；
4. Python/JavaScript 语法；
5. Playwright Chromium；
6. Git 跟踪安全；
7. Docker build。

本机没有 Docker daemon，因此容器构建和真实 PostgreSQL execution 不能在本地宣称通过；它们由 GitHub Actions 验证。Dockerfile 的静态检查仍需确认非 root `USER`、HEALTHCHECK、固定基线和 `.dockerignore`。

## 发布验收

在受控 Beta 环境使用去标识化材料完成：migration、live/ready、邀请码注册、Career Match、建议/版本、DOCX/PDF、重复下载、主动删除、到期清理和账号删除。检查日志不得出现简历、JD、密码、邀请码、Token、Key 或 presigned URL。
