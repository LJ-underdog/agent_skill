# Pre-Task & During-Task Data Collection Guide

任务进行中的数据采集快速参考。每次实验/发现后立即填写对应模板。
高质量的 project summary 取决于这份记录的质量。

---

## 核心原则

**数据隔离**：不同实验配置的结果绝对不并列比较。
**只 copy-paste**：代码、命令、错误信息必须从实际文件/终端复制，不从记忆重写。
**区分推断和验证**：标 `[HYPOTHESIS]` 的结论未经实验不能进入 summary。
**失败同等重要**：被证伪的假说、失败的修复、revert 的原因，与成功路径同等完整记录。
**条件范围**：每个结论注明"在什么配置/条件下成立"。

---

## Part A：任务开始时（一次性）

### A1 目录结构

```bash
PROJECT=step35-fp8  # 替换为实际名称
mkdir -p /home/hanchang/project_${PROJECT}/{logs}
touch /home/hanchang/project_${PROJECT}/{experiment_log,hypothesis_log,commit_log}.md
```

### A2 Baseline 记录

在 `experiment_log.md` 顶部写入：

```markdown
# Baseline（任务开始）
日期：YYYY-MM-DD HH:MM
命令：
```bash
{完整命令，包含所有参数}
```
结果：
  状态：PASS / CRASH / WRONG OUTPUT
  cos_sim：{值，精确到6位} （或：crash message 原文，不 paraphrase）
  TTFT：{ms}，TPOT：{ms}
  配置：M={}, T={}, hidden={}, inter_dim={}, E={}, K={}, dtype={}, preshuffle={}, is_shuffled={}, quant_type={}
已知 workaround（如有）：ATOM_STEP3P5_NO_SLIDING=1 等
日志：{保存路径，必须在 /home/hanchang/project_*/logs/ 下}
```

### A3 已知事实初始化

从 recall 和 memory 提取已知事实，写入 `experiment_log.md`：

```markdown
# 已知事实（任务开始前已验证）
来源：recall/knowledge/{文件名} 或 memory/MEMORY.md

F1. {事实描述} [来源：{文件} L{行号} / 实验日期]
F2. ...
```

---

## Part B：任务进行中（每次实验/发现后填写）

### B1 实验记录模板

```markdown
## 实验 #{编号} — {简短描述}
时间：YYYY-MM-DD HH:MM
脚本/命令：{从终端 copy-paste}
目的：（验证什么假说？或探索什么问题？）

### 完整配置
| 参数 | 值 |
|------|----|
| M / T（token 数） | |
| hidden | |
| inter_dim | |
| E（expert 数） | |
| K（top-k） | |
| dtype | bf16 / fp8 / ... |
| preshuffle | True / False |
| is_shuffled | True / False |
| quant_type | no_quant / per_1x128 / ... |
| block_m | （若已知） |
| 其他关键参数 | |

### 结果
| 指标 | 值 |
|------|----|
| cos_sim | （精确到 6 位，如 0.999989） |
| TTFT | ms |
| TPOT | ms |
| 状态 | PASS / FAIL / CRASH |

（如果 CRASH）完整 crash message（直接 copy-paste，不 paraphrase）：
```
{原始错误信息}
```

### 代码来源（如有）
文件：{绝对路径}
行号：L{start}–L{end}
原文：
```python
{copy-paste 原文，不修改}
```

### 结论
{这个实验证明/否定了什么？}
状态：[CONFIRMED 假说 #{编号}] / [DISPROVED 假说 #{编号}] / [NEW FINDING]

### 下一步
{这个结果触发了什么？下一个实验/假说是什么？}
日志保存：/home/hanchang/project_*/logs/{文件名}
```

---

### B2 假说记录模板

```markdown
## 假说 #{编号} — {描述}
提出时间：YYYY-MM-DD
状态：[HYPOTHESIS]

基于：（什么观察/代码/逻辑导致了这个假说）
预期：（如果假说正确，实验 #{编号} 应该看到什么）
验证实验：#{实验编号}

--- 实验结束后填写 ---
实际结果：
状态更新：[CONFIRMED] / [DISPROVED]
理由：（实验数据 or 代码原文）

（如果 DISPROVED）
为什么假说是错的：
这说明了什么（对根因理解的修正）：
```

> **规则**：DISPROVED 的假说不能删除，必须保留完整记录。

---

### B3 代码发现记录模板

