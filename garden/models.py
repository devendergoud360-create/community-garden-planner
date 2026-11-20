from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Any

STATUSES = ("planted", "growing", "harvested", "failed")

REQUIRED_FIELDS = ("id", "bed", "plant", "sown_date", "status")


@dataclass
class PlantRecord:
    id: int
    bed: str
    plant: str
    sown_date: str
    status: str = "planted"
    variety: str = ""
    days_to_harvest: int = 60
    expected_harvest: str = ""
    harvest_date: str = ""
    harvest_notes: str = ""
    yield_kg: float = 0.0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.expected_harvest:
            self.expected_harvest = self._compute_expected()

    def _compute_expected(self) -> str:
        try:
            sown = date.fromisoformat(self.sown_date)
        except ValueError:
            return self.expected_harvest
        return (sown + timedelta(days=self.days_to_harvest)).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlantRecord:
        missing = [k for k in REQUIRED_FIELDS if k not in data or data[k] in (None, "")]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        known = {f: data.get(f) for f in cls.__dataclass_fields__}
        known["id"] = int(known["id"])
        known["bed"] = str(known["bed"]).strip()
        known["plant"] = str(known["plant"]).strip()
        known["sown_date"] = str(known["sown_date"]).strip()
        try:
            date.fromisoformat(known["sown_date"])
        except ValueError:
            raise ValueError(f"invalid sown_date '{known['sown_date']}' (expected YYYY-MM-DD)") from None
        status = str(known.get("status") or "planted").strip().lower()
        if status not in STATUSES:
            raise ValueError(f"invalid status '{status}'")
        known["status"] = status
        known["days_to_harvest"] = int(known.get("days_to_harvest") or 60)
        if not 1 <= known["days_to_harvest"] <= 365:
            raise ValueError(f"days_to_harvest out of range: {known['days_to_harvest']}")
        known["yield_kg"] = float(known.get("yield_kg") or 0.0)
        if not 0.0 <= known["yield_kg"] <= 1000.0:
            raise ValueError(f"yield_kg out of range: {known['yield_kg']}")
        notes = known.get("harvest_notes")
        known["harvest_notes"] = str(notes) if notes is not None else ""
        variety = known.get("variety")
        known["variety"] = str(variety) if variety is not None else ""
        harvest_date = known.get("harvest_date")
        known["harvest_date"] = str(harvest_date) if harvest_date else ""
        if known["harvest_date"]:
            try:
                date.fromisoformat(known["harvest_date"])
            except ValueError:
                raise ValueError(f"invalid harvest_date '{known['harvest_date']}'") from None
        expected = known.get("expected_harvest")
        known["expected_harvest"] = str(expected) if expected else ""
        if known["expected_harvest"]:
            try:
                date.fromisoformat(known["expected_harvest"])
            except ValueError:
                raise ValueError(f"invalid expected_harvest '{known['expected_harvest']}'") from None
        tags = known.get("tags") or []
        known["tags"] = [str(t) for t in tags] if isinstance(tags, list) else []
        rec = cls(**known)
        if not rec.expected_harvest:
            rec.expected_harvest = rec._compute_expected()
        return rec

    @property
    def expected_date(self) -> date | None:
        try:
            return date.fromisoformat(self.expected_harvest) if self.expected_harvest else None
        except ValueError:
            return None

    @property
    def sown(self) -> date | None:
        try:
            return date.fromisoformat(self.sown_date)
        except ValueError:
            return None

    @property
    def days_until_harvest(self) -> int | None:
        exp = self.expected_date
        if exp is None:
            return None
        return (exp - date.today()).days

    @property
    def is_overdue(self) -> bool:
        if self.status in ("harvested", "failed"):
            return False
        d = self.days_until_harvest
        return d is not None and d < 0

    @property
    def due_soon(self) -> bool:
        if self.status in ("harvested", "failed"):
            return False
        d = self.days_until_harvest
        return d is not None and 0 <= d <= 14
