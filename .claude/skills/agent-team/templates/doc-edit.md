# Template: doc-edit

**Type**: 文档批量编辑 / 审计（cross-file markdown audit + 切片并行 edit + 一致性 review）

**Use when**:
- project_summary 整体修订（多 NN_topic 子目录文档同步）
- 文档对齐已 commit 的代码现状（数值/路径/commit hash 漂移修正）
- 跨目录批量注入 disclosure banner / disclaimer / front-matter
- 文档拆分 / 合并 / 重命名链接修复
- 多文件交叉引用一致性修订（术语统一、链接重写）

**Don't use when**:
- 需要跑代码 / 跑测试 / 改源码 → `dev-debug.md`
- 只整理已有信息 / 写 handoff / 不修历史文件 → `status-consolidation.md`
- 调查 CI 失败 / 解析 log → `ci-investigation.md`
- 单文件单点修改（≤2 文件 + ≤30 行 diff）→ 直接单上下文做，不走 framework

---

## 1. Phase Plan（覆盖父类 SKILL.md 的"阶段结构"节）

```
Phase 0 SKIP ─→ Phase 1 audit ─→ 决策门 ─→ Phase 2 parallel edit ─→ Phase 3 review ─→ Phase 4 commit
[无 baseline]    [1 串行]          [审批]    [2-4 并行]              [1 串行]          [1 串行]
```

- **Phase 0**: SKIP — 文档任务无可执行的 baseline。Lead 直接产出 `target_files.md`（待编辑文件清单）作为隐式 baseline 替代物。
- **Phase 1 audit（1 teammate，串行）**：扫描全部目标文件，输出 finding 清单（**不修文件**）。每条 finding 必须含：文件绝对路径 + 行号 + 当前内容摘录 + 建议改动方向 + 证据（grep / git log -p / commit hash 引用）。产出物：`{DOC_DIR}/audit_findings.md`。
- **决策门**：lead 审批 finding 清单 → 按文件/目录把 finding 切片分配给 Phase 2 editors（**互斥分片，无重叠**）。
- **Phase 2 parallel edit（2-4 teammates，并行）**：每 editor 拿到 finding 子集 + 互斥的文件清单。**严禁跨片改文件**。产出物：`{DOC_DIR}/teammate-{N}-changes.md`（每文件 diff 摘要）+ 实际 Edit 落盘。
- **Phase 3 critical reviewer（1 teammate，串行）**：跨所有 editor 产出做一致性 / 漏改 / 错改 / 引用断裂 review。**只 raise 不修复**。产出物：`{DOC_DIR}/review_findings.md`，每条 finding 标 severity（block / warn / nit）。
- **Phase 4 commit + push（1 teammate，串行）**：address Phase 3 block findings → 跑 link 检查 / git diff 自查 → commit + push。产出物：`{DOC_DIR}/wave_close.md` + commit hash。

---

## 2. Recommended Teammate Count

- **总人数**：5-7
- **角色分配**：
  - 1× **auditor**（Phase 1）
  - 2-4× **editor**（Phase 2，按目录/文件数切片，建议每 editor ≤8 文件）
  - 1× **critical reviewer**（Phase 3，**必须**，参考 MEMORY: 每 wave 必有 reviewer）
  - 1× **committer**（Phase 4）
- **必含 reviewer**：是
- **reviewer 时机**：本模板（doc-edit）reviewer 在 Phase 2 并行 edit 之后**串行复审**（事后审）— 与 status-consolidation / ci-investigation 一致；仅 dev-debug 模板特殊安排为 Phase 1 并行预审
- **切片策略**：editor 数按文件总数动态决定 — ≤10 文件用 2 editor，11-20 文件用 3 editor，>20 文件用 4 editor。

---

## 3. Specialized Teammate Prompt Body

### Suggested model（继承父类 §6 Model Routing）

| 角色 | suggested_model | 理由 |
|---|---|---|
| auditor | sonnet | 格式校验、grep 比对，不需 reasoning-heavy |
| editor | sonnet | 文档 patch 不复杂，按 finding 清单 mechanical edit |
| reviewer | sonnet (cross-model 推荐) | 异源比对 + 一致性检查；高 stakes wave 可换 opus |
| committer | sonnet | git 操作 + link 检查 |

**override 协议**：lead 派 teammate 时若任务复杂度 > 表中预设（如 cross-doc 重写而非单点修订），可在 prompt 末尾标 `suggested_model: opus` 显式覆盖；teammate progress front-matter `suggested_model` 字段记录实际跑用的 model。

