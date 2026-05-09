# Template: ci-investigation

**Type**: CI / GitHub Actions log forensics / PR 失败 root cause 排查（**只调查不修复**）

**Use when**:
- GitHub Actions / 任意 CI workflow 失败，需要从 raw log 找 root cause
- 需要确认某 commit 是否在某分支上（branch_commits 实证）
- 跨仓 PR 依赖追踪（如 `aiter` PR 依赖 `composable_kernel` 子模块 SHA 已镜像到 develop）
- `check-signal` exit 78 等"短路信号"需要追溯到真正的上游失败 workflow
- PR / Actions 页面图标看不清（WebFetch 丢图标），需要换工具拿真实状态

**Don't use when**:
- 已知 root cause 要修源码 → 转 **dev-debug** 模板的 Phase 2/3
- 不是 CI 失败而是本地测试失败 → **dev-debug**
- 只是要给 PR 加一个新 commit / retrigger CI / 打 reviewer ping → 不走 agent-team，单上下文做完
- 失败已被其他 wave 调查清楚，只缺一行 patch → lead 5–15 行 trivial patch 例外（§0.1）

---

## 1. Phase Plan（覆盖父类 SKILL.md 的"阶段结构"节）

CI 调查任务**没有 fix Phase**——fix 路径选择交给调用方 lead 与用户。本模板只走"取证 → 出报告"。

| Phase | 串行/并行 | Teammate 数 | 产出物 |
|---|---|---|---|
| **Phase 0：拉日志** | 串行 | 1（log fetcher） | `/tmp/ci-job-<ID>.txt`（raw log）+ `DOC_DIR/00_log_inventory.md`（含 source URL / size / line count） |
| **Phase 1：并行分析** | **并行 ≥2**（铁则 §0.2） | 2（log analyzer + dependency verifier） | `DOC_DIR/01_log_analysis.md`（fail step + exit code + 关键 stack）+ `DOC_DIR/02_dependency_audit.md`（commit 分支归属 / 跨仓同步） |
| **Phase 2：报告** | 串行 | 1（report writer） | `DOC_DIR/REPORT.md`（TL;DR + 完整证据链 + fix path A/B/C 表 + 用户待决策项） |
| **Phase R：评审**（**必须**） | 串行 | 1（reviewer） | `DOC_DIR/03_review.md`（raise findings，**不修复**） |

**Phase 0 不可跳过**：log 必须先落盘，所有后续 teammate 都引用同一份 `/tmp/ci-job-<ID>.txt`，避免重复拉、避免 WebFetch 丢内容。

**为什么没有 Phase 3 验证**：调查类任务的"验证"= 证据链交叉对照（log + branch_commits + 上游 PR），由 reviewer 在 Phase R 完成；不跑代码、不 retrigger CI。

---

## 2. Recommended Teammate Count

- **总人数**：3–4（最小可行 3，含 reviewer 4）
- **角色分配**：
  | 角色 | 数 | 责任 |
  |---|---|---|
  | log fetcher | 1 | `curl` Azure blob URL → `/tmp/`，写 inventory |
  | log analyzer | 1 | 找 fail step / exit code / 真正报错栈，区分短路信号 vs root cause |
  | dependency verifier | 1 | 用 `branch_commits` / `search?type=commits` 验证上下游 commit 归属 |
  | report writer | 1 | 汇总 → REPORT.md（含 fix path 选项表，**不指定**采纳哪条） |
  | reviewer（可选） | 1 | 检查证据链是否闭环，raise 推断未实证项 |
- **必含 reviewer**：✅ 是（参考父类 MEMORY 与 SKILL.md §0）— **强制 4 人最小配置**，reviewer 必须独立于 report writer，禁止 self-review 后门
- **reviewer 时机**：所有 4 模板默认 reviewer 在主产出 Phase 之后**串行复审**（事后审）；仅 dev-debug 模板特殊安排为 Phase 1 并行预审。本模板（ci-investigation）reviewer 在 Phase 2 报告完成后串行

---

## 3. Specialized Teammate Prompt Body

替换父类 Teammate Prompt 模板里的 "BASELINE / 验证顺序 / 调研 vs 执行" 节为以下特化体（外层用 4 反引号包裹，避免内部嵌套提前闭合）。其余结构（编号 / WORK_DIR / DOC_DIR / Context 保护规则 / 收尾流程）继承父类不变。

````
你是 {PROJECT} 团队的 **teammate-{N}**（角色：{ROLE}）。

