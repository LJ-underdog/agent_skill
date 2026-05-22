---
name: agent-team
description: |
  Launch a structured multi-agent team for complex debugging and development tasks.
  Supports a parent-child inheritance model: instantiate a task-specific team config,
  run the team, and promote learned patterns back to the parent.
  Use when: task decomposes into independent subtasks, >30 tool calls expected,
  multiple hypotheses need parallel exploration, or clear investigate→propose→approve→implement→verify flow.
  Trigger phrases: "start agent team", "agent team 来做", "launch agent team for", "用 agent team",
  "instantiate agent-team for X".
---

# Agent Team — 多智能体调试 / 开发团队

任务：`$ARGUMENTS`

---

## -1. 与官方 Claude Code subagent / agent-teams 的关系

Claude Code 提供 2 个官方多 agent 产品，本 skill 是它们之外的**第 3 种选择**：

| 工具 | 范围 | 通信 | 何时用 |
|---|---|---|---|
| 官方 subagent (`/agents`) | 单 session 内 fork | 不直接，仅 lead 中转 | 一次性 side task / 防上下文污染 |
| 官方 agent-teams (experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) | 跨 session | task-list + mailbox 直接通信 | 临时探索 / 不需要复杂模板继承 |
| **本 skill (agent-team)** | 跨 session | 不直接，靠文件交换 + lead 中转 | 多 wave / 重 prompt 工程 / 需要严格 §0 铁则纪律 / 需要模板继承 |

**本 skill 的核心增量**（相对官方 agent-teams）：
- 三层继承模型（SKILL.md → templates/<name>.md → TEAM_CONFIG.md）
- §0 铁则强约束（lead 不执行 / 必须并行 / writes single-threaded / self-report 不可信 / teammate 不递归 / lead 整 wave 不变）
- Workflow 0.5 模板选择器
- reviewer raise-only 模式 + Promotion 闭环

**何时用官方而非本 skill**：
- 任务 < 30 tool calls / 单 wave 即可完成
- 不需要跨 wave promote 经验回父类
- 简单的 multi-hypothesis 探索（不需要严格 §0 纪律）

**继承官方约束**：本 skill 的 §0.5 / §0.6 与官方 subagent / agent-teams 文档明文要求**严格对齐**（无嵌套 / lead 不变 wave-lifetime），不引入与官方冲突的语义。

---

## -0.5 调度方式优先级（tmux pane teammate vs in-process Agent tool）[BREAKING]

本节定义 teammate **调度方式选择**（顶级 meta 决策，影响 wave 开始前的工具选择）。tmux 模式内部的**角色细则**（4-pane 角色表 / 持久化保证 / 临时角色 / refresh 协议 / 角色反模式）见 §9.6.5；**两节 single source of truth 分工**：§-0.5 = "用哪种调度方式"，§9.6.5 = "选 tmux 后角色怎么分"。

本 skill 支持 **2 种** teammate 调度方式。**默认优先 tmux pane teammate**；in-process `Agent` tool 仅在窄场景退化使用。违反此优先级 = 反模式。

### -0.5.1 对比表

| 维度 | tmux pane teammate（**默认**） | in-process Agent tool（subagent_type=general-purpose） |
|---|---|---|
| **持久化能力** | ✅ 跨 wave 角色 / context 保留在 pane history（scrollback + claude session memory） | ❌ 每次 Agent 调用 fresh context，结束即销毁 |
| **用户可见性** | ✅ 可 `tmux attach` 实时观察任何 pane 内子 claude 工作过程（工具调用 / 思考 / 输出全可见） | ❌ 黑盒 — 仅看到最终 return；lead 无法观察中间状态 |
| **启动 overhead** | ❌ 子 claude 启动 3-8s（首次 pane setup + claude 加载）；后续派单仅 send-keys（<100ms） | ✅ Agent tool < 1s 启动 |
| **并行能力** | ⚠️ 标准 3-pane teammate 容量（pane 1/2/3，pane 0=lead，§9.2）；可扩到 8-pane 但布局成本高 | ✅ 同 message 内 Agent tool call 无硬上限（推荐 ≤5 / §0.2） |
| **适用场景** | 多 wave 长任务 / 角色固定 / 需视觉调试 / 教学演示 / 子任务有跨 wave 上下文依赖 | 一次性 fact-finding / 短查询 / 无持久化需求 / CI runner 无 tmux 环境 |
| **何时不用此模式** | < 5 tool calls 的 trivial 查询；无 tmux 环境；需要 mailbox 协议（独立 session 不支持 SendMessage） | 默认情况下都不用（除非命中下方 §-0.5.2 退化触发条件 a/b/c/d） |

> 表头详细解释 footnote：**持久化能力** = 跨 wave 边界 teammate 是否保留 context；**用户可见性** = lead 之外的 human user 能否实时观察 teammate 工作；**启动 overhead** = 单次 teammate 派单时的端到端 wall-time（含进程启动）。

### -0.5.2 优先级规则（默认 tmux）

**Lead 派单时按序判断**：

1. **默认走 tmux pane teammate**（标准 4-pane 模板，4-pane 角色表见 §9.6.5.1）
2. **退化为 in-process Agent tool** 仅当命中以下 ≥1 条：
   - **(a)** 任务 < 5 tool calls 且**无需跨 wave 持久化**（如 grep 一个文件、读一个配置项）
   - **(b)** 单次性 fact-finding（如"查这个 PR 的 CI 状态"）
   - **(c)** 当前环境**无 tmux session**（CI runner / 容器内 / 远程 sandbox）
   - **(d)** **同 wave 需 ≥ 4 个并行 teammate**（超 §9.2 标准 3-pane 容量）→ **混合模式**：3 个走 tmux pane（按 §9.6.5.1 持久角色分配），其余走 in-process Agent。混合派单 prompt 必须显式标注每个 teammate 的调度模式（如 `pane-2 (drafter, tmux)` / `agent-4 (fact-finder, in-process)`）

派单前 lead **必须在派单 prompt 开头**显式声明走哪种模式：
- tmux 模式：`"派给 pane-{N}（角色：{role}）..."`
- in-process 模式：`"退化 in-process Agent，原因：(a)/(b)/(c)/(d)"`
- 混合模式：每个 teammate 单独标，并说明命中 (d)

未声明 = 默认 tmux（按 §-0.5.1 表"持久化" / "可见性"优势走）。

### -0.5.3 持久化角色绑定

**详见 §9.6.5.1 4-pane 角色表**（lead / auditor-patcher / drafter / architect-reviewer 4 角色 × pane 0/1/2/3 映射）。本节不重复表格内容（避免 §-0.5 与 §9.6.5 同步漂移）。摘要：**所有 pane 角色绑定为 wave 间持久**，跨 wave 不变；refresh 协议 / 临时角色覆盖见 §9.6.5.3-§9.6.5.4。

### -0.5.4 派单时如何引用 pane 角色（lead prompt 模板示例）

```bash
# Lead 写派单 prompt 时，必须在开头声明 pane id + 角色：
# 注意：以下 heredoc 内 <...> 均为占位符（lead 用实际内容替换，不要保留 <> 字面文本）
cat > $WAVE/prompts/wave-N-pane-2.md <<'EOF'
# Pane-2 任务（持久角色：drafter）— <任务标题>     ← <...> = 占位，lead 填实际内容

你运行在 tmux pane `claudeteam:0.2`，持久角色 = **drafter**。
本 wave 起在后续所有 wave 中持续承担此角色（起草类工作）。

## 背景
<引用 wave 间共享 context：可直接说"参考上 wave 你写的 progress/wave-{N-1}-pane-2.md"，
 因为 pane 2 的 claude session 还活着，能记得自己上 wave 做了什么>
                                                  ← <...> = 占位，lead 填实际引用路径

## 任务 / 红线 / Output
<标准 5 项：编号 / 上 teammate 收尾摘要 / 本次 item / WORK_DIR+DOC_DIR / 红线>
                                                  ← <...> = 占位，lead 填实际任务内容
EOF

tmux send-keys -t claudeteam:0.2 \
  "请读取 $WAVE/prompts/wave-N-pane-2.md 并严格按其执行" Enter
```

**关键**：派单 prompt 标题里写"持久角色：{role}"是**契约**（pane 子 claude 借此自我定位 + 跨 wave 一致性自查）；lead 派给 wrong pane（如把 architect 任务派给 drafter pane 2）= 反模式。混合模式 (§-0.5.2 (d)) 派 in-process Agent 时不需 pane 角色字段，但 prompt 头部仍须标 `调度模式：in-process Agent，原因：(d) ≥4 并行`。

### -0.5.5 业界依据 / cross-ref

- **持久化**：与 Letta MemGPT "Core Memory" 在**功能上相似**（per-agent 持久 context），**实现机制不同**（Letta = 显式 RAG/scratchpad 写入；tmux pane = implicit scrollback + claude session memory）；两者都达成"agent 跨调用保留状态"目的但机制不可互换
- **可见性**：Anthropic — multi-agent debugging「observability of subagent intermediate state is critical for production trust」；tmux attach = 100% observability
- **退化触发条件 (a)(b)(c)**：与 §0.2 "< 2 teammate 不要走 wave" 同精神（小任务不上重框架）
- **退化触发条件 (d) 混合模式**：与 Anthropic multi-agent 论文 "match agent count to task parallelism, not to framework capacity" 一致 — 不强行把 4-6 并行塞进 3-pane 容量
- cross-ref：§0.6 Lead 整 wave 不变 / §9.2 Standard layout / §9.3 file-based 派单协议 / §9.6.5 tmux 模式角色细则 (single source of truth for 4-pane 角色表) / §9.7 Roundtrip smoke test

---

## 0. 铁则（最高优先级，违反即取消本次 agent-team）

### 0.1 主 agent（Lead）不执行任何具体工作

Lead **只做**这四类动作：
- 决策（采纳哪条方案 / 派谁 / 是否进入下一 Phase）
- 写协调文档（TEAM_CONFIG / WAVE_CLOSE / todo / 简短的用户汇报）
- 派 teammate（通过 Agent tool）
- 读状态（`ls` / `git status` / `git diff` / 读自己写的协调文档）

**Lead 严禁**：
- Bash 调研（`python -c "import X"` 验证环境 / `find` / `grep` 搜代码 / `head` / `cat` 看脚本内容 / 跑任何业务命令）
- Read 长源码文件做内容分析（区别于读 TEAM_CONFIG / WAVE_CLOSE 这种自己写的协调文档）
- 跑 GPU / 跑 verify 脚本 / 跑 baseline / 分析 log
- 写新的源码 / verify 脚本（任何文档之外的代码必须派 teammate）

**Lead 例外允许**：
- 5–15 行内的 trivial patch 自己 Edit（写 30 行 teammate prompt 派单 overhead 比直接改更高时）
- 无副作用的状态查询命令：`ls` / `git status` / `git diff` / `git log --oneline -10`

**任何调研 / 验证 / 执行类动作 → 派 teammate（哪怕只是 1 个 Bash 调用）。**

### 0.2 Agent Team 必须并行

启动 agent team 后：

- **Phase 1 必须同时派 ≥2 个 teammate**（在同一个 message 里发出多个 Agent tool call）
- **串行派单**（一个 teammate 等另一个 teammate 完成才派下一个）= 反模式，等同于没用 agent-team
- 如确实有依赖关系必须串行，**先向用户说明依赖原因 + 拿到明确 override 再执行**
- 单 teammate 任务直接单上下文做，不要走 agent-team 流程

> **脚注（Wave 0.5 META-1 实证补充, 2026-05-09 / 2026-05-11 落地）**:
> Claude Code harness 实测**真并发**执行多 Agent tool_use（实测 wall-time ≈ max teammate duration，非 sum；实证：landing wave T1-T4 sequential 预期 820s vs 实测 ≈278s，节省 542s）。
> 已知风险: claude-code GitHub issue **#57037** (permission cascade-failure on parallel batch) 偶发；若整个 wave 多 teammate 同时报 "Permission to use X denied"，**兜底切 sequential**（每 turn 1 Agent call）并向用户 raise 触发了已知 bug。
> ❌ **严禁预防性切 sequential** — 听说 / 怀疑 parallel 有 bug 就主动改串行 = 违反本节铁则。仅当**实证**触发 cascade-failure 才允许切 sequential。

### 0.3 Writes single-threaded（写入单线程铁则）

多 agent 出主意可以并行（调研 / 验证 / 各自写 progress.md / 跑独立 benchmark），
但**写入** —— 改源码 / 写 patch 进同一文件 / 落盘 deliverable —— 必须串行。

**OK 的并行写**（每 teammate 写自己独立的输出文件）：
- `progress/teammate-{N}.md` — 每个 teammate 自己一份
- `proposed_fix_{item}.md` — 每个 item 独立文件
- 独立 benchmark log / 独立调研 report

**不 OK 的并行写**：
- 多 teammate 并行 Edit 同一个源码文件
- 多 teammate 并行写同一个 deliverable / consolidated report
- 多 teammate 并行实施同一 component 的不同部分

**正确做法**：
- Trivial patch（5-15 行） → lead 自己 Edit（已在 §0.1 例外列出）
- 非 trivial 修改 → 派**单个** integrator teammate 串行汇总各方案后落盘
- 多文件协作 → 先派**单个 contract definer** 固定 interface，再并行实施

**三维约束自洽**：§0.1 限 lead 行为 / §0.2 限调研并发 / §0.3 限写入并发。

> **Wave 0.5 cross-check（实证补充, 2026-05-09 / 2026-05-11 落地）**：
> writes-single-thread 的限制范围 = **源码 / patch / deliverable**（如 `~/.claude/skills/` 文件、wave-level consolidated report、共同 commit patch）。
> **不**扩展到 `progress/teammate-N.md`（天然按 N 分片，多 teammate 并写无 race）或独立 benchmark / 调研 report；这些路径分片设计已在 SHARED OUTPUT SKELETON 中固化。若未来 wave 引入 wave-level 共写文档则需新增 lock / leader / aggregator（详见 META_FINDING.md Dim-4 / 触发 Proposal-META-A）。

