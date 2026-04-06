# PRD — OpenQuery Americas Official Sources

## Requirements Summary

Build OpenQuery into the OSS reference for official lookup sources in the Americas, focused on identifiers for people, legal entities, vehicles, and fiscal documents, while explicitly excluding paid sources, non-official sources, login-only human flows, app-only flows, bulk dataset downloads as the primary goal, and advanced biometrics.

The work must be executed in a **phase-based** way:
- **Phase 1:** America-first operational completeness
- **Phase 2+:** expand to other continents after America is systematically covered

America is considered sufficiently developed when no **important** official source in scope is left without evaluation, classification, or an explicit development plan.

## Grounded repo facts

- OpenQuery already exposes a unified **CLI** via Typer in `src/openquery/app.py` and package entrypoint `openquery = "openquery.app:main"` in `pyproject.toml`.
- OpenQuery already exposes a **FastAPI API** plus dashboard mount in `src/openquery/server/app.py`.
- Source connectors live in `src/openquery/sources/<country>/` and models in `src/openquery/models/<country>/` as documented in `docs/adding-sources.md`.
- `src/openquery/sources/__init__.py` already uses `pkgutil.walk_packages` + `importlib.import_module` for autodiscovery, but currently swallows `ImportError` and provides no diagnostics for failed modules.
- OpenQuery already has America-first inventory helpers in `src/openquery/source_inventory.py` and a published snapshot in `docs/americas-source-inventory.json`, but today that inventory only captures implemented sources and a narrow status model.
- `docs/sources.md` already points contributors to `docs/americas-source-inventory.json`, so inventory changes must preserve or explicitly migrate that contract.
- The repository currently contains ~140 source modules across 18 country/region directories, but documentation and test artifacts still drift on counts (`README.md`, `docs/sources.md`, `docs/test_results.md`).
- CI currently enforces `ruff`, `pytest`, and Docker build only in `.github/workflows/ci.yml`; there is no typecheck gate.
- Live evidence currently shows **66% success** on real-source runs in `docs/test_results.md`, so reliability repair must be part of the America program.

## Architecture clarifications before execution

### Runtime registry vs coverage backlog (explicit split)
The plan intentionally separates two concerns:
1. **Runtime connector registry** — only implemented Python sources that can be instantiated by CLI/API.
2. **Coverage backlog/inventory** — the broader America-first catalog of important official sources, including implemented, broken/regression, blocked, excluded, and discovered-but-not-yet-implemented targets.

This avoids overloading the runtime registry with backlog entries that do not have a connector yet.

### Chosen extension path (explicit)
Wave 1 will **extend existing infrastructure in place** rather than migrate to a brand-new catalog stack.

Canonical artifacts for wave 1:
- **Runtime discovery code:** `src/openquery/sources/__init__.py`
- **Inventory logic:** `src/openquery/source_inventory.py`
- **Published machine-readable snapshot:** `docs/americas-source-inventory.json`
- **Human-facing docs:** `docs/sources.md` and `README.md`

If a later package-owned data file becomes necessary, it must be introduced as a compatibility-preserving extension, not a silent replacement.

### Inventory schema contract (wave-1 required)
The America inventory must define an explicit schema. Minimum required fields per record:
- `id` — stable slug (`<country>.<source>` for implemented connectors; `catalog.<country>.<slug>` for backlog-only entries)
- `country` — ISO alpha-2 country code
- `region_phase` — `americas`
- `official_name` — authority/system name
- `official_url` — canonical official URL
- `identifier_classes` — subset of `person`, `company`, `vehicle`, `fiscal`, `mixed`, `custom`
- `runtime_status` — one of `implemented`, `broken`, `blocked`, `excluded`, `discovered`, `queued`
- `source_type` — `api`, `browser`, `dataset`, `hybrid`
- `officiality` — `official`
- `implemented_source_name` — runtime connector name when implemented, else `null`
- `blocker_reason` — required when status is `blocked` or `excluded`
- `importance_score` — integer 0-100
- `importance_tier` — `critical`, `high`, `medium`, `long_tail`
- `last_reviewed_at` — ISO date
- `evidence_note` — short provenance note for why the source exists / matters

Validation rules:
- backlog-only entries must never appear as callable runtime sources
- implemented entries must resolve to a real registered source name
- `excluded` entries must cite a non-goal reason
- `blocked` entries must cite an operational blocker reason
- the published docs snapshot must stay compatible with current docs consumers or explicitly update them in the same wave

