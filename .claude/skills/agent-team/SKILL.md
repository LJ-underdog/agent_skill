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

## 继承模型

```
SKILL.md (父类 — 通用 agent team 框架)
  └── TEAM_INSTANCE_TEMPLATE.md (子类骨架)
        └── project_{name}/TEAM_CONFIG.md (子类实例 — 任务特化)
                ↓ [任务结束后 Promote]
        SKILL.md (父类更新)
```

子类只填写任务特有部分（ENVIRONMENT、BASELINE、KNOWN_FACTS 等）；父类的 Lead 行为规则、Teammate prompt 结构、审批门、todo 格式自动适用，不在子类重复。

---

## 与 project-summary 的集成

agent-team（执行）通常与 project-summary（记录）同时使用。
详见 [SKILLS_INDEX.md](../../SKILLS_INDEX.md)，核心要点：

- **先 instantiate project-summary**，生成 `TASK_TEMPLATE.md`（参数 schema、指标、已知事实）
- **再 instantiate agent-team**，生成 `TEAM_CONFIG.md`，从 TASK_TEMPLATE.md 引用共享字段
- teammate progress 文件即为 project-summary 的 experiment_log，**无需另外维护**
- 任务结束后，两个 skill 各自执行 Promote workflow

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

**判断后如不适合，直接单 Claude 完成，不要强行用 Agent Team。**

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

## 阶段结构（父类强制）

```
Phase 0 ─串行─→ 决策门 ─→ Phase 1 ─并行─→ 决策门 ─→ Phase 2 ─串行─→ Phase 3
[baseline]       [分析]     [调查]           [审批]     [实施]           [验证]
```

**Phase 0（必须先跑，不可跳过）：**
- 串行完成：运行当前系统 → 记录 crash traceback 或通过结果
- 目的：确认起始状态，决定 Phase 1 重点
- 输出：`DOC_DIR/baseline_result.md`

**Phase 1（并行调查，最多 3 个 teammate 同时）：**
- 每个 teammate 1-3 个 item
- 输出：`WORK_DIR/progress/teammate-{N}.md` + `WORK_DIR/proposed_fix_{item}.md`

**Phase 2（审批后串行执行）：**
- 每个修复 lead 审批通过后才能实施
- 实施前备份 diff

**Phase 3（验证，可并行）：**
- 必须同时跑：fix 路径验证 + baseline 回归

---

## Lead 行为规则（父类）

### 启动 teammate 时传入（缺一不可）
1. 编号：`你是 teammate-{N}`
2. 上一个 teammate 的收尾存档摘要（如有）
3. 本次分配的 item 列表（含依赖关系）
4. 完整的 Teammate Prompt（从 TEAM_CONFIG.md 生成）
5. WORK_DIR 和 DOC_DIR 路径

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

缺任何一条 → 不批准，加调查 item 补充。

### 存档规律
每处理 2 个 teammate 后写一次 `DOC_DIR/lead_progress.md`。

---

## Teammate Prompt 模板（父类固定部分）

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

## 验证顺序（debugging 类任务）

1. **最小复现**：先写最小脚本隔离问题，确认 bug 可单独复现
2. **中间值验证**：断言根因前，直接打印/检查中间状态（canary 或 assert）
3. **组件级验证**：验证单个组件正确性，不只看端到端结果
4. **端到端验证**：最后跑完整流程，同时跑基线回归

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

# Teammate {N} Progress

## 接手状态
[lead 摘要 / 上一个 teammate 收尾存档]

## 已完成 Items

### [#{XXX}] 标题
**类型**：调查型 / 执行型 / 验证型
**结论**（来自实验/代码/文档，附来源）：
**数据**：{指标值} / 文件 Y L行号 / 实验输出
**【未验证假设】**（如有，与结论分开）：

## 收尾存档

---

## 本次分配

**teammate-{N} 负责**：#{XXX}, #{YYY}
上一个 teammate 收尾摘要：{lead 填入}
具体 item 说明：{lead 填入}
```

---

## TODO List 格式

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

| 类型 | 说明 | 输出 | 允许的工具 |
|------|------|------|-----------|
| `[调查]` | 读代码/最小复现/中间值检测 | progress + proposed_fix_{item}.md | Read, Grep, Bash（只读或最小脚本） |
| `[执行]` | 修改代码/写文件 | progress + patch 备份 | Edit, Bash（需 lead 批准） |
| `[验证]` | 完整测试矩阵 | progress + DOC_DIR/04_verification.md | Bash |

---

## 文档管理规则

- **所有输出写入 DOC_DIR（非临时目录）**：临时目录重启后消失
- **日志**：保存到 `LOG_DIR/`，重要日志复制到 DOC_DIR
- **proposed_fix 文件**：写到 WORK_DIR（若 WORK_DIR 是临时目录，同时写到 DOC_DIR）
- **lead_progress.md**：写到 DOC_DIR
- **teammate progress**：WORK_DIR/progress/（收尾时 lead 摘要写入 DOC_DIR）

---

## 反模式表（通用，父类维护）

| 反模式 | 正确做法 |
|--------|---------|
| 编译/构建缓存未完全清理就测试 | 清理所有缓存文件（构建产物 + 生成文件缺一不可） |
| 用后台任务跑长时编译 | nohup + 轮询监控（后台任务可能被 timeout kill） |
| 单元测试 PASS 就认为生产路径正确 | 显式用生产路径配置验证 |
| "逻辑完整"的根因直接提修复 | 最小复现/中间值检测先验证根因 |
| 并行 teammate 共用同一个 proposed_fix.md | 每个 item 独立文件（防并行写冲突） |
| crash → 直接改代码 | Phase 0 先精确定位 traceback（阶段 + 完整 message） |
| 日志/结果写临时目录 | 写持久路径（DOC_DIR） |
| 从错误的仓库 push 导致 author 错误 | 明确 push 仓库路径和 author 配置（子类 ENVIRONMENT 指定） |
| 未覆盖 baseline 回归就认为修复完成 | Phase 3 始终同时跑 fix 路径 + baseline 回归 |
| 多假设串行调查 | Phase 1 并行，互不阻塞 |

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
