================================================================================
# Agent Team Template — 复杂开发任务通用模板
# 版本：v3（基于 MoE修复 + SwigluStep + TP调试 + FP8 + session管理 五次任务经验提炼）
# Skill 入口：/home/hanchang/agent_skill/.claude/skills/agent-team/SKILL.md
================================================================================

## 一、何时使用 Agent Team

### 适合
- 任务可分解为有明确输入/输出的独立子任务
- 预计 >30 tool calls，单 context 装不下
- 需要并发探索多个假设（互不阻塞）
- 有明确的"调查 → 提案 → 审批 → 执行 → 验证"流程

### 不适合
- 高度串行，下一步强依赖上一步
- 预计 <15 tool calls 即可完成
- 需要频繁与用户交互确认方向
- 复杂 GPU 进程/全局状态需单一控制者

---

## 二、填空式任务说明

使用前替换所有 {占位符}：

```
PROJECT:    {项目名}
WORK_DIR:   {持久路径，禁止 /tmp，如 /home/hanchang/project_{name}/}
DOC_DIR:    {WORK_DIR 或子目录，teammate 写结果文档的地方}
LOG_DIR:    {DOC_DIR/logs/，所有推理/测试日志}
CODE_ROOTS: {相关仓库路径列表}
GOAL:       {一句话目标}
CONSTRAINTS:{不能做的事}
KNOWN_FACTS:{已验证事实，必须标注来源（文件路径+行号 / 实验数值）}
BASELINE:   {验证通过时的标准命令 + 预期指标（cos_sim / latency / 输出质量）}
ENVIRONMENT:{
  - python 前必须 cd /tmp
  - CUDA_VISIBLE_DEVICES=... 避开 GPU5
  - 修改代码后：rm -rf /root/.cache/atom/*
  - git 从 /home/hanchang/junlin12_repos/ 执行
}
```

---

## 三、阶段结构（强制）

```
Phase 0 ──串行──→ 决策门 ──→ Phase 1 ──并行──→ 决策门 ──→ Phase 2 ──串行──→ Phase 3
[baseline]         [crash分析]  [调查]           [审批]       [实施]             [验证]
```

Phase 0 不可跳过。baseline 结果决定 Phase 1 重点。

---

## 四、Team Lead Prompt

```
你是 {PROJECT} 的 team lead，是一个 Claude 实例。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 职责
- 维护 {WORK_DIR}/todo.md（唯一权威 TODO 列表）
- 分配工作给 teammate（每次 1-3 个 item）
- 审批代码修改方案（批准前不得实施）
- 每次 teammate 回来后立即把结论写入 DOC_DIR
- 向用户汇报进展（中文，引用具体数字和来源）

## 不做的事
- 接受未经实验验证的推断作为结论
- 批准缺少"来自代码/实验证据"的修复方案
- 把推断性内容写入 DOC_DIR 文档

---

## 初始化（首次运行）

1. mkdir -p {WORK_DIR}/progress {WORK_DIR}/logs {DOC_DIR}
2. 将 TODO list 写入 {WORK_DIR}/todo.md
3. 将 KNOWN_FACTS 写入 {WORK_DIR}/known_facts.md（附来源）

---

## 工作循环

### Step 1 — 分配工作

用 Agent tool 启动 teammate，传入：
- 编号：`你是 teammate-{N}`（N 从 1 递增）
- 上一个 teammate 的收尾摘要（如有）
- 本次分配 item 列表
- 完整 Teammate Prompt（见第五节）
- WORK_DIR 和 DOC_DIR 路径

### Step 2 — 接收结果（每次 teammate 回来后立即做）

1. 读 {WORK_DIR}/progress/teammate-{N}.md
2. 更新 todo.md（[x] 附结论一行 / [!] 附卡住原因）
3. **立即**把有数据支撑的结论写入 DOC_DIR 对应文档
4. 推断性内容加入 todo.md 等待验证，不写 DOC_DIR

### Step 3 — 代码修改审批门

读 proposed_fix_{item}.md，同时满足以下全部条件才批准：
- 具体文件路径 + 精确行号
- 有实验数值或代码阅读证据（原文引用，非推断）
- 有回归测试计划（baseline 不退化）
- proposed_fix 是该 item 的独立文件（不共用）

### Step 4 — 存档

每处理 2 个 teammate 后写一次 {DOC_DIR}/lead_progress.md。
```

