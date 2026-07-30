# Resume Export & Delivery

## 用户问题

Career Match 和 Resume Optimizer 已能生成、比较和恢复确认后的文本版本，但用户仍需手工复制到 Word 才能投递。Phase 4 的目标是把指定 `ResumeVersion` 转换为可检查的结构化简历，并从同一份结构化数据稳定生成 DOCX 和 PDF。

## 用户故事

- 用户可以从任意属于自己的 ResumeVersion 打开导出工作区。
- 用户可以预览并修正确定性解析得到的结构化字段。
- 用户可以选择 `professional` 或 `minimal_ats` 模板、中文/英文和 A4/Letter 纸张。
- 用户可以生成并下载 DOCX 或 PDF，重复打开历史导出记录。
- 下载文件名包含姓名、公司、岗位和版本，但不包含数据库路径或内部存储名。
- 用户不能预览、生成、下载或删除其他用户的版本与导出文件。

## 第一版范围

- 对 ResumeVersion 文本做确定性结构化，不调用 LLM，不改写内容。
- 提供可编辑的结构化预览；用户显式提交的编辑作为该次导出的确认快照保存。
- 直接生成 DOCX；使用同一 Schema 直接生成 PDF。
- 同步生成、小文件本地私有存储、导出状态、历史、下载、删除与失败重试。
- 输出 `professional` 和 `minimal_ats` 两个模板。

## 非目标

- 不做拖拽设计器、任意配色、复杂双栏、照片或技能进度条。
- 不承诺还原上传 PDF/DOCX 的原始像素级版式。
- 不开发 Cover Letter、面试、公开分享、OCR、部署或新 AI Labs。
- 不使用 LLM 补全姓名、经历、日期、技能或其他缺失事实。

## 导出流程

```text
选择 ResumeVersion
  -> 校验用户所有权
  -> 确定性结构化文本
  -> 返回 Schema + 原始文本 + 解析提示
  -> 用户检查/编辑结构化字段
  -> 选择模板、格式、语言和纸张
  -> 创建 pending 记录
  -> generating
  -> 写入随机内部文件名的临时文件
  -> 原子移动为最终文件
  -> ready + 安全下载名 + 内容哈希
```

失败时记录变为 `failed`，清理临时或不完整文件，不得进入 `ready`。删除时先校验文件位于专用导出目录，再删除文件并软删除记录。

## Resume Schema

```text
StructuredResume
  original_text
  basics
    name, email, phone, location, links[], summary
  education[]
    organization, title, location, start_date, end_date, bullet_points[]
  experience[]
    organization, title, location, start_date, end_date, bullet_points[]
  projects[]
    organization, title, location, start_date, end_date, bullet_points[]
  skills[]
  certifications[]
  awards[]
  additional_information[]
```

`original_text` 始终保留 ResumeVersion 原文。解析器只识别明确标题、联系方式和原有行，不推断事实；无法可靠形成内容区块时返回明确 `structure_unavailable`，前端仍可查看原文。用户编辑后的 Schema 只用于该次导出，并连同来源版本和来源哈希保存，保证可追溯。

## 模板设计

### professional

- 单栏、清晰姓名与联系方式标题区、克制的深蓝标题层级。
- 使用稳定段落和真实项目符号，不使用照片、图表或技能进度条。
- 适合商业、咨询、金融和数据分析岗位。

### minimal_ats

- 单栏、黑色标准字体、简单大写/粗体章节标题。
- 不使用表格、文本框、图标、页眉装饰或多栏布局。
- 保持文本读取顺序和项目符号顺序，优先 ATS 可解析性。

## API

- `GET /career/resume-versions/{version_id}/preview`
- `POST /career/resume-versions/{version_id}/exports`
- `GET /career/resume-exports`
- `GET /career/resume-exports/{export_id}`
- `GET /career/resume-exports/{export_id}/download`
- `DELETE /career/resume-exports/{export_id}`

创建请求包含模板、格式、语言、纸张和用户确认的 `resume` Schema。响应不返回 `storage_path`。下载响应必须具有准确 `Content-Type` 和安全的 `Content-Disposition`。

## 数据模型

`resume_exports` 保存：用户、Resume、ResumeVersion、模板、格式、纸张、语言、状态、安全下载名、内部存储路径、来源内容哈希、结构化快照、输出哈希、错误码、创建/更新时间、过期和删除时间。

同一版本、模板、格式和结构化内容允许再次生成独立记录；每条记录有独立状态和文件，避免覆盖历史。所有状态转换和文件写入由 Service 协调，SQL 由 Repository 管理。

## 安全与隐私

- 所有 Version、Resume 和 Export 通过当前用户反向校验。
- 内部文件使用导出 ID/随机后缀，不使用用户文件名作为路径。
- 下载名移除路径分隔符、控制字符和非法字符，并限制总长度。
- 服务只解析位于专用导出根目录内的已记录路径，阻止目录穿越。
- 导出内容不包含 API Key、Prompt、匹配风险、活动日志或内部 ID。
- 日志只记录导出 ID、格式、模板、状态和耗时，不保存简历正文。
- 导出目录、DOCX、PDF 和转换临时文件均被 Git 忽略。

## 状态机

```text
pending -> generating -> ready
                      -> failed
ready -> deleted
failed -> deleted
```

同步第一版不会长期停留在 `pending`/`generating`；这些状态为失败一致性和后续异步化保留。任何非法状态转换均拒绝。

## 验收标准

- 两个模板均能生成可解析 DOCX，空章节不渲染，项目符号和标题稳定。
- PDF 与 DOCX 使用同一个 `StructuredResume` 和章节顺序，内容一致。
- 中文和英文样例能生成、解析并完成视觉检查。
- PDF 能力不可用时返回明确错误，不产生伪 PDF。
- 文件名安全、内容类型正确、文件可重复下载和删除。
- 越权请求统一返回 `404`；本地绝对路径不出现在 API 响应。
- Career Match、Resume Optimizer、五个 AI Labs 和静态页面回归通过。

## 测试计划

- Schema：确定性解析、空内容、空章节、用户编辑和原文保留。
- DOCX：两个模板、中英文、长内容、标题、真实项目符号、解析回读。
- PDF：生成、文本回读、分页、CJK 字体能力和明确失败路径。
- 文件：安全命名、目录穿越、原子写入、哈希、删除和失败清理。
- API：鉴权、所有权、状态、Content-Type、Content-Disposition、历史和重复导出。
- 数据库：schema、migration、事务与级联关系。
- 前端：预览、模板/格式选择、生成、下载、失败重试、历史和浏览器回归。

## 已知限制

- 确定性解析依赖常见章节标题；非标准自由排版可能需要用户手工整理字段。
- 第一版保存结构化内容与段落顺序，不恢复原始字体、列布局、照片或图形。
- PDF 使用运行环境中可检测的 Unicode 字体；缺少可用字体时会明确失败。
- 本地文件存储只适合单实例原型，公开部署前需要对象存储、定期清理和恶意文件扫描。
