# Install Notes — llm-usage skill

部署时间：2026-05-08
部署方式：agent-team（teammate-1 实现 + teammate-2 验证）

## 部署产物

- `SKILL.md` — 用户审核原文，逐字写入（4.0 KB / 76 行）
- `llm_usage.py` — Python 标准库实现，约 230 行
  - 仅依赖 `urllib` / `json` / `argparse` / `datetime` / `os` / `sys`
  - 无需 `pip install` 任何包

## 离线自测（teammate-1 已完成）

21 个 assertion 全 PASS，覆盖：
- `parse_time` 三种合法格式 + garbage 拒绝
- `default_range` 计算（end = UTC 今日 00:00，span = 30 天）
- `build_url` 的 `+` → `%2B` 编码
- `classify_error` 三种 404 / DBNull 分支
- `render_report` USD 降序排序
- `main` 缺 key (rc=3) / 坏时间 (rc=2)

退出码：0=成功 / 2=参数错误 / 3=缺 key / 4=API 失败 / 5=非 JSON

## API spec 验证状态

**已端到端验证（2026-05-08）**。Lead 用 `container.env` 中的 APIM key 实跑：

| # | 条款 | 结果 |
|---|---|---|
| V1 | `application.{name, costCenter, apiKey}` 字段在顶层 | ✅ 全部存在（apiKey 脱敏 `63df712c***...`） |
| V3 | `stats.<Service>[]` 每项含 model/totalRequests/promptTokens/completionTokens/totalTokens/approxChargeInUSD | ✅ 全部存在 |
| V6 | `404 Not found any usage` = 合法"无用量"响应 | ✅ `--start 2026-05-07 --end 2026-05-08` 触发 |
| V9 | `totalRequests=10000` 响应级 cap | ✅ 30 天窗口实测 = 10000 整数 |
| UTC | `dateRange.end` 总是 UTC | ✅ `end=2026-05-07` echo 为 `2026-05-07T00:00:00` |
| 排序 | 明细按 USD 降序 | ✅ Sonnet-4.6($972) → Opus-4.7($177) → Opus-4.6($62) → Haiku-4.5($4) |
| 错误分类 | `classify_error` 三种 404 / DBNull 分支 | ✅ V6 实测落入正确分支 |

**SKILL.md spec 准确，无需修改。**

环境就绪：Python 3.12.3 / urllib 标准库 / curl 8.5.0 / `https://llm-api.amd.com` 可达。

**KEY 来源**：`/home/junlin12/.claude/container.env` 的 `ANTHROPIC_CUSTOM_HEADERS`（同一把 APIM key 既走 chat completion 也走 UsageStats），但**默认未 export 为 `AMD_LLM_GATEWAY_KEY`**。日常调用 `llm_usage.py` 前需手动 `export AMD_LLM_GATEWAY_KEY=<key>` 或写到 `~/.bashrc`。

## 用户首次自验清单（设 KEY 后跑）

```bash
# 0. 设置 KEY（粘贴时小心 shell history）
export AMD_LLM_GATEWAY_KEY='<your-apim-key>'
echo -n "$AMD_LLM_GATEWAY_KEY" | wc -c   # 应非 0；不要 echo 内容

# 1. 最小成功调用：昨天到今天 UTC 00:00（避开 DBNull bug 与 10000-cap）
curl -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2026-05-07&end=2026-05-08" \
  | python3 -m json.tool | head -60

# 2. 字段结构验证（V1+V3）
curl -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2026-05-07&end=2026-05-08" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('app keys:', list(d.get('application',{}).keys()))
print('dateRange:', d.get('dateRange'))
svc=d.get('stats') or {}
for name, items in svc.items():
    if items:
        print(f'service={name} sample item keys:', list(items[0].keys())); break
"

# 3. 缺 start → 404 Gateway 短 JSON（V4）
curl -i -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?end=2026-05-08" | head -20

# 4. 缺 end → 同上 404（V5）
curl -i -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2026-05-07" | head -20

# 5. 无用量 → 404 业务响应（V6）
curl -i -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2020-01-01&end=2020-01-02" | head -20

# 6. DBNull bug（V8）—— 预期 HTTP 200 + errorMessage 含 "DBNull"
curl -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2026-05-07&end=2026-05-09" \
  | python3 -m json.tool | head -20

# 7. 时区转 UTC（V2）—— 带 +08:00 应被 echo 为 UTC
curl -s -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  "https://llm-api.amd.com/api/UsageStats?start=2026-05-07T00:00:00%2B08:00&end=2026-05-07T12:00:00%2B08:00" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('dateRange'))"
# 预期：dateRange.start ≈ "2026-05-06T16:00:00"
```

## 部署后用脚本调用

```bash
# 默认（近 30 天，end = 今日 UTC 00:00）
python3 ~/.claude/skills/llm-usage/llm_usage.py

# 明确区间
python3 ~/.claude/skills/llm-usage/llm_usage.py --start 2026-05-07 --end 2026-05-08

# 原始 JSON
python3 ~/.claude/skills/llm-usage/llm_usage.py --json
```