WORK_DIR = {WORK_DIR}
DOC_DIR  = {DOC_DIR}

## 任务
{ITEM_LIST}（含 Phase 编号，参考 todo.md）

## 调查对象
- PR / workflow URL：{PR_URL}
- 失败 job URL（用户从 Actions "Download log" 复制）：{JOB_LOG_URL}
- 涉及仓库：{REPO_LIST}（含上下游依赖关系）

---

## 红线（特化，覆盖父类"调研 vs 执行"节）

1. **只调查 + 出报告**。**禁止**任何修改性动作：
   - ❌ 不改 PR 任何文件
   - ❌ 不 push 任何 commit / branch
   - ❌ 不 retrigger CI / 不 dispatch workflow
   - ❌ 不在 PR 评论 / approve / request changes
   - ❌ 不动 `.github/workflows/*.yml`
2. **结论必须实证**。看到 `check-signal` exit 78、"upstream skipped"、"dependency failed" 等**短路信号**时：
   - 必须追溯到**真正的失败 workflow + step + exit code**才算 root cause
   - 短路信号本身**不是** root cause（exit 78 = 上游 dependency workflow 没过的传播信号）
3. **不跨 wave 派衍生 teammate**（你是 teammate，不是 lead）。
4. **不动他人 progress / DOC_DIR 文件**（写自己的 `progress/teammate-{N}.md` + 自己的 `DOC_DIR/0X_*.md`）。

---

## 输出文件 schema

### 角色 = log fetcher → `DOC_DIR/00_log_inventory.md`

| 字段 | 内容 |
|---|---|
| Source URL | 用户提供的 Azure blob URL（原文，不删 token） |
| Local path | `/tmp/ci-job-<ID>.txt` |
| Size | bytes |
| Line count | `wc -l` |
| First/Last 3 lines | quote |
| 拉取命令 | 原文（含 `curl -sS -o ...`） |

### 角色 = log analyzer → `DOC_DIR/01_log_analysis.md`

```
## TL;DR
{1 句话：哪一步失败 + 真正 exit code（非短路信号）}

## 失败 Step
- Step name: {GHA step 名}
- Step index in job: #N
- Exit code: {数字}
- Log line range: L{start}-L{end}（指 /tmp/ci-job-<ID>.txt）
- 关键 stack / error message（原文 quote ≤30 行）

## 短路信号过滤
- [ ] 已确认非 `check-signal` exit 78 短路传播
- [ ] 已确认非 "upstream skipped"
- 若是短路信号 → 上游真正失败 workflow URL: {URL}

## 证据来源
- raw log: /tmp/ci-job-<ID>.txt L{XX-YY}
- 不引用 PR / Actions 页面（图标信息不可靠，见 §5）
```

### 角色 = dependency verifier → `DOC_DIR/02_dependency_audit.md`

```
## 待验证依赖
| 依赖项 | 期望状态 | 实证 URL | 实测状态 | 结论 |
|---|---|---|---|---|
| {repo}@{SHA} 在 develop | 是 | https://github.com/<org>/<repo>/branch_commits/<SHA> | {fetched 内容摘要} | ✅/❌ |
| 上游 PR #NNNN merged 后镜像到 mirror repo | 是 | search?q=<title>&type=commits | {结果} | ✅/❌ |

## 跨仓同步证据（如适用）
- 上游 PR: {URL} merged at {date}
- 下游 mirror commit: {SHA or "未找到"}
- bot/同步机制: {如 assistant-librarian[bot]}
- 延迟 / 漏镜像: {Y/N + 证据}
```

### 角色 = reviewer → `DOC_DIR/03_review.md`

```
# CI Investigation Review

## R-{NN} {一句话标题}
- **severity**：[block] / [warn] / [nit]
- **类型**：[证据链断裂] / [短路信号未追溯] / [跨仓依赖未实证] / [推断未实证] / [报告漏 fix path] / [其他]
- **涉及文件**：{绝对路径，如 01_log_analysis.md / 02_dependency_audit.md / REPORT.md}
- **证据**：（必须有 raw log 行号 / WebFetch source URL / branch_commits URL）
- **不给妥协方案**，只描述问题（参考 MEMORY: reviewer 妥协方案不可盲信）
```

### 角色 = report writer → `DOC_DIR/REPORT.md`

