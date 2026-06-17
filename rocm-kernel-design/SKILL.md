---
name: rocm-kernel-design
description: |
  ROCm kernel 设计主流程 —— 在 AMD GPU（CDNA gfx942/gfx950）上设计、实现、验证、优化
  kernel（CK / ck_tile / aiter / HIP / Triton）的单-agent 迭代方法论。以"实测证据驱动每一步取舍"
  为核心，并把 ROCm 硬件差异与 GPU 使用纪律显式编码进流程。
  TRIGGER when 用户说："用 rocm-kernel-design" / "设计 ROCm kernel" / "做个 CK/aiter kernel" /
  "优化 HIP kernel" / "写个 MoE/GEMM kernel（AMD/ROCm/MI300/MI350）" / "把 X 接进 CK/aiter" /
  "调 ROCm kernel 性能 / 精度"。
  DO NOT TRIGGER：纯 CUDA/Nvidia kernel、与 GPU kernel 无关的任务、只问概念不动代码。
---

# rocm-kernel-design —— ROCm kernel 设计主流程

任务：`$ARGUMENTS`

> 核心信念：**kernel 工作靠实测、不靠记忆**。任何一处改动都必须同时拿到"正确性证据 + 性能证据"两份数据，写进文件，再据此决定要不要留。无证据的改动不进 baseline。

---

## 0. 何时用 / 跳过

**用**：要在 ROCm（CDNA gfx942/gfx950）上新写或改一个 kernel（CK XDL / ck_tile / aiter codegen 实例 / HIP / Triton），或优化其性能/精度，或把一个新特性（激活、量化、layout）接进现有 kernel。

**跳过**：纯 Nvidia/CUDA kernel；不碰 kernel 的任务；只解释概念不动代码（直接答即可）。

---

## 1. 主流程（实测证据驱动的单 agent 循环）

本流程把"开发 kernel"拆成五个有序阶段，每个阶段都有明确产物，且核心环是一个带数据闸门的迭代环 —— 没有数据就不允许把改动并入基线。

```
锁定规格 → 跑通最小版 → 列优化机会 → [单点试验环：动一处 → 测正确性 → 测性能 → 落数据 → 闸门判定]* → 定稿
```

### 阶段 A — 锁定规格（Spec lock，先写死，别跳）

动手前把这一组规格落到任务笔记开头（建议命名 `trials.md`，下文沿用），后面所有判定都回看它：

- **输入/输出**：每个 tensor 的 shape + dtype + layout（行主/列主/preshuffle）。
- **量化格式**：weight/activation dtype、scale 格式（E8M0 / fp32）、粒度（per_tensor / per_token / per_1x128 / 128×128 / group-32）、对称性。
- **数学语义**：kernel 算什么（写出公式），含激活、bias、routing 权重等。
- **对照基准**：谁是"真值"—— torch 参考实现（fp32 / 高精度算同一公式），配 cos_sim + checkAllclose 阈值。**规格里必须写明"和谁比"**，否则后面无法判对错。
- **目标 arch**：gfx942（CDNA3）还是 gfx950（CDNA4）？这决定能用哪些指令（见 §4）。
- **边界约束**：显存上限、是否允许 rebuild、做单算子隔离（op-isolate）还是 e2e。

规格有缺口 → 先用 `AskUserQuestion` 问清，别带着猜测去写 kernel。

### 阶段 B — 跑通最小版（first green）

目标只有一个：**先对，再说快**。

- 优先**复用现有 kernel/实例**，只补缺口（新激活分支、新 codegen 实例），别从零造。
- 复用前先确认现有 kernel 的 epilogue/dispatch **真覆盖**你的 case（见 §6：CK 有多套 MoE kernel，激活 dispatch 各自独立）。
- "跑通"的判定 = 对 torch 参考 cos_sim 达标（哪怕很慢）。这一版就是后续所有试验的对照基线。

### 阶段 C — 列优化机会（opportunity list）

