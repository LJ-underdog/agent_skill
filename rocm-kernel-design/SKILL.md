---
name: rocm-kernel-design
description: |
  Evidence-driven workflow for designing, implementing, validating, and optimizing
  GPU kernels on the AMD ROCm / CDNA stack (CK / ck_tile / aiter / HIP / Triton;
  gfx942=MI300/CDNA3, gfx950=MI350/CDNA4). Core belief: kernel work is decided by
  measurement, not memory — every change must produce a correctness proof AND a perf
  number, recorded to a ledger, before it is kept. Enforces a spec contract, a
  draft->plan gate before touching kernel code, single-knob iteration with validation
  after every change, an auditable evidence workspace, and built-in GPU/git discipline.
  Profiling: rocprofv3 / rocprof-compute (omniperf). Hardware truth: rocm-ref + AMD
  CDNA ISA docs. Correctness: numerical diff (cos_sim / rel+abs err) vs a CPU or
  torch-fp32 reference. Adapted & merged from MIT HAN Lab's Kernel Design Agents.
  Use when: writing/optimizing a ROCm CK/ck_tile/aiter/HIP/Triton kernel, porting an
  FMHA/GEMM/attention/MoE kernel, tuning tile/policy/occupancy, or wiring a new feature
  (activation/quant/layout) into an existing kernel.
  Trigger: "design a rocm kernel", "ck_tile/CK/aiter/HIP kernel", "tune this rocm kernel",
  "rocm-kernel-design", "用 rocm-kernel-design 做", "ROCm/MI300/MI350 kernel 实现/调优".
  DO NOT trigger: pure CUDA/Nvidia kernels (use the original KDA + ncu), non-kernel
  tasks, or concept-only questions (just answer).
---

# rocm-kernel-design — 证据驱动的 ROCm kernel 实现与调优工作流

任务：`$ARGUMENTS`

> **核心信念：kernel 工作靠实测、不靠记忆。** 任何一处改动都必须同时拿到"正确性证据 + 性能证据"两份数据、写进账本,再据此决定要不要留。无证据的改动不进 baseline。
>
> 域：AMD ROCm / CDNA（CK / ck_tile / aiter / HIP / Triton）。profiling 用 **rocprofv3 / rocprof-compute(原 omniperf)**;硬件知识用 **rocm-ref + AMD CDNA ISA 文档**;正确性用 **CPU reference 或 torch-fp32 reference 数值对拍**。并行编排可选本机 **agent-team**。移植/合并自 MIT HAN Lab 的 Kernel Design Agents（原版面向 CUDA + ncu）。

---

## 0. 何时用 / 跳过

**用**：在 ROCm（gfx942/gfx950）上新写或改一个 kernel（CK XDL / ck_tile / aiter codegen 实例 / HIP / Triton），优化其性能/精度,或把新特性（激活/量化/layout）接进现有 kernel。
**跳过**：纯 Nvidia/CUDA kernel（回原版 KDA + ncu）；不碰 kernel 的任务；只解释概念不动代码（直接答）；纯文档讲义（用 html-report）。

**两条铁律(全程不破)**：
1. **draft 闸门**：没有 `docs/draft.md`（且细化出 `docs/plan.md`）之前,不许动 kernel 代码。
2. **每个候选必验证**：每次有意义的改动后立刻跑 validation;通过才记为候选,失败也记原因,**不许静默丢弃**。
   附加：**慢但对 > 快但错**,正确性永远压过性能。

---

## 1. Task Contract / 规格锁定（先写死,填 `docs/task-contract.md`,别跳）

动手前把这组规格落到任务笔记开头,后面所有判定都回看它:

| 字段 | 说明（ROCm 语境） |
|---|---|
| **Objective** | 要实现/优化什么 kernel,面向哪个目标芯片（gfx942 / gfx950） |
| **I/O 规格** | 每个 tensor 的 shape + dtype + layout（行主/列主/preshuffle） |
| **量化格式** | weight/activation dtype、scale 格式（E8M0/fp32）、粒度（per_tensor/per_token/per_1x128/128×128/group-32）、对称性 |
| **数学语义** | kernel 算什么（写出公式）,含激活/bias/routing 权重 |
| **对照基准(oracle)** | 谁是"真值"——仓库的 CPU `reference_*.hpp`,或 torch fp32/高精度同公式;配 **cos_sim + rel/abs err** 阈值。**必须写明"和谁比"**,否则无法判对错 |
| **Performance target** | 可测目标（TFLOPS / 带宽利用 / 相对 baseline 加速 / X% roofline）;没有写 N/A |
| **Allowed approaches** | 复用哪些现成 pipeline/policy;约束（不改公共头/保持 API/不动 submodule pin） |
| **Validation command** | 一条能判对错的命令（编译 + 对拍,print `PASS/FAIL + err`） |
| **Evaluation command** | 一条能测性能的命令（benchmark,print 数字）;与 validation 不同才单列 |
| **Promotion criteria** | 候选被采纳的条件（见 §1 三道闸门） |
| **Target arch / build** | `GPU_TARGETS`(gfx942/gfx950)、编译 flags、ROCm 版本、op-isolate 还是 e2e |

