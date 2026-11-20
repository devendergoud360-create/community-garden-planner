from __future__ import annotations

import csv
import json
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import PlantRecord

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JSON_PATH = DATA_DIR / "plants.json"
CSV_PATH = DATA_DIR / "plants.csv"
SAMPLE_CSV = DATA_DIR / "sample_plants.csv"
REPORTS_DIR = BASE_DIR / "reports"

CSV_COLUMNS = [
    "id", "bed", "plant", "variety", "sown_date", "status",
    "days_to_harvest", "expected_harvest", "harvest_date",
    "harvest_notes", "yield_kg", "tags",
]


def ensure_dirs() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


@lru_cache(maxsize=None)
def writable(target: Path) -> Path:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        probe = target.parent / ".write_probe"
        probe.touch()
        probe.unlink()
        return target
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "garden-planner"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback / target.name


def live_path() -> Path:
    return writable(JSON_PATH)


def reports_dir() -> Path:
    return writable(REPORTS_DIR)


def _validate_payload(items: Any) -> list[PlantRecord]:
    if not isinstance(items, list):
        raise ValueError("storage root must be a list of records")
    records: list[PlantRecord] = []
    errors: list[str] = []
    for i, item in enumerate(items, start=1):
        try:
            records.append(PlantRecord.from_dict(item))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"record #{i}: {exc}")
    if errors and not records:
        raise ValueError("; ".join(errors[:5]))
    return records


def load_records(path: Path | None = None) -> list[PlantRecord]:
    ensure_dirs()
    target = writable(path or JSON_PATH)
    if not target.exists():
        return []
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  [!] Could not read {target.name}: {exc}")
        return []
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        backup = target.with_suffix(target.suffix + ".corrupt")
        try:
            target.rename(backup)
            print(f"  [!] Corrupted file moved to {backup.name}; starting fresh.")
        except OSError:
            print(f"  [!] JSON parse error ({exc}); starting with empty data.")
        return []
    try:
        return _validate_payload(payload)
    except ValueError as exc:
        print(f"  [!] Schema error: {exc}")
        return []


def save_records(records: list[PlantRecord], path: Path | None = None) -> None:
    ensure_dirs()
    target = writable(path or JSON_PATH)
    tmp = target.with_suffix(".tmp")
    payload = [r.to_dict() for r in records]
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        print(f"  [!] Save failed: {exc}")


def next_id(records: list[PlantRecord]) -> int:
    return max((r.id for r in records), default=0) + 1


def export_csv(records: list[PlantRecord], path: Path | None = None) -> Path:
    ensure_dirs()
    target = writable(path or CSV_PATH)
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            row = r.to_dict()
            row["tags"] = "|".join(row.get("tags") or [])
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return target


def import_csv_file(path: Path) -> tuple[list[PlantRecord], list[str]]:
    errors: list[str] = []
    records: list[PlantRecord] = []
    if not path.exists():
        return [], [f"file not found: {path}"]
    try:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                return [], ["empty or header-less CSV file"]
            missing = [c for c in ("bed", "plant", "sown_date") if c not in reader.fieldnames]
            if missing:
                return [], [f"missing required columns: {', '.join(missing)}"]
            for lineno, row in enumerate(reader, start=2):
                try:
                    clean = {k: (v or "").strip() for k, v in row.items() if k}
                    if clean.get("tags"):
                        clean["tags"] = [t for t in clean["tags"].split("|") if t]
                    else:
                        clean["tags"] = []
                    if not clean.get("id"):
                        clean["id"] = 0
                    rec = PlantRecord.from_dict(clean)
                    records.append(rec)
                except (ValueError, TypeError, KeyError) as exc:
                    errors.append(f"line {lineno}: {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"unreadable file: {exc}"]
    if records:
        base = max(r.id for r in records)
        for r in records:
            if r.id <= 0:
                base += 1
                r.id = base
    return records, errors
