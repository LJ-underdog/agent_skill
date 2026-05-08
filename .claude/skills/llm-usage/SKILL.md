---
name: llm-usage
description: Use when the user asks about AMD LLM Gateway token usage, charge-back, cost, or how much an application has spent on Claude/GPT/Gemini via llm.amd.com. Queries the UsageStats API and returns request count, token volume, and approximate USD charge per model for a date range (default last 30 days).
---

# LLM Gateway Usage Stats

查询 AMD LLM Gateway（`llm.amd.com`）的 token 用量与计费，按模型聚合输出。

## When to Use

- 用户问"我这个月用了多少 token / 花了多少钱"
- 用户问 charge-back、cost center、token usage 相关
- 需要核对某个时间段的 LLM 调用成本
- 看哪个模型贡献了大头费用

NOT for: 配额申请、模型白名单查询（去 https://llm.amd.com/ ），或非 AMD LLM Gateway 的其他 API。

## Prerequisites

环境变量 `AMD_LLM_GATEWAY_KEY` 必须已设置（API key，作为 `Ocp-Apim-Subscription-Key` header 发送）。该 key 绑定到一个 application + cost center,查询结果只覆盖该 key 所属应用。

## Usage

直接用 Bash 工具调用脚本：

```bash
# 默认:近 30 天
python3 ~/.claude/skills/llm-usage/llm_usage.py

# 指定区间(仅日期)
python3 ~/.claude/skills/llm-usage/llm_usage.py --start 2026-04-01 --end 2026-05-06

# 小时粒度 + 时区偏移(脚本会自动 URL 编码 `+`)
python3 ~/.claude/skills/llm-usage/llm_usage.py \
  --start "2026-04-30T00:00:00+08:00" --end "2026-05-01T00:00:00+08:00"

# 拿原始 JSON(用于进一步处理)
python3 ~/.claude/skills/llm-usage/llm_usage.py --json
```

输出包含 application 名、cost center、合计请求数 / token / USD,以及按 service+model 排序(按费用降序)的明细表。

## API Reference

- Endpoint: `GET https://llm-api.amd.com/api/UsageStats?start=<iso>&end=<iso>`
- Header: `Ocp-Apim-Subscription-Key: <api-key>`
- `start` 和 `end` **都必填**,少任何一个返回 `404 Resource not found`(Gateway 路由级别 404,不是业务层)
- 时间格式:接受 `YYYY-MM-DD`,也接受完整 ISO 8601 datetime(含小时/分钟),含时区偏移(如 `+08:00`,URL 里 `+` 必须编码成 `%2B`)
- 时区:**裸 datetime 按 UTC 解析**(无时区时 = `Z`)。带偏移会自动转换为 UTC,echo 回的 `dateRange` 总是 UTC
- 返回结构(关键字段):
  - `application.{name, costCenter, apiKey}`
  - `dateRange.{start, end}` — 总是 UTC
  - `totalRequests`, `totalTokens`, `approxChargeInUSD`
  - `stats.<Service>[]` — 每项含 `model`, `totalRequests`, `promptTokens`, `completionTokens`, `totalTokens`, `approxChargeInUSD`
- 文档与 try-it: https://llm.amd.com/api-details#api=amd-llm-webapi-prod&operation=get-api-usagestats

## Error Modes

要区分三种"看起来像 404 / 失败"的响应:

| HTTP / 响应 | 含义 |
|---|---|
| `404 Resource not found`(Gateway 风格短 JSON) | 缺 `start` 或 `end` 参数 |
| `404 Not found any usage of application on given date range.` | 区间内确实无用量(合法响应,HTTP 仍是 404) |
| `200` + `errorMessage: "Unable to cast object of type 'System.DBNull' to type 'System.Int32'."` | 区间跨入**当前 UTC 日**就会触发服务端 bug,`totalRequests` 等字段为 `null`。绕开方法:把 `end` 限制在 UTC 今天 00:00(= BJT 08:00)之前,等 UTC 日切换后再查 |

## Notes

- `totalTokens` 包含 prompt cache read/write 的 token,会显著大于 `prompt + completion` 之和——这是正常的,cache hit 多说明计费效率高
- 单次查询只返回区间总和,不直接支持按天/小时拆分;但**小时粒度过滤是真生效的**(实测平移 12 小时窗口结果不同),所以可以通过"固定 start,逐步推进 end"做累计减法反推每小时/每天用量
- 区间语义:`start` 含、`end` 不含。`start=A&end=B` 返回 `dateRange.end = B 00:00:00`。要覆盖某天全天,end 用次日 00:00
- 默认 30 天查询观察到 `totalRequests` 正好等于 10000,疑似有响应级请求条数上限;区间太大时拿到的明细可能被截断,建议按周/按天拆开查再聚合
- 返回的 `apiKey` 是脱敏的(前 8 位 + `*`),用于确认调用的是哪把 key
