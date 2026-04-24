---
name: project-summary
description: |
  Write a rigorous, verifiable project summary for a completed engineering task.
  Covers the full lifecycle: pre-task setup → during-task recording → post-task writing → self-review.
  Every conclusion must be traceable to an experiment result or code reading.
  Trigger phrases: "write project summary", "create project doc", "document this task",
  "总结这个任务", "写 project summary", "做任务总结".
---

# Project Summary — 工程任务文档化全流程

任务：`$ARGUMENTS`

---

## 概述

高质量的 project summary 取决于任务进行中的记录质量。这个 skill 分三个阶段：

```
阶段一：任务开始前        阶段二：任务进行中        阶段三：任务结束后
[目录结构 + Baseline]    [实验记录 + 假说管理]     [写作 + 自检]
```

配套工具：[PRE_TASK_GUIDE.md](./PRE_TASK_GUIDE.md)（任务中随时查阅的记录模板）

---

## 阶段一：任务开始前

### 1.1 创建项目目录结构

```bash
mkdir -p /home/hanchang/project_{name}/logs
touch /home/hanchang/project_{name}/{experiment_log,hypothesis_log,commit_log}.md
```

标准文件结构：

```
project_{name}/
├── README.md              # 项目状态、目标、最终结果（持续更新）
├── 01_investigation.md    # 调查发现（实验数据 + 代码发现）
├── 02_root_cause.md       # 根因分析
├── 03_code_changes.md     # 代码改动精确文本
├── 04_verification.md     # 验证结果（数值 + 覆盖范围）
├── experiment_log.md      # 【关键】每次实验的完整记录
├── hypothesis_log.md      # 所有假说，含被证伪的
├── commit_log.md          # 所有 commit，含 revert
└── logs/                  # 实验/运行日志（不放 /tmp）
```

### 1.2 定义参数 Schema 并记录 Baseline

**第一步**：参考 PRE_TASK_GUIDE.md Part A1，定义本任务的实验参数和指标。

**第二步**：立即记录 Baseline（任务开始时的初始状态）：

```markdown
## Baseline（任务开始时）
日期：YYYY-MM-DD HH:MM
命令/操作：{完整命令或操作步骤，copy-paste}

配置（按本任务参数 schema）：
  {param_1} = {值}
  {param_2} = {值}

结果（按本任务指标 schema）：
  {metric_1} = {精确值}
  {metric_2} = {精确值}
  状态：PASS / FAIL / CRASH

（如果 CRASH）完整错误信息：{copy-paste，不 paraphrase}
日志：/home/hanchang/project_{name}/logs/{文件名}
```

### 1.3 从 recall/memory 获取已知事实

```bash
cat /root/.local/share/claude/recall/hanchang/knowledge/index.md
cat /root/.claude/projects/-home-hanchang/memory/MEMORY.md
```

将已知事实写入 `experiment_log.md` 顶部，标注来源，这些无需在任务中重新验证。

---

## 阶段二：任务进行中

> **核心原则**：结论只能来自实验数值、代码原文、文档引用。
> 推断标注 `[HYPOTHESIS]`，验证后才能标 `[CONFIRMED]`。

### 2.1 每次实验后立即记录

使用 PRE_TASK_GUIDE.md 中的实验记录模板。**最容易犯的错误**：

| 错误做法 | 正确做法 |
|---------|---------|
| 只记录指标值，不记录实验配置 | 每个数据点必须对应完整的参数配置（按本任务 schema） |
| 不同配置的结果放在一起比较 | 每个配置的数据点独立记录，比较时明确注明配置差异 |
| 从记忆重写代码/命令/错误信息 | 直接 copy-paste 实际文件或终端输出 |
| 只记录 PASS 的实验 | FAIL 和被证伪的假说同等重要，必须完整记录 |
| 实验完成后才补记 | 实验结束后立即记录（记忆会衰减） |

### 2.2 假说管理

每个假说都要经历完整生命周期：

```
[HYPOTHESIS] → 实验 → [CONFIRMED] 或 [DISPROVED + 证据]
```

**被证伪的假说必须完整保留**，不能删除。这些记录将成为 summary 中"弯路"章节的依据——诚实记录"走过的弯路"和"为什么这条路不通"，是 project summary 最有参考价值的部分。

### 2.3 代码发现记录

```markdown
文件：{绝对路径}
行号：L{start}–L{end}
原文（copy-paste，不修改）：
{copy-paste 原始代码/配置}
含义：{你的理解}
关联假说：#{假说编号}
关联实验：#{实验编号}
```

### 2.4 Commit 记录

每次 commit 后立即记录（参见 PRE_TASK_GUIDE.md B4 模板）：
- 仓库 + 操作目录（避免从错误的仓库 push）
- hash（从 git log copy-paste）
- 改了什么 + 为什么
- 是否后续 revert + revert 原因

### 2.5 日志和产出保存

**日志必须保存到 DOC_DIR，不能放在 /tmp**（机器重启后 /tmp 消失）：

