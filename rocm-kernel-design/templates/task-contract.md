# Task Contract — <kernel name>

> 填全再开工。没有 docs/draft.md（并细化出 docs/plan.md）不许动 kernel 代码。

## 1. Objective
<要实现/优化什么 kernel;面向哪个目标芯片 gfx942(MI300/CDNA3) / gfx950(MI350/CDNA4)>

## 2. I/O 规格
<每个 tensor 的 shape + dtype + layout（行主/列主/preshuffle）>

## 3. 量化格式（无量化则 N/A）
<weight/activation dtype、scale 格式(E8M0/fp32)、粒度(per_tensor/per_token/per_1x128/128×128/group-32)、对称性>

## 4. 数学语义
<kernel 算什么,写出公式,含激活/bias/routing 权重>

## 5. Correctness requirements（oracle）
- Oracle: <仓库 reference_*.hpp 路径,或 torch fp32/高精度同公式>
- 判据: cos_sim ≥ <e.g. 0.999>（首选,稳健）+ rel/abs err（报 max/mean,bf16/fp16/fp8 宽容差）
- 不变量: <例如 masked-out 严格 0、deterministic 路逐位可复现>
- 覆盖矩阵: dtype × 模式(batch/jagged/group...) × 开关(causal/mask/softmax/quant...) × 形状边界（做**交叉积**,不只对角线）

## 6. Performance target
<可测目标:TFLOPS / 带宽利用% / 相对 baseline 加速 / 达 X% roofline;没有写 N/A>

## 7. Allowed approaches
<CK/ck_tile/aiter/HIP/Triton;可复用哪些现成 pipeline/policy/实例;约束:不改公共头 / 保持 API / 不动 submodule pin / ...>

## 8. Validation command
```
<一条命令:编译 + 跑对拍,print PASS/FAIL + cos_sim + err 数值>
```

## 9. Evaluation command
```
<一条命令:benchmark,print 性能数字;与 validation 相同则写 "同上">
```

## 10. Promotion criteria（三道闸门）
<① validation PASS（cos_sim 达标无 NaN）② eval 较 baseline 真涨（超噪声）③ 其它已覆盖 case 零回归>

## 11. Target arch / build
- GPU_TARGETS: <gfx942 / gfx950 / 多目标>
- build: `<cmake/make 命令与关键 flags>`
- ROCm 版本: <rocminfo / 版本号>
- 隔离方式: <op-isolate 单算子 / e2e>
