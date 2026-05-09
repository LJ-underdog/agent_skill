# Template: dev-debug

**Type**: 标准开发 / 调试 / 复现 → 调研 → 修 → 验证（= 当前 generic flow，4 个特化模板里覆盖最广的一类）

**Use when**:
- 标准 debugging 任务（已有现象 / traceback，要定位根因 + 修复）
- 新功能开发（要在已有代码基础上加 feature，并保证不退化 baseline）
- bug 复现修复（用户给出复现步骤，需要先复现再修）
- 性能优化任务（已有 baseline 指标，需要调优 + 回归保证不慢）
- crash 调查（运行时崩溃，需先精确定位 traceback 再改）
- kernel / 算子改动 + correctness 回归（修改底层后要保证 numerics 一致）

**Don't use when**:
- 文档批量编辑 / 文档审计 → 用 `templates/doc-edit.md`
- 纯状态整理 / handoff / wave close / freeze → 用 `templates/status-consolidation.md`
- CI / log forensics / PR 失败排查（无本地复现条件、只有远程日志）→ 用 `templates/ci-investigation.md`
- 单 teammate 任务（直接单上下文做完，不要走 agent-team 框架）

---

## 1. Phase Plan（覆盖父类 SKILL.md 的"阶段结构"节）

```
Phase 0 ─串行─→ 决策门 ─→ Phase 1 ─并行─→ 决策门 ─→ Phase 2 ─串行─→ Phase 3
[baseline]       [分析]     [调查]           [审批]     [实施]           [验证]
```

### Phase 0 — Baseline / 起始状态确认（**串行，必须先跑，不可跳过**）
- 运行当前系统：跑现有 baseline 命令 / 触发 crash 复现 / 确认现象
- **crash 类任务**：必须精确定位 traceback（阶段 + 完整 message + 关键栈帧）；不允许只凭"症状描述"进 Phase 1
- **新功能 / 性能类任务**：先记录 baseline 指标具体数值（latency / accuracy / throughput）
- 输出：`DOC_DIR/baseline_result.md`（含命令、完整输出、关键指标 / traceback）
- 决策门：Phase 0 结果决定 Phase 1 调查重点（哪个组件、哪个层次、哪条假设优先）

### Phase 1 — 并行调查（**强制 ≥2 个 teammate 同 message 并行，建议上限 5**）
- 多假设同时铺开（每个 teammate 一条假设线索 / 一个组件 / 一个层次）
- 每个 teammate 1-3 个 item（避免一个 teammate 揽太多导致 context 爆）
- 每个调查型 item 必须输出 `proposed_fix_{item}.md`（含文件路径 + 行号 + 改动前后 + 来源 + 回归测试计划）
- 输出：`WORK_DIR/progress/teammate-{N}.md` + `WORK_DIR/proposed_fix_{item}.md`（每 item 独立文件，防并行写冲突）
- 违反「同 message ≥2 个并行」= 反模式（违反父类 §0.2）
- 决策门：lead 收齐所有 proposed_fix → 走「代码修改审批门」检查每个 fix → 通过的进 Phase 2

### Phase 2 — 串行实施（**审批后才能实施，串行执行避免冲突**）
- 每个修复必须 lead 在派单 prompt 里**明确批准**才能改代码
- 实施前必须 `git diff > before_fix_{item}.patch` 备份
- 实施 teammate 不自行跑完整测试（验证留给 Phase 3，避免边改边跑导致状态混乱）
- 多个 fix 串行实施：避免并行修同一文件 / 同一函数导致 conflict
- 输出：`WORK_DIR/progress/teammate-{N}.md` + `before_fix_{item}.patch` + 修改行号记录

