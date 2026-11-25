"""Allowed values for Yoisho BD OS fields. One place, so screens, checks and
scoring agree. Labels are what the founder sees."""

from __future__ import annotations

JAPAN_CONNECTION = {
    "NOT_ASSESSED": "Not assessed",
    "NONE_FOUND": "None found",
    "WEAK": "Weak",
    "MODERATE": "Moderate",
    "STRONG": "Strong",
    "VERIFIED": "Verified direct connection",
}

FIT = {"": "Not assessed", "NONE": "None", "LOW": "Low", "MEDIUM": "Medium", "HIGH": "High"}

COMPETITOR_CLASS = {
    "GREEN": "Green: prospect or partner",
    "YELLOW": "Yellow: review required",
    "RED": "Red: competitor, no cold outreach",
}

RELATIONSHIP_STATUS = {
    "COLD_PROSPECT": "Cold prospect",
    "EXISTING_CLIENT": "Existing client",
    "EXISTING_PARTNER": "Existing partner",
    "ACTIVE_RELATIONSHIP": "Active relationship",
    "EXISTING_OPPORTUNITY": "Existing opportunity",
    "PREVIOUSLY_CONTACTED": "Previously contacted",
    "SUPPRESSED": "Suppressed from cold outreach",
}

PRIORITY = {"": "Not scored", "P1": "P1", "P2": "P2", "P3": "P3", "MONITOR": "Monitor"}

CRM_STAGE = {
    "IDENTIFIED": "Identified",
    "RESEARCHING": "Researching",
    "QUALIFIED": "Qualified",
    "NOT_A_FIT": "Not a fit",
    "CONTACTING": "Contacting",
    "IN_CONVERSATION": "In conversation",
    "PARTNER": "Partner",
    "CLIENT": "Client",
}

RESEARCH_STATUS = {
    "NOT_STARTED": "Not started",
    "L1": "Quick research done",
    "L2": "Qualification research done",
    "FAILED": "Research failed",
}

ORG_TYPES = [
    "Japanese company in India", "Indian company with Japan links", "Manufacturer",
    "Automotive", "University", "College", "Japanese language school (Japan)",
    "Vocational school (Japan)", "School", "Training institute", "Study abroad consultancy",
    "Recruitment agency", "Employer", "Industry association", "Government body", "Other",
]

PILLAR = {"LEARN": "Learn", "STUDY": "Study", "WORK": "Work", "MULTI": "Multiple pillars",
          "OTHER": "Other strategic"}

OPP_STAGE = {
    "IDENTIFIED": "Identified",
    "RESEARCHING": "Researching",
    "QUALIFIED": "Qualified",
    "IN_DISCUSSION": "In discussion",
    "PROPOSAL": "Proposal",
    "WON": "Won",
    "LOST": "Lost",
    "ON_HOLD": "On hold",
}

TASK_STATUS = {"OPEN": "Open", "DONE": "Done"}
TASK_PRIORITY = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}

INTERACTION_KIND = {
    "EMAIL": "Email", "CALL": "Call", "MEETING": "Meeting", "INTRODUCTION": "Introduction",
    "REFERRAL": "Referral", "EVENT": "Event", "NOTE": "Note", "OTHER": "Other",
}

EVIDENCE_LABEL = {
    "FACT": "Verified fact",
    "INFERENCE": "Reasonable inference",
    "UNKNOWN": "Unknown",
}

VERIFICATION = {
    "UNVERIFIED": "Not checked", "VERIFIED": "Verified", "RISKY": "Risky (catch-all)",
    "INVALID": "Invalid", "GUESS": "Guess, not checked",
}

MAX_PRIMARY_CONTACTS = 2


def check(value: str, allowed, field: str) -> str:
    """Return the value when allowed, else raise ValueError naming the field."""
    if value not in allowed:
        raise ValueError(f"{field}: {value!r} is not one of {', '.join(map(str, allowed))}")
    return value
