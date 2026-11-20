from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .analytics import summarize, threshold_warnings
from .models import PlantRecord
from .storage import CSV_COLUMNS, REPORTS_DIR, ensure_dirs


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _status_line(s: dict) -> str:
    return (
        f"Total records: {s['total']} | Beds: {s['beds']} | "
        f"Growing: {s['by_status']['growing']} | Planted: {s['by_status']['planted']} | "
        f"Harvested: {s['harvested_count']} | Failed: {s['failed_count']}"
    )


def export_markdown(records: list[PlantRecord], path: Path | None = None) -> Path:
    ensure_dirs()
    target = path or (REPORTS_DIR / f"garden_report_{_stamp()}.md")
    s = summarize(records)
    warnings = threshold_warnings(records)
    lines = [
        "# Community Garden Planner — Executive Summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Overview",
        "",
        _status_line(s),
        "",
        f"- Average days to harvest: **{s['avg_days_to_harvest']}**",
        f"- Total yield: **{s['total_yield_kg']} kg** across {s['harvested_count']} harvested plant(s)",
        f"- Average yield per harvested plant: **{s['avg_yield_kg']} kg**",
        f"- Failure rate: **{s['failure_rate']}%**",
        "",
        "## Plants by Status",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    lines += [f"| {k} | {v} |" for k, v in s["by_status"].items()]
    lines += ["", "## Records by Bed", "", "| Bed | Plants |", "| --- | ---: |"]
    lines += [f"| {k} | {v} |" for k, v in s["by_bed"].items()]
    if s["top_beds_by_yield"]:
        lines += ["", "## Top Beds by Yield", "", "| Bed | Yield (kg) |", "| --- | ---: |"]
        lines += [f"| {b} | {y:.2f} |" for b, y in s["top_beds_by_yield"][:10]]
    if s["harvests_by_month"]:
        lines += ["", "## Harvests by Month", "", "| Month | Harvested |", "| --- | ---: |"]
        lines += [f"| {m} | {c} |" for m, c in s["harvests_by_month"].items()]
    lines += ["", "## Threshold Warnings", ""]
    lines += [f"- {w}" for w in warnings]
    lines += ["", "## All Records", "",
              "| ID | Bed | Plant | Variety | Sown | Status | Expected | Harvested | Yield (kg) | Notes |",
              "| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- |"]
    for r in sorted(records, key=lambda x: (x.bed, x.plant)):
        notes = r.harvest_notes.replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {r.id} | {r.bed} | {r.plant} | {r.variety or '-'} | {r.sown_date} | "
            f"{r.status} | {r.expected_harvest} | {r.harvest_date or '-'} | {r.yield_kg} | {notes or '-'} |"
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def export_text_log(records: list[PlantRecord], path: Path | None = None) -> Path:
    ensure_dirs()
    target = path or (REPORTS_DIR / f"garden_audit_{_stamp()}.txt")
    s = summarize(records)
    width = 100
    lines = [
        "=" * width,
        "COMMUNITY GARDEN PLANNER — AUDIT LOG".center(width),
        f"Generated: {datetime.now().isoformat(timespec='seconds')}".center(width),
        "=" * width,
        "",
        "SUMMARY",
        "-" * width,
        _status_line(s),
        f"Total yield: {s['total_yield_kg']} kg | Avg yield: {s['avg_yield_kg']} kg | "
        f"Avg days to harvest: {s['avg_days_to_harvest']}",
        "",
        "WARNINGS",
        "-" * width,
    ]
    lines += [f"  * {w}" for w in threshold_warnings(records)]
    lines += ["", "RECORDS", "-" * width,
              f"{'ID':>4} {'BED':<8} {'PLANT':<18} {'SOWN':<11} {'STATUS':<10} {'DUE':<11} {'YIELD':>7}"]
    lines += ["-" * width]
    for r in sorted(records, key=lambda x: x.id):
        lines.append(
            f"{r.id:>4} {r.bed:<8} {r.plant[:17]:<18} {r.sown_date:<11} {r.status:<10} "
            f"{r.expected_harvest:<11} {r.yield_kg:>7.2f}"
        )
    lines += ["-" * width, f"End of audit — {len(records)} record(s).", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def export_summary_csv(records: list[PlantRecord], path: Path | None = None) -> Path:
    ensure_dirs()
    target = path or (REPORTS_DIR / f"garden_summary_{_stamp()}.csv")
    s = summarize(records)
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_records", s["total"]])
        writer.writerow(["total_beds", s["beds"]])
        for status, count in s["by_status"].items():
            writer.writerow([f"status_{status}", count])
        writer.writerow(["total_yield_kg", s["total_yield_kg"]])
        writer.writerow(["avg_yield_kg", s["avg_yield_kg"]])
        writer.writerow(["avg_days_to_harvest", s["avg_days_to_harvest"]])
        writer.writerow(["failure_rate_pct", s["failure_rate"]])
        writer.writerow(["overdue_count", len(s["overdue"])])
        writer.writerow(["due_soon_count", len(s["due_soon"])])
        for bed, count in s["by_bed"].items():
            writer.writerow([f"bed_{bed}_records", count])
    return target


def export_records_csv(records: list[PlantRecord], path: Path | None = None) -> Path:
    ensure_dirs()
    target = path or (REPORTS_DIR / f"garden_records_{_stamp()}.csv")
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            row = r.to_dict()
            row["tags"] = "|".join(row.get("tags") or [])
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return target