## --auto-segment（wave 3 新增）

绕开 `totalRequests=10000` 响应级 cap：把 `[start, end)` 自动切成多个短段（默认每段 6 天）逐段查询；任何段命中 cap 自动二分递归到 1 天粒度；最后按 `(service, model)` 累加。

### 用法

```bash
# 30 天精确聚合（默认 6 天/段）
AMD_LLM_GATEWAY_KEY=<key> python3 ~/.claude/skills/llm-usage/llm_usage.py \
  --auto-segment --start 2026-04-08 --end 2026-05-07

# 调短段长（用量大时建议 3 天/段，控制每段 reqs < cap）
... --auto-segment --start ... --end ... --segment-days 3

# 聚合后的 JSON（含 `_aggregation` 元数据：每段 start/end/reqs/cap_triggered/depth）
... --auto-segment --json --start ... --end ...
```

约束：`--auto-segment` 只接受 `YYYY-MM-DD` 形式的 `--start/--end`（按 UTC 解释）；`--segment-days` 须在 `[1, 7]`；不带 `--auto-segment` 时行为完全不变（兼容旧调用）。

### 实测精确数对比（30 天窗口 2026-04-08 → 2026-05-07）

| 指标 | 单次查询（旧） | --auto-segment（精确） | 差额 |
|---|---:|---:|---:|
| `totalRequests` | 10,000（CAP 截断） | **12,643** | **+2,643（+26.4%）** |
| `totalTokens` | 2,301,429,390 | **2,519,890,615** | **+218,461,225（+9.5%）** |
| `approxChargeInUSD` | $1,215.88（截断） | **$1,535.70** | **+$319.82（+26.3%）** |
| API 调用数 | 1 | 5（无递归触发） | +4 |

按 model 明细差异最大的是 **Opus-4.7**：单次查询 1,696 reqs / $177.30，auto-segment 4,339 reqs / $497.13。Sonnet-4.6 / Opus-4.6 / Haiku-4.5 三者两种模式数字一致，**说明 cap 在响应级按时间顺序截断，截断点正好落在 Opus-4.7 调用密集的窗口内**（4/26 之后大量 Opus-4.7 调用未被纳入单次查询的 10000 桶）。

### 错误处理

- 某段返回 V6（HTTP 404 + "Not found any usage"）→ 该段 reqs/usd/tokens=0，不算失败
- 某段返回 DBNull / Gateway 路由 404 / 真实 5xx → 整个聚合任务 fail（exit 4），错误信息含触发段
- `--segment-days` 超出 `[1,7]` 或 `--start >= --end` → exit 2

### 何时用

- 怀疑被 10000-cap 截断（单次查询返回的 `totalRequests` 正好等于 10000，明细和 USD 也按比例打折）
- 需要月报 / 季报级别的精确数字（accounting / 报销 / 内部 charge-back）
- 需要拿到聚合 JSON 做后续分析（`--json` 输出含 `_aggregation.segments` 元数据，每段都可追溯）

不需要用：单次查询返回 `totalRequests < 10000` 的窗口（数据完整，加段反而多调 API）。

### Wave 3 验证

| 项 | 结果 |
|---|---|
| 离线 unit test | 14/14 PASS（`/tmp/agent_team/llm-usage-skill/test_auto_segment.py`，无真实 HTTP，mock fetch 覆盖切段+递归+no-usage+硬错误） |
| 端到端非 `--auto-segment` | 30 天窗口 → 10000 reqs / $1215.88（与 wave 1 V9 cap 实测一致，向后兼容 OK） |
| 端到端 `--auto-segment` | 30 天窗口 → 12,643 reqs / $1,535.70 / 2.52B tokens（与 wave 2 teammate-3 聚合脚本数字 byte-identical） |
| 4 模型明细 | 全部匹配 wave 2 teammate-3 §4 表 |
| 调用次数 | 5（5 段，无 cap 触发，无递归） |

## Progress 索引（ephemeral，重启后失效）

- `/tmp/agent_team/llm-usage-skill/progress/teammate-1.md` — wave 1 实现细节 + 离线自测结果
- `/tmp/agent_team/llm-usage-skill/progress/teammate-2.md` — wave 1 环境检查 + V1-V10 完整清单
- `/tmp/agent_team/llm-usage-skill/progress/teammate-3.md` — wave 2 30 天精确聚合（aggregate.py 原始实现）
- `/tmp/agent_team/llm-usage-skill/progress/teammate-4.md` — wave 2 git push 操作记录
- `/tmp/agent_team/llm-usage-skill/progress/teammate-6.md` — wave 3 --auto-segment 实现 + 验证 + push（本次）
- `/tmp/agent_team/llm-usage-skill/test_llm_usage.py` — wave 1 21 项 self-test
- `/tmp/agent_team/llm-usage-skill/test_auto_segment.py` — wave 3 14 项 self-test（无 HTTP）
