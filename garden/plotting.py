from __future__ import annotations

from collections import Counter
from pathlib import Path

from .analytics import summarize, trend_points
from .models import PlantRecord

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
    MPL_ERROR = ""
except ImportError as exc:  # defensive fallback per brief
    HAS_MPL = False
    MPL_ERROR = str(exc)
    plt = None  # type: ignore[assignment]


def _finish(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def chart_available() -> bool:
    return HAS_MPL


def plot_status(records: list[PlantRecord], path: Path) -> Path | str:
    if not HAS_MPL:
        return f"matplotlib unavailable ({MPL_ERROR}); install with: pip install matplotlib"
    if not records:
        return "no records to plot"
    summary = summarize(records)
    labels = list(summary["by_status"].keys())
    values = list(summary["by_status"].values())
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = ["#4CAF50", "#8BC34A", "#FF9800", "#F44336"]
    ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors[: len(values)], startangle=90)
    ax.set_title("Plant Status Distribution")
    return _finish(fig, path)


def plot_beds(records: list[PlantRecord], path: Path) -> Path | str:
    if not HAS_MPL:
        return f"matplotlib unavailable ({MPL_ERROR}); install with: pip install matplotlib"
    if not records:
        return "no records to plot"
    counts = Counter(r.bed for r in records)
    beds = sorted(counts)
    values = [counts[b] for b in beds]
    fig, ax = plt.subplots(figsize=(max(7, len(beds) * 0.6), 5))
    ax.bar(beds, values, color="#4CAF50", edgecolor="#2E7D32")
    ax.set_xlabel("Garden Bed")
    ax.set_ylabel("Plant Records")
    ax.set_title("Records per Garden Bed")
    ax.tick_params(axis="x", rotation=45)
    return _finish(fig, path)


def plot_sowing_trend(records: list[PlantRecord], path: Path) -> Path | str:
    if not HAS_MPL:
        return f"matplotlib unavailable ({MPL_ERROR}); install with: pip install matplotlib"
    if not records:
        return "no records to plot"
    months, values = trend_points(records)
    if not months:
        return "no sowing dates to plot"
    fig, ax = plt.subplots(figsize=(max(7, len(months) * 0.5), 4.5))
    ax.plot(months, values, marker="o", color="#2E7D32", linewidth=2)
    ax.fill_between(range(len(months)), values, alpha=0.15, color="#4CAF50")
    ax.set_xlabel("Month")
    ax.set_ylabel("Plants Sown")
    ax.set_title("Sowing Trend Over Time")
    ax.tick_params(axis="x", rotation=45)
    return _finish(fig, path)


def generate_all(records: list[PlantRecord], out_dir: Path) -> list[Path | str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path | str] = []
    for name, fn in (
        ("status_distribution.png", plot_status),
        ("records_per_bed.png", plot_beds),
        ("sowing_trend.png", plot_sowing_trend),
    ):
        results.append(fn(records, out_dir / name))
    return results
