#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from garden import plotting, reports, storage, ui
from garden.analytics import filter_records, summarize, threshold_warnings
from garden.models import STATUSES, PlantRecord
from garden.validation import (
    BED_RE,
    NOTES_RE,
    PLANT_RE,
    confirm,
    prompt_choice,
    prompt_date,
    prompt_float,
    prompt_int,
    prompt_nonempty,
    prompt_optional,
)

storage.ensure_dirs()


def load() -> list[PlantRecord]:
    records = storage.load_records()
    print(f"  Loaded {len(records)} record(s) from {storage.JSON_PATH.name}.")
    return records


def save(records: list[PlantRecord]) -> None:
    storage.save_records(records)


def add_record(records: list[PlantRecord]) -> None:
    ui.section("Add Plant Record")
    print(f"  {ui.DIM}Fields marked with * are required. Blank optional fields are skipped.{ui.RESET}\n")
    bed = prompt_nonempty("  Bed ID * (e.g. A1, North-3): ", 1, 20, BED_RE)
    plant = prompt_nonempty("  Plant name * (e.g. Tomato): ", 2, 40, PLANT_RE)
    variety = prompt_optional("  Variety (optional): ", 40, PLANT_RE)
    sown = prompt_date("  Sowing date (YYYY-MM-DD) *: ", allow_future=False)
    status = prompt_choice(f"  Status * ({'/'.join(STATUSES)}): ", STATUSES)
    days = prompt_int("  Days until expected harvest (1-365): ", 1, 365)
    tags_raw = prompt_optional("  Tags (comma-separated, optional): ", 80)
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    rec = PlantRecord(
        id=storage.next_id(records),
        bed=bed,
        plant=plant,
        variety=variety,
        sown_date=sown,
        status=status,
        days_to_harvest=days,
        tags=tags,
    )
    if status in ("harvested", "failed"):
        _prompt_harvest(rec, allow_yield=status == "harvested")
    records.append(rec)
    save(records)
    print(f"\n  {ui.GREEN}✓ Saved record #{rec.id} — {rec.plant} in bed {rec.bed} "
          f"(due {rec.expected_harvest}).{ui.RESET}")


def _prompt_harvest(rec: PlantRecord, allow_yield: bool = True) -> None:
    if rec.status == "harvested":
        rec.harvest_date = prompt_date("  Harvest date (YYYY-MM-DD): ", allow_future=True)
        if allow_yield:
            rec.yield_kg = prompt_float("  Yield in kg (0-1000): ", 0, 1000)
    rec.harvest_notes = prompt_optional("  Harvest notes: ", 200, NOTES_RE)


def search_records(records: list[PlantRecord]) -> None:
    ui.section("Search Records")
    print("  1. Keyword search (plant/bed/variety/notes/tags)")
    print("  2. Filter by bed")
    print("  3. Filter by status")
    print("  4. Combined keyword + bed + status")
    mode = prompt_choice("  Choose search mode: ", ("1", "2", "3", "4"))
    keyword = bed = status = None
    if mode in ("1", "4"):
        keyword = prompt_nonempty("  Keyword: ", 1, 40)
    if mode in ("2", "4"):
        bed = prompt_nonempty("  Bed ID: ", 1, 20, BED_RE)
    if mode in ("3", "4"):
        status = prompt_choice(f"  Status ({'/'.join(STATUSES)}): ", STATUSES)
    hits = filter_records(records, keyword=keyword, bed=bed, status=status)
    print(f"\n  {len(hits)} match(es).")
    ui.show_records(hits)


def update_record(records: list[PlantRecord]) -> None:
    ui.section("Update Record")
    if not records:
        print("  No records to update.")
        return
    ui.show_records(records, page_size=20, interactive=False)
    rid = prompt_int("  Enter record ID to update: ", 1, 10_000)
    rec = next((r for r in records if r.id == rid), None)
    if not rec:
        print(f"  {ui.RED}No record with ID {rid}.{ui.RESET}")
        return
    print(f"\n  Editing #{rec.id}: {rec.plant} @ {rec.bed} [{rec.status}]")
    print("  1. Change status")
    print("  2. Add/replace harvest notes")
    print("  3. Record harvest (date + yield)")
    print("  4. Change expected harvest days")
    print("  5. Cancel")
    choice = prompt_choice("  Choice: ", ("1", "2", "3", "4", "5"))
    if choice == "1":
        rec.status = prompt_choice(f"  New status ({'/'.join(STATUSES)}): ", STATUSES)
        if rec.status == "harvested" and not rec.harvest_date:
            _prompt_harvest(rec, allow_yield=True)
        elif rec.status == "failed" and not rec.harvest_notes:
            rec.harvest_notes = prompt_optional("  Failure notes: ", 200, NOTES_RE)
    elif choice == "2":
        rec.harvest_notes = prompt_optional("  Harvest notes: ", 200, NOTES_RE)
    elif choice == "3":
        rec.status = "harvested"
        rec.harvest_date = prompt_date("  Harvest date (YYYY-MM-DD): ")
        rec.yield_kg = prompt_float("  Yield in kg (0-1000): ", 0, 1000)
        rec.harvest_notes = prompt_optional("  Harvest notes: ", 200, NOTES_RE)
    elif choice == "4":
        rec.days_to_harvest = prompt_int("  Days until harvest (1-365): ", 1, 365)
        if rec.sown:
            from datetime import timedelta

            rec.expected_harvest = (rec.sown + timedelta(days=rec.days_to_harvest)).isoformat()
    else:
        print("  Cancelled.")
        return
    save(records)
    print(f"  {ui.GREEN}✓ Record #{rec.id} updated.{ui.RESET}")


