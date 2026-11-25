"""Read and write Yoisho BD OS records.

Rules this module enforces, so every screen and command gets them for free:

- Stable, readable IDs (ORG-000001, CON-000001, ...). An ID is never reused.
- No deletes. Records are archived and can be restored.
- Duplicate organizations are refused: same website domain, or the same name
  when there is no website. Archived records count, so an archived duplicate
  is found and named instead of a second copy being made.
- Every change to a field is written to ``yo_audit`` with who made it and why.
- RED comes only from the founder or a founder's category rule, never from
  the system's own judgment (TARGETING section 3).
- At most two primary contacts per organization (brief section 8.8).
"""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiosqlite

from yoisho_bd import vocab
from yoisho_bd.schema import MIGRATIONS

TZ = ZoneInfo("Asia/Kolkata")

FOUNDER = "founder"
SYSTEM = "system"


class DuplicateOrganization(ValueError):
    def __init__(self, existing: dict, why: str):
        self.existing = existing
        self.why = why
        state = " (archived)" if existing.get("archived_at") else ""
        super().__init__(f"{existing['name']} already exists as {existing['id']}{state}: {why}")


class NotFound(LookupError):
    pass


def today() -> date:
    return datetime.now(TZ).date()


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def normalize_domain(value: str) -> str:
    """'https://www.Example.co.jp/en/' -> 'example.co.jp'."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "http://" + value
    host = urlparse(value).hostname or ""
    return host.removeprefix("www.").rstrip(".")


_LEGAL = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|incorporated|corp|corporation|co|company|"
    r"kabushiki|kaisha|kk|gk|plc|llc|india|japan)\b")


def name_key(name: str) -> str:
    """A name reduced for duplicate checks: no accents, case, punctuation or
    legal suffixes. 'ABC Japan Pvt. Ltd.' and 'abc' give the same key."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace(".", ""))
    stripped = _LEGAL.sub(" ", text)
    key = re.sub(r"\s+", " ", stripped).strip()
    return key or re.sub(r"\s+", " ", text).strip()


ORG_FIELDS = {
    "name", "website", "country", "state_region", "city", "industry", "sub_industry",
    "org_type", "japan_connection", "japan_connection_evidence", "japan_confidence",
    "learn_fit", "study_fit", "work_fit", "opportunity_score", "relationship_score",
    "research_confidence", "priority", "crm_stage", "territory_tier", "last_contact",
    "next_action", "next_action_date", "research_status", "sources", "notes",
    "sellbird_company_id",
}
CONTACT_FIELDS = {
    "name", "job_title", "department", "email", "email_source", "verification_status",
    "linkedin", "country", "language", "relevance", "confidence", "source", "is_primary",
    "relationship_status", "last_contact", "next_follow_up", "notes", "sellbird_prospect_id",
}
OPP_FIELDS = {
    "name", "pillar", "opp_type", "description", "evidence", "hypothesis", "potential_value",
    "probability", "priority", "stage", "target_date", "next_action", "next_action_date",
    "outcome", "notes", "origin",
}
TASK_FIELDS = {"title", "org_id", "contact_id", "opp_id", "task_type", "priority", "due_date",
               "status", "notes"}
INTERACTION_FIELDS = {"org_id", "contact_id", "opp_id", "kind", "occurred_on", "summary",
                      "outcome", "next_action", "next_action_date"}

_CHECKED = {
    "japan_connection": vocab.JAPAN_CONNECTION,
    "learn_fit": vocab.FIT, "study_fit": vocab.FIT, "work_fit": vocab.FIT,
    "crm_stage": vocab.CRM_STAGE,
    "research_status": vocab.RESEARCH_STATUS,
}
_DATE_FIELDS = {"next_action_date", "last_contact", "next_follow_up", "due_date",
                "target_date", "occurred_on"}

PREFIX = {"yo_organizations": "ORG", "yo_contacts": "CON", "yo_opportunities": "OPP",
          "yo_tasks": "TSK", "yo_interactions": "INT", "yo_briefs": "BRF",
          "yo_evidence": "EVD", "yo_scores": "SCR"}


def _clean_date(field: str, value) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as e:
        raise ValueError(f"{field}: {value!r} is not a date (use YYYY-MM-DD)") from e