把候选优化全列出来（tile 尺寸、pipeline version、LDS double-buffer、preshuffle、向量化、occupancy/waves_per_eu、bank conflict 消除…），按"收益高 + 风险低"排序，从最划算的先做。

### 阶段 D — 单点试验环（one knob per trial）

**每一轮只拧一个旋钮**，然后跑完整四步：
1. **测正确性**：op_tests 对 torch 参考算 cos_sim + checkAllclose（§2）。
2. **测性能**：算子级量时延/带宽（§3）。
3. **落数据**：把"改了什么 / cos_sim / 时延 / 是否回归"追加进 `trials.md`（§1.5）。
4. **闸门判定**：按 §1.6 的合入闸门决定留或弃。

一轮动多处 = 数据无法归因到哪个改动，禁止。

### 阶段 E — 定稿（finalize）

汇总所有试验，挑出最优组合；确认无正确性回归；按 §5 纪律决定是否 commit（默认**不 commit**，留工作区等人类拍板）。

### 1.5 数据账本（trials.md，决策只认账本）

每轮试验追加一块结构化记录：

```
## trial N — <改动一句话>
arch: gfx942 | shape: [...] | dtype/quant: f8/per_token
correctness: cos_sim=0.99998 (vs torch fp32 ref) | checkAllclose 说明(fp8 噪声来源)
perf: stage1 X us (baseline Y us, -Z%) | 工具: rocprofv3
gate: KEEP / DROP （一句话理由）
```

落数据是硬要求 —— 跨试验/跨 session 的取舍只认账本，不认"我记得"。

### 1.6 合入闸门（一个改动凭什么留下）

**三道闸全过才 KEEP：**
1. **正确性过**：cos_sim ≥ 规格阈值（典型 ≥ 0.999），且无 NaN。
2. **性能真涨**：bench 较当前 baseline 有可测改善（超出抖动噪声）。
3. **零回归**：其它已覆盖的 shape/dtype 仍然过。

任一道不过 → DROP，记下原因，回退到上一个 KEEP 状态再试下一个旋钮。**正确性永远压过性能**：慢但对 > 快但错。

---

## 2. Validation（正确性）

- **判据 = 对 torch 参考的 cos_sim**（参考用 fp32/高精度算同一公式）。cos_sim 是聚合判据，稳健。
- `checkAllclose`（atol/rtol）会因 **fp8/低精度量化噪声**标 failed，这常是**正常的**——只要 cos_sim 优秀即可，需在笔记里说明残差来源（dtype 舍入，非公式错）。
- **逐元素 rel 误差偏高常是"近零放大"假象**：参考输出大量接近 0 的元素，相对误差被极小分母放大 → 看 cos_sim，别被逐元素 rel 吓到。
- 复用 `op_tests/`（如 `test_moe_2stage.py`）的现成 harness：它带 `--act`/`--quant` CLI、torch 参考、`checkAllclose`+`calc_diff`(≈1−cos)。
- 公式正交性检查：激活/量化常**正交**——激活在 fp32 算（gate/up 先反量化），量化只是 GEMM 的输入位宽。先单独验公式数学等价（fp32 重实现 vs torch，随机点 max|err| 应 ~1e-15），再验整 kernel。

---

## 3. Evaluation（性能）

- 算子级 bench：`rocprofv3`（trace / counters）、`rocprof-compute`（即原 omniperf / ROCm Compute Profiler，看 MFMA util、LDS bank conflict、VALU/VMEM busy、occupancy）。
- 关注指标：kernel 时延、达成带宽/算力占峰值比、MFMA 利用率、LDS bank conflict、寄存器溢出（spill）。
- 先测 baseline，再测每次改动 delta；时延波动大时多跑几次取稳定值。
- 反汇编核指令：`roc-obj` / objdump 看是否用了期望的 `v_mfma_*`（确认走对计算路径，如普通 fp8 mfma vs MX scaled-mfma）。

---