### Importance rubric (wave-1 required)
A source is considered **important** when `importance_score >= 60`.

Score components (0-100 total):
- **Official reach (0-30):** national/federal > state/provincial > municipal
- **Identifier utility (0-25):** directly supports in-scope person/company/vehicle/fiscal lookups
- **Practical demand (0-20):** common compliance, identity, business, or vehicle lookup need
- **Maintainability fit (0-15):** compatible with project non-goals and reusable patterns
- **Reliability leverage (0-10):** closes a major current gap or repairs a broken high-value existing source

Tier mapping:
- `critical`: 85-100
- `high`: 70-84
- `medium`: 60-69
- `long_tail`: <60

America-first operational completeness for a phase means:
- no `critical`, `high`, or `medium` official source remains unclassified
- no `critical` or `high` source remains without either implementation, explicit blocker, or explicit exclusion

### Explicit non-Americas boundary
For wave 1, the America inventory contract applies only to Americas-country sources. Existing `INTL` runtime connectors remain callable runtime sources but are **out of scope** for America inventory completeness unless a later global inventory contract is introduced.

### Wave-1 mandatory public surface
Wave 1 must ship **CLI + docs** as the mandatory trustworthy surfaces.
- CLI: `openquery sources` remains the implemented-source runtime listing and may expose summary inventory metadata.
- Docs: `README.md` and `docs/sources.md` must publish inventory-derived counts/statuses.
- API exposure is optional in wave 1 and can follow only if low-cost after the CLI/docs contract is green.

### Wave 1 execution cutline (Ralph start)
The first Ralph execution wave is intentionally bounded to:
1. strengthen existing autodiscovery with diagnostics / duplicate detection / import-failure reporting
2. extend the existing America inventory contract in place
3. fix stale tests and count-sync assumptions around the current inventory/registry surfaces
4. update CLI/docs only as needed to make the inventory trustworthy

New source repairs/additions start only after this foundation is green.

## Acceptance Criteria

1. The existing America inventory path (`src/openquery/source_inventory.py` + `docs/americas-source-inventory.json`) is extended to track both implemented and backlog status using the explicit schema contract above.
2. Registry autodiscovery remains in place, but failed imports and duplicate registration problems no longer disappear silently.
3. The repo exposes trustworthy **implemented-source** registry data separately from broader **coverage inventory** metadata through the mandatory wave-1 surfaces: **CLI + docs**.
4. Verification distinguishes stable mocked/unit coverage from live/integration coverage and supports ongoing repair waves.
5. Documentation and automated counts stop drifting: README/docs/published inventory all derive from the same source of truth.
6. Initial execution wave is bounded to existing-registry hardening, existing-inventory extension, verification cleanup, and CLI/docs trustworthiness.

## Implementation Steps

### Step 1 — Harden existing source autodiscovery
**Goal:** keep the current scalable registry model, but make it debuggable and trustworthy.

Primary files:
- `src/openquery/sources/__init__.py`
- `tests/test_sources_registry.py`
- `tests/test_cli.py`
- `tests/test_api.py`
- `tests/test_api_extended.py`

Autodiscovery diagnostics contract (required):
- duplicate source names must **fail fast** with a clear error
- module import failures must be retained in a structured diagnostics surface (for example an internal diagnostics registry/helper) rather than disappearing silently
- tests must be able to assert on those diagnostics
- CLI may optionally expose a summary view, but testable programmatic diagnostics are mandatory even if no user-facing command is added yet

Deliverables:
- Keep `pkgutil.walk_packages` autodiscovery.
- Add structured diagnostics for import failures instead of silent `ImportError` swallowing.
- Detect duplicate source registration collisions and stop on them deterministically.
- Update stale registry/API/CLI tests away from legacy assumptions.

### Step 2 — Extend the existing America inventory in place
**Goal:** turn the current implemented-only inventory into the America program control plane.

Primary files:
- `src/openquery/source_inventory.py`
- `docs/americas-source-inventory.json`
- `tests/test_source_inventory.py`
- `docs/sources.md`
- `docs/adding-sources.md`
- `README.md`

Deliverables:
- Expand the inventory schema to include runtime/backlog separation, importance scoring, and blocker/exclusion metadata.
- Preserve compatibility with current docs consumers, or update all consumers in the same wave.
- Keep the published JSON snapshot as a trustworthy machine-readable artifact for the current rollout.
- Update contributor guidance in `docs/adding-sources.md` so source authors follow the new inventory contract.