def _validate(fields: dict, allowed: set[str], kind: str) -> dict:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"{kind}: unknown field(s) {', '.join(sorted(unknown))}")
    out = {}
    for key, value in fields.items():
        if key in _CHECKED and value is not None:
            vocab.check(value, _CHECKED[key], key)
        if key in _DATE_FIELDS:
            value = _clean_date(key, value)
        if isinstance(value, str):
            value = value.strip()
        out[key] = value
    return out


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @classmethod
    def for_sellbird(cls) -> "Store":
        """The store inside Sellbird's own database file."""
        from sellbird.state import StateManager
        return cls(StateManager().db_path)

    @asynccontextmanager
    async def connect(self):
        async with aiosqlite.connect(self.db_path, timeout=30) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")
            yield db

    async def init(self) -> None:
        async with self.connect() as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                "CREATE TABLE IF NOT EXISTS yo_meta (key TEXT PRIMARY KEY, value TEXT)")
            async with db.execute("SELECT value FROM yo_meta WHERE key='schema_version'") as c:
                row = await c.fetchone()
            version = int(row[0]) if row else 0
            for target, script in enumerate(MIGRATIONS, start=1):
                if version < target:
                    await db.executescript(script)
                    await db.execute(
                        "INSERT INTO yo_meta(key, value) VALUES('schema_version', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(target),))
                    await db.commit()

    # ── shared helpers ──

    async def _next_id(self, db, table: str) -> str:
        prefix = PREFIX[table]
        await db.execute(
            "INSERT INTO yo_counters(prefix, value) VALUES(?, 1) "
            "ON CONFLICT(prefix) DO UPDATE SET value = value + 1", (prefix,))
        async with db.execute("SELECT value FROM yo_counters WHERE prefix=?", (prefix,)) as c:
            (value,) = await c.fetchone()
        return f"{prefix}-{value:06d}"

    async def _get(self, db, table: str, record_id: str) -> dict:
        async with db.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)) as c:
            row = await c.fetchone()
        if row is None:
            raise NotFound(f"{record_id} not found")
        return dict(row)

    async def _insert(self, db, table: str, fields: dict) -> str:
        record_id = await self._next_id(db, table)
        fields = {"id": record_id, **fields}
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        await db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(fields.values()))
        return record_id

    async def _update(self, db, table: str, record_id: str, changes: dict, *, actor: str,
                      reason: str) -> dict:
        before = await self._get(db, table, record_id)
        changed = {k: v for k, v in changes.items() if before.get(k) != v}
        if not changed:
            return before
        sets = ", ".join(f"{k}=?" for k in changed)
        stamp = ", updated_at=?" if "updated_at" in before else ""
        params = list(changed.values()) + ([now_iso()] if stamp else []) + [record_id]
        await db.execute(f"UPDATE {table} SET {sets}{stamp} WHERE id=?", params)
        for field, value in changed.items():
            await self._audit(db, table, record_id, field, before.get(field), value, actor, reason)
        return await self._get(db, table, record_id)

    async def _audit(self, db, table, record_id, field, old, new, actor, reason):
        await db.execute(
            "INSERT INTO yo_audit(entity, entity_id, field, old_value, new_value, reason, actor, at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (table, record_id, field, None if old is None else str(old),
             None if new is None else str(new), reason or "", actor, now_iso()))

    async def _set_archived(self, table: str, record_id: str, archived: bool, actor: str,
                            reason: str) -> dict:
        async with self.connect() as db:
            value = now_iso() if archived else None
            record = await self._update(db, table, record_id, {"archived_at": value},
                                        actor=actor, reason=reason)
            await db.commit()
            return record

    async def history(self, record_id: str) -> list[dict]:
        async with self.connect() as db:
            async with db.execute(
                    "SELECT * FROM yo_audit WHERE entity_id=? ORDER BY id", (record_id,)) as c:
                return [dict(r) for r in await c.fetchall()]

    # ── organizations ──

    async def find_duplicate(self, name: str, website: str = "", *, exclude_id: str = "",
                             db=None) -> tuple[dict, str] | None:
        domain = normalize_domain(website)
        key = name_key(name)

        async def _run(conn):
            if domain:
                async with conn.execute(
                        "SELECT * FROM yo_organizations WHERE domain=? AND id!=?",
                        (domain, exclude_id)) as c:
                    row = await c.fetchone()
                if row:
                    return dict(row), f"same website ({domain})"
            if key:
                async with conn.execute(
                        "SELECT * FROM yo_organizations WHERE name_key=? AND id!=?",
                        (key, exclude_id)) as c:
                    for row in await c.fetchall():
                        row = dict(row)
                        # Two different websites with the same name are two
                        # organizations (a parent and its Indian subsidiary).
                        if domain and row["domain"] and row["domain"] != domain:
                            continue
                        return row, "same name"
            return None

        if db is not None:
            return await _run(db)
        async with self.connect() as conn:
            return await _run(conn)

    async def create_org(self, name: str, website: str = "", *, actor: str = FOUNDER,
                         **fields) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("name: an organization needs a name")
        fields = _validate(fields, ORG_FIELDS - {"name", "website"}, "organization")
        if "priority" in fields:
            vocab.check(fields["priority"], vocab.PRIORITY, "priority")
        async with self.connect() as db:
            hit = await self.find_duplicate(name, website, db=db)
            if hit:
                raise DuplicateOrganization(*hit)
            record_id = await self._insert(db, "yo_organizations", {
                "name": name, "name_key": name_key(name), "website": (website or "").strip(),
                "domain": normalize_domain(website), "created_at": now_iso(),
                "updated_at": now_iso(), **fields})
            await self._audit(db, "yo_organizations", record_id, "created", None, name, actor, "")
            await db.commit()
            return await self._get(db, "yo_organizations", record_id)

    async def get_org(self, org_id: str) -> dict:
        async with self.connect() as db:
            return await self._get(db, "yo_organizations", org_id)

    async def update_org(self, org_id: str, changes: dict, *, actor: str = FOUNDER,
                         reason: str = "") -> dict:
        if {"competitor_class", "relationship_status"} & set(changes):
            raise ValueError("use set_competitor_class or set_relationship_status for labels")
        changes = _validate(changes, ORG_FIELDS, "organization")
        if "priority" in changes:
            vocab.check(changes["priority"], vocab.PRIORITY, "priority")
        async with self.connect() as db:
            if "name" in changes or "website" in changes:
                current = await self._get(db, "yo_organizations", org_id)
                name = changes.get("name", current["name"])
                website = changes.get("website", current["website"])
                hit = await self.find_duplicate(name, website, exclude_id=org_id, db=db)
                if hit:
                    raise DuplicateOrganization(*hit)
                changes["name_key"] = name_key(name)
                changes["domain"] = normalize_domain(website)
            record = await self._update(db, "yo_organizations", org_id, changes,
                                        actor=actor, reason=reason)
            await db.commit()
            return record

    async def set_competitor_class(self, org_id: str, value: str, *, reason: str,
                                   actor: str = FOUNDER) -> dict:
        vocab.check(value, vocab.COMPETITOR_CLASS, "competitor_class")
        if not (reason or "").strip():
            raise ValueError("competitor_class: a change needs a reason")
        if value == "RED" and not (actor == FOUNDER or actor.startswith("rule:")):
            raise PermissionError("Only the founder or a founder's rule can mark an organization RED")
        async with self.connect() as db:
            record = await self._update(
                db, "yo_organizations", org_id,
                {"competitor_class": value, "competitor_reason": reason.strip(),
                 "competitor_set_by": actor}, actor=actor, reason=reason)
            await db.commit()
            return record

    async def set_relationship_status(self, org_id: str, value: str, *, note: str = "",
                                      actor: str = FOUNDER) -> dict:
        vocab.check(value, vocab.RELATIONSHIP_STATUS, "relationship_status")
        async with self.connect() as db:
            record = await self._update(
                db, "yo_organizations", org_id,
                {"relationship_status": value, "relationship_note": (note or "").strip()},
                actor=actor, reason=note)
            await db.commit()
            return record

    async def archive_org(self, org_id: str, *, reason: str = "", actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_organizations", org_id, True, actor, reason)

    async def restore_org(self, org_id: str, *, actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_organizations", org_id, False, actor, "restored")

    ORG_SORTS = {"name": "name COLLATE NOCASE", "score": "opportunity_score",
                 "added": "created_at", "updated": "updated_at", "priority": "priority",
                 "next_action_date": "next_action_date", "city": "city COLLATE NOCASE",
                 "territory": "territory_tier"}
    ORG_FILTERS = {"country", "city", "industry", "org_type", "priority", "competitor_class",
                   "relationship_status", "japan_connection", "crm_stage", "research_status"}

    async def list_orgs(self, *, search: str = "", include_archived: bool = False,
                        sort: str = "updated", descending: bool = True, limit: int = 500,
                        **filters) -> list[dict]:
        unknown = set(filters) - self.ORG_FILTERS
        if unknown:
            raise ValueError(f"unknown filter(s): {', '.join(sorted(unknown))}")
        where, params = [], []
        if not include_archived:
            where.append("archived_at IS NULL")
        for key, value in filters.items():
            if value not in (None, ""):
                where.append(f"{key} = ?")
                params.append(value)
        if search.strip():
            like = f"%{search.strip().lower()}%"
            where.append("(lower(name) LIKE ? OR domain LIKE ? OR lower(city) LIKE ? "
                         "OR lower(industry) LIKE ? OR lower(notes) LIKE ?)")
            params += [like] * 5
        order = self.ORG_SORTS.get(sort, self.ORG_SORTS["updated"])
        direction = "DESC" if descending else "ASC"
        sql = "SELECT * FROM yo_organizations"
        if where:
            sql += " WHERE " + " AND ".join(where)
        # Empty values sort last whichever way the list runs.
        sql += f" ORDER BY ({order} IS NULL OR {order} = ''), {order} {direction} LIMIT ?"
        params.append(int(limit))
        async with self.connect() as db:
            async with db.execute(sql, params) as c:
                return [dict(r) for r in await c.fetchall()]

    @staticmethod
    def cold_outreach_allowed(org: dict) -> tuple[bool, str]:
        """Cold outreach needs GREEN (or YELLOW after founder review) and Cold Prospect."""
        if org.get("archived_at"):
            return False, "archived"
        if org.get("relationship_status") != "COLD_PROSPECT":
            label = vocab.RELATIONSHIP_STATUS.get(org.get("relationship_status"), "known relationship")
            return False, f"{label}: no cold outreach"
        cls = org.get("competitor_class")
        if cls == "RED":
            return False, "Red: competitor"
        if cls == "YELLOW" and org.get("competitor_set_by") != FOUNDER:
            return False, "Yellow: needs your review first"
        return True, "allowed"

    # ── contacts ──

    async def _primary_count(self, db, org_id: str, exclude_id: str = "") -> int:
        async with db.execute(
                "SELECT COUNT(*) FROM yo_contacts WHERE org_id=? AND is_primary=1 "
                "AND archived_at IS NULL AND id!=?", (org_id, exclude_id)) as c:
            (n,) = await c.fetchone()
        return n

    async def create_contact(self, org_id: str, name: str, *, actor: str = FOUNDER,
                             **fields) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("name: a contact needs a name")
        fields = _validate(fields, CONTACT_FIELDS - {"name"}, "contact")
        if "verification_status" in fields:
            vocab.check(fields["verification_status"], vocab.VERIFICATION, "verification_status")
        if fields.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", fields["email"]):
            raise ValueError(f"email: {fields['email']!r} is not an email address")
        if fields.get("email") and not fields.get("email_source"):
            raise ValueError("email_source: say where the email came from")
        async with self.connect() as db:
            await self._get(db, "yo_organizations", org_id)
            fields["is_primary"] = int(bool(fields.get("is_primary", 0)))
            if fields["is_primary"] and await self._primary_count(db, org_id) >= vocab.MAX_PRIMARY_CONTACTS:
                raise ValueError(f"is_primary: this organization already has "
                                 f"{vocab.MAX_PRIMARY_CONTACTS} primary contacts")
            record_id = await self._insert(db, "yo_contacts", {
                "org_id": org_id, "name": name, "created_at": now_iso(),
                "updated_at": now_iso(), **fields})
            await self._audit(db, "yo_contacts", record_id, "created", None, name, actor, "")
            await db.commit()
            return await self._get(db, "yo_contacts", record_id)

    async def update_contact(self, contact_id: str, changes: dict, *, actor: str = FOUNDER,
                             reason: str = "") -> dict:
        changes = _validate(changes, CONTACT_FIELDS, "contact")
        if "verification_status" in changes:
            vocab.check(changes["verification_status"], vocab.VERIFICATION, "verification_status")
        async with self.connect() as db:
            current = await self._get(db, "yo_contacts", contact_id)
            if "is_primary" in changes:
                changes["is_primary"] = int(bool(changes["is_primary"]))
                if changes["is_primary"] and await self._primary_count(
                        db, current["org_id"], contact_id) >= vocab.MAX_PRIMARY_CONTACTS:
                    raise ValueError(f"is_primary: this organization already has "
                                     f"{vocab.MAX_PRIMARY_CONTACTS} primary contacts")
            record = await self._update(db, "yo_contacts", contact_id, changes,
                                        actor=actor, reason=reason)
            await db.commit()
            return record

    async def get_contact(self, contact_id: str) -> dict:
        async with self.connect() as db:
            return await self._get(db, "yo_contacts", contact_id)

    async def archive_contact(self, contact_id: str, *, reason: str = "",
                              actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_contacts", contact_id, True, actor, reason)

    async def restore_contact(self, contact_id: str, *, actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_contacts", contact_id, False, actor, "restored")

    async def list_contacts(self, *, org_id: str = "", search: str = "",
                            include_archived: bool = False, limit: int = 500) -> list[dict]:
        where, params = [], []
        if not include_archived:
            where.append("c.archived_at IS NULL")
        if org_id:
            where.append("c.org_id = ?")
            params.append(org_id)
        if search.strip():
            like = f"%{search.strip().lower()}%"
            where.append("(lower(c.name) LIKE ? OR lower(c.job_title) LIKE ? "
                         "OR lower(c.email) LIKE ? OR lower(o.name) LIKE ?)")
            params += [like] * 4
        sql = ("SELECT c.*, o.name AS org_name FROM yo_contacts c "
               "JOIN yo_organizations o ON o.id = c.org_id")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY c.is_primary DESC, c.name COLLATE NOCASE LIMIT ?"
        params.append(int(limit))
        async with self.connect() as db:
            async with db.execute(sql, params) as c:
                return [dict(r) for r in await c.fetchall()]

    # ── opportunities ──

    async def create_opportunity(self, org_id: str, name: str, pillar: str, *,
                                 actor: str = FOUNDER, **fields) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("name: an opportunity needs a name")
        vocab.check(pillar, vocab.PILLAR, "pillar")
        fields = _validate(fields, OPP_FIELDS - {"name", "pillar"}, "opportunity")
        if "stage" in fields:
            vocab.check(fields["stage"], vocab.OPP_STAGE, "stage")
        if fields.get("probability") not in (None, ""):
            p = int(fields["probability"])
            if not 0 <= p <= 100:
                raise ValueError("probability: use 0 to 100, or leave it empty")
            fields["probability"] = p
        else:
            fields["probability"] = None
        async with self.connect() as db:
            await self._get(db, "yo_organizations", org_id)
            record_id = await self._insert(db, "yo_opportunities", {
                "org_id": org_id, "name": name, "pillar": pillar, "created_at": now_iso(),
                "updated_at": now_iso(), **fields})
            await self._audit(db, "yo_opportunities", record_id, "created", None, name, actor, "")
            await db.commit()
            return await self._get(db, "yo_opportunities", record_id)

    async def update_opportunity(self, opp_id: str, changes: dict, *, actor: str = FOUNDER,
                                 reason: str = "") -> dict:
        changes = _validate(changes, OPP_FIELDS, "opportunity")
        if "pillar" in changes:
            vocab.check(changes["pillar"], vocab.PILLAR, "pillar")
        if "stage" in changes:
            vocab.check(changes["stage"], vocab.OPP_STAGE, "stage")
        if "probability" in changes:
            p = changes["probability"]
            changes["probability"] = None if p in (None, "") else int(p)
            if changes["probability"] is not None and not 0 <= changes["probability"] <= 100:
                raise ValueError("probability: use 0 to 100, or leave it empty")
        async with self.connect() as db:
            record = await self._update(db, "yo_opportunities", opp_id, changes,
                                        actor=actor, reason=reason)
            await db.commit()
            return record

    async def get_opportunity(self, opp_id: str) -> dict:
        async with self.connect() as db:
            return await self._get(db, "yo_opportunities", opp_id)

    async def archive_opportunity(self, opp_id: str, *, reason: str = "",
                                  actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_opportunities", opp_id, True, actor, reason)

    async def restore_opportunity(self, opp_id: str, *, actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_opportunities", opp_id, False, actor, "restored")

    ACTIVE_OPP_STAGES = ("IDENTIFIED", "RESEARCHING", "QUALIFIED", "IN_DISCUSSION", "PROPOSAL")

    async def list_opportunities(self, *, org_id: str = "", pillar: str = "", stage: str = "",
                                 active_only: bool = False, search: str = "",
                                 include_archived: bool = False, limit: int = 500) -> list[dict]:
        where, params = [], []
        if not include_archived:
            where.append("p.archived_at IS NULL")
        for col, value in (("p.org_id", org_id), ("p.pillar", pillar), ("p.stage", stage)):
            if value:
                where.append(f"{col} = ?")
                params.append(value)
        if active_only:
            where.append(f"p.stage IN ({','.join('?' * len(self.ACTIVE_OPP_STAGES))})")
            params += list(self.ACTIVE_OPP_STAGES)
        if search.strip():
            like = f"%{search.strip().lower()}%"
            where.append("(lower(p.name) LIKE ? OR lower(p.description) LIKE ? OR lower(o.name) LIKE ?)")
            params += [like] * 3
        sql = ("SELECT p.*, o.name AS org_name FROM yo_opportunities p "
               "JOIN yo_organizations o ON o.id = p.org_id")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY p.updated_at DESC LIMIT ?"
        params.append(int(limit))
        async with self.connect() as db:
            async with db.execute(sql, params) as c:
                return [dict(r) for r in await c.fetchall()]

    # ── tasks ──

    async def create_task(self, title: str, *, actor: str = FOUNDER, **fields) -> dict:
        title = (title or "").strip()
        if not title:
            raise ValueError("title: a task needs a title")
        fields = _validate(fields, TASK_FIELDS - {"title"}, "task")
        if "priority" in fields:
            vocab.check(fields["priority"], vocab.TASK_PRIORITY, "priority")
        async with self.connect() as db:
            for table, key in (("yo_organizations", "org_id"), ("yo_contacts", "contact_id"),
                               ("yo_opportunities", "opp_id")):
                if fields.get(key):
                    await self._get(db, table, fields[key])
            record_id = await self._insert(db, "yo_tasks", {
                "title": title, "created_at": now_iso(), "updated_at": now_iso(), **fields})
            await self._audit(db, "yo_tasks", record_id, "created", None, title, actor, "")
            await db.commit()
            return await self._get(db, "yo_tasks", record_id)

    async def update_task(self, task_id: str, changes: dict, *, actor: str = FOUNDER,
                          reason: str = "") -> dict:
        changes = _validate(changes, TASK_FIELDS, "task")
        if "priority" in changes:
            vocab.check(changes["priority"], vocab.TASK_PRIORITY, "priority")
        if "status" in changes:
            vocab.check(changes["status"], vocab.TASK_STATUS, "status")
        async with self.connect() as db:
            if "status" in changes:
                changes = dict(changes)
                record = await self._update(db, "yo_tasks", task_id, changes,
                                            actor=actor, reason=reason)
                done_at = now_iso() if changes["status"] == "DONE" else None
                await db.execute("UPDATE yo_tasks SET completed_at=? WHERE id=?", (done_at, task_id))
                record = await self._get(db, "yo_tasks", task_id)
            else:
                record = await self._update(db, "yo_tasks", task_id, changes,
                                            actor=actor, reason=reason)
            await db.commit()
            return record

    async def complete_task(self, task_id: str, *, actor: str = FOUNDER) -> dict:
        return await self.update_task(task_id, {"status": "DONE"}, actor=actor)

    async def reopen_task(self, task_id: str, *, actor: str = FOUNDER) -> dict:
        return await self.update_task(task_id, {"status": "OPEN"}, actor=actor)

    async def reschedule_task(self, task_id: str, due_date: str, *, actor: str = FOUNDER,
                              reason: str = "") -> dict:
        return await self.update_task(task_id, {"due_date": due_date}, actor=actor, reason=reason)

    async def get_task(self, task_id: str) -> dict:
        async with self.connect() as db:
            return await self._get(db, "yo_tasks", task_id)

    async def archive_task(self, task_id: str, *, reason: str = "", actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_tasks", task_id, True, actor, reason)

    async def list_tasks(self, *, status: str = "OPEN", org_id: str = "", search: str = "",
                         include_archived: bool = False, limit: int = 500) -> list[dict]:
        where, params = [], []
        if not include_archived:
            where.append("t.archived_at IS NULL")
        if status:
            where.append("t.status = ?")
            params.append(status)
        if org_id:
            where.append("t.org_id = ?")
            params.append(org_id)
        if search.strip():
            like = f"%{search.strip().lower()}%"
            where.append("(lower(t.title) LIKE ? OR lower(t.notes) LIKE ? OR lower(o.name) LIKE ?)")
            params += [like] * 3
        sql = ("SELECT t.*, o.name AS org_name FROM yo_tasks t "
               "LEFT JOIN yo_organizations o ON o.id = t.org_id")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (" ORDER BY (t.due_date = ''), t.due_date, "
                "CASE t.priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END LIMIT ?")
        params.append(int(limit))
        async with self.connect() as db:
            async with db.execute(sql, params) as c:
                return [dict(r) for r in await c.fetchall()]

    async def task_buckets(self, *, on: date | None = None, upcoming_days: int = 7) -> dict:
        """Open tasks split into overdue, today, upcoming (next N days) and later."""
        on = on or today()
        horizon = on + timedelta(days=upcoming_days)
        buckets = {"overdue": [], "today": [], "upcoming": [], "later": [], "no_date": []}
        for task in await self.list_tasks(status="OPEN"):
            due = task["due_date"]
            if not due:
                buckets["no_date"].append(task)
                continue
            d = date.fromisoformat(due)
            if d < on:
                buckets["overdue"].append(task)
            elif d == on:
                buckets["today"].append(task)
            elif d <= horizon:
                buckets["upcoming"].append(task)
            else:
                buckets["later"].append(task)
        return buckets

    # ── interactions ──

    async def record_interaction(self, kind: str, *, actor: str = FOUNDER, **fields) -> dict:
        vocab.check(kind, vocab.INTERACTION_KIND, "kind")
        fields = _validate(fields, INTERACTION_FIELDS - {"kind"}, "interaction")
        fields.setdefault("occurred_on", today().isoformat())
        if not fields["occurred_on"]:
            fields["occurred_on"] = today().isoformat()
        if not any(fields.get(k) for k in ("org_id", "contact_id", "opp_id")):
            raise ValueError("an interaction needs an organization, contact or opportunity")
        async with self.connect() as db:
            for table, key in (("yo_organizations", "org_id"), ("yo_contacts", "contact_id"),
                               ("yo_opportunities", "opp_id")):
                if fields.get(key):
                    await self._get(db, table, fields[key])
            record_id = await self._insert(db, "yo_interactions", {
                "kind": kind, "created_at": now_iso(), **fields})
            await self._audit(db, "yo_interactions", record_id, "created", None, kind, actor, "")
            if fields.get("org_id") and kind != "NOTE":
                org = await self._get(db, "yo_organizations", fields["org_id"])
                if fields["occurred_on"] > (org["last_contact"] or ""):
                    await self._update(db, "yo_organizations", fields["org_id"],
                                       {"last_contact": fields["occurred_on"]},
                                       actor=actor, reason=f"interaction {record_id}")
            await db.commit()
            return await self._get(db, "yo_interactions", record_id)

    async def list_interactions(self, *, org_id: str = "", contact_id: str = "",
                                opp_id: str = "", limit: int = 200) -> list[dict]:
        where, params = ["archived_at IS NULL"], []
        for col, value in (("org_id", org_id), ("contact_id", contact_id), ("opp_id", opp_id)):
            if value:
                where.append(f"{col} = ?")
                params.append(value)
        sql = ("SELECT * FROM yo_interactions WHERE " + " AND ".join(where)
               + " ORDER BY occurred_on DESC, id DESC LIMIT ?")
        params.append(int(limit))
        async with self.connect() as db:
            async with db.execute(sql, params) as c:
                return [dict(r) for r in await c.fetchall()]

    async def archive_interaction(self, interaction_id: str, *, reason: str = "",
                                  actor: str = FOUNDER) -> dict:
        return await self._set_archived("yo_interactions", interaction_id, True, actor, reason)

    # ── search across everything ──

    async def search(self, query: str, *, limit: int = 20) -> dict:
        query = (query or "").strip()
        if not query:
            return {"organizations": [], "contacts": [], "opportunities": [], "tasks": []}
        return {
            "organizations": await self.list_orgs(search=query, limit=limit),
            "contacts": await self.list_contacts(search=query, limit=limit),
            "opportunities": await self.list_opportunities(search=query, limit=limit),
            "tasks": await self.list_tasks(status="", search=query, limit=limit),
        }

    # ── evidence, briefs, scores (filled by later steps) ──

    async def add_evidence(self, org_id: str, topic: str, claim: str, label: str, *,
                           source_url: str = "", source_title: str = "", source_date: str = "",
                           confidence: str = "", brief_id: str = "") -> dict:
        vocab.check(label, vocab.EVIDENCE_LABEL, "label")
        claim = (claim or "").strip()
        if not claim:
            raise ValueError("claim: evidence needs a claim")
        if label == "FACT" and not source_url:
            raise ValueError("source_url: a verified fact needs its source")
        async with self.connect() as db:
            await self._get(db, "yo_organizations", org_id)
            record_id = await self._insert(db, "yo_evidence", {
                "org_id": org_id, "brief_id": brief_id, "topic": topic, "claim": claim,
                "label": label, "source_url": source_url, "source_title": source_title,
                "source_date": source_date, "confidence": confidence,
                "retrieved_at": now_iso()})
            await db.commit()
            return await self._get(db, "yo_evidence", record_id)

    async def list_evidence(self, org_id: str, *, topic: str = "", brief_id: str = "") -> list[dict]:
        sql, params = "SELECT * FROM yo_evidence WHERE org_id=?", [org_id]
        if topic:
            sql += " AND topic=?"
            params.append(topic)
        if brief_id:
            sql += " AND brief_id=?"
            params.append(brief_id)
        async with self.connect() as db:
            async with db.execute(sql + " ORDER BY id", params) as c:
                return [dict(r) for r in await c.fetchall()]

    async def save_brief(self, org_id: str, depth: str, content: dict, *, pages_read: int = 0) -> dict:
        async with self.connect() as db:
            await self._get(db, "yo_organizations", org_id)
            record_id = await self._insert(db, "yo_briefs", {
                "org_id": org_id, "depth": depth, "content": json.dumps(content),
                "pages_read": pages_read, "created_at": now_iso()})
            await db.commit()
            row = await self._get(db, "yo_briefs", record_id)
        row["content"] = json.loads(row["content"])
        return row

    async def latest_brief(self, org_id: str) -> dict | None:
        async with self.connect() as db:
            async with db.execute(
                    "SELECT * FROM yo_briefs WHERE org_id=? ORDER BY created_at DESC, id DESC LIMIT 1",
                    (org_id,)) as c:
                row = await c.fetchone()
        if row is None:
            return None
        row = dict(row)
        row["content"] = json.loads(row["content"])
        return row

    async def save_score(self, org_id: str, total: int, priority: str, factors: dict, *,
                         explanation: str = "", inputs_hash: str = "") -> dict:
        vocab.check(priority, vocab.PRIORITY, "priority")
        async with self.connect() as db:
            record_id = await self._insert(db, "yo_scores", {
                "org_id": org_id, "total": int(total), "priority": priority,
                "factors": json.dumps(factors), "explanation": explanation,
                "inputs_hash": inputs_hash, "created_at": now_iso()})
            await self._update(db, "yo_organizations", org_id,
                               {"opportunity_score": int(total), "priority": priority},
                               actor=SYSTEM, reason=f"score {record_id}")
            await db.commit()
            row = await self._get(db, "yo_scores", record_id)
        row["factors"] = json.loads(row["factors"])
        return row

    # ── counts for the dashboard ──

    async def counts(self) -> dict:
        on = today().isoformat()
        queries = {
            "organizations": "SELECT COUNT(*) FROM yo_organizations WHERE archived_at IS NULL",
            "qualified": "SELECT COUNT(*) FROM yo_organizations WHERE archived_at IS NULL "
                         "AND crm_stage IN ('QUALIFIED','CONTACTING','IN_CONVERSATION')",
            "p1": "SELECT COUNT(*) FROM yo_organizations WHERE archived_at IS NULL AND priority='P1'",
            "active_opportunities": "SELECT COUNT(*) FROM yo_opportunities WHERE archived_at IS NULL "
                                    "AND stage IN ('IDENTIFIED','RESEARCHING','QUALIFIED',"
                                    "'IN_DISCUSSION','PROPOSAL')",
            "tasks_due": "SELECT COUNT(*) FROM yo_tasks WHERE archived_at IS NULL AND status='OPEN' "
                         "AND due_date != '' AND due_date <= :on",
            "contacts": "SELECT COUNT(*) FROM yo_contacts WHERE archived_at IS NULL",
        }
        out = {}
        async with self.connect() as db:
            for key, sql in queries.items():
                async with db.execute(sql, {"on": on} if ":on" in sql else ()) as c:
                    (out[key],) = await c.fetchone()
        return out