## 4. ROCm 工具映射 + 硬件差异（显式编码）

### 4.1 工具映射（CUDA → ROCm）

| 概念 | CUDA / Nvidia | ROCm / AMD |
|---|---|---|
| 模板 GEMM/kernel 库 | CUTLASS | **CK（Composable Kernel）/ ck_tile** |
| BLAS | cuBLAS / cuBLASLt | **rocBLAS / hipBLASLt** |
| 算子库 | — | **aiter**（codegen + Python 算子，即本仓） |
| profiler | Nsight Systems / ncu | **rocprofv3 / rocprof-compute（原 omniperf）** |
| 编译器 | nvcc | **hipcc**（clang 后端） |
| ISA 参考 | PTX / SASS | **GCN/CDNA ISA**（配 AMD 官方 CDNA ISA 文档，见 §4.3） |
| 矩阵核 | Tensor Core (WMMA/MMA) | **Matrix Core (MFMA)**；CDNA5 起转 WMMA |
| Triton | Triton(CUDA) | Triton(ROCm，`tl.dot` / `tl.dot_scaled`) |

### 4.2 硬件差异（gfx942 vs gfx950，落 kernel 前必查）

| 维度 | gfx942（MI300，CDNA3） | gfx950（MI350，CDNA4） |
|---|---|---|
| fp8 mfma | 有，`v_mfma_f32_*_f8f8`，**E4M3 是 fnuz**（bias 8） | 有，K 翻倍；E4M3 是 **fn / OCP**（bias 7） |
| fp4 / fp6 | **无** | 有，`v_mfma_f32_*_f4 / _f6` |
| MX scaled-mfma（block-scale 在硬件 MFMA 内） | **无**（CDNA4-only） | 有，`v_mfma_*_mxfp8 / _mxfp4` + `V_MFMA_LD_SCALE_B32` |
| group-32 microscaling（E8M0 / 32 元素共享 scale） | **硬件无**（只能 software） | 硬件 native |
| stochastic rounding（fp8 转换） | 无 | 有 |

**结论性约束**（反复踩）：
- gfx942 上 **group-32 MX（mxfp8/mxfp4）不能 native**，只能 software（普通 fp8 mfma + 软件 scale）或转 block-fp8[128,128] / 反量化 BF16。
- gfx942 的 fp8 是 **fnuz**（bias 8），OCP checkpoint 是 fn（bias 7）；同 bit 数值差 2×，dequant→requant 过 f32 会自动吸收。
- 选 arch 前查 AMD 官方 CDNA ISA 文档（§4.3），**未经文档验证的 ISA 结论不要写进 kernel 假设**。

### 4.3 ISA 文档（必查，落硬件结论前）

落任何 ISA / 硬件指令结论前，先查 AMD 官方 CDNA ISA 参考文档（CDNA3 = gfx942、CDNA4 = gfx950 各有一份 ISA reference）。标准查阅流程：
1. 先用索引/目录定位相关 topic（MFMA 寄存器布局、数据类型与精度、MI350 数据转换等）。
2. 再读对应章节确认具体编码/约束。
3. 必要时回到原始 ISA reference PDF 核对位段。
4. 关键概念：MFMA（matrix core 累加 fp32）、LDS（共享内存 / bank conflict）、VGPR/AGPR（寄存器 / spill）、cbsz/abid/blgp（MFMA 广播）、K-tile（GEMM contraction 分块）。

未经官方文档验证的硬件结论，不得写进 kernel 假设（见 §0 验证原则）。

---

## 5. 内嵌纪律（必守）

### 5.1 GPU 使用纪律

