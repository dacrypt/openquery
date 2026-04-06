"""Deterministic sync checks for docs-facing inventory counts and contracts."""

from __future__ import annotations

from pathlib import Path

from openquery.source_inventory import build_americas_inventory
from openquery.sources import list_sources


def test_sources_guide_count_matches_inventory_snapshot():
    inventory = build_americas_inventory()
    docs_text = Path("docs/sources.md").read_text()

    expected = (
        f"It currently tracks **{len(inventory['sources'])}** Americas runtime connectors\n"
        f"across **{len(inventory['countries'])}** countries, with explicit rollout statuses "
        "(`implemented`, `broken`, `blocked`, `excluded`, `queued`)."
    )
    assert expected in docs_text


def test_sources_guide_distinguishes_inventory_from_live_report():
    docs_text = Path("docs/sources.md").read_text()

    assert "docs/americas-source-inventory.json" in docs_text
    assert "docs/test_results.md" in docs_text
    assert "not\nthe source of truth for inventory counts" in docs_text


def test_readme_runtime_count_matches_registry():
    runtime_sources = list_sources()
    runtime_country_count = len({source.meta().country for source in runtime_sources})
    readme = Path("README.md").read_text()

    expected = (
        f"## Built-in Sources — {len(runtime_sources)} sources across "
        f"{runtime_country_count} country and region namespaces"
    )
    assert expected in readme


def test_readme_points_to_inventory_source_of_truth():
    readme = Path("README.md").read_text()

    assert "docs/americas-source-inventory.json" in readme
    assert "INTL" in readme
    assert "defers a new typecheck gate until a later wave" in readme


def test_runtime_connector_count_is_distinct_from_americas_inventory_scope():
    runtime_sources = list_sources()
    inventory = build_americas_inventory()

    assert len(runtime_sources) > len(inventory["sources"])
    assert any(source.meta().country == "INTL" for source in runtime_sources)


def test_wave1_adr_records_typecheck_deferral_and_sync_contract():
    adr_text = Path(".omx/plans/adr-openquery-americas-wave1.md").read_text()

    assert "typecheck gating is deferred" in adr_text
    assert "docs/americas-source-inventory.json" in adr_text
