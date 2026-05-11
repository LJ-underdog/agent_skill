# Template: status-consolidation

**Type**: 状态整理 / handoff / wave close / 项目 freeze 总结（**只读 + 综合**类任务，不动源码、不跑实验）

**Use when**:
- 跨 session handoff（用户即将关窗口，下个 session 接手前需汇总现状）
- Wave close summary（一个 wave 结束后整理 findings + decisions）
- 项目暂停前归档（给未来 N 周后回来的自己留 do-not-redo 列表）
- 多个 progress 文件汇总成单一 SESSION_HANDOFF
- 写 `PROJECT_CLOSED` 标记 + 引用证据链
- 给同事/接手人写"接手包"（含未决策选项）

**Don't use when**:
- 需要执行任何修复 → 用 `dev-debug.md`
- 需要批量改文档（如统一术语、修引用） → 用 `doc-edit.md`
- 需要找 root cause / 跑诊断 → 用 `ci-investigation.md` 或 `dev-debug.md`
- 单 teammate 任务（直接单上下文整理，不要走 agent-team 流程）

**复合任务拆 wave 规则**（防止与 doc-edit 选择器互斥模糊）：
- 「freeze 项目 + 给所有 README 加 deprecated banner」类复合任务 → **拆两 wave**：先 status-consolidation 出"待改文件 + 改动清单"（只产 plan，不 Edit）→ 再起 doc-edit wave 按清单实施
- 一句话判别：**"需要 Edit 任何业务文件" → doc-edit；"只产清单 / 摘要 / 决策项" → status-consolidation**

---

## 1. Phase Plan（覆盖父类 SKILL.md 的"阶段结构"节）

| Phase | 状态 | 串/并 | 产出物 |
|-------|------|-------|--------|
| **Phase 0** | **SKIP** | — | 无需 baseline；本模板不跑任何实验 |
| **Phase 1: parallel readers** | 必跑 | **并行**（≥2 同 message） | `progress/teammate-{1,2}.md` 含原文摘录 + 行号引用 |
| **Phase 2: synthesizer** | 必跑 | 串行（依赖 Phase 1） | `DOC_DIR/SESSION_HANDOFF.md` 或 `WAVE_CLOSE.md` 主文档 |
| **Phase 3: critical reviewer** | **必跑** | 串行（依赖 Phase 2） | `progress/teammate-reviewer.md` 含 findings 清单 |
| **Commit Phase** | **无** | — | Lead 自己决定是否 commit handoff（通常先给用户审） |

**Phase 1 细分（两个 reader 分工建议）**：
- Reader-A：读 `progress/*.md` + `git log --oneline` + lead_progress.md → 提取每个 teammate 的关键发现
- Reader-B：读实验数据 / log 文件 / proposed_fix_*.md → 提取数值 + 复现命令

**Phase 3 reviewer 必查项**（缺一即 raise）：
- 每个事实是否有来源（progress 行号 / git SHA / log 摘录）？
- 是否漏掉"接手 do-not-redo 列表"？
- 是否把"用户待决策选项"自己替用户决定了？
- 是否漏写 memory 同步动作（跨 session 持久事实）？
- 是否写到了临时目录而非持久路径？

---

## 2. Recommended Teammate Count

- **总人数：3-4**
- **角色分配**：
  - 2 × **reader**（Phase 1 并行）— 一个读 progress/git，一个读数据/log
  - 1 × **synthesizer**（Phase 2）— 写主 handoff 文档
  - 1 × **critical reviewer**（Phase 3）— **必含**（参考 MEMORY: 必须有 reviewer teammate）
- 可选：如 progress 文件 >10 个，扩到 3 reader + 1 synth + 1 reviewer = 5
- **reviewer 时机**：本模板（status-consolidation）reviewer 在 Phase 2 synthesize 之后**串行复审**（事后审）— 与 doc-edit / ci-investigation 一致；仅 dev-debug 模板特殊安排为 Phase 1 并行预审

---

## 3. Specialized Teammate Prompt Body

替换父类 Teammate Prompt 模板里的 "BASELINE / 验证顺序 / 调研 vs 执行" 节为（外层用 4 反引号包裹，避免内部嵌套提前闭合）：

