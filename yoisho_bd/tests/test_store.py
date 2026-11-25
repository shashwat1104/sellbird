"""Phase 1 step 1b: the data foundation. Fictional data only (public repo)."""

import asyncio
import csv
from datetime import date, timedelta

import pytest

from yoisho_bd.importer import import_csv
from yoisho_bd.store import (DuplicateOrganization, NotFound, Store, name_key,
                             normalize_domain, today)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "bd.db"))
    run(s.init())
    return s


# ── helpers ──

def test_normalize_domain():
    assert normalize_domain("https://www.Example.co.jp/en/") == "example.co.jp"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("") == ""


def test_name_key_strips_legal_suffixes():
    assert name_key("Fictional Motors India Pvt. Ltd.") == name_key("fictional motors")
    assert name_key("Kabushiki Kaisha Sample") == "sample"


# ── schema ──

def test_init_is_repeatable_and_leaves_user_version_alone(store):
    run(store.init())

    async def check():
        async with store.connect() as db:
            async with db.execute("PRAGMA user_version") as c:
                (uv,) = await c.fetchone()
            async with db.execute("SELECT value FROM yo_meta WHERE key='schema_version'") as c:
                (sv,) = await c.fetchone()
        return uv, sv
    uv, sv = run(check())
    assert uv == 0          # Sellbird's migration counter is never touched
    assert sv == "1"


# ── organizations ──

def test_create_org_gives_stable_ids(store):
    a = run(store.create_org("Alpha Example", "alpha.example.com", city="Gurugram"))
    b = run(store.create_org("Beta Example", "beta.example.com"))
    assert a["id"] == "ORG-000001" and b["id"] == "ORG-000002"
    assert a["domain"] == "alpha.example.com"
    assert a["relationship_status"] == "COLD_PROSPECT" and a["competitor_class"] == "GREEN"


def test_duplicate_by_domain_refused(store):
    run(store.create_org("Alpha Example", "https://www.alpha.example.com/about"))
    with pytest.raises(DuplicateOrganization) as e:
        run(store.create_org("Alpha Renamed", "alpha.example.com"))
    assert "same website" in str(e.value)


def test_duplicate_by_name_when_no_website(store):
    run(store.create_org("Sample Language School"))
    with pytest.raises(DuplicateOrganization):
        run(store.create_org("sample language school k.k."))


def test_same_name_different_sites_allowed(store):
    run(store.create_org("Gamma Example", "gamma.example.jp"))
    org = run(store.create_org("Gamma Example", "gamma-india.example.in"))
    assert org["id"] == "ORG-000002"


def test_archived_duplicate_is_named(store):
    org = run(store.create_org("Delta Example", "delta.example.com"))
    run(store.archive_org(org["id"], reason="test"))
    with pytest.raises(DuplicateOrganization) as e:
        run(store.create_org("Delta Example", "delta.example.com"))
    assert "(archived)" in str(e.value)


def test_update_org_validates_and_audits(store):
    org = run(store.create_org("Epsilon Example", "eps.example.com"))
    with pytest.raises(ValueError):
        run(store.update_org(org["id"], {"japan_connection": "HUGE"}))
    with pytest.raises(ValueError):
        run(store.update_org(org["id"], {"not_a_field": 1}))
    run(store.update_org(org["id"], {"industry": "Automotive", "next_action_date": "2026-12-01"},
                         reason="research"))
    history = run(store.history(org["id"]))
    fields = [h["field"] for h in history]
    assert "created" in fields and "industry" in fields and "next_action_date" in fields
    with pytest.raises(ValueError):
        run(store.update_org(org["id"], {"next_action_date": "next week"}))


def test_update_org_rename_into_duplicate_refused(store):
    run(store.create_org("Zeta Example", "zeta.example.com"))
    other = run(store.create_org("Eta Example", "eta.example.com"))
    with pytest.raises(DuplicateOrganization):
        run(store.update_org(other["id"], {"website": "zeta.example.com"}))


def test_archive_and_restore(store):
    org = run(store.create_org("Theta Example"))
    run(store.archive_org(org["id"], reason="not relevant"))
    assert run(store.list_orgs()) == []
    assert len(run(store.list_orgs(include_archived=True))) == 1
    run(store.restore_org(org["id"]))
    assert len(run(store.list_orgs())) == 1


def test_list_orgs_filters_search_sort(store):
    run(store.create_org("Iota Example", city="Pune", industry="Automotive"))
    run(store.create_org("Kappa Example", city="Chennai", industry="Education"))
    run(store.create_org("Lambda Example", city="Pune", industry="Education"))
    assert {o["name"] for o in run(store.list_orgs(city="Pune"))} == {"Iota Example", "Lambda Example"}
    assert [o["name"] for o in run(store.list_orgs(search="educ", sort="name", descending=False))] \
        == ["Kappa Example", "Lambda Example"]
    with pytest.raises(ValueError):
        run(store.list_orgs(colour="blue"))
    with pytest.raises(ValueError):
        run(store.update_org(run(store.list_orgs())[0]["id"], {"priority": "P9"}))


