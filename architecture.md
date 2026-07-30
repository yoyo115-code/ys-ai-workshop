# Nova AI Platform — 架构设计文档

> 版本：v1.0 · 日期：2026-06-18 · 作者：Rita_Yu

---

## 目录

1. [架构选型理由](#1-架构选型理由)
2. [架构总览](#2-架构总览)
3. [技术选型与工具](#3-技术选型与工具)
4. [后端模块结构](#4-后端模块结构)
5. [依赖库说明](#5-依赖库说明)
6. [分层架构（后端）](#6-分层架构后端)
7. [接口规范](#7-接口规范)
8. [功能请求链路](#8-功能请求链路)
9. [命名约定](#9-命名约定)
10. [错误处理规范](#10-错误处理规范)
11. [配置与密钥管理](#11-配置与密钥管理)
12. [已知限制与技术债](#12-已知限制与技术债)
13. [优化策略](#13-优化策略)

---

## 1. 架构选型理由

### 核心约束

| 约束 | 说明 |
|------|------|
| 时间 | 1 天内完成可演示版本 |
| 团队基础 | 成员 Python 水平参差，部分同学后端经验较薄弱 |
| 功能范围 | 5 个独立 AI 工具，用户系统、持久化 |
| 演示场景 | 本地运行 + 浏览器访问，无需公网部署 |

### 选型决策

**选择 FastAPI + 单文件前端（而非 Django / Flask + React 前后端分离）的理由：**

1. **零构建工具**：单个 `index.html` 不需要 npm、Webpack、Vite，任何成员都能直接打开理解
2. **FastAPI 开箱即用**：自动生成 `/docs` 交互文档，便于调试接口；`Pydantic` 提供请求体校验，减少手写校验代码
3. **单文件后端易于协作**：`main.py` 一眼看完所有路由，不需要理解项目目录结构才能改代码
4. **LLM 调用统一抽象**：`call_llm()` 函数把 DeepSeek 和 Anthropic 两个提供商封装在一处，切换只改 `.env`，不改业务代码
5. **可演进**：单文件结构在功能增加后可以自然拆分为多模块

**没有选择的方案及理由：**

- `Flask`：无内置异步支持、无自动 API 文档、校验需手写，学习收益比 FastAPI 低
- `Django`：ORM、Admin、模板引擎复杂，等对本项目是过度工程
- `React / Vue 前端`：引入 Node.js 工具链，对后端方向同学是额外负担，本项目 UI 交互简单不需要组件化

---

## 2. 架构总览

### 系统架构图

```
┌──────────────────────────────────────────────────────────────┐
│                       浏览器 (Client)                         │
│                                                              │
│   index.html  ─── HTML 结构                                  │
│   (内嵌 CSS)  ─── 样式 / 响应式布局                           │
│   (内嵌 JS)   ─── fetch 请求 / DOM 操作 / 状态管理            │
│                                                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                  HTTP/1.1  (localhost:8000)
                           │
          ┌────────────────┴────────────────┐
          │  GET /          (HTML 页面)      │
          │  POST /resume                   │
          │  POST /copywrite                │
          │  POST /translate                │
          │  POST /pdf-summary  (multipart) │
          │  POST /csv-preview  (multipart) │
          └────────────────┬────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    FastAPI 后端 (main.py)                      │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  路由层      │──▶│  业务逻辑层   │──▶│   LLM 适配层     │  │
│  │  @app.xxx   │   │  call_llm()  │   │  Provider 选择   │  │
│  └─────────────┘   └──────────────┘   └────────┬─────────┘  │
│                                                │             │
│  ┌────────────────────────────────────────┐   │             │
│  │           配置层 (.env)                │   │             │
│  │  LLM_PROVIDER / API Keys              │   │             │
│  └────────────────────────────────────────┘   │             │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                          ┌─────────────────────┴──────────────────────┐
                          │                                             │
               ┌──────────▼──────────┐                   ┌────────────▼────────────┐
               │    Anthropic API    │                   │      DeepSeek API       │
               │  claude-sonnet-4-6  │                   │      deepseek-chat      │
               │  api.anthropic.com  │                   │    api.deepseek.com     │
               └─────────────────────┘                   └─────────────────────────┘
```

### 数据流方向

```
用户输入 ──▶ 前端 JS 序列化 ──▶ HTTP POST ──▶ FastAPI 路由
    ──▶ Pydantic 校验 ──▶ call_llm() ──▶ LLM API
    ──▶ 返回文本 ──▶ JSON 响应 ──▶ 前端 DOM 更新 ──▶ 用户看到结果
```

---

## 3. 技术选型与工具

### 运行时与框架

| 层 | 技术 | 版本约束 | 选型理由 |
|----|------|----------|----------|
| 后端语言 | Python | ≥ 3.10 | 团队主语言；AI 库生态最完整 |
| Web 框架 | FastAPI | 最新稳定版 | 异步原生、自动文档、Pydantic 集成 |
| ASGI 服务器 | Uvicorn | 最新稳定版 | FastAPI 官方推荐，启动命令简单 |
| 前端 | Vanilla HTML/CSS/JS | — | 零依赖，无构建步骤，所见即所得 |

### LLM 提供商

| 提供商 | 模型 | SDK | 用途 |
|--------|------|-----|------|
| DeepSeek | `deepseek-chat` | `openai`（兼容接口） | 默认提供商，成本低 |
| Anthropic | `claude-sonnet-4-6` | `anthropic` | 备用提供商，能力更强 |

> DeepSeek 使用 OpenAI SDK 的原因：DeepSeek 兼容 OpenAI API 格式，通过设置 `base_url` 即可复用，无需额外学习新 SDK。

### 开发工具

| 工具 | 用途 |
|------|------|
| `python-dotenv` | 读取 `.env` 环境变量，隔离密钥与代码 |
| FastAPI `/docs` | 自动生成的 Swagger UI，本地调试接口无需 Postman |
| `.gitignore` | 防止 `__pycache__` 和 `.env` 进入版本库 |

---

## 4. 后端模块结构

### 当前文件结构

```
my-ai-platform/
├── main.py              # 后端全部逻辑（路由 + 业务 + LLM 适配）
├── index.html           # 前端全部逻辑（HTML + CSS + JS）
├── .env                 # 环境变量（不提交 git）
├── .gitignore
├── requirements.txt     # Python 依赖声明
└── __pycache__/         # Python 编译缓存（自动生成，不提交）
```

### main.py 内部结构（逻辑分区）

```python
main.py
│
├── [初始化区]
│   ├── 环境变量加载 (load_dotenv)
│   ├── FastAPI 实例创建
│   ├── LLM 客户端初始化
│   │   ├── anthropic.Anthropic(...)
│   │   └── openai.OpenAI(base_url="deepseek")
│   └── PROVIDER 读取（环境变量决定路由到哪个 LLM）
│
├── [数据模型区] Pydantic Models
│   ├── TextRequest   { text: str }
│   └── SceneRequest  { scene: str }
│
├── [工具函数区]
│   └── call_llm(system, user) -> str
│       └── 根据 PROVIDER 分流到 DeepSeek 或 Anthropic
│
└── [路由区] API Endpoints
    ├── GET  /              → 返回 index.html
    ├── POST /resume        → 简历优化
    ├── POST /copywrite     → 文案生成
    ├── POST /translate     → 翻译润色
    ├── POST /pdf-summary   → PDF 摘要（TODO）
    └── POST /csv-preview   → CSV 分析
```

---

## 5. 依赖库说明

```
requirements.txt
```

| 库 | 作用 | 是否直接使用 |
|----|------|-------------|
| `fastapi` | Web 框架核心；提供路由、请求解析、响应序列化 | 是 |
| `uvicorn` | ASGI 服务器；执行 `uvicorn main:app --reload` | 是（运行时） |
| `anthropic` | Anthropic 官方 Python SDK；调用 Claude 系列模型 | 是 |
| `openai` | OpenAI Python SDK；同时用于调用兼容接口的 DeepSeek | 是 |
| `python-dotenv` | 从 `.env` 文件加载环境变量到 `os.environ` | 是 |
| `python-multipart` | FastAPI 处理 `multipart/form-data` 文件上传的依赖 | 间接（FastAPI 需要） |

> **注意**：`pdfplumber` 未在 requirements.txt 中，但 PDF 摘要功能（`/pdf-summary`）的完整实现需要它。当前该端点返回占位文本，是已知技术债。

---

## 6. 分层架构（后端）

### 当前实现：单层结构

当前 `main.py` 是**单文件平铺**结构，路由、业务逻辑、LLM 调用混在一起。这是1天开发约束下的合理选择，但不是理想分层。

```
现状（单文件）：
┌─────────────────────────────────────┐
│            main.py                  │
│  路由 + 业务逻辑 + LLM 适配 混合     │
└─────────────────────────────────────┘
```

### 理想分层：三层结构

```
理想（三层）：
┌─────────────────────────────────────┐
│          Router 层（表示层）          │
│  负责：HTTP 方法 / URL 定义 / 请求校验 │
│  文件：routers/resume.py 等          │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│          Service 层（业务层）          │
│  负责：Prompt 构建 / 业务规则 / 编排   │
│  文件：services/resume_service.py 等  │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│          LLM 适配层（基础层）          │
│  负责：provider 选择 / SDK 调用封装   │
│  文件：llm/client.py                 │
└─────────────────────────────────────┘
```

**各层职责边界：**

| 层 | 允许做的事 | 不允许做的事 |
|----|-----------|-------------|
| Router | 接收请求、返回响应、参数校验 | 直接调用 LLM SDK |
| Service | 构建 Prompt、组织逻辑 | 了解 HTTP 细节 |
| LLM 适配层 | 调用 SDK、处理重试 | 包含业务逻辑 |

---

## 7. 接口规范

### 通用约定

- **基础 URL**：`http://localhost:8000`
- **请求格式**：`application/json`（文件上传用 `multipart/form-data`）
- **响应格式**：`application/json`
- **响应结构**：所有成功响应统一返回 `{ "reply": "<string>" }`

### 端点清单

#### GET /
- **描述**：返回前端页面
- **响应**：HTML 文档（`text/html`）

---

#### POST /resume
- **描述**：简历优化
- **请求体**：
  ```json
  { "text": "负责公司后端开发工作，参与接口设计..." }
  ```
- **字段**：`text` (string, required) — 原始简历片段
- **响应**：
  ```json
  { "reply": "【优化后简历内容】" }
  ```

---

#### POST /copywrite
- **描述**：文案生成
- **请求体**：
  ```json
  { "scene": "给一款低糖夏日奶茶写朋友圈文案..." }
  ```
- **字段**：`scene` (string, required) — 场景描述
- **响应**：
  ```json
  { "reply": "【生成的文案】" }
  ```

---

#### POST /translate
- **描述**：翻译 / 润色
- **请求体**：
  ```json
  { "text": "需要翻译的文本" }
  ```
- **字段**：`text` (string, required)
- **响应**：
  ```json
  { "reply": "【翻译结果】" }
  ```

---

#### POST /pdf-summary
- **描述**：PDF 摘要（功能开发中）
- **请求体**：`multipart/form-data`，字段名 `file`，类型 `.pdf`
- **响应**（当前）：
  ```json
  { "reply": "PDF 摘要功能开发中" }
  ```

---

#### POST /csv-preview
- **描述**：CSV 表格分析
- **请求体**：`multipart/form-data`，字段名 `file`，类型 `.csv`
- **响应**：
  ```json
  { "reply": "【CSV 结构和字段分析】" }
  ```

### 前端字段映射表

前端 JS 中 `FIELD` 对象定义了功能名到请求字段名的映射，是前后端契约的核心：

```javascript
// index.html 中的契约声明
const FIELD = {
  resume:    "text",   // POST /resume    → { "text": ... }
  copywrite: "scene",  // POST /copywrite → { "scene": ... }
  translate: "text",   // POST /translate → { "text": ... }
};
```

---

## 8. 功能请求链路

### 文本类功能链路（简历 / 文案 / 翻译）

```
用户在 textarea 输入内容
         │
         ▼
前端：点击按钮触发 submitText(feature)
         │
         ├─ 校验：input.value.trim() 为空 → 显示错误，中止
         │
         ▼
前端：fetch(`/${feature}`, { method: "POST", body: JSON.stringify({[FIELD[feature]]: text}) })
         │
         ▼
FastAPI：Pydantic 自动校验请求体结构
         │
         ├─ 校验失败 → 422 Unprocessable Entity → 前端显示错误
         │
         ▼
路由函数：调用 call_llm(system_prompt, user_input)
         │
         ▼
call_llm()：读取 PROVIDER 环境变量
         │
         ├─ "deepseek" → deepseek_client.chat.completions.create(...)
         │                    model: "deepseek-chat"
         │
         └─ 其他     → anthropic_client.messages.create(...)
                            model: "claude-sonnet-4-6"
         │
         ▼
LLM API 返回文本
         │
         ▼
路由函数：return { "reply": text }
         │
         ▼
前端：解析 payload.reply → 写入 DOM → 用户看到结果
```

---

### 文件上传类功能链路（PDF / CSV）

```
用户点击上传区域选择文件
         │
         ▼
前端：onFileChosen(type) 触发
         │
         ├─ validateFile()：校验扩展名和 MIME 类型
         │   └─ 不合法 → 清空 input，显示错误，中止
         │
         ▼
前端：点击按钮触发 submitFile(type, endpoint)
         │
         ├─ 再次 validateFile() → 不合法则中止
         │
         ▼
前端：构造 FormData，append("file", file)
     fetch(endpoint, { method: "POST", body: formData })
         │
         ▼
FastAPI：python-multipart 解析 multipart/form-data
         │
         ▼
路由函数：await file.read()
         │
         │── /csv-preview：decode UTF-8，截取前 2000 字符 → call_llm()
         │
         └── /pdf-summary：（TODO：pdfplumber 解析 → call_llm()）
                           当前直接返回占位文本
         │
         ▼
前端：解析 payload.reply → 写入 DOM
```

---

## 9. 命名约定

### HTTP 接口命名

| 规则 | 示例 | 说明 |
|------|------|------|
| URL 全小写 + 连字符 | `/pdf-summary` | 不用驼峰，不用下划线 |
| 动词隐含在 HTTP 方法中 | `POST /resume` | URL 本身是名词，不写 `/do-resume` |
| 资源名用单数 | `/resume` 非 `/resumes` | 本项目是操作型接口，非 REST 资源接口 |

### 请求体字段命名

| 功能 | 字段名 | 类型 | 说明 |
|------|--------|------|------|
| 简历优化 | `text` | string | 通用文本字段 |
| 翻译润色 | `text` | string | 通用文本字段 |
| 文案生成 | `scene` | string | 语义化命名，区别于纯文本 |
| 文件上传 | `file` | File | multipart 字段名，前后端固定 |

> **关键约定**：前端 `FIELD` 对象 (`index.html:983`) 与后端 Pydantic Model 字段名 (`main.py:23-27`) 必须严格一致。修改任何一侧都必须同步修改另一侧。

### 响应体字段命名

所有端点统一使用 `reply` 字段返回 AI 输出结果：

```python
return {"reply": text}   # 后端固定格式
```

```javascript
const reply = payload.reply;  // 前端固定读取
```

### Python 代码命名

| 类型 | 约定 | 示例 |
|------|------|------|
| 函数 / 变量 | `snake_case` | `call_llm`, `pdf_summary` |
| 类（Pydantic Model） | `PascalCase` | `TextRequest`, `SceneRequest` |
| 常量 / 全局配置 | `UPPER_SNAKE_CASE` | `PROVIDER`, `anthropic_client` |
| 路由路径 | 小写 + 连字符 | `"/pdf-summary"` |

### 前端命名

| 类型 | 约定 | 示例 |
|------|------|------|
| DOM ID | `{功能}-{元素}` | `resume-input`, `pdf-btn` |
| JS 函数 | `camelCase` | `switchTab()`, `submitText()` |
| CSS 类 | `kebab-case` | `.tab-btn`, `.output-area` |

---

## 10. 错误处理规范

### HTTP 状态码约定

| 状态码 | 场景 | 前端行为 |
|--------|------|----------|
| 200 | 请求成功，`reply` 字段包含结果 | 显示结果 |
| 422 | 请求体结构不合法（Pydantic 自动返回） | 显示错误信息 |
| 500 | 后端异常（LLM API 调用失败等） | 显示"请求失败"提示 |

### 前端错误处理策略

```javascript
// index.html 中的统一错误处理模式
if (!response.ok) {
    throw new Error(formatError(response, payload));
}
// catch 块：setOutput(feature, error.message, "error")
```

前端区分三类错误状态：
- **`placeholder`**：等待中 / 提示性文字（灰色）
- **`error`**：请求失败 / 校验失败（红色背景）
- **无 class**：成功结果（正常显示）

### 当前后端的错误处理缺口

当前 `call_llm()` 未捕获 LLM API 异常，若 API Key 失效或网络超时会直接返回 500。**后续改进**：在 `call_llm()` 内增加 `try/except`，返回结构化错误信息。

---

## 11. 配置与密钥管理

### .env 文件结构

```bash
ANTHROPIC_API_KEY=<Anthropic 密钥>
DEEPSEEK_API_KEY=<DeepSeek 密钥>
LLM_PROVIDER=deepseek   # 可选值: "deepseek" | "anthropic"
```

### 切换 LLM 提供商

只需修改 `.env` 中的 `LLM_PROVIDER`，重启服务即可，不需要改代码：

```
LLM_PROVIDER=anthropic  → 使用 Claude claude-sonnet-4-6
LLM_PROVIDER=deepseek   → 使用 DeepSeek deepseek-chat（默认）
```

**设计意图**：DeepSeek 作为日常默认（成本低），Anthropic 作为高质量备用，一行配置切换。

### 安全规范

- `.env` 已加入 `.gitignore`，**绝不提交到 Git**
- 密钥仅通过 `os.getenv()` 读取，不硬编码在源码中
- `requirements.txt` 不包含版本锁定（演示项目可接受；生产项目应使用 `pip freeze > requirements.txt`）

---

## 12. 已知限制与技术债

| 编号 | 问题 | 影响 | 优先级 |
|------|------|------|--------|
| T-01 | PDF 摘要功能未实现，返回占位文本 | 功能不可用 | 高 |
| T-02 | `pdfplumber` 未在 requirements.txt 中 | PDF 功能实现后需补充 | 高 |
| T-03 | `call_llm()` 无异常捕获 | LLM 报错直接 500 | 中 |
| T-04 | 无用户认证 / 鉴权 | 任何人均可调用，API 密钥暴露风险 | 中（演示可接受） |
| T-05 | CSV 读取硬截断 2000 字符 | 大文件分析不完整 | 低 |
| T-06 | 无请求频率限制 | 演示场景可接受，上线需加 | 低 |
| T-07 | System Prompt 均为 TODO 占位 | AI 输出质量未优化 | 中 |

---

## 13. 优化策略

以下是从当前单文件结构逐步演进的路径，按优先级排列。

### 阶段一：拆分后端结构（下一个项目）

当功能超过 5 个或需要多人并行开发时，将 `main.py` 拆分为：

```
my-ai-platform/
├── main.py                  # 仅保留 app 初始化和路由注册
├── routers/
│   ├── __init__.py
│   ├── text_tools.py        # resume / copywrite / translate
│   └── file_tools.py        # pdf_summary / csv_preview
├── services/
│   ├── __init__.py
│   └── llm_service.py       # call_llm() 和 Prompt 管理
├── llm/
│   ├── __init__.py
│   └── client.py            # SDK 初始化、Provider 切换
├── models/
│   ├── __init__.py
│   └── schemas.py           # 所有 Pydantic 模型
└── config.py                # 统一配置读取
```

### 阶段二：Prompt 管理（同阶段一）

将各功能的 System Prompt 从路由函数中抽离，集中到 `services/prompts.py`：

```python
PROMPTS = {
    "resume":    "你是资深职场顾问，专注于提炼结果表达和行动动词...",
    "copywrite": "你是品牌文案策划，善于用简洁语言传递情感...",
    "translate": "你是翻译专家，优先保持自然表达而非字面翻译...",
}
```

### 阶段三：前后端分离（复杂项目）

当前端交互变复杂（多步流程、状态管理、组件复用）时，引入：

- **后端**：保持 FastAPI，增加 CORS 配置，支持前端跨域调用
- **前端**：迁移到 Vue 3（推荐：对后端同学友好，模板语法直观）或 React
- **构建**：Vite（构建速度快，配置简单）

### 阶段四：生产化（上线场景）

| 方向 | 方案 |
|------|------|
| 部署 | Docker + Nginx 反向代理 |
| 密钥管理 | 环境变量注入（不依赖 `.env` 文件） |
| 异常监控 | Sentry 集成 |
| API 限流 | `slowapi`（基于 FastAPI 的限流中间件） |
| 鉴权 | JWT Token 或 API Key 验证 |
| 日志 | 结构化日志（`loguru` 或 `structlog`） |
| 依赖锁定 | `pip freeze > requirements.lock` 或使用 `uv` |
