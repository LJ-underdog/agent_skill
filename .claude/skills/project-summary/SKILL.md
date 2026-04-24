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
阶段一：任务开始前      阶段二：任务进行中      阶段三：任务结束后
[目录结构 + Baseline]  [实验记录 + 假说管理]   [写作 + 自检]
```

配套工具：[PRE_TASK_GUIDE.md](./PRE_TASK_GUIDE.md)（任务中随时查阅的记录模板）

---

## 阶段一：任务开始前

### 1.1 创建项目目录结构

```bash
mkdir -p /home/hanchang/project_{name}/{logs}
```

标准文件结构：

```
project_{name}/
├── README.md              # 项目状态、目标、最终结果（持续更新）
├── 01_investigation.md    # 调查发现（实验数据 + 代码发现）
├── 02_root_cause.md       # 根因分析（审批前确认）
├── 03_code_changes.md     # 代码改动精确文本
├── 04_verification.md     # 验证结果（数值 + 覆盖范围）
├── experiment_log.md      # 【关键】每次实验的完整记录（见 PRE_TASK_GUIDE）
├── hypothesis_log.md      # 所有假说，含被证伪的
└── logs/                  # 推理/测试日志（不放 /tmp）
```

### 1.2 记录 Baseline

在任务开始时立即记录当前状态，这是后续所有比较的基准：

```markdown
## Baseline（任务开始时）
日期：YYYY-MM-DD
命令：{完整推理/测试命令}
结果：
  cos_sim = {值}（配置：M={}, T={}, hidden={}, inter_dim={}, dtype={}, ...）
  TTFT = {ms}，TPOT = {ms}
  输出质量：{描述或 prompt/response 摘要}
已知 workaround：{如 ATOM_STEP3P5_NO_SLIDING=1}
```

### 1.3 从 recall/memory 获取已知事实

```bash
# 查阅 recall knowledge
ls /root/.local/share/claude/recall/hanchang/knowledge/
cat /root/.local/share/claude/recall/hanchang/knowledge/index.md

# 查阅 MEMORY
cat /root/.claude/projects/-home-hanchang/memory/MEMORY.md
```

将已知事实写入 `experiment_log.md` 顶部，标注 `[已验证，来源：recall/{文件名}]`。

---

## 阶段二：任务进行中

> **核心原则**：结论只能来自实验数值、代码原文、文档引用。
> 推断标注 `[HYPOTHESIS]`，验证后才能标 `[CONFIRMED]`。

### 2.1 每次实验后立即记录

使用 PRE_TASK_GUIDE.md 中的实验记录模板。**最容易犯的错误**：

| 错误做法 | 正确做法 |
|---------|---------|
| 记录 `cos_sim = -0.007`，不写配置 | 记录完整配置（H=2048, I=640, T=32, bf16, preshuffle_off+V3） |
| 不同配置的实验结果放在一起比较 | 每个配置的数据点独立记录，比较时明确注明配置差异 |
| 从记忆重写代码示例 | 直接 copy-paste 实际测试脚本的代码 |
| 只记录 PASS 的实验 | FAIL 和被证伪的假说同等重要 |

### 2.2 假说管理

每个假说都要经历完整生命周期：

```
[HYPOTHESIS] → 实验 → [CONFIRMED] 或 [DISPROVED + 证据]
```

**被证伪的假说必须完整保留**，不能删除。这些记录将成为 summary 中"弯路"章节的依据（canary 实验证伪 Bugs 2-4 就是典型案例）。

### 2.3 代码发现记录

```markdown
文件：/home/hanchang/aiter/aiter/fused_moe.py
行号：L904-907
原文：
```python
if not run_1stage and inter_dim > 192 and get_gfx() == "gfx950":
    block_m = 128
```
含义：...
关联实验：#实验编号
```

### 2.4 commit 记录

每次 commit 后立即记录：
```
Commit Hash: {hash}
仓库：aiter / ATOM
内容：{改了什么}
原因：{为什么}
是否后续 revert：[ ]
```

### 2.5 推理日志保存

**日志必须保存到 DOC_DIR，不能放在 /tmp**（机器重启后 /tmp 消失）：

```bash
# 正确
tee /home/hanchang/project_{name}/logs/run_$(date +%Y%m%d_%H%M).log

# 错误
tee /tmp/output.log  # 重启后丢失
```

---

## 阶段三：任务结束后

### 3.1 写作前：收集材料

检查以下来源是否都可用：

| 来源 | 检查项 |
|------|--------|
| `experiment_log.md` | 每次实验配置完整，结果精确到位 |
| `hypothesis_log.md` | 包含所有假说，含被证伪的 |
| git log | 每个 commit hash 可查 |
| `logs/` | 推理日志已持久化 |
| recall knowledge | 已查阅，与任务记录一致 |
| 代码原文 | 关键行号仍然有效（代码未被移动） |

### 3.2 写作结构（每个子任务）

```markdown
# 子任务 N：{名称}