### Phase 3 — 验证（**可并行，但必须同时跑两条**）
- **必须同时跑**：fix 路径验证 + baseline 回归（缺一不可）
- fix 路径：用最初的复现步骤 / 验收测试，确认 bug 已修
- baseline 回归：用 Phase 0 的 baseline 命令，确认未引入退化
- 输出：`DOC_DIR/04_verification.md`（含两条路径的命令 + 输出 + 指标对比）
- 反模式：只跑 fix 路径不跑 baseline 回归 = 不算修复完成

---

## 2. Recommended Teammate Count

**总人数：4-7**

| Phase | 角色 | 人数 | 说明 |
|-------|------|-----|------|
| Phase 0 | baseline runner | 1-2 | 单 baseline → 1 人；crash 复现 + traceback 解析 → 2 人 |
| Phase 1 | 调查 teammate | 2-4 | 每个 teammate 1-3 item；多假设并行；同 message 派出 |
| Phase 1 | reviewer | 1 | **必须含**：critical findings only，不修复但 raise 阻塞项 |
| Phase 2 | fix 实施 teammate | 1-2 | 串行；多 fix 时按依赖顺序；单 fix → 1 人 |
| Phase 3 | 验证 teammate | 2 | fix 路径验证 + baseline 回归并行 |

**必含 reviewer：是**（来源：MEMORY「每 wave 必须包含 reviewer + 文档员」）
- **reviewer 时机（dev-debug 特有）**：reviewer 在 Phase 1 同 message 派出，与调查 teammate **并行预审**（不是事后审）— dev-debug 选择并行预审是因为 Phase 1 调查 teammate 提的 proposed_fix 必须在 Phase 2 实施前被 reviewer 挑战，事后审会导致已实施代码被推翻成本高
- 对比其他 3 模板（doc-edit / status-consolidation / ci-investigation）reviewer 在主产出 Phase 之后**串行复审**（事后审）— 因为它们的产出是文档/报告，事后审不需要回滚源码
- raise 的 block finding 必须有闭环 task：(a) 接受 + 标注 / (b) 升级 fail / (c) 派 task 补证据
- **reviewer 妥协方案不可盲信**（来源：MEMORY 2026-05-09 §reviewer 妥协）：reviewer raise"致命"= task 方向修正信号，不要直接采纳其妥协方案

---

## 3. Specialized Teammate Prompt Body

下面这段 prompt body 直接复用父类 SKILL.md 「Teammate Prompt 模板」的 dev-debug 特化部分（含 BASELINE / KNOWN_FACTS / 验证顺序 / 调研 vs 执行 vs 验证）。lead instantiate 时把 `{占位符}` 替换为 TEAM_CONFIG.md 对应字段。

