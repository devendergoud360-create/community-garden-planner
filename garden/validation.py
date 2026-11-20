from __future__ import annotations

import re
from datetime import date, datetime, timedelta

BED_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-]{0,19}$")
PLANT_RE = re.compile(r"^[A-Za-z][A-Za-z \-'&.,]{1,39}$")
NOTES_RE = re.compile(r"^[\w \-.,'\"()!?/:\n]{0,200}$")
YEAR_MIN = date.today().replace(year=date.today().year - 10)
YEAR_MAX = date.today() + timedelta(days=730)


def _read(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\n\nExiting. Goodbye!")


def prompt_nonempty(prompt: str, min_len: int = 1, max_len: int = 60, pattern: re.Pattern | None = None) -> str:
    while True:
        raw = _read(prompt)
        if not raw:
            print("  [!] Input cannot be blank.")
            continue
        if len(raw) < min_len:
            print(f"  [!] Minimum {min_len} characters required.")
            continue
        if len(raw) > max_len:
            print(f"  [!] Maximum {max_len} characters allowed.")
            continue
        if pattern and not pattern.match(raw):
            print("  [!] Input contains invalid characters or format.")
            continue
        return raw


def prompt_int(prompt: str, lo: int, hi: int) -> int:
    while True:
        raw = _read(prompt)
        try:
            value = int(raw)
        except ValueError:
            print("  [!] Enter a whole number.")
            continue
        if value < lo or value > hi:
            print(f"  [!] Enter a number between {lo} and {hi}.")
            continue
        return value


def prompt_float(prompt: str, lo: float, hi: float) -> float:
    while True:
        raw = _read(prompt)
        try:
            value = float(raw)
        except ValueError:
            print("  [!] Enter a numeric value (e.g. 2.5).")
            continue
        if value < lo or value > hi:
            print(f"  [!] Enter a value between {lo} and {hi}.")
            continue
        return round(value, 2)


def prompt_date(prompt: str, allow_future: bool = True) -> str:
    while True:
        raw = _read(prompt)
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print("  [!] Use format YYYY-MM-DD (e.g. 2026-03-15).")
            continue
        if parsed < YEAR_MIN:
            print(f"  [!] Date cannot be before {YEAR_MIN.isoformat()}.")
            continue
        if not allow_future and parsed > date.today():
            print("  [!] Date cannot be in the future.")
            continue
        if allow_future and parsed > YEAR_MAX:
            print(f"  [!] Date cannot be after {YEAR_MAX.isoformat()}.")
            continue
        return parsed.isoformat()


def prompt_choice(prompt: str, options: list[str] | tuple[str, ...]) -> str:
    opts = [str(o).strip().lower() for o in options]
    while True:
        raw = _read(prompt).lower()
        if raw in opts:
            return raw
        print(f"  [!] Choose one of: {', '.join(opts)}")


def prompt_optional(prompt: str, max_len: int = 200, pattern: re.Pattern | None = None) -> str:
    while True:
        raw = _read(prompt)
        if not raw:
            return ""
        if len(raw) > max_len:
            print(f"  [!] Maximum {max_len} characters allowed.")
            continue
        if pattern and not pattern.match(raw):
            print("  [!] Input contains invalid characters or format.")
            continue
        return raw


def confirm(prompt: str) -> bool:
    return prompt_choice(f"{prompt} (y/n): ", ("y", "yes", "n", "no")) in ("y", "yes")