- **选空闲卡**：跑前 `rocm-smi --showuse --showmemuse` 查 8 卡，挑 0% 计算 / 0% VRAM 的；避开 0/1（常被抢）。用 `HIP_VISIBLE_DEVICES=<n>` 命令行临时指定，**不写持久环境**。
- **rebuild 前确认独占**：`ps aux | grep -E 'ninja|hipcc|clang|setup.py|cmake|gen_instances'` 确认无他人在编（`<defunct>` 僵尸无害）才开 `AITER_REBUILD=1`。
- **外部满载就退避**：别人占满卡 → 等待/换卡，**绝不 kill 外部进程**。
- **判泄漏看 VRAM 趋势**：跑完采样 VRAM 是否回基线（多次采样无单调上升 = 无泄漏；残留 ~300MB 多为 driver/cache）。
- **失败重试 ≤ 2 次**：脚本 bug 修了再跑算合理；硬件/arch 阻塞（如 gfx942 跑 fp4）不重试无意义的尝试。
- **用完还原**：临时脚本删掉；env 仅命令行临时；不留脏环境。

### 5.2 代码 / git 纪律

- **未验证不 commit**：cos_sim 没过、实现没跑通 → 留工作区，不 commit、不 push、不 `git add`。
- **精确 git add**：只 add 本任务真正改的文件，逐个列；不用 `git add -A` / `git add .`。
- **不动 submodule pin**：CK submodule 内容可改（验证用），但 **pin 不变 / 不 re-pin**，除非人类明确拍板。
- **commit message 不加 Co-Authored-By trailer**（本仓约定；按本仓来，与某些项目相反）。
- 改动留工作区、等 lead/人类决定 commit 与否，是默认姿态。

---

## 6. 血泪坑（ROCm MoE 专属，复用前必查）

- **CK 有多套 MoE kernel，激活 dispatch 各一份**：`gridwise_moe_gemm.hpp`（普通 / per_token / per_tensor）、`gridwise_moe_gemm_blockscale.hpp`（block-fp8）、mxfp4 变体……**每套的 epilogue 激活 `if constexpr` 链是独立的**。给一套加了激活分支 ≠ 另一套也有。曾在 blockscale 漏加某激活分支 → ActOP 不命中 → epilogue 直接输出未激活的原始值 → cos_sim 极低才暴露。**复用前先 grep 目标 kernel 的 epilogue 确认你的 ActOP 真有分支**。
- **codegen tag/cuh 选择要对齐**：`gen_instances.py` 按 quant_type 选 `quanttype`（`""` / `_blockscale` / `_mxfp4`）决定 include 哪个 `common*.cuh`；若 cuh 与 CDEElementOp 不匹配 → rebuild 编译失败。补实例时照**同 quant 的现有循环**改，别混。
- **JIT 不对 CK header 做 hash**：改了 CK header 或 codegen → 必须 `AITER_REBUILD=1`（删 .so + build 树重编），否则改动不生效。
- **arch 门控**：FP4/MX 实例常被 `#ifndef __gfx942__` 包住；gfx942 上即便补了 codegen 也编成空符号。先确认 arch 能产真符号。

---

## 7. ★Worked example：把一个新激活接进 per_token fp8 MoE★

演示完整主流程：在已支持若干激活的 per_token fp8（PTPC）MoE 上，新接一个之前没覆盖的激活。重点不是这个激活本身，而是**怎么定位"该改哪一层、哪一层已现成"**，以及怎么用证据收尾。下面以接入一个带 gate/up 的门控激活为例。

### 锁定规格
- 输入：MoE g1u1，hidden×E 激活 + w1=[E,2·inter,model] / w2=[E,model,inter]，**a8w8 per_token fp8**（QuantType=per_token=2），激活 = 目标门控激活（gate/up 形态，各有 clamp 上下界）。
- 输出：bf16/f16。
- 对照基准：torch fp32 实现同一激活公式 + per_token 反量化；cos_sim ≥ 0.999。
- 目标 arch：**gfx942**（per_token fp8 = 普通 fp8 mfma fnuz，gfx942 原生支持，无需 MX）。

### 跑通最小版（先查现状，最大化复用）

关键在于 PTPC 路径上有**两个相互独立的 codegen 门控**，要分开看，别串成一条因果链：

