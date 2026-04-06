# Test Spec — OpenQuery Americas Official Sources

## Scope
This test spec covers the first execution program for America-first official-source completeness infrastructure, grounded in the **existing** autodiscovery and inventory surfaces.

## Test Objectives
1. Prove the existing source registry autodiscovery remains scalable and no longer hides import failures silently.
2. Prove the existing America inventory contract can be extended in place without conflating backlog entries with implemented runtime connectors.
3. Prove the mandatory wave-1 surfaces (**CLI + docs**) stay trustworthy after registry/inventory changes.
4. Prove docs/count synchronization no longer drifts silently.
5. Keep default CI stable while preserving a separate live accountability lane.
6. Prove the first Ralph wave stays bounded to autodiscovery hardening, inventory extension, and verification/doc sync before net-new source waves begin.

## Required Verification Commands
- `uv run ruff check src/ tests/`
- `uv run pytest --tb=short -q`
- `uv run pytest tests/test_source_inventory.py tests/test_sources_registry.py tests/test_cli.py tests/test_api_extended.py -q`
- `docker build -t openquery:test .`
- periodic/non-blocking accountability run: `uv run python tests/e2e/run_real_queries.py`

## Test Matrix

Note: the America inventory contract applies only to Americas-country sources. Non-Americas runtime connectors are outside this inventory scope for wave 1.

### A. Existing autodiscovery hardening
- Registry loads a non-empty source set in a synced environment.
- `pkgutil.walk_packages` discovery still finds multi-country sources.
- Unknown source lookup still raises a helpful error.
- Import failures are retained in a structured diagnostics surface rather than silently collapsing.
- Duplicate source names fail fast deterministically.
- Tests can assert against the diagnostics surface even if no new CLI command is added.

Suggested files:
- `tests/test_sources_registry.py`
- `tests/test_cli.py`
- `tests/test_api.py`

### B. Existing inventory extension
- Inventory schema validates required fields, enum values, and implemented/backlog linkage rules.
- Every implemented **Americas** source in registry has inventory metadata (or an intentional exclusion rule).
- Inventory entries that are not yet implemented never appear as callable runtime sources.
- Existing non-Americas runtime connectors (for example `INTL`) are explicitly outside the America inventory contract unless a separate global inventory contract is added later.
- Every inventory record referencing an implemented source resolves to a real source.
- Derived counts are deterministic.
- Published snapshot remains compatible with docs consumers after schema extension.

Suggested files:
- `tests/test_source_inventory.py`
- new targeted sync tests under `tests/`
- `docs/adding-sources.md` consumer expectations

### C. Mandatory wave-1 public surfaces
- `openquery sources` still lists available implemented sources.
- If metadata/status fields are added, CLI output remains parseable and documented.
- `README.md` and `docs/sources.md` counts/status summaries are derived from the same validated inventory snapshot.
- `/api/v1/sources` remains stable if touched, but API extension is optional rather than required for wave 1.

Suggested files:
- `tests/test_cli.py`
- `tests/test_api.py`
- `tests/test_api_extended.py` (only if API surface changes)
- `tests/test_dashboard.py` (only if dashboard/API surface changes)

### D. Importance rubric / completeness logic
- Inventory scoring follows the documented importance rubric.
- At least one fixture covers each tier boundary (`critical`, `high`, `medium`, `long_tail`).
- Completeness logic only treats `importance_score >= 60` as in-scope for America-first closure.
- `critical` and `high` entries cannot remain unclassified in completed snapshots.

### E. Verification-lane hardening on current stale assumptions
- Legacy assertions that expect `country == "CO"` or tiny source counts are updated to current multi-country reality.
- `tests/test_api_extended.py::test_all_sources_have_country` is corrected.
- `tests/test_new_sources.py`, `tests/test_sources_registry.py`, and `tests/test_source_inventory.py` reflect the actual current surfaces.
- Contributor docs, including `docs/adding-sources.md`, align with the actual inventory + verification workflow.

Suggested files:
- `tests/test_api_extended.py`
- `tests/test_new_sources.py`
- `tests/test_sources_registry.py`
- `tests/test_source_inventory.py`
- `CONTRIBUTING.md`
- `.github/workflows/ci.yml`

### F. Wave-execution contract for new/repaired sources
For each added or repaired source after wave 1:
- meta() is correct (country, inputs, browser/captcha flags)
- result model roundtrips cleanly
- query validation errors are explicit
- registry presence is asserted
- inventory status is updated in the same wave
- docs are updated in the same wave
- optional live test path exists when feasible

## Acceptance Gates
A change set in this program is not complete until:
1. All touched unit/regression tests pass locally.
2. Full `uv run pytest --tb=short -q` passes.
3. Full `uv run ruff check src/ tests/` passes.
4. Docker build passes.
5. Inventory schema/linkage/count-sync checks pass.
6. Deterministic count-sync enforcement proves which files derive counts from inventory versus live test reporting.
7. Architect/verifier review confirms registry, inventory, docs, and verification claims match the actual repo.
8. First-wave scope remains bounded to autodiscovery + inventory + verification/doc sync unless explicitly expanded.
9. CLI + docs wave-1 surfaces are proven trustworthy before optional API expansion.
10. Typecheck deferral is explicitly documented as a completed ADR/docs outcome for wave 1.

## Known Risks to Watch During Testing
- optional dependencies causing false-negative discovery failures
- source imports with side effects
- stale docs claiming outdated counts
- live-site instability being mistaken for deterministic regressions
- contributor workflow drift between docs and code
- schema extension breaking existing inventory consumers