```markdown
## 代码发现 #{编号} — {描述}
时间：YYYY-MM-DD
文件：{绝对路径}
行号：L{start}–L{end}

原文（copy-paste，不修改）：
```python
{原文}
```

含义：{你的理解}
注意：{可能的误区或需要进一步验证的点}
关联假说：#{假说编号}
关联实验：#{实验编号}
```

---

### B4 Commit 记录模板

```markdown
## Commit #{编号}
时间：YYYY-MM-DD HH:MM
仓库：aiter / ATOM
从哪个目录操作：/home/hanchang/junlin12_repos/{aiter|atom}（必须！不从工作仓库 push）
Hash：{精确 hash，从 git log 复制}
分支：{PR 分支名}
内容（改了什么）：
  文件：
  行号：
  改动：
原因（为什么改）：
关联假说/实验：#{编号}

是否后续 revert：[ ] 否  [ ] 是
（如果 revert）
  Revert commit hash：
  Revert 原因：（被 canary 实验证伪？还是其他原因？）
  Revert 时间：
```

---

### B5 JIT 缓存操作记录

每次清理 JIT 缓存时记录：

```markdown
## JIT 缓存清理 #{编号}
时间：YYYY-MM-DD HH:MM
触发原因：（修改了哪个文件/submodule？）
清理命令（copy-paste）：
```bash
rm -f aiter/jit/module_moe_ck2stages_{variant}*.so
rm -rf aiter/jit/build/module_moe_ck2stages_{variant}*
```
清理前结果：cos_sim = {值}（stale .so 产生的错误结果）
清理后结果：cos_sim = {值}（重编译后的正确结果）
重编译耗时：{秒}
```

---

## Part C：任务结束时（写 summary 前检查）

逐条确认，未完成的补录：

### 数据完整性
- [ ] 所有实验都有完整配置记录（M, T, hidden, inter_dim, E, K, dtype, preshuffle, is_shuffled, quant_type）
- [ ] 每个 cos_sim/TTFT 值唯一对应一个实验配置（无"跨配置混用"）
- [ ] FAIL 和被证伪的假说有记录（不只有成功路径）
- [ ] 所有 commit hash 已从 git log 核实

### 代码质量
- [ ] 代码片段均为 copy-paste 原文（不从记忆重写）
- [ ] 运算符优先级正确（`(silu(g) * u) @ w.T`，不是 `silu(g) * u @ w.T`）
- [ ] chunk/split 返回 tuple，不能直接做矩阵运算
- [ ] Float tensor canary 用浮点哨兵值，不用整数
- [ ] Pseudocode 明确标注

### 日志持久化
- [ ] 所有推理日志保存在 `/home/hanchang/project_*/logs/`（不在 /tmp）
- [ ] 日志文件名包含时间戳或描述

### 边界清晰
- [ ] "未覆盖的场景"明确标注（如 tp=8 kernel 仅有对齐计算，无实测）
- [ ] 理论推断和实验验证分开（标注 `[理论推断]` vs `[实验验证]`）
- [ ] 每个结论说明了适用条件（"在 T=32 batch 下"，不写无条件全称）

---

## 快速参考：常见遗漏点

| 场景 | 容易遗漏的记录 |
|------|--------------|
| 实验 FAIL 后切换配置 | 切换前的 FAIL 配置和结果 |
| 修改代码后 PASS | 修改了哪一行，为什么这样改（不只写"改好了"） |
| 发现 stale .so | 清理前后的对比数据（cos_sim 从多少变成多少）|
| Bug 被 canary 证伪 | canary 值，放在哪里，跑了什么，结果是什么 |
| 两个 bug 互相掩盖 | 分开记录"Bug A 掩盖 Bug B"时的实验配置和数值 |
| 选了不同方案 | 被放弃的方案的失败原因（如 CK codegen KPerBlock=32 的 static_assert 错误） |
| 切换 preshuffle | 切换前后的配置差异（is_shuffled, block_m 如何变化） |

---

## 日志路径规范

```
/home/hanchang/project_{name}/
├── experiment_log.md      # 所有实验的完整记录
├── hypothesis_log.md      # 所有假说（含 DISPROVED）
├── commit_log.md          # 所有 commit hash 和内容
└── logs/
    ├── baseline_YYYYMMDD.log
    ├── exp{编号}_{描述}.log
    └── run_tp{N}_YYYYMMDD_HHMM.log
```

所有日志文件名包含足够信息，一年后也能知道这个日志是做什么实验的。