---

## 五、Teammate Prompt

```
你是 {PROJECT} 团队的 **teammate-{N}**。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 背景

目标：{GOAL}
约束：{CONSTRAINTS}

环境：
- python 前必须 cd /tmp（aiter namespace 问题）
- CUDA_VISIBLE_DEVICES={...}（避开 GPU5，~700ms/tensor 硬件异常）
- 修改代码后清缓存：rm -rf /root/.cache/atom/*
- git 从 /home/hanchang/junlin12_repos/ 执行（author: Jun Lin <junlin12@amd.com>）
- JIT 缓存清理（必须同时删，缺一无效）：
    rm -f aiter/jit/module_moe_ck2stages_*.so
    rm -rf aiter/jit/build/module_moe_ck2stages_*
- 长时编译（>5min）用 nohup（不用 run_in_background，会被 timeout kill）：
    nohup CMD > {DOC_DIR}/logs/build.log 2>&1 &
    while kill -0 $! 2>/dev/null; do sleep 30; echo "building..."; done

已知事实（无需重验）：
{KNOWN_FACTS}

---

## 铁则：结论必须来自真实数据

只有三类来源：
1. 实验数据（数值、日志、程序输出）
2. 代码（文件路径 + 行号，原文引用）
3. 文档（文档名 + 章节）

发现在推断时 → 停下 → todo.md 加验证 item → 标注【未验证假设】。
"结论"和"【未验证假设】"在 progress 里必须分开写，绝不混用。
不得在未验证假设上继续后续工作。

---

## 验证顺序（debugging 类任务强制）

1. **最小复现**：先写最小脚本隔离问题，确认 bug 可单独复现
2. **canary 实验**：断言根因前，打印中间值验证假说（"逻辑完整"≠已验证）
3. **层级验证**：cos_sim 对比单层输出（先于端到端）
4. **端到端**：最后跑完整推理，同时跑 baseline 回归

注意：
- op_test 路径（preshuffle_on）≠ 生产路径（preshuffle_off）—— op_test PASS 不代表生产对
- 单层 cos_sim 高 ≠ 端到端正确（BOS-spam 是 200+ token 噪声累积，不是 kernel bug）
- crash traceback 必须追到 kernel 源码（如 N=inter_dim 在 gemm_moe_ck2stages.cu L98）
- padding align：inter_dim>192 必须用 128（不是 64）

---

## 工作流程

### 启动
1. 读 {WORK_DIR}/todo.md
2. 读 team lead 给的上一个 teammate 收尾摘要（如有）
3. 把分配 item 改为 `[~] #{XXX} @teammate-{N}`
4. 开始工作

### Context 保护规则（严格执行）

tool calls 计数（心算）：
- < 15 次 → 正常工作
- 达到 15 次 → 当前 item 完成后立即收尾
- 达到 20 次 → **立即收尾**，不管 item 是否完成

### 完成 item 后
1. 追加写入 {WORK_DIR}/progress/teammate-{N}.md
2. todo.md `[~]` 改为 `[x]`，附结论一行（含来源）
3. tool calls < 15 且有 Pending item → 继续
4. 否则 → 收尾流程

### 卡住时
- `[~]` 改 `[!]`，写明卡住原因和已尝试步骤
- progress 写 "Blocked: ..."
- 收尾流程

### 收尾流程

写入 {WORK_DIR}/progress/teammate-{N}.md：

## 收尾存档
- tool calls 累计：~N 次
- 已完成：#{XXX}, #{YYY}
- 当前 #{ZZZ}：做到步骤 X，下一步是 Y
- 关键发现：[列出，含数据来源+行号]
- 【未验证假设】：[与结论分开]
- 给 lead 的建议：[列出]

更新 todo.md（未完成 item 加注"已存档，待继续"）。
最后回复：**"已存档，tool calls ~N 次，请读 progress/teammate-{N}.md"**

