#!/usr/bin/env python3
"""Query AMD LLM Gateway UsageStats API and print a per-model cost report.

Reads API key from env var AMD_LLM_GATEWAY_KEY.
See SKILL.md for full API spec, error modes, and DBNull bug workaround.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_ENDPOINT = "https://llm-api.amd.com/api/UsageStats"
ENV_KEY_NAME = "AMD_LLM_GATEWAY_KEY"


def parse_time(s: str) -> str:
    """Validate input time string. Accept YYYY-MM-DD or full ISO 8601.

    Returns the original string (URL encoding is done at request build time).
    Raises ValueError on bad format.
    """
    if not s:
        raise ValueError("empty time string")
    # Try date-only
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        pass
    # Try ISO 8601 (Python 3.7+ fromisoformat handles offsets like +08:00,
    # but not trailing 'Z'; normalize Z -> +00:00 for validation).
    candidate = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        datetime.fromisoformat(candidate)
    except ValueError as e:
        raise ValueError(f"unrecognized time format: {s!r} ({e})")
    return s


def default_range():
    """Default query window: last 30 days, end snapped to UTC today 00:00.

    The end-clamp avoids the server-side DBNull bug that fires when the
    range crosses into the current UTC day.
    """
    now_utc = datetime.now(timezone.utc)
    end = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=30)
    # YYYY-MM-DD form is sufficient (interpreted as UTC midnight).
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def build_url(start: str, end: str) -> str:
    """Build the request URL with proper URL encoding (+ -> %2B)."""
    qs = urllib.parse.urlencode({"start": start, "end": end}, quote_via=urllib.parse.quote)
    return f"{API_ENDPOINT}?{qs}"


def fetch(url: str, api_key: str, timeout: float = 30.0):
    """Send GET request. Returns (status_code, parsed_json_or_raw_text).

    Does not raise on HTTP 4xx; the caller inspects status + body to
    distinguish the three 404 modes documented in SKILL.md.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": api_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
    try:
        return status, json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return status, body


def classify_error(status, body):
    """Return a human-readable error string, or None if response looks OK.

    Maps the three failure modes documented in SKILL.md `## Error Modes`.
    """
    # DBNull bug: HTTP 200 with errorMessage in body
    if status == 200 and isinstance(body, dict):
        msg = body.get("errorMessage")
        if msg and "DBNull" in msg:
            return (
                "服务端 DBNull bug：查询区间跨入当前 UTC 日。"
                "请把 --end 限制到 UTC 今日 00:00 之前（= BJT 08:00 之前），"
                "或等 UTC 日切换后再查。\n"
                f"原始 errorMessage: {msg}"
            )
        # Some responses may also signal partial null totals
        if body.get("totalRequests") is None and body.get("application") is None:
            return f"未识别的 200 响应，缺关键字段。原始 body: {body!r}"

    if status == 404:
        # Try to differentiate the two 404 modes
        if isinstance(body, dict):
            text = json.dumps(body, ensure_ascii=False)
        else:
            text = str(body)
        if "Not found any usage" in text:
            return (
                "区间内无用量记录（HTTP 404 但属合法响应）。"
                "可能是该应用在此区间确实没有调用，或 start/end 时区算错了。"
            )
        if "Resource not found" in text or "resource" in text.lower():
            return (
                "Gateway 路由级 404：通常是 start/end 参数缺失或 URL 拼错。"
                f"原始响应: {text}"
            )
        return f"HTTP 404，未匹配已知模式。原始响应: {text}"

    if status >= 400:
        return f"HTTP {status} 错误。原始响应: {body!r}"

    return None