### 0.4 Teammate self-report 不可作为 ground truth

Teammate 在 progress.md 写「PASS / DONE / 跑通」时，
必须有可验证 artifact 作背书 — 否则视为 NOT RUN。

**三类有效 artifact**：
1. git diff / file mtime / 文件路径 + 行号（代码 / 文档修改类）
2. 命令 stdout/stderr 截录（运行类）
3. 外部源 URL + 引文（调研类）

**Teammate 红线**（写入 prompt 模板）：
- 不许 fabricate「PASS」— 若未实跑必须明示「NOT RUN, blocker: ...」
- progress.md 「结论」节每条必须附 artifact 路径或行号

**Reviewer 红线**（写入 reviewer prompt）：
- 对每条 teammate「PASS / DONE」claim，必须 cross-check artifact
- 仅看 progress 描述就 PASS 整个 wave = 反模式
- 至少抽查 1/3 teammate 的 claim → artifact 链条

> **Cross-ref**: reviewer artifact 抽查 ≥ 1/3 的操作清单详见 §代码修改审批门。
> §0.4 立 teammate 视角红线 / §代码修改审批门 立 reviewer 视角操作清单 — 配套生效。

### 0.5 Teammate 不递归派单

Teammate **不得**通过 Agent tool 派 sub-teammate（无限嵌套风险）。
如确需子任务：teammate 在 progress 里 raise「需派 sub-teammate 处理 X」，
由 lead 决定下一 wave 是否派单。

**业界依据**：Claude Code subagent 文档 — "the built-in Plan agent ... to prevent infinite nesting (subagents cannot spawn other subagents)"；Claude Code agent-teams 文档 — "No nested teams: teammates cannot spawn their own teams or teammates"。

### 0.6 Lead 整 wave 不变 [BREAKING]

一个 wave 启动后，lead session **不可中途切换**。
如需新 lead（用户更换 agent / context 重启），必须：
1. 当前 lead 写 `WAVE_CLOSE.md` 收尾
2. 显式 close 本 wave
3. 新 session 重新 instantiate 新 wave

**业界依据**：Claude Code agent-teams 文档 — "Lead is fixed: the session that creates the team is the lead for its lifetime"。

**[BREAKING] 范围**：仅约束极少数旧 wave "mid-wave 切 lead" 的不规范行为；同一 wave 内 lead 不变 / wave 边界可换 lead 是合规的（窄措辞 narrow，不限制跨 wave 切换）。

---

## 继承模型

```
SKILL.md (父类 — 通用框架 + Workflow 0.5 模板选择器)
  ├── templates/dev-debug.md             ← 标准开发/调试/复现-修-验证
  ├── templates/doc-edit.md              ← 文档批量编辑/审计
  ├── templates/status-consolidation.md  ← handoff/wave close/freeze 总结
  └── templates/ci-investigation.md      ← CI/log forensics/PR 失败排查
        └── (instantiate 时) TEAM_INSTANCE_TEMPLATE.md (子类骨架)
              └── project_{name}/TEAM_CONFIG.md (子类实例 — 任务特化)
                      ↓ [任务结束后 Promote]
              SKILL.md (父类更新) / templates/*.md (模板更新)
```