def test_missing_record_raises(store):
    with pytest.raises(NotFound):
        run(store.get_org("ORG-999999"))


# ── labels ──

def test_red_only_by_founder_or_rule(store):
    org = run(store.create_org("Mu Example"))
    with pytest.raises(PermissionError):
        run(store.set_competitor_class(org["id"], "RED", reason="looks similar", actor="system"))
    run(store.set_competitor_class(org["id"], "RED", reason="R1 applies", actor="rule:R1"))
    org = run(store.set_competitor_class(org["id"], "GREEN", reason="override: partner now"))
    assert org["competitor_class"] == "GREEN" and org["competitor_set_by"] == "founder"


def test_label_change_needs_reason(store):
    org = run(store.create_org("Nu Example"))
    with pytest.raises(ValueError):
        run(store.set_competitor_class(org["id"], "YELLOW", reason=" "))


def test_labels_not_settable_through_update(store):
    org = run(store.create_org("Xi Example"))
    with pytest.raises(ValueError):
        run(store.update_org(org["id"], {"competitor_class": "RED"}))


def test_cold_outreach_rules(store):
    org = run(store.create_org("Omicron Example"))
    assert Store.cold_outreach_allowed(org) == (True, "allowed")
    yellow = run(store.set_competitor_class(org["id"], "YELLOW", reason="possible overlap",
                                            actor="system"))
    assert not Store.cold_outreach_allowed(yellow)[0]
    reviewed = run(store.set_competitor_class(org["id"], "YELLOW", reason="reviewed, fine"))
    assert Store.cold_outreach_allowed(reviewed)[0]
    partner = run(store.set_relationship_status(org["id"], "EXISTING_PARTNER", note="MOU"))
    allowed, why = Store.cold_outreach_allowed(partner)
    assert not allowed and "Existing partner" in why


# ── contacts ──

def test_contacts_link_and_primary_cap(store):
    org = run(store.create_org("Pi Example"))
    run(store.create_contact(org["id"], "Asha Example", is_primary=True))
    run(store.create_contact(org["id"], "Ben Example", is_primary=True))
    with pytest.raises(ValueError):
        run(store.create_contact(org["id"], "Chie Example", is_primary=True))
    third = run(store.create_contact(org["id"], "Chie Example"))
    assert third["is_primary"] == 0
    contacts = run(store.list_contacts(org_id=org["id"]))
    assert len(contacts) == 3 and contacts[0]["org_name"] == "Pi Example"


def test_contact_email_needs_source(store):
    org = run(store.create_org("Rho Example"))
    with pytest.raises(ValueError):
        run(store.create_contact(org["id"], "Dev Example", email="dev@rho.example.com"))
    with pytest.raises(ValueError):
        run(store.create_contact(org["id"], "Dev Example", email="not-an-email",
                                 email_source="manual"))
    c = run(store.create_contact(org["id"], "Dev Example", email="dev@rho.example.com",
                                 email_source="company website"))
    assert c["verification_status"] == "UNVERIFIED"


def test_contact_needs_existing_org(store):
    with pytest.raises(NotFound):
        run(store.create_contact("ORG-999999", "Eve Example"))


def test_archive_contact(store):
    org = run(store.create_org("Sigma Example"))
    c = run(store.create_contact(org["id"], "Fumi Example"))
    run(store.archive_contact(c["id"], reason="left company"))
    assert run(store.list_contacts(org_id=org["id"])) == []


# ── opportunities ──

def test_opportunity_never_invents_value(store):
    org = run(store.create_org("Tau Example"))
    opp = run(store.create_opportunity(org["id"], "Corporate Japanese pilot", "LEARN"))
    assert opp["potential_value"] == "" and opp["probability"] is None
    with pytest.raises(ValueError):
        run(store.create_opportunity(org["id"], "Bad", "COOKING"))
    with pytest.raises(ValueError):
        run(store.update_opportunity(opp["id"], {"probability": 150}))
    opp = run(store.update_opportunity(opp["id"], {"stage": "QUALIFIED", "probability": ""}))
    assert opp["stage"] == "QUALIFIED" and opp["probability"] is None


def test_active_opportunities(store):
    org = run(store.create_org("Upsilon Example"))
    a = run(store.create_opportunity(org["id"], "A", "STUDY"))
    run(store.create_opportunity(org["id"], "B", "WORK", stage="LOST"))
    active = run(store.list_opportunities(active_only=True))
    assert [o["id"] for o in active] == [a["id"]]


# ── tasks ──

def test_task_buckets_and_completion(store):
    t0 = today()
    run(store.create_task("Overdue", due_date=(t0 - timedelta(days=2)).isoformat()))
    run(store.create_task("Today", due_date=t0.isoformat(), priority="HIGH"))
    soon = run(store.create_task("Soon", due_date=(t0 + timedelta(days=3)).isoformat()))
    run(store.create_task("No date"))
    buckets = run(store.task_buckets())
    assert [t["title"] for t in buckets["overdue"]] == ["Overdue"]
    assert [t["title"] for t in buckets["today"]] == ["Today"]
    assert [t["title"] for t in buckets["upcoming"]] == ["Soon"]
    assert [t["title"] for t in buckets["no_date"]] == ["No date"]

    done = run(store.complete_task(soon["id"]))
    assert done["status"] == "DONE" and done["completed_at"]
    again = run(store.reopen_task(soon["id"]))
    assert again["status"] == "OPEN" and again["completed_at"] is None
    moved = run(store.reschedule_task(soon["id"], (t0 + timedelta(days=30)).isoformat()))
    assert moved["due_date"] == (t0 + timedelta(days=30)).isoformat()
    with pytest.raises(ValueError):
        run(store.update_task(soon["id"], {"priority": "URGENT"}))


