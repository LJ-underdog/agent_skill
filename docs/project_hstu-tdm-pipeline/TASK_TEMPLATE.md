# Task Template: hstu-tdm-pipeline

# 继承自：agent_skill/.claude/skills/project-summary/SKILL.md
# 创建日期：2026-08-19
# 状态：ACTIVE（Step 0/1 完成，Step 0 回归验证受阻于 GPU wedge）

---

## 任务概述

**目标**：参照 `ROCm/rocm-libraries#7755` 的 commit 序列，为 HSTU fwd 的 **SiLU（no-softmax）路径**在 gfx1250 上实现一条 TDM pipeline（Q/K/V 走硬件 box-major DMA 而非软件搬运）。
**相关仓库**：`/data/composable_kernel`（branch `hstu_attention_fwd_450` @ `a56c3ea3f`）、`/data/agent_skill`
**环境/硬件约束**：gfx1250 / CDNA5 / wave32；ROCm 7.14.60850（pip wheel `_rocm_sdk_core`，非 `/opt/rocm`）；单卡

---

## 参数 Schema

> HSTU fwd no-softmax 的实例空间是完全正交的 5 维，96 个实例 = 3×2×2×4×2。

| 参数名 | 说明 | 示例值 | 来源 |
|--------|------|--------|------|
| mode | batched / jagged / group | `-jagged=0` / `-jagged=1` / `-g=2` | `instances/` 文件名前缀，各 32 个 |
| dtype | 数据类型 | `-prec=fp16` / `bf16` | 各 48 个 |
| causal | 是否因果掩码 | `-causal=1` / `0` | 各 48 个 |
| maxk | head dim 档位 | `-hdim_qk=64/96/128/256` | 各 24 个 |
| dropout | 是否 dropout | `-p_drop=0` / `0.2` | 各 48 个 |
| MTile | decode/prefill 档 | 64 / 128 | `hstu_attention_fwd_setting_gfx125.hpp` |
| 变长参数 | jagged 专用 | `-seqlens=64,96,128,160`、`-targets`、`-context_len`、`-local_len`、`-minfull_len` | `-?` 帮助 |

> ⚠️ **batched 模式 `-seqlens` 只能给单值**，多值触发 `'1 == seq_lengths_q.size()'` abort（rc=134）。本任务因此误判过 32 个 case。

---

## 指标 Schema

| 指标名 | 说明 | PASS 标准 | FAIL 标准 | 精度 |
|--------|------|-----------|-----------|------|
| exit code | launcher 返回值 | 0 | 254 / 134 / 253 / 124 | 整数 |
| cos_sim | device vs CPU reference | ≥ 0.9999999 | < 0.999999 | 9 位小数 |
| 超容差元素数 | `\|o-r\| > atol + rtol·\|r\|`，rtol=1.6e-2 / atol=1e-5 | 0 | > 0 | 整数 |
| v_wmma / v_mfma | 反汇编指令计数 | wmma > 0 且 mfma == 0 | mfma > 0 | 整数 |

> ⚠️ **`rc=254` 有两义**：数值不匹配 **或** launcher 因实例未编入而主动拒绝，靠 stderr 首行区分。
> ⚠️ **无 PASS 字符串可 grep**，只能看 exit code + dump 数值。

---

## 成功标准

```
任务完成 = 满足以下所有条件：
✓ HSTU no-softmax 走 TDM pipeline，batch + jagged 两种 mode 对拍通过
✓ 回归：现有 SiLU 路径基线不退化（batch 32/32 + jagged 31/32 = 63/64）
✓ 反汇编 v_mfma == 0
✓ HEAD 保持 a56c3ea3f，不 commit/push/add 到 CK 仓库
```

---

## 已知事实（无需重验）

