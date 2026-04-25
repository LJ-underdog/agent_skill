---
name: project-summary
description: |
  Write a rigorous, verifiable project summary for a completed engineering task.
  Supports a parent-child inheritance model: instantiate a task-specific child
  template, evolve it during the task, and promote learnings back to the parent.
  Trigger phrases: "write project summary", "create project doc", "document this task",
  "总结这个任务", "写 project summary", "做任务总结",
  "用 project-summary skill 做 X", "instantiate project-summary for X".
---

# Project Summary — 工程任务文档化全流程

任务：`$ARGUMENTS`

---

## 强制原则：执行任务必须使用 Agent Team

**所有涉及代码调试、实验运行、修复实施的任务，必须通过 agent-team 执行。不允许单 Claude 直接跑实验或改代码。**

理由：
- Agent team 提供并行调查、独立 reviewer、明确的 Phase 0→1→2→3 门控
- 结论有 teammate 进度文件作为证据链，不依赖单次对话记忆
- Reviewer agent 独立验证根因，防止错误假说直接进入 fix

**标准工作流程（每次任务）**：

```
Step 1: instantiate project-summary  →  生成 TASK_TEMPLATE.md
Step 2: instantiate agent-team       →  生成 TEAM_CONFIG.md（引用 TASK_TEMPLATE 共享字段）
Step 3: agent-team 执行              →  Phase 0（baseline）→ Phase 1（并行调查）→ Phase 2（实施）→ Phase 3（验证）
Step 4: project-summary 整理         →  用 teammate progress 作为 experiment_log，输出 01-04 文档
Step 5: Promote                      →  两个 skill 各自执行 Promote workflow
```

**跳过 agent-team 的唯一允许情况**：预计 <10 tool calls 的纯文档整理或参数查询。

---

## 与 agent-team 的集成

详见 [SKILLS_INDEX.md](../../SKILLS_INDEX.md)，核心要点：

- **先 instantiate 本 skill**，生成 `TASK_TEMPLATE.md`（参数 schema、指标、已知事实）
- agent-team 的 `TEAM_CONFIG.md` 从 `TASK_TEMPLATE.md` 引用共享字段，**不重复填写**
- 使用 agent-team 时，teammate progress 文件即为 experiment_log，**无需另外维护**
- 任务结束后，用本 skill 的写作结构整理 01-04 文档

---

## 继承模型

```
SKILL.md (父类 — 通用原则 + Changelog)
  └── PRE_TASK_GUIDE.md (父类配套 — 通用记录规范)
        └── INSTANCE_TEMPLATE.md (子类骨架)
              ├── project_{name}/TASK_TEMPLATE.md   (子类实例)
              └── project_{name}/TASK_TEMPLATE.md   (可继承另一个子类)
                      ↓ [任务结束后 Promote]
              SKILL.md / PRE_TASK_GUIDE.md (父类更新)
```

子类**只写与父类不同的部分**（参数 schema、指标、约束等）；父类原则自动适用，不在子类重复。

---

## Workflow 1：Instantiate（任务开始时）

### Step 1：自动读取上下文

按顺序读取，**能从代码/文档获取的不问用户**：

```
① git log --oneline -10              → 了解近期改动和代码状态
② cat README.md / CLAUDE.md          → 约束（不能改哪些文件/装饰器）
③ recall knowledge index             → 已知事实，避免重复验证
   /root/.local/share/claude/recall/hanchang/knowledge/index.md
④ MEMORY.md                          → 已知 bug、环境约束、路径
   /root/.claude/projects/-home-hanchang/memory/MEMORY.md
⑤ 上一个相关子类（如有）              → 可继承的参数 schema / 已知事实
   /home/hanchang/project_{related_name}/TASK_TEMPLATE.md
```

### Step 2：推导子类各字段

从读取到的信息推导（不是直接问用户），**推导逻辑**如下：

| 子类字段 | 推导来源 | 推导逻辑 |
|---------|---------|---------|
| **参数 Schema** | 代码接口 / 命令行参数 | 找 argparse / click / 函数签名 / Makefile target，列出可变的输入维度 |
| **指标 Schema** | 任务目标描述 / 已有测试 | "成功"是什么？cos_sim？延迟？通过率？找现有测试/benchmark 脚本的输出格式 |
| **成功标准** | 已有 baseline / 规格文档 | 参考已有 baseline 数值，或从文档找到明确阈值 |
| **已知事实** | recall / MEMORY.md | 直接提取已标 `[已验证]` 的条目 |
| **已知约束** | CLAUDE.md / 代码注释 | 找 `# DO NOT MODIFY`、`@support_torch_compile`、README 中的约束说明 |
| **父类/兄弟类** | project_* 目录 | 如果有相关任务，读其 TASK_TEMPLATE.md 的参数 schema |

### Step 3：向用户确认（最多 5 个问题，只问推导不出来的）

