# Skills Index — 工具技能生态系统

所有可调用的 skill 及其关系。

---

## 技能清单

| Skill | 触发词 | 用途 |
|-------|--------|------|
| [agent-team](./claude/skills/agent-team/SKILL.md) | "start agent team", "用 agent team" | 将复杂任务分解给多个 Claude 子 agent 并行执行 |
| [project-summary](./claude/skills/project-summary/SKILL.md) | "write project summary", "做任务总结" | 为工程任务生成可验证的文档记录 |
| [dev-pipeline](./claude/skills/dev-pipeline/SKILL.md) | "do a full pipeline", "dev pipeline" | 结构化开发流程：brainstorm → spec → plan → execute |

---

## 何时用哪个？

```
新任务开始
  │
  ├─ 任务简单（<15 tool calls，高度串行）
  │       → 直接单 Claude 完成，不需要任何 skill
  │
  ├─ 任务复杂（>30 tool calls，可并行假设，明确调查→执行→验证流程）
  │       → agent-team（执行）+ project-summary（记录）同时启动
  │
  ├─ 新功能开发，需要 spec first
  │       → dev-pipeline
  │
  └─ 任务结束后，需要整理记录
          → project-summary（仅文档阶段）
```

---

## 组合使用：agent-team + project-summary

这是最常见的组合。两个 skill **共享同一套任务配置**：

```
project_{name}/
├── TASK_TEMPLATE.md    ← project-summary 子类实例
│                          包含：参数 schema、指标 schema、baseline、已知事实
│
└── TEAM_CONFIG.md      ← agent-team 子类实例
                           从 TASK_TEMPLATE.md 引用共享字段
                           额外包含：ENVIRONMENT、todo list、teammate prompts
```

**启动顺序**：

```
Step 1: 先 instantiate project-summary
  → 生成 TASK_TEMPLATE.md（定义参数 schema、指标、已知事实）
  → 这是整个任务的"知识基础"

Step 2: 再 instantiate agent-team
  → 生成 TEAM_CONFIG.md
  → KNOWN_FACTS 从 TASK_TEMPLATE.md 直接引用（不重复填写）
  → BASELINE 从 TASK_TEMPLATE.md 引用
  → ENVIRONMENT 是 agent-team 特有的（project-summary 不需要）

Step 3: agent-team 运行
  → teammate progress 文件 = experiment_log（project-summary 的记录）
  → 不需要另外维护 experiment_log.md

Step 4: 任务结束
  → 用 project-summary 的写作结构整理成 01-04 文档
  → 执行两个 skill 各自的 Promote workflow
```

**字段映射**（避免重复填写）：

| 字段 | 填写位置 | 引用方 |
|------|---------|-------|
| 参数 Schema / 指标 | TASK_TEMPLATE.md | TEAM_CONFIG.md（参考，不重复） |
| BASELINE | TASK_TEMPLATE.md | TEAM_CONFIG.md 直接引用 |
| KNOWN_FACTS | TASK_TEMPLATE.md | TEAM_CONFIG.md 直接引用 |
| CONSTRAINTS | TASK_TEMPLATE.md | TEAM_CONFIG.md 直接引用 |
| ENVIRONMENT | TEAM_CONFIG.md | project-summary 不需要此字段 |
| TODO list | TEAM_CONFIG.md | project-summary 不需要此字段 |
| Promotion Candidates | 各自维护 | 分别 promote 到各自父类 |

---

## 继承层次

```
agent-team/SKILL.md (父类)
  └── agent-team/TEAM_INSTANCE_TEMPLATE.md (子类骨架)
        └── project_{name}/TEAM_CONFIG.md (子类实例)

project-summary/SKILL.md (父类)
  └── project-summary/INSTANCE_TEMPLATE.md (子类骨架)
        └── project_{name}/TASK_TEMPLATE.md (子类实例)

两个子类实例通过共享字段连接：
  TASK_TEMPLATE.md ──(提供 KNOWN_FACTS/BASELINE/CONSTRAINTS)──→ TEAM_CONFIG.md
```

---

## 文件位置

```
agent_skill/
├── SKILLS_INDEX.md                              ← 本文件
├── agent_team_template.md                       ← 旧版参考文档（已被 skills/ 取代）
└── .claude/skills/
    ├── agent-team/
    │   ├── SKILL.md                             ← 父类（可调用）
    │   └── TEAM_INSTANCE_TEMPLATE.md            ← 子类骨架
    ├── project-summary/
    │   ├── SKILL.md                             ← 父类（可调用）
    │   ├── INSTANCE_TEMPLATE.md                 ← 子类骨架
    │   └── PRE_TASK_GUIDE.md                    ← 配套参考手册
    └── dev-pipeline/
        └── SKILL.md                             ← 父类（可调用）
```
