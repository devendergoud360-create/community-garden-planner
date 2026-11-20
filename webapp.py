from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from garden import plotting, reports, storage
from garden.analytics import filter_records, summarize, threshold_warnings
from garden.models import STATUSES, PlantRecord
from garden.validation import BED_RE, NOTES_RE, PLANT_RE, YEAR_MAX, YEAR_MIN

app = Flask(__name__)
app.secret_key = "garden-planner-local-demo"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

storage.ensure_dirs()


def get_records() -> list[PlantRecord]:
    records = storage.load_records()
    if not records and storage.SAMPLE_CSV.exists() and not storage.live_path().exists():
        imported, _ = storage.import_csv_file(storage.SAMPLE_CSV)
        for i, r in enumerate(imported, start=1):
            r.id = i
        storage.save_records(imported)
        return imported
    return records


def put_records(records: list[PlantRecord]) -> None:
    storage.save_records(records)


def validate_form(form) -> dict[str, object]:
    errors: dict[str, str] = {}
    values: dict[str, object] = {}

    bed = (form.get("bed") or "").strip()
    if not bed:
        errors["bed"] = "Bed is required."
    elif not BED_RE.match(bed):
        errors["bed"] = "1–20 chars; letters, digits, space, _ or - (must start alphanumeric)."
    values["bed"] = bed

    plant = (form.get("plant") or "").strip()
    if not plant:
        errors["plant"] = "Plant name is required."
    elif not PLANT_RE.match(plant):
        errors["plant"] = "2–40 chars; letters, spaces and - ' & . , only."
    values["plant"] = plant

    variety = (form.get("variety") or "").strip()
    if variety and not PLANT_RE.match(variety):
        errors["variety"] = "Same format as plant name (or leave blank)."
    values["variety"] = variety

    sown = (form.get("sown_date") or "").strip()
    try:
        parsed = date.fromisoformat(sown)
        if parsed < YEAR_MIN:
            errors["sown_date"] = f"Cannot be before {YEAR_MIN.isoformat()}."
        elif parsed > YEAR_MAX:
            errors["sown_date"] = f"Cannot be after {YEAR_MAX.isoformat()}."
        elif parsed > date.today():
            errors["sown_date"] = "Sowing date cannot be in the future."
    except ValueError:
        errors["sown_date"] = "Use a valid date (YYYY-MM-DD)."
    values["sown_date"] = sown

    status = (form.get("status") or "").strip().lower()
    if status not in STATUSES:
        errors["status"] = f"Choose one of: {', '.join(STATUSES)}."
    values["status"] = status

    try:
        days = int(form.get("days_to_harvest") or "")
        if not 1 <= days <= 365:
            raise ValueError
        values["days_to_harvest"] = days
    except (ValueError, TypeError):
        errors["days_to_harvest"] = "Whole number between 1 and 365."

    notes = (form.get("harvest_notes") or "").strip()
    if notes and not NOTES_RE.match(notes):
        errors["harvest_notes"] = "Notes contain unsupported characters."
    values["harvest_notes"] = notes

    yield_raw = (form.get("yield_kg") or "").strip()
    if yield_raw:
        try:
            yield_kg = float(yield_raw)
            if not 0 <= yield_kg <= 1000:
                raise ValueError
            values["yield_kg"] = round(yield_kg, 2)
        except ValueError:
            errors["yield_kg"] = "Number between 0 and 1000."
    else:
        values["yield_kg"] = 0.0

    harvest_date = (form.get("harvest_date") or "").strip()
    if harvest_date:
        try:
            date.fromisoformat(harvest_date)
        except ValueError:
            errors["harvest_date"] = "Use a valid date (YYYY-MM-DD)."
    values["harvest_date"] = harvest_date

    tags_raw = (form.get("tags") or "").strip()
    values["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
    return values if not errors else values | {"_errors": errors}  # type: ignore[return-value]


def split(values: dict) -> tuple[dict, dict]:
    errors = values.pop("_errors", {})
    return values, errors


@app.context_processor
def inject_globals():
    records = get_records()
    return {
        "today": date.today().isoformat(),
        "record_count": len(records),
        "statuses": STATUSES,
    }


@app.route("/slides")
def slides():
    return send_from_directory(Path(__file__).parent / "presentation", "index.html")


@app.route("/")
def dashboard():
    records = get_records()
    s = summarize(records) if records else None
    warnings = threshold_warnings(records) if records else []
    return render_template("dashboard.html", s=s, warnings=warnings[:6])


@app.route("/records")
def records_page():
    records = get_records()
    keyword = (request.args.get("q") or "").strip()
    bed = (request.args.get("bed") or "").strip()
    status = (request.args.get("status") or "").strip()
    hits = filter_records(records, keyword=keyword or None, bed=bed or None, status=status or None)
    ordered = sorted(hits, key=lambda r: (r.bed, r.sown_date, r.id))
    beds = sorted({r.bed for r in records})
    return render_template(
        "records.html",
        records=ordered,
        beds=beds,
        q=keyword,
        fbed=bed,
        fstatus=status,
        total=len(records),
    )


@app.route("/add", methods=["GET", "POST"])
def add_record():
    if request.method == "POST":
        values, errors = split(validate_form(request.form))
        if errors:
            flash("Please fix the highlighted fields.", "error")
            return render_template("record_form.html", mode="add", values=values, errors=errors, rec=None)
        records = get_records()
        rec = PlantRecord(
            id=storage.next_id(records),
            bed=values["bed"],
            plant=values["plant"],
            variety=values["variety"],
            sown_date=values["sown_date"],
            status=values["status"],
            days_to_harvest=values["days_to_harvest"],
            harvest_notes=values["harvest_notes"],
            yield_kg=values["yield_kg"],
            harvest_date=values["harvest_date"],
            tags=values["tags"],
        )
        records.append(rec)
        put_records(records)
        flash(f"Record #{rec.id} added — {rec.plant} in bed {rec.bed} (due {rec.expected_harvest}).", "ok")
        return redirect(url_for("records_page"))
    return render_template("record_form.html", mode="add", values={}, errors={}, rec=None)


@app.route("/edit/<int:rid>", methods=["GET", "POST"])
def edit_record(rid: int):
    records = get_records()
    rec = next((r for r in records if r.id == rid), None)
    if not rec:
        abort(404)
    if request.method == "POST":
        values, errors = split(validate_form(request.form))
        if errors:
            flash("Please fix the highlighted fields.", "error")
            return render_template(
                "record_form.html", mode="edit", values=values, errors=errors, rec=rec
            )
        rec.bed = values["bed"]
        rec.plant = values["plant"]
        rec.variety = values["variety"]
        rec.sown_date = values["sown_date"]
        rec.status = values["status"]
        rec.days_to_harvest = values["days_to_harvest"]
        rec.harvest_notes = values["harvest_notes"]
        rec.yield_kg = values["yield_kg"]
        rec.harvest_date = values["harvest_date"]
        rec.tags = values["tags"]
        rec.expected_harvest = rec._compute_expected()
        put_records(records)
        flash(f"Record #{rec.id} updated.", "ok")
        return redirect(url_for("records_page"))
    values = {
        "bed": rec.bed,
        "plant": rec.plant,
        "variety": rec.variety,
        "sown_date": rec.sown_date,
        "status": rec.status,
        "days_to_harvest": rec.days_to_harvest,
        "harvest_notes": rec.harvest_notes,
        "yield_kg": rec.yield_kg if rec.yield_kg else "",
        "harvest_date": rec.harvest_date,
        "tags": ", ".join(rec.tags),
    }
    return render_template("record_form.html", mode="edit", values=values, errors={}, rec=rec)


@app.route("/delete/<int:rid>", methods=["POST"])
def delete_record(rid: int):
    records = get_records()
    rec = next((r for r in records if r.id == rid), None)
    if not rec:
        abort(404)
    records.remove(rec)
    put_records(records)
    flash(f"Record #{rid} deleted ({rec.plant} @ {rec.bed}).", "ok")
    return redirect(url_for("records_page"))


@app.route("/summary")
def summary_page():
    records = get_records()
    s = summarize(records) if records else None
    return render_template("summary.html", s=s)


@app.route("/warnings")
def warnings_page():
    records = get_records()
    warnings = threshold_warnings(records) if records else []
    return render_template("warnings.html", warnings=warnings)


@app.route("/charts", methods=["GET", "POST"])
def charts_page():
    records = get_records()
    available = plotting.chart_available()
    results: list[tuple[str, bool]] = []
    if request.method == "POST" and records and available:
        for item in plotting.generate_all(records, storage.reports_dir() / "charts"):
            results.append((Path(item).name, True) if isinstance(item, Path) else (str(item), False))
        if any(ok for _, ok in results):
            flash("Charts generated.", "ok")
        else:
            flash(next((m for m, ok in results if not ok), "Chart generation failed."), "error")
        return redirect(url_for("charts_page"))
    chart_dir = storage.reports_dir() / "charts"
    existing = sorted(p.name for p in chart_dir.glob("*.png")) if chart_dir.exists() else []
    return render_template(
        "charts.html", available=available, charts=existing, mpl_error=plotting.MPL_ERROR
    )


@app.route("/charts/<path:name>")
def chart_image(name: str):
    return send_from_directory(storage.reports_dir() / "charts", name)


@app.route("/reports", methods=["GET", "POST"])
def reports_page():
    records = get_records()
    if request.method == "POST":
        kind = request.form.get("kind")
        if not records:
            flash("No data to export.", "error")
            return redirect(url_for("reports_page"))
        makers = {
            "md": (reports.export_markdown, "Markdown summary"),
            "txt": (reports.export_text_log, "Text audit log"),
            "metrics": (reports.export_summary_csv, "Metrics CSV"),
            "csv": (reports.export_records_csv, "Records CSV"),
        }
        if kind in makers:
            fn, label = makers[kind]
            path = fn(records)
            flash(f"{label} exported: {path.name}", "ok")
        return redirect(url_for("reports_page"))
    files = sorted(
        (p.name, p.stat().st_size)
        for p in storage.reports_dir().glob("garden_*.*")
    )
    return render_template("reports.html", files=files[::-1])


@app.route("/reports/download/<path:name>")
def download_report(name: str):
    return send_from_directory(storage.reports_dir(), name, as_attachment=True)


@app.route("/import", methods=["GET", "POST"])
def import_page():
    records = get_records()
    errors: list[str] = []
    preview: list[PlantRecord] = []
    do_merge = False
    if request.method == "POST":
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            tmp = storage.writable(storage.DATA_DIR / "_upload.csv")
            uploaded.save(tmp)
        else:
            raw = (request.form.get("path") or "").strip()
            tmp = Path(raw).expanduser() if raw else None
        if not tmp or not tmp.exists():
            errors = [f"file not found: {tmp}"]
        else:
            preview, errors = storage.import_csv_file(tmp)
            do_merge = request.form.get("action") == "merge"
            if do_merge and preview:
                existing = {r.id for r in records}
                base = storage.next_id(records)
                added = 0
                for r in preview:
                    if r.id in existing or r.id <= 0:
                        r.id = base
                        base += 1
                        existing.add(r.id)
                    records.append(r)
                    added += 1
                put_records(records)
                flash(f"Imported {added} record(s). Total now {len(records)}.", "ok")
                return redirect(url_for("records_page"))
        try:
            if tmp and tmp.name == "_upload.csv":
                tmp.unlink(missing_ok=True)
        except OSError:
            pass
    sample = storage.SAMPLE_CSV.name if storage.SAMPLE_CSV.exists() else None
    return render_template(
        "import.html",
        errors=errors,
        preview=preview,
        sample=sample,
        sample_path=str(storage.SAMPLE_CSV),
    )


@app.route("/seed", methods=["POST"])
def seed():
    records = get_records()
    if not storage.SAMPLE_CSV.exists():
        flash("Sample dataset missing.", "error")
        return redirect(url_for("dashboard"))
    replace = request.form.get("replace") == "1"
    if records and not replace:
        flash(
            f"{len(records)} record(s) already exist — tick “Replace existing data” to re-seed.",
            "error",
        )
        return redirect(url_for("dashboard"))
    imported, errors = storage.import_csv_file(storage.SAMPLE_CSV)
    fresh: list[PlantRecord] = []
    for r in imported:
        r.id = len(fresh) + 1
        fresh.append(r)
    put_records(fresh)
    flash(f"Loaded {len(fresh)} demo record(s)." + (f" ({len(errors)} row issues)" if errors else ""), "ok")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Community Garden Planner (web) → http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
