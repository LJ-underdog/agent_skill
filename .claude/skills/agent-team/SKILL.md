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