```bash
# 正确
tee /home/hanchang/project_{name}/logs/run_$(date +%Y%m%d_%H%M).log

# 错误（重启后丢失）
tee /tmp/output.log
```

---

## 阶段三：任务结束后

### 3.1 写作前：收集和核查材料

| 来源 | 检查项 |
|------|--------|
| `experiment_log.md` | 每次实验配置完整，结果精确，无空缺字段 |
| `hypothesis_log.md` | 包含所有假说，含被证伪的 |
| `commit_log.md` | 每个 hash 已从 git log 核实 |
| `logs/` | 运行日志已持久化（不在 /tmp） |
| recall knowledge | 已查阅，与任务记录一致 |
| 代码原文 | 关键行号仍然有效（代码未被移动或重构） |

### 3.2 写作结构（每个子任务）

```markdown
# 子任务 N：{名称}
**日期**：
**状态**：✅ / ⚠️
**commits**：{hash}（仓库）

## 1. 背景
{问题从何而来，起始状态，症状描述}

## 2. 调查过程
{包含走过的弯路！每个关键实验注明完整配置，不只写结论}

## 3. 根因
{每个结论附来源：实验 #编号 or 代码 文件 L行号}

## 4. 解决方案
{精确代码，可运行；注意语法、运算符优先级、类型匹配}

## 5. 验证结果
{覆盖的场景 + 【未覆盖的场景】都要写}

## 6. 教训
{针对本任务的具体教训，写前先核实是否真正来自本任务}
```

### 3.3 Mermaid 图写作规范

- **依赖图**：每条依赖边需要技术理由（B 需要 A 的代码修改，而非仅因为时间先后）
- **before/after 对比**：拆成两张独立的图，不在同一图里混用两种状态
- **所有节点有入边**（无孤立节点）
- **决策节点**：每个条件分支唯一（一个 Yes，一个 No，不出现两个 Yes）

### 3.4 自检清单（写完后逐条验证）

#### 数据准确性
- [ ] 每个关键指标值都标注了对应的完整实验配置（按本任务参数 schema，无缺失字段）
- [ ] 不同配置的实验结果没有混用（每个数据点唯一对应一个实验配置）
- [ ] 阈值表述有具体案例支撑（"接近上限"、"明显异常"等须附实测数据，不用模糊词汇单独定性）
- [ ] 指标表述与实测精度一致（如实测 99.99% 准确率，不能写"完全准确"；实测 cos_sim=0.999989，不能写"bit-exact"）

#### 表述范围
- [ ] 结论说明了适用条件（"在配置 X 下成立"，不写无条件全称）
- [ ] 没有基于少量样本的全称结论（测了 N 个 case 说"未观察到"，不说"不存在"）
- [ ] "未测试"的场景明确标注（区分"实验验证"和"理论推断"）
- [ ] 假说（unverified）和结论（experimentally verified）分开，未混用

#### 代码正确性
- [ ] 所有代码示例在目标语言中语法正确（或明确标注为 pseudocode）
- [ ] 函数返回值类型正确（如返回 tuple 不能直接做运算）
- [ ] 运算符优先级正确（必要时加括号明确语义）
- [ ] 数据类型匹配（int/float/string 不能互换赋值）
- [ ] 代码示例为 copy-paste 原文，不是从记忆重写的版本

#### 逻辑结构
- [ ] 依赖图的每条边有技术理由，而非仅因时间顺序
- [ ] 弯路（被证伪的假说）有记录，不只记录成功路径
- [ ] 教训针对本任务，写前核实该教训是否真正来自本任务（而非照搬其他任务）
- [ ] 发现顺序（时间）和逻辑依赖（因果）区分清楚

---

## 材料来源速查

写 project summary 时按顺序查阅：

```
1. recall knowledge files
   /root/.local/share/claude/recall/hanchang/knowledge/index.md

2. project_{name}/ 目录的各文档
   experiment_log.md, hypothesis_log.md, commit_log.md

3. git log（核查 commit hash）
   git -C {仓库路径} log --oneline -10

4. 运行日志
   /home/hanchang/project_{name}/logs/

5. MEMORY.md（最终状态、已知约束）
   /root/.claude/projects/-home-hanchang/memory/MEMORY.md
```

---

## 常见坑（通用版）

| 坑 | 正确处理 |
|----|---------|
| 依赖图把时间顺序画成逻辑依赖 | 每条边问"B 能否在 A 完成前独立进行" |
| 相似指标来自不同实验配置被并列 | 一律分开，标注各自的完整参数配置 |
| 结论没有说明适用条件 | 加上"在配置 X 下"、"当参数 Y 为 Z 时" |
| 教训从其他任务直接照搬 | 写教训前确认：这个教训是在本任务中实际遇到的？ |
| 只记录最终成功的路径 | 被证伪的假说和失败的方案同样重要，保留完整记录 |
| 发现新 bug 时忘记记录触发条件 | 立即记录"什么操作/实验触发了这个发现" |
| 代码示例从记忆重写 | 永远 copy-paste，永远不从记忆重写 |
