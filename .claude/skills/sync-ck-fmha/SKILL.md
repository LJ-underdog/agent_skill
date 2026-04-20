---
name: sync-ck-fmha
description: >
  Sync AITER with a CK (Composable Kernel) FMHA API change from ROCm/rocm-libraries.
  Use when a PR in ROCm/rocm-libraries changes the fmha_fwd / fmha_batch_prefill /
  fmha_fwd_splitkv API (traits structs, args structs, kernel codegen), and you need
  to update the AITER call chain accordingly.
  Trigger phrases: "sync CK", "update CK submodule", "integrate CK PR", "CK FMHA 变更".
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, WebFetch
---

# Sync AITER with CK FMHA API Changes

This skill guides through syncing AITER when CK's FMHA API changes. The CK submodule
(`3rdparty/composable_kernel`) is a subtree-split mirror of `projects/composablekernel/`
in the `ROCm/rocm-libraries` monorepo.

## Prerequisites

Ask the user for:
1. The CK PR URL (e.g., `https://github.com/ROCm/rocm-libraries/pull/XXXX`)
2. The branch name (e.g., `ck/author/feature-name`)

---

## Phase 1: Understand What Changed in CK

### 1a. Fetch the PR diff

```bash
# Read the PR page to identify changed files and their semantics
# WebFetch: https://github.com/ROCm/rocm-libraries/pull/<PR>/files
```

Focus on files under `projects/composablekernel/example/ck_tile/01_fmha/`:
- `fmha_fwd.hpp` — public API structs (`fmha_*_traits`, `fmha_*_args`), changed fields/params
- `codegen/ops/fmha_*.py` — new codegen variants (e.g., new `F_xxx` field → new `_xxx`/`_nxxx` suffix)
- `include/ck_tile/ops/fmha/kernel/` — kernel template changes
- `include/ck_tile/ops/fmha/pipeline/` — pipeline implementation changes

**Key questions to answer before writing any code:**
- Which public structs changed? (`fmha_fwd_traits`, `fmha_batch_prefill_traits`, etc.)
- What new fields/template params were added?
- Does the codegen generate new kernel variants? What naming suffix?
- What is the semantic meaning of each new field?

### 1b. Read analogous existing implementations

**Before touching any code**, read how the analogous existing fwd kernels handle the same
concept. For example, if adding `sink_size` to batch_prefill, first read:

```bash
grep -n "sink_size\|has_sink\|sink" csrc/py_itfs_ck/mha_varlen_fwd_kernels.cu | head -20
grep -n "sink_size\|has_sink\|sink" csrc/py_itfs_ck/mha_fwd_kernels.cu | head -20
```

This reveals the existing convention. **Do not guess — read the code.**

---

## Phase 2: Sync the Submodule

The CK submodule points to `ROCm/composable_kernel` (standalone), but FMHA development
happens in `ROCm/rocm-libraries` (monorepo). Sync via shallow clone + rsync.

```bash
# Step 1: shallow clone the PR branch
git clone --branch <BRANCH_NAME> --depth=1 \
    https://github.com/ROCm/rocm-libraries.git /tmp/rocm_libs_pr

# Step 2: verify CK is at expected path
ls /tmp/rocm_libs_pr/projects/composablekernel/include/ck_tile/ops/fmha/

# Step 3: restore .git pointer if it gets deleted by rsync
# (rsync --delete removes the .git file in the submodule)
echo "gitdir: ../../.git/modules/3rdparty/composable_kernel" \
    > 3rdparty/composable_kernel/.git

# Step 4: create a branch and sync files
git -C 3rdparty/composable_kernel checkout -b <feature-branch>
rsync -a --delete /tmp/rocm_libs_pr/projects/composablekernel/ \
    3rdparty/composable_kernel/
echo "gitdir: ../../.git/modules/3rdparty/composable_kernel" \
    > 3rdparty/composable_kernel/.git

# Step 5: commit
git -C 3rdparty/composable_kernel add -A
git -C 3rdparty/composable_kernel commit \
    -m "[rocm-libraries] ROCm/rocm-libraries#<PR_NUMBER> (commit <SHA>) <title>"
```

---

## Phase 3: Trace the Full Data Flow

**Golden rule: before writing code, draw the complete chain and confirm every hop.**

AITER's FMHA call chain (using batch_prefill as example):

```
Python:  mha_batch_prefill_func(... new_param ...)
           ↓ cmdGenFunc_mha_batch_prefill  → module name / blob filter
           ↓ @compile_ops JIT
C++:     aiter::torch_itfs::mha_batch_prefill(..., int new_param, ...)   [PyBind]
           ↓ MHA_BATCH_PREFILL_PYBIND macro                              [rocm_ops.hpp]
           ↓ get_ck_fmha_batch_prefill_args(...)                         [py_itfs_ck/]
           ↓ fmha_batch_prefill_args args{};  args.new_field = ...
           ↓ aiter::mha_batch_prefill(args, ...)                         [cpp_itfs/]
           ↓ get_mha_batch_prefill_traits(..., bool new_flag)
           ↓ fmha_batch_prefill(traits, args, stream)                    [CK API]
           ↓ code-generated dispatch → FmhaBatchPrefillKernel<...>       [GPU]
```