三层继承：
1. **父类 SKILL.md**（本文件）— 通用框架：§0 铁则、Workflow 0/0.5/1/2/3、Lead 行为规则、Teammate Prompt 共通骨架、TODO 格式、文档管理规则、§反模式表通用条
2. **特化模板 templates/*.md** — 任务类型特化：Phase plan、teammate 数量与角色分工、Specialized Prompt Body、特化 Item 类型、特化反模式
3. **子类实例 project_{name}/TEAM_CONFIG.md** — 单次任务特化：ENVIRONMENT、BASELINE、KNOWN_FACTS、本任务 todo

子类只填写任务特有部分；父类的 Lead 行为规则、Teammate prompt 共通骨架、审批门、todo 格式自动适用，不在子类重复。模板覆盖父类的 Phase 结构 / 特化 prompt 体 / 特化反模式，但 §0 铁则、Workflow 1/2/3、Lead 行为规则等父类节**自动继承**，模板不可绕过。

---

## 与 project-summary 的集成

agent-team（执行）通常与 project-summary（记录）同时使用。
详见 [SKILLS_INDEX.md](../../SKILLS_INDEX.md)，核心要点：

- **先 instantiate project-summary**，生成 `TASK_TEMPLATE.md`（参数 schema、指标、已知事实）
- **再 instantiate agent-team**，生成 `TEAM_CONFIG.md`，从 TASK_TEMPLATE.md 引用共享字段
- teammate progress 文件即为 project-summary 的 experiment_log，**无需另外维护**
- 任务结束后，两个 skill 各自执行 Promote workflow

---

## 1. Memory 分层（4-tier 模型 / Proposal-006）

本 skill 4 处 memory，按 tier 分层管理（仿 Letta MemGPT 设计 + Anthropic context engineering 三大对策 compaction / structured note-taking / sub-agent isolation）：

| Tier | 名称 | 路径 | 何时读 | 何时写 |
|---|---|---|---|---|
| L1 | Message Buffer | 当前 turn 上下文 | 自动 | 自动 |
| L2 | Core Memory | TEAM_CONFIG.md / WAVE_CLOSE.md | 每个 teammate prompt 必读 | lead 每 phase 收尾写 |
| L3 | Recall Memory | progress/teammate-*.md | reviewer 必读全部 / synthesizer 按需读 | teammate 自管 |
| L4 | Archival Memory | ~/.claude/projects/.../memory/MEMORY.md | lead 启动时读 / Promotion 时写 | Workflow 3 promote |

**每个 template 在 §3 Specialized Teammate Prompt Body 头部声明「必读 tier 清单」**：
- 默认 L2
- dev-debug：L2 + L3（看 teammate 间假设关系）
- doc-edit：L2 + L4（历史决策记录）
- status-consolidation：L2 + L3（必读全部 progress）
- ci-investigation：L2

**Lead 自己应避免一锅端读 L3 全部**；按需 selective load（按 teammate id / 按 phase / 按异常信号挑读），与 §0.1「Lead 不 Read 长源码」铁则一致。

**业界依据**：Letta MemGPT 4 类（Message Buffer / Core Memory / Recall / Archival）+ Anthropic「effective context engineering」三大对策（compaction / structured note-taking / sub-agent isolation）。

---

## Workflow 0：决策 — 是否使用 Agent Team？

**适合：**
- 任务可分解为有明确输入/输出的独立子任务
- 预计 >30 tool calls，单 context 装不下
- 多个假设可并行探索（互不阻塞）
- 有清晰的"调查 → 提案 → 审批 → 执行 → 验证"流程
- 需要同时阅读大量代码/日志

**不适合：**
- 高度串行，每步强依赖上一步
- 预计 <15 tool calls 即可完成
- 需要频繁与用户交互确认方向
- 复杂进程/全局状态需要单一控制者
- **Single-codebase coding-tight task**（即使 item ≥ 4）—— Anthropic 自己说
  "coding tasks involve fewer truly parallelizable tasks than research"；
  arXiv 2601.04748 实证：skill-based single-agent 在编码 benchmark 上
  ~等同 multi-agent 准确率 + 54% token 节省 + 50% 延迟降低。
  只有任务跨多 codebase / 多领域 / 含调研维度时才上 multi-agent。
  （来源：Proposal-007 / 反模式表 #17）

**判断后如不适合，直接单 Claude 完成，不要强行用 Agent Team。**

---

## Workflow 0.5：选择特化模板

通过 Workflow 0 决定使用 agent-team 后，按任务类型选择 `templates/` 下的特化模板。
每个模板覆盖父类 SKILL.md 的"阶段结构 / Item 类型 / 验证顺序 / Specialized Antipatterns"等节，
但父类 §0 铁则、继承模型、Workflow 1/2/3、Lead 行为规则、§反模式表通用条 自动适用。

### 模板对照表

| 模板 | 适用任务 | Phase plan 简述 | 推荐 teammate 数 |
|---|---|---|---|
| `templates/dev-debug.md` | 开发 / 调试 / 复现-修-验证 | Phase 0 baseline → 1 调查 → 2 fix → 3 验证 | 4-7 |
| `templates/doc-edit.md` | 文档批量编辑 / 审计 | Skip 0 → 1 audit → 2 并行 edit → 3 review → 4 commit | 5-7 |
| `templates/status-consolidation.md` | handoff / wave close / freeze | Skip 0 → 1 并行 read → 2 synthesize → 3 review | 3-4 |
| `templates/ci-investigation.md` | CI / log forensics / PR fail | Phase 0 拉 log → 1 并行分析 → 2 报告（无 fix） | 3-4 |

### 选择决策树

```
任务是改源码 / 跑测试 / debug crash？
  ├─ Yes → templates/dev-debug.md
  │        └─ 根因模糊 / 多个 plausible hypothesis / anchoring 风险高？→ 启用 §dev-debug 子模式 competing-hypotheses（Proposal-021 Path B）
  └─ No
      ├─ 任务是改多个 markdown 文件？        → templates/doc-edit.md
      ├─ 任务是从 progress / log 汇总状态？ → templates/status-consolidation.md
      ├─ 任务是查 CI / Actions 失败？        → templates/ci-investigation.md
      └─ 都不匹配                            → fallback templates/dev-debug.md（最通用）
```

### Teammate 数量量化规则（继承 Anthropic scaling rule）

| 任务复杂度 | 推荐 teammate 数 | 典型 tool calls / teammate |
|---|---|---|
| Fact-finding（单一调研） | 1（直接单 context，不开 wave） | 3-10 |
| Direct comparison（2-3 选项对比） | 2-4 | 10-15 |
| Multi-domain research / debugging | 4-7（本 skill 上限 5 推荐 / 极限 7） | 10-20 |
| Complex 跨多 codebase 重构 | >10 — 应分多 wave，不一次性派 | — |

**下限规则**：< 2 teammate 不要走 wave，直接单 context 做（违反 §反模式表第 8 条 / 来源：Proposal-008）。
**业界依据**：Anthropic — "Simple fact-finding requires just 1 agent with 3-10 tool calls, direct comparisons might need 2-4 subagents, complex research might use more than 10 subagents with clearly divided responsibilities" (Built multi-agent research system)。

### 5 模式归类（Anthropic Building Effective Agents）

本 skill 当前 4 templates 都属 **Orchestrator-Workers** 模式特化。
- **Prompt Chaining**：Workflow 1/2/3 本身串行链
- **Routing**：Workflow 0.5 即显式 Routing 决策（任务类型 → 模板）
- **Parallelization**：§0.2 铁则强制 Phase 1 ≥2 teammate 同 message
- **Orchestrator-Workers**：4 templates 主体模式（lead orchestrate + teammate worker）
- **Evaluator-Optimizer**：见 Proposal-013（Trace + reviewer artifact spot-check 是其轻量实现；Voting 多 teammate 独立给方案后投票，本 skill 暂不实现，作未来扩展）

### Instantiate 时使用模板

在 `project_{name}/TEAM_CONFIG.md` 顶部声明：

```markdown
## Template
继承自：`templates/<name>.md`
```

Lead 派 teammate 时按 `templates/<name>.md` 的 §3 Specialized Teammate Prompt Body 取 prompt 段，与父类 SKILL.md 的 Teammate Prompt 共通骨架（编号 / WORK_DIR / DOC_DIR / 铁则 / Context 保护 / 收尾流程 / Progress 格式）拼装成完整 prompt。

---

## Workflow 1：Instantiate（任务开始时）

### Step 1：自动读取上下文

```
① git log --oneline -10 + README/CLAUDE.md → 约束、代码结构
② recall knowledge index                   → 已知事实，避免重复验证
   /root/.local/share/claude/recall/hanchang/knowledge/index.md
③ MEMORY.md                                → 环境配置、已知 bug、路径
   /root/.claude/projects/-home-hanchang/memory/MEMORY.md
④ project-summary TASK_TEMPLATE.md（如有） → baseline、参数 schema
⑤ 兄弟任务 TEAM_CONFIG.md（如有）          → 复用 ENVIRONMENT 配置
```

### Step 2：推导子类各字段

| 字段 | 推导来源 | 推导逻辑 |
|------|---------|---------|
| **CODE_ROOTS** | `git remote -v` + ls | 列出所有相关仓库路径 |
| **ENVIRONMENT** | CLAUDE.md + MEMORY.md | 提取 python 运行前置、GPU 设置、缓存清理、git push 路径 |
| **BASELINE** | logs/ 目录 + test 脚本 | 找到上次成功运行的命令和预期指标 |
| **KNOWN_FACTS** | recall + MEMORY.md | 直接提取已标 `[已验证]` 的条目 |
| **CONSTRAINTS** | CLAUDE.md + 代码注释 | `@support_torch_compile`、`# DO NOT MODIFY`、不能动的接口 |
| **Phase 0 todo** | 任务类型 | crash 调试 → 先跑 baseline；新功能 → 先定义验收测试 |

### Step 3：向用户确认（最多 5 个问题）

```
Q1. 任务目标？（一句话，无法从 README 获取时问）
Q2. 成功标准的具体数值？（哪个指标达到什么值）
Q3. 有哪些不能改的文件/接口？（CLAUDE.md 没覆盖的部分）
Q4. 预期的调查方向？（已知哪些可能的根因）
Q5. 有没有相关兄弟任务可以复用 ENVIRONMENT？
```

### Step 4：生成子类实例

读取 `TEAM_INSTANCE_TEMPLATE.md`，填入 Step 1-3 的信息，生成：

```
project_{name}/TEAM_CONFIG.md
```

同时初始化：
```bash
mkdir -p project_{name}/{progress,logs}
touch project_{name}/todo.md
```

### Step 4.5：Checkpoint scan（resume 现有 wave 时 / Proposal-009）

若 WORK_DIR 已存在 `progress/` 目录且非空：
1. `ls progress/teammate-*.md` → 列已完成 teammate 编号
2. 读 `todo.md` → 看哪些 item 标 `[x]` / `[~]` / `[ ]`
3. 在 `TEAM_CONFIG.md` 顶部声明 `## Resume from: progress/teammate-{N}.md`
4. 跳过已完成 teammate；从下一个未完成 phase 启动

Resume wave 不重派已完成 teammate；不重读 L4 archival memory（节约启动 token）。
依赖：Wave 1.A.0 Proposal-013 YAML front-matter（resume 起点必须有 YAML schema）+ Wave 1.B Proposal-003。

### Step 5：展示给用户确认，再启动 Lead

---

## Workflow 2：Evolve（团队运行中）

### 主动识别 Promotion Candidate 的触发条件

| 触发场景 | PC 类型 | 建议加入父类位置 |
|---------|---------|---------------|
| 反模式表没覆盖的新反模式被踩到 | 新增反模式条目 | 父类 §反模式表 |
| 审批门标准在某场景失效 | 审批门规则补充 | 父类 §代码修改审批门 |
| todo item 类型不够用（调查/执行/验证之外的） | 新 item 类型 | 父类 §Item 类型说明 |
| context 保护规则 15/20 在本任务不适用 | 调整建议 | 父类 §Context 保护规则 |
| 发现通用的 Phase 0 设计模式 | Phase 0 设计 | 父类 §阶段结构 |
| 某类任务的环境配置可复用 | 环境模板 | TEAM_INSTANCE_TEMPLATE.md |
| Lead 存档规律需要调整 | 存档规律 | 父类 §存档规律 |

在 `TEAM_CONFIG.md` 的 `## Promotion Candidates` 节追加：

```markdown
### [PC-{N}] {简短描述}
发现时间：YYYY-MM-DD
触发场景：{从上表选择}
来源：teammate-{N} 的 progress / lead review / 任务结束后分析

**内容**（用父类可直接使用的措辞）：
{具体的规则/条目}

**为什么 promote**：{在本任务中的具体表现 + 为什么对其他任务也有价值}

**建议加入父类位置**：
[ ] SKILL.md — 反模式表
[ ] SKILL.md — 审批门
[ ] SKILL.md — Item 类型说明
[ ] SKILL.md — 阶段结构
[ ] TEAM_INSTANCE_TEMPLATE.md — 环境模板示例
[ ] 其他：{位置}

**置信度**：[ ] 高（本任务明确踩坑）  [ ] 中（多次观察）  [ ] 低（直觉）
**Review 结果**：[ ] 待 review  [ ] 接受  [ ] 修改→{内容}  [ ] 拒绝→{原因}
```

---

## Workflow 3：Promote（任务结束后）

与 project-summary 的 Promote 流程相同：
1. 收集 TEAM_CONFIG.md 的 Promotion Candidates，按建议位置分组
2. 向用户展示，逐条 review
3. 执行：Edit 父类文件
4. Commit：`promote: {task} → {N} items`，更新 Changelog

---

## 阶段结构

阶段结构由 Workflow 0.5 选定的特化模板定义，参见 `templates/<name>.md` §1 Phase Plan。

**所有模板共享的父类约束（无论 Phase 编号 / 是否 SKIP Phase 0）：**
- 任何"并行"Phase 必须在同 message 派 ≥2 个 teammate（违反 §0.2 = 反模式）
- 每个 teammate 1-3 个 item，建议 teammate 上限 5（context 保护）
- 每个 teammate 输出 `WORK_DIR/progress/teammate-{N}.md`
- 涉及代码修改的 Phase 必须经过 Lead 审批门（见下文 §代码修改审批门）
- 验证类 Phase 必须同时跑 fix 路径 + baseline 回归（适用模板：dev-debug；其他模板按各自定义）

具体 Phase 数量、串/并行规则、产出物 schema、决策门 → 由模板覆盖。

---

## Lead 行为规则（父类）

> **前置：先满足 §0.1（Lead 不执行具体工作）和 §0.2（必须并行）。**
> 本节只描述 Lead 在"决策 + 协调 + 派单 + 读状态"边界内的具体动作。

### 启动 teammate 时传入（缺一不可）
1. 编号：`你是 teammate-{N}`
2. 上一个 teammate 的收尾存档摘要（如有）
3. 本次分配的 item 列表（含依赖关系）
4. 完整的 Teammate Prompt（从 TEAM_CONFIG.md 生成）
5. WORK_DIR 和 DOC_DIR 路径

#### Anthropic 4 要素必备校验（每次派单前自查）

每条 teammate prompt **必须**包含以下 4 要素（Anthropic「Built multi-agent research system」明文要求 — "Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries"）：

1. **Objective**（本次目标）— 一句话可量化
2. **Output format**（输出格式）— 引用 SHARED OUTPUT SKELETON 或显式列必填节（含 YAML front-matter REQUIRED 字段）
3. **Tools + sources guidance**（工具与来源指引）— 显式列允许用的工具 + 来源类型优先级（如「官方文档 > postmortem 博客 > 学术 > 一般博客」防 SEO 农场偏好）
4. **Clear task boundaries**（任务边界）— 显式列「不做」清单

> 这 4 要素与上方 5 项「编号 / 收尾摘要 / item / WORK_DIR / DOC_DIR」**正交补充**：上方 5 项侧重协调与上下文，4 要素侧重**任务规约 + 边界 + 输出契约**。两者并存，不替代。

#### 角色复用（templates/roles/ YAML 角色库 / Proposal-023, Wave 5）

常用角色（reviewer / synthesizer / web-researcher / doc-editor / debug-investigator）prompt 已抽到 `templates/roles/<name>.yaml`，每文件含 frontmatter（name / description / tools / suggested_model / isolated_context / must_read_tiers）+ backstory + 红线。

**Wave 派单时**：lead 可在 prompt 引用 `[Role: <name>]`（如 `[Role: reviewer]`），由 lead 拼装时 read `templates/roles/<name>.yaml` + 注入 wave 特化 item，避免每 wave 重写 5 项必备 prompt。

**与现有 wave 兼容**：旧的 ad-hoc prompt 仍可用（**0 BREAKING**）；新 wave 优先用 `[Role: ...]` 引用。cross-ref §6 Model Routing（suggested_model 字段）/ §1 Memory 4-tier（must_read_tiers 字段）/ §Reviewer Rubric（reviewer.yaml 引用）。

### 接收结果后（每次立即）
1. 读 `WORK_DIR/progress/teammate-{N}.md`
2. 更新 `WORK_DIR/todo.md`（[x] / [!]，附结论一行）
3. **立即**把有数据支撑的结论写入 DOC_DIR
4. 推断性内容不写入文档，加入 todo.md 等待验证

### 代码修改审批门（每个 fix 必须同时满足）
- [ ] 具体文件路径 + 精确行号
- [ ] 有实验数值或代码阅读证据（非推断）
- [ ] 有回归测试计划（说明如何验证基线不退化）
- [ ] proposed_fix 写在独立文件 `proposed_fix_{item}.md`（不共用）
- [ ] **Reviewer artifact spot-check**: 对 teammate progress 中每条「PASS / DONE」claim cross-check artifact；至少抽查 1/3 teammate 的 claim → artifact 链条（详见 §0.4 三类有效 artifact）

缺任何一条 → 不批准，加调查 item 补充。

### Reviewer Rubric（GPA 5 维 / Proposal-019，推父类）

每个 wave 收尾，reviewer 必须为整 wave 评 5 维 1-5 分（含 evidence 引用）。结构化评分维度统一在父类，4 模板 §3 通过引用本节使用（不重复 5 维表）。

| 维度 | 含义 | 评分依据示例 |
|---|---|---|
| Goal Fulfillment | wave 是否达成 GOAL 节目标 | 引用 GOAL 节 + deliverable 验证 |
| Logical Consistency | teammate 之间结论无矛盾 | 列具体冲突点（如 source URL 互相印证 / 抵触）|
| Execution Efficiency | tool call 总数 vs ideal、是否有重复劳动 | 列 wave_total_tool_calls vs §7 budget |
| Plan Quality | wave 计划本身是否合理（是否漏关键 item） | 列 missing items |
| Plan Adherence | teammate 是否走偏 / 越权 | 列每个 teammate 实际 vs 派单 |

**评分要求**：
- 每维 1-5 分（1 = 严重不达标 / 5 = 完美），分数必须附 evidence 引用（progress 行号 / artifact path / cmd output / URL 三选一，遵循 §0.4 三类 artifact）
- + Critical Findings 节（自由文本，标 P0/P1/P2，**不修复，不给妥协方案** — 与反模式表 #15 / status-consolidation §3 Reviewer Isolated Context 对齐）

**业界依据**：
- UC Berkeley RDI：警告盲信 LLM-as-judge 比没有 eval 更糟，应 "explicit rubric + few-shot + structured JSON 要 evidence before scoring"
- Agent GPA (arXiv 2510.08847)：5 维 trajectory-level 指标，可 LLM-as-judge reference-free 算

### Approval Vocabulary（typed user response）

Lead 派高风险 item（risk ≥ medium：git push / commit / 改源码 / GPU verify / 跑 prod 命令）
前，必须显式向用户 raise 4 选 1：

| Token | 含义 | Lead 后续动作 |
|---|---|---|
| **APPROVE** | 按草案执行，不再 review | 立即派 teammate / 立即执行（无延迟） |
| **EDIT: <patch>** | 改成这样后执行 | 应用 patch 后立即执行 |
| **REJECT: <reason>** | 不执行 + 提供原因（不是「再想想」） | 写 todo 记录 + 不重试 |
| **RESPOND: <question>** | 这是问答不是 approval gate | 回完继续 review |

用户使用自由文本时，lead 必须先 normalize 到 4 个 token 之一再行动；
歧义时反问「请明示 APPROVE / EDIT / REJECT / RESPOND」。

**announcement-instead-of-action 反模式**：
- lead 收到 APPROVE 后说「立即修正——」然后没动手 = 没修正 = 等同未 APPROVE
- APPROVE 后必须**下一个 tool call** 即执行，不能再写任何"宣告"性文字

### 存档规律
每处理 2 个 teammate 后写一次 `DOC_DIR/lead_progress.md`。

---

## Teammate Prompt 模板（父类共通骨架）

本节是**所有特化模板共享**的 prompt 共通骨架，包含：编号 / WORK_DIR / DOC_DIR / 铁则 / Context 保护 / 收尾流程 / Progress 文件格式 / 代码修改规则。
特化部分（BASELINE / 验证顺序 / 调研 vs 执行 / 任务专属红线 / 输出 schema）由 Workflow 0.5 选定的特化模板的 §3 Specialized Teammate Prompt Body 提供。

Lead 派 teammate 时按以下顺序拼装完整 prompt：
1. 本节共通骨架（替换 `{占位符}`）
2. + 特化模板 §3 Specialized Teammate Prompt Body
3. + 子类 TEAM_CONFIG.md 的 ENVIRONMENT / KNOWN_FACTS / 本次分配 item

子类实例生成完整 prompt 时，将 `{占位符}` 替换为 TEAM_CONFIG.md 中的对应字段。

```
你是 {PROJECT} 团队的 **teammate-{N}**。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 背景

目标：{GOAL}
约束：{CONSTRAINTS}

环境：
{ENVIRONMENT}
  ← 从 TEAM_CONFIG.md 的 ENVIRONMENT 节展开，包含：
     - 运行前置命令（cd /tmp 等）
     - 资源设置（GPU、内存等）
     - 缓存清理命令
     - git push 路径和 author
     - 长时任务运行方式

已知事实（无需重验）：
{KNOWN_FACTS}
  ← 从 TEAM_CONFIG.md 的 KNOWN_FACTS 节展开

---

## 铁则：结论必须来自真实数据

只有三类来源可作为结论：
1. 实际运行的实验数据（数值、日志、程序输出）
2. 直接读取的代码（文件路径 + 行号，原文引用）
3. 查阅的文档（文档名 + 章节）

发现自己在推断时 → 立即停下 → todo.md 加验证 item → 标注【未验证假设】。
progress 文件里"结论"和"【未验证假设】"必须分开写，绝不混用。
不得在未验证假设上继续后续工作。

---

## 验证顺序

验证顺序由 Workflow 0.5 选定的特化模板定义，参见 `templates/<name>.md` §5 Specialized Tools / Verification。
- `templates/dev-debug.md` — 4 步：最小复现 → 中间值 → 组件级 → 端到端 + baseline 回归
- `templates/ci-investigation.md` — web 工具优先级（curl raw log > WebFetch markdown）
- `templates/doc-edit.md` / `templates/status-consolidation.md` — 由模板各自定义（无 dev 类验证序）

{TASK_SPECIFIC_VERIFICATION}
  ← 从 TEAM_CONFIG.md 的 TASK_SPECIFIC_VERIFICATION 节展开
     （任务特有的验证注意事项，如特定工具路径、特定测试命令）

---

## 工作流程

### 启动
1. 读 {WORK_DIR}/todo.md
2. 读 team lead 给的上一个 teammate 收尾摘要（如有）
3. 把本次分配 item 改为 `[~] #{XXX} @teammate-{N}`
4. 开始工作

### Context 保护规则（严格执行）

tool calls 计数（心算）：
- < 15 次 → 正常工作
- 达到 15 次 → 当前 item 完成后立即收尾
- 达到 20 次 → **立即收尾**，无论 item 是否完成

### 完成 item 后
1. 追加写入 {WORK_DIR}/progress/teammate-{N}.md
2. todo.md `[~]` 改为 `[x]`，附结论一行（含来源）
3. tool calls < 15 且有 Pending item → 继续
4. 否则 → 收尾流程

### 卡住时
- `[~]` 改为 `[!]`，写明卡住原因和已尝试步骤
- progress 写 "Blocked: ..."
- 收尾流程

### 收尾流程

写入 {WORK_DIR}/progress/teammate-{N}.md：

## 收尾存档
- tool calls 累计：~N 次
- 已完成：#{XXX}, #{YYY}
- 当前 #{ZZZ}：已做到步骤 X，下一步是 Y
- 关键发现：[列出，含数据来源 + 文件行号]
- 【未验证假设】：[与结论分开]
- 给 lead 的建议：[列出]

更新 todo.md（未完成 item 加注"已存档，待继续"）。
最后回复：**"已存档，tool calls ~N 次，请读 progress/teammate-{N}.md"**

---

## 代码修改规则

### 提出修复方案（调查型 item）

写入 {WORK_DIR}/proposed_fix_{item编号}.md（每个 item 独立文件）：

## 修复方案 #{item}
文件：（绝对路径）
行号：（精确起止行）
改动前：（原文，不省略）
改动后：（修改后，不省略）
理由（来自代码 L行号 / 实验数值）：（必须有来源）
回归测试计划：{BASELINE 命令} + 预期通过标准

不直接修改代码，等 lead 明确批准。

### 实施修复（需 lead 在本次 prompt 明确批准）

1. 备份：`git -C {repo} diff > {DOC_DIR}/before_fix_{item}.patch`
2. Read 再 Edit
3. 记录修改行号到 progress
4. 不自行运行完整测试

---

## Progress 文件格式

每个 progress/teammate-{N}.md 顶部**必须**以下列 YAML front-matter 开头（机读 schema），后跟正文 markdown：

```
---
teammate_id: {N}
status: completed | blocked | partial          # REQUIRED
next_recommended: [teammate-X]                 # 可选；类似 LangGraph Command(goto)
suggested_model: opus | sonnet | haiku         # 实际跑用的 model（可选）
artifacts:                                     # REQUIRED — 每条 PASS claim 的 artifact
  - { type: file, path: /abs/path, line: 123 }
  - { type: cmd_output, snippet: "..." }
  - { type: url, url: "https://..." }
cost:
  tool_calls: ~12                              # REQUIRED — 心算 tool calls 数
  wall_time_min: ~8                            # 估算（可选）
blockers: []                                   # REQUIRED — 未解决问题；空列表 = 无 blocker
---

# Teammate {N} Progress

## 接手状态
[lead 摘要 / 上一个 teammate 收尾存档]

## 摘要（compaction 节，§8.1 配合）
<!-- tool calls ≥12 时优先填此节供 lead 只读（替代硬切）；< 12 可省略 -->
- 已完成事实：[1-3 句话]
- 未决问题：[1-3 句话]
- 下一步：[1-3 句话]

## 已完成 Items

### [#{XXX}] 标题
**类型**：调查型 / 执行型 / 验证型
**结论**（来自实验/代码/文档，附来源）：
**数据**：{指标值} / 文件 Y L行号 / 实验输出
**【未验证假设】**（如有，与结论分开）：

## 收尾存档
```

### Trace 节（OpenTelemetry 风格，wave-level 聚合用）

每个 progress 文件正文末尾**应**追加 `## Trace` 节供 wave-level 程序化聚合：

```
## Trace
- wave_id: {从 TEAM_CONFIG.md PROJECT 字段}
- start_ts: <ISO 8601>
- end_ts: <ISO 8601>
- tool_calls_by_type: {Read: x, Bash: y, WebSearch: z, ...}
- decisions: [<决策 1 brief>, <决策 2 brief>]
```

### REQUIRED 节标记

SHARED OUTPUT SKELETON 中所有以 `<!-- REQUIRED -->` HTML 注释标记的节为**必填**；
synthesizer 拼合 N 份 progress 时若发现某 teammate 缺 REQUIRED 节或缺 YAML front-matter，
**必须明示报告并 raise**，禁止假装拼上（防 MAST 论文「format mismatch silent fail」/ 反模式表 #12）。

向后兼容：旧 progress（无 YAML front-matter）不可作为 resume 起点；lead 重启 wave 时必须手动补或弃用旧 wave。

---

## 本次分配

**teammate-{N} 负责**：#{XXX}, #{YYY}
上一个 teammate 收尾摘要：{lead 填入}
具体 item 说明：{lead 填入}
```

---

## TODO List 格式

> Budget 节单独由 `TEAM_CONFIG.md ## Budget` 提供（schema 详见 §7 + TEAM_INSTANCE_TEMPLATE.md），不重复列在 todo.md。Lead 派单时**必须**在 prompt 末尾附 budget pressure 软警告（§7.2）。

```markdown
# TODO - {PROJECT}

## 规范
- [~] = 进行中（@teammate-N 认领）
- [x] = 完成（附结论一行）
- [!] = 卡住，需 lead 介入
- [ ] = Pending

## Phase 0（串行，必须先跑）
- [ ] #000 [验证] 当前状态 baseline → 记录结果

## Phase 1（并行调查，#000 结果决定重点）
- [ ] #A01 [调查] ... [depends: #000]
- [ ] #B01 [调查] ... [depends: #000，若 crash 在 X 阶段]

## Phase 2（执行，审批后）
- [ ] #C01 [执行] 实施 fix A（depends: #A02 批准）

## Phase 3（验证）
- [ ] #V01 [验证] fix 路径（预期指标：{指标} {阈值}）
- [ ] #V02 [验证] baseline 回归（预期：与 baseline 一致）

## In Progress
## Done
## Blocked
```

---

## Item 类型说明

父类提供通用 3 类（`[调查]` / `[执行]` / `[验证]`），由 dev-debug 模板使用。其他模板可定义自己的 Item 类型集（详见各模板 §4 Item Types）。

| 类型 | 说明 | 输出 | 允许的工具 | 主要使用模板 |
|------|------|------|-----------|------------|
| `[调查]` | 读代码 / 最小复现 / 中间值检测 | progress + proposed_fix_{item}.md | Read, Grep, Bash（只读或最小脚本） | dev-debug |
| `[执行]` | 修改代码 / 写文件 | progress + patch 备份 | Edit, Bash（需 lead 批准） | dev-debug, doc-edit |
| `[验证]` | 完整测试矩阵 | progress + DOC_DIR/04_verification.md | Bash | dev-debug |
| `[审计]` / `[编辑]` / `[评审]` | 文档审计、编辑、跨片一致性评审 | 详见 doc-edit 模板 §4 | Read, Grep, Edit | doc-edit |
| `[拉日志]` / `[分析]` / `[实证]` / `[报告]` | CI raw log 取证、依赖归属实证、报告写作 | 详见 ci-investigation 模板 §4 | Bash (curl), Read, Grep, WebFetch | ci-investigation |
| `[读]` / `[综合]` / `[评审]` | 多源 progress 摘录、综合 handoff、reviewer | 详见 status-consolidation 模板 §4 | Read, Grep | status-consolidation |
| `[escalate]` | 需用户决策才能继续（task 方向冲突 / scope 模糊 / 需 user trade-off）；teammate 写 ESCALATION.md 触发 lead 立即向用户 raise（不等 wave 收尾） | progress + `{WORK_DIR}/ESCALATION.md` | Read, Write | 所有模板 |

**模板可新增或屏蔽 Item 类型**，但所有模板都默认继承 `[调查]` / `[执行]` / `[验证]` 三类（除非模板 §4 显式覆盖）。

### `[escalate]` vs `[!] Blocked` 区别（Proposal-015 / HITL escalation）

- `[!] Blocked` = teammate 缺 evidence / 缺 access / 工具失败 → 需要补 evidence 或换 path（lead 派新 teammate 即可，不阻塞 wave）
- `[escalate]` = teammate 发现 task 方向冲突 / scope 模糊 / 需要 user trade-off 决策 → lead 立即 raise 给用户，不能自己决策
- **reviewer raise 致命问题**（如发现 baseline 跑错 model / proposal 草稿与用户原意偏离）属于 escalate，**不是** Blocked
  （来源：MEMORY.md 「reviewer 妥协方案不可盲信」2026-05-09）

### Escalate 触发协议（teammate 视角）

teammate 发现 escalate 触发条件时：
1. 在 `{WORK_DIR}/ESCALATION.md` 写：`## E-{编号}` + 触发原因 + 待 user 决策选项 (a)/(b)/(c) + 各自代价 + artifact 引用
2. progress.md `status: blocked` + blockers 列 escalate 原因
3. 收尾流程立即跑（不继续 next item）
4. 收尾消息额外加 "**ESCALATE**: 见 ESCALATION.md E-{编号}"

### Escalate 触发协议（lead 视角）

lead 收到 teammate 收尾消息含 `ESCALATE` 标签时：
1. **立即**读 `{WORK_DIR}/ESCALATION.md` 最新 E-{编号}
2. **不**派新 teammate；**不**自己决策；**立即**向用户 raise（按 §Lead 行为规则 Approval Vocabulary 提供 4 选 1）
3. 用户回复后再决定下一步（继续原 wave / 重派正确 task / close wave）

**业界依据**：
- AutoGen `HandoffTermination(target="user")`
- LangGraph `interrupt() + checkpoint`
- LangChain HITL: "Don't interrupt on reversible steps. Reserve it for irreversible, high-blast-radius, or regulated steps"

---

## 文档管理规则

- **所有输出写入 DOC_DIR（非临时目录）**：临时目录重启后消失
- **日志**：保存到 `LOG_DIR/`，重要日志复制到 DOC_DIR
- **proposed_fix 文件**：写到 WORK_DIR（若 WORK_DIR 是临时目录，同时写到 DOC_DIR）
- **lead_progress.md**：写到 DOC_DIR
- **teammate progress**：WORK_DIR/progress/（收尾时 lead 摘要写入 DOC_DIR）

---

## 6. Model Routing（per-role suggested model / Proposal-012）

所有 teammate 默认 inherit lead 模型，但每个 template 在 §3 Specialized Teammate Prompt Body
可标 `suggested_model: opus|sonnet|haiku` hint：

| Task 类型 | suggested_model | 理由 |
|---|---|---|
| dev-debug 根因调查 / 跨多文件重构 | inherit (opus) | reasoning-heavy |
| dev-debug verify 类 | sonnet | 跑命令 + 看 log，不需重 reasoning |
| doc-edit 编辑类 | sonnet | 文档 patch 不复杂 |
| doc-edit 审计类 | sonnet | 格式校验 |
| status-consolidation synthesizer | inherit | 多源综合需深推理 |
| status-consolidation reviewer | sonnet | 异源对比，但不需创造性（cross-model judge 配合 §3 Reviewer Isolated Context 原则）|
| ci-investigation research | sonnet | web search 快 + 文档读取 |
| ci-investigation 报告 | sonnet | 总结 |

**不强制**：用户 / lead 可按 wave 决定 override；hint 仅作默认。teammate progress front-matter 的 `suggested_model` 字段记录实际跑用的 model（机读对账用）。

**不引入自动 router**（binary router 需训练数据，复杂度过高）；
人工指定即可获 RouteLLM 80% 收益（按 LMSYS 数据外推）。

**预期成本节约**：当前 fleet cost ~$1535 / 30 天 → routing 后估计 ~$600-800 / 30 天
（Sonnet ≈ Opus / 5；Haiku ≈ Opus / 60；按 MEMORY.md llm-usage 实测 30 天数）。

**业界依据**：
- Anthropic — Built multi-agent："control costs by routing tasks to faster, cheaper models like Haiku"
- Anthropic Cookbook multimodal/using_sub_agents.ipynb：Opus orchestrate + Haiku worker 经典案例
- Claude Code subagent yaml frontmatter `model: haiku|sonnet|opus`
- CrewAI per-agent `llm` + `function_calling_llm`
- OpenAI Swarm per-agent `model` 字段
- LMSYS RouteLLM：matrix factorization router 14% GPT-4 calls 达 95% 性能

---

## 7. TODO Budget 字段（Proposal-016, BREAKING）

每个 wave 的 `TEAM_CONFIG.md` **必须**含 `## Budget` 节（schema 见 `TEAM_INSTANCE_TEMPLATE.md` Budget 节）；旧 wave 不写 budget 时使用 fallback 默认值（`wave_total_tool_calls=100 / per_teammate_default=20`），不阻塞 resume。

### 7.1 字段语义

| 字段 | 含义 | 默认 (fallback) |
|---|---|---|
| `wave_total_tool_calls` | 全 wave 上限（含 reviewer + synthesizer + 所有 teammate 累计） | 100 |
| `per_teammate_default` | 单 teammate 默认上限 | 20 |
| `per_teammate_overrides` | 复杂调研类 teammate 显式放宽（如 `{teammate-3: 30}`） | {} |
| `wave_total_estimated_usd` | 含模型 cost 估（按 §6 Model Routing 后估） | （选填） |
| `on_overrun` | 超预算时行为：`warn` / `abort` / `escalate-to-user` | `warn` |

### 7.2 Lead 派单 prompt 末尾强制加 budget pressure 软警告

> 剩余预算 N tool calls — 若快用完请收尾不要开新 task

teammate progress front-matter `cost.tool_calls` 字段供 lead 程序化对账（每 teammate 实际 vs 预算）。

### 7.3 Context 保护规则升级（多 axis，覆盖父类 Teammate Prompt 模板原 §Context 保护规则）

| Axis | 软警告 | 硬截断 |
|---|---|---|
| tool calls | ≥15 当前 item 完成后收尾 | ≥20 立即收尾 |
| 估算 token 累积 | ≥80K 收尾警告 | ≥120K 立即收尾 |
| wall-time | ≥30 min 自查「是否有真进展」 | ≥60 min escalate to lead |
| 同操作重复（含 tool+args_hash） | 连续 ≥5 次未拿新信息 raise STUCK | 连续 ≥8 次硬截断 |

**业界依据**：MetaGPT `team.invest($) + NoMoneyException`；CrewAI `max_rpm / max_iter / max_execution_time / max_retry_limit`；Anthropic — multi-agent "agents typically use about 4× more tokens than chat ... multi-agent systems use about 15× more tokens" / "Token usage explains 80% of the variance"；Inngest 软警告 + 硬截断（剩 10 iter "Start wrapping up" / 剩 3 iter "MUST respond NOW"）。

### 7.4 BREAKING 范围与向后兼容

- **BREAKING**：新 wave 必须在 `TEAM_CONFIG.md` 写 `## Budget` 节（fallback 仅作为旧 wave 兼容，新 wave 不写 = lead 应主动补全）
- **向后兼容**：旧 wave（无 Budget 节）resume 时 lead 用 fallback 默认值继续，不阻塞，但收尾时建议 promote 一条「补 Budget 字段」task

---

## 8. Compaction & Tool-Result Clearing（Proposal-025，仅 §8.1）

### 8.1 Teammate compaction（替代硬切，配合 §7 Context 保护多 axis）

tool calls **≥12** 时，**优先 compaction** 而非硬切（§7 Context 保护规则原 ≥15 软警告 / ≥20 硬截断之前）：

- teammate 生成「已完成事实 + 未决问题 + 下一步」3 段摘要写到 progress.md `## 摘要` 节（位置见 §Progress 文件格式 SHARED OUTPUT SKELETON）
- lead 后续只读 `## 摘要` 节不读全文（节省 lead context）
- 保留上下文连续性（不像硬切 → 下一 teammate 失去 context）

**何时硬切而非 compaction**：tool calls 已 ≥20（硬截断阈值）/ wall-time ≥60 min（硬截断 escalate）时，直接收尾不再 compaction（已 stuck 状态 compaction 也救不回）。

**业界依据**：Anthropic context engineering 三大对策之一 — compaction（总结后 reset）；与 structured note-taking（progress.md = 外部 file-based memory）+ sub-agent（本 skill 现有继承模型）配合。

> §8.2 Lead 视角 selective load + §8.3 Tool-result clearing 暂不落地（待 Defer-006 触发后再扩展）。

---

## 9. tmux Pane Visualization（手工方案 / 教学 & 调试用）

本节定义**手工 tmux 多 pane** 模拟 agent-team 的方案 — lead 在主 pane 跑 `claude`，右侧 3 个 pane 各跑一个**独立** `claude` session，lead 通过 `tmux send-keys` + file-based prompt 派单，通过 `tmux capture-pane` 监控。**与官方 `teammateMode: "tmux"` 并行存在，互补而非替代**。

### 9.0 Prerequisites & Bootstrap

本小节给出"从零到 §9.2 标准布局可跑"所需的全部前置依赖、bootstrap 脚本、session 命名约定、wave 目录骨架以及子 pane 就绪检测，作为 §9.1-§9.6 的入口。**配置后必须先跑 §9.0.5 readiness 检测，再进入 §9.3 派单**。

#### 9.0.1 前置依赖清单

| 依赖 | 最低版本 / 路径 | 备注 |
|---|---|---|
| tmux | **≥ 3.0**（实测 3.4） | `split-window -p%` 百分比形式在 3.0+ 已**移除**，本节统一用 `-l <lines>` explicit lines；3.0 以下的 `'{right}'` / `'{bottom-right}'` target 也未完全稳定 |
| claude CLI | `~/.local/bin/claude`（实测 `2.1.76`） | `which claude` 应能解析；若用 enterprise 部署，确认 `--dangerously-skip-permissions` 未被策略禁用 |
| `~/.claude/container.env` | 含 `ANTHROPIC_*` + 4 个 model 锁定变量（OPUS/SONNET/HAIKU/SUBAGENT） | **裸 `KEY=value` 格式**（由 podman `--env-file` 加载）；裸 bash 下需 `set -a; source $ENV_FILE; set +a` 才能 export 给 tmux 子进程。`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` **仅官方 agent-teams 模式需要**；本 skill 的 tmux 手工模式不需要此环境变量（各 pane 是独立 claude session，不走 TeamCreate / mailbox 协议） |
| 子 pane shell env | bash（默认） | 子 pane 是独立 shell 进程，**不**继承 lead claude 进程的内存态 env；必须在 bootstrap 脚本里先 source container.env，再 `tmux new-session` |

**`IS_SANDBOX=1` 的语义**：container.env **不含**此变量，必须在子 pane 启动命令前 **inline export**。缺失会导致子 claude 在 tool call 阶段触发 host 权限检查并阻断；配合 `--dangerously-skip-permissions` 才能进入 §9.5 反模式表所述的"独立 session 自主工作"模式。两者缺一不可。

#### 9.0.2 Session 命名约定

| 场景 | session 名 |
|---|---|
| 单 wave（默认） | `claudeteam` |
| 多 wave 并发隔离 | `claudeteam-<wave-id>`（如 `claudeteam-tmux_skill_wave2`） |
| 调试 / 教学一次性 session | 任意，但建议保留 `claudeteam` 前缀方便 `tmux ls \| grep claudeteam` |

**与 §0.6（Lead 整 wave 不变）配合**：一个 wave 独占一个 session；wave 收尾 → `tmux kill-session -t <name>`；切换 wave 前 close 旧 session，禁止跨 wave 复用 pane。

#### 9.0.3 Wave 目录骨架

Lead 在 Workflow 1 Step 4 (Instantiate) 阶段、**调用 bootstrap 之前**先创建：

```bash
WAVE_DIR=/home/junlin12/<wave-name>
mkdir -p $WAVE_DIR/{prompts,progress,logs}
```

- `prompts/teammate-N.md` — lead Write 落盘的派单内容（§9.3 file-based 协议）
- `progress/teammate-N.md` — teammate 自己写入的结果（与 §1 Memory Tier-3 Recall Memory 对应）
- `logs/` — 可选的 `tmux pipe-pane` 持久化输出 / bootstrap 探测产物

#### 9.0.4 Bootstrap 脚本（可直接 copy-paste）

```bash
#!/bin/bash
# tmux agent team 最小 bootstrap (1 lead + 3 teammate)
# 前置: §9.0.1 全部满足; WAVE_DIR 已 mkdir
set -e
SESSION=${SESSION:-claudeteam}
ENV_FILE=$HOME/.claude/container.env

# 1) 把 container.env 的裸 KEY=value 注入当前 shell, 让 tmux 子进程继承
set -a; source $ENV_FILE; set +a

# 2) 起 session, pane 0 = lead (左侧窄列)
tmux new-session -d -s $SESSION -x 240 -y 68 \
  "IS_SANDBOX=1 claude --dangerously-skip-permissions"

# 3) 右侧切 167 列容器, 再上下切 3 个 teammate pane (与 §9.2 一致, 全部用 -l)
tmux split-window -h -t $SESSION:0.0 -l 167 \
  "IS_SANDBOX=1 claude --dangerously-skip-permissions"
tmux split-window -v -t $SESSION:0.1 -l 34 \
  "IS_SANDBOX=1 claude --dangerously-skip-permissions"
tmux split-window -v -t $SESSION:0.2 -l 17 \
  "IS_SANDBOX=1 claude --dangerously-skip-permissions"
tmux select-pane -t $SESSION:0.0
```

**与 §9.2 的关系**：§9.2 假设 lead 已经在 `claudeteam:0` 主 pane 内手工 `claude`，只切右侧 3 pane；§9.0.4 用于**从零起 session**（lead 也作为脚本一部分启动）。两者命令风格、`-l <lines>` 数值、`IS_SANDBOX=1 claude --dangerously-skip-permissions` 启动串完全一致。

**spawn 时序说明**：bootstrap 脚本 4 条 `tmux ... claude --dangerously-skip-permissions` 在脚本返回时**仅完成 tmux pane 创建 + 子进程 fork**；子 claude 自身从 fork 到进入 `❯` REPL idle 状态另需 **~3-8s**（node runtime 启动 + API key 校验 + sandbox 初始化）。**bootstrap 脚本退出 ≠ 子 REPL ready**，必须紧跟 §9.0.5 readiness 检测，不可直接进 §9.3 派单。

#### 9.0.5 子 pane Readiness 检测（派单前必跑）

子 claude 进程从 spawn 到 REPL prompt-ready 需要数秒；若 §9.3 第一次 `send-keys` 在此之前发出，输入会被 shell 吞掉而非进入 claude REPL。Lead 在 bootstrap 完成后、首次派单之前必须逐 pane 检测：

```bash
SESSION=${SESSION:-claudeteam}
for p in 1 2 3; do
  echo "=== pane $p readiness ==="
  tmux capture-pane -t $SESSION:0.$p -p | tail -3
done
```

**判定标准**：tail 输出中必须出现 `❯` idle 提示符（claude REPL 等待输入态）。若看到的是 shell `$` 提示符 → 子 claude 已退出（检查 API key / quota / `--dangerously-skip-permissions` 是否被策略拦）；若 tail 为空或显示 "Cogitated..." 进行中 → 再等几秒重抓。**3 个 pane 全部 `❯` 才算 §9.0 配置完成**，可进入 §9.1 决策与 §9.3 派单。

**脚本化轮询变体**（自动等到全部 ready，适合 bootstrap → smoke test 串行流水）：

```bash
SESSION=${SESSION:-claudeteam}
for p in 1 2 3; do
  while ! tmux capture-pane -t $SESSION:0.$p -p | grep -q '❯'; do
    sleep 2
  done
  echo "pane $p READY"
done
```

→ readiness PASS 后跑 §9.7 smoke test 做端到端 roundtrip 验证，**确认 file → send-keys → 子 claude 响应链路真通**后再进 §9.3 真实派单。

### 9.0.6 statusLine（推荐：每 pane 显示 context% + cost）

多 pane 并行时 lead 需快速判断每个 teammate 的 context 余量 + 累计 cost 才能决策是否 refresh（§9.6.5.4）/ 是否继续派单。给 `~/.claude/settings.json` 加 `statusLine` 字段（顶层，与 `permissions` 平级），所有 pane 实时渲染（settings hot-reload，不必重启已运行的 claude）：

```json
"statusLine": {
  "type": "command",
  "command": "python3 -c 'import json,sys,os; d=json.load(sys.stdin); m=d.get(\"model\",{}).get(\"display_name\",\"?\"); ctx=(d.get(\"context_window\") or {}).get(\"used_percentage\") or 0; cost=(d.get(\"cost\") or {}).get(\"total_cost_usd\") or 0; cwd=os.path.basename((d.get(\"workspace\") or {}).get(\"current_dir\",\"\") or d.get(\"cwd\",\"\")); print(f\"[{m}] ctx {ctx}% | ${cost:.2f} | {cwd}\")'"
}
```

渲染示例（每 pane 底部一行）：`[claude-opus-4-7] ctx 43% | $28.28 | junlin12`

**字段来源**（stdin JSON schema，官方）：
- `context_window.used_percentage` — input-only 百分比（首次 API call 前为 `null`，已用 `// 0` 兜底）
- `cost.total_cost_usd` — client-side 估算，不反映 AMD Gateway 实际 charge-back（实际 charge 走 `llm-usage` skill 查 UsageStats）
- `model.display_name` / `workspace.current_dir`

**用 `python3` 而非 `jq`**：tmux pane 标准环境可能无 `jq`；如装了 `jq` 可换为单行 jq 命令。亦可用 `npx -y ccusage statusline` 拿更丰富的 burn-rate 数据（要联网 npm registry）。

### 9.1 何时用 / 何时不用

| 场景 | 用本方案 | 用官方 Agent / `teammateMode: "tmux"` |
|---|---|---|
| 演示 / 教学 / 实时观察多 teammate 工作 | ✅ | ❌（子进程不可见） |
| 调试 agent-team 框架本身 | ✅ | ❌ |
| 官方 `teammateMode: "tmux"` 在当前环境不生效 | ✅ 手工兜底 | — |
| 单 teammate 任务 | ❌（开销大） | ✅ 直接 Agent tool |
| 需要 mailbox / SendMessage / shutdown_request 协议 | ❌（独立 session 不支持） | ✅ |
| 无人值守自动 wave / 自动重试 | ❌（独立 session 不共享 task list） | ✅ |

### 9.2 标准布局命令（lead 在主 pane 跑一次）

> bootstrap 命令（含起 session + spawn 4 个 `claude`）见 §9.0.4；本节聚焦布局参数推导逻辑（`-l <lines>` 数值由 240×68 终端 / 70+167 列 / 16/16/17 行实测得出）。

```bash
# 右侧 pane（167 列），再上下切 3 个
tmux split-window -h -l 167 'bash'
tmux split-window -v -t '{right}' -l 34 'bash'
tmux split-window -v -t '{bottom-right}' -l 17 'bash'
tmux select-pane -t 0

# 每个右 pane 启动 interactive claude（sandbox + skip permissions）
for p in 1 2 3; do
  tmux send-keys -t claudeteam:0.$p \
    "IS_SANDBOX=1 claude --dangerously-skip-permissions" Enter
done
```

### 9.3 派单机制（file-based，禁止 multi-line 直传）

```bash
# 1) Lead 用 Write 工具把 prompt 落盘
#    /home/junlin12/<wave>/prompts/teammate-1.md
# 2) send-keys 触发子 claude Read 该文件
tmux send-keys -t claudeteam:0.1 \
  "请读取 /home/junlin12/<wave>/prompts/teammate-1.md 并执行" Enter

# 3) 监控 / 收结果
tmux capture-pane -t claudeteam:0.1 -p | tail -20      # 看 pane 输出
cat /home/junlin12/<wave>/progress/teammate-1.md       # 读 teammate 写入
```

**为什么 file-based**：`send-keys` 对 multi-line / 含特殊字符的 prompt 极易失真（换行被吃 / quote 错位 / Enter 时机错乱）；落盘 + Read 把"派单内容"和"触发信号"解耦，与 §0.5 teammate 不递归派单铁则共享同一文件协议。

### 9.4 与官方 `teammateMode: "tmux"` 的区别

| 维度 | 本方案（手工） | 官方 `teammateMode: "tmux"` |
|---|---|---|
| pane 创建 | lead 手工 `split-window` | spawn teammate 时自动 |
| session 关系 | 各 pane 独立 `claude` session | 同一 team / 共享 mailbox + task list |
| 派单通道 | 文件 + `send-keys` | `Agent` tool / `SendMessage` |
| Shutdown / mailbox 协议 | ❌ 不支持 | ✅ |
| 可视化 | ✅ 100% 可见 | ✅（pane 内）|
| 适用场景 | 教学 / 调试 / 兜底 | 生产 wave |

**实测注意**：`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 + teammateMode: "tmux"` 时，**`Agent` tool 仍走子进程模式**（不创建 pane），只有 `TeamCreate` + 显式 spawn 才会创建 pane。混用本方案不会冲突，但 lead 必须清楚二者 task list 不互通。

### 9.5 反模式

| 反模式 | 正确做法 |
|---|---|
| 把右 pane 子 claude 当作 agent-team 子类（期待它收 `SendMessage` / 接 `TeamCreate` task） | 当作**独立 session**对待；通过文件协议传递 prompt / progress |
| `send-keys` 直接传 multi-line prompt | 永远先 Write 到 `prompts/teammate-N.md`，再 `send-keys` 触发 Read |
| 派单后不 `capture-pane` 也不读 progress 文件，假设子 claude 一定在跑 | 至少 `tmux capture-pane \| tail` 一次确认进入工作状态；异常退出 lead 收不到通知 |
| 用本方案跑无人值守长 wave | 改用 §0/§2 + 官方 Agent tool；独立 session 无 task list 不利于自动重试与 §0.6 lead 不变铁则 |
| 多个 lead 共用同一 tmux session 互相 `send-keys` | 违反 §0.6 lead 整 wave 不变；每个 wave 独占一个 session |
| Lead 自己 send-keys 到自己 pane 0（试图自派单） | lead pane 0 仅做协调（决策 / Write prompt / capture-pane / 读 progress）；执行类动作必须 send-keys 到 pane 1/2/3 任意 teammate pane；自派会让 lead REPL 收到自己派的 prompt 形成回路，且违反 §0.1 lead 不执行铁则 |
| 调试时跑 `tmux split-window` 不带参数 / 不带 `-t target` → 创建孤立 bash pane 打乱 pane 编号 | 任何 `split-window` 必须显式 `-t $SESSION:0.X` 指定父 pane + 跟启动命令（`'bash'` 或 `'IS_SANDBOX=1 claude --dangerously-skip-permissions'`）；孤立 pane 会让 §9.0.4/§9.2 后续 `:0.1/:0.2/:0.3` 编号全部错位，readiness loop / 派单 target 都失效 |

### 9.6 业界依据 / cross-ref

- 与 §0.2（**Phase 1 同 message 派 ≥2 teammate**）正交：本节给的是**可视化呈现层**，并行原则仍由 lead 在主 pane 一次性触发多个 `send-keys`（同一 assistant turn 内连发，禁止"先发一个看效果"）。
- 与 §0.5（**Teammate 不递归派单**）共享 file-based 协议：prompt / progress 都走 `<wave>/prompts/` 与 `<wave>/progress/` 目录约定。
- 与官方 Claude Code `teammateMode: "tmux"` 文档互补；本节明确"手工方案 = 教学 / 兜底"，不取代官方模式作为生产路径。

### 9.6.5 Persistent Role Assignment

§9.0-§9.6 只规定 tmux 布局与派单协议。本节定义 **4-pane 角色映射 + 跨 wave 持久化保证**，让每个 pane 成为长生命周期专职 teammate。所有 cross-ref 集中在 §9.6.5.6。

#### 9.6.5.1 标准 4-pane 角色表（SSOT）

| Pane | 角色 | 职责 | 主要适用模板 |
|---|---|---|---|
| `:0.0` | **lead** | 决策 / 派单 / 读状态（§0.1 例外 5 类） | 全部 |
| `:0.1` | **auditor + patcher** | 对照 review 改文档 / apply approved patch / commit-currency 校验 | dev-debug / doc-edit / ci-investigation |
| `:0.2` | **drafter** | 起草新 prompt / 新节 / 新模板；synthesize 多源摘录 | doc-edit / status-consolidation |
| `:0.3` | **architect + reviewer** | 框架级设计 / GPA 5 维 review / §0.4 artifact 抽查 ≥ 1/3 | 全部 |

4 = 1 lead + 3 teammate（与 §9.2 标准布局对齐）。**本表是角色映射 single source of truth**；其他节（如 §-0.5）应 cross-ref 本表而非重复。

#### 9.6.5.2 持久化保证

跨 wave 复用同一 pane 给同一角色 → 子 claude 子进程 context history 不丢失 = 跨 wave 记忆。三条强制约束：

1. **PID 不变 = context 不变**：wave 切换不 respawn / 不 `/clear`；bootstrap 仅首 wave 跑一次，后续 wave 直接复用
2. **派单 prompt 必须显式触发角色记忆**：跨 wave 第 1 次派单 prompt 开头必须写 `你的持久化角色 = <role>（在所有 wave 中持续承担此角色，做 <职责简述> 类工作）。`，作为 self-anchor 防 role drift
3. **Lead 在 TEAM_CONFIG.md 顶部声明 `## Pane Role Map`** 作为单源真相

**`## Pane Role Map` schema 建议**（在 TEAM_CONFIG.md 模板新增）：

```markdown
## Pane Role Map

| Pane | 持久角色 | 本 wave 临时角色 | refresh 状态 | GPA history（可选） |
|---|---|---|---|---|
| :0.0 | lead | — | — | — |
| :0.1 | auditor+patcher | — / log-fetcher (wave-N) | — / refreshed @ wave-M | wave-N: 4.2 / wave-M: 4.5 |
| :0.2 | drafter | — | — | — |
| :0.3 | architect+reviewer | — | — | — |
```

- "本 wave 临时角色" 仅 wave 内有效；跨 wave 持续 ≥ 2 wave 应升格为持久变更（见 §9.6.5.3）
- "GPA history" 可选；用于 §9.6.5.4 refresh 触发参考
- 此节是单源真相，teammate prompt cross-ref 之

#### 9.6.5.3 角色 vs 模板的关系

`templates/<name>.md §3 Specialized Teammate Prompt Body` 应按角色分段（如 doc-edit §3：`pane-1 (auditor) / pane-2 (drafter) / pane-3 (reviewer)`）而非按抽象 `teammate-N`。

**临时角色覆盖**：当模板需要的角色 ≠ 标准 4 角色（如 ci-investigation 需要 log-fetcher），允许临时复用 pane（如 pane-1 临时承担 log-fetcher），lead 必须在派单 prompt 显式声明：
```
你的持久化角色 = auditor + patcher，但**本 wave 临时角色 = log-fetcher**
（理由：...；下 wave 回归 auditor）。
```
TEAM_CONFIG.md `## Pane Role Map` 同步注明。

**若临时角色需跨 ≥ 2 wave 持续，应正式升格为持久角色变更**（在 TEAM_CONFIG.md `## Pane Role Map` 写明，并标 `effective wave-N onward`），避免长期"临时"侵蚀持久角色契约。

#### 9.6.5.4 跨 wave Context Drift 风险 + Refresh 协议

**风险**：pane 子 claude 跑 ≥ 5 wave 后 context 接近上限 → reasoning 退化 / tool call 截断。

**触发信号**（lead 每 wave 收尾后检查；命中任一触发 refresh）：

| # | 信号 | 类型 |
|---|---|---|
| 1 | pane 累计 wave 数 ≥ 5 | **hard**（数值） |
| 2 | 单 wave 末 progress.md 出现 "context too long" / "truncated" / 子 claude 主动建议 `/compact` | **hard**（grep 可证） |
| 3 | 该 pane 近期 reasoning 质量下降（如 GPA Logical Consistency 维度连续 2 wave ≤ 3、明显的指令遗漏 / 误读） | **soft**（reviewer 主观判断；GPA 历史可参考 TEAM_CONFIG.md `## Pane Role Map` GPA column 但非强制依据） |

**Refresh 协议**（命中任一信号）：
1. lead 派 `tmux send-keys -t claudeteam:0.N '/clear' Enter` 给该 pane → 子 claude 清空 context
2. 下个 wave 第 1 次派单 prompt 开头**重注角色 + 最近 1-2 wave 关键决策摘要**（lead 从 WAVE_CLOSE.md 摘录 ≤ 10 行）
3. TEAM_CONFIG.md `## Pane Role Map` 标 `refreshed @ wave-N`
4. **Refresh 不重 bootstrap pane**（PID 不变 / 角色不变 / 仅 context 清）

**Refresh 不适用于 lead pane**（§0.6 lead 整 wave 不变；跨 wave 换 lead 须走 WAVE_CLOSE 协议而非 `/clear` 短路）。

#### 9.6.5.5 反模式（角色持久化特化）

| 反模式 | 正确做法 |
|---|---|
| 每 wave 重 bootstrap / `respawn-pane -k` 销毁子 claude | 跨 wave 复用 PID；仅在子 claude 死或 §9.6.5.4 触发 refresh 时才动 pane |
| 跨 wave 派单 prompt 省略"持久化角色 = X"开头 | 即使 context 仍在，显式声明 self-anchor 必加 |
| 一个 wave 内动态在 4 pane 之间换角色 | 角色绑 pane / 不绑 wave；同 wave 内角色稳定 |
| 给 reviewer pane（:0.3）派纯执行任务（如跑 baseline） | reviewer pane 应 read-heavy / isolated context；执行类派 :0.1 patcher 或 :0.2 drafter |
| pane-1/2/3 互相 send-keys（cross-pane peer 通信） | 永远经 lead 中转；pane 之间通过 file-based progress 间接通信 |

#### 9.6.5.6 业界依据 / cross-ref（集中）

- §0.1（lead 不执行）：本节不改变 lead 行为；只给"派给谁"的稳定映射
- §0.2（必须并行）：4 个固定角色 pane 同 message send-keys 天然 ≥ 2 并行
- §0.4（self-report 不可信）：reviewer pane（:0.3）专职 artifact 抽查 ≥ 1/3
- §0.6（lead 整 wave 不变）：本节扩展为"所有角色 pane 在 wave 边界尽量不变"
- §9.0.4 bootstrap：起 4 pane 一次 → 本节定义 4 pane 长期分工
- §9.4 手工 vs 官方 teammateMode：手工方案"独立 claude session"恰好是 persistent role 的基础设施
- templates/`<name>`.md §3：模板 §3 应按角色（auditor / drafter / reviewer）分段

### 9.6.6 Dispatch Completeness Checklist

防 lead 派单遗漏 / send-keys 未送达 / wave 收尾时漏掉某 pane（wave3 实证 P0-A：pane-1 progress 缺失，lead 未察觉）。Lead 在每次派单前后必须执行三步闭环：

#### 9.6.6.1 派单后立即落 dispatch.log

每次 `tmux send-keys` 后**同 turn 内**追加一行到 `$WAVE/logs/dispatch.log`：

```bash
echo "[wave-$WAVE_ID] dispatched: pane-$N → $PROMPT_PATH @ $(date -Iseconds)" \
  >> $WAVE/logs/dispatch.log
```

- 一行 / 一个 send-keys；多 pane 并行派单 → 多行
- 时间戳用 `-Iseconds` 便于排查 send-keys 间隔（cross-ref §9.0.5 readiness）
- **schema 锁定**：行首必须 `[wave-N] dispatched:`；新字段加在 `@ timestamp` 之后，不要插在行首；否则 §9.6.6.3 `grep -c '^\[wave-'` 对账 silent 失效。

#### 9.6.6.2 派单后 receipt 确认（至少 1 次）

派单完成后 lead 必须至少跑一次：

```bash
tmux capture-pane -t claudeteam:0.$N -p | tail -3
```

确认 send-keys 已被子 claude 接收（应看到 `❯ 请读取 .../prompt-path 并执行` 或子 claude 已开始 Read 提示）。**未确认 = 视为派单未送达**，按 §9.8 troubleshooting 排查（pane index 错 / 子 claude 死 / 派单 prompt 文件路径错）。

#### 9.6.6.3 Wave 收尾对账

Wave 收尾时（写 WAVE_CLOSE.md 前）lead 必须：

```bash
EXPECTED=$(grep -c '^\[wave-' $WAVE/logs/dispatch.log)        # 派单总数
DELIVERED=$(ls $WAVE/progress/wave${WAVE_ID}-pane-*.md | wc -l) # 实际 progress 数
[ "$EXPECTED" = "$DELIVERED" ] || echo "MISSING: $((EXPECTED - DELIVERED)) panes"
```

不一致 → 派 reviewer pane（:0.3）按 §9.6.5.5 反模式 #5 红线（不 send-keys 探询）改用 capture-pane 诊断；若确认 pane 仍工作中则延后 WAVE_CLOSE；若 pane 已死则记入 WAVE_CLOSE 的 "incomplete deliverables" 节。

#### 9.6.6.4 反模式

| 反模式 | 正确做法 |
|---|---|
| 派单后不写 dispatch.log，wave 收尾凭记忆数 pane | 每次 send-keys 同 turn 落 log；收尾按 §9.6.6.3 对账 |
| 派单后不 capture-pane receipt，假设 send-keys 一定送达 | 至少 1 次 capture-pane tail；连续 3 个 pane 都不 capture = 反模式 |
| 发现 pane progress 缺失就 send-keys 探询（violate §9.6.5.5 #5 / R4-F4 deadlock）| 用 `tmux capture-pane` 只读诊断；必要时 lead 自己派新 prompt 给该 pane（不允许 reviewer pane 越权 send-keys） |
| **auditor apply 后仅 grep 节名/行号验证，不做语义 spot-check** | 落地后必须 ≥1/3 grep 语义关键字（如新增措辞 / schema 字段），与 §0.4 reviewer artifact 抽检规则对齐 |

#### 9.6.6.5 cross-ref

- §9.0.5 readiness：派单前；§9.6.6 receipt：派单后；§9.7 smoke：bootstrap 后整体验证 — 三者覆盖派单生命周期
- §9.8 troubleshooting：receipt 失败的处置流程
- §9.6.5.5 反模式 #5：cross-pane deadlock 禁令，§9.6.6.3 收尾对账时必须遵守

### 9.7 Verification Roundtrip Smoke Test（setup 后必跑）

**目标**：在 §9.2 布局 + §9.3 派单协议落地后，**派任何真实 teammate 之前**，先跑一次最小 roundtrip（file → send-keys → capture-pane → 子 claude 响应），验证目标 pane 的子 claude 处于 idle 且能正常 Read + 执行 prompt。失败则不要进入 §9.3 真实派单，先走 §9.8 Troubleshooting。

**5 步可复制脚本**（以验证 `claudeteam:0.3` 为例，改 pane id 即可复用）：

```bash
WAVE=/home/junlin12/<wave>
PANE=claudeteam:0.3
mkdir -p $WAVE/prompts $WAVE/logs

# 1) write 测试 prompt（让子 claude 回 ROUNDTRIP-OK + 用 $TMUX_PANE 自报 pane）
cat > $WAVE/prompts/roundtrip_test.md <<'EOF'
请执行一次：`bash -c 'echo "ROUNDTRIP-OK from pane $TMUX_PANE"'`
然后回到 idle，不要做其他事。
EOF

# 2) 基线 capture（确认 pane idle、无残留 spinner / approval prompt）
tmux capture-pane -t $PANE -p -S -5 > $WAVE/logs/pane3_before.txt
tail -3 $WAVE/logs/pane3_before.txt   # 末行应为 `❯`

# 3) send-keys 触发
tmux send-keys -t $PANE \
  "请读取 $WAVE/prompts/roundtrip_test.md 并执行" Enter

# 4) 等待 + 二次 capture（实测 25s 内完成；首跑给 30s 余量）
sleep 30
tmux capture-pane -t $PANE -p -S -30 > $WAVE/logs/pane3_after.txt

# 5) diff 看 ROUNDTRIP-OK 是否出现
diff $WAVE/logs/pane3_before.txt $WAVE/logs/pane3_after.txt | grep -E 'ROUNDTRIP-OK|● Read'
```

**PASS 标准**（三条全满足才算通过）：

| # | 检查项 | grep 关键字 |
|---|---|---|
| 1 | capture-after 含 `ROUNDTRIP-OK` 字样 | `ROUNDTRIP-OK` |
| 2 | 含 `● Read` 工具调用痕迹（证明子 claude 真的读了 prompt 文件，不是把整段 send-keys 当文本回显） | `● Read` |
| 3 | capture-after 末尾回到 `❯` idle 提示符（证明本 turn 已结束，pane 可继续接派单） | 末行 `❯` |

**实测基线**（tmux_skill_wave2 pane3 实证 2026-05-22）：

| 指标 | 实测 | 阈值 |
|---|---|---|
| send-keys → capture 含 ROUNDTRIP-OK | 25s（含 Read + Bash + 回 idle 全链路） | < 30s ✅ / > 60s ❌ 进 §9.8 |
| 工具调用 (lead-side) | Bash×4 + Write×2 = 6（lead 在主 pane 跑的 capture/send-keys/diff/Write prompt） | 上限 10 |
| 工具调用 (subclient-side) | TBD（pane-2 wave3 补测：子 claude 在被派 pane 内为完成 roundtrip prompt 实际 Read + Bash 次数） | 上限 5（roundtrip 本身极小） |

> **超 60s 视为子 claude 卡住** → 不要再补 send-keys（会被当 mid-turn 反馈），转 §9.8 Troubleshooting 排查（mid-tool / plan mode / approval / 路径错）。

**Caveat — pane index 漂移**：子 claude 内 `tmux display-message -p '#{pane_index}'` 默认返回 **client active pane** 而非 invoking pane（实测 send-keys 到 `:0.3` 但子 claude 自报 `pane 2`）。**自报 pane 必须用 `echo $TMUX_PANE` 或 `tmux display-message -t $TMUX_PANE -p '#{pane_index}'`**。不影响协议本体（lead 只要 send-keys target 写对，prompt 就送达正确 pane），但若 PASS 标准 #1 的 echo 用 `display-message` 写法，diff 会出现"pane 号对不上"的假告警，误判 roundtrip 失败。

**业界依据 / cross-ref**：
- 与 §0.4（**Teammate self-report 不可作为 ground truth**）一致：PASS 不靠"子 claude 说 OK"，靠 lead 的 capture-pane diff 客观证据
- 与 §9.3 file-based 派单协议同构（同一目录约定 + 触发机制），smoke test 复用真实派单的所有基础设施
- 失败排查清单见 §9.8 Troubleshooting

### 9.8 Troubleshooting

§9.7 smoke test 失败、或 wave 中途 roundtrip 异常时，按下表对照症状 → 诊断 → 修复。所有诊断命令都是**只读**的（`list-panes` / `capture-pane` / `show-environment`），可放心执行。

| 症状 | 诊断 | 修复 |
|---|---|---|
| `send-keys` 后 `capture-pane` 看不到 prompt 文本出现在子 pane | `tmux list-panes -t claudeteam -F '#{pane_index} #{pane_current_command}'` 看 pane index 是否正确、对应进程是否是 `node`/`claude` 而非 `bash` | 校正 `claudeteam:0.N` 中的 N；若是 bash 说明子 claude 已退出，按下一行处理 |
| 子 pane 显示 bash prompt 而非 ❯（子 claude 进程死了） | `tmux list-panes -F '#{pane_pid} #{pane_current_command}'` 确认；查 `~/.claude/logs/*.log` 是否 OOM / API 错误 | `tmux respawn-pane -t claudeteam:0.N -k 'IS_SANDBOX=1 claude --dangerously-skip-permissions'` 原地重启该 pane，不破坏布局 |
| 子 pane 报 `Command not found: claude` | `tmux send-keys -t claudeteam:0.N 'which claude; echo $PATH' Enter` 后 capture | 在 `~/.bashrc` 加 `PATH`，或 respawn 时用 absolute path（如 `/home/junlin12/.local/bin/claude`） |
| 子 claude 收到 prompt 但无响应（pane 显示派单文本但无 `●` 工具调用） | `tmux capture-pane -t claudeteam:0.N -p \| tail -20` 看是否卡在 permission prompt / plan mode / 上一 turn 未结束 | 补一个 `tmux send-keys -t claudeteam:0.N '' Enter` 单独送 Enter；仍无响应则 respawn pane，确认启动 flag 含 `--dangerously-skip-permissions` |
| `send-keys` 多行 prompt 被截断 / 乱码 / quote 错位 | 反模式 — `send-keys` 对 multi-line 不可靠（§9.3 / §9.5） | 永远 Write 到 `<wave>/prompts/pane-N.md` + 单行 `send-keys "请读取 /abs/path 并执行"`（file-based 协议） |
| 子 claude API 报 401 / 403 / "missing key" | `tmux send-keys -t claudeteam:0.N 'env \| grep -i anthropic' Enter` 后 capture；或 `tmux show-environment -t claudeteam` | 启 pane 前 `set -a; source ~/.claude/container.env; set +a`；或在 `~/.bashrc` 持久化（参考 §9.0 Prerequisites 环境变量清单） |
| `capture-pane` 截到的输出被刷掉（scrollback 不够） | `tmux capture-pane -p -S -200` 加大回溯仍不够 = 已被 ring buffer 覆盖 | 派单前 `tmux pipe-pane -t claudeteam:0.N -o 'cat >> <wave>/logs/pane-N.log'` 持久化全程输出，long-running wave 必备 |
| `tmux: no server running` / session 不存在 | `tmux ls` 看 server 是否起、`claudeteam` session 是否在 | `tmux new-session -d -s claudeteam`，再按 §9.2 重做布局；多 wave 并发时用 `claudeteam-<wave-name>` 避免冲突（§9.0 命名约定） |
| 子 pane index 自报值与 lead target 不一致（如 lead `send-keys -t :0.3` 子 claude 自报 pane 2） | `tmux display-message -p '#{pane_index}'` 默认作用于 client 的 active pane，非 invoking pane | 子 claude 内自报 pane id 用 `echo $TMUX_PANE` 或 `tmux display-message -t "$TMUX_PANE" -p '#{pane_index}'`；不影响 lead 派单正确性 |

#### Teardown

Wave 完成后清理（cross-ref §0.6 lead 整 wave 不变 / wave 边界换 session）：

```bash
# 1) 归档 logs（如启用 pipe-pane 持久化）—— progress/ 文件按 §1 Memory tier 保留策略处理
ls /home/junlin12/<wave>/logs/

# 2) 关闭整个 tmux session（连同 4 pane + 子 claude 进程）
tmux kill-session -t claudeteam
```

下一 wave 起新 session（`claudeteam-<next-wave>`），不复用旧 session 的 pane —— 与 §0.6 "lead 整 wave 不变 / wave 边界换 session" 一致。

---

## 反模式表（通用，父类维护）

本表只维护**所有模板共享**的通用反模式。**dev-debug / doc-edit / status-consolidation / ci-investigation 模板各自的特化反模式见各 templates/<name>.md §6 Specialized Antipatterns。**

| 反模式 | 正确做法 |
|--------|---------|
| #1 并行 teammate 共用同一个 proposed_fix.md / 输出文件 | 每个 item 独立文件（防并行写冲突）。**同样适用于 wave-level shared deliverable / 同一 patch 文件 / consolidated report —— 写入必须串行**（参见 §0.3 Writes single-threaded） |
| 日志 / 结果写临时目录 | 写持久路径（DOC_DIR） |
| 从错误的仓库 push 导致 author 错误 | 明确 push 仓库路径和 author 配置（子类 ENVIRONMENT 指定） |
| 多假设串行调查 / 串行派 teammate | 同 message 里发 ≥2 个 Agent tool call 并行（违反 §0.2） |
| "待验证假说"放入 KNOWN_FACTS | KNOWN_FACTS 只收录有代码行号或实验数据的已验证事实；"待验证"的放 TODO [调查] item，附验证方法（来源：fp8-tp2 任务 F14 案例） |
| Lead 自己跑 Bash 调研 / 读源码分析 / 跑业务命令 | 派 teammate（违反 §0.1） |
| Lead 串行派 teammate（一个等一个完成） | 同 message 里发 ≥2 个 Agent tool call 并行（违反 §0.2） |
| 单 teammate 任务也走 agent-team 流程 | 直接单上下文做完，不要走 agent-team 框架 |
| Workflow 0.5 不选择模板，直接套通用 SKILL.md | 必须先按决策树选 templates/<name>.md，模板覆盖父类阶段结构 / Item 类型 / Specialized Antipatterns |
| 把模板特化反模式（如 dev-debug 的"crash 直接改代码"）当父类规则 | 特化反模式在各 templates/<name>.md §6；父类只管通用条 |
| Reviewer raise"致命"问题时盲信其妥协方案 | reviewer 视角 = 找最低执行成本；lead 视角 = 对齐用户真实任务目标。raise 多半是 task 方向修正信号，lead 应主动认错 / 派新 teammate 对齐目标，而不是按 reviewer 妥协方案继续跑（来源：tp2_verify_post_merge_wave 2026-05-09） |
| #12 Format mismatch / 无 inter-teammate schema → synthesizer 静默吃错（teammate 漏写关键节、字段名漂移、单位不一致，synthesizer 拼合时 silent fail，下游 wave 拿错信号）| 强制 YAML front-matter（status / artifacts / cost / blockers REQUIRED）+ `<!-- REQUIRED -->` 节标记；synthesizer 必须 grep REQUIRED + 校验 front-matter，缺失即 raise，禁止 silent skip（参考 MAST 论文 37% coordination breakdowns；Proposal-013 / 来源 T3-Source-4 / 5 / 6）|
| #14 Parallel-writer divergence（多 teammate 并行 Edit 同一文件 / 同一 deliverable / 同 component 不同部分，写入互相覆盖或风格不一致）| 写入串行：trivial 5-15 行 lead 自己 Edit；非 trivial → 派单 integrator teammate 串行汇总；多文件 → contract definer 先定 interface（违反 §0.3；来源：T3-Source-1 Cognition Flappy Bird / T3-Source-2 Cognition narrow class / T3-Source-6 Microsoft Swarm Diaries） |
| #18 Announcement-instead-of-action（lead 收到 APPROVE 后说"立即修正——"/"现在执行——"然后没有 tool call 跟进 = 等同未 APPROVE）| APPROVE 后**下一个 tool call 即执行**，不写"宣告"性文字；APPROVE 与 tool call 之间不允许任何解释性段落（违反 Approval Vocabulary 节；来源：T4-Source-7 + MEMORY.md announcement-instead-of-action） |
| #13 Teammate 递归派单（teammate 自己 spawn sub-teammate 形成无限嵌套，lead 失控；与官方 subagent / agent-teams 明文禁止冲突）| Teammate **绝不**调用 Agent tool；如需子任务在 progress raise「需派 sub-teammate 处理 X」，由 lead 决定下一 wave 是否派（违反 §0.5；来源：T1-Source-3 Claude Code subagent doc / T1-Source-4 agent-teams doc）|
| #19 Mid-wave lead 切换（同一 wave 内换 agent / context 重启换 lead session 而未 close 本 wave，导致 wave 状态 / decisions 丢失或不一致）| 当前 lead 必须先写 `WAVE_CLOSE.md` 收尾 + 显式 close 本 wave + 新 session 重新 instantiate 新 wave（违反 §0.6；来源：T1-Source-4 agent-teams "Lead is fixed for its lifetime"）|
| #15 Reviewer-actor collective delusion（reviewer 与 actor 同模型 + 共享所有 progress 中间 reasoning，self-preference + conformity 双重叠加 → reviewer "看起来 PASS" 实则与 actor 同视角误判，未抓出根本问题）| reviewer template 强制 isolated context：reviewer 只读最终 deliverable + 原始 TEAM_CONFIG.md success criteria，**不读** teammate 中间 progress 的 reasoning 段；reviewer prompt 显式角色化（adversarial critic / user safety officer）；高 stakes wave 考虑 cross-model judge（lead = Opus → reviewer 派 Sonnet teammate 或反之）（来源：T3-Source-8 DReaMAD + Agent-as-a-Judge / T3-Source-9 collective delusion；已落 Wave 2.A C3 Proposal-014 status-consolidation §3 Reviewer Isolated Context 原则节）|
| #16 Stuck-no-progress detection silent fail（teammate 跑 18 次 Bash 但都是同一 grep 微调 args / Read 同一文件多次 / 反复 retry 同一 endpoint 无新信息，tool calls 数 OK 但 0 真进展，当前框架看不出 silent stuck）| teammate prompt 红线加："若同一类操作（grep/Read 同一文件）连续 ≥5 次未拿到新信息，必须 raise 'STUCK' 给 lead"；reviewer 抽查 progress 时关注"重复操作但无新数据"模式（来源：T3-Source-7 Agent Patterns infinite loop typology）|
| #17 对 coding-tight task 强行开 wave（任务主体是 single-codebase coding / 非 research / 非多 source 综合，但 item ≥ 4 触发了 Workflow 0 阈值导致开 wave，反而把适合单 context + skills 的活分散切碎，coordination overhead > 收益）| Workflow 0.5 选择器加"task domain"判定支线：若 task 主体是 single-codebase coding，即使 item ≥ 4 也建议**单 context + skills**（不开 wave）；Anthropic 明说 "coding tasks involve fewer truly parallelizable tasks than research, and LLM agents are not yet great at coordinating ... in real time"（来源：T3-Source-11 HN/philschmid + T3-Source-12 skill-based single agent；已落 Wave 2.A C1 Proposal-007 Workflow 0「不适合」清单 + C2 Proposal-008 Workflow 0.5 量化规则）|
| #20 Self-report 即 ground truth（reviewer / lead 仅看 teammate progress.md 的"PASS / DONE"叙述就接受结论，不交叉验证 artifact 链 — 是 §0.4 铁则的反模式表显式条目，反复触发场景包括："跑通了" 无 git diff / "verify done" 无 stdout / "调研完成" 无 URL 引文）| 任何"PASS / DONE" claim 必须配 §0.4 三类 artifact 之一（git diff / file mtime+行号 / cmd stdout 截录 / 外部 URL+引文）；reviewer 抽查 ≥ 1/3 teammate 的 claim → artifact 链；progress.md 「结论」节缺 artifact = 视为 NOT RUN（违反 §0.4；升级版 / 来源：T3-Source-6 Microsoft Swarm Diaries lying test writer + T3-Source-9 Redis confident hallucination + Proposal-3-2）|
| #22 Plan 假设 silent 升格 / caveat-stripping（Phase 1 调查 teammate 给"reasoned 推断 + 自标【未验证假设】caveat"→ wave 内后续 phase 逐层 strip caveat → synth 写 plan 时丢 / reviewer isolated context 不查外部 doc / user APPROVE 时 caveat 已不可见 / impl 字面执行 / final reviewer grep path 不验 semantics → 升格为"plan 已 APPROVE 的事实"，无人回头核对原始 caveat 还在不在 — 与 #15/#20 正交：#15 防 reviewer-actor 共谋 / #20 防 actor self-report / #22 防 **reasoned-but-unverified 推断在 phase 链条上自动升格**）| 4 条 lead-level 对策：(1) 调查 teammate prompt 红线"任何引用外部 doc/项目/数据的推荐**必须 grep/Read 该外部源验证**，否则措辞标【未实证推断】"；(2) synth teammate prompt 红线"上游 progress 含【未验证假设】或类似 caveat 的推荐，写入 plan 时**必须保留 caveat 措辞**，不得 strip"；(3) reviewer 不破 #15 isolated context — 改派**独立 sanity-check 子任务 teammate** 实证 plan 中所有外部引用；(4) lead 在 wave-planning 阶段必须显式问"本 wave 是否引用任何外部 doc/项目？是否已派 teammate 实证 grep 验证？"（来源：stepfun_fp8_fmoe_wave2 doc-impl 2026-05-13 user 挑穿 — gfx950 vs gfx942 cross-link 硬件 axis 错配，失败链 6 步：doc_t1 标"未验证假设"→ doc_t4 strip → doc_t5 isolated → user APPROVE → impl_t3v2 字面执行 → impl_t4 grep path 不验 semantics → 用户挑穿）|
| #23 Push target 自动 default branch（lead push 前未派 recon teammate 调研 target repo 的 branch 结构 / 文件惯例 / 未来主线，直接选 default branch [通常 = main] 作为 push target；当 default branch ≠ 用户实际工作主线 [如有 chore/restructure-* 重构分支] 时 → push 到错误 target → 用户挑穿后需要重 push + 留无主历史 commit）| Push 类 wave **必须**先派 1 个轻量 recon teammate（≤10 tool calls）调研 target repo：(1) 列全部 active branch + HEAD + 风格差异（NN_topic/ vs flat-file vs 其他 convention）；(2) 找出 default vs 用户工作主线（看最近 commit 频率 + restructure / migrate 等改名关键词）；(3) 给 push target + 落点 + 文件命名推荐 + 是否需要 cleanup 历史 commit。recon 输出作为后续 push teammate 派单 prompt 的 plan 输入（来源：step35_vllm_repro Wave DOC-1 2026-05-15 — DOC1-E push 到 main 是 default branch 但用户实际工作主线 = `chore/restructure-toplevel`，挑穿后追加 DOC1-F recon + Phase 5/6 重 push）|
| #24 Push 前 review 仅看文档内容，不查文件结构 / target convention 一致性（reviewer 5 维 GPA 只评文档质量本身 [Goal/Logic/Exec/Plan/Adherence]，不评落点是否符合 target 已有 convention；落地后才发现新 doc 用旧 NN_topic/ 子目录而 target 已切 flat-file，或新 doc 路径锚点 dead-link）| 涉及 push 到外部 repo 的 wave，reviewer 必须扩 5 维为 **5+1 维**：新增第 6 维 **Plan-Adherence-To-Target-Convention**（落点 / 文件命名 / 跨文件 cross-link / 路径锚点 是否符合 target repo 既有惯例）。第 6 维必须基于 recon teammate（见 #23）输出的 §"Target convention" 节 1-1 对账。本维度独立于 §15 isolated context — reviewer 必须 grep target repo 现有内容验证（来源：step35_vllm_repro Wave DOC-1 2026-05-15 — Phase5-T3 引入第 6 维 plan-adherence 后实测 8/8 项符合 + dead-link = 0；DOC1-D 原 5 维 GPA 4.4/5 PASS 但漏查 target convention 是用户挑穿的根因）|
| #25 Staged 蓝图文件混入 commit（lead 用"蓝图模式"避免跨 teammate 串行 git index 冲突 — 让 stage teammate 在 staged/ 写 `*_patch.md` 描述要 apply 到现有文件的内容；push teammate 未明示"蓝图非 commit 文件"红线 → 直接 `cp staged/X_patch.md target/` 导致蓝图文件本身污染 repo）| Push teammate 派单 prompt **必须**显式列"蓝图文件清单 + apply 目标"红线节，明示 `*_patch.md` 是 apply 蓝图本身，绝对不可作为独立文件 commit；只能 Read 蓝图 → Edit 现有 target 文件 → 蓝图文件不进 repo。Push 后 git status / diff --stat 自检步必须确认 staged/ 路径 0 文件出现在 commit 中（来源：step35_vllm_repro Wave DOC-1 2026-05-15 — Phase5-T2 写 README_patch.md / CODE_CHANGES_patch.md 蓝图，Phase6-Push 显式 P2-2 红线后正确 apply 到现有 README.md / CODE_CHANGES.md 而蓝图本身不进 repo）|

---

## 启动检查清单

- [ ] TEAM_CONFIG.md 已生成（PROJECT / WORK_DIR / DOC_DIR / LOG_DIR）
- [ ] CODE_ROOTS 路径列表完整
- [ ] GOAL 一句话，可量化
- [ ] CONSTRAINTS 已从 CLAUDE.md 和代码注释提取
- [ ] KNOWN_FACTS 已从 recall/MEMORY 提取（附来源）
- [ ] BASELINE 命令 + 预期指标（具体数值）
- [ ] ENVIRONMENT 已填写（子类特有的运行前置、资源设置、缓存清理）
- [ ] 初始 TODO list 已写（Phase 0 → 1 → 2 → 3，含依赖关系）
- [ ] DOC_DIR 目录已创建

---

## Changelog（父类更新历史）

| 日期 | 来源任务 | 变更内容 |
|------|---------|---------|
| 2026-04-23 | step35-flash（v2） | 初始版本，基于 MoE/SwigluStep/TP/FP8 任务经验 |
| 2026-04-25 | step35-flash（v3） | 应用继承模型，去除任务特有内容，通用化 |
| 2026-04-25 | fp8-tp2-inference（PC-1） | 反模式：待验证假说不应放入 KNOWN_FACTS |
| 2026-04-30 | 用户原则强化 | 新增 §0 铁则：Lead 不执行具体工作 + agent team 必须并行；反模式表新增 3 条对应项；Lead 行为规则 / Phase 1 加交叉引用 |
| 2026-05-09 | agent-team-skill-specialization | 拆分父类/特化：新增 templates/{dev-debug,doc-edit,status-consolidation,ci-investigation}.md 4 个特化模板 + Workflow 0.5 选择器；从 SKILL.md 抽走 dev-debug 特化内容（阶段结构 / 验证顺序 / dev-debug 反模式 7 条），改 stub 引用 templates/<name>.md；Item 类型表扩充含模板专属类型；继承模型图升级为三层 |
| 2026-05-11 | pr6914_bwd_repro | templates/dev-debug.md 新增 §validate-AND-falsify pair 子模式（competing-hypotheses 2-teammate 退化版）：单怀疑点场景同 message 派 validator + falsifier 显式 role split，互锁结论才接受根因。实证：T11(revert)/T12(static audit) 排除 PR mask；T13(dump)/T14(device printf) 锁定 ref runner shape OOB 根因 |
| 2026-05-13 | stepfun_fp8_fmoe_wave2 doc-impl | 反模式表新增 #22 Plan 假设 silent 升格 / caveat-stripping — 与 #15/#20 正交的第三类失败模式：reasoned-but-unverified 推断在 wave 内 phase 链条上自动升格为事实。含 4 条 lead-level 对策（调查 prompt 加 grep 红线 / synth 必须保留 caveat / reviewer 不破 #15 改派独立 sanity-check 子任务 / lead 显式问外部引用是否实证）。实证：doc-impl 在 16/RESULTS.md (gfx950) §四-B 加反向 cross-link 指向 wave2 (gfx942) — 跨硬件代际 cross-link，user 挑穿后修正措辞 + 加硬件 axis 澄清段 |
| 2026-05-15 | step35_vllm_repro Wave DOC-1 | 反模式表新增 3 条 push-target 类反模式：#23 Push target 自动 default branch（lead 未派 recon 调研 branch 结构 → 错 push 到 main 而非 chore/restructure-toplevel 重构主线）；#24 Push 前 review 仅看文档内容不查 target convention（reviewer 5 维 GPA 漏第 6 维 plan-adherence-to-target-convention，落地后才发现 NN_topic/ vs flat-file convention 不一致）；#25 Staged 蓝图文件混入 commit（lead 用蓝图模式避 git index 冲突，但 push teammate 未明示"蓝图非 commit"红线导致 README_patch.md / CODE_CHANGES_patch.md 直接 cp 进 repo）。三条均含正面对策：Push 类 wave 必前置 recon teammate / reviewer 扩 5+1 维 / push prompt 显式蓝图清单红线 |
| 2026-05-22 | tmux_skill_integration_wave | 新增 §9 tmux Pane Visualization 节 — 手工 tmux 多 pane 方案文档化（split-window 布局 / send-keys 派单 / capture-pane 监控 / file-based prompt 协议）+ 与官方 `teammateMode: "tmux"` 对比表 + 5 条反模式 + 何时用 / 不用决策表；4 个 templates（dev-debug / doc-edit / status-consolidation / ci-investigation）§1 Phase Plan 末尾各加一行"实时观察（可选）"cross-ref 指向父类 §9 |
| 2026-05-22 | tmux_skill_wave2 | §9 扩充 setup 闭环（4 个新小节）：§9.0 Prerequisites & Bootstrap（tmux ≥ 3.0 / claude CLI / container.env / IS_SANDBOX 语义 + session 命名约定 + wave 目录骨架 + bootstrap 脚本 + readiness 检测）；§9.7 Verification Roundtrip Smoke Test（5 步可复制脚本 + 3 条 PASS 标准 + 实测 25s 基线 + pane index 漂移 caveat）；§9.8 Troubleshooting（9 行症状→诊断→修复表 + Teardown）。实证基础：本 wave 3 个 tmux pane teammate 实跑 setup → roundtrip → 起草 3 节 draft，全链路真 tmux send-keys 派单 + capture-pane 验证 |