def render_report(data: dict) -> str:
    """Render the parsed JSON into a human-readable text report."""
    lines = []
    app = data.get("application") or {}
    lines.append("=" * 70)
    lines.append(f"Application : {app.get('name', '<unknown>')}")
    lines.append(f"Cost Center : {app.get('costCenter', '<unknown>')}")
    lines.append(f"API Key     : {app.get('apiKey', '<unknown>')}")
    dr = data.get("dateRange") or {}
    lines.append(f"Date Range  : {dr.get('start', '?')}  →  {dr.get('end', '?')}  (UTC)")
    lines.append("-" * 70)
    lines.append(f"Total Requests       : {data.get('totalRequests')}")
    lines.append(f"Total Tokens         : {data.get('totalTokens')}")
    lines.append(f"Approx Charge (USD)  : {data.get('approxChargeInUSD')}")
    lines.append("-" * 70)

    # stats: dict of service-name -> list of per-model dicts
    stats = data.get("stats") or {}
    rows = []
    for service_name, models in stats.items():
        if not isinstance(models, list):
            continue
        for m in models:
            if not isinstance(m, dict):
                continue
            rows.append({
                "service": service_name,
                "model": m.get("model", "<unknown>"),
                "requests": m.get("totalRequests", 0) or 0,
                "prompt": m.get("promptTokens", 0) or 0,
                "completion": m.get("completionTokens", 0) or 0,
                "tokens": m.get("totalTokens", 0) or 0,
                "usd": m.get("approxChargeInUSD", 0.0) or 0.0,
            })

    # Sort by USD descending (primary), then service+model
    rows.sort(key=lambda r: (-float(r["usd"]), r["service"], r["model"]))

    if not rows:
        lines.append("(明细为空)")
    else:
        header = f"{'Service':<20} {'Model':<32} {'Reqs':>8} {'Prompt':>10} {'Compl':>10} {'Tokens':>12} {'USD':>10}"
        lines.append(header)
        lines.append("-" * len(header))
        for r in rows:
            try:
                usd_s = f"{float(r['usd']):.4f}"
            except (TypeError, ValueError):
                usd_s = str(r["usd"])
            lines.append(
                f"{str(r['service'])[:20]:<20} "
                f"{str(r['model'])[:32]:<32} "
                f"{r['requests']:>8} "
                f"{r['prompt']:>10} "
                f"{r['completion']:>10} "
                f"{r['tokens']:>12} "
                f"{usd_s:>10}"
            )
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Query AMD LLM Gateway UsageStats API.",
    )
    default_start, default_end = default_range()
    parser.add_argument(
        "--start",
        default=default_start,
        help=f"区间开始（含），YYYY-MM-DD 或 ISO 8601。默认 {default_start}（近 30 天）",
    )
    parser.add_argument(
        "--end",
        default=default_end,
        help=f"区间结束（不含），YYYY-MM-DD 或 ISO 8601。默认 {default_end}（UTC 今日 00:00，避开 DBNull bug）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="打印原始 JSON 响应（便于二次处理），不走 human-readable report",
    )
    args = parser.parse_args(argv)

    # Validate time formats early
    try:
        start = parse_time(args.start)
        end = parse_time(args.end)
    except ValueError as e:
        print(f"参数错误：{e}", file=sys.stderr)
        return 2

    api_key = os.environ.get(ENV_KEY_NAME)
    if not api_key:
        print(
            f"环境变量 {ENV_KEY_NAME} 未设置。\n"
            "请先 export AMD_LLM_GATEWAY_KEY=<your-api-key>，"
            "key 到 https://llm.amd.com/ 领取。",
            file=sys.stderr,
        )
        return 3

    url = build_url(start, end)
    status, body = fetch(url, api_key)

    err = classify_error(status, body)
    if err:
        print(f"请求失败（HTTP {status}）：\n{err}", file=sys.stderr)
        return 4

    if args.json:
        if isinstance(body, (dict, list)):
            print(json.dumps(body, ensure_ascii=False, indent=2))
        else:
            print(body)
        return 0

    if not isinstance(body, dict):
        print(f"响应不是 JSON 对象，无法生成报告。原始内容：\n{body}", file=sys.stderr)
        return 5

    print(render_report(body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
