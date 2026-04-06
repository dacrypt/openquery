"""Tests for the America-first source inventory snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from openquery.source_inventory import (
    ALLOWED_IMPORTANCE_TIERS,
    ALLOWED_SOURCE_TYPES,
    ALLOWED_STATUSES,
    AMERICAS_COUNTRY_CODES,
    build_americas_inventory,
)
from openquery.sources import list_sources


def test_inventory_builder_returns_americas_scope():
    inventory = build_americas_inventory()

    assert inventory["scope"] == "americas"
    assert set(inventory["statuses"]) == ALLOWED_STATUSES
    assert set(inventory["source_types"]) == ALLOWED_SOURCE_TYPES
    assert set(inventory["importance_tiers"]) == ALLOWED_IMPORTANCE_TIERS
    assert inventory["sources"]


def test_inventory_entries_are_americas_and_structured():
    inventory = build_americas_inventory()

    for entry in inventory["sources"]:
        assert entry["country"] in AMERICAS_COUNTRY_CODES
        assert entry["region_phase"] == "americas"
        assert entry["runtime_status"] in ALLOWED_STATUSES
        assert entry["status"] == entry["runtime_status"]
        assert entry["identifier_classes"]
        assert entry["officiality"] == "official"
        assert entry["source_type"] in ALLOWED_SOURCE_TYPES
        assert entry["importance_tier"] in ALLOWED_IMPORTANCE_TIERS
        assert 0 <= entry["importance_score"] <= 100


def test_inventory_contains_multiple_runtime_statuses_from_live_report():
    inventory = build_americas_inventory()
    statuses = {entry["runtime_status"] for entry in inventory["sources"]}

    assert "implemented" in statuses
    assert statuses & {"broken", "blocked", "excluded"}


def test_every_americas_runtime_source_has_inventory_metadata():
    inventory = build_americas_inventory()
    inventory_names = {entry["name"] for entry in inventory["sources"]}

    americas_runtime_names = {
        source.meta().name
        for source in list_sources()
        if source.meta().country in AMERICAS_COUNTRY_CODES
    }

    assert americas_runtime_names <= inventory_names


def test_inventory_snapshot_matches_builder_output():
    snapshot = json.loads(Path("docs/americas-source-inventory.json").read_text())
    built = build_americas_inventory()

    assert snapshot == built


def test_inventory_snapshot_entries_link_to_registry_when_implemented():
    snapshot = json.loads(Path("docs/americas-source-inventory.json").read_text())
    registry_names = {source.meta().name for source in list_sources()}

    for entry in snapshot["sources"]:
        if entry["implemented_source_name"] is not None:
            assert entry["implemented_source_name"] in registry_names
