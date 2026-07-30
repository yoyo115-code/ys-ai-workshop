# ADR-003: Immutable Resume Versions

- 状态：Accepted for Phase 3 implementation
- 日期：2026-07-30

## Context

Career Match 保存一份申请对应的简历文本和 JD。Resume Optimizer 需要让用户逐条接受、拒绝、编辑和重新生成建议，同时支持历史比较与恢复。如果直接覆盖 `resume_sources.extracted_text`，将无法证明某次修改来自哪条建议，也无法可靠回退。

## Decision

采用 `Resume` 聚合根与不可变 `ResumeVersion` 完整文本快照：

- `resumes` 负责用户所有权、来源申请和当前版本指针。
- `resume_versions` 保存完整结构化文本、父版本、连续版本号、来源类型和内容哈希。
- `resume_suggestions` 固定关联生成时的版本；版本变化后不会把旧建议应用到新文本。
- `resume_suggestion_events` 追加记录用户决策和文本编辑，不修改或删除历史事件。
- 创建优化版本在单个数据库事务中完成：锁定当前版本、校验建议、生成文本、插入版本、更新当前指针。任一步失败全部回滚。
- 恢复旧版本不是移动指针到历史行，而是以旧内容创建 `source_type=restored` 的新版本；这样恢复动作也可审计和撤回。
- 比较 API 使用两个完整文本快照生成确定性 Diff，不调用 LLM。

## Why full snapshots

相较只存 patch，完整快照更适合当前 SQLite MVP：读取和恢复简单、不会因 patch 链损坏而失去内容，也便于计算哈希和测试事务。简历纯文本体积有限，存储开销可接受。

## Alternatives considered

### 原地覆盖当前简历

拒绝。无法比较、审计或可靠回退，且与用户明确要求冲突。

### 只保存 diff/patch

暂不采用。节省空间，但恢复依赖完整 patch 链，冲突处理和迁移复杂度明显更高。

### 每个申请直接保存多个文本字段

拒绝。会把版本、建议和申请生命周期混在同一表，难以扩展手工版本与恢复语义。

## State and invariants

- ResumeVersion 创建后内容、父版本和版本号不可修改。
- 同一 Resume 的 `version_number` 唯一且单调递增。
- `current_version_id` 必须属于同一个 Resume。
- Suggestion 只能应用到其关联版本；已 `superseded` 的建议不能决策。
- 高风险或需澄清的模型建议不能直接标记为 `accepted`。
- 删除采用 Resume 软删除入口；本阶段不提供物理清理 API。

## Consequences

优点：

- 历史可审计、比较和恢复。
- 版本创建和回滚可以用 SQLite 事务明确验证。
- LLM 只负责生成建议，版本合成由确定性代码完成。

代价：

- 每个版本重复保存完整文本。
- 重复原句需要歧义检测，不能盲目字符串替换。
- 并发写入仍受 SQLite 和同步请求限制。

## Privacy

完整版本包含用户简历正文，数据库必须保持在 Git 之外。活动日志只记录 Resume、Version、Suggestion 的 ID 和技术状态，不记录内容、Prompt 或完整模型响应。

## Validation

- 数据库唯一索引与外键验证版本归属和编号。
- 测试注入版本创建故障，确认新版本和 `current_version_id` 同时回滚。
- 比较和恢复测试验证父版本、来源类型、内容与时间信息。
