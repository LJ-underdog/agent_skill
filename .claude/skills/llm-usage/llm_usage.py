#!/usr/bin/env python3
"""Query AMD LLM Gateway UsageStats API and print a per-model cost report.

Reads API key from env var AMD_LLM_GATEWAY_KEY.
See SKILL.md for full API spec, error modes, and DBNull bug workaround.

--auto-segment mode (wave 3): split [start, end) into segments (default 6 days
each) to bypass the response-level 10000-totalRequests cap. Any segment that
hits the cap is recursively bisected down to 1-day granularity. All segments
are then aggregated by (service, model).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

API_ENDPOINT = "https://llm-api.amd.com/api/UsageStats"
ENV_KEY_NAME = "AMD_LLM_GATEWAY_KEY"
CAP = 10000  # observed response-level totalRequests cap


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


def parse_date_only(s: str) -> date:
    """Strict YYYY-MM-DD -> date object. Raises ValueError otherwise.

    Used by --auto-segment mode, which only operates at day granularity.
    """
    return datetime.strptime(s, "%Y-%m-%d").date()


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


def is_no_usage(status, body) -> bool:
    """True if response is the legal V6 'no usage in window' 404."""
    if status != 404:
        return False
    if isinstance(body, dict):
        text = json.dumps(body, ensure_ascii=False)
    else:
        text = str(body)
    return "Not found any usage" in text


def render_report(data: dict, title_extra: str = "") -> str:
    """Render the parsed JSON into a human-readable text report.

    `title_extra` is appended to the top banner (used by --auto-segment to
    annotate "Aggregated from N segments").
    """
    lines = []
    app = data.get("application") or {}
    lines.append("=" * 70)
    lines.append(f"Application : {app.get('name', '<unknown>')}")
    lines.append(f"Cost Center : {app.get('costCenter', '<unknown>')}")
    lines.append(f"API Key     : {app.get('apiKey', '<unknown>')}")
    dr = data.get("dateRange") or {}
    lines.append(f"Date Range  : {dr.get('start', '?')}  →  {dr.get('end', '?')}  (UTC)")
    if title_extra:
        lines.append(title_extra)
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


# ---------------------------------------------------------------------------
# --auto-segment: split a date window into ≤N-day segments and recursively
# bisect any segment that hits the 10000 totalRequests cap.
# ---------------------------------------------------------------------------


def split_initial_segments(start_d: date, end_d: date, seg_days: int):
    """Split [start_d, end_d) into segments of length ≤ seg_days.

    Returns a list of (seg_start, seg_end) date pairs covering the full window
    with no gaps and no overlaps. The last segment may be shorter than
    seg_days. Raises ValueError if start_d >= end_d or seg_days < 1.
    """
    if seg_days < 1:
        raise ValueError("seg_days must be >= 1")
    if start_d >= end_d:
        raise ValueError(f"start_d ({start_d}) must be < end_d ({end_d})")
    out = []
    cur = start_d
    while cur < end_d:
        nxt = cur + timedelta(days=seg_days)
        if nxt > end_d:
            nxt = end_d
        out.append((cur, nxt))
        cur = nxt
    return out


def query_segment(start_d: date, end_d: date, api_key: str, segments_log: list,
                  agg_models: dict, totals: dict, depth: int = 0):
    """Query [start_d, end_d). Recursively bisect if cap is hit.

    Mutates `segments_log`, `agg_models`, `totals`. Returns None.
    Raises RuntimeError on hard error (V4/V5/V8/真实 5xx).
    """
    span_days = (end_d - start_d).days
    url = build_url(start_d.isoformat(), end_d.isoformat())
    status, body = fetch(url, api_key)

    # V6 legal "no usage" → contribute 0
    if is_no_usage(status, body):
        segments_log.append({
            "start": start_d.isoformat(), "end": end_d.isoformat(),
            "depth": depth, "reqs": 0, "tokens": 0, "usd": 0.0,
            "cap_triggered": False, "note": "no usage",
        })
        return

    # Hard errors: DBNull, Gateway 404, missing param, true 5xx, non-JSON
    err = classify_error(status, body)
    if err:
        raise RuntimeError(
            f"段 [{start_d} → {end_d}] 失败 (HTTP {status}): {err}"
        )

    if not isinstance(body, dict) or "totalRequests" not in body:
        raise RuntimeError(
            f"段 [{start_d} → {end_d}] 响应缺 totalRequests: {body!r}"
        )

    total_reqs = body.get("totalRequests") or 0
    total_tokens = body.get("totalTokens") or 0
    total_usd = body.get("approxChargeInUSD") or 0.0
    capped = (total_reqs == CAP)

    # Cap hit + can still subdivide → bisect
    if capped and span_days > 1:
        segments_log.append({
            "start": start_d.isoformat(), "end": end_d.isoformat(),
            "depth": depth, "reqs": total_reqs, "tokens": total_tokens,
            "usd": total_usd, "cap_triggered": True,
            "note": "CAP triggered, subdividing (not counted)",
        })
        mid = start_d + timedelta(days=span_days // 2)
        if mid == start_d:
            mid = start_d + timedelta(days=1)
        query_segment(start_d, mid, api_key, segments_log, agg_models, totals, depth + 1)
        query_segment(mid, end_d, api_key, segments_log, agg_models, totals, depth + 1)
        return

    # Accumulate (leaf segment)
    totals["totalRequests"] += total_reqs
    totals["totalTokens"] += total_tokens
    totals["approxChargeInUSD"] += total_usd
    note = "CAP at 1-day, lower bound" if (capped and span_days <= 1) else ""
    segments_log.append({
        "start": start_d.isoformat(), "end": end_d.isoformat(),
        "depth": depth, "reqs": total_reqs, "tokens": total_tokens,
        "usd": total_usd, "cap_triggered": capped, "note": note,
    })

    # Per-(service, model) accumulation
    stats = body.get("stats") or {}
    for svc_name, items in stats.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            model = it.get("model", "<unknown>")
            key = (svc_name, model)
            slot = agg_models.setdefault(key, {
                "requests": 0, "promptTokens": 0, "completionTokens": 0,
                "totalTokens": 0, "approxChargeInUSD": 0.0,
            })
            slot["requests"] += it.get("totalRequests") or 0
            slot["promptTokens"] += it.get("promptTokens") or 0
            slot["completionTokens"] += it.get("completionTokens") or 0
            slot["totalTokens"] += it.get("totalTokens") or 0
            slot["approxChargeInUSD"] += it.get("approxChargeInUSD") or 0.0

    # Cache application metadata for the synthesized report
    app = body.get("application")
    if app and "application" not in totals:
        totals["application"] = app


def aggregate_window(start_d: date, end_d: date, api_key: str, seg_days: int):
    """Run the full --auto-segment aggregation. Returns a synthesized dict
    shaped like the single-shot API response so render_report works.
    """
    initial_segments = split_initial_segments(start_d, end_d, seg_days)
    segments_log = []
    agg_models = {}
    totals = {"totalRequests": 0, "totalTokens": 0, "approxChargeInUSD": 0.0}

    for s, e in initial_segments:
        query_segment(s, e, api_key, segments_log, agg_models, totals, depth=0)

    # Build synthesized response
    stats_out = {}
    for (svc, model), v in agg_models.items():
        stats_out.setdefault(svc, []).append({
            "model": model,
            "totalRequests": v["requests"],
            "promptTokens": v["promptTokens"],
            "completionTokens": v["completionTokens"],
            "totalTokens": v["totalTokens"],
            "approxChargeInUSD": round(v["approxChargeInUSD"], 4),
        })

    leaf_count = sum(1 for s in segments_log if not s["cap_triggered"] or s["note"].startswith("CAP at 1-day"))
    synth = {
        "application": totals.get("application") or {},
        "dateRange": {
            "start": f"{start_d.isoformat()}T00:00:00",
            "end": f"{end_d.isoformat()}T00:00:00",
        },
        "totalRequests": totals["totalRequests"],
        "totalTokens": totals["totalTokens"],
        "approxChargeInUSD": round(totals["approxChargeInUSD"], 4),
        "stats": stats_out,
        "_aggregation": {
            "mode": "auto-segment",
            "segment_days": seg_days,
            "initial_segments": len(initial_segments),
            "total_api_calls": len(segments_log),
            "leaf_segments": leaf_count,
            "segments": segments_log,
        },
    }
    return synth


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


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
    parser.add_argument(
        "--auto-segment",
        action="store_true",
        help="自动按 --segment-days 切窗口逐段查询并聚合（绕开 10000-cap）。"
             "对触发 cap 的段递归二分到 1 天粒度。仅支持 YYYY-MM-DD 形式的 start/end。",
    )
    parser.add_argument(
        "--segment-days",
        type=int,
        default=6,
        help="--auto-segment 模式下初始段长（天，默认 6，须 >=1 且 <=7）",
    )
    args = parser.parse_args(argv)

    # Validate time formats early
    try:
        start = parse_time(args.start)
        end = parse_time(args.end)
    except ValueError as e:
        print(f"参数错误：{e}", file=sys.stderr)
        return 2

    # Validate --segment-days range up front (before KEY check) so bad CLI
    # input fails as parameter error (rc=2) regardless of env state.
    if args.auto_segment and (args.segment_days < 1 or args.segment_days > 7):
        print(f"参数错误：--segment-days 必须在 [1, 7] 范围内（当前 {args.segment_days}）",
              file=sys.stderr)
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

    # ---- Auto-segment branch ---------------------------------------------
    if args.auto_segment:
        try:
            start_d = parse_date_only(start)
            end_d = parse_date_only(end)
        except ValueError as e:
            print(f"参数错误：--auto-segment 仅接受 YYYY-MM-DD 形式的 --start/--end ({e})",
                  file=sys.stderr)
            return 2
        if start_d >= end_d:
            print(f"参数错误：--start ({start_d}) 必须早于 --end ({end_d})", file=sys.stderr)
            return 2

        try:
            synth = aggregate_window(start_d, end_d, api_key, args.segment_days)
        except RuntimeError as e:
            print(f"--auto-segment 聚合失败：\n{e}", file=sys.stderr)
            return 4

        if args.json:
            print(json.dumps(synth, ensure_ascii=False, indent=2))
            return 0

        agg_meta = synth["_aggregation"]
        title_extra = (
            f"Aggregated from {agg_meta['total_api_calls']} segments "
            f"(auto-segment mode, segment_days={agg_meta['segment_days']}, "
            f"initial={agg_meta['initial_segments']})"
        )
        print(render_report(synth, title_extra=title_extra))
        # Brief per-segment trace appended after the main report
        print()
        print("Per-segment trace:")
        for s in agg_meta["segments"]:
            indent = "  " * s["depth"]
            usd_s = f"${s['usd']:.2f}" if s["usd"] is not None else "ERR"
            tag = " [CAP]" if s["cap_triggered"] else ""
            note = f"  ({s['note']})" if s["note"] else ""
            print(f"  {indent}[{s['start']} → {s['end']}] reqs={s['reqs']} usd={usd_s}{tag}{note}")
        return 0

    # ---- Single-shot branch (default, unchanged) -------------------------
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