def delete_record(records: list[PlantRecord]) -> None:
    ui.section("Delete Record")
    if not records:
        print("  No records to delete.")
        return
    ui.show_records(records, page_size=20, interactive=False)
    rid = prompt_int("  Enter record ID to delete: ", 1, 10_000)
    rec = next((r for r in records if r.id == rid), None)
    if not rec:
        print(f"  {ui.RED}No record with ID {rid}.{ui.RESET}")
        return
    if not confirm(f"  Delete #{rec.id} {rec.plant} @ {rec.bed}?"):
        print("  Cancelled.")
        return
    records.remove(rec)
    save(records)
    print(f"  {ui.GREEN}✓ Deleted record #{rid}.{ui.RESET}")


def show_summary(records: list[PlantRecord]) -> None:
    ui.section("Executive Summary")
    if not records:
        print("  No data yet.")
        return
    s = summarize(records)
    print(f"\n  {ui.BOLD}Overview{ui.RESET}")
    print(f"  Total records : {s['total']}")
    print(f"  Garden beds   : {s['beds']}  → {', '.join(s['by_bed'])}")
    print(f"  Avg days to harvest : {s['avg_days_to_harvest']}")
    print(f"  Total yield   : {s['total_yield_kg']} kg "
          f"(avg {s['avg_yield_kg']} kg / harvested plant)")
    print(f"  Failure rate  : {s['failure_rate']}%")

    print(f"\n  {ui.BOLD}By Status{ui.RESET}")
    print(ui.table(
        [[k, str(v)] for k, v in s["by_status"].items()],
        ["Status", "Count"],
    ))

    print(f"  {ui.BOLD}By Bed{ui.RESET}")
    print(ui.table(
        [[k, str(v)] for k, v in s["by_bed"].items()],
        ["Bed", "Plants"],
    ))

    if s["top_beds_by_yield"]:
        print(f"  {ui.BOLD}Top Beds by Yield{ui.RESET}")
        print(ui.table(
            [[b, f"{y:.2f} kg"] for b, y in s["top_beds_by_yield"][:8]],
            ["Bed", "Yield"],
        ))

    if s["harvests_by_month"]:
        print(f"  {ui.BOLD}Harvests by Month{ui.RESET}")
        print(ui.table(
            [[m, str(c)] for m, c in s["harvests_by_month"].items()],
            ["Month", "Harvested"],
        ))

    if s["overdue"]:
        print(f"  {ui.RED}{ui.BOLD}Overdue ({len(s['overdue'])}){ui.RESET}")
        print(ui.table(
            [[r.bed, r.plant, r.expected_harvest, str(abs(r.days_until_harvest or 0))]
             for r in s["overdue"]],
            ["Bed", "Plant", "Due", "Days late"],
        ))


def show_warnings(records: list[PlantRecord]) -> None:
    ui.section("Threshold Warnings")
    ui.print_warnings(threshold_warnings(records))


def make_charts(records: list[PlantRecord]) -> None:
    ui.section("Generate Charts")
    if not records:
        print("  No data to chart.")
        return
    out = storage.REPORTS_DIR / "charts"
    results = plotting.generate_all(records, out)
    if not plotting.chart_available():
        print(f"  {ui.YELLOW}⚠ {results[0]}{ui.RESET}")
        print(f"  {ui.DIM}Charts are optional — install matplotlib to enable them.{ui.RESET}")
        return
    for item in results:
        if isinstance(item, Path):
            print(f"  {ui.GREEN}✓{ui.RESET} {item}")
        else:
            print(f"  {ui.YELLOW}⚠ {item}{ui.RESET}")


