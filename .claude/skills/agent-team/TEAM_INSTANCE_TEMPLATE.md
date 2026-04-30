# Team Config: {TASK_NAME}

# 继承自：agent_skill/.claude/skills/agent-team/SKILL.md
# 继承兄弟类（如有）：project_{related_name}/TEAM_CONFIG.md
# 创建日期：{YYYY-MM-DD}
# 状态：[ACTIVE / COMPLETE / PROMOTING]

---

## ⚠️ 父类铁则（不可覆盖，违反即取消本次 agent-team）

本子类**必须**遵守父类 SKILL.md `## 0. 铁则`：

- **§0.1 Lead 不执行任何具体工作** — Lead 只做：决策 / 写协调文档 / 派 teammate / 读状态。任何调研/验证/执行类动作必须派 teammate
- **§0.2 必须并行** — Phase 1 同 message 派 ≥2 个 teammate；串行派单 = 反模式

子类不得在任何字段（CONSTRAINTS / ENVIRONMENT / 反模式扩展等）写"本任务允许 lead 自己跑 X"或"本任务串行派"绕过铁则；如确需串行，须先取得用户明确 override 并记入 `## 任务特化 — 反模式扩展`。

---

## 基础配置

```
PROJECT:    {简短名称，如 fp8-tp2-debug}
WORK_DIR:   {持久路径，禁止临时目录，如 /home/hanchang/project_{name}/}
DOC_DIR:    {同 WORK_DIR 或子目录}
LOG_DIR:    {DOC_DIR/logs/}
CODE_ROOTS: {相关仓库路径列表}
GOAL:       {一句话，可量化}
```

---

## CONSTRAINTS

<!--
推导来源：
- CLAUDE.md 中的规则
- 代码注释中的 # DO NOT MODIFY / @support_torch_compile 等装饰器
- MEMORY.md 中的约束条目
- 用户 Q3
-->

- {约束 1}
- {约束 2}

---

## ENVIRONMENT

<!--
推导来源：
- CLAUDE.md 的运行说明
- MEMORY.md 的环境配置
- 兄弟类 TEAM_CONFIG.md 的 ENVIRONMENT（如有）

这是和父类 Teammate Prompt 中 {ENVIRONMENT} 占位符对接的核心字段。
包含以下类别（按实际情况填写，不相关的删除）：
-->

```
# 运行前置（如特殊 cd 要求、virtualenv 激活、环境变量）
{如：cd /tmp && /opt/venv/bin/python
 原因：{说明为什么需要这个前置步骤}}

# 资源设置（GPU、内存、并发限制）
{如：CUDA_VISIBLE_DEVICES=0,1（避开 GPU5，~700ms/tensor 硬件异常）}

# 构建缓存清理（修改代码后必须执行）
{如：rm -rf /root/.cache/atom/*}
{说明：为什么需要清理，不清理会有什么问题}

# 编译缓存清理（如适用）
{如：rm -f {path}/*.so && rm -rf {path}/build/*}
{重要：必须同时删两处，只删其一无效}

# git push 配置
{如：从 /home/hanchang/junlin12_repos/{repo} 执行}
{author：{name} <{email}>}

# 长时任务运行方式（>5min 的编译/推理）
nohup {CMD} > {LOG_DIR}/build_{task}.log 2>&1 &
while kill -0 $! 2>/dev/null; do sleep 30; echo "..."; done
{不用 run_in_background=True，会被 timeout kill}
```

---

## BASELINE

<!--
推导来源：
- logs/ 目录中的历史日志
- 已有的测试脚本输出格式
- project-summary TASK_TEMPLATE.md 的 Baseline 节
- 用户 Q2

BASELINE 是所有 proposed_fix 的回归测试基准。
每个 proposed_fix 必须说明如何验证 baseline 不退化。
-->

```bash
# 标准运行命令（copy-paste，可直接运行）
{完整命令}
```