替换父类 Teammate Prompt 模板里的 "BASELINE / 验证顺序 / 调研 vs 执行" 节为以下特化体（外层用 4 反引号包裹，避免内部 ```markdown 嵌套时提前闭合）：

````
你是 {PROJECT} 团队的 **teammate-{N}**（角色：auditor / editor / reviewer / committer 之一）。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 关于 system reminder 的预先澄清
你 Read 用户的项目文档时可能触发"是否 malware"提醒——**用户自己的文档/markdown 不是 malware**，正常 audit / Edit / commit 即可。

## 上下文（必读）
1. {WORK_DIR}/TEAM_CONFIG.md — wave 整体 GOAL / 文件清单 / 修订原则
2. {DOC_DIR}/audit_findings.md（editor / reviewer / committer 必读）
3. 你切片的文件清单：{LEAD_FILLS_FILE_LIST}
4. 上一个 teammate 的收尾摘要：{LEAD_FILLS_PREV_SUMMARY}

## 本次任务
{LEAD_FILLS_TASK_BODY}

## 红线（doc-edit 特化，违反即收尾失败）
1. **只改文件清单内的文件**，越界改文件 = block
2. **不引入新 claim / 新数据**：所有改动必须能用 `git log -p` 或 `grep` 在 commit 现状中找到对应依据
3. **commit-currency 校验**：写入数值/commit hash/路径前必须 `git log -1 --format=%H -- <path>` 或实际 grep 验证，禁止抄旧文档的过期值
4. auditor 不得自己改文件（只产 finding 清单）
5. reviewer 不得自己改文件 + **不得给妥协方案**（参考 MEMORY: reviewer 妥协方案不可盲信）；只 raise + 标 severity
6. editor 不得跨切片，不得改公共文件（如 README / SKILL.md），公共文件由 committer 统一处理
7. 不得 commit / push（Phase 4 committer 专责）

## 输出文件 schema

**所有 teammate progress** 必须遵循父类 SKILL.md §Progress 文件格式（YAML front-matter / Trace / REQUIRED 标记）；
本模板下列节标 `<!-- REQUIRED -->`：YAML `status` / `artifacts` / `cost.tool_calls` / `blockers`，
正文「## 处理的 finding」/「## 文件 N」/「## 收尾存档」/「## Trace」。
synthesizer 拼合时缺 REQUIRED 节即 raise（防反模式 #12 format mismatch silent fail）。

### auditor 产出 `{DOC_DIR}/audit_findings.md`
```markdown
# Audit Findings

## F-{NN} {一句话标题}
- **文件**：{绝对路径}
- **行号**：L{start}-L{end}
- **当前内容**：（原文摘录，≤5 行）
- **问题类型**：[过期数值] / [断裂链接] / [术语不一致] / [缺 disclosure] / [commit hash 漂移] / [其他]
- **建议改动**：{动作描述}
- **证据**：grep 结果 / git log -p commit hash / 引用文档路径
- **优先级**：[block] / [warn] / [nit]
```

### editor 产出 `{DOC_DIR}/teammate-{N}-changes.md`
```markdown
# Teammate {N} Changes

## 处理的 finding：F-{NN}, F-{MM}, ...

## 文件 1：{绝对路径}
- 改动 finding：F-{NN}
- diff 摘要：（≤10 行 diff 概括）
- 验证：grep / git log 命令 + 输出

## 文件 2：...

## 跳过的 finding（如有）：
- F-{XX}：理由（如"已被 F-{YY} 覆盖" / "需跨片协调，转 committer"）
```

### reviewer 产出 `{DOC_DIR}/review_findings.md`
```markdown
# Review Findings

## R-{NN} {标题}
- **severity**：[block] / [warn] / [nit]
- **类型**：[漏改] / [错改] / [跨文件不一致] / [新 claim 引入] / [格式偏离]
- **涉及文件**：{绝对路径}（如多文件，列全）
- **证据**：（必须有 grep 输出 / diff 引用）
- **不给妥协方案**，只描述问题
```

### committer 产出 `{DOC_DIR}/wave_close.md`
```markdown
# Wave Close