### Step 3 — Repair verification baseline around current surfaces
**Goal:** make the existing repo honest and stable enough to scale.

Primary files:
- `.github/workflows/ci.yml`
- `pyproject.toml`
- `CONTRIBUTING.md`
- `docs/test_results.md`
- `tests/test_api_extended.py`
- `tests/test_new_sources.py`
- `tests/test_source_inventory.py`
- `tests/e2e/run_real_queries.py`
- new deterministic sync check under `tests/` and/or a small helper script under `scripts/` if needed

Deliverables:
- Fix stale assertions such as country=`CO`-only assumptions.
- Separate stable/default verification from live accountability where needed.
- Add a deterministic count-sync enforcement path (test or helper-backed test) that defines exactly which counts derive from inventory/docs versus live test reporting.
- **Typecheck branch closure:** for wave 1, explicitly defer adding mypy/pyright and instead record that deferral in docs/ADR; completion is proven by updated documentation/ADR, not by a new typecheck command in this wave.
- Keep `docs/test_results.md` useful without making CI hostage to live-site volatility.

### Step 4 — Classify the America backlog using the explicit rubric
**Goal:** move from vague “important sources” to an explicit backlog.

Primary files:
- `src/openquery/source_inventory.py`
- `docs/americas-source-inventory.json`
- `docs/sources.md`
- `.omx/plans/` supporting notes if needed

Deliverables:
- Classify current Americas sources by person/company/vehicle/fiscal scope.
- Add backlog entries for important official sources not yet implemented.
- Score each backlog item with the rubric and assign a tier.
- Mark blocked/excluded items explicitly.

### Step 5 — Execute repair/addition waves after the foundation is green
**Goal:** iteratively close important gaps.

Primary files (pattern-based):
- `src/openquery/models/<country>/<source>.py`
- `src/openquery/sources/<country>/<source>.py`
- `tests/test_<source>.py` and/or grouped country tests
- `tests/e2e/*`
- `README.md`
- `docs/sources.md`
- `docs/americas-source-inventory.json`

Deliverables:
- Add or repair high-priority official sources by wave.
- Each wave must update inventory status, tests, and docs.
- Prefer browser/API patterns that reuse existing helpers over custom one-offs.

## Risks and Mitigations

- **Risk:** autodiscovery keeps hiding optional-dependency or broken-module imports.  
  **Mitigation:** record import failures explicitly and expose them to tests/maintainers.
- **Risk:** changing the inventory schema breaks current docs/tests consumers.  
  **Mitigation:** extend the existing inventory in place and update `docs/sources.md`, `README.md`, and `tests/test_source_inventory.py` together.
- **Risk:** live-source volatility turns every wave into flaky red CI.  
  **Mitigation:** keep mocked/unit gates fast and stable; treat live-source accountability as a separate lane.
- **Risk:** count drift persists across README/docs/published inventory.  
  **Mitigation:** add a deterministic sync test that declares which files derive counts from the inventory snapshot and which are allowed to differ because they report live execution results.
- **Risk:** infinite scope.  
  **Mitigation:** operational completeness = no important America source left unclassified, and no critical/high source left without implementation, blocker, or exclusion.

## Verification Steps

Minimum per wave:
1. `uv run ruff check src/ tests/`
2. `uv run pytest --tb=short -q`
3. targeted regression for current affected surfaces:  
   `uv run pytest tests/test_source_inventory.py tests/test_sources_registry.py tests/test_cli.py tests/test_api_extended.py -q`
4. if inventory/docs change, run the deterministic count-sync verification that checks inventory-derived counts against `README.md`/`docs/sources.md` and treats `docs/test_results.md` as a live-report artifact with separately validated semantics
5. Docker build remains green: `docker build -t openquery:test .`
6. verify the typecheck decision branch is closed by updated ADR/docs text (wave 1 explicitly defers adding a typecheck gate)
7. periodic live accountability run: `uv run python tests/e2e/run_real_queries.py`

## RALPLAN-DR Summary

### Principles
1. **Extend real infrastructure before inventing replacements.**
2. **Operational completeness beats vague exhaustiveness.**
3. **One trustworthy inventory contract for America-first coverage.**
4. **Stable regression gates separate from volatile live-site accountability.**
5. **Runtime registry and coverage backlog stay explicitly distinct.**