```
你是 {PROJECT} 团队的 **teammate-{N}**（角色：{ROLE}，例如 baseline-runner / investigator / fix-implementer / verifier / reviewer 之一）。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 背景

目标：{LEAD_FILLS_GOAL}
约束：{LEAD_FILLS_CONSTRAINTS}

环境：
{LEAD_FILLS_ENVIRONMENT}
  ← 从 TEAM_CONFIG.md 的 ENVIRONMENT 节展开，包含：
     - 运行前置命令（cd /tmp 等）
     - 资源设置（GPU、内存等）
     - 缓存清理命令
     - git push 路径和 author
     - 长时任务运行方式

BASELINE：
{LEAD_FILLS_BASELINE}
  ← 从 TEAM_CONFIG.md 的 BASELINE 节展开，含：
     - 当前已知通过的命令（含完整参数）
     - 预期指标（具体数值 + 容忍阈值）
     - baseline 日志路径

已知事实（无需重验）：
{LEAD_FILLS_KNOWN_FACTS}
  ← 从 TEAM_CONFIG.md 的 KNOWN_FACTS 节展开
     注意：只收录有代码行号或实验数据的已验证事实；"待验证"的放 TODO [调查] item

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

## 验证顺序（dev-debug 类任务核心方法论）

1. **最小复现**：先写最小脚本隔离问题，确认 bug 可单独复现（不要在完整 pipeline 里调试）
2. **中间值验证**：断言根因前，直接打印 / 检查中间状态（canary 或 assert）；不允许只凭"逻辑推断"提修复
3. **组件级验证**：验证单个组件正确性，不只看端到端结果（端到端 PASS 不代表每个组件都对）
4. **端到端验证**：最后跑完整流程，**同时跑 baseline 回归**

{TASK_SPECIFIC_VERIFICATION}
  ← 从 TEAM_CONFIG.md 的 TASK_SPECIFIC_VERIFICATION 节展开
     （任务特有的验证注意事项，如特定工具路径、特定测试命令、dump 中间值的位置）

---

## 调研 vs 执行 vs 验证 边界

| 当前 item 类型 | 你能做 | 你不能做 |
|--------------|-------|---------|
| `[调查]` | Read 源码 / Grep / 跑最小复现脚本 / 中间值 dump / 写 proposed_fix | 改源码（即使你觉得 fix 显然） |
| `[执行]` | Edit 源码（仅 lead 在 prompt 里明确批准的 fix） | 跑完整测试 / 改超出批准范围的代码 |
| `[验证]` | 跑 baseline 命令 + fix 路径命令 / 收集指标 | 改代码 / 改 fix 方案 |

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

写入 {WORK_DIR}/proposed_fix_{item编号}.md（**每个 item 独立文件，防并行写冲突**）：

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
4. **不自行运行完整测试**（验证留给 Phase 3 验证型 teammate）

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

## 4. Item Types

**沿用父类默认三类**：`[调查]` / `[执行]` / `[验证]`。dev-debug 不引入新 item 类型。

| 类型 | 说明 | 输出 | 允许的工具 |
|------|------|------|-----------|
| `[调查]` | 读代码 / 最小复现 / 中间值检测 / 提 fix 方案 | `progress/teammate-{N}.md` + `proposed_fix_{item}.md` | Read, Grep, Bash（只读或最小复现脚本） |
| `[执行]` | 修改代码 / 写文件（仅 lead 明确批准的 fix） | `progress/teammate-{N}.md` + `before_fix_{item}.patch` 备份 + 修改行号记录 | Edit, Bash（受批准范围约束） |
| `[验证]` | 完整测试矩阵：fix 路径 + baseline 回归 | `progress/teammate-{N}.md` + `DOC_DIR/04_verification.md` | Bash |

**关键边界**：
- `[调查]` teammate **绝不直接改源码**（即使觉得 fix 显然）；只写 proposed_fix
- `[执行]` teammate **只改 lead 明确批准范围的代码**；不自行扩展 fix 范围
- `[验证]` teammate **只跑测试不改代码**；指标不达标 → 标记 [!] 回 lead 而不是自行调试

---

## 5. Specialized Tools / Verification

### dev-debug 验证顺序（按此顺序逐层验证，不可跳级）

1. **最小复现**
   - 写最小脚本（< 50 行最佳）隔离问题
   - 不在完整 pipeline 里 print 调试 — 太多噪音
   - 输出：能稳定触发 bug / crash 的最小 repro 命令 + 输出

2. **中间值验证**
   - 在断言根因前，必须 dump 中间状态（canary value / assert / print）
   - **禁止"逻辑推断 → 直接提 fix"**（来源：父类反模式表「逻辑完整的根因直接提修复」）
   - 输出：中间值 vs 期望值的对比（数值 / shape / dtype）

3. **组件级验证**
   - 修复某组件后，**单独验证该组件正确性**（unit test / 单算子 dump）
   - 不能只看端到端通过 — 端到端可能因为多 bug 互相抵消而 PASS
   - 输出：组件级输入 / 输出 dump

4. **端到端验证 + baseline 回归（同时跑）**
   - fix 路径：原始复现命令 → 验证现象消失 / 指标达标
   - baseline 回归：Phase 0 的 baseline 命令 → 验证未退化
   - **两条都要跑**，缺 baseline 回归 = 不算修复完成

### 工具优先级
- 中间值 dump：直接在源码加 `print(f"[CANARY-{tag}] {value=}")` 而不是用 debugger（无副作用，便于 grep）
- 跑长时编译 / 长时测试：`nohup` + 轮询监控（**不**用后台任务，可能被 timeout kill — 来源：父类反模式表）
- 缓存清理：构建产物 + 生成文件**缺一不可**清理（编译缓存未清 = 测试结果不可信，来源：父类反模式表「编译/构建缓存未完全清理就测试」）

---

## 6. Specialized Antipatterns

本节列 dev-debug 独有反模式，不重复父类 §反模式表通用条。


以下条目**从父类 §反模式表挪入此处**（dev-debug 特化，T5 之后会从父类清掉）：

| 反模式 | 正确做法 |
|--------|---------|
| 编译/构建缓存未完全清理就测试 | 清理所有缓存文件（构建产物 + 生成文件缺一不可） |
| 用后台任务跑长时编译 | nohup + 轮询监控（后台任务可能被 timeout kill） |
| 单元测试 PASS 就认为生产路径正确 | 显式用生产路径配置验证 |
| "逻辑完整"的根因直接提修复，跳过最小复现 / 中间值检测 | 必须按「最小复现 → 中间值验证 → 组件级 → 端到端」逐层走 |
| crash → 直接改代码 | Phase 0 先精确定位 traceback（阶段 + 完整 message + 关键栈帧） |
| 未覆盖 baseline 回归就认为修复完成 | Phase 3 始终同时跑 fix 路径 + baseline 回归 |
| 并行 teammate 共用同一个 proposed_fix.md | 每个 item 独立文件 `proposed_fix_{item}.md`（防并行写冲突） |

**新增 dev-debug 特化反模式**（来源：MEMORY「Debugging task 方法论」/ MEMORY「Reviewer 妥协方案不可盲信」）：

| 反模式 | 正确做法 |
|--------|---------|
| 在"症状已知 + 推断 mechanism"上跳到打补丁让用户选 (a)/(b)/(c) | 必须 layer-by-layer / op-by-op 实验定位根因，dump 中间值对照参考路径；列方案前根因必须**实验定位**（不是推断） |
| teammate 给"X 因为 Y"的因果链未做实验直接被 lead 采纳 | lead 区分「实验数据支撑」vs「推断」；推断必须再派 teammate 做实验验证 |
| reviewer raise 致命问题（如 baseline 跑错 model）时直接采纳其妥协方案（10% sanity / soft-PASS） | reviewer raise"致命" = task 方向修正信号，应**修 baseline / 重派正确 task**，或回 lead/用户裁决，而不是顺其妥协方案 |
| 实施 teammate 边改边跑完整测试 | 实施只改不跑；验证统一交 Phase 3 的 [验证] teammate（避免边改边跑导致状态混乱） |
| 一个 teammate 揽 4+ items 导致 context 爆 | 单 teammate 最多 3 item；超出拆给下一个 teammate |

---

## 模板继承说明

本模板**继承**父类 SKILL.md 的以下节，不在此重复：
- §0 铁则（Lead 不执行 + 必须并行）
- §继承模型 / §与 project-summary 的集成
- §Workflow 0 / 1 / 2 / 3
- §Lead 行为规则（含代码修改审批门 / 存档规律）
- §TODO List 格式
- §文档管理规则
- §反模式表的通用条目（除上面挪入本模板的 dev-debug 特化条之外）
- §启动检查清单
- §Changelog

本模板**覆盖**父类的：
- §阶段结构（本模板 §1 Phase Plan 即覆盖版）
- §Teammate Prompt 模板的 dev-debug 特化部分（本模板 §3）
- §验证顺序（本模板 §5）
- §Item 类型说明（本模板 §4 沿用父类，无变化但显式列出边界）
