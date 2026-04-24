---
name: project-summary
description: |
  Write a rigorous, verifiable project summary for a completed engineering task.
  Supports a parent-child inheritance model: the skill instantiates a task-specific
  child template, evolves it during the task, and promotes learnings back to the parent.
  Trigger phrases: "write project summary", "create project doc", "document this task",
  "总结这个任务", "写 project summary", "做任务总结",
  "用 project-summary skill 做 X", "instantiate project-summary for X".
---

# Project Summary — 工程任务文档化全流程

任务：`$ARGUMENTS`

---

## 继承模型概览

```
SKILL.md (父类 — 通用原则)
  └── PRE_TASK_GUIDE.md (父类配套 — 通用记录规范)
        └── INSTANCE_TEMPLATE.md (子类骨架 — instantiation 起点)
              └── project_{name}/TASK_TEMPLATE.md (子类实例 — 任务特化)
```

子类实例**继承**父类的所有结构和原则，只需填写任务特有的部分（参数 schema、指标定义、通过标准）。任务结束后，子类中发现的通用规律可以**反向 promote** 回父类。

---

## Workflow 1：Instantiate（任务开始时）

> **触发**：用户说"用 project-summary skill 做 X 任务"时执行。

### Step 1：信息收集

按顺序收集以下信息（优先从代码/文档读取，不足时再问用户）：

**从代码/文档自动读取：**
- 相关仓库结构（`ls`、`git log --oneline -5`）
- 已有的 README、spec、已知 bug 记录
- 上一次任务的 recall knowledge（`/root/.local/share/claude/recall/hanchang/knowledge/index.md`）
- MEMORY.md 中的相关条目

**需要向用户确认的（最多问 5 个）：**
```
Q1. 任务目标是什么？（一句话，SMART 原则）
Q2. 成功标准是什么？（什么指标达到什么值算完成）
Q3. 最可能的 debug/实验循环是什么？（跑推理？跑单元测试？对比 diff？）
Q4. 有什么已知约束？（不能改某些文件、特定硬件要求等）
Q5. 有什么已知的风险或预期 bug？
```

### Step 2：生成子类实例

读取 `INSTANCE_TEMPLATE.md`，填入收集到的信息，生成：

```
/home/hanchang/project_{name}/TASK_TEMPLATE.md
```

同时创建完整的项目目录结构（参见父类 1.1 节）。

### Step 3：向用户展示子类实例，确认后开始任务

展示生成的 `TASK_TEMPLATE.md`，重点确认：
- 参数 schema 是否覆盖了所有关键变量
- 成功标准是否可量化
- 有没有遗漏的已知约束

---

## Workflow 2：Evolve（任务进行中）

> 使用 PRE_TASK_GUIDE.md 中的模板记录实验、假说、代码发现、commit。

### 发现通用规律时：标记 Promotion Candidate

当你在任务中发现了一个**可能适用于其他任务**的规律（不仅限于本任务），在子类的 `## Promotion Candidates` 节追加：

```markdown
## Promotion Candidates

### [PC-{编号}] {简短描述}
发现时间：YYYY-MM-DD
来源：实验 #{编号} / 代码发现 #{编号}

**内容**：
{具体的规律/原则/checklist 条目，用父类可以直接使用的语言描述}

**为什么认为可以 promote**：
{在本任务中如何体现？为什么认为对其他任务也有价值？}

**建议加入父类的位置**：
[ ] SKILL.md — 自检清单
[ ] SKILL.md — 常见坑
[ ] SKILL.md — 写作结构
[ ] PRE_TASK_GUIDE.md — 记录模板
[ ] PRE_TASK_GUIDE.md — 常见遗漏点
[ ] 其他：{具体位置}

**置信度**：
[ ] 高（在本任务中有明确实验证据）
[ ] 中（有观察支撑，但未做完整验证）
[ ] 低（直觉，需要更多任务验证）
```

### 子类实例的更新节奏

| 时机 | 需要更新的内容 |
|------|--------------|
| 每次实验后 | experiment_log.md |
| 发现新 bug/根因后 | hypothesis_log.md + 01_investigation.md |
| Commit 后 | commit_log.md |
| 发现通用规律后 | Promotion Candidates 节 |
| 任务阶段性完成后 | TASK_TEMPLATE.md 的状态字段 |