### Decision Drivers
1. The repo already has autodiscovery and an America inventory, so the fastest correct path is to harden and extend them.
2. Current silent import failures, stale tests, and docs drift make the existing scaling path untrustworthy.
3. The America rollout needs a control plane that can classify both implemented and not-yet-implemented official sources.

### Viable Options

#### Option A — Incrementally extend existing autodiscovery + existing inventory
**Pros**
- Aligns with the actual codebase
- Lowest migration risk for docs/tests/contributors
- Fastest path to trustworthy CLI/docs counts and backlog control

**Cons**
- Existing inventory shape may constrain some design choices
- May require compatibility shims while the schema grows

#### Option B — Migrate to a brand-new catalog package/data location
**Pros**
- Clean slate for schema design
- Clearer long-term separation if done carefully

**Cons**
- Higher migration risk for docs/tests/current consumers
- More work before wave-1 user value
- Easy to introduce drift during transition

#### Option C — Repair broken sources first, leave registry/inventory mostly alone
**Pros**
- Faster visible user wins on some sources
- Addresses current credibility pain directly

**Cons**
- Does not solve the control-plane problem for America completeness
- Continues stale tests/docs drift and silent discovery issues

### Recommended Option
**Option A**

## ADR

### Decision
Adopt an **incremental foundation-first America program**: harden existing autodiscovery, extend the existing America inventory in place, clean stale verification/docs assumptions, then execute source repair/addition waves.

### Drivers
- Existing autodiscovery and inventory already solve part of the problem and should be reused.
- Silent import failures and stale assumptions currently undermine trust.
- America-first completeness needs explicit backlog classification, not just implemented-source enumeration.

### Alternatives considered
- **Brand-new catalog migration** — rejected for wave 1 because current docs/tests already depend on the existing inventory path.
- **Repair-only first** — rejected because it leaves the America control plane underdefined.

### Why chosen
This path is the lowest-risk route that matches the actual repo while still building the machinery needed for America-first completeness.

### Consequences
- Wave 1 is still infrastructure-heavy, but it is now grounded in the repo’s real extension points.
- Existing inventory consumers must be updated carefully when the schema grows.
- New source waves start only after discovery + inventory + verification are trustworthy.

### Follow-ups
1. Harden autodiscovery diagnostics in `src/openquery/sources/__init__.py` with a testable diagnostics contract.
2. Extend `src/openquery/source_inventory.py` and `docs/americas-source-inventory.json` in place.
3. Update `docs/adding-sources.md`, `docs/sources.md`, and other docs consumers to the new inventory contract.
4. Add deterministic count-sync enforcement and explicitly document typecheck deferral for wave 1.
5. Start priority source repair/addition waves by rubric tier.

## Available-Agent-Types Roster
- `explorer` — fast codebase fact gathering
- `planner` — plan revisions / sequencing
- `architect` — architecture review / tradeoffs
- `critic` — plan quality gate
- `executor` — implementation lane
- `test-engineer` — verification/test hardening
- `verifier` — completion evidence review
- `writer` — docs/inventory/doc-sync updates

## Follow-up Staffing Guidance

### Ralph path (sequential owner with bounded parallel sidecars)
- **Lane 1:** `executor` (high) — autodiscovery diagnostics + inventory extension
- **Lane 2:** `test-engineer` (medium) — stale tests, count-sync checks, regression harness
- **Lane 3:** `writer` (medium) — README/docs/inventory contract sync
- **Final sign-off:** `architect` then `verifier`

### Team path (parallel)
- **Worker A:** autodiscovery diagnostics + duplicate detection
- **Worker B:** inventory schema extension + snapshot sync
- **Worker C:** stale tests / CI / verification lane
- **Worker D:** docs/public surface updates
- **Leader verification:** team proves targeted lanes green; Ralph/verifier checks integrated repo state before closure

## Launch Hints

### Ralph
```bash
$ralph .omx/plans/prd-openquery-americas-official-sources.md
```

### Team
```bash
$team .omx/plans/prd-openquery-americas-official-sources.md
```

## Team Verification Path
1. Autodiscovery diagnostics tests pass.
2. Inventory schema/linkage/count-sync tests pass.
3. CLI source listing and docs snapshot stay consistent.
4. Full lint + pytest + docker build pass before shutdown.
