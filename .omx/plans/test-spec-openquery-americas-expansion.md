# Test Spec — OpenQuery Americas Expansion

## Metadata
- Date: 2026-04-04
- Linked PRD: `.omx/plans/prd-openquery-americas-expansion.md`

## Test Strategy
Use two verification lanes:
1. **Fast regression lane** (required for every change): deterministic and CI-friendly.
2. **Live accountability lane** (required for milestone checkpoints): measures real source health and prioritization.

## Test Targets and Evidence

### A) Inventory and catalog correctness
- File under test: `src/openquery/source_inventory.py`
- Existing tests: `tests/test_source_inventory.py`

Checks:
1. Inventory scope is `americas`.
2. Inventory statuses include `implemented`, `blocked`, `excluded`, `queued`.
3. Snapshot names match builder names.
4. Snapshot names all exist in registry.

Command:
```bash
uv run pytest tests/test_source_inventory.py -q
```

### B) Multi-country source listing (CLI/API)
- Files: `tests/test_cli.py`, `tests/test_api_extended.py`, `tests/test_sources_registry.py`

Checks:
1. Remove/update outdated wording/assumptions (“all 13 sources”, country==CO).
2. Ensure assertions are compatible with Americas multi-country registry.
3. Ensure `/api/v1/sources` responses preserve required fields and valid countries.

Command:
```bash
uv run pytest tests/test_cli.py tests/test_api_extended.py tests/test_sources_registry.py -q
```

### C) General regression safety
Command:
```bash
uv run ruff check src/ tests/
uv run pytest --tb=short -q
```

Pass criteria:
- Ruff exits 0.
- Pytest exits 0.
- No new failing tests introduced.

### D) Live accountability (milestone)
Command:
```bash
uv run python tests/e2e/run_real_queries.py
```

Checks:
1. `docs/test_results.md` and/or `docs/test_results.json` regenerate successfully.
2. Failure categories and top failing sources are visible for prioritization.
3. Accountability coverage remains complete for tracked sources.

## Acceptance Gates

### Gate 1 — Planning gate complete
- `.omx/plans/prd-openquery-americas-expansion.md` exists.
- `.omx/plans/test-spec-openquery-americas-expansion.md` exists.

### Gate 2 — Regression truthfulness
- Legacy narrow assumptions updated in targeted tests.
- Fast regression command set passes.

### Gate 3 — Inventory accountability
- Inventory snapshot and registry consistency tests pass.
- Status vocabulary remains valid.

### Gate 4 — Milestone live evidence
- Live run executes and produces refreshed report artifacts.
- Recovery backlog can be derived from report.

## Non-goal enforcement checks
Reject work items that require:
- paid or unofficial sources
- human-login-only flows
- mobile-app-only pipelines
- bulk dataset mirroring as primary interface
- advanced biometrics

## Reporting format for each execution slice
1. Scope changed (files + objective).
2. Commands executed.
3. Command outputs summary (pass/fail).
4. Risks or regressions found.
5. Next slice recommendation.