| # | 事实 | 来源 | 是否继承 |
|---|------|------|---------|
| F1 | gfx1250 = CDNA5，wave32，MFMA 已移除换 WMMA，无 AGPR | `HANDOFF_2026-08-18.md` §2.1（四方独立印证） | 继承 |
| F2 | PR #7755 = 本地 squash commit `a2ebc0513`，在 `upstream/develop`，**不是** HEAD 祖先 | `git merge-base --is-ancestor` 判否 | — |
| F3 | TDM 底层设施（`load_tile_tdm` @ `load_tile.hpp:188`、`amd_tdm_descriptor.hpp`、`ops/tdm/`）**已在工作区且与 upstream 零差异** | `git diff HEAD upstream/develop` 空输出 | — |
| F4 | TDM 的 `box_dim` 从 dram tile distribution 反推（`tile_window.hpp:893-898`），5D scatter dist 推出的 box 是散的 —— 这是 PR 里 V 那个 1.6% 字节吻合率的根因 | upstream 源码 + PR commit 5f7aec9 | — |
| F5 | TDM 不支持 dropout：`static_assert(!kHasDropout)`，且是**kernel 接口未扩展**而非硬件限制 | `block_fmha_pipeline_qr_ks_vs_tdm.hpp:79` | — |
| F6 | `CK_TILE_ENABLE_TDM_FEATURE` 仅在 `__gfx125__` 为 1，否则 TDM 指令**编译成空且不报错**（静默出错） | `config.hpp:221-225` | — |
| F7 | `MakeKLdsBlockDescriptor:216` 的 `!IsPerfectHeaddimSize` 分支**本身就是 plain row-major**，且 smem size 与 xor 分支相同 | 代码阅读 | — |
| F8 | HSTU 的 Q 是 load-once 直接进寄存器，**没有 Q 的 LDS descriptor**（与 FMHA 结构性差异） | `hstu_attention_fwd_pipeline_policy.hpp`，无 MakeQLds* | — |
| F9 | jagged/group 在 pipeline 层**完全不感知**，全在 kernel 层处理 | `kIsJagged` 在 pipeline 体内 0 次引用 | — |
| F10 | `gpu_busy_percent` 在 gfx1250 恒 100 与负载无关，不能判 wedge | 本任务单变量对照（空闲/满载各采样） | — |
| F11 | CK 实例编译 `-j 255` 会 OOM（251GB 不够），须用 `-j 24` | 本任务实测 | — |
| F12 | HSTU trload 与非 trload pipeline **只差 10 处**，其余逐字相同 | Explore 逐行 diff | — |

---

## 已知约束

- **红线**：不 `git commit` / `push` / `add` 到 `/data/composable_kernel`；HEAD 必须保持 `a56c3ea3f`
- 不动别人的进程（不 kill / attach / ptrace）
- ⛔ 不要 `cat /sys/kernel/debug/kfd/hqds` —— 会导致内核 NULL deref（已实测踩中两次）
- 运行二进制必须带 `LD_LIBRARY_PATH=/opt/venv/lib/python3.14/site-packages/_rocm_sdk_core/lib`
- `amdgpu.gpu_recovery = 0`（驱动不自愈，wedge 后静默），已两次因此吃亏

---

## Baseline

```bash
# 96 实例构建（Step 0 之前建立）
cmake -G Ninja -S /data/composable_kernel -B build_nosoftmax \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/opt/venv/bin/hipcc \
  -DCMAKE_PREFIX_PATH="/tmp/rocm-cmake-install;/tmp/hipshim" \
  -DGPU_TARGETS=gfx1250 -DHSTU_FWD_NO_SOFTMAX_INSTANCES=ON
→ "HSTU_FWD_NO_SOFTMAX_INSTANCES=ON: 96 fwd instances"
```

| 项 | 数值 | 备注 |
|---|---|---|
| 96 配置对拍 | **91 PASS / 5 FAIL** | 5 个失败每个只错 1 元素，误差恰好 = 半个 ulp（ratio 恒 0.50 跨 fp16/bf16），旧二进制同样复现 → 既有问题 |
| 收窄到 batch+jagged | **预期 63/64** | group 的 4 个失败被排除，只剩 `jagged/bf16/no_causal/maxk_128/has_dropout` |
| 反汇编 | 221184 `v_wmma` / **0** `v_mfma` | = 2 × 110592（48 实例版），fp16/bf16 各半，96/96 对象全含 wmma |
| 性能 | 1276 TFLOPS fp16 | b=8/nh=8/hdim=128/seq=4096，0.432 ms |

---

## 任务特化 — 常见坑

| 坑 | 正确处理 |
|----|---------|
| `ninja -j $(nproc)`（255）编译 CK 实例 | OOM killer 杀 clang，报错 `unable to execute command: Killed` 长得像编译错误。用 `-j 24` |
| `pkill -f "ninja -j"` / `pgrep -f` | 会匹配到**自己的 bash 命令行**，导致自杀或误报 RUNNING。用 `-x` |
| `timeout N <cmd>` 的子进程 | TaskStop 后**不会被杀**（脱离任务组），要手工 `kill -9` |
| 后台脚本被启动成两个实例 | 两个 HSTU 进程并发抢 GPU；本任务疑似因此触发 MES wedge（未证实） |
| 并行 `llvm-objdump` 写同一 stdout | 输出交错撕裂成碎片，指令计数偏差。每进程写各自文件 |
| 全量编译 FMHA | 3261 个实例。用 `--optdim 128 --filter '*qr_tdm*...'` 压到 5 个，16.8 秒 |