规格有缺口 → 先用 `AskUserQuestion` 问清,别带猜测写 kernel。

---

## 2. 证据 Workspace（与目标仓库分离,自建一个 task workspace）

```
<task-workspace>/
  docs/
    task-contract.md      # §1 契约
    draft.md              # 实现计划草稿(闸门,先写它)
    plan.md               # 可执行计划(draft 细化后)
  src/                    # 候选 kernel 代码
  runs/                   # 每次跑的原始 log(validation/eval 输出)
  profile/               # rocprofv3 / rocprof-compute 产物与一句话结论
  benchmark.csv           # 逐候选性能:candidate,arch,shape,tile,metric,value,date
  candidates.jsonl        # 每候选一行(带血缘):
                          #   {id,parent,desc,status(pass/fail/promoted/rejected),reason,evidence}
```
> 要保证:**后来人能据此还原"改了什么、测了什么、为什么晋级/否决"**。跨试验/跨 session 的取舍**只认账本,不认"我记得"**。本环境无 `Date.now()`,时间戳用 `date +%F` 现取。

---

## 3. 主循环（draft 前禁止写 kernel）

```
锁定规格 → 勘察+baseline → (按需查 rocm-ref) → 写 draft→plan(闸门)
        → 跑通最小版(first green) → 列优化机会 → [单点试验环]* → 定稿
```

1. **勘察**：读 workspace + 目标仓库结构、现有 kernel、reference、测试。
2. **定 baseline**：现状行为、对拍怎么跑、当前性能数。
3. **按需调研**：只查这任务必需的（优先 **rocm-ref**,见 §5;和现成 pipeline/policy）。
4. **写 `docs/draft.md`（闸门）**：必含——baseline 与验证方法 / 主要风险与未知 / 排序的候选方向（收益 vs 风险）/ 头几个具体步骤 / 精确 validation+eval 命令 / 晋级或否决一个候选所需证据。
5. **draft → `docs/plan.md`**：细化成可执行计划,再动代码。
6. **跑通最小版（first green）——先对再快**：优先**复用现有 kernel/实例**只补缺口;复用前先 **grep 确认** epilogue/dispatch **真覆盖**你的 case（别假设,见 §7）;"跑通"=对 reference cos_sim 达标（哪怕慢）,这版即后续所有试验的对照基线。
7. **列优化机会**：tile 尺寸 / pipeline version / LDS double-buffer / preshuffle / 向量化 / occupancy(waves_per_eu) / bank conflict 消除…按"收益高+风险低"排序。
8. **单点试验环（one knob per trial）**：每轮**只拧一个旋钮**,然后跑完整四步：
   ① 测正确性(§4) → ② 测性能(§6) → ③ 落账本(`candidates.jsonl`+`benchmark.csv`+`profile/`,写 parent 血缘) → ④ **三道闸门判定**(§3.1)。一轮动多处 = 无法归因,禁止。
9. **重复**直到满足 promotion criteria,或把 blocker 显式写出。

> **并行试候选**：候选方向 ≥2 且独立时,可用本机 **agent-team**（每 pane 一个候选,file-based 派单）,lead 汇总对拍/benchmark 选优。单候选/强串行就别上多 pane。

### 3.1 合入闸门（一个改动凭什么留下）
**三道闸全过才 KEEP：**
1. **正确性过**：cos_sim ≥ 规格阈值（典型 ≥0.999）且无 NaN;rel/abs err 在容差内。
2. **性能真涨**：bench 较当前 baseline 有可测改善（超出抖动噪声）。
3. **零回归**：其它已覆盖的 shape/dtype/模式仍过。

任一不过 → DROP,记原因,回退到上一个 KEEP 状态再试下一旋钮。

---

## 4. 正确性：对拍 reference（oracle）