````
你是 {PROJECT} 团队的 **teammate-{N}**（角色：reader / synthesizer / reviewer 之一）。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 上下文（必读）
1. {WORK_DIR}/TEAM_CONFIG.md — wave 整体 GOAL / handoff 边界
2. {WORK_DIR}/progress/*.md — 各 teammate 的产出（reader 必读全集；synthesizer / reviewer 读全集 + 主 handoff 草稿）
3. {LEAD_FILLS_HISTORICAL_LOGS} — 任何相关 log / 实验输出（reader-B 重点）
4. 上一个 teammate 的收尾摘要：{LEAD_FILLS_PREV_SUMMARY}

## 任务
{LEAD_FILLS_TASK_BODY}

## 红线（status-consolidation 特化，违反 = 任务作废）
- **只读 + 汇总**：禁止执行任何修复、禁止跑新实验、禁止改任何源文件
- **禁止派衍生 teammate**
- 禁止建议"未来行动"以外的修复方案（不是本模板职责）
- **每条写入 handoff 的事实必须有来源**：progress 文件 line 号 / git commit SHA / log 摘录三选一
- **不替用户做决策**：发现待决策选项时列为 "待用户决策" 节，给出 (a)/(b)/(c) 选项 + 各自代价，不预选
- **不跨 wave 持有结论**：如读到的内容已被后续 wave overrule，必须标 "已被 wave-N overrule" 而不是直接采用

## 输出文件 schema（共通）

**所有 teammate progress** 必须遵循父类 SKILL.md §Progress 文件格式（YAML front-matter / Trace / REQUIRED 标记）；
本模板下列节标 `<!-- REQUIRED -->`：YAML `status` / `artifacts` / `cost.tool_calls` / `blockers`，
正文（reader）「## 来源覆盖」/「## 关键事实」/「## Trace」，
（synthesizer 主 handoff）「### TL;DR」/「### 证据链」/「### 待决策选项」/「### 接手 do-not-redo 列表」/「### Memory 同步动作」，
（reviewer）「## 证据链完整性 check」/「## Findings」。
synthesizer 拼合时缺 REQUIRED 节即 raise（防反模式 #12 format mismatch silent fail）。

## 输出文件 schema（synthesizer 用）

文件路径：`{DOC_DIR}/SESSION_HANDOFF.md` 或 `{DOC_DIR}/WAVE_{N}_CLOSE.md`

必须包含 5 节：

### TL;DR（≤10 行）
- 项目当前状态一句话
- 关键阻塞 / 关键成果
- 下一步建议（不是命令式，是选项）

### 证据链
按时间顺序列出每个 wave / teammate 的关键发现，每条形如：
- [来源: progress/teammate-3.md L42-L58] {发现内容}
- [来源: git SHA abc1234] {commit 摘要}
- [来源: logs/run_xxx.log] {数值/异常}

### 待决策选项（用户视角）
列 (a)/(b)/(c)，每条含：
- 选项描述
- 已知证据 / 未知风险
- 估算代价（时间 / 资源 / 风险）
- **不预选 / 不暗示偏好**

### 接手 do-not-redo 列表（关键防重做）
明确列出"下个 session 接手时不要重复"的事项，例如：
- 不要重跑 baseline X（已跑，结果在 logs/baseline_X.log，PASS）
- 不要重新调研 Y 假设（已证伪，见 progress/teammate-5.md L80）
- 不要重新派 reviewer 检查 Z（wave-2 已覆盖）

### Memory 同步动作（持久化）

**铁则**：本节**只产出"待 lead 决定写入的清单"**，synthesizer / reviewer / 任何 status-consolidation teammate **均不得直接 Edit memory 文件**。memory 写入由 lead 在用户审过 handoff 后亲自执行（与红线 §1 "禁止改任何源文件" 一致；memory 文件视为持久源文件）。

列出本 wave 学到的、应当落入下列文件的事实（**给 lead 的待办清单**，不勾选 = 未执行）：
- [ ] `~/.claude/projects/-home-junlin12/memory/MEMORY.md` — 跨项目通用经验
- [ ] `{项目特定 memory 文件}` — 项目专用事实
- [ ] `~/.claude/CLAUDE.md` — 工作原则强化（仅强证据时）

## 输出文件 schema（reader 用）
追加写入 `{WORK_DIR}/progress/teammate-{N}.md`：
- ## 来源覆盖：列出本 reader 读了哪些文件 / commit / log
- ## 关键事实：每条带行号 / SHA 引用
- ## 缺口：哪些信息没找到（synthesizer 需要追问）

## 输出文件 schema（reviewer 用）
追加写入 `{WORK_DIR}/progress/teammate-reviewer.md`：
- ## 证据链完整性 check：逐条对照 handoff 是否有来源
- ## 缺失风险：列出未覆盖的潜在 follow-up
- ## Findings（block / warn / nit）：分级
- ## Memory 同步检查：是否漏写持久化动作

## Reviewer 红线（§0.4 配套，self-report 不可信铁则下游执行）
- **不许仅看 progress 描述就 PASS**: 仅文字描述 = self-report，必须按 §0.4 三类 artifact 做 cross-check
- **artifact 三类必查**: 代码/文档（file path + line / git diff）/ 运行（cmd stdout snippet）/ 调研（URL + 引文）
- **抽查覆盖率 ≥ 1/3**: 至少抽查 1/3 teammate 的 claim → artifact 链条；少于此 = reviewer 失职
- **遇 fabricated PASS 立即 raise**: 如 teammate 自报 PASS 但 artifact 不存在 / 不匹配，必须在 progress 标 [Blocked] + 列入 Findings；不许妥协 / 不许"信任默认"
````

---

## 4. Item Types

本模板新增 3 类，覆盖父类默认 `[调查]` / `[执行]` / `[验证]`（status-consolidation 不跑实验，全程只读 + 综合）。


| 类型 | 边界 | 允许工具 |
|------|------|---------|
| `[读]` | 只读源文件 / progress / log，不写任何业务文件，仅写 progress | Read, Grep, Bash（只读：ls/git log/git diff/wc） |
| `[综合]` | 只写 handoff 主文档 + progress；禁止写源码 / verify 脚本 / proposed_fix | Read, Write（仅限 DOC_DIR 下 handoff 文档）, Edit（仅限自己的 progress） |
| `[评审]` | 只读 handoff + progress + 原始来源做交叉验证；禁止写任何业务文件 | Read, Grep, Bash（只读） |

父类的 `[调查]` / `[执行]` / `[验证]` 在本模板**不使用**。

---

## 5. Specialized Tools / Verification

- **handoff 路径必须持久**：参考父类 §文档管理规则，不得写到 `/tmp` 或临时目录；推荐 `DOC_DIR/SESSION_HANDOFF.md` 或项目根
- **Memory 写入**：reviewer 发现需要 promote 到 MEMORY.md 的事实时，**仅列清单**给 lead，不直接 Edit memory（lead 决定何时 commit）
- **git diff/log 优先于 Read**：reader 用 `git log --oneline -20` + `git diff <SHA>..HEAD --stat` 比 Read 长 commit 文件更省 token

---

## 6. Specialized Antipatterns

本节列 status-consolidation 独有反模式，不重复父类 §反模式表。


| 反模式 | 正确做法 |
|--------|---------|
| Synthesizer 引入未在任何 progress / log / commit 出现的"推断结论" | 仅汇总有来源的事实；推断 → 列入"待决策选项"或 reviewer 加 finding |
| Handoff 文档没写"接手 do-not-redo 列表" → 下个 session 重复调研 baseline / 重派已完成 teammate | 必须含 do-not-redo 节，每条带证据指针 |
| 把"用户待决策选项"自己替用户做了决定写进 handoff（如 "建议采用方案 a"） | 列 (a)/(b)/(c) + 各自代价，不预选；用户视角而非 lead 视角 |
| Handoff 写到临时目录（`/tmp/handoff.md`） | 必须写持久路径（DOC_DIR / 项目根）；参考父类 §文档管理规则 |
| 漏写 memory 同步动作 → 跨 session 持久事实只活在 handoff，下次失忆 | reviewer 必检 "Memory 同步动作" 节；持久事实必须落 MEMORY.md / 项目特定 memory |
| Reviewer 给"妥协方案"代替 raise（如"证据不全就降级为 sanity check"） | reviewer 只 raise + 给 lead 选项，不替 lead 妥协；参考 MEMORY 2026-05-09 "Reviewer 妥协方案不可盲信" |
| 把已被后续 wave overrule 的旧结论原样搬入 handoff | 标 "已被 wave-N overrule"，并指向覆盖来源 |