For each hop, answer: **Where does the new value come from? Where does it go?**

### Files to check for each layer

| Layer | Files |
|-------|-------|
| Python stub | `aiter/ops/mha.py` — function signature, `cmdGenFunc_*` |
| PyBind macro | `csrc/include/rocm_ops.hpp` — `MHA_*_PYBIND` |
| C++ declaration | `csrc/include/torch/mha_*.h` |
| AITER traits/args | `csrc/include/mha_fwd.h` — `mha_*_traits`, `mha_fwd_args` |
| Torch interface | `csrc/py_itfs_ck/mha_*_kernels.cu` |
| C++ dispatch | `csrc/cpp_itfs/mha_fwd*.cu` |
| CK API | `3rdparty/composable_kernel/example/ck_tile/01_fmha/fmha_fwd.hpp` |

### Verify completeness with grep

After making changes, run:
```bash
grep -rn "<new_field_name>" \
    aiter/ops/mha.py \
    csrc/include/mha_fwd.h \
    csrc/include/rocm_ops.hpp \
    csrc/include/torch/mha_batch_prefill.h \
    csrc/py_itfs_ck/mha_batch_prefill_kernels.cu \
    csrc/cpp_itfs/mha_fwd_batch_prefill.cu
```

Every layer must appear in the output. **Missing layers = bug.**

---

## Phase 4: Key Change Patterns

### 4a. New template parameter in `fmha_*_traits_` (e.g., `kHasFoo_`)

CK change: hardcoded `false` → real template param `bool kHasFoo_ = false`
Codegen change: generates `_foo` / `_nfoo` variants

AITER changes needed:
1. **`mha_fwd.h`**: Add `bool has_foo` param to `mha_*_traits` constructor, pass to CK base
2. **`cpp_itfs/`**: `bool has_foo = args.foo_size > 0;` (or whatever drives it), pass to traits
3. **`py_itfs_ck/`**: Set `args.foo_field` from inputs; init args as `args{}` (zero-init)
4. **`rocm_ops.hpp`**: Add `py::arg("foo_param")` to PyBind macro
5. **`torch/mha_*.h`**: Add param to C++ declaration
6. **`aiter/ops/mha.py`**: Update **all four** Python functions — `cmdGenFunc_*`, the
   `@compile_ops` stub, `_mha_batch_prefill` (internal wrapper), and `mha_batch_prefill_func`
   (user-facing entry point). All four need `foo_param: int = 0` and must pass it through.
   Use `has_effective_foo = foo_param > 0 and <conditions>` in `cmdGenFunc` for module name.

   > **Common miss**: developers update `cmdGenFunc` and the stub but forget
   > `_mha_batch_prefill` and `mha_batch_prefill_func`. The parameter silently defaults to 0
   > and the feature never activates from the user-facing API.

### 4b. New field in `fmha_*_args`

Read the struct definition carefully — it's **aggregate-initialized**. Field order matters.
Check the new field's position relative to existing fields and ensure AITER's
`get_ck_fmha_*_args()` sets it in the right place.

```bash
# Read the full struct in new CK to verify field order
grep -n "struct fmha_batch_prefill_args" \
    3rdparty/composable_kernel/example/ck_tile/01_fmha/fmha_fwd.hpp
```

### 4c. New codegen variant suffix (e.g., `_sink`/`_nsink`)

In `cmdGenFunc_*` Python:
```python
# Match the conditions the C++ mask/args logic uses
has_effective_foo = foo_size > 0 and (causal or not (window == (-1, -1)))
if has_effective_foo:
    md_name += "_foo"
    filter_fwd += "_foo*"
else:
    md_name += "_nfoo"
    filter_fwd += "_nfoo*"
```

**Critical**: Python module name selection must exactly match what C++ `has_foo` evaluates to.
Mismatches cause "invalid argument" errors at dispatch (kernel variant not found).

### 4d. Semantic independence of new fields

Before wiring a new field, clarify: is it **independent** of other fields, or **derived** from them?

Example: `sink_ptr` (virtual token logit pointer) and `sink_size` (sink phase KV count) are
**independent** — the kernel reads `sink_ptr` unconditionally, regardless of `sink_size`.
Incorrectly coupling them causes subtle numerical differences.

---

## Phase 5: Verification

### 5a. Verify codegen works

```bash
mkdir -p /tmp/ck_codegen_test
python3 3rdparty/composable_kernel/example/ck_tile/01_fmha/generate.py \
    -d <kernel_type> --receipt <N> \
    --filter "*<variant_suffix>*" \
    --output_dir /tmp/ck_codegen_test
ls /tmp/ck_codegen_test/
```

Check that `_foo` and `_nfoo` variant files are generated.

### 5b. Verify module name generation