oracle 可以是仓库 host 端 `reference_*.hpp`,也可以是 torch fp32/高精度同公式实现。标准对拍链:
1. 随机输入（固定种子）→ 跑 GPU kernel 出结果。
2. 同输入跑 reference 出基准。
3. 比 **cos_sim（聚合判据,稳健,首选）** + **rel/abs err（报 max/mean）**;bf16/fp16/fp8 用宽容差。
4. **覆盖矩阵**：dtype × 各模式（batch/jagged/group...）× 各开关（causal/mask/softmax/quant...）× 形状边界。**测开关的交叉积,不要只测对角线**（见 §8 覆盖洞教训）。
5. **deterministic 路**额外验逐位可复现（同输入两跑 byte-identical）。

**低精度对拍的两个常见假象（别被吓到,但要在账本里写清残差来源）：**
- `checkAllclose`(atol/rtol) 在 **fp8/低精度量化噪声**下常标 failed——只要 cos_sim 优秀即可,注明是 dtype 舍入而非公式错。
- **逐元素 rel 误差偏高常是"近零放大"**：reference 大量输出接近 0,极小分母放大相对误差 → 看 cos_sim,别盯逐元素 rel。

公式正交性：激活/量化常**正交**（激活 fp32 算,量化只是 GEMM 输入位宽）→ 先单独验公式数学等价（fp32 重实现 vs torch,随机点 max|err| ~1e-15）,再验整 kernel。

validation command 必须 print 明确的 `PASS/FAIL + err 数值`,让主循环可自动判读。

---

## 5. 硬件知识：rocm-ref + AMD CDNA ISA 文档（不臆造）

任何关于 MFMA/WMMA、wave64/32、VGPR/AGPR、LDS bank、occupancy、存储层级、原子、cross-lane、量化格式的判断,**必须对照文档**,别凭印象:
- **rocm-ref**（本仓 `rocm-ref.*.gz`）：`cd /tmp && tar xzf <pkg>` 得 `/tmp/rocm-ref/`;先读 `INDEX.md` 路由。权威 topic：`mfma-register-layout` / `wmma-matrix-ops` / `occupancy-register-pressure` / `memory-hierarchy` / `lds-bank-conflicts` / `cross-lane-ops` / `hardware-specs-table` / `vgpr-sgpr-agpr`;官方 ISA PDF 在 `p4vdoc/`。
- **关键代次事实**：**MFMA 仅 CDNA3/4(gfx942/gfx950)**,CDNA5(MI400) 改 **WMMA**;gfx942/950 = wave64;**gfx950/CDNA4 每 CU LDS = 160 KB**（rocminfo GROUP segment 实测;rocm-ref `hardware-specs-table` 同;**注意 rocm-ref 内部 128 vs 160 不一致,以 rocminfo 实测为准;64KB 是 CDNA3**）。
- **以实测兜底**：硬件数字优先 `rocminfo`/`rocm-smi` 实测,再对文档;两者冲突时实测优先并记下。
- 找不到文档/实测支撑的硬件数字 → 删或改成相对表述,**不臆造**。

### 5.1 gfx942 vs gfx950 硬件差异（落 kernel 前必查）
| 维度 | gfx942（MI300,CDNA3） | gfx950（MI350,CDNA4） |
|---|---|---|
| f16/bf16 MFMA | 32×32×8 / 16×16×16 | + K 翻倍 32×32×16 / 16×16×32（2× 吞吐） |
| fp8 mfma | 有 `v_mfma_f32_*_f8f8`,**E4M3=fnuz**（bias 8） | 有,K 翻倍;E4M3=**fn/OCP**（bias 7） |
| fp4 / fp6 | **无** | 有 `v_mfma_f32_*_f4 / _f6` |
| MX scaled-mfma（block-scale 在硬件 MFMA 内） | **无** | 有 `v_mfma_*_mxfp8 / _mxfp4` + `V_MFMA_LD_SCALE_B32` |
| group-32 microscaling（E8M0,32 元素共享 scale） | **硬件无**（只能 software） | 硬件 native |
| stochastic rounding（fp8 转换） | 无 | 有 |
| LDS / CU | 64 KB | **160 KB** |

**结论性约束（反复踩）**：gfx942 上 group-32 MX 不能 native（只能 software fp8+软件 scale,或转 block-fp8[128,128]/反量化 BF16）;gfx942 fp8 是 fnuz(bias8)、OCP 是 fn(bias7),同 bit 差 2×,dequant→requant 过 f32 自动吸收。**未经文档验证的 ISA 结论不写进 kernel 假设。**

---

