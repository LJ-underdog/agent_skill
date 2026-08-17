# Task Template: {TASK_NAME}

# 继承自：agent_skill/.claude/skills/project-summary/SKILL.md
# 继承兄弟类（如有）：project_{related_name}/TASK_TEMPLATE.md
# 创建日期：{YYYY-MM-DD}
# 状态：[ACTIVE / COMPLETE / PROMOTING]

<!--
填写指引（Claude 在 Instantiate Step 2 时参考）：

TASK_NAME       → 简短英文名，如 fp8-tp2-inference
继承兄弟类      → 若有相关任务，写其路径；否则删除该行
状态            → 任务进行中=ACTIVE，完成=COMPLETE，正在 promote=PROMOTING
-->

---

## 任务概述

**目标**：{一句话，SMART 原则}
**相关仓库**：{列出，如 ~/ATOM, ~/aiter}
**环境/硬件约束**：{如 gfx950, ROCm, 避开 GPU5}

<!--
推导来源：
- 目标    → README / 用户 Q1
- 仓库    → git remote -v 或用户描述
- 约束    → CLAUDE.md / MEMORY.md / 用户 Q3
-->

---

## 参数 Schema

> 本任务中"哪些变量会影响实验结果"。每次实验必须记录所有参数。
> 继承兄弟类时：只写与兄弟类不同或新增的参数，相同的标 [继承自 {X}]。

<!--
推导来源：
- 查命令行参数：argparse / click / bash 脚本的 --xxx 选项
- 查函数签名：关键函数的输入参数
- 查 Makefile / 测试脚本：哪些参数被遍历
- 参考兄弟类的参数 schema（如有）
示例（ML kernel 任务）：token数、hidden_size、inter_dim、dtype、block_m
示例（网络任务）：并发数、batch_size、超时、payload大小
示例（编译任务）：优化级别、目标架构、特性开关
-->

| 参数名 | 说明 | 示例值 | 来源 |
|--------|------|--------|------|
| {param_1} | {说明} | {值} | {代码文件 L行号 / 用户确认} |
| {param_2} | {说明} | {值} | ... |

---

## 指标 Schema

> 本任务中"如何衡量实验是否成功"。

<!--
推导来源：
- 查已有测试/benchmark 脚本的输出格式
- 从任务目标推断："跑通"=无 crash？输出正确？达到延迟目标？
- 参考兄弟类的指标 schema（如有）
示例：cos_sim、TTFT/TPOT、P99 延迟、通过率、编译时间
精度约定：数值型指标精确到几位小数？延迟到毫秒还是秒？
-->

| 指标名 | 说明 | PASS 标准 | FAIL 标准 | 精度 |
|--------|------|-----------|-----------|------|
| {metric_1} | {说明} | {如 > 0.9999} | {如 < 0.99} | {如 6位小数} |
| {metric_2} | {说明} | {说明} | {说明} | {说明} |

---

## 成功标准

```
任务完成 = 满足以下所有条件：
✓ {metric_1} {关系} {阈值}（来源：{baseline 数值 / 规格文档}）
✓ {metric_2} {关系} {阈值}
✓ 回归：{baseline 场景} 不退化
```

<!--
推导来源：
- 已有 baseline 数值（git log 中找到上次成功运行）
- 规格文档 / PR 要求
- 用户 Q2
-->

---

## 已知事实（无需重验）

> 来自 recall / MEMORY.md / 代码阅读，已有实验证据。

<!--
推导来源：
- recall knowledge index → 读取相关子任务的 [已验证] 条目
- MEMORY.md → 已知 bug、架构信息
- 兄弟类的已知事实（标注"继承自 {X}"）
规则：这里只写有明确来源的事实，推断不在这里。
-->

| # | 事实 | 来源 | 是否继承 |
|---|------|------|---------|
| F1 | {描述} | recall/{文件} / 代码 {文件} L{行} | — / 继承自 {X} |
| F2 | ... | ... | ... |

---

## 已知约束

