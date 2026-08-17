# Pre-Task & During-Task Data Collection Guide

任务进行中的数据采集快速参考。在任何类型的工程任务中均适用。
高质量的 project summary 取决于这份记录的质量。

---

## 核心原则（任何任务类型通用）

| 原则 | 说明 |
|------|------|
| **数据隔离** | 不同配置的实验结果绝不并列比较 |
| **只 copy-paste** | 代码、命令、错误信息必须从实际文件/终端复制，不从记忆重写 |
| **区分推断和验证** | `[HYPOTHESIS]` 未经实验不能进入 summary 作为结论 |
| **失败同等重要** | 被证伪的假说、失败的修复、revert 的原因，与成功路径同等完整记录 |
| **条件范围** | 每个结论注明"在什么配置/条件下成立"，不写无条件全称陈述 |

---

## Part A：任务开始时（一次性设置）

### A1 定义本任务的"参数 Schema"

**这是最关键的一步**。不同任务关心的实验参数完全不同。在开始之前，写下：
"哪些参数会影响实验结果？"

```markdown
## 本任务实验参数 Schema
任务名：{任务名称}
日期：YYYY-MM-DD

### 关键参数（每次实验必须记录的）
| 参数名 | 说明 | 示例值 |
|--------|------|--------|
| {param_1} | {说明} | {示例} |
| {param_2} | {说明} | {示例} |
| ...      | ...    | ...    |

### 关键指标（每次实验的输出）
| 指标名 | 说明 | 期望范围 |
|--------|------|---------|
| {metric_1} | {说明} | {如 > 0.9999} |
| {metric_2} | {说明} | ... |

### 合格/不合格标准
PASS 定义：{metric_1} > X 且 {metric_2} < Y
FAIL 定义：{其他情况}
```

**不同任务类型的参数 schema 示例**：

<details>
<summary>ML Kernel 调试（如 MoE、Attention）</summary>

```
参数：token数(M/T), hidden_size, inter_dim, expert数(E), top-k(K),
      dtype(bf16/fp8), preshuffle, is_shuffled, quant_type, block_m
指标：cos_sim（精确到6位）, TTFT(ms), TPOT(ms)
PASS：cos_sim > 0.9999
```
</details>

<details>
<summary>网络/API 性能调试</summary>

```
参数：并发数, batch_size, 超时时间, 重试次数, payload大小(KB), 协议版本
指标：P50/P99延迟(ms), 吞吐量(QPS), 错误率(%)
PASS：P99 < 100ms 且 错误率 < 0.1%
```
</details>

<details>
<summary>编译器/代码生成调试</summary>

```
参数：输入规模(行数/节点数), 优化级别(-O0/-O2/-O3), 目标架构, 特性开关
指标：编译时间(s), 生成代码大小(KB), 运行时性能(ns/op)
PASS：生成代码与参考实现输出一致（diff 为空）
```
</details>

<details>
<summary>分布式系统调试</summary>

```
参数：节点数, TP/PP/DP 配置, 数据集大小, 网络带宽, GPU/CPU型号
指标：吞吐量(tokens/s), 内存占用(GB), 通信延迟(ms), 是否 OOM/crash
PASS：完整跑通，吞吐量 > baseline 的 90%
```
</details>

---

### A2 创建项目目录结构

```bash
PROJECT="{任务名}"
mkdir -p ~/project_${PROJECT}/logs
touch ~/project_${PROJECT}/{experiment_log,hypothesis_log,commit_log}.md
```

目录说明：

```
project_{name}/
├── experiment_log.md   # 每次实验的完整记录（本手册 Part B 模板）
├── hypothesis_log.md   # 所有假说（含 DISPROVED）
├── commit_log.md       # 所有 commit（含 revert）
└── logs/               # 实验日志文件（不放 /tmp，重启会丢失）
```

### A3 记录 Baseline

```markdown
## Baseline（任务开始时的初始状态）
日期：YYYY-MM-DD HH:MM
命令/操作：
{copy-paste 完整命令或操作步骤}

配置（按 A1 定义的参数 schema 填写）：
{param_1} = {值}
{param_2} = {值}
...

结果：
{metric_1} = {值}
{metric_2} = {值}
状态：PASS / FAIL / CRASH

（如果 CRASH）完整错误信息：
{copy-paste，不 paraphrase}

日志保存路径：~/project_*/logs/{文件名}
```

### A4 从 recall/memory 提取已知事实

```bash
cat /root/.local/share/claude/recall/<user>/knowledge/index.md
cat /root/.claude/projects/-home-<user>/memory/MEMORY.md
```

在 `experiment_log.md` 顶部写入（不可在任务中重新验证的事实）：

```markdown
## 已知事实（任务开始前已验证，无需重验）
F1. {事实} [来源：recall/{文件名} / memory.md / 文档]
F2. ...
```

---

## Part B：任务进行中（每次实验/发现后填写）

### B1 实验记录