```python
python3 -c "
from aiter.ops.mha import cmdGenFunc_mha_batch_prefill
import torch
q = torch.empty(1, 8, 128, dtype=torch.bfloat16)
k = torch.empty(1, 1, 128, dtype=torch.bfloat16)
ip = torch.empty(2, dtype=torch.int32)
pi = torch.empty(1, dtype=torch.int32)
# Test both branches
r0 = cmdGenFunc_mha_batch_prefill(q,k,k,ip,ip,pi, 1,16, 0.,None,0.,False,False,-1,-1, 0,False,False)
r1 = cmdGenFunc_mha_batch_prefill(q,k,k,ip,ip,pi, 1,16, 0.,None,0.,False,True,-1,-1,  4,False,False)
print('nfoo:', r0['md_name'])
print('foo: ', r1['md_name'])
"
```

### 5c. Compile and run

Trigger JIT compilation (avoid `block=True` waiting — let it run in background):

```bash
AITER_REBUILD=1 python3 -c "
from aiter.ops.mha import mha_batch_prefill_func
import torch
# minimal call to trigger compilation
...
" > /tmp/compile_test.txt 2>&1 &
```

Check for compilation errors: `grep -i "error\|undefined" /tmp/compile_test.txt`

### 5d. Numerical verification against torch reference

For the new feature (e.g., `has_foo`):
1. **Read the CK pipeline/kernel code** to understand exact semantics
2. **Read the CK fmha_fwd_runner.hpp** for the reference computation (lines around `init_foo`)
3. Implement the torch reference
4. Run calibration cases first (feature disabled = known-good baseline)
5. Run feature-enabled case and compare

```python
# Calibration pattern:
out_no_feature = run_ck(... foo_param=0 ...)
ref_no_feature = torch_ref(... foo_param=0 ...)
assert (out_no_feature - ref_no_feature).abs().max() < atol  # baseline correct

out_with_feature = run_ck(... foo_param=N ...)
ref_with_feature = torch_ref_with_foo(... foo_param=N ...)
assert (out_with_feature - ref_with_feature).abs().max() < atol  # feature correct
```

Use discriminating test values (not all-zeros) to ensure differences surface.

---

## Phase 6: Add Tests to `op_tests/test_batch_prefill.py`

Follow the existing test structure:

```python
def ref_masked_attention_with_foo(query, key, value, foo_param, ...):
    """Torch reference implementing the new feature semantics."""
    ...

def run_batch_prefill_foo(batch_size, ..., foo_param, dtype, seed):
    """Run CK kernel + reference, compare with get_tolerances()."""
    kv_cache = build_paged_kv_cache(...)
    k_ref, v_ref = extract_kv_caches(kv_cache, contiguous_kv=True)
    k_cache, v_cache = apply_kv_layout(k_ref, v_ref, ..., "vectorized")
    o_ref = [ref_masked_attention_with_foo(...) for each batch]
    out = aiter.mha_batch_prefill_func(... foo_param=foo_param ...)
    rtol, atol = get_tolerances(dtype)
    assert_output_matches_reference(out, q_indptr_cpu, o_ref, rtol, atol)

@pytest.mark.parametrize("foo_param", [4, 16])
@pytest.mark.parametrize("dtype", [torch.bfloat16, torch.float16])
...
def test_batch_prefill_foo(...):
    run_batch_prefill_foo(...)
```

Run ALL parametrized combinations programmatically before committing:
```python
# In a background task:
for combo in itertools.product(batch_sizes, head_pairs, qo_lens, ...):
    result = run_batch_prefill_foo(*combo)
    assert result["status"] == "passed"
```

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Didn't read analogous impl first | Wrong derivation logic (`ptr != nullptr` vs `size > 0`) | Always read existing similar kernel first |
| Missed a layer in data flow | "invalid argument" or dispatch mismatch | `grep -rn new_field` across all layers |
| Stale `.so` cache | Old signature causing arg shift, subtle wrong results | `rm aiter/jit/mha_*.so` before testing |
| Stale build lock | Compilation hangs forever | `find aiter/jit/build -name "lock" && rm ...` |
| CK aggregate init order wrong | Compile error or wrong field set | Read full struct, count fields manually |
| Python `sink_size > 0 and causal` condition | Module name doesn't match C++ has_foo | Trace C++ mask logic, match exactly in Python |
| Running long compilations blocking conversation | User waits minutes | Always use `run_in_background=true` for compile/test |

---

## Commit Convention

```bash
git add 3rdparty/composable_kernel \
        aiter/ops/mha.py \
        csrc/cpp_itfs/mha_fwd_batch_prefill.cu \
        csrc/include/mha_fwd.h \
        csrc/include/rocm_ops.hpp \
        csrc/include/torch/mha_batch_prefill.h \
        csrc/py_itfs_ck/mha_batch_prefill_kernels.cu \
        op_tests/test_batch_prefill.py

git commit -m "[CK] <short description>

Update CK submodule to ROCm/rocm-libraries#<PR> (commit <SHA>) which <what changed>.

AITER-side changes:
- <layer>: <what changed and why>
- ...

Verified: <what was tested, max_diff values>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
