"""JSON endpoints behind the dashboard's sign-in (``/api/yoisho/...``).

Sellbird's guard checks every request here: the dashboard token as a bearer
header, same-origin only, JSON bodies for writes. Errors come back as
``{"error": "..."}`` with 400 (bad input), 403 (not allowed), 404 (missing)
or 409 (duplicate, with the existing record).
"""

from __future__ import annotations

from functools import wraps

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from yoisho_bd import vocab
from yoisho_bd.store import DuplicateOrganization, NotFound, Store

router = APIRouter(prefix="/api/yoisho")

_STORE: Store | None = None


async def store() -> Store:
    global _STORE
    if _STORE is None:
        s = Store.for_sellbird()
        await s.init()
        _STORE = s
    return _STORE


def use_store(s: Store) -> None:
    """Tests point the API at their own database."""
    global _STORE
    _STORE = s


def handled(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except DuplicateOrganization as e:
            return JSONResponse({"error": str(e), "existing": e.existing}, status_code=409)
        except NotFound as e:
            return JSONResponse({"error": str(e)}, status_code=404)
        except PermissionError as e:
            return JSONResponse({"error": str(e)}, status_code=403)
        except (ValueError, TypeError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    return wrapper


async def body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception as e:
        raise ValueError("send a JSON object") from e
    if not isinstance(data, dict):
        raise ValueError("send a JSON object")
    return data


def _flag(value) -> bool:
    return str(value).lower() in ("1", "true", "yes")


# ── reference lists for forms ──

@router.get("/vocab")
async def get_vocab():
    return {
        "japan_connection": vocab.JAPAN_CONNECTION, "fit": vocab.FIT,
        "competitor_class": vocab.COMPETITOR_CLASS,
        "relationship_status": vocab.RELATIONSHIP_STATUS, "priority": vocab.PRIORITY,
        "crm_stage": vocab.CRM_STAGE, "research_status": vocab.RESEARCH_STATUS,
        "org_types": vocab.ORG_TYPES, "pillar": vocab.PILLAR, "opp_stage": vocab.OPP_STAGE,
        "task_status": vocab.TASK_STATUS, "task_priority": vocab.TASK_PRIORITY,
        "interaction_kind": vocab.INTERACTION_KIND, "verification": vocab.VERIFICATION,
        "evidence_label": vocab.EVIDENCE_LABEL,
    }


@router.get("/counts")
@handled
async def get_counts():
    return await (await store()).counts()


@router.get("/search")
@handled
async def get_search(q: str = ""):
    return await (await store()).search(q)


# ── organizations ──

@router.get("/orgs")
@handled
async def list_orgs(request: Request):
    params = dict(request.query_params)
    s = await store()
    filters = {k: v for k, v in params.items() if k in Store.ORG_FILTERS and v}
    return {"items": await s.list_orgs(
        search=params.get("search", ""), include_archived=_flag(params.get("archived", "")),
        sort=params.get("sort", "updated"), descending=params.get("dir", "desc") != "asc",
        **filters)}


@router.post("/orgs")
@handled
async def create_org(request: Request):
    data = await body(request)
    name = data.pop("name", "")
    website = data.pop("website", "")
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return await (await store()).create_org(name, website, **data)


@router.get("/orgs/{org_id}")
@handled
async def get_org(org_id: str):
    s = await store()
    org = await s.get_org(org_id)
    allowed, why = Store.cold_outreach_allowed(org)
    return {
        "org": org,
        "cold_outreach": {"allowed": allowed, "reason": why},
        "contacts": await s.list_contacts(org_id=org_id, include_archived=True),
        "opportunities": await s.list_opportunities(org_id=org_id, include_archived=True),
        "tasks": await s.list_tasks(status="", org_id=org_id),
        "interactions": await s.list_interactions(org_id=org_id),
        "evidence": await s.list_evidence(org_id),
        "brief": await s.latest_brief(org_id),
        "history": (await s.history(org_id))[-30:],
    }


@router.patch("/orgs/{org_id}")
@handled
async def update_org(org_id: str, request: Request):
    data = await body(request)
    reason = data.pop("_reason", "")
    return await (await store()).update_org(org_id, data, reason=reason)


@router.post("/orgs/{org_id}/competitor")
@handled
async def set_competitor(org_id: str, request: Request):
    data = await body(request)
    return await (await store()).set_competitor_class(
        org_id, data.get("value", ""), reason=data.get("reason", ""))


@router.post("/orgs/{org_id}/relationship")
@handled
async def set_relationship(org_id: str, request: Request):
    data = await body(request)
    return await (await store()).set_relationship_status(
        org_id, data.get("value", ""), note=data.get("note", ""))


@router.post("/orgs/{org_id}/archive")
@handled
async def archive_org(org_id: str, request: Request):
    data = await body(request)
    return await (await store()).archive_org(org_id, reason=data.get("reason", ""))


@router.post("/orgs/{org_id}/restore")
@handled
async def restore_org(org_id: str):
    return await (await store()).restore_org(org_id)


# ── contacts ──

@router.get("/contacts")
@handled
async def list_contacts(search: str = "", org_id: str = "", archived: str = ""):
    return {"items": await (await store()).list_contacts(
        search=search, org_id=org_id, include_archived=_flag(archived))}


@router.post("/contacts")
@handled
async def create_contact(request: Request):
    data = await body(request)
    org_id, name = data.pop("org_id", ""), data.pop("name", "")
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return await (await store()).create_contact(org_id, name, **data)


@router.patch("/contacts/{contact_id}")
@handled
async def update_contact(contact_id: str, request: Request):
    data = await body(request)
    reason = data.pop("_reason", "")
    return await (await store()).update_contact(contact_id, data, reason=reason)


@router.post("/contacts/{contact_id}/archive")
@handled
async def archive_contact(contact_id: str, request: Request):
    data = await body(request)
    return await (await store()).archive_contact(contact_id, reason=data.get("reason", ""))


@router.post("/contacts/{contact_id}/restore")
@handled
async def restore_contact(contact_id: str):
    return await (await store()).restore_contact(contact_id)


# ── opportunities ──

@router.get("/opportunities")
@handled
async def list_opps(search: str = "", pillar: str = "", stage: str = "", active: str = "",
                    archived: str = ""):
    return {"items": await (await store()).list_opportunities(
        search=search, pillar=pillar, stage=stage, active_only=_flag(active),
        include_archived=_flag(archived))}


@router.post("/opportunities")
@handled
async def create_opp(request: Request):
    data = await body(request)
    org_id, name, pillar = data.pop("org_id", ""), data.pop("name", ""), data.pop("pillar", "")
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return await (await store()).create_opportunity(org_id, name, pillar, **data)


@router.patch("/opportunities/{opp_id}")
@handled
async def update_opp(opp_id: str, request: Request):
    data = await body(request)
    reason = data.pop("_reason", "")
    return await (await store()).update_opportunity(opp_id, data, reason=reason)


@router.post("/opportunities/{opp_id}/archive")
@handled
async def archive_opp(opp_id: str, request: Request):
    data = await body(request)
    return await (await store()).archive_opportunity(opp_id, reason=data.get("reason", ""))


@router.post("/opportunities/{opp_id}/restore")
@handled
async def restore_opp(opp_id: str):
    return await (await store()).restore_opportunity(opp_id)


# ── tasks ──

@router.get("/tasks")
@handled
async def list_tasks(search: str = "", status: str = "OPEN"):
    s = await store()
    if status == "OPEN" and not search:
        return {"buckets": await s.task_buckets()}
    return {"items": await s.list_tasks(status=status, search=search)}


@router.post("/tasks")
@handled
async def create_task(request: Request):
    data = await body(request)
    title = data.pop("title", "")
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return await (await store()).create_task(title, **data)


@router.patch("/tasks/{task_id}")
@handled
async def update_task(task_id: str, request: Request):
    data = await body(request)
    reason = data.pop("_reason", "")
    return await (await store()).update_task(task_id, data, reason=reason)


@router.post("/tasks/{task_id}/archive")
@handled
async def archive_task(task_id: str, request: Request):
    data = await body(request)
    return await (await store()).archive_task(task_id, reason=data.get("reason", ""))


# ── interactions and notes ──

@router.post("/interactions")
@handled
async def create_interaction(request: Request):
    data = await body(request)
    kind = data.pop("kind", "")
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return await (await store()).record_interaction(kind, **data)


@router.post("/interactions/{interaction_id}/archive")
@handled
async def archive_interaction(interaction_id: str, request: Request):
    data = await body(request)
    return await (await store()).archive_interaction(interaction_id, reason=data.get("reason", ""))