def export_report(records: list[PlantRecord]) -> None:
    ui.section("Export Report")
    if not records:
        print("  No data to export.")
        return
    print("  1. Markdown executive summary (.md)")
    print("  2. Plain-text audit log (.txt)")
    print("  3. Summary metrics CSV (.csv)")
    print("  4. Full records CSV (.csv)")
    print("  5. All of the above")
    choice = prompt_choice("  Choose format: ", ("1", "2", "3", "4", "5"))
    made: list[Path] = []
    if choice in ("1", "5"):
        made.append(reports.export_markdown(records))
    if choice in ("2", "5"):
        made.append(reports.export_text_log(records))
    if choice in ("3", "5"):
        made.append(reports.export_summary_csv(records))
    if choice in ("4", "5"):
        made.append(reports.export_records_csv(records))
    for p in made:
        print(f"  {ui.GREEN}✓{ui.RESET} {p}")
    print(f"  {ui.DIM}Reports saved under {storage.REPORTS_DIR}{ui.RESET}")


def bulk_import(records: list[PlantRecord]) -> None:
    ui.section("Bulk CSV Import")
    print(f"  {ui.DIM}Expected columns: bed, plant, sown_date (required); "
          f"variety, status, days_to_harvest, harvest_notes, yield_kg, tags (optional){ui.RESET}")
    raw = prompt_nonempty("  Path to CSV file: ", 1, 300)
    path = Path(raw).expanduser()
    imported, errors = storage.import_csv_file(path)
    if errors:
        print(f"\n  {ui.YELLOW}Row-by-row validation log ({len(errors)} issue(s)):{ui.RESET}")
        for e in errors[:40]:
            print(f"    {ui.RED}✗{ui.RESET} {e}")
        if len(errors) > 40:
            print(f"    … {len(errors) - 40} more")
    if not imported:
        print(f"\n  {ui.RED}No valid rows imported.{ui.RESET}")
        return
    print(f"\n  {ui.GREEN}{len(imported)} row(s) valid and ready.{ui.RESET}")
    if not confirm("  Merge these into current data?"):
        print("  Import cancelled.")
        return
    existing_ids = {r.id for r in records}
    base = storage.next_id(records)
    added = 0
    for r in imported:
        if r.id in existing_ids or r.id <= 0:
            r.id = base
            base += 1
            existing_ids.add(r.id)
        records.append(r)
        added += 1
    save(records)
    print(f"  {ui.GREEN}✓ Imported {added} record(s). Total now {len(records)}.{ui.RESET}")


def demo_seed(records: list[PlantRecord]) -> None:
    ui.section("Seed Demo Dataset")
    if records and not confirm(f"  {len(records)} record(s) already exist. Append demo data anyway?"):
        return
    sample = storage.SAMPLE_CSV
    if not sample.exists():
        print(f"  {ui.RED}Sample file missing: {sample}{ui.RESET}")
        return
    imported, errors = storage.import_csv_file(sample)
    for r in imported:
        r.id = storage.next_id(records)
        records.append(r)
    save(records)
    print(f"  {ui.GREEN}✓ Seeded {len(imported)} demo record(s).{ui.RESET}")
    if errors:
        for e in errors:
            print(f"    {ui.YELLOW}!{ui.RESET} {e}")


def main_menu(records: list[PlantRecord]) -> list[PlantRecord]:
    actions = {
        "1": add_record,
        "2": lambda rs: ui.show_records(rs),
        "3": search_records,
        "4": update_record,
        "5": delete_record,
        "6": show_summary,
        "7": show_warnings,
        "8": make_charts,
        "9": export_report,
        "10": bulk_import,
        "11": demo_seed,
    }
    while True:
        print(ui.MENU)
        print(f"  {ui.DIM}records={len(records)} · date={ui.today_str()} · "
              f"11=seed demo · 12=save & exit{ui.RESET}")
        choice = prompt_choice("  Select option: ",
                               tuple(str(i) for i in range(1, 13)))
        if choice == "12":
            save(records)
            print(f"\n  {ui.GREEN}✓ Saved {len(records)} record(s). Goodbye!{ui.RESET}\n")
            raise SystemExit(0)
        handler = actions[choice]
        try:
            handler(records)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 — keep demo session alive
            print(f"  {ui.RED}Unexpected error: {exc}{ui.RESET}")
        save(records)


def main() -> None:
    print(ui.banner())
    records = load()
    if not records and storage.SAMPLE_CSV.exists():
        print(f"  {ui.DIM}Tip: choose option 11 to seed the 40-row demo dataset.{ui.RESET}")
    if not plotting.chart_available():
        print(f"  {ui.DIM}Note: matplotlib not installed — chart export will be skipped gracefully.{ui.RESET}")
    main_menu(records)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Data saved on last change.")
        sys.exit(130)
