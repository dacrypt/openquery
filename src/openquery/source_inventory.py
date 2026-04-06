"""Helpers for tracking America-first source inventory."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from openquery.sources import list_sources
from openquery.sources.base import SourceMeta

AMERICAS_COUNTRY_CODES = {
    "AR",
    "BO",
    "BR",
    "CL",
    "CO",
    "CR",
    "DO",
    "EC",
    "GT",
    "HN",
    "MX",
    "PA",
    "PE",
    "PY",
    "SV",
    "US",
    "UY",
}
ALLOWED_STATUSES = {"implemented", "broken", "blocked", "excluded", "discovered", "queued"}
ALLOWED_SOURCE_TYPES = {"api", "browser", "dataset", "hybrid"}
ALLOWED_IMPORTANCE_TIERS = {"critical", "high", "medium", "long_tail"}
LIVE_REPORT_PATH = Path("docs/test_results.md")


class SourceInventoryEntry(TypedDict):
    id: str
    name: str
    country: str
    region_phase: str
    official_name: str
    display_name: str
    official_url: str
    url: str
    requires_browser: bool
    requires_captcha: bool
    supported_inputs: list[str]
    identifier_classes: list[str]
    identifier_categories: list[str]
    runtime_status: str
    status: str
    source_type: str
    officiality: str
    implemented_source_name: str | None
    blocker_reason: str | None
    importance_score: int
    importance_tier: str
    last_reviewed_at: str
    evidence_note: str
    diagnostics: NotRequired[dict[str, str]]


def build_americas_inventory() -> dict[str, object]:
    """Build a machine-readable snapshot of the America-first inventory."""
    live_reviewed_at, live_statuses = _read_live_statuses()
    entries: list[SourceInventoryEntry] = []

    for source in sorted(list_sources(), key=lambda src: src.meta().name):
        meta = source.meta()
        if meta.country not in AMERICAS_COUNTRY_CODES:
            continue

        runtime_status, blocker_reason, evidence_note = _runtime_status_for_source(
            meta.name, live_statuses
        )
        identifier_classes = _classify_identifier_classes(meta)
        importance_score = _score_importance(meta, identifier_classes, runtime_status)
        importance_tier = _importance_tier(importance_score)
        source_type = _classify_source_type(meta)

        entry: SourceInventoryEntry = {
            "id": meta.name,
            "name": meta.name,
            "country": meta.country,
            "region_phase": "americas",
            "official_name": meta.display_name,
            "display_name": meta.display_name,
            "official_url": meta.url,
            "url": meta.url,
            "requires_browser": meta.requires_browser,
            "requires_captcha": meta.requires_captcha,
            "supported_inputs": [doc.value for doc in meta.supported_inputs],
            "identifier_classes": identifier_classes,
            "identifier_categories": identifier_classes,
            "runtime_status": runtime_status,
            "status": runtime_status,
            "source_type": source_type,
            "officiality": "official",
            "implemented_source_name": meta.name,
            "blocker_reason": blocker_reason,
            "importance_score": importance_score,
            "importance_tier": importance_tier,
            "last_reviewed_at": live_reviewed_at,
            "evidence_note": evidence_note,
        }
        entries.append(entry)

    countries = Counter(entry["country"] for entry in entries)
    statuses = Counter(entry["runtime_status"] for entry in entries)

    return {
        "scope": "americas",
        "last_reviewed_at": live_reviewed_at,
        "status_source": str(LIVE_REPORT_PATH),
        "statuses": sorted(ALLOWED_STATUSES),
        "source_types": sorted(ALLOWED_SOURCE_TYPES),
        "importance_tiers": sorted(ALLOWED_IMPORTANCE_TIERS),
        "countries": dict(sorted(countries.items())),
        "status_counts": dict(sorted(statuses.items())),
        "sources": entries,
    }


def _classify_identifier_classes(meta: SourceMeta) -> list[str]:
    inputs = {doc.value for doc in meta.supported_inputs}
    categories: list[str] = []

    if {"cedula", "pasaporte", "ssn"} & inputs:
        categories.append("person")
    if {"nit"} & inputs:
        categories.extend(["company", "fiscal"])
    if {"placa", "vin"} & inputs:
        categories.append("vehicle")
    if "custom" in inputs:
        categories.append("custom")

    if not categories:
        categories.append("mixed")

    return sorted(set(categories))


def _classify_source_type(meta: SourceMeta) -> str:
    url = meta.url.lower()
    if meta.requires_browser:
        return "browser"
    if any(token in url for token in ("datos.", "/resource/", ".json", "/api/")):
        return "dataset"
    return "api"


def _score_importance(
    meta: SourceMeta,
    identifier_classes: list[str],
    runtime_status: str,
) -> int:
    reach = 30 if meta.country in {"BR", "CO", "MX", "US", "AR", "CL", "PE"} else 24
    typed_classes = {"person", "company", "vehicle", "fiscal"} & set(identifier_classes)
    utility = min(25, len(typed_classes) * 10)
    demand = 20 if typed_classes else 10
    maintainability = 15 if runtime_status in {"implemented", "broken"} else 10
    reliability = 10 if runtime_status == "broken" else 6 if runtime_status == "implemented" else 4
    return min(100, reach + utility + demand + maintainability + reliability)


def _importance_tier(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 60:
        return "medium"
    return "long_tail"


def _read_live_statuses() -> tuple[str, dict[str, tuple[str, str | None, str]]]:
    if not LIVE_REPORT_PATH.exists():
        return datetime.now(UTC).date().isoformat(), {}

    reviewed_at = datetime.now(UTC).date().isoformat()
    statuses: dict[str, tuple[str, str | None, str]] = {}

    for raw_line in LIVE_REPORT_PATH.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("> Last full run:"):
            reviewed_at = line.split("**", 2)[1].split()[0]
            continue
        if not line.startswith("| `"):
            continue

        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 5:
            continue

        source_name = parts[0].strip("`")
        status_col = parts[1]
        details = parts[4]

        if status_col.startswith("✅"):
            statuses[source_name] = ("implemented", None, "Live accountability report shows OK")
        elif status_col.startswith("❌"):
            statuses[source_name] = (
                "broken",
                None,
                f"Live accountability report failure: {details}",
            )
        elif status_col.startswith("⏭"):
            status, blocker_reason = _map_skip_detail(details)
            statuses[source_name] = (
                status,
                blocker_reason,
                f"Live accountability report skip: {details}",
            )

    return reviewed_at, statuses


def _map_skip_detail(details: str) -> tuple[str, str | None]:
    if details.startswith("API_REMOVED"):
        return "excluded", details
    return "blocked", details or "Skipped in live accountability report"


def _runtime_status_for_source(
    source_name: str,
    live_statuses: dict[str, tuple[str, str | None, str]],
) -> tuple[str, str | None, str]:
    if source_name in live_statuses:
        return live_statuses[source_name]
    return "queued", None, "Registered runtime connector pending live accountability coverage"