预期结果：
```
{metric_1} = {值}（如 PASS / cos_sim=0.999989 / P99<100ms）
{metric_2} = {值}
```

---

## KNOWN_FACTS

<!--
推导来源：
- recall knowledge index（直接提取已验证条目）
- MEMORY.md 已验证内容
- 兄弟类的 KNOWN_FACTS（标注"继承自 {X}"）

规则：只写有实验证据或代码来源的事实，推断不在这里。
-->

| # | 事实 | 来源 | 继承自 |
|---|------|------|-------|
| F1 | {描述} | recall/{文件} / 代码 {文件} L{行} | — / {兄弟类名} |
| F2 | ... | ... | ... |

---

## TASK_SPECIFIC_VERIFICATION

<!--
填写本任务特有的验证注意事项，对应 Teammate Prompt 中的 {TASK_SPECIFIC_VERIFICATION}。
父类已有通用验证顺序（最小复现→中间值→组件级→端到端），这里只写本任务额外的注意点。

示例（ML kernel 任务）：
- op_test 走 preshuffle_on，生产路径走 preshuffle_off，两者结果可能不同
- cos_sim > 0.9999 认为正确（bf16 精度上限），单层 PASS 不等于端到端 PASS

示例（网络任务）：
- 压测需要预热 30s 再采集数据
- 高并发测试必须在 staging 环境，不在 production

填写后该节内容会展开进 Teammate Prompt。
-->

{本任务特有的验证注意事项，不填则省略该节}

---

## 初始 TODO List

<!--
Phase 0 必须是"先跑 baseline，记录当前状态"。
Phase 1 的内容依据 Phase 0 的结果决定（crash 类型、失败阶段等）。
已知的调查方向可以预填，但 Phase 1 在 Phase 0 完成后才正式启动。
-->

```markdown
# TODO - {PROJECT}

## Phase 0（串行，必须先跑）
- [ ] #000 [验证] 运行 baseline → 记录 crash/通过结果

## Phase 1（并行调查，#000 结果决定重点）
- [ ] #A01 [调查] {已知调查方向 A} [depends: #000]
- [ ] #B01 [调查] {已知调查方向 B，若 crash 在 X 阶段} [depends: #000]

## Phase 2（执行，审批后）
- [ ] #C01 [执行] 实施 fix（depends: #A02 批准）

## Phase 3（验证）
- [ ] #V01 [验证] fix 路径（预期：{指标} {阈值}）
- [ ] #V02 [验证] baseline 回归（预期：与 baseline 一致）

## In Progress
## Done
## Blocked
```

---

## 任务特化 — 反模式扩展

<!--
父类反模式表是通用的。这里写本任务特有的反模式（通常是踩坑后追加）。
任务结束时判断是否 promote 到父类。
-->

| 反模式 | 正确做法 | Promote 候选 |
|--------|---------|-------------|
| {本任务特有坑} | {正确做法} | [ ] 是  [ ] 否 |

---

## Promotion Candidates

<!--
PC 模板（遇到触发场景时 copy 后填写）：

### [PC-{N}] {简短描述}
发现时间：YYYY-MM-DD
触发场景：{从父类 Workflow 2 触发条件表选择}
来源：teammate-{N} progress / lead review

**内容**（用父类可直接使用的措辞）：
{规则/条目}

**为什么 promote**：
{本任务具体表现} + {为什么对其他任务也有价值}

**建议加入父类位置**：
[ ] SKILL.md — 反模式表
[ ] SKILL.md — 审批门
[ ] SKILL.md — Item 类型说明
[ ] SKILL.md — 阶段结构
[ ] TEAM_INSTANCE_TEMPLATE.md — 环境模板示例
[ ] 其他：{位置}

**置信度**：[ ] 高  [ ] 中  [ ] 低
**Review 结果**：[ ] 待 review  [ ] 接受  [ ] 修改→{内容}  [ ] 拒绝→{原因}
-->

（任务进行中追加，Lead 主动识别）