```
Q1. 任务目标？（如果 README 已有，跳过）
Q2. 成功标准的具体数值？（如果有 baseline 测试，跳过）
Q3. 有哪些不能改的文件/接口？（CLAUDE.md 没有的部分）
Q4. 预期的 debug 循环是什么？（跑测试？端到端推理？diff 对比？）
Q5. 有没有相关的兄弟任务可以继承参数 schema？（输入任务名）
```

### Step 4：生成子类实例

读取 `INSTANCE_TEMPLATE.md`，用 Step 1-3 的信息填入，生成：

```
/home/hanchang/project_{name}/TASK_TEMPLATE.md
```

同时建立项目目录（见 1.1 节）。

### Step 5：展示给用户确认

展示生成的 TASK_TEMPLATE.md 关键部分，确认：
- 参数 schema 覆盖了所有关键变量
- 成功标准可量化
- 已知约束没有遗漏

---

## Workflow 2：Evolve（任务进行中）

使用 PRE_TASK_GUIDE.md 中的模板记录实验、假说、代码发现、commit。

### 主动识别 Promotion Candidate 的触发条件

Claude 在以下情况应**主动**提出 PC，不等用户标记：

| 触发场景 | PC 类型 | 建议加入父类位置 |
|---------|---------|---------------|
| 自检清单某条没检查到，导致 review 发现问题 | 补充清单条目 | SKILL.md 自检清单 |
| 遇到父类"常见坑"没覆盖的坑 | 新增坑条目 | SKILL.md 常见坑 |
| 发现某类实验结果容易被漏记 | 新增遗漏提醒 | PRE_TASK_GUIDE.md 常见遗漏点 |
| 某个代码错误模式在多个地方出现 | 代码正确性检查项 | SKILL.md 自检清单-代码正确性 |
| 发现"理论推断"和"实验验证"容易混淆的新场景 | 区分规则 | SKILL.md 自检清单-表述范围 |
| 某参数在本任务很重要，可能在同类任务也很重要 | 参数 schema 建议 | PRE_TASK_GUIDE.md 任务类型示例 |
| 写弯路文档时发现父类结构不够用 | 写作结构改进 | SKILL.md 写作结构 |

### 标记格式

在 TASK_TEMPLATE.md 的 `## Promotion Candidates` 节追加：

```markdown
### [PC-{N}] {简短描述}
发现时间：YYYY-MM-DD
触发场景：{从上表选择，或自定义}
来源：实验 #{编号} / 代码发现 #{编号} / review 过程

**内容**（用父类可直接使用的措辞）：
{具体的原则/checklist 条目/坑描述}

**为什么 promote**：{在本任务中的具体表现 + 为什么认为对其他任务也有价值}

**建议加入父类位置**：
[ ] SKILL.md — 自检清单-数据准确性
[ ] SKILL.md — 自检清单-表述范围
[ ] SKILL.md — 自检清单-代码正确性
[ ] SKILL.md — 自检清单-逻辑结构
[ ] SKILL.md — 常见坑
[ ] PRE_TASK_GUIDE.md — 常见遗漏点
[ ] PRE_TASK_GUIDE.md — 任务类型示例
[ ] 其他：{具体位置}

**置信度**：[ ] 高（实验证据）  [ ] 中（多次观察）  [ ] 低（直觉）
**Review 结果**：[ ] 待 review  [ ] 接受  [ ] 修改→{修改后内容}  [ ] 拒绝→{原因}
```

---

## Workflow 3：Promote（任务结束后）

### Step 1：收集并分组

读取 TASK_TEMPLATE.md 的 `## Promotion Candidates`，按建议位置分组展示：

```
本次任务共 {N} 个 Promotion Candidates：

置信度高（实验证据）：{N1} 个
置信度中（多次观察）：{N2} 个
置信度低（直觉）：{N3} 个
```

### Step 2：分组展示，逐条 review

```
━━━ SKILL.md — 自检清单 ━━━

[PC-1] {内容}（置信度：高）
来源：{实验/review 依据}
→ 接受 / 修改 / 拒绝？

[PC-2] ...

━━━ PRE_TASK_GUIDE.md — 常见遗漏点 ━━━
...
```

### Step 3：执行

- **接受**：Edit 父类文件
- **修改后接受**：按用户给的措辞 Edit
- **拒绝**：在子类 TASK_TEMPLATE.md 中标 `[REJECTED: {原因}]`

### Step 4：更新父类 Changelog（见文末）并 Commit

```bash
cd /home/hanchang/agent_skill
git add .claude/skills/project-summary/
git commit -m "promote: {task-name} → {N} items added to parent template

$(PC 列表)"
git push origin main
```

---

## 跨子类继承（兄弟任务）

当任务 B 与任务 A 高度相关（同一代码库、同类问题），子类 B 可以继承子类 A：