```markdown
## 实验 #{编号} — {简短描述}
时间：YYYY-MM-DD HH:MM
目的：（验证哪个假说？探索什么问题？）
命令/操作：
{copy-paste}

### 配置（按本任务 A1 定义的 schema 填写）
{param_1} = {值}
{param_2} = {值}
{...其他关键参数...}

### 结果
{metric_1} = {精确值}
{metric_2} = {精确值}
状态：PASS / FAIL / CRASH

（如果 FAIL/CRASH）完整错误信息（copy-paste，不 paraphrase）：
```
{原始错误}
```

### 代码来源（如有）
文件：{绝对路径}
行号：L{start}–L{end}
原文（copy-paste）：
```
{原文}
```

### 结论
[CONFIRMED 假说 #{编号}] / [DISPROVED 假说 #{编号}] / [NEW FINDING]
{结论说明，必须注明"在上述配置下"}

### 下一步
{这个结果触发了什么？}
日志：~/project_*/logs/{文件名}
```

**常见遗漏**：
- 切换配置前，先记录切换前的结果
- 实验 PASS 了也要记录完整配置（不只记录 FAIL）
- 结论必须写"在上述配置下"，不写无条件全称

---

### B2 假说记录

```markdown
## 假说 #{编号} — {描述}
提出时间：YYYY-MM-DD
状态：[HYPOTHESIS]

基于：（什么观察/代码/逻辑 → 提出这个假说）
预期：（如果假说正确，实验应看到 {metric} = {预期值}）
验证实验：#{实验编号}

--- 实验完成后填写 ---
实际结果：
状态：[CONFIRMED] / [DISPROVED]
理由：（引用实验 #{编号} 的数据 or 代码 L{行号}）

（如果 DISPROVED）
为什么假说错了：
对根因理解的修正：
```

> **规则**：DISPROVED 的假说不删除，保留完整记录。这是 summary "弯路"章节的原材料。

---

### B3 代码发现记录

```markdown
## 代码发现 #{编号} — {描述}
时间：YYYY-MM-DD
文件：{绝对路径}
行号：L{start}–L{end}

原文（copy-paste，不修改）：
```
{原文}
```

含义：{你的理解}
可能的误区：{需要实验验证的点}
关联假说：#{假说编号}
关联实验：#{实验编号}
```

---

### B4 Commit 记录

```markdown
## Commit #{编号}
时间：YYYY-MM-DD HH:MM
仓库：{仓库名}
操作目录：{push 时用的仓库路径}
Hash：{从 git log copy-paste}
分支：{PR 分支名}

改了什么：
  文件：{绝对路径}
  行号：L{start}–L{end}
  改动：{copy-paste diff 关键部分}

为什么改：（关联假说/实验 #{编号}）

是否 revert：[ ] 否   [ ] 是
（如果 revert）
  Revert hash：
  Revert 原因：（实验证伪？其他？）
```

---

### B5 构建/编译缓存操作记录

适用场景：JIT 编译（如 aiter）、make clean、pip reinstall、清 __pycache__ 等。

```markdown
## 缓存清理 #{编号}
时间：YYYY-MM-DD HH:MM
触发原因：（修改了什么文件/模块？）
清理命令（copy-paste）：
```bash
{命令}
```

清理前结果：{metric} = {值}（使用旧缓存时的错误结果）
清理后结果：{metric} = {值}（重新构建后的正确结果）
重新构建耗时：{时间}
```

---

## Part C：任务结束时（写 summary 前检查）

### 数据完整性
- [ ] 所有实验都有完整配置（按本任务 A1 定义的 schema 填写，无空缺字段）
- [ ] 每个结果值（cos_sim、延迟、错误率等）唯一对应一个实验配置
- [ ] 不同配置的实验结果没有混用
- [ ] FAIL 和被证伪的假说有记录（不只有成功路径）
- [ ] 所有 commit hash 从 git log 核实过

### 代码质量
- [ ] 代码片段均为 copy-paste 原文（不从记忆重写）
- [ ] 错误信息为原始文本（不是 paraphrase 版本）
- [ ] 代码示例在目标语言中语法正确（若非可运行代码，明确标注为 pseudocode）

### 日志持久化
- [ ] 所有日志保存在 `~/project_*/logs/`（不在 /tmp）
- [ ] 日志文件名包含时间戳或描述，一年后仍能识别

### 边界清晰
- [ ] "未测试"的场景明确标注（如"基于对齐计算推断，未实测"）
- [ ] `[HYPOTHESIS]`（理论推断）和 `[CONFIRMED]`（实验验证）分开，无混用
- [ ] 每个结论注明适用条件，不写无条件全称陈述

---

## 快速参考：哪些时刻容易漏记

| 时刻 | 容易遗漏 |
|------|---------|
| 实验 FAIL 后立刻切换配置 | 切换前的完整配置和 FAIL 结果 |
| 发现新 bug 时 | 是哪个实验/什么操作触发了这个发现 |
| 改完代码 PASS 了 | 改了哪行、为什么这样改（不只记"改好了"）|
| 缓存/环境问题解决后 | 清理前的错误结果（证明是缓存问题的对比数据）|
| 一个假说被证伪时 | 该假说的完整记录（被证伪≠可以删除）|
| 选了方案 A 放弃方案 B | 方案 B 失败的具体原因和错误信息 |
| 跑了多次调参 | 每次的参数和结果（不只记最优的那次）|
