# Community Garden Planner

A beginner-friendly Python terminal application for tracking garden beds, plants, sowing dates, and harvest notes — with strict input validation, JSON/CSV persistence, executive summaries, threshold warnings, chart export, and multi-format reports.

## Quick Start

### Web UI (browser)

```bash
cd community-garden-planner
python3 webapp.py
```

Open **http://127.0.0.1:5000** — dashboard, records table with filters, add/edit forms
with the same server-side validation as the CLI, summary, warnings, charts, report
downloads, and bulk CSV import. Requires Flask (`pip install flask` or `apt install python3-flask`).

**Browser slide deck:** `/slides` (or https://community-garden-planner.vercel.app/slides) —
the 10-slide presentation in HTML with keyboard navigation (`←` `→`, Space, `F` for fullscreen).
Also available as `Community_Garden_Planner.pptx`.

### Terminal CLI

```bash
python3 main.py
```

On first launch choose **11. Seed demo dataset** to load 44 realistic records (normal, boundary, and edge cases).

Optional charts (gracefully skipped if unavailable):

```bash
pip install -r requirements.txt
```

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | Add plant record | Guided prompts with defensive validation |
| 2 | List records | Paginated, fixed-width tables with OVERDUE/SOON flags |
| 3 | Search | Keyword, bed, status, or combined filters |
| 4 | Update | Status, harvest notes, harvest date + yield, due-date changes |
| 5 | Delete | Confirmation prompt before removal |
| 6 | Executive summary | Totals, averages, per-bed/per-status breakdowns, top beds by yield |
| 7 | Threshold warnings | Overdue, due-soon, failure-rate anomalies, missing notes |
| 8 | Charts | Matplotlib PNGs (status pie, records-per-bed, sowing trend) |
| 9 | Export | Markdown summary, plain-text audit log, summary CSV, full records CSV |
| 10 | Bulk import | CSV ingest with row-by-row error log |
| 11 | Seed demo | Loads `data/sample_plants.csv` (44 rows) |
| 12 | Save & exit | Atomic JSON write |

## Validation Rules

- **Bed ID**: 1–20 chars, alphanumeric/`_`/`-`/space, must start alphanumeric
- **Plant name**: 2–40 chars, letters/spaces/`-'&.,`
- **Sowing date**: strict `YYYY-MM-DD`, within last 10 years, not in the future
- **Days to harvest**: integer 1–365
- **Yield**: float 0–1000 kg
- **Status**: `planted | growing | harvested | failed`
- Blank/non-numeric input re-prompts instead of crashing

## Data & Reports

```
data/
  plants.json            # live application state (auto-created)
  sample_plants.csv      # 44-row demo dataset
  sample_plants.json     # JSON copy of demo data
  broken_import.csv      # deliberately bad rows for import-error demo
reports/
  garden_report_*.md     # executive summary (Markdown)
  garden_audit_*.txt     # plain-text audit log
  garden_summary_*.csv   # aggregated metrics
  garden_records_*.csv   # full record dump
  charts/*.png           # when matplotlib is installed
```

Corrupted JSON is moved to `*.json.corrupt` and the app starts clean — it never crashes on bad storage files.

## Tests

```bash
python3 tests/test_garden.py
```

50 checks covering models, validation patterns, analytics, storage recovery, CSV round-trip, import error logging, reports, plotting fallback, UI, and restart persistence.

## Demo Script (2 minutes)

1. `python3 main.py` → option **11** to seed data
2. Option **1**, enter a bad bed (`bad!name`) and a future date — show rejection messages, then valid values
3. Option **6** — executive summary tables; option **7** — threshold warnings
4. Option **9** → **5** — export all report formats; open the Markdown file
5. Quit (option **12**), relaunch — show records persisted
6. Option **10** with `data/broken_import.csv` — show row-by-row error log

## Tech Stack

- Python 3.10+ standard library (`csv`, `json`, `datetime`, `dataclasses`, `statistics`, `re`)
- Matplotlib (optional, defensive `ImportError` fallback)
- ANSI-colored menu-driven terminal UI