## 6. 性能剖析：AMD 工具（替代 ncu）

| 用途 | 工具 |
|---|---|
| 计数器 / trace | `rocprofv3`（或旧 `rocprof`） |
| 内核级深度分析 / roofline（≈ncu） | `rocprof-compute`（原 omniperf / ROCm Compute Profiler）|
| 反汇编核指令 | `roc-obj` / objdump——确认真用了期望的 `v_mfma_*`（如普通 fp8 mfma vs MX scaled-mfma） |
| 占用率/寄存器 | 编译器 `-Rpass-analysis=kernel-resource-usage` / ISA dump（`--save-temps`） |
| 设备信息 / 监控 | `rocminfo`、`rocm-smi` |
| 调试 | `rocgdb` |

关注：kernel 时延、达成带宽/算力占峰值比、**MFMA 利用率**、LDS bank conflict、寄存器 spill、occupancy、VALU/VMEM busy。先测 baseline 再测 delta,波动大多跑取稳定值。**优化判断要有剖析证据：先用 roofline 定位 memory-bound 还是 compute-bound 再动手**（别凭直觉砍）。

---

## 7. 构建 + 复用的坑（grep 别假设）

- 典型：`cmake -DCMAKE_PREFIX_PATH=/opt/rocm -DGPU_TARGETS=gfx942 -DCMAKE_BUILD_TYPE=Release ...`;按 example 的 CMake target 编。
- **模板实例化易爆炸**：先收敛到 MVP 最小实例集（单 dtype/单形状）打通端到端,再按 plan 扩;把"加新实例"当一个候选维度记入 benchmark（**编译时间也是成本**）。
- **复用现有 kernel 前先 grep 确认覆盖,别假设**（最常见的 silent-wrong 来源）：
  - 一个库常有**多套 kernel,各自独立的 epilogue/dispatch `if constexpr` 链**。给一套加了分支 ≠ 另一套也有。曾在某变体漏加激活分支 → epilogue 直接输出未激活原值 → cos_sim 极低才暴露。**复用前 `grep` 目标 kernel 的 epilogue 确认你的开关真有分支。**
  - codegen 实例的 tag/cuh 选择常由**多个独立的 quant_type 列表**门控（走哪个 tag 与 include 哪个 cuh 是两个判断,不是一推一）;补实例照**同 quant 的现有循环**改。
  - JIT 常**不对 C++ header 做 hash**：改了 header/codegen 必须强制 rebuild（删 .so + build 树重编）,否则不生效。
  - **arch 门控**：FP4/MX 实例常被 `#ifndef __gfx942__` 包住,gfx942 上即便补了 codegen 也编成空符号 → 先确认 arch 能产真符号。

---

## 8. 通用教训（跨项目复用,血泪沉淀)

- **覆盖洞 > throw 危险**：测试矩阵只测"对角线"（如 causal=1 配因子 / causal=0 不配因子）会漏掉交叉 case。**新特性要做开关的交叉积覆盖**;未支持的组合若不 throw 会**静默算错**——要么对拍覆盖,要么显式 throw。
- **收紧类优化要离线穷举校验**：当优化是"缩小遍历范围/收紧 mask"时,写一个离线穷举的**超集校验器**（枚举所有 tile/坐标,断言新范围 ⊇ 必需集合），它能比对拍**更早更硬**地挡住 silent-under-tighten。
- **零回归重构用 byte-identity gate**：纯重构/加轴若声称"不碰已有路径",用**设备符号逐位对比**（dump 两版 .hsaco 符号 diff）证明 byte-identical,比只跑对拍更硬。
- **反误报铁律**：给"源码/硬件/他人代码"下 bug 定性前,先回到**真源码 + rocm-ref/ISA + 实测**核对,别凭一次对拍 FAIL 或一次 grep 就判。注意 look-alike 陷阱（如 fp32 与 f16 可有相同 M×N×K 形状;runtime switch ≠ compile-time 实例轴）。核不实就标"待复核",不标 bug。
- **point-in-time 文档锚定 commit**：里程碑文档里的源码行号是快照,会随代码增长漂移;锚定到具体 commit 并注明,**别盲目刷到 HEAD**（会破坏快照完整性）。
- **诚实归因**：性能模型的[推导]数会高估（Amdahl）,实测多少记多少;产出汇报附 validation(PASS+err)/benchmark/profile 结论,**不许只说"做完了"**。

---

## 9. 内嵌纪律（必守）