1. **走哪个 kernel tag？** —— 由 `QuantType_list=[3,4]` 这一组门控。per_token=2 不在 [3,4] 里 → 落到 plain tag `a8w8` → `quanttype=""` → plain `gemm_moe_ck2stages_common.cuh` → 用 **`gridwise_moe_gemm.hpp`（普通 kernel）**。
2. **include 哪个 cuh 后缀？** —— 由另一组 `quant_type in [4,5]` 这一门控独立决定。per_token=2 同样不在 [4,5] 里 → 选 **plain `.cuh`（无 `_blockscale` / `_mxfp4` 后缀）**。
   > 这两个门控用的是**不同的 quant_type 列表**（tag 看 [3,4]、cuh 后缀看 [4,5]），是两个独立判断，不是一个推另一个。恰好 per_token=2 两组都不命中，所以两边都走 plain 路径。
3. **epilogue 有这个激活吗？** `grep <act>_and_mul gridwise_moe_gemm.hpp` → 若**有**（helper + epilogue 各 quant 分支，per_token 走 PerTokenQuant 路径 `gate=scale_a*scale_b*c_thread_buf`），则 **epilogue 不是缺口，CK 不用改**；这一步就是用 grep 把"假设有"变成"确认有"，避开 §6 的血泪坑。
4. **codegen 缺口在哪？** general 量化循环往往只覆盖基础激活（如 silu/gelu）× {per_tensor, per_token}；而门控激活的专用循环可能只覆盖 no-quant / mxfp4 / block-fp8 三条线 —— 于是 **`f8 × per_token × 该激活` 的实例数 = 0**，这才是真正要补的缺口。

### 改动清单（最小）
| 改动 | 文件 | 说明 | 工作量 |
|---|---|---|---|
| 补 `f8 × per_token × <该激活>` 实例循环 | `csrc/.../gen_instances.py` | 照现有 block-fp8 门控激活段，把粒度从 `per_1x128` 换成 `per_token`，a/b=`f8`，act 设为目标激活（映射到对应 ActOP）。独立循环，不污染既有覆盖 | **~15 行** |
| CK epilogue | — | 无需改（普通 kernel 已有该激活的 epilogue 分支，第 3 步已确认） | 0 |
| dispatch / 桥接 | — | 复用 a8w8 tag + 现有 `map_activation_to_ck_stage1` 映射（已有） | 0 |

### 测正确性
- `AITER_REBUILD=1`（codegen 改了，blob 要重生成）→ `test_moe_2stage.py -q <per_token> -a <该激活> -d bf16 ...`。
- 对 torch fp32 参考算 cos_sim；fp8 噪声下 checkAllclose 可能 failed，但 cos_sim 应达 ~0.9999（与已覆盖的 silu 基线同级）。
- 先做 dry-run：`gen_instances.py -w /tmp` 确认 per_token 该激活实例数 > 0、include 的是 plain `common.cuh`、ActOP 映射正确。

### 闸门判定
- 三道闸过（cos_sim PASS / 实例正确生成 / 既有 silu/gelu per_token 不回归）→ KEEP，记进 trials.md。
- 全程守 GPU 纪律（空闲卡 + 确认独占再 rebuild）；验证通过前不 commit、不 re-pin。

---

## 8. 自检（写完 kernel/改动后）

1. 规格里的 cos_sim 基准达标？checkAllclose 残差有 dtype 解释？
2. 目标 arch 的指令/格式经 AMD 官方 CDNA ISA 文档验证过？没编出空符号？
3. 复用的 kernel epilogue/dispatch 真覆盖本 case（grep 确认，非假设）？
4. trials.md 记了每轮试验的证据？
5. GPU 纪律守了（空闲卡 / 未 kill 外部 / VRAM 无泄漏 / 失败≤2 / 还原）？
6. 未验证未 commit、未动 pin、git add 精确、commit 无 Co-Authored-By？

任一不过 → 修正后再收尾。