<!--
推导来源：
- CLAUDE.md 中的规则（如不能修改 @support_torch_compile 的文件）
- MEMORY.md 中的约束条目
- 代码注释中的 # DO NOT MODIFY
- 用户 Q3
-->

- {约束 1，如"不能修改 @support_torch_compile 装饰的文件"}
- {约束 2，如"修改代码后必须清缓存：rm -rf /root/.cache/atom/*"}
- {约束 3}

---

## Baseline

<!--
任务开始时立即记录，不要等到实验失败才补记。
命令和结果都要 copy-paste，不从记忆重写。
-->

```
日期：{YYYY-MM-DD HH:MM}
命令/操作（copy-paste）：
{命令}

配置：
  {param_1} = {值}
  {param_2} = {值}

结果：
  {metric_1} = {精确值}
  状态：PASS / FAIL / CRASH

日志：~/project_{name}/logs/{文件名}
```

---

## 任务特化 — 实验记录扩展字段

> 在 PRE_TASK_GUIDE.md B1 模板基础上，本任务额外需要记录的字段。

<!--
思考：除了通用的参数 schema，本任务在记录实验时还需要什么？
例如：kernel 名称（调试 dispatch 时）、环境变量（影响行为的 env var）、
      GPU 编号（有异常 GPU 时）、JIT 编译耗时等
-->

| 额外字段 | 说明 | 为什么本任务需要 |
|---------|------|----------------|
| {field} | {说明} | {原因} |

---

## 任务特化 — 自检清单扩展

> 在父类自检清单基础上，本任务额外需要检查的项。

<!--
思考：父类清单有哪些条目对本任务不够具体？本任务有哪些特有的坑？
例如：
- "inter_dim 对齐必须用 128（inter>192）而不是 64"（TP 任务特有）
- "preshuffle 和 is_shuffled 两个参数要分清楚"（MoE 任务特有）
这里写的是本任务发现的，任务结束后判断是否 promote 到父类。
-->

- [ ] {本任务特有检查项 1}
- [ ] {本任务特有检查项 2}

---

## 任务特化 — 常见坑

> 任务进行中发现的本任务特有坑，随时追加。

| 坑 | 正确处理 | 是否 promote 候选 |
|----|---------|-----------------|
| {坑描述} | {正确做法} | [ ] 是  [ ] 否 |

---

## 子任务结构

| 子任务 | 状态 | 文档 | 关键 commit |
|--------|------|------|-------------|
| {名称} | [ ]待 / [~]中 / [✓]完 | {文件名} | {hash} |

---

## Promotion Candidates

> 任务中发现的可能对其他任务也有价值的规律。
> Claude 应主动识别（见 SKILL.md Workflow 2 触发条件），不等用户标记。

<!--
PC 模板（复制后填写）：

### [PC-{N}] {简短描述}
发现时间：YYYY-MM-DD
触发场景：{从 SKILL.md Workflow 2 触发条件表选择}
来源：实验 #{编号} / 代码发现 #{编号} / review 过程

**内容**（用父类可直接使用的措辞）：
{具体的原则/checklist 条目/坑描述}

**为什么 promote**：
{在本任务中的具体表现} + {为什么认为对其他任务也有价值}

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
**Review 结果**：[ ] 待 review  [ ] 接受  [ ] 修改→{内容}  [ ] 拒绝→{原因}
-->

（任务进行中追加，Claude 主动识别）

---

## 任务完成 Checklist

执行 Promote Workflow 前确认：

- [ ] experiment_log.md：所有实验有完整配置记录（无空缺字段）
- [ ] hypothesis_log.md：包含所有假说（含 DISPROVED），无遗漏
- [ ] commit_log.md：所有 hash 已从 git log 核实
- [ ] logs/：所有日志已持久化（不在 /tmp）
- [ ] 所有子任务完成或明确标注未完成原因
- [ ] Promotion Candidates 节已整理，置信度已标注
- [ ] 状态更新为 [COMPLETE]，准备 promote
