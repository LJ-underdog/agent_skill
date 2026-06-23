# ROCM-21707 复现与定位步骤

> 目标机:失败机 `smci350-rck-g03-b12-03`(AmazonLinux MI350X / gfx950),用测试用户 `amd` 账户。
> 这台机 amdgpu 驱动 + ROCm 已装好(正因如此才挂),**不用重装**。
> 失败现象:`ck_hipgraph_dropout_tests` 的 `tile_example_fmha_bwd -s=4096` 在 SQA harness 下被判 soft hang。
> 本文把"复现"和"区分根因(真 hang vs harness 误杀 vs 驱动/CWSR)"合在一套步骤里。

---

## 0. 切到测试用户

```
sudo su - amd
```
`amd` 有 GPU 组(video/render)+ NOPASSWD sudo,和 SQA nightly 跑测试时一致。

---

## A. 版本对齐核对(先确认这台 = 失败配置)

```
echo "host:   $(hostname)"
rocminfo | grep -m1 "gfx9"
rocm-smi --showproductname 2>/dev/null | grep -i "series\|MI3"
ls -d /opt/rocm* ; cat /opt/rocm/.info/version 2>/dev/null
cat /sys/module/amdgpu/version
uname -r
grep PRETTY_NAME /etc/os-release
```

逐项对齐目标(失败时的配置):

| 项 | 应为 |
|---|---|
| hostname | smci350-rck-g03-b12-03 |
| GPU arch | gfx950 (MI350X) |
| ROCm | 7.13.0 或 7.14.0 |
| amdgpu(内核驱动) | 6.19.x  ← 被怀疑的关键变量 |
| OS | AmazonLinux 2023 |

重点:`cat /sys/module/amdgpu/version` 必须是 6.19.x。若已不是(驱动被升/降过),这台现在可能复现不出来,先记下这个值。

---

## B. 编译 CK(失败的那个 commit)

### B0. 环境 + 预检(全部秒级,失败立刻停,别白等 37 分钟)

```
export ROCM=/opt/rocm                 # 若 A 步是别的路径就改这里
export PATH=$ROCM/bin:$PATH
export LD_LIBRARY_PATH=$ROCM/lib:$LD_LIBRARY_PATH

# 自动探测 clang++(两种常见布局)
CLANGXX=$(ls $ROCM/llvm/bin/clang++ $ROCM/lib/llvm/bin/clang++ 2>/dev/null | head -1)
echo "CLANGXX=$CLANGXX"                # 必须非空,否则下面别往下走
"$CLANGXX" --version | head -1

# ninja(更快;AmazonLinux 没有就装)
command -v ninja >/dev/null || sudo dnf install -y ninja-build
ninja --version

# GPU 可见
rocminfo | grep -m1 gfx950

# 内存够不够(每个重 TU 可能吃几 GB,据此定 -j)
free -g | awk '/Mem:/{print "RAM total/avail(GB): "$2"/"$7}'
```

### B1. 取源码(建议全新 clone;先确认没有 nightly 正在用 /home/amd/rocm-libraries)

```
cd /home/amd
rm -rf rocm-libraries
git clone -b develop https://github.com/ROCm/rocm-libraries rocm-libraries
cd rocm-libraries
git reset --hard f000f7786e9ac67510549f4d17784d327705e295
git log -1 --oneline                  # 确认 HEAD = f000f7786e
```

### B2. 配置(Ninja)+ 只编 bwd(挂的是 bwd,fwd 是过的,省时间)

```
mkdir -p projects/composablekernel/build && cd projects/composablekernel/build
cmake -G Ninja \
      -DBUILD_DEV=ON -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_FLAGS="-O3 -ftemplate-backtrace-limit=0" \
      -DGPU_TARGETS=gfx950 \
      -DCMAKE_CXX_COMPILER="$CLANGXX" \
      -DCMAKE_PREFIX_PATH=$ROCM \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ..

# 并发别用满核:fmha bwd 实例(尤其 maxk_256)单 TU 吃几 GB,满核会 OOM 被 kill。
# -j 32 是稳妥起点;若 dmesg/日志出现 OOM-killed,降到 -j 16。
ninja -j 32 tile_example_fmha_bwd

# (可选,只有要完整复现 fwd 那两条命令时才编;fwd 不挂)
# ninja -j 32 tile_example_fmha_fwd
```
说明:
- 只编 `tile_example_fmha_bwd`,省掉 fwd 那批实例。
- 用了 Ninja(比 Makefile 快);去掉了 `CMAKE_VERBOSE_MAKEFILE`(Ninja 下无效且刷屏)。
- `BUILD_DEV=ON` 与 SQA 一致;**若配置/编译因 `-Werror` 类警告报错,改 `-DBUILD_DEV=OFF` 再来**。
- bwd 目标编译约几十分钟(取决于 -j 和机器),正常。