```
# CI Investigation Report — {PR / workflow ID}

## TL;DR（≤3 行）
{root cause 一句话 + 推荐 fix path 编号}

## 完整证据链
1. 失败 job: {URL}（raw log: /tmp/ci-job-<ID>.txt）
2. 失败 step: {name} exit {code} @ L{XX-YY}
3. 真正 root cause（非短路信号）: {描述}
4. 依赖审计: 见 02_dependency_audit.md
5. 所有 source URL 列表（branch_commits / search / blob log）

## Fix Path 选项（不指定采纳）
| ID | 路径 | 工作量 | 风险 | 推荐度 |
|---|---|---|---|---|
| A | {如：等上游 mirror bot 重跑} | 0（被动等） | 不确定何时镜像 | ★★ |
| B | {如：手动 cherry-pick + push 到 mirror develop} | 中（需要 mirror 写权限） | 可能与 bot 冲突 | ★★★ |
| C | {如：改 aiter check_deps.sh 跳过该 commit} | 高（改 CI 配置） | 影响其他 PR | ★ |

## 用户待决策项
- [ ] 采纳哪条 fix path？（A/B/C）
- [ ] 是否需要联系 mirror bot owner？
- [ ] 是否在 PR 留评论说明等待原因？

## Do-NOT-Redo（接手者参考）
- 已确认 X / 已排除 Y / 已拉的 log path
```

---

（其余流程：Context 保护规则 / 卡住处理 / 收尾流程 → 沿用父类 SKILL.md）
````

---

## 4. Item Types

本模板覆盖父类默认 `[调查]` / `[执行]` / `[验证]` — 新增 4 类（无 `[执行]`，本模板禁止任何修改性动作）。


新增 4 类（替代父类的 `[调查]` / `[执行]` / `[验证]`，因为 ci-investigation 没有"执行"）：

| 类型 | 说明 | 输出 | 允许的工具 |
|---|---|---|---|
| `[拉日志]` | 从 Azure blob URL `curl` raw log 落盘 + 写 inventory | `00_log_inventory.md` + `/tmp/ci-job-*.txt` | Bash（curl, wc）, Read |
| `[分析]` | 读 raw log 找 fail step / exit code / 关键 stack | `01_log_analysis.md` | Read, Grep |
| `[实证]` | 用 web 工具查 commit 分支归属 / 跨仓同步状态 | `02_dependency_audit.md` | WebFetch（限定 URL pattern：`branch_commits/<SHA>`、`search?type=commits`） |
| `[报告]` | 汇总证据链 + 列 fix path 选项 + 用户待决策项 | `REPORT.md` | Write, Read |

**注**：本模板**没有** `[执行]` item 类型（红线禁止修改性动作）。如调用方 lead 看完报告决定走某 fix path，应另起 wave 用 `dev-debug` 模板。

---

## 5. Specialized Tools / Verification

**本节是 ci-investigation 模板最关键节**：CI 调查结论的可信度取决于 web 工具选择是否正确（详见 §5.1 优先级表）。


### 5.1 GitHub Actions 调试 web 工具优先级表

参考 MEMORY.md "调试 GitHub Actions 失败的 web 工具优先级（2026-05-09 实证）" 与 fp8_tp4_repro.md 同节。

| 数据需求 | 推荐工具 | 用法 | 替代 / 禁用 |
|---|---|---|---|
| Job raw log | `curl` Azure blob URL → `/tmp/` → Read | 用户从 Actions 页 "Download log raw" 复制 URL；`curl -sS "<URL>" -o /tmp/ci-job-<ID>.txt` | ❌ WebFetch（markdown 化会吃掉 log 细节，stack trace 缩进丢失） |
| PR / Actions 页面 CI 状态（pass/fail 图标） | **不要试** WebFetch | — | 让用户截图 / 复制具体失败 job 的 raw log URL；侧栏 badge 数字 = 该 workflow 失败 job 数（唯一可用线索） |
| Commit 分支归属（某 SHA 是否在 develop） | WebFetch `https://github.com/<org>/<repo>/branch_commits/<SHA>` | prompt: "列出页面上所有分支名 + 是否包含该 commit" | ✅ 可信 |
| Commit search（按 message / title 找镜像 commit） | WebFetch `https://github.com/<org>/<repo>/search?q=<term>&type=commits` | prompt: "列出 top 5 commit SHA + author + date + title" | ✅ 可信 |
| GitHub REST API（list checks / get logs / list runs） | unauth = 60 req/h rate limit；**没 PAT 就放弃** | — | ❌ 不要重试硬撞 rate limit；SSH key **不能**当 PAT 用 |
| `gh` CLI | 当前环境**未安装**（实证 2026-05-09），不要 try | — | 用 `curl` + WebFetch 组合替代 |