```
INSTANCE_TEMPLATE.md (骨架)
    ↓
project_{A}/TASK_TEMPLATE.md (子类 A)
    ↓
project_{B}/TASK_TEMPLATE.md (子类 B，继承 A 的参数 schema 和已知事实)
```

**子类 B 的继承方式**：
1. 在 TASK_TEMPLATE.md 开头写 `# 继承自：project_{A}/TASK_TEMPLATE.md`
2. 直接复用 A 的参数 schema（不重写相同字段）
3. 只写 B 与 A 不同的参数/约束/已知事实
4. A 中已验证的事实在 B 中标 `[继承自 A，已验证]`，无需重验

**适用场景示例**：
- FP8 任务继承 MoE 任务（同一 MoE kernel，已知 preshuffle/block_m 规律）
- tp=4/8 任务继承 tp=2 任务（参数 schema 相同，只是 TP 数不同）
- 同一模型的不同量化方案（复用架构参数 schema）

---

## 父类原则（所有子类必须遵守）

### 数据记录原则
- 结论只来自：实验数值、代码原文（文件路径+行号+copy-paste）、文档引用
- 推断标注 `[HYPOTHESIS]`，验证后才标 `[CONFIRMED]`
- 不同参数配置的实验结果绝不并列比较
- 失败路径和被证伪假说必须完整保留

### 表述原则
- 每个结论注明适用条件
- 数值精度与实测一致（不夸大精度）
- "未测试"的场景明确标注
- 少量样本的观察不推广为全称结论

### 代码原则
- 代码示例必须 copy-paste（不从记忆重写）
- 代码语法正确（或明确标 pseudocode）
- 函数返回值类型正确，运算符优先级明确

### 文档结构原则
- 弯路（被证伪假说）与成功路径同等重要
- 教训针对本任务（写前核实来源）
- 依赖图边有技术理由（不因时间顺序画依赖）

---

## 自检清单（父类通用）

#### 数据准确性
- [ ] 每个关键指标值标注了完整实验配置（按本任务参数 schema）
- [ ] 不同配置的结果没有混用
- [ ] 阈值表述有具体案例（不用无依据的模糊定性词）
- [ ] 指标表述与实测精度一致（不夸大精度）

#### 表述范围
- [ ] 结论说明适用条件，无无条件全称陈述
- [ ] 少量样本的观察标注了样本量限制
- [ ] "未测试"场景明确标注（区分"理论推断"和"实验验证"）
- [ ] `[HYPOTHESIS]` 和 `[CONFIRMED]` 分开，未混用

#### 代码正确性
- [ ] 代码示例语法正确（或明确标 pseudocode）
- [ ] 函数返回值类型正确
- [ ] 运算符优先级正确（有歧义时加括号）
- [ ] 数据类型匹配

#### 逻辑结构
- [ ] 依赖图的每条边有技术理由
- [ ] 弯路（被证伪假说）有记录
- [ ] 教训针对本任务，已核实来源
- [ ] 发现顺序（时间）和逻辑依赖（因果）区分清楚
- [ ] Mermaid 图：无孤立节点，before/after 拆成两图

---

## 常见坑（通用）

| 坑 | 正确处理 |
|----|---------|
| 依赖图把时间顺序画成逻辑依赖 | 每条边问"B 能否在 A 完成前独立进行" |
| 相似指标来自不同实验配置被并列 | 一律分开，标注各自的完整参数配置 |
| 结论没有说明适用条件 | 加上"在配置 X 下"、"当参数 Y 为 Z 时" |
| 教训从其他任务直接照搬 | 写教训前确认：在本任务中实际遇到了吗？ |
| 只记录最终成功的路径 | 被证伪的假说和失败方案同样保留 |
| 发现新 bug 时忘记记录触发条件 | 立即记录"什么操作/实验触发了这个发现" |
| 代码示例从记忆重写 | 永远 copy-paste，永远不从记忆重写 |
| 量化/精度相关任务先分析 kernel，后读量化配置 | 量化类型决定整条 dispatch 路径，必须先读配置文件（weight_block_size 等字段）再分析 kernel 参数（来源：fp8-tp2 任务，若不先读 quant config 分析方向可能完全错误） |

---

## Changelog（父类更新历史）

> 记录每次 Promote 操作带来的父类变更。

| 日期 | 来源任务 | 变更内容 | PC 编号 |
|------|---------|---------|---------|
| 2026-04-24 | step35-flash | 初始版本，基于 5 个子任务的 review 经验 | — |
| 2026-04-25 | fp8-tp2-inference（PC-2） | 常见坑：量化/精度任务必须先读量化配置再分析 kernel | — |

---

## 材料来源速查

```
recall knowledge:  /root/.local/share/claude/recall/hanchang/knowledge/index.md
MEMORY.md:         /root/.claude/projects/-home-hanchang/memory/MEMORY.md
项目文档:          /home/hanchang/project_{name}/
git log:           git -C {仓库路径} log --oneline -10
运行日志:          /home/hanchang/project_{name}/logs/
```