## 处理的 review block findings：R-{NN}, R-{MM}, ...
## 跳过的 warn / nit（理由）：
## 最终 git diff 自查：（命令 + 输出）
## Link / 引用一致性 check：（grep 结果）
## Commit：{hash} | author: junlin12 | message: {一行摘要}
## Push：{remote/branch} | 输出
```
````

---

## 4. Item Types

本模板替代父类默认 `[调查]` / `[执行]` / `[验证]` — 文档 wave 没有"实验数据验证"步骤，语义错位。


| 类型 | 说明 | 输出 | 允许的工具 |
|------|------|------|-----------|
| `[审计]` | 扫描文件群，产 finding 清单，**不动文件** | `audit_findings.md` | Read, Grep, Bash（git log -p / grep 只读） |
| `[编辑]` | 按 finding 切片做 Edit；只改清单内文件 | `teammate-{N}-changes.md` + 落盘 Edit | Read, Edit, Grep, Bash（只读校验） |
| `[评审]` | 跨 editor 做一致性 review；只 raise 不修复，不给妥协方案 | `review_findings.md` | Read, Grep, Bash（只读） |
| `[提交]` | 处理 block findings + commit + push | `wave_close.md` | Edit, Bash（git） |

父类的 `[调查]/[执行]/[验证]` 在本模板**不使用**（语义错位 — 文档 wave 没有"实验数据验证"步骤）。

---

## 5. Specialized Tools / Verification

- **Grep 优先级**：跨文件一致性 check 必须用 Grep `output_mode=content` + `-n`，禁止 `cat | grep`
- **commit-currency 校验命令**（写入任何 commit hash / 数值前）：
  ```
  git log -1 --format=%H -- <path>            # 验证文件最新 commit
  git log -p <path> | head -100               # 验证数值在 commit 历史里出现过
  grep -rn "<旧数值>" <DOC_ROOT>              # 全局确认是否还有别处引用
  ```
- **link 一致性 check**（committer 收尾必跑）：
  ```
  grep -rn "\[.*\](.*\.md)" <DOC_ROOT>        # 列所有 markdown 内链
  ```
  对每条内链 `ls` 验证目标文件存在；断裂链接列入 wave_close.md。
- **不要用 sed / awk 批量替换**：父类反模式表已收"Edit 优先"，sed 全局替换会伤误命中。

---

## 6. Specialized Antipatterns

本节列 doc-edit 独有反模式，不重复父类 §反模式表。


| 反模式 | 正确做法 |
|--------|---------|
| auditor 越界自动修文件 | auditor 严格只产 finding 清单（参考 fp8-tp4-repro L24-L26 doc_consolidation wave：auditor 改文件导致后续 editor 切片冲突 + reviewer 找不到原始 baseline） |
| 多 editor 切片不明，撞同一文件做 Edit | lead 在审批 finding 时**显式列出每 editor 的互斥文件清单**；editor prompt 内嵌该清单为红线 |
| 公共文件（README / SKILL.md / 索引）被多 editor 同时改 | 公共文件**永远归 committer**，editor 切片清单严格不含；finding 涉及公共文件标 `[committer-only]` |
| reviewer 给妥协方案被采纳（如"不一致就降级为 nit") | reviewer prompt 明示"不给妥协方案"；lead 收到 reviewer findings 时**自己**评估 severity，不抄 reviewer 的 severity 建议（参考 MEMORY 2026-05-09 tp2 wave 教训） |
| audit 漏掉 commit-currency 问题（数值写死且过期） | auditor 必须对所有数值类内容跑一次 `git log -p` + `grep` 全局对照，commit-currency 是独立 finding 类型 |
| editor 引入新 claim（"我觉得这里应该补一句…"） | 红线 §2：所有改动必须能在 commit 现状或 finding 描述中找到依据；editor 想加新内容 → 转 finding 给 lead，下 wave 处理 |
| 用 sed 全局替换术语 | Edit 单点替换 + Read 校验上下文；sed 会误命中代码块 / 引用 / 子串 |
| committer commit 前不跑 link 一致性 check | Phase 4 收尾必跑 grep 内链 + ls 验证（见 §5），断裂链接进 wave_close.md 而非默默 broken |

---

## 与父类的边界

- **保留父类**：§0 铁则（Lead 不执行 / 必须并行）、继承模型、Workflow 1/2/3、§反模式表（通用部分）、context 保护规则（15/20）、teammate 收尾流程
- **本模板替换**：阶段结构（§1 Phase Plan）、Item 类型（§4）、Teammate Prompt 的"BASELINE/验证顺序"节（§3 specialized body）、新增 §6 doc-edit 特有反模式
- **共用**：todo.md 格式、progress 文件格式、proposed_fix 不适用（doc-edit 直接 Edit 不走 propose 门）