def test_task_links_must_exist(store):
    with pytest.raises(NotFound):
        run(store.create_task("Ghost", org_id="ORG-999999"))


# ── interactions ──

def test_interaction_updates_last_contact(store):
    org = run(store.create_org("Phi Example"))
    run(store.record_interaction("CALL", org_id=org["id"], occurred_on="2026-11-20",
                                 summary="intro call"))
    run(store.record_interaction("NOTE", org_id=org["id"], occurred_on="2026-11-24",
                                 summary="internal note"))
    org = run(store.get_org(org["id"]))
    assert org["last_contact"] == "2026-11-20"       # notes are not contact
    assert len(run(store.list_interactions(org_id=org["id"]))) == 2
    with pytest.raises(ValueError):
        run(store.record_interaction("CALL"))


# ── search ──

def test_search_across_records(store):
    org = run(store.create_org("Chi Robotics Example"))
    run(store.create_contact(org["id"], "Gita Example", job_title="HR Head"))
    run(store.create_opportunity(org["id"], "Robotics engineers for Japan", "WORK"))
    run(store.create_task("Research Chi Robotics hiring", org_id=org["id"]))
    hits = run(store.search("robotics"))
    assert len(hits["organizations"]) == 1
    assert len(hits["contacts"]) == 1      # matched through the organization name
    assert len(hits["opportunities"]) == 1
    assert len(hits["tasks"]) == 1
    assert run(store.search("")) == {"organizations": [], "contacts": [],
                                     "opportunities": [], "tasks": []}


# ── evidence, briefs, scores ──

def test_fact_needs_source(store):
    org = run(store.create_org("Psi Example"))
    with pytest.raises(ValueError):
        run(store.add_evidence(org["id"], "japan", "Parent company is in Osaka", "FACT"))
    ev = run(store.add_evidence(org["id"], "japan", "Parent company is in Osaka", "FACT",
                                source_url="https://psi.example.com/about"))
    assert ev["label"] == "FACT"
    run(store.add_evidence(org["id"], "hiring", "No hiring page found", "UNKNOWN"))
    assert len(run(store.list_evidence(org["id"], topic="japan"))) == 1


def test_brief_and_score_round_trip(store):
    org = run(store.create_org("Omega Example"))
    brief = run(store.save_brief(org["id"], "L1", {"overview": "x"}, pages_read=2))
    assert run(store.latest_brief(org["id"]))["id"] == brief["id"]
    score = run(store.save_score(org["id"], 82, "P1", {"japan": 25}, explanation="e"))
    assert score["factors"] == {"japan": 25}
    org = run(store.get_org(org["id"]))
    assert org["opportunity_score"] == 82 and org["priority"] == "P1"


# ── counts ──

def test_counts_match_records(store):
    assert run(store.counts())["organizations"] == 0
    org = run(store.create_org("Count Example"))
    run(store.update_org(org["id"], {"crm_stage": "QUALIFIED"}))
    run(store.save_score(org["id"], 85, "P1", {}))
    run(store.create_opportunity(org["id"], "Pilot", "LEARN"))
    run(store.create_task("Due today", due_date=today().isoformat()))
    run(store.create_task("Due later", due_date=(today() + timedelta(days=9)).isoformat()))
    c = run(store.counts())
    assert c == {"organizations": 1, "qualified": 1, "p1": 1, "active_opportunities": 1,
                 "tasks_due": 1, "contacts": 0}


# ── CSV import ──

def test_import_relationship_list(store, tmp_path):
    existing = run(store.create_org("Sample School Example", "school.example.jp"))
    path = tmp_path / "list.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "website", "relationship_status", "competitor_class", "note"])
        w.writerow(["Sample School Example", "https://school.example.jp", "Existing partner", "", "MOU"])
        w.writerow(["Rival Institute Example", "rival.example.in", "", "RED", "R1"])
        w.writerow(["", "", "", "", ""])
        w.writerow(["Bad Row Example", "", "Best friends", "", ""])
    result = run(import_csv(store, path))
    assert result.updated == [existing["id"]]
    assert len(result.created) == 1          # a row with a bad label is not created
    assert len(result.errors) == 2
    assert run(store.get_org(existing["id"]))["relationship_status"] == "EXISTING_PARTNER"
    rival = [o for o in run(store.list_orgs()) if o["name"] == "Rival Institute Example"][0]
    assert rival["competitor_class"] == "RED"
    assert not [o for o in run(store.list_orgs()) if o["name"] == "Bad Row Example"]