**日期**：
**状态**：✅ / ⚠️
**commits**：{hash}（仓库）

## 1. 背景
{问题从何而来，起始状态，症状描述}

## 2. 调查过程
{包含走过的弯路！每个关键实验注明配置}

## 3. 根因
{每个结论附来源：实验#编号 or 代码 L行号}

## 4. 解决方案
{精确代码，可运行，注释说明逻辑}
{注意：运算符优先级、数据类型必须正确}

## 5. 验证结果
{覆盖的场景 + 【未覆盖的场景】都要写}

## 6. 教训
{针对本任务的具体教训，不照搬其他任务}
```

### 3.3 Mermaid 图写作规范

- **任务依赖图**：每条边需要技术理由（不能因时间顺序画依赖）
- **before/after 对比**：拆成两张独立的图，不在同一图里混用
- **所有节点必须有入边**（无孤立节点）
- **决策节点**：每个条件只有一个"Yes"出边，一个"No"出边

### 3.4 自检清单（写完后逐条验证）

#### 数据准确性
- [ ] 每个 cos_sim 值标注了对应实验配置（M, T, inter_dim, dtype 等全部参数）
- [ ] 不同配置的实验结果没有混用（每个数据点唯一对应一个配置）
- [ ] 没有 `> 0.9999 = 正常，0.998~0.999 = 可接受` 这类无具体案例的模糊阈值
- [ ] cos_sim=0.999989 表述为"高精度对齐"不是"bit 级对齐"（bit-exact 应为 1.0）

#### 表述范围
- [ ] 结论说明了适用条件（"在 T=32 batch 下 V3 被自然选中"vs"V3 始终被选中"）
- [ ] 没有基于少量样本的全称结论（"4 个 prompt 未观察到损失"不等于"量化无损失"）
- [ ] "未测试"的场景明确标注（如 tp=8 kernel 仅有对齐计算推断，无实测）
- [ ] 假说（unverified）和结论（experimentally verified）分开，未混用

#### 代码正确性
- [ ] 所有代码示例在 Python 中语法正确，可运行
- [ ] `a.chunk(n)` 返回 tuple，不能直接与矩阵相乘（`x @ w.chunk()`无效）
- [ ] 运算符优先级正确（`*` 和 `@` 混用时加括号：`(silu(g) * u) @ w.T`）
- [ ] Canary 值数据类型匹配（float tensor 用 float canary，不用整数 0xDEADBEEF）
- [ ] 标为 pseudocode 的代码明确说明不可直接运行

#### 逻辑结构
- [ ] 依赖图的每条依赖边有技术理由（A 的代码修改是 B 的前提）
- [ ] 弯路（被证伪的假说）有记录，不只记录成功路径
- [ ] 教训针对本任务，没有照搬其他任务的教训（需确认适用性）
- [ ] Bug 发现顺序和 Bug 逻辑关系区分清楚（时间顺序 ≠ 逻辑依赖）

---

## 材料来源速查

写 project summary 时按顺序查阅：

```
1. recall knowledge files
   /root/.local/share/claude/recall/hanchang/knowledge/index.md
   → 查阅各子任务的实验数据

2. project_* 目录的 01-06 文件（任务进行中写的）
   /home/hanchang/project_{name}/

3. experiment_log.md + hypothesis_log.md
   → 实验配置和假说生命周期

4. git log（核查 commit hash）
   git -C /home/hanchang/junlin12_repos/{aiter,atom} log --oneline -10

5. 推理日志
   /home/hanchang/project_{name}/logs/

6. MEMORY.md（最终状态、已知约束）
   /root/.claude/projects/-home-hanchang/memory/MEMORY.md
```

---

## 常见坑（从 Step-3.5-Flash 总结经验）

| 坑 | 正确处理 |
|----|---------|
| 依赖图把时间顺序画成逻辑依赖 | 每条边问"B 的代码修改是否依赖 A 的代码修改" |
| 同名但不同实验配置的结果并列 | 一律分开表格，标注各自的完整配置 |
| "修复 Bug 0 后 PASS"但没说在什么条件下 | 说明 T=32 batch 下自然选中 V3，decode 场景（T=1-8）仍需 Bug 1 修复 |
| 教训"preshuffle 路径不同"不适用于 BF16 SwigluStep | 写教训前先核实：该教训是否真正来自本任务？ |
| op_test 和生产路径的差异随时间变化 | 明确说明是"修复前"还是"修复后"的路径对比 |
