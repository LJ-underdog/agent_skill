---
name: agent-team
description: |
  Launch a structured multi-agent team for complex debugging and development tasks.
  Use when: task decomposes into independent subtasks, >30 tool calls expected,
  multiple hypotheses need parallel exploration, or clear investigate→propose→approve→implement→verify flow.
  Trigger phrases: "start agent team", "agent team 来做", "launch agent team for", "用 agent team".
---

# Agent Team — 多智能体调试 / 开发团队

任务：`$ARGUMENTS`

---

## 一、决策：是否使用 Agent Team？

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
- 复杂 GPU 进程/全局状态需要单一控制者

**判断后如不适合，直接单 Claude 完成，不要强行用 Agent Team。**

---

## 二、Setup — 填写任务配置

在启动前，向用户确认或自行从上下文获取：

```
PROJECT:    {简短名称，如 fp8-tp2-debug}
WORK_DIR:   {持久路径，禁止 /tmp，如 /home/hanchang/project_{name}/}
DOC_DIR:    {同 WORK_DIR 或子目录，teammate 写结果文档的地方}
LOG_DIR:    {WORK_DIR/logs/，所有推理/测试日志存这里}
CODE_ROOTS: {相关仓库路径列表}
GOAL:       {一句话目标}
CONSTRAINTS:{不能做的事，如"不能修改 @support_torch_compile 装饰的文件"}
KNOWN_FACTS:{已验证事实，附来源（文件路径+行号 / 实验数值）}
ENVIRONMENT:{
  - python 前必须 cd /tmp（aiter namespace 问题）
  - CUDA_VISIBLE_DEVICES=... 避开 GPU5
  - 修改代码后：rm -rf /root/.cache/atom/*
  - git 操作从 /home/hanchang/junlin12_repos/ 执行
}
BASELINE:   {验证无 bug 时的标准推理命令 + 预期输出（cos_sim / latency / prompt 质量）}
```

---

## 三、阶段结构（强制）

```
Phase 0 ── 串行 ──→ 决策门 ──→ Phase 1 ── 并行 ──→ 决策门 ──→ Phase 2 ── 串行 ──→ Phase 3
[baseline]           [crash 分析]  [调查]             [审批]       [实施]               [验证]
```

**Phase 0（必须先跑，不可跳过）：**
- T-1 串行完成：baseline 推理 → 记录 crash traceback 或通过结果
- 目的：确认当前状态，决定 Phase 1 重点
- 输出：`DOC_DIR/baseline_result.md`（crash 阶段 + 完整 traceback + 关键错误）

**Phase 1（并行调查，最多 3 个 teammate 同时）：**
- 每个 teammate 1-3 个 item
- 输出：`WORK_DIR/progress/teammate-{N}.md` + `WORK_DIR/proposed_fix_{item}.md`

**Phase 2（审批后串行执行）：**
- 每个修复 team lead 审批通过后才能实施
- 实施前备份：`git -C {repo} diff > DOC_DIR/before_fix_{item}.patch`

**Phase 3（验证，可并行）：**
- 回归矩阵：列出所有 (输入, 预期输出) 对
- **必须同时跑**：fix 路径验证 + baseline 回归（bf16 tp=2 不退化）

---

## 四、主 Claude（Lead）行为规则

你作为 Lead，通过 Agent tool 启动 teammate。

### 启动 teammate 时传入的信息（缺一不可）
1. 编号：`你是 teammate-{N}`
2. 上一个 teammate 的收尾存档摘要（如有）
3. 本次分配的 item 列表（含依赖关系）
4. 完整的 Teammate Prompt（见第五节）
5. `WORK_DIR` 和 `DOC_DIR` 路径

### 接收结果后（每次 teammate 回来后立即做）
1. 读 `WORK_DIR/progress/teammate-{N}.md`
2. 更新 `WORK_DIR/todo.md`（[x] / [!]，附结论一行）
3. **立即**把有数据支撑的结论写入 `DOC_DIR/` 对应文档
4. 推断性内容不写入文档，加入 todo.md 等待验证

### 代码修改审批门（每个 fix 必须同时满足）
- [ ] 具体文件路径 + 精确行号
- [ ] 有实验数值或代码阅读证据（非推断）
- [ ] 有回归测试计划（说明如何验证 baseline 不退化）
- [ ] proposed_fix 写在独立文件 `proposed_fix_{item}.md`（不共用）

缺任何一条 → 不批准，加调查 item 补充。

### 存档规律
每处理 2 个 teammate 后写一次 `DOC_DIR/lead_progress.md`（状态 + findings + 下一步）。

