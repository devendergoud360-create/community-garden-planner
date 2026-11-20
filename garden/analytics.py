from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from statistics import mean
from typing import Any

from .models import STATUSES, PlantRecord


def filter_records(
    records: list[PlantRecord],
    keyword: str | None = None,
    bed: str | None = None,
    status: str | None = None,
) -> list[PlantRecord]:
    out = records
    if keyword:
        kw = keyword.lower()
        out = [
            r for r in out
            if kw in r.plant.lower()
            or kw in r.variety.lower()
            or kw in r.bed.lower()
            or kw in r.harvest_notes.lower()
            or any(kw in t.lower() for t in r.tags)
        ]
    if bed:
        out = [r for r in out if r.bed.lower() == bed.lower()]
    if status:
        out = [r for r in out if r.status == status.lower()]
    return out


def summarize(records: list[PlantRecord]) -> dict[str, Any]:
    by_status = Counter(r.status for r in records)
    by_bed: dict[str, int] = Counter(r.bed for r in records)
    harvested = [r for r in records if r.status == "harvested" and r.yield_kg > 0]
    yields = [r.yield_kg for r in harvested]
    days = [r.days_to_harvest for r in records if r.days_to_harvest > 0]
    overdue = [r for r in records if r.is_overdue]
    due_soon = [r for r in records if r.due_soon]
    failed = [r for r in records if r.status == "failed"]
    bed_yield: dict[str, float] = defaultdict(float)
    for r in harvested:
        bed_yield[r.bed] += r.yield_kg
    months = Counter()
    for r in harvested:
        if r.harvest_date:
            try:
                months[date.fromisoformat(r.harvest_date).strftime("%Y-%m")] += 1
            except ValueError:
                pass
    return {
        "total": len(records),
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "by_bed": dict(sorted(by_bed.items())),
        "beds": len(by_bed),
        "harvested_count": by_status.get("harvested", 0),
        "total_yield_kg": round(sum(yields), 2),
        "avg_yield_kg": round(mean(yields), 2) if yields else 0.0,
        "avg_days_to_harvest": round(mean(days), 1) if days else 0.0,
        "overdue": overdue,
        "due_soon": due_soon,
        "failed_count": len(failed),
        "failure_rate": round(100 * len(failed) / len(records), 1) if records else 0.0,
        "top_beds_by_yield": [(b, round(y, 2)) for b, y in
                              sorted(bed_yield.items(), key=lambda kv: kv[1], reverse=True)],
        "harvests_by_month": dict(sorted(months.items())),
        "harvested_records": harvested,
    }


def threshold_warnings(records: list[PlantRecord], warn_days: int = 14) -> list[str]:
    warnings: list[str] = []
    today = date.today()
    for r in sorted(records, key=lambda x: x.expected_harvest):
        if r.status in ("harvested", "failed"):
            continue
        d = r.days_until_harvest
        if d is None:
            continue
        if d < 0:
            warnings.append(
                f"OVERDUE  bed={r.bed} {r.plant} was due {r.expected_harvest} ({abs(d)} days late)"
            )
        elif d <= warn_days:
            warnings.append(
                f"SOON     bed={r.bed} {r.plant} due in {d} day(s) on {r.expected_harvest}"
            )
    if records:
        fails = sum(1 for r in records if r.status == "failed")
        rate = 100 * fails / len(records)
        if rate >= 20:
            warnings.append(f"ANOMALY  failure rate is {rate:.0f}% across {len(records)} records")
        empty_notes = sum(1 for r in records if r.status == "harvested" and not r.harvest_notes.strip())
        if empty_notes:
            warnings.append(f"DATA     {empty_notes} harvested record(s) missing harvest notes")
    if not warnings:
        warnings.append(f"OK       no thresholds breached as of {today.isoformat()}")
    return warnings


def trend_points(records: list[PlantRecord]) -> tuple[list[str], list[int]]:
    buckets: Counter[str] = Counter()
    for r in records:
        if r.sown:
            buckets[r.sown.strftime("%Y-%m")] += 1
    keys = sorted(buckets)
    return keys, [buckets[k] for k in keys]
