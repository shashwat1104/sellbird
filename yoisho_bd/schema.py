"""Yoisho BD OS tables, kept in Sellbird's SQLite file with a ``yo_`` prefix.

Yoisho tracks its own schema version in ``yo_meta``. It never reads or writes
SQLite's ``PRAGMA user_version``, which belongs to Sellbird's migrations.
Each migration is additive: new tables, new columns, new indexes. Nothing is
dropped, and records are archived rather than deleted.
"""

from __future__ import annotations

MIGRATIONS: list[str] = [
    # 1: Phase 1 foundation
    """
    CREATE TABLE IF NOT EXISTS yo_counters (
        prefix TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS yo_organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_key TEXT NOT NULL,
        website TEXT DEFAULT '',
        domain TEXT DEFAULT '',
        country TEXT DEFAULT '',
        state_region TEXT DEFAULT '',
        city TEXT DEFAULT '',
        industry TEXT DEFAULT '',
        sub_industry TEXT DEFAULT '',
        org_type TEXT DEFAULT '',
        japan_connection TEXT DEFAULT 'NOT_ASSESSED',
        japan_connection_evidence TEXT DEFAULT '',
        japan_confidence TEXT DEFAULT '',
        learn_fit TEXT DEFAULT '',
        study_fit TEXT DEFAULT '',
        work_fit TEXT DEFAULT '',
        competitor_class TEXT DEFAULT 'GREEN',
        competitor_reason TEXT DEFAULT '',
        competitor_set_by TEXT DEFAULT 'default',
        relationship_status TEXT DEFAULT 'COLD_PROSPECT',
        relationship_note TEXT DEFAULT '',
        opportunity_score INTEGER,
        relationship_score INTEGER,
        research_confidence TEXT DEFAULT '',
        priority TEXT DEFAULT '',
        crm_stage TEXT DEFAULT 'IDENTIFIED',
        territory_tier INTEGER,
        last_contact TEXT DEFAULT '',
        next_action TEXT DEFAULT '',
        next_action_date TEXT DEFAULT '',
        research_status TEXT DEFAULT 'NOT_STARTED',
        sources TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        sellbird_company_id TEXT DEFAULT '',
        archived_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_org_domain ON yo_organizations(domain);
    CREATE INDEX IF NOT EXISTS yo_org_name_key ON yo_organizations(name_key);

    CREATE TABLE IF NOT EXISTS yo_contacts (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL REFERENCES yo_organizations(id),
        name TEXT NOT NULL,
        job_title TEXT DEFAULT '',
        department TEXT DEFAULT '',
        email TEXT DEFAULT '',
        email_source TEXT DEFAULT '',
        verification_status TEXT DEFAULT 'UNVERIFIED',
        linkedin TEXT DEFAULT '',
        country TEXT DEFAULT '',
        language TEXT DEFAULT '',
        relevance TEXT DEFAULT '',
        confidence TEXT DEFAULT '',
        source TEXT DEFAULT '',
        is_primary INTEGER DEFAULT 0,
        relationship_status TEXT DEFAULT 'COLD_PROSPECT',
        last_contact TEXT DEFAULT '',
        next_follow_up TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        sellbird_prospect_id TEXT DEFAULT '',
        archived_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_contact_org ON yo_contacts(org_id);

    CREATE TABLE IF NOT EXISTS yo_opportunities (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL REFERENCES yo_organizations(id),
        name TEXT NOT NULL,
        pillar TEXT NOT NULL,
        opp_type TEXT DEFAULT '',
        description TEXT DEFAULT '',
        evidence TEXT DEFAULT '',
        hypothesis TEXT DEFAULT '',
        potential_value TEXT DEFAULT '',
        probability INTEGER,
        priority TEXT DEFAULT '',
        stage TEXT DEFAULT 'IDENTIFIED',
        target_date TEXT DEFAULT '',
        next_action TEXT DEFAULT '',
        next_action_date TEXT DEFAULT '',
        outcome TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        origin TEXT DEFAULT 'manual',
        archived_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_opp_org ON yo_opportunities(org_id);

    CREATE TABLE IF NOT EXISTS yo_tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        org_id TEXT DEFAULT '',
        contact_id TEXT DEFAULT '',
        opp_id TEXT DEFAULT '',
        task_type TEXT DEFAULT '',
        priority TEXT DEFAULT 'MEDIUM',
        due_date TEXT DEFAULT '',
        status TEXT DEFAULT 'OPEN',
        notes TEXT DEFAULT '',
        completed_at TEXT,
        archived_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_task_due ON yo_tasks(status, due_date);

    CREATE TABLE IF NOT EXISTS yo_interactions (
        id TEXT PRIMARY KEY,
        org_id TEXT DEFAULT '',
        contact_id TEXT DEFAULT '',
        opp_id TEXT DEFAULT '',
        kind TEXT NOT NULL,
        occurred_on TEXT NOT NULL,
        summary TEXT DEFAULT '',
        outcome TEXT DEFAULT '',
        next_action TEXT DEFAULT '',
        next_action_date TEXT DEFAULT '',
        archived_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_int_org ON yo_interactions(org_id);

    CREATE TABLE IF NOT EXISTS yo_briefs (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL REFERENCES yo_organizations(id),
        depth TEXT NOT NULL,
        content TEXT NOT NULL,
        pages_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_brief_org ON yo_briefs(org_id);

    CREATE TABLE IF NOT EXISTS yo_evidence (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL REFERENCES yo_organizations(id),
        brief_id TEXT DEFAULT '',
        topic TEXT NOT NULL,
        claim TEXT NOT NULL,
        label TEXT NOT NULL,
        source_url TEXT DEFAULT '',
        source_title TEXT DEFAULT '',
        source_date TEXT DEFAULT '',
        confidence TEXT DEFAULT '',
        retrieved_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_evidence_org ON yo_evidence(org_id, topic);

    CREATE TABLE IF NOT EXISTS yo_scores (
        id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL REFERENCES yo_organizations(id),
        total INTEGER NOT NULL,
        priority TEXT NOT NULL,
        factors TEXT NOT NULL,
        explanation TEXT DEFAULT '',
        inputs_hash TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_score_org ON yo_scores(org_id);

    CREATE TABLE IF NOT EXISTS yo_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        reason TEXT DEFAULT '',
        actor TEXT DEFAULT '',
        at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS yo_audit_entity ON yo_audit(entity, entity_id);
    """,
]
