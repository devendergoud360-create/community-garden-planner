from __future__ import annotations

from datetime import date

from .models import PlantRecord

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner() -> str:
    return f"""{GREEN}{BOLD}
   ___ _| |_ ___ _ _  __ _ __ _| |_ 
  / -_)| ' \\  _| ' \\/ _` / _` | ' \\ 
  \\___||_|_||_| ||_|\\__,_\\__, |_||_|
           |_|          |___/
{RESET}{CYAN}  Community Garden Planner  ·  beds · plants · sowing · harvest notes{RESET}
{DIM}  ─────────────────────────────────────────────────────────────────{RESET}
"""


MENU = f"""{BOLD}MAIN MENU{RESET}
  {CYAN}1{RESET}. Add plant record
  {CYAN}2{RESET}. List / view records
  {CYAN}3{RESET}. Search records
  {CYAN}4{RESET}. Update record status / harvest notes
  {CYAN}5{RESET}. Delete record
  {CYAN}6{RESET}. Executive summary
  {CYAN}7{RESET}. Threshold warnings
  {CYAN}8{RESET}. Generate charts
  {CYAN}9{RESET}. Export report (md / txt / csv)
  {CYAN}10{RESET}. Bulk import CSV
  {CYAN}11{RESET}. Seed demo dataset
  {CYAN}12{RESET}. Save & exit
"""


def table(rows: list[list[str]], headers: list[str], max_width: int = 22) -> str:
    def clip(cell: str) -> str:
        cell = str(cell)
        return cell if len(cell) <= max_width else cell[: max_width - 1] + "…"

    data = [[clip(c) for c in row] for row in rows]
    headers = [clip(h) for h in headers]
    widths = [max(len(h), *(len(r[i]) for r in data)) if data else len(h) for i, h in enumerate(headers)]
    sep = "+".join("-" * (w + 2) for w in widths)
    sep = f"+{sep}+"
    head = "|".join(f" {h:<{w}} " for h, w in zip(headers, widths))
    lines = [sep, f"|{head}|", sep]
    for row in data:
        lines.append("|" + "|".join(f" {c:<{w}} " for c, w in zip(row, widths)) + "|")
    lines.append(sep)
    return "\n".join(lines)


def record_row(r: PlantRecord) -> list[str]:
    flag = ""
    if r.is_overdue:
        flag = " !OVERDUE"
    elif r.due_soon:
        flag = " !SOON"
    return [
        str(r.id),
        r.bed,
        r.plant,
        r.variety or "-",
        r.sown_date,
        r.status + flag,
        r.expected_harvest,
        f"{r.yield_kg:.2f}" if r.yield_kg else "-",
    ]


RECORD_HEADERS = ["ID", "Bed", "Plant", "Variety", "Sown", "Status", "Due", "Yield"]


def show_records(records: list[PlantRecord], page_size: int = 12, interactive: bool = True) -> None:
    if not records:
        print(f"\n{YELLOW}No records found.{RESET}")
        return
    ordered = sorted(records, key=lambda r: (r.bed, r.sown_date, r.id))
    total = len(ordered)
    if not interactive:
        shown = ordered[:page_size]
        print(f"\n{BOLD}Showing {len(shown)} of {total} record(s){RESET}")
        print(table([record_row(r) for r in shown], RECORD_HEADERS))
        if total > len(shown):
            print(f"  {DIM}… {total - len(shown)} more not shown (use Search or List){RESET}")
        return
    pages = (total + page_size - 1) // page_size
    page = 1
    while True:
        start = (page - 1) * page_size
        chunk = ordered[start : start + page_size]
        print(f"\n{BOLD}Records {start + 1}–{start + len(chunk)} of {total} "
              f"(page {page}/{pages}){RESET}")
        print(table([record_row(r) for r in chunk], RECORD_HEADERS))
        if pages == 1:
            return
        choice = input(f"  [Enter=next, b=back, q=quit list] ").strip().lower()
        if choice == "q":
            return
        if choice == "b":
            if page > 1:
                page -= 1
        elif choice in ("", "n", "next"):
            if page < pages:
                page += 1
        else:
            print(f"  {DIM}Unrecognized key — use Enter, b, or q.{RESET}")


def print_warnings(warnings: list[str]) -> None:
    print(f"\n{BOLD}THRESHOLD WARNINGS{RESET}")
    print("-" * 70)
    for w in warnings:
        if w.startswith("OVERDUE") or w.startswith("ANOMALY"):
            color = RED
        elif w.startswith("SOON") or w.startswith("DATA"):
            color = YELLOW
        else:
            color = GREEN
        print(f"  {color}{w}{RESET}")
    print("-" * 70)


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title} {'─' * max(0, 60 - len(title))}{RESET}")


def today_str() -> str:
    return date.today().isoformat()