---

## 五、Teammate Prompt 模板

启动每个 teammate 时使用以下 prompt（替换 {} 占位符）：

```
你是 {PROJECT} 团队的 **teammate-{N}**。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 背景

目标：{GOAL}

约束：{CONSTRAINTS}

环境：
- python 前必须 cd /tmp
- CUDA_VISIBLE_DEVICES={...}（避开 GPU5）
- 修改代码后清缓存：rm -rf /root/.cache/atom/*
- git 操作从 /home/hanchang/junlin12_repos/ 执行（author: Jun Lin <junlin12@amd.com>）
- JIT 缓存清理：rm -f aiter/jit/module_moe_ck2stages_*.so
                 rm -rf aiter/jit/build/module_moe_ck2stages_*
  （必须同时删 .so 和 blob/ 目录，只删其一无效）
- 长时编译（>5min）用：nohup CMD > /tmp/build.log 2>&1 &
  然后 while kill -0 $! 2>/dev/null; do sleep 30; echo "..."; done
  不用 run_in_background=True（会被 timeout kill）

已知事实（无需重验，来源已标注）：
{KNOWN_FACTS}

---

## 铁则：结论必须来自真实数据

只有三类来源可作为结论：
1. 实际运行的实验数据（数值、日志、程序输出）
2. 直接读取的代码（文件路径 + 行号，原文引用）
3. 查阅的文档（文档名 + 章节）

发现自己在推断时 → 立即停下 → todo.md 加验证 item → 标注【未验证假设】。
progress 文件里"结论"和"【未验证假设】"必须分开写，绝不混用。

**不得在未验证假设上继续后续工作。**

---

## 验证顺序（debugging 类任务强制执行）

1. **最小复现**：先写最小脚本隔离问题，确认 bug 可复现
2. **canary 实验**：在断言根因前，用 canary（直接打印中间值）验证假说
3. **层级验证**：cos_sim 对比单层输出（不只看端到端结果）
4. **端到端**：最后跑完整推理，同时跑回归 baseline

注意：
- op_test 路径（preshuffle_on）≠ 生产路径（preshuffle_off）
- op_test PASS ≠ 生产路径正确，必须测生产路径
- 单层 cos_sim 高 ≠ 端到端正确（如 BOS-spam 是噪声累积，不是 kernel bug）

---

## 工作流程

### 启动
1. 读 {WORK_DIR}/todo.md
2. 读 team lead 给的上一个 teammate 收尾摘要（如有）
3. 把本次分配 item 改为 `[~] #{XXX} @teammate-{N}`
4. 开始工作

### Context 保护规则（严格执行）

累计 tool calls 计数（心算）：
- < 15 次 → 正常工作
- 达到 15 次 → 当前 item 完成后立即收尾
- 达到 20 次 → **立即收尾**，无论 item 是否完成

宁可多存档，不要 context 溢出丢失进度。

### 完成 item 后
1. 追加写入 {WORK_DIR}/progress/teammate-{N}.md
2. 在 todo.md 把 `[~]` 改为 `[x]`，附一行结论（必须含来源）
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
- 当前 #{ZZZ} 进度：已做到步骤 X，下一步是 Y
- 关键发现：[列出，含数据来源和文件行号]
- 【未验证假设】：[与结论分开列出]
- 给 team lead 的建议：[列出]

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
回归测试计划：baseline 命令 + 预期指标

**不直接修改代码，等 team lead 明确批准。**

### 实施修复（需 team lead 在本次 prompt 明确批准）

1. 备份：`git -C {repo} diff > {DOC_DIR}/before_fix_{item}.patch`
2. 用 Edit tool 实施（先 Read 再 Edit）
3. 记录修改行号到 progress
4. 不自行运行完整测试（由专门的验证 item 做）

---

## Progress 文件格式

{WORK_DIR}/progress/teammate-{N}.md：

# Teammate {N} Progress

## 接手状态
[team lead 摘要 / 上一个 teammate 收尾存档]

## 已完成 Items

### [#{XXX}] 标题
**类型**：调查型 / 执行型 / 验证型
**结论**（来自实验/代码/文档，附来源）：
**数据**：cos_sim=X / 文件 Y L行号 / 实验输出...
**【未验证假设】**（如有，与结论分开）：

## 收尾存档
（见上方收尾流程格式）

---

## 本次分配

**teammate-{N} 负责**：#{XXX}, #{YYY}
上一个 teammate 收尾摘要：{team lead 填入}
具体 item 说明：{team lead 填入}
```

---

## 六、TODO List 格式

`{WORK_DIR}/todo.md`：

```markdown
# TODO - {PROJECT}