### 9.1 GPU 使用纪律
- **选空闲卡**：跑前 `rocm-smi --showuse --showmemuse` 查所有卡,挑 0% 计算/0% VRAM 的;避开常被抢的卡。用 `HIP_VISIBLE_DEVICES=<n>` 命令行临时指定,**不写持久环境**。
- **rebuild 前确认独占**：`ps aux | grep -E 'ninja|hipcc|clang|setup.py|cmake|gen_instances'` 确认无他人在编（`<defunct>` 僵尸无害）才开重编。
- **外部满载就退避**：别人占满 → 等待/换卡,**绝不 kill 外部进程**。
- **判泄漏看 VRAM 趋势**：跑完采样 VRAM 是否回基线（多次采样无单调上升 = 无泄漏;残留 ~300MB 多为 driver/cache）。
- **失败重试 ≤ 2 次**：脚本 bug 修了再跑算合理;硬件/arch 阻塞（如 gfx942 跑 fp4）别重试无意义尝试。
- **用完还原**：临时脚本删掉;env 仅命令行临时;不留脏环境。

### 9.2 代码 / git 纪律
- **未验证不 commit**：cos_sim 没过/没跑通 → 留工作区,不 commit/不 push/不 `git add`。
- **精确 git add**：只 add 本任务真正改的文件,逐个列;不用 `git add -A` / `git add .`。
- **不动 submodule pin**：submodule 内容可改（验证用）,但 **pin 不变/不 re-pin**,除非人类明确拍板。
- **commit message trailer 按目标仓约定**（有的仓要 Co-Authored-By、有的禁;先看仓库习惯）。
- 改动留工作区、等人类决定 commit 与否,是默认姿态。

---

## 10. 与其它 skill 的配合
- **agent-team**：并行试候选 / 分解设计的编排层。
- **project-summary / html-report**：把最终方案、调优结论写成可验证记录或图文报告。
- **dev-pipeline**：需要 spec-first 的新功能开发流程。
- 设计阶段（还没定方案）先产设计文档 + review;本 skill 主要管**实现+调优阶段**的纪律与证据。

---

## 11. 自检（写完 kernel/改动后）
1. 规格里的 cos_sim/err 基准达标？checkAllclose 残差有 dtype 解释？
2. 目标 arch 的指令/格式经 rocm-ref / AMD CDNA ISA 文档（或 rocminfo 实测）验证过？没编出空符号？
3. 复用的 kernel epilogue/dispatch 真覆盖本 case（**grep 确认,非假设**）？覆盖矩阵做了开关交叉积？
4. `candidates.jsonl` + `benchmark.csv` 记了每轮试验的证据 + 血缘？
5. GPU 纪律守了（空闲卡 / 未 kill 外部 / VRAM 无泄漏 / 失败≤2 / 还原）？
6. 未验证未 commit、未动 pin、git add 精确、trailer 合目标仓约定？
7. 收紧类优化有离线穷举校验？零回归重构有 byte-identity 证据？

任一不过 → 修正后再收尾。

---
## 附：domain 示例（把新激活接进 per_token fp8 MoE）
一个完整跑通主流程的压缩示例（重点是"怎么定位该改哪层、哪层已现成",不是激活本身）：
- **规格**：MoE g1u1,a8w8 per_token fp8(QuantType=per_token),激活=目标门控激活;输出 bf16;oracle=torch fp32 同公式 + per_token 反量化,cos_sim≥0.999;arch=gfx942（per_token fp8=普通 fp8 mfma fnuz,原生支持,无需 MX）。
- **first green（先查现状最大化复用）**：PTPC 路径上有**两个独立 codegen 门控**（走哪个 kernel tag 看一组 quant_type 列表、include 哪个 cuh 后缀看另一组）——别串成一条因果链。`grep <act>_and_mul <kernel>.hpp` 确认 epilogue **已有**该激活分支（→ CK 不用改,用 grep 把"假设有"变"确认有",避开 §7 坑）。真正缺口往往是 `f8 × per_token × 该激活` 的 **codegen 实例数 = 0**。
- **最小改动**：补该实例循环（~15 行,照同 quant 现有段改,不污染既有覆盖）;epilogue/dispatch 复用,0 改。
- **验证+闸门**：强制 rebuild → 对拍 torch fp32 cos_sim ~0.9999（与已覆盖激活同级,fp8 下 checkAllclose 可能 failed 属正常）;三道闸过（cos_sim PASS / 实例正确生成 / 既有激活不回归）→ KEEP 记账本;全程守 GPU 纪律,验证通过前不 commit、不 re-pin。