---

## C. 复现(直接跑,不经 SQA harness —— 这同时就是"脱 harness"实验)

第二个终端盯 GPU:
```
watch -n1 rocm-smi
```
第三个终端盯内核日志(看有没有 cwsr / runlist / hang):
```
sudo dmesg -w
```

主终端跑 —— **关键就是这条 bwd**(SQA 在 ~3 秒杀它;这里直接跑、让它跑完):
```
cd /home/amd/rocm-libraries/projects/composablekernel/build
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=4096 -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=4096 -d=64 -drop_prefs=0 -drop_seed=10 -drop_offset=1234
```
(可选,只有当 B2 也编了 fwd、要完整复现那 4 条时再跑;fwd 不挂)
```
./bin/tile_example_fmha_fwd -b=1 -h=8 -s=4096 -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
./bin/tile_example_fmha_fwd -b=1 -h=8 -s=4096 -d=64 -drop_prefs=0 -drop_seed=10 -drop_offset=1234
```

判读(这一步直接分根因):
- bwd 几十秒内跑完 + 打印 `valid:y` → 不是 GPU hang;SQA 失败只是 harness 的 ~3 秒看门狗误杀了慢的 CPU 校验 → test-infra 问题。
- bwd 卡到 600s 超时 / rocm-smi 卡住 / dmesg 报 hang → 真 hang → 进 D。

---

## D. 后续单变量实验(确认是真 hang 后再做)

实验 1 — seqlen 扫描(看是不是只有大 s 才挂、阈值在哪):
```
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=512  -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=1024 -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=2048 -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
time timeout 600 ./bin/tile_example_fmha_bwd -b=1 -h=8 -s=4096 -d=64 -drop_prefs=1 -drop_seed=10 -drop_offset=1234
```

实验 3 — 关 CWSR(先跟 owner 确认机器没在跑别的 job,这步会把整机 GPU 驱动卸掉):
```
sudo modprobe -r amdgpu && sudo modprobe amdgpu cwsr_enable=0
cat /sys/module/amdgpu/parameters/cwsr_enable        # 应为 0
# 然后重跑 bwd s=4096;若此时跑通 → CWSR 实锤
# 恢复默认:
sudo modprobe -r amdgpu && sudo modprobe amdgpu
```

---

## 判读总结(把结果对到结论)

| 现象 | 结论 | 下一步 |
|---|---|---|
| C 步 bwd 直接跑能完成 valid:y(几十秒) | 不是 GPU hang,是 harness ~3s 看门狗误杀慢校验 | 提 test-infra:加大 `--test_timeout`,bug 不在 CK/驱动 |
| C 步 bwd 真 hang;实验1 小 s 过、大 s 才挂 | 大-seqlen 特定问题(CK 大-s 路径 或 驱动在大-s 下) | 做实验3 区分 |
| 实验3 关 CWSR 后跑通 | CWSR/驱动回归实锤 | 交 driver team,引 ROCm #5590/#5724/#6165 |
| 实验3 关 CWSR 后仍挂 | 排除 CWSR;回到 CK 大-s 路径排查 | 缩小到具体 GEMM/pipeline |

## 注意
- 这是共享 SQA 机:实验 3 的 `modprobe -r amdgpu` 会卸掉整机 GPU 驱动,务必先确认无其他 job 并知会 owner。
- 用哪个用户名不影响这个 GPU/内核级 hang 的复现,关键只是 GPU 组 + sudo(`amd` 都有)。
- 关键命令是 C 步那条 `time timeout 600 ... tile_example_fmha_bwd ... -s=4096`,一跑就当场分清"真 hang"还是"harness 误杀"。