### 5.2 验证顺序（覆盖父类"验证顺序"节，CI 调查特化）

1. **Log 落盘优先**：先 `curl` 拉 raw log 到 `/tmp/`，再做任何分析（不要边 WebFetch 边推断）
2. **过滤短路信号**：`grep -n "exit 78\|check-signal\|upstream skipped\|dependency failed\|skipped"` → 任何命中都不能算 root cause，必须追溯
3. **跨仓依赖必须双向证**：上游 PR merged ≠ 下游 mirror 已同步；必须查 `branch_commits/<SHA>` 实证
4. **证据链原文 quote**：报告里所有 "因为…所以…" 必须附 raw log 行号或 WebFetch source URL
5. **不 retrigger / 不重跑**：CI 失败的可复现性已由 raw log 固化，不需要重跑验证

### 5.3 必备命令片段

```bash
# Phase 0：拉 log
curl -sS "<AZURE_BLOB_URL>" -o /tmp/ci-job-<ID>.txt
wc -l /tmp/ci-job-<ID>.txt
head -3 /tmp/ci-job-<ID>.txt
tail -3 /tmp/ci-job-<ID>.txt

# Phase 1 [分析]：找失败 step（用 Grep 工具，非 bash grep）
# pattern: "##\[error\]|FAILED|exit code|Process completed with exit code"

# Phase 1 [实证]：commit 在不在 develop
# WebFetch URL: https://github.com/<org>/<repo>/branch_commits/<SHA>
# prompt: "列出该 commit 出现在哪些分支（branch list），develop 是否在其中"
```

---

## 6. Specialized Antipatterns

本节列 ci-investigation 独有反模式，**不重复**父类 §反模式表。


| 反模式 | 正确做法 | 来源 / 实证 |
|---|---|---|
| WebFetch 看 PR check 状态期望拿 pass/fail 图标 | 让用户复制具体失败 job 的 raw log URL；只看侧栏 badge 数字 | fp8_tp4_repro.md 2026-05-09 PR2887 实证 |
| 推断未实证的 commit 归属（"应该在 develop 上"） | WebFetch `branch_commits/<SHA>` 实证 | MEMORY.md 调试节 |
| 看到 `check-signal` exit 78 直接报告"workflow X failed" | 追溯到真正失败的上游 dependency workflow + step + exit code | fp8_tp4_repro.md PR2887 章节 |
| 跨仓依赖只查上游 PR merged 状态 | 必须同时查下游 mirror repo 是否已同步该 SHA（bot 可能延迟或漏） | fp8_tp4_repro.md "ROCm/composable_kernel 仓库架构" 节 |
| 调用 `gh` 命令未先确认环境是否安装 | 当前环境无 `gh`；直接用 `curl` + WebFetch | 2026-05-09 实证 |
| 用 GitHub REST API unauth 硬撞 rate limit 重试 | 60 req/h 撞限就放弃，改换 WebFetch 公开页面或让用户手动提供数据 | MEMORY.md |
| WebFetch raw log Azure blob URL 期望拿到完整内容 | markdown 化丢失，必须用 `curl` 落盘到 `/tmp/` 再 Read | fp8_tp4_repro.md 同节 |
| Report 里"推荐 fix path X"二选一直接帮用户决策 | 列 A/B/C 表 + 标推荐度 + 留"用户待决策项"清单，不替用户拍板 | 父类 §0.1 边界 |

---

## 附录：与父类 SKILL.md 的差异速查

| 父类章节 | 本模板处理 |
|---|---|
| §0 铁则（Lead 不执行 + 必须并行） | **保留**，调用方 lead 仍受约束 |
| §继承模型 | **保留** |
| §阶段结构（Phase 0-3） | **覆盖**：Phase 0 拉日志 / Phase 1 并行分析 / Phase 2 报告 / **无 Phase 3** |
| §Item 类型（[调查]/[执行]/[验证]） | **覆盖**：[拉日志]/[分析]/[实证]/[报告]，**无 [执行]** |
| §代码修改审批门 | **不适用**（本模板禁止任何代码修改） |
| §验证顺序（debugging 类） | **覆盖**：见 §5.2 CI 调查特化顺序 |
| §反模式表 | **追加**：本模板 §6 列 8 条 ci-investigation 独有反模式 |
| §Teammate Prompt 模板 | **替换** "BASELINE / 验证顺序 / 调研 vs 执行" 节为本模板 §3 |
