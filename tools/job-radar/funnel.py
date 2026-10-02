#!/usr/bin/env python3
"""Read-only Job Radar funnel health using the shared recruiting notes/config."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import radar

SYNC_PATH = Path(__file__).resolve().parents[1] / "recruiting-sync" / "sync.py"
SPEC = importlib.util.spec_from_file_location("job_workspace_recruiting_sync", SYNC_PATH)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


@dataclass(frozen=True)
class FunnelEntry:
    priority: str
    title: str
    queued_on: str | None
    deadline: str | None


def recorded_date(pattern: str, text: str) -> str | None:
    values = set(re.findall(pattern, text, re.I))
    if len(values) > 1:
        raise sync.SyncError("queue: conflicting recorded dates on one task")
    if not values:
        return None
    value = values.pop()
    try:
        dt.date.fromisoformat(value)
    except ValueError as error:
        raise sync.SyncError("queue: invalid recorded date") from error
    return value


def current_queue_entries(queue_text: str, config) -> tuple[FunnelEntry, ...]:
    lines = queue_text.splitlines(keepends=True)
    start, end = sync.section(lines, config.markdown["queue_heading"], "queue")
    dated_sections: dict[int, str | None] = {}
    section_date = None
    for index in range(start, end):
        if re.match(r"^#{3,6}\s+", lines[index]):
            match = re.match(r"^#{3,6}\s+(\d{4}-\d{2}-\d{2})(?=[：:\s]|$)", lines[index])
            section_date = match.group(1) if match else None
        dated_sections[index] = section_date
    entries = []
    for entry in sync.queue_entries(queue_text, config):
        if not re.match(r"^- \[ \]", entry["primary"]):
            continue
        if not entry["supported"]:
            raise sync.SyncError(f"queue: unsupported pending task at line {entry['line']}")
        priority = re.match(r"^- \[ \] (#p[012])", entry["primary"]).group(1)
        # Verification dates are not evidence of when a task entered the queue.
        queued_on = recorded_date(
            r"(?:queued(?:\s+on)?|added(?:\s+on)?|入队(?:日期)?|加入日期)\s*[:：*`\s]*(\d{4}-\d{2}-\d{2})",
            entry["block"],
        ) or dated_sections[entry["start"]]
        if queued_on:
            sync.date(queued_on, "queue.queued_on")
        deadline = recorded_date(
            r"(?:deadline|closes?(?:\s+on)?|apply\s+by|截止(?:时间|日期)?|有效至)\s*[:：*`\s]*(\d{4}-\d{2}-\d{2})",
            entry["block"],
        )
        entries.append(FunnelEntry(priority, entry["company"] + "｜" + entry["role"], queued_on, deadline))
    return tuple(entries)


def build_funnel_health(root: Path, config_path: str | Path,
                        today: dt.date | None = None) -> dict:
    root = sync.repository(root)
    config = sync.load_config(root, config_path)
    notes = sync.notes(root, config)
    queue_text, history_text = notes[config.queue], notes[config.history]
    history_rows, _ = sync.history_rows(history_text, config)
    _, category_issues = sync.count_rows(history_rows, config)
    if category_issues:
        raise sync.SyncError("; ".join(category_issues))
    entries = current_queue_entries(queue_text, config)
    report_date = today or dt.date.today()
    recent_start = report_date - dt.timedelta(days=6)
    annotation_dates = set(re.findall(r"(?m)^#{1,6}\s+(\d{4}-\d{2}-\d{2})(?=[：:\s]|$)", queue_text))
    recent_queued, missing_annotations = 0, []
    for value in sorted(annotation_dates):
        batch_date = dt.date.fromisoformat(value)
        if not recent_start <= batch_date <= report_date:
            continue
        annotations = radar.queue_disposition_annotations(queue_text, value)
        if not annotations:
            missing_annotations.append(value)
            continue
        if len(annotations) != 1:
            raise sync.SyncError(f"queue: ambiguous disposition annotation for {value}")
        annotation = annotations[0]
        total = sum(annotation[key] for key in radar.SYNC_DISPOSITIONS)
        if annotation.get("evaluated", total) != total:
            raise sync.SyncError(f"queue: inconsistent disposition total for {value}")
        recent_queued += annotation["queued"]
    stale, urgent, expired = [], [], []
    for entry in entries:
        if entry.queued_on and (report_date - dt.date.fromisoformat(entry.queued_on)).days > 7:
            stale.append(asdict(entry))
        if entry.deadline:
            days_left = (dt.date.fromisoformat(entry.deadline) - report_date).days
            if days_left < 0:
                expired.append(asdict(entry))
            elif days_left <= 3:
                urgent.append(asdict(entry))
    return {
        "report_date": report_date.isoformat(),
        "current_count": len(entries),
        "p0_count": sum(entry.priority == "#p0" for entry in entries),
        "p1_count": sum(entry.priority == "#p1" for entry in entries),
        "p2_count": sum(entry.priority == "#p2" for entry in entries),
        "recent_queued_count": recent_queued,
        "recent_history_count": sum(recent_start <= dt.date.fromisoformat(row["cells"][0]) <= report_date
                                    for row in history_rows),
        "stale_entries": stale, "urgent_entries": urgent, "expired_entries": expired,
        "unknown_dates": {
            "queue_added_on": sum(entry.queued_on is None for entry in entries),
            "queue_deadline": sum(entry.deadline is None for entry in entries),
            "history_submitted_on": sum(row["cells"][1] == config.markdown["unknown_date"] for row in history_rows),
            "recent_batch_dates_without_disposition": missing_annotations,
        },
        "date_basis": {
            "queue_inflow": "Recorded queued counts in dated disposition annotations; missing batches are not inferred.",
            "history_flow": "Confirmed-on column records entry confirmation, not the actual submission date.",
            "urgent": "Date-only approximation: today through the third following calendar date, inclusive.",
        },
    }


def render_funnel_health(health: dict) -> str:
    lines = [f"# {health['report_date']} Funnel health", "",
             f"- Pending: {health['current_count']} (#p0 {health['p0_count']} / #p1 {health['p1_count']} / #p2 {health['p2_count']})",
             f"- Recorded batch inflow, last 7 days: {health['recent_queued_count']}",
             f"- Recorded application confirmations, last 7 days: {health['recent_history_count']}"]
    for key, heading in (("stale_entries", "In queue over 7 days"),
                         ("urgent_entries", "Deadline today through the next 3 dates"),
                         ("expired_entries", "Recorded deadline has passed")):
        lines += ["", f"## {heading}", ""]
        lines += [f"- {row['priority']} {radar.markdown_inline(row['title'])}; queued: {row['queued_on'] or 'unknown'}; deadline: {row['deadline'] or 'unknown'}"
                  for row in health[key]] or ["- None recorded"]
    unknown = health["unknown_dates"]
    lines += ["", "## Date coverage", "",
              f"- Pending tasks without a recorded entry date: {unknown['queue_added_on']}",
              f"- Pending tasks without a recorded deadline: {unknown['queue_deadline']}",
              f"- History rows without an actual submission date: {unknown['history_submitted_on']}",
              "- Recent batch dates without disposition counts: " + (", ".join(unknown["recent_batch_dates_without_disposition"]) or "None recorded"),
              "", *["- " + value for value in health["date_basis"].values()], ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="The user's Git workspace root")
    parser.add_argument("--config", default=sync.DEFAULT_CONFIG, help="Existing recruiting-sync config, relative to root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        health = build_funnel_health(args.root, args.config)
        print(json.dumps(health, ensure_ascii=False, indent=2) if args.json else render_funnel_health(health))
        return 0
    except (OSError, ValueError, sync.SyncError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
