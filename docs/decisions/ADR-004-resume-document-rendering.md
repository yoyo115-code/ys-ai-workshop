# ADR-004: Resume document rendering

- 状态：Accepted and implemented in Phase 4
- 日期：2026-07-30

## 背景

ResumeVersion 当前是不可变纯文本快照。Phase 4 需要从同一确认版本稳定生成 DOCX 和 PDF，同时支持预览、用户修正、文件历史、下载和删除。方案必须避免模型补写事实、系统转换工具的不透明差异，以及用户文件名参与本地路径。

## 决策

### 1. 单一结构化数据源

新增严格 `StructuredResume` Pydantic Schema。确定性解析器只把 ResumeVersion 已有行映射到 basics、education、experience、projects、skills、certifications、awards 和 additional information，并保留 `original_text`。不调用 LLM，也不自动改写。

用户可以在预览中修正结构化字段。提交导出时，后端把用户确认的 Schema、来源 `resume_version_id` 和来源 `content_hash` 一起保存；模板只读这份快照。这样 DOCX/PDF 内容一致且可追溯，同时不修改不可变 ResumeVersion。

### 2. DOCX 直接生成

采用 `python-docx`：

- 可明确设置 A4/Letter、页边距、字体、标题间距和真实项目符号；
- 生成结果可由 Word、WPS、LibreOffice 打开；
- 不需要浏览器或外部 office 服务。

`professional` 使用克制的单栏商业简历样式；`minimal_ats` 使用无表格、无文本框、无图形的单栏顺序。两者使用固定设计 token，不依赖 Word 默认值。

### 3. PDF 直接生成

采用 ReportLab 从同一 `StructuredResume` 直接排版 PDF，不把 DOCX 转换为 PDF。原因：

- 避免生产环境必须安装 LibreOffice；
- 生成成功或失败由应用直接控制；
- DOCX 与 PDF 共用结构、章节顺序和模板 token。

PDF 渲染前检测可用 Unicode 字体。英文可使用 PDF 标准字体；包含中文时必须找到并注册支持 CJK 的系统字体，否则返回 `pdf_font_unavailable`，绝不生成缺字或伪 PDF。

LibreOffice 只用于开发阶段 DOCX 视觉 QA，不是运行时 PDF 依赖。

### 4. 本地私有存储与原子写入

第一版文件存放在配置的专用目录，内部文件名只使用 export ID 和格式。生成先写临时文件，成功后原子移动并更新 `ready`；失败清理临时文件并标记 `failed`。API 只返回安全下载名，不暴露 `storage_path`。

## 模板 token

### professional

- 单栏；A4/Letter；0.65–0.75 英寸页边距。
- Arial 拉丁字体与明确 CJK 字体提示，姓名 20–22 pt，章节标题 11–12 pt，正文 9.5–10.5 pt。
- 深蓝章节标题、细分隔线、稳定项目符号；不使用照片、技能条或装饰图形。

### minimal_ats

- 单栏；A4/Letter；0.7–0.8 英寸页边距。
- Arial 拉丁字体与明确 CJK 字体提示，全黑；姓名 18–20 pt，章节标题 11 pt，正文 10 pt。
- 不使用表格、文本框、多栏、图标、页眉页脚装饰或背景色。

## API 与状态

API 负责预览、生成、历史、详情、下载和删除。状态为 `pending -> generating -> ready|failed`，以及 `ready|failed -> deleted`。同步生成失败也必须保留可解释的失败记录，但不保留不完整文件。

## 安全与隐私影响

- 所有资源查询带 `user_id`；越权返回 `404`。
- 下载名与内部路径分离；路径解析必须保持在专用根目录下。
- `Content-Disposition` 使用 RFC 兼容安全名，并提供 UTF-8 文件名。
- 导出快照包含个人信息，只能保存在本地运行目录，不进入 Git 或 activity log preview。
- 删除记录时同步清理文件；公开部署前需要对象存储和到期清理任务。

## 被否决方案

- **调用 LLM 重新结构化或润色**：会增加事实漂移，且导出不应改变已确认内容。
- **浏览器打印 HTML 为 PDF**：需要浏览器运行时并引入跨版本分页差异。
- **LibreOffice 作为唯一 PDF 转换路径**：安装重、错误不透明，不适合作为最小运行依赖。
- **把用户下载名直接作为本地路径**：存在目录穿越、覆盖和跨平台字符问题。
- **原地给 ResumeVersion 写结构化 JSON**：破坏 Phase 3 的不可变版本模型。

## 后果

- 优点：内容来源清楚、两种格式一致、测试可确定、PDF 无外部转换依赖。
- 代价：需要维护两个渲染器；复杂原始布局不会保留；CJK PDF 依赖运行环境字体。
- 后续：公开部署时把文件存储抽象迁移到对象存储，并加入过期清理、病毒扫描和异步任务。

## 实现验证

- DOCX 由 `python-docx` 直接生成；测试回读 Open XML 文本、标题样式、项目符号和 Minimal ATS 无表格契约。
- PDF 由 ReportLab 直接生成；测试回读中英文、检查长内容分页，并覆盖 CJK/渲染器不可用错误。
- Professional 中文与 Minimal ATS 英文的 DOCX/PDF 已渲染为页面图像人工检查。开发环境的第三方 LibreOffice 若无法发现 macOS 系统字体，可能显示方框；使用 macOS 系统渲染器检查同一 DOCX 可确认中文内容与布局正常。发布到新平台前仍需做 Word/WPS/LibreOffice 抽样。
