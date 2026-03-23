#!/usr/bin/env python3
"""Generate month, quarter, or year history summaries."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import html
from pathlib import Path
from typing import Any

from .history import (
    DEFAULT_HISTORY_DIR,
    REASON_CATEGORIES,
    STREAM_LABELS,
    ensure_history_dirs,
    infer_reason_category,
    load_jsonl,
)
from .templates import load_css


STATUS_LABELS = {
    "completed": "Completed",
    "partial": "Partially Done",
    "moved": "Moved",
    "incomplete": "Incomplete",
    "conditional": "Conditional",
    "pending_sync": "Pending Sync",
    "unsynced": "Unsynced",
    "planned": "Planned",
}

STATUS_CLASSES = {
    "completed": "status-completed",
    "partial": "status-partial",
    "moved": "status-moved",
    "incomplete": "status-incomplete",
    "conditional": "status-conditional",
    "pending_sync": "status-pending-sync",
    "unsynced": "status-unsynced",
    "planned": "status-planned",
}

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML summary from archived planner history.")
    parser.add_argument("--period", choices=("month", "quarter", "year"), required=True)
    parser.add_argument("--target", help="Target period, e.g. 2026-03, 2026-Q1, or 2026.")
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR, help="History archive directory.")
    parser.add_argument("--output", help="Output HTML path.")
    parser.add_argument("--time-zone", default="Asia/Shanghai", help="Display time zone label.")
    return parser.parse_args()


def today_local() -> dt.date:
    return dt.date.today()


def default_target(period: str, today: dt.date) -> str:
    if period == "month":
        return today.strftime("%Y-%m")
    if period == "quarter":
        quarter = (today.month - 1) // 3 + 1
        return f"{today.year}-Q{quarter}"
    return today.strftime("%Y")


def period_bounds(period: str, target: str) -> tuple[dt.date, dt.date, str]:
    if period == "month":
        year_text, month_text = target.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        start = dt.date(year, month, 1)
        if month == 12:
            end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
        return start, end, f"{year}-{month:02d}"
    if period == "quarter":
        year_text, quarter_text = target.split("-Q", 1)
        year = int(year_text)
        quarter = int(quarter_text)
        start_month = (quarter - 1) * 3 + 1
        start = dt.date(year, start_month, 1)
        if quarter == 4:
            end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            end = dt.date(year, start_month + 3, 1) - dt.timedelta(days=1)
        return start, end, f"{year} Q{quarter}"
    year = int(target)
    return dt.date(year, 1, 1), dt.date(year, 12, 31), str(year)


def parse_sort_dt(record: dict[str, Any]) -> dt.datetime:
    if record.get("planned_start"):
        return dt.datetime.fromisoformat(record["planned_start"])
    return dt.datetime.combine(dt.date.fromisoformat(record["event_date"]), dt.time.min)


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record)
    item["event_day"] = dt.date.fromisoformat(item["event_date"])
    item["sort_dt"] = parse_sort_dt(item)
    item["has_precise_time"] = bool(item.get("planned_start"))
    item["status_label"] = STATUS_LABELS.get(item.get("status", "planned"), "Planned")
    item["status_class"] = STATUS_CLASSES.get(item.get("status", "planned"), "status-planned")
    item["stream_label"] = STREAM_LABELS.get(item.get("stream", "general"), item.get("stream", "General"))
    item["reason_category"] = item.get("reason_category") or infer_reason_category(item.get("title", ""), item.get("status_note", ""))
    return item


def status_badge(record: dict[str, Any]) -> str:
    return f"<span class=\"status-badge {record['status_class']}\">{html.escape(record['status_label'])}</span>"


def compact_note(text: str, limit: int = 100) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def compute_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "completed": sum(1 for item in records if item.get("status") in {"completed", "partial"}),
        "moved": sum(1 for item in records if item.get("status") in {"moved", "incomplete"}),
        "conditional": sum(1 for item in records if item.get("status") == "conditional"),
        "unsynced": sum(1 for item in records if item.get("status") in {"pending_sync", "unsynced"}),
    }


def reason_counts(records: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter = Counter(
        item.get("reason_category", "Unspecified")
        for item in records
        if item.get("status") in {"moved", "incomplete"}
    )
    return [(reason, counter.get(reason, 0)) for reason in REASON_CATEGORIES if counter.get(reason, 0)]


def render_reason_bars(counts: list[tuple[str, int]]) -> str:
    if not counts:
        return "<div class=\"empty-state\">No moved or incomplete records were archived for this period.</div>"
    max_count = max(count for _, count in counts) or 1
    rows = []
    for reason, count in counts:
        width = max(10, int((count / max_count) * 100))
        rows.append(
            "<div class=\"reason-row\">"
            f"<div class=\"reason-label\">{html.escape(reason)}</div>"
            f"<div class=\"reason-track\"><div class=\"reason-fill\" style=\"width:{width}%\"></div></div>"
            f"<div class=\"reason-value\">{count}</div>"
            "</div>"
        )
    return "".join(rows)


def render_stream_stats(records: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record.get("stream", "general")].append(record)
    cards = []
    for stream_id, label in STREAM_LABELS.items():
        items = grouped.get(stream_id, [])
        if not items:
            continue
        counts = Counter(item.get("status", "planned") for item in items)
        cards.append(
            "<article class=\"stream-card\">"
            f"<h3>{html.escape(label)}</h3>"
            f"<p>{len(items)} records</p>"
            "<div class=\"stream-line\">"
            f"<span>{counts.get('completed', 0) + counts.get('partial', 0)} done</span>"
            f"<span>{counts.get('moved', 0) + counts.get('incomplete', 0)} moved</span>"
            f"<span>{counts.get('conditional', 0)} conditional</span>"
            f"<span>{counts.get('pending_sync', 0) + counts.get('unsynced', 0)} unsynced</span>"
            "</div>"
            "</article>"
        )
    return "".join(cards) or "<div class=\"empty-state\">No workstream records were archived for this period.</div>"


def month_week_buckets(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    buckets = []
    cursor = start
    while cursor <= end:
        bucket_end = min(end, cursor + dt.timedelta(days=6 - cursor.weekday()))
        buckets.append({"start": cursor, "end": bucket_end, "label": f"{cursor:%b %d} - {bucket_end:%b %d}"})
        cursor = bucket_end + dt.timedelta(days=1)
    return buckets


def quarter_week_buckets(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    buckets = []
    cursor = start
    index = 1
    while cursor <= end:
        bucket_end = min(end, cursor + dt.timedelta(days=6))
        buckets.append({"start": cursor, "end": bucket_end, "label": f"W{index:02d}", "subtitle": f"{cursor:%b %d} - {bucket_end:%b %d}"})
        index += 1
        cursor = bucket_end + dt.timedelta(days=1)
    return buckets


def year_month_buckets(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    buckets = []
    cursor = start
    while cursor <= end:
        month_end = dt.date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1) - dt.timedelta(days=1)
        buckets.append({"start": cursor, "end": month_end, "label": MONTH_LABELS[cursor.month - 1]})
        cursor = month_end + dt.timedelta(days=1)
    return buckets


def render_bucket_overview(records: list[dict[str, Any]], buckets: list[dict[str, Any]], title: str, subtitle: str) -> str:
    grouped: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        for index, bucket in enumerate(buckets):
            if bucket["start"] <= record["event_day"] <= bucket["end"]:
                grouped[record["stream"]][index].append(record)
                break
    head = "".join(
        "<div class=\"overview-head-cell\">"
        f"<strong>{html.escape(bucket['label'])}</strong>"
        f"{('<small>' + html.escape(bucket['subtitle']) + '</small>') if bucket.get('subtitle') else ''}"
        "</div>"
        for bucket in buckets
    )
    rows = []
    for stream_id, label in STREAM_LABELS.items():
        cells = []
        has_content = False
        for index, _bucket in enumerate(buckets):
            cell_items = grouped.get(stream_id, {}).get(index, [])
            if cell_items:
                has_content = True
            bullets = []
            for item in sorted(cell_items, key=lambda entry: entry["sort_dt"])[:4]:
                bullets.append(
                    "<li>"
                    f"{status_badge(item)}"
                    f"<span>{html.escape(compact_note(item['title'], 40))}</span>"
                    "</li>"
                )
            cell_html = "<ul>" + "".join(bullets) + "</ul>" if bullets else "<div class=\"cell-empty\"></div>"
            cells.append(f"<div class=\"overview-cell\">{cell_html}</div>")
        if not has_content:
            continue
        rows.append(
            "<div class=\"overview-row\">"
            f"<div class=\"overview-stream\"><strong>{html.escape(label)}</strong><small>{len(grouped.get(stream_id, {}))} active buckets</small></div>"
            f"<div class=\"overview-grid\">{''.join(cells)}</div>"
            "</div>"
        )
    rows_html = "".join(rows) if rows else "<div class=\"empty-state\">No archived records in this period.</div>"
    return (
        "<section class=\"panel\">"
        f"<div class=\"panel-head\"><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>"
        "<div class=\"overview-shell\">"
        "<div class=\"overview-row overview-head\">"
        "<div class=\"overview-stream overview-stream-head\">Workstream</div>"
        f"<div class=\"overview-grid overview-grid-head\">{head}</div>"
        "</div>"
        f"{rows_html}"
        "</div>"
        "</section>"
    )


def render_daily_review(records: list[dict[str, Any]], start: dt.date, end: dt.date) -> str:
    grouped: dict[dt.date, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["event_day"]].append(record)
    cards = []
    cursor = start
    while cursor <= end:
        items = sorted(grouped.get(cursor, []), key=lambda entry: entry["sort_dt"])
        lines = []
        for item in items:
            time_label = item["sort_dt"].strftime("%H:%M") if item["has_precise_time"] else "No time"
            note_html = f"<p class=\"review-note\">{html.escape(compact_note(item.get('status_note', ''), 80))}</p>" if item.get("status_note") else ""
            lines.append(
                "<li>"
                f"<div class=\"review-line-top\"><span>{html.escape(time_label)}</span>{status_badge(item)}</div>"
                f"<strong>{html.escape(item['title'])}</strong>"
                f"<p>{html.escape(item['stream_label'])}</p>"
                f"{note_html}"
                "</li>"
            )
        day_html = "<ul>" + "".join(lines) + "</ul>" if lines else "<div class=\"empty-state small\">No archived records for this day.</div>"
        cards.append(
            f"<article class=\"review-card\" id=\"day-{cursor.isoformat()}\">"
            f"<h3>{cursor:%b %d}</h3><p class=\"review-sub\">{WEEKDAY_LABELS[cursor.weekday()]}</p>"
            f"{day_html}"
            "</article>"
        )
        cursor += dt.timedelta(days=1)
    return (
        "<section class=\"panel\">"
        "<div class=\"panel-head\"><h2>Daily Review</h2><p>Day-level execution history for the selected month.</p></div>"
        f"<div class=\"review-grid\">{''.join(cards)}</div>"
        "</section>"
    )


def render_group_review(records: list[dict[str, Any]], buckets: list[dict[str, Any]], title: str, subtitle: str) -> str:
    cards = []
    for bucket in buckets:
        items = [record for record in records if bucket["start"] <= record["event_day"] <= bucket["end"]]
        items.sort(key=lambda entry: entry["sort_dt"])
        lines = []
        for item in items[:8]:
            note_html = f"<p class=\"review-note\">{html.escape(compact_note(item.get('status_note', ''), 96))}</p>" if item.get("status_note") else ""
            lines.append(
                "<li>"
                f"<div class=\"review-line-top\"><span>{html.escape(item['stream_label'])}</span>{status_badge(item)}</div>"
                f"<strong>{html.escape(item['title'])}</strong>"
                f"{note_html}"
                "</li>"
            )
        label = bucket["label"] if bucket.get("subtitle") is None else f"{bucket['label']} · {bucket['subtitle']}"
        anchor_id = (
            f"week-{bucket['start'].isocalendar().year}-W{bucket['start'].isocalendar().week:02d}"
            if title.startswith("Weekly")
            else f"month-{bucket['start']:%Y-%m}"
        )
        bucket_html = "<ul>" + "".join(lines) + "</ul>" if lines else "<div class=\"empty-state small\">No archived records for this bucket.</div>"
        cards.append(
            f"<article class=\"review-card\" id=\"{anchor_id}\">"
            f"<h3>{html.escape(label)}</h3>"
            f"{bucket_html}"
            "</article>"
        )
    return (
        "<section class=\"panel\">"
        f"<div class=\"panel-head\"><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>"
        f"<div class=\"review-grid\">{''.join(cards)}</div>"
        "</section>"
    )


def render_html(period: str, label: str, records: list[dict[str, Any]], time_zone: str, start: dt.date, end: dt.date) -> str:
    stats = compute_stats(records)
    reasons = reason_counts(records)
    if period == "month":
        buckets = month_week_buckets(start, end)
        overview_html = render_bucket_overview(
            records,
            buckets,
            "Weekly Overview",
            "Month view keeps weekly buckets for the timeline and daily cards for detail.",
        )
        review_html = render_daily_review(records, start, end)
    elif period == "quarter":
        buckets = quarter_week_buckets(start, end)
        overview_html = render_bucket_overview(
            records,
            buckets,
            "Weekly Roadmap",
            "Quarter view compresses the timeline into week-by-week movement.",
        )
        review_html = render_group_review(
            records,
            buckets,
            "Weekly Review",
            "Weekly review lists what was completed, moved, or left pending.",
        )
    else:
        buckets = year_month_buckets(start, end)
        overview_html = render_bucket_overview(
            records,
            buckets,
            "Monthly Milestones",
            "Year view shows milestone density by month rather than day-level timing.",
        )
        review_html = render_group_review(
            records,
            buckets,
            "Monthly Review",
            "Monthly review summarizes the archived movement for each month.",
        )
    overview_column_count = max(1, len(buckets))
    css = load_css("history_summary.css")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Planner History Summary · {html.escape(label)}</title>
  <style>
    {css}
    .overview-grid-head {{ grid-template-columns: repeat({overview_column_count}, minmax(160px, 1fr)); }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <p>Research Planner Template · History Summary</p>
          <h1>{html.escape(label)}</h1>
          <p>{html.escape(period.title())} summary generated from archived planner records. Display time zone: {html.escape(time_zone)}.</p>
        </div>
      </div>
      <div class="hero-stats">
        <article class="stat-card"><span>Done</span><strong>{stats['completed']}</strong></article>
        <article class="stat-card"><span>Moved / Incomplete</span><strong>{stats['moved']}</strong></article>
        <article class="stat-card"><span>Conditional</span><strong>{stats['conditional']}</strong></article>
        <article class="stat-card"><span>Pending Sync</span><strong>{stats['unsynced']}</strong></article>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Delay Reasons</h2><p>Automatic classification based on titles and status notes.</p></div>
      {render_reason_bars(reasons)}
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Workstream Stats</h2><p>Archived record counts grouped by workstream.</p></div>
      <div class="stream-grid">{render_stream_stats(records)}</div>
    </section>
    {overview_html}
    {review_html}
  </div>
</body>
</html>"""


def main() -> int:
    args = parse_args()
    target = args.target or default_target(args.period, today_local())
    start, end, label = period_bounds(args.period, target)
    history_paths = ensure_history_dirs(Path(args.history_dir).expanduser().resolve())
    records = [normalize_record(record) for record in load_jsonl(history_paths["events"]) if start <= dt.date.fromisoformat(record["event_date"]) <= end]
    records.sort(key=lambda item: (item["event_day"], item["sort_dt"], item["stream"], item["title"]))
    html_text = render_html(args.period, label, records, args.time_zone, start, end)
    output_path = Path(args.output).expanduser().resolve() if args.output else history_paths["summaries"] / f"{target}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