---

## 子任务结构（PR #7755 commit 序列映射）

| Step | 内容 | 状态 |
|---|---|---|
| Step 0 | cherry-pick `a2ebc0513`（框架地基 + TDM 参考实现） | ✅ 代码落地；❌ **回归验证未完成** |
| Step 1 | 真机验证 FMHA `qr_tdm` | ✅ **8/9 valid:y** |
| Step 2 | HSTU TDM 骨架 + LDS 布局打平（仍用老 loader） | 未开始（设计已定，改动比预想小） |
| Step 3 | dram dist 换 trivial tile-major（仍用老 loader） | 未开始 |
| Step 4 | kernel 侧 K/V dram view 改 affine | 未开始 |
| Step 5 | 换 `load_tile_tdm` + `s_wait_tensorcnt_barrier` | 未开始 |
| Step 6 | 派发三态 enum + 收窄 | 未开始 |
| Step 7 | prefill（MTile=128）+ P relayout | 未开始 |

**已定决策**：① 只 K/V 走 TDM，Q 完全不动；② 做 Step 1 的真机验证。

---

## Promotion Candidates

### [PC-1] 先用老 loader 跑通新 pipeline，再逐个操作数换新硬件
发现时间：2026-08-19
触发场景：从 PR #7755 的 commit 序列提炼
来源：代码发现（上游 commit 4/5/6 的顺序）

**内容**：引入新硬件路径（DMA / 新指令）时，先把新 pipeline 用**已知正确的老 loader** 跑通，拿到功能正确的基线，再逐个操作数切到新硬件。上游明知此阶段性能 −21%~−32% 也坚持先拿基线，然后 Q/K、V 分两步换 —— 这样每步只变一个变量，出问题能二分定位。上游 V 那个 1.6% 字节吻合率的布局错位坑就是这么抓出来的。

**为什么 promote**：这是"单变量对照"在**增量开发**（而非调试）场景的应用，通用性强。本任务据此把原计划的 1 步拆成 Step 2/3/4/5 四步。

**建议加入父类位置**：[x] SKILL.md — 常见坑（或新增"增量开发原则"节）
**置信度**：[x] 高（上游实证 + 本任务采纳）
**Review 结果**：[ ] 待 review

### [PC-2] 字节吻合率对比随机基线可区分"精度问题"与"布局错位"
发现时间：2026-08-19
触发场景：父类"常见坑"没覆盖的判读方法
来源：PR #7755 commit 5f7aec9

**内容**：怀疑数据布局错位时，对同一内存区域做**字节级**比对，把吻合率与**随机基线**（两个无关字节偶然相等 ≈ 1/256 ≈ 0.4%）对比，而不是与 100% 对比：
- 精度问题（舍入模式不同）→ 高位字节相同，吻合率远高于随机，通常 >50%
- 布局错位 → 比较的是两段无关数据，吻合率落在随机基线量级（0.4%~2%）

上游实测 1.6%，直接排除了"精度"方向。

**为什么 promote**：给"数值不对"这一大类问题提供了一个**廉价且判别力强**的二分方法，不限于 GPU kernel。

**建议加入父类位置**：[x] SKILL.md — 常见坑
**置信度**：[x] 高（上游实证）
**Review 结果**：[ ] 待 review

### [PC-3] 否定性诊断指标必须做空载对照
发现时间：2026-08-19
触发场景：遇到父类没覆盖的坑
来源：实验（gpu_busy_percent 单变量对照）

**内容**：把某个观测量当作"故障指标"写进文档前，必须先在**已知健康**的状态下采样一次。本任务发现 `gpu_busy_percent` 在 gfx1250 上空载与满载都恒为 100，而上一份交接文档把"GPU%=100 恒定"列为整卡 wedge 的旁证 —— 照此判断必然误判。

**为什么 promote**：交接文档里的"故障特征"最容易被后人当判据直接用，一个假信号会长期误导。成本只是一次空载采样。

**建议加入父类位置**：[x] SKILL.md — 自检清单-数据准确性
**置信度**：[x] 高（实验证据）
**Review 结果**：[ ] 待 review

---

## 任务完成 Checklist

- [x] Baseline 已记录（91/96，含 5 个既有失败的根因）
- [x] 参数 / 指标 schema 完整
- [x] Step 0 代码落地
- [x] Step 1 真机验证
- [ ] **Step 0 回归验证**（受阻于 GPU wedge）
- [ ] Step 2–7
- [ ] Promote review