---

## Workflow 3：Promote（任务结束后）

> 任务完成后执行，将子类中发现的通用规律反向 promote 到父类。

### Step 1：收集所有 Promotion Candidates

读取 `project_{name}/TASK_TEMPLATE.md` 中的 `## Promotion Candidates` 节，列出所有候选项。

### Step 2：整理并向用户展示

按父类位置分组，展示给用户：

```
以下是本次任务中发现的 {N} 个 Promotion Candidates，请 review 后决定是否合并到父类模板：

━━━ 建议加入 SKILL.md — 自检清单 ━━━
[PC-1] {内容}
来源：{实验/代码依据}
置信度：高
→ [ ] 接受  [ ] 修改后接受  [ ] 拒绝

[PC-2] ...

━━━ 建议加入 PRE_TASK_GUIDE.md — 常见遗漏点 ━━━
[PC-3] ...
```

### Step 3：执行用户决定

- **接受**：直接 Edit 对应父类文件，加入该条目
- **修改后接受**：用用户给出的措辞修改后 Edit
- **拒绝**：在子类 TASK_TEMPLATE.md 中标注 `[REJECTED: {原因}]`，保留记录

### Step 4：Commit 更新后的父类

```bash
cd /home/hanchang/agent_skill
git add .claude/skills/project-summary/
git commit -m "promote: update parent template from {task-name} task

Promoted items:
- [PC-N] {描述} → SKILL.md 自检清单
- [PC-M] {描述} → PRE_TASK_GUIDE.md 常见遗漏点
"
git push origin main
```

---

## 父类原则（所有子类必须遵守）

### 数据记录原则
- 结论只能来自：实验数值、代码原文（文件路径+行号+copy-paste）、文档引用
- 推断标注 `[HYPOTHESIS]`，验证后才标 `[CONFIRMED]`
- 不同参数配置的实验结果绝不并列比较
- 失败路径和被证伪假说必须完整保留

### 表述原则
- 每个结论注明适用条件（"在配置 X 下"）
- 数值精度与实测一致（不夸大精度）
- "未测试"的场景明确标注
- 少量样本的观察不能推广为全称结论

### 代码原则
- 代码示例必须 copy-paste（不从记忆重写）
- 代码语法正确（或明确标 pseudocode）
- 函数返回值类型正确，运算符优先级明确

### 文档结构原则
- 弯路（被证伪假说）与成功路径同等重要
- 教训针对本任务（写前核实来源）
- 依赖图边有技术理由（不因时间顺序画依赖）

---

## 自检清单（父类通用部分）

写完 summary 后逐条验证：

#### 数据准确性
- [ ] 每个关键指标值标注了完整实验配置（按本任务参数 schema）
- [ ] 不同配置的结果没有混用
- [ ] 阈值表述有具体案例（不用无依据的模糊定性词）
- [ ] 指标表述与实测精度一致（不夸大精度）

#### 表述范围
- [ ] 结论说明适用条件，无无条件全称陈述
- [ ] 少量样本的观察标注了样本量限制
- [ ] "未测试"场景明确标注（"理论推断"vs"实验验证"）
- [ ] `[HYPOTHESIS]` 和 `[CONFIRMED]` 分开，未混用

#### 代码正确性
- [ ] 代码示例语法正确（或明确标 pseudocode）
- [ ] 函数返回值类型正确
- [ ] 运算符优先级正确
- [ ] 数据类型匹配

#### 逻辑结构
- [ ] 依赖图的每条边有技术理由
- [ ] 弯路（被证伪假说）有记录
- [ ] 教训针对本任务，已核实来源
- [ ] 发现顺序（时间）和逻辑依赖（因果）区分清楚
- [ ] Mermaid 图：无孤立节点，before/after 拆成两图

---

## 材料来源速查

```
recall knowledge files:
  /root/.local/share/claude/recall/hanchang/knowledge/index.md

项目文档:
  /home/hanchang/project_{name}/
  experiment_log.md, hypothesis_log.md, commit_log.md

git log:
  git -C {仓库路径} log --oneline -10

运行日志:
  /home/hanchang/project_{name}/logs/

MEMORY.md:
  /root/.claude/projects/-home-hanchang/memory/MEMORY.md
```