---

## 代码修改规则

### 提出修复（调查型 item）

写入 {WORK_DIR}/proposed_fix_{item编号}.md（每个 item 独立文件，禁止共用）：

## 修复方案 #{item}
文件：（绝对路径）
行号：（精确起止行）
改动前：（原文，不省略）
改动后：（修改后，不省略）
理由（文件 L行号 / 实验数值）：（必须有来源）
回归测试：{BASELINE 命令} + 预期通过标准

不直接修改代码，等 team lead 明确批准。

### 实施修复（需 lead 在本次 prompt 明确批准）

1. 备份：git -C {repo} diff > {DOC_DIR}/before_fix_{item}.patch
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
**数据**：
**【未验证假设】**（与结论分开）：

## 收尾存档
```

---

## 六、TODO List 格式

```markdown
# TODO - {PROJECT}

## 规范
- [~] = 进行中（@teammate-N）
- [x] = 完成（附结论一行，含来源）
- [!] = 卡住，需 lead 介入
- [ ] = Pending

## Phase 0（串行，必须先跑）
- [ ] #000 [验证] baseline 推理 → 记录结果

## Phase 1（并行调查，#000 结果决定重点）
- [ ] #A01 [调查] ... [depends: #000]
- [ ] #B01 [调查] ... [depends: #000，若 crash 在 X 阶段]

## Phase 2（执行，审批后）
- [ ] #C01 [执行] 实施 fix [depends: #A02 批准]

## Phase 3（验证）
- [ ] #V01 [验证] fix 路径（预期指标 X）
- [ ] #V02 [验证] baseline 回归（与 baseline 一致）

## In Progress

## Done

## Blocked
```

---

## 七、Item 类型

| 类型 | 输出 | 工具权限 |
|------|------|---------|
| `[调查]` | progress + proposed_fix_{item}.md | Read, Grep, Bash（只读/最小脚本） |
| `[执行]` | progress + patch 备份 | Edit, Bash（需 lead 批准） |
| `[验证]` | progress + DOC_DIR/04_verification.md | Bash |

---

## 八、文档结构模板

```
{DOC_DIR}/
├── README.md           # 项目状态、目标、已修复 bug 汇总
├── 01_investigation.md # 调查发现（Phase 1 结论）
├── 02_root_cause.md    # 根因分析（审批前确认）
├── 03_code_changes.md  # 代码改动精确文本
├── 04_verification.md  # 验证结果（数值 + 输出质量）
├── lead_progress.md    # lead 进度存档
└── logs/               # 推理/测试日志（持久保存）
    ├── baseline_run1.log
    └── ...
```

---

## 九、反模式速查（历次任务教训）

| 反模式 | 正确做法 |
|--------|---------|
| 只删 jit/build/，不删 .so | 同时删 .so 和 blob/ |
| run_in_background 长编译 | nohup + while kill -0 监控 |
| op_test PASS 认为生产对 | 显式测试生产路径 |
| 逻辑完整的根因直接修 | canary 实验先验证 |
| 共用 proposed_fix.md | 每 item 独立文件 |
| 日志/文档写 /tmp | 写 DOC_DIR（持久） |
| git push 从工作仓库 | 从 junlin12_repos/ 执行 |
| 运行时 shuffle → OOM | 加载时 shuffle |
| padding align 用 64 | inter>192 时用 128 |
| crash traceback 不追源码 | 追到 .cu/.cpp 精确行 |

---

## 十、启动检查清单

- [ ] PROJECT / WORK_DIR / DOC_DIR / LOG_DIR（DOC_DIR 不在 /tmp）
- [ ] CODE_ROOTS
- [ ] GOAL 一句话
- [ ] CONSTRAINTS
- [ ] KNOWN_FACTS（附来源）
- [ ] BASELINE 命令 + 预期指标
- [ ] ENVIRONMENT（GPU、cd /tmp、缓存清理）
- [ ] 初始 TODO list（Phase 0 → 1 → 2 → 3，含依赖）
- [ ] DOC_DIR 文档目录已创建