## 规范
- [~] = 进行中（@teammate-N 认领）
- [x] = 完成（附结论一行）
- [!] = 卡住，需 lead 介入
- [ ] = Pending

## Phase 0（串行，必须先跑）
- [ ] #000 [验证] baseline 推理 → 记录 crash / 通过结果

## Phase 1（并行调查，#000 结果决定重点）
- [ ] #A01 [调查] ... [depends: #000]
- [ ] #A02 [调查] ... [depends: #000]
- [ ] #B01 [调查] ... [depends: #000，若 crash 在 X 阶段]

## Phase 2（执行，审批后）
- [ ] #C01 [执行] 实施 fix A（depends: #A02 批准）
- [ ] #C02 [执行] 实施 fix B（depends: #A03 批准）

## Phase 3（验证）
- [ ] #V01 [验证] fix 路径端到端（4 prompts，预期指标 X）
- [ ] #V02 [验证] baseline 回归（bf16 tp=2，预期与 baseline 一致）

## In Progress

## Done

## Blocked
```

---

## 七、Item 类型说明

| 类型 | 说明 | 输出 | 允许的工具 |
|------|------|------|-----------|
| `[调查]` | 读代码/跑最小复现/canary 实验 | progress + proposed_fix_{item}.md | Read, Grep, Bash（只读或最小 python 脚本） |
| `[执行]` | 修改代码/写文件 | progress + patch 备份 | Edit, Bash（需 lead 批准） |
| `[验证]` | 完整测试矩阵 | progress + DOC_DIR/{04_verification.md} | Bash |

---

## 八、文档管理规则（防止数据丢失）

- **所有输出写入 DOC_DIR（非 /tmp）**：/tmp 重启后消失
- **推理/测试日志**：保存到 `LOG_DIR/`，重要日志复制到 DOC_DIR
- **proposed_fix 文件**：写到 WORK_DIR（如果 WORK_DIR 在 /tmp，同时写一份到 DOC_DIR）
- **lead_progress.md**：写到 DOC_DIR（不只在 /tmp）
- **teammate progress**：WORK_DIR/progress/（可在 /tmp，收尾时 lead 摘要写入 DOC_DIR）

---

## 九、已知反模式（历次任务教训）

| 反模式 | 正确做法 | 来源任务 |
|--------|---------|---------|
| 只删 jit/build/，不删 .so | 同时删 .so 和 blob/（二者缺一不可） | SwigluStep |
| 用 run_in_background 跑长编译 | nohup + while kill -0 监控 | FP8 |
| op_test PASS 就认为生产路径对 | 显式测试生产路径（preshuffle_off, tp=2 等） | MoE + SwigluStep |
| "逻辑上完整"的根因直接提修复 | canary/最小复现先验证根因 | MoE（Bug2/3/4 被证伪） |
| 共用 proposed_fix.md | 每个 item 独立文件（防并行冲突） | FP8 |
| 端到端 crash → 直接改代码 | Phase 0 先记录 traceback 精确位置 | FP8 |
| 日志/结果写 /tmp | 写 DOC_DIR（持久路径） | 本次 session |
| git push 从工作仓库 | 从 junlin12_repos/ 执行 | 本次 session |
| 运行时 shuffle | 加载时 shuffle（process_weights_after_loading） | MoE |
| align 用 64 | inter_dim>192 时用 128（align=64 only for inter≤192） | TP调试 |
| 多个 teammate 并行写同一文件 | 并行 teammate 分配互不重叠的文件/区域 | 通用 |
| 假设 crash 根因不追溯源码 | 追到 kernel 源码确认（如 N=inter_dim 在 .cu L98） | TP调试 |

---

## 十、启动检查清单

在开始前确认：

- [ ] PROJECT / WORK_DIR / DOC_DIR / LOG_DIR 已填写（DOC_DIR 不在 /tmp）
- [ ] CODE_ROOTS 路径列表
- [ ] GOAL 一句话
- [ ] CONSTRAINTS（不能改的文件/装饰器）
- [ ] KNOWN_FACTS（已验证事实 + 来源）
- [ ] BASELINE 命令 + 预期指标（cos_sim / 输出质量 / latency）
- [ ] ENVIRONMENT（GPU 编号、cd /tmp、缓存清理命令）
- [ ] 初始 TODO list（Phase 0 → 1 → 2 → 3，含依赖关系）
- [ ] 项目文档目录已创建（DOC_DIR/01_investigation.md 等）
