"""Bring the founder's own lists in from a CSV file: existing clients, partners,
active relationships, competitors. The file stays on the server, never in git.

Columns (header row required, only ``name`` is mandatory):
    name, website, relationship_status, competitor_class, note, org_type, city, country

``relationship_status`` and ``competitor_class`` take either the code
(EXISTING_PARTNER) or the label shown on screen ("Existing partner").
A row naming an organization already in the CRM updates its labels and
never makes a second copy.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from yoisho_bd import vocab
from yoisho_bd.store import FOUNDER, DuplicateOrganization, Store


def _code(value: str, table: dict, column: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    upper = value.upper().replace(" ", "_").replace("-", "_")
    if upper in table:
        return upper
    for code, label in table.items():
        if label.lower() == value.lower() or label.split(":")[0].lower() == value.lower():
            return code
    raise ValueError(f"{column}: {value!r} is not one of {', '.join(table)}")


@dataclass
class ImportResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"{len(self.created)} added, {len(self.updated)} updated, "
                f"{len(self.errors)} rows with problems")


async def import_csv(store: Store, path: str | Path) -> ImportResult:
    result = ImportResult()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for number, raw in enumerate(rows, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        name = row.get("name", "")
        if not name:
            result.errors.append(f"row {number}: no name")
            continue
        try:
            status = _code(row.get("relationship_status", ""), vocab.RELATIONSHIP_STATUS,
                           "relationship_status")
            cls = _code(row.get("competitor_class", ""), vocab.COMPETITOR_CLASS, "competitor_class")
            note = row.get("note", "")
            extra = {k: row[k] for k in ("org_type", "city", "country") if row.get(k)}
            try:
                org = await store.create_org(name, row.get("website", ""), actor=FOUNDER, **extra)
                result.created.append(org["id"])
            except DuplicateOrganization as dup:
                org = dup.existing
                result.updated.append(org["id"])
            if status:
                await store.set_relationship_status(org["id"], status, note=note or "imported list")
            if cls:
                await store.set_competitor_class(org["id"], cls, reason=note or "imported list")
        except (ValueError, PermissionError) as e:
            result.errors.append(f"row {number} ({name}): {e}")
    return result
