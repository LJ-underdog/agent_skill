# agent_skill

可复用的 Claude Code Skills 集合，面向 AITER / CK (Composable Kernel) / ROCm GPU kernel 开发工作流。

---

## 目录结构

```
agent_skill/
├── CLAUDE.md                            # 通用工作原则（输出语言、答案验证、ROCm 文档规范）
├── README.md                            # 本文件
├── SKILLS_INDEX.md                      # 全部 skill 的索引与组合用法
├── agent_team_template.md               # 旧版参考文档（已被 .claude/skills/ 取代）
├── rocm-ref.2026.03.25.gz               # ROCm 参考文档（ISA、指令集、硬件规格）
├── docs/                                # 环境搭建 / 复现记录
│   ├── ROCM-21707-repro.md
│   └── claude-setup-linux.md
├── rocm-kernel-design/                  # ROCm kernel 设计与调优（注意：不在 .claude/skills/ 下）
│   └── SKILL.md
└── .claude/
    └── skills/
        ├── agent-team/                  # 多 agent 团队：调查 → 提案 → 审批 → 执行 → 验证
        │   ├── SKILL.md
        │   ├── TEAM_INSTANCE_TEMPLATE.md
        │   └── templates/               # 4 个特化模板 + roles/ 角色库
        ├── dev-pipeline/                # 全流程开发 pipeline
        │   └── SKILL.md
        ├── llm-usage/                   # AMD LLM Gateway token 用量 / 费用查询
        │   └── SKILL.md
        ├── project-summary/             # 工程任务总结文档
        │   └── SKILL.md
        └── sync-ck-fmha/                # CK FMHA API 同步
            └── SKILL.md
```

---

## Skills

### `dev-pipeline` — 全流程开发 Pipeline

**触发词**：`full pipeline`、`dev pipeline`、`spec and plan for`、`start pipeline`

从需求到执行的完整 7 步工作流：

| 步骤 | 内容 | 方式 |
|------|------|------|
| 1 | Brainstorm，生成初版 spec (`specs/*.md`) | 自动（`/superpowers:brainstorming`） |
| 2 | 审查 spec，补充需求 | **人工** |
| 3 | Agent team 迭代（Spec Reviewer + Spec Writer，最多 3 轮） | 自动 |
| 4 | 主 agent 修小问题，列大决策请求确认 | 半自动 |
| 5 | 最终确认 spec | **人工（可跳过）** |
| 6 | 生成可执行 plan (`plans/*.md`) | 自动（`/superpowers:writing-plans`） |
| 7 | 执行 plan | 自动（`/superpowers:executing-plans`） |

适用场景：开发新 feature、debug、做 research。支持"下班前给需求，隔天看结果"模式。

---

### `sync-ck-fmha` — CK FMHA API 同步

**触发词**：`sync CK`、`update CK submodule`、`integrate CK PR`、`CK FMHA 变更`

当 `ROCm/rocm-libraries` 中有 PR 修改了 CK 的 FMHA API（`fmha_fwd` / `fmha_batch_prefill` / `fmha_fwd_splitkv` 的 traits struct、args struct、kernel codegen）时，自动同步 AITER 调用链。

CK submodule 路径：`3rdparty/composable_kernel`（是 `projects/composablekernel/` 的 subtree-split mirror）

---

## 使用方法

### 安装（user 级别，全局可用）

```bash
ln -s /path/to/agent_skill/.claude/skills/dev-pipeline ~/.claude/skills/
ln -s /path/to/agent_skill/.claude/skills/sync-ck-fmha ~/.claude/skills/
```

### 安装（project 级别，仅对特定项目生效）

```bash
mkdir -p .claude/skills
ln -s /path/to/agent_skill/.claude/skills/dev-pipeline .claude/skills/
```

### 调用

```
/dev-pipeline 优化 CK gemm kernel，支持 bf16，当前实现在 xxx.cpp，测试方法是 make test
/sync-ck-fmha PR#1234
```

---

## ROCm 参考文档

`rocm-ref.2026.03.25.gz` 包含 ROCm ISA、硬件指令、GPU 规格等参考资料。

```bash
# 解压
mkdir -p /tmp/rocm-ref && tar -xzf rocm-ref.2026.03.25.gz -C /tmp/rocm-ref

# 查看索引
cat /tmp/rocm-ref/rocm-ref/INDEX.md
```

根据 `CLAUDE.md` 中的规定，所有涉及 ROCm 硬件/指令的问题必须先查阅此文档再给出答案。

---

## 工作原则（CLAUDE.md）

1. **输出语言**：所有输出使用中文
2. **答案验证**：所有结论必须经过查阅资料、联网搜索或查看代码验证
3. **ROCm 相关**：必须先查阅 `rocm-ref.2026.03.25.gz`，未经验证不得输出
