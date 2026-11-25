"""Phase 1 step 1c: endpoints, pages and the sign-in guard. Fictional data only."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.middleware import Middleware

from yoisho_bd import api, server
from yoisho_bd.store import Store


class Open:  # stands in for the sign-in, so tests reach the routes
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


@pytest.fixture
def client(tmp_path):
    import sellbird.dashboard as dash
    s = Store(str(tmp_path / "bd.db"))
    asyncio.run(s.init())
    api.use_store(s)
    app = dash.build_app(guard=Middleware(Open), routers=[server.pages])
    yield TestClient(app)
    api.use_store(None)


def test_org_crud_and_duplicates(client):
    r = client.post("/api/yoisho/orgs", json={"name": "Api Example", "website": "api.example.com",
                                             "city": "Gurugram"})
    assert r.status_code == 200
    org = r.json()
    assert org["id"] == "ORG-000001"
    dup = client.post("/api/yoisho/orgs", json={"name": "Other", "website": "https://api.example.com"})
    assert dup.status_code == 409 and dup.json()["existing"]["id"] == org["id"]
    bad = client.post("/api/yoisho/orgs", json={"name": ""})
    assert bad.status_code == 400

    patched = client.patch(f"/api/yoisho/orgs/{org['id']}",
                           json={"industry": "Automotive", "_reason": "from website"}).json()
    assert patched["industry"] == "Automotive"
    detail = client.get(f"/api/yoisho/orgs/{org['id']}").json()
    assert detail["cold_outreach"]["allowed"] is True
    assert any(h["field"] == "industry" and h["reason"] == "from website" for h in detail["history"])
    assert client.get("/api/yoisho/orgs/ORG-999999").status_code == 404

    listed = client.get("/api/yoisho/orgs?city=Gurugram&sort=name&dir=asc").json()["items"]
    assert [o["id"] for o in listed] == [org["id"]]


def test_labels_through_api(client):
    org = client.post("/api/yoisho/orgs", json={"name": "Label Example"}).json()
    assert client.post(f"/api/yoisho/orgs/{org['id']}/competitor",
                       json={"value": "RED", "reason": ""}).status_code == 400
    red = client.post(f"/api/yoisho/orgs/{org['id']}/competitor",
                      json={"value": "RED", "reason": "Japanese institute in India (R1)"}).json()
    assert red["competitor_class"] == "RED" and red["competitor_set_by"] == "founder"
    assert client.get(f"/api/yoisho/orgs/{org['id']}").json()["cold_outreach"]["allowed"] is False
    rel = client.post(f"/api/yoisho/orgs/{org['id']}/relationship",
                      json={"value": "EXISTING_PARTNER", "note": "MOU"}).json()
    assert rel["relationship_status"] == "EXISTING_PARTNER"
    # Labels can't be changed through a plain edit.
    assert client.patch(f"/api/yoisho/orgs/{org['id']}",
                        json={"competitor_class": "GREEN"}).status_code == 400


def test_archive_restore_through_api(client):
    org = client.post("/api/yoisho/orgs", json={"name": "Archive Example"}).json()
    client.post(f"/api/yoisho/orgs/{org['id']}/archive", json={"reason": "test"})
    assert client.get("/api/yoisho/orgs").json()["items"] == []
    assert len(client.get("/api/yoisho/orgs?archived=1").json()["items"]) == 1
    client.post(f"/api/yoisho/orgs/{org['id']}/restore")
    assert len(client.get("/api/yoisho/orgs").json()["items"]) == 1


def test_contacts_opps_tasks_notes_search_counts(client):
    org = client.post("/api/yoisho/orgs", json={"name": "Flow Example"}).json()
    c = client.post("/api/yoisho/contacts", json={"org_id": org["id"], "name": "Hana Example",
                                                 "job_title": "HR Head", "is_primary": True}).json()
    assert c["is_primary"] == 1
    no_source = client.post("/api/yoisho/contacts", json={"org_id": org["id"], "name": "X",
                                                         "email": "x@flow.example.com"})
    assert no_source.status_code == 400
    p = client.post("/api/yoisho/opportunities", json={"org_id": org["id"], "name": "Pilot batch",
                                                      "pillar": "LEARN", "probability": ""}).json()
    assert p["probability"] is None and p["potential_value"] == ""
    t = client.post("/api/yoisho/tasks", json={"title": "Call HR", "org_id": org["id"],
                                              "due_date": "2020-01-01"}).json()
    buckets = client.get("/api/yoisho/tasks").json()["buckets"]
    assert [x["id"] for x in buckets["overdue"]] == [t["id"]]
    done = client.patch(f"/api/yoisho/tasks/{t['id']}", json={"status": "DONE"}).json()
    assert done["status"] == "DONE"
    note = client.post("/api/yoisho/interactions", json={"kind": "MEETING", "org_id": org["id"],
                                                        "summary": "Met at an event"})
    assert note.status_code == 200
    hits = client.get("/api/yoisho/search?q=flow").json()
    assert len(hits["organizations"]) == 1 and len(hits["contacts"]) == 1
    counts = client.get("/api/yoisho/counts").json()
    assert counts["organizations"] == 1 and counts["active_opportunities"] == 1
    assert counts["tasks_due"] == 0
    vocab = client.get("/api/yoisho/vocab").json()
    assert "RED" in vocab["competitor_class"]


def test_pages_and_theme(client, tmp_path, monkeypatch):
    home = client.get("/")
    assert home.status_code == 200 and "Yoisho BD OS" in home.text
    assert "/static/auth.js" in home.text            # sign-in runs first
    css = client.get("/static/app.css").text
    assert "Yoisho theme" in css and "--accent: #B9531D" in css
    engine = client.get("/static/engine.html").text
    assert "Yoisho BD OS: engine" in engine and 'class="yo-back"' in engine
    assert client.get("/static/yoisho/app.js").status_code == 200
    assert client.get("/static/yoisho/..%2Fserver.py").status_code == 404
    assert client.get("/static/yoisho/missing.js").status_code == 404
    # Logo: 404 without a file, served from private/brand/ when present.
    monkeypatch.setattr(server, "PRIVATE_BRAND", tmp_path / "brand")
    assert client.get("/static/yoisho-logo").status_code == 404
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "logo.png").write_bytes(b"\x89PNG fake")
    r = client.get("/static/yoisho-logo")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_real_guard_refuses_data_without_token(tmp_path):
    import sellbird.dashboard as dash
    s = Store(str(tmp_path / "bd.db"))
    asyncio.run(s.init())
    api.use_store(s)
    try:
        client = TestClient(dash.build_app(routers=[server.pages]), base_url="http://127.0.0.1:5555")
        assert client.get("/").status_code == 200                       # page holds no data
        assert client.get("/api/yoisho/counts").status_code == 401      # data needs the token
        assert client.get("/api/yoisho/orgs").status_code == 401
        evil = client.get("/api/yoisho/counts", headers={"Origin": "https://evil.example.com"})
        assert evil.status_code in (401, 403)
    finally:
        api.use_store(None)
