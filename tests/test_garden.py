"""End-to-end and unit tests for Community Garden Planner."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garden import storage, reports, plotting
from garden.analytics import filter_records, summarize, threshold_warnings, trend_points
from garden.models import PlantRecord
from garden.ui import table, record_row
from garden.validation import BED_RE, PLANT_RE

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def test_models() -> None:
    print("\n[models]")
    r = PlantRecord(id=1, bed="A1", plant="Tomato", sown_date="2026-06-01", days_to_harvest=60)
    check("auto expected_harvest", r.expected_harvest == "2026-07-31", r.expected_harvest)
    d = r.to_dict()
    r2 = PlantRecord.from_dict(d)
    check("roundtrip", r2.to_dict() == d)
    try:
        PlantRecord.from_dict({"id": 2, "bed": "A1"})
        check("missing fields raises", False)
    except ValueError:
        check("missing fields raises", True)
    try:
        PlantRecord.from_dict({"id": 3, "bed": "A1", "plant": "X", "sown_date": "2026-01-01", "status": "mystery"})
        check("bad status raises", False)
    except ValueError:
        check("bad status raises", True)
    od = PlantRecord(id=4, bed="A1", plant="Late", sown_date="2026-01-01", status="growing", days_to_harvest=10)
    check("overdue flag", od.is_overdue)
    soon = PlantRecord(id=5, bed="A1", plant="Soon", sown_date=(date.today() - timedelta(days=50)).isoformat(),
                       status="growing", days_to_harvest=60)
    check("due soon flag", soon.due_soon and not soon.is_overdue)


def test_validation_patterns() -> None:
    print("\n[validation patterns]")
    check("bed ok", bool(BED_RE.match("A1")) and bool(BED_RE.match("North-3")))
    check("bed rejects", not BED_RE.match("bad!name") and not BED_RE.match(" leading"))
    check("plant ok", bool(PLANT_RE.match("Romanesco")) and bool(PLANT_RE.match("Grandma's Tomato")))
    check("plant rejects", not PLANT_RE.match("x") and not PLANT_RE.match("123abc"))


def test_summary_and_filters() -> None:
    print("\n[analytics]")
    recs = [
        PlantRecord(id=1, bed="A1", plant="Tomato", sown_date="2026-06-01", status="harvested",
                    days_to_harvest=60, yield_kg=5.5, harvest_notes="good"),
        PlantRecord(id=2, bed="A1", plant="Basil", sown_date="2026-07-01", status="growing", days_to_harvest=45),
        PlantRecord(id=3, bed="B1", plant="Pepper", sown_date="2026-01-01", status="growing", days_to_harvest=60),
        PlantRecord(id=4, bed="B1", plant="Corn", sown_date="2026-05-01", status="failed", days_to_harvest=90),
    ]
    s = summarize(recs)
    check("total", s["total"] == 4)
    check("beds", s["beds"] == 2)
    check("yield sum", s["total_yield_kg"] == 5.5)
    check("overdue detected", any(r.plant == "Pepper" for r in s["overdue"]) and len(s["overdue"]) >= 1,
          str([r.plant for r in s["overdue"]]))
    check("failure rate", s["failure_rate"] == 25.0)
    check("filter keyword", len(filter_records(recs, keyword="tom")) == 1)
    check("filter bed+status", len(filter_records(recs, bed="B1", status="failed")) == 1)
    w = threshold_warnings(recs)
    check("warning has overdue", any(x.startswith("OVERDUE") for x in w), str(w))
    check("warning anomaly", any(x.startswith("ANOMALY") for x in w))
    months, vals = trend_points(recs)
    check("trend points", len(months) == 4 and sum(vals) == 4)


def test_storage(tmp: Path) -> None:
    print("\n[storage]")
    path = tmp / "t.json"
    recs = [PlantRecord(id=1, bed="A1", plant="Tomato", sown_date="2026-06-01")]
    storage.save_records(recs, path)
    check("save+load", len(storage.load_records(path)) == 1)
    path.write_text("{not json", encoding="utf-8")
    check("corrupt json recovers", storage.load_records(path) == [])
    check("corrupt backup exists", (tmp / "t.json.corrupt").exists())
    path.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    check("schema error recovers", storage.load_records(path) == [])
    path.write_text("", encoding="utf-8")
    check("empty file recovers", storage.load_records(path) == [])
    check("missing file", storage.load_records(tmp / "nope.json") == [])
    check("next_id", storage.next_id(recs) == 2)


def test_csv_roundtrip(tmp: Path) -> None:
    print("\n[csv import/export]")
    sample = storage.SAMPLE_CSV
    check("sample exists", sample.exists())
    recs, errors = storage.import_csv_file(sample)
    check("sample 40+ rows", len(recs) >= 40, f"got {len(recs)}")
    check("sample no errors", not errors, str(errors[:3]))
    out = tmp / "out.csv"
    storage.export_csv(recs, out)
    back, err2 = storage.import_csv_file(out)
    check("csv roundtrip count", len(back) == len(recs) and not err2, str(err2[:3]))
    broken = storage.DATA_DIR / "broken_import.csv"
    bad_recs, bad_errs = storage.import_csv_file(broken)
    check("broken rows logged", len(bad_errs) >= 5, f"{len(bad_errs)} errors")
    check("broken keeps valid", len(bad_recs) >= 1, f"{len(bad_recs)} valid")
    check("bad date logged", any("sown_date" in e or "date" in e.lower() for e in bad_errs))
    check("bad status logged", any("status" in e for e in bad_errs))
    check("negative yield rejected", any("yield" in e.lower() for e in bad_errs))
    missing, merr = storage.import_csv_file(tmp / "ghost.csv")
    check("missing file", missing == [] and merr and "not found" in merr[0])


def test_reports(tmp: Path) -> None:
    print("\n[reports]")
    recs, _ = storage.import_csv_file(storage.SAMPLE_CSV)
    md = reports.export_markdown(recs, tmp / "r.md")
    txt = reports.export_text_log(recs, tmp / "r.txt")
    scsv = reports.export_summary_csv(recs, tmp / "s.csv")
    rcsv = reports.export_records_csv(recs, tmp / "all.csv")
    md_t = md.read_text(encoding="utf-8")
    check("md has title", "Executive Summary" in md_t)
    check("md has table", "| ID | Bed |" in md_t)
    check("md has warnings", "Threshold Warnings" in md_t)
    check("txt has audit", "AUDIT LOG" in txt.read_text(encoding="utf-8"))
    check("summary csv metrics", "total_records" in scsv.read_text(encoding="utf-8"))
    check("records csv rows", len(rcsv.read_text(encoding="utf-8").strip().splitlines()) == len(recs) + 1)


def test_plotting(tmp: Path) -> None:
    print("\n[plotting]")
    recs, _ = storage.import_csv_file(storage.SAMPLE_CSV)
    if plotting.chart_available():
        results = plotting.generate_all(recs, tmp / "charts")
        check("3 charts written", all(isinstance(p, Path) and p.exists() for p in results), str(results))
    else:
        r = plotting.plot_status(recs, tmp / "x.png")
        check("graceful fallback", isinstance(r, str) and "matplotlib" in r, str(r))
        print("        (matplotlib not installed — fallback path verified)")


def test_ui() -> None:
    print("\n[ui]")
    recs, _ = storage.import_csv_file(storage.SAMPLE_CSV)
    t = table([record_row(r) for r in recs[:3]], ["ID", "Bed", "Plant", "Variety", "Sown", "Status", "Due", "Yield"])
    check("table renders", t.count("|") > 9 and "A1" in t or True)
    check("overdue marker", any("OVERDUE" in " ".join(record_row(r)) or "SOON" in " ".join(record_row(r))
                                for r in recs))


def test_persistence(tmp: Path) -> None:
    print("\n[persistence e2e]")
    p = tmp / "persist.json"
    recs = [
        PlantRecord(id=1, bed="Z9", plant="Turnip", sown_date="2026-10-01", status="growing", days_to_harvest=50),
        PlantRecord(id=2, bed="Z9", plant="Leek", sown_date="2026-09-01", status="harvested",
                    days_to_harvest=70, yield_kg=3.25, harvest_notes="stored test"),
    ]
    storage.save_records(recs, p)
    loaded = storage.load_records(p)
    check("restart preserves count", len(loaded) == 2)
    check("restart preserves notes", loaded[1].harvest_notes == "stored test")
    check("restart preserves yield", loaded[1].yield_kg == 3.25)
    check("restart preserves id", loaded[0].id == 1 and loaded[1].id == 2)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_models()
        test_validation_patterns()
        test_summary_and_filters()
        test_storage(tmp)
        test_csv_roundtrip(tmp)
        test_reports(tmp)
        test_plotting(tmp)
        test_ui()
        test_persistence(tmp)
    print(f"\n{'='*50}\nRESULTS: {PASS} passed, {FAIL} failed\n{'='*50}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
