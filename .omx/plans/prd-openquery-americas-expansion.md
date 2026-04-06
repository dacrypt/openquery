# PRD — OpenQuery Americas Expansion (Ralph planning gate)

## Metadata
- Date: 2026-04-04
- Source requirements artifact: `.omx/specs/deep-interview-quiero-que-desarrolles-el-proyecto-compleamente.md`
- Context snapshot: `.omx/context/quiero-que-desarrolles-el-proyecto-compleamente-20260404T024519Z.md`

## Requirements Summary
Build OpenQuery as an OSS reference for official identifier-based lookups, executing **America-first** and then expanding to other continents.

In-scope identifier families:
- personal identifiers
- legal entity identifiers
- vehicle identifiers (plate/registration/VIN-like)
- fiscal/tax identifiers

Out-of-scope (explicit non-goals):
- paid sources
- unofficial sources
- human-login-only flows
- mobile-app-only flows
- bulk dataset mirroring as primary interface
- advanced biometrics

Decision boundary:
- Agent can choose roadmap, source priority, and sequencing without additional user approvals as long as scope/non-goals are respected.

## Repo-grounded evidence
- Multi-surface runtime exists: CLI in `src/openquery/app.py:9-50`; API/dashboard in `src/openquery/server/app.py:10-45`.
- Registry discovery is already package auto-walk based (not manual import list) in `src/openquery/sources/__init__.py:42-61`.
- Source contract is centralized in `src/openquery/sources/base.py:16-74`.
- Existing Americas inventory machinery exists in `src/openquery/source_inventory.py:11-60` with snapshot `docs/americas-source-inventory.json` and tests `tests/test_source_inventory.py:16-49`.
- Current live quality baseline is 66% success in `docs/test_results.md:3-5` with dominant failures due to HTML changes `docs/test_results.md:28-33`.
- Legacy tests still carry narrow assumptions (e.g., all country==CO) in `tests/test_api_extended.py:57-60` and outdated count wording in `tests/test_cli.py:33`, `tests/test_sources_registry.py:14,48`.

## RALPLAN-DR Summary
### Principles (5)
1. **Official-first correctness**: prioritize official government/entity sources over speculative breadth.
2. **Accountability over vanity counts**: every important source must be accounted for (implemented/blocked/excluded/queued).
3. **Repair-before-growth**: stabilize high-value broken sources before adding large new waves.
4. **Single source-of-truth inventory**: docs/CLI/API/test reporting should derive from registry/inventory, not manual duplicated counts.
5. **Phase-gated expansion**: complete Americas accountability gate before continent expansion.

### Decision Drivers (top 3)
1. Improve real-world reliability (current live success baseline is low for a reference OSS).
2. Prevent drift between implemented sources, docs claims, and test expectations.
3. Scale expansion without losing operability and verification confidence.

### Viable Options
- **Option A — Add new connectors immediately**
  - Pros: fastest apparent growth.
  - Cons: compounds reliability debt and catalog drift.
- **Option B — Inventory + verification + repair first, then expansion waves (chosen)**
  - Pros: improves truthfulness, stability, and sustainable expansion velocity.
  - Cons: slower short-term source-count growth.
- **Option C — Country-by-country deep completion before cross-country scaling**
  - Pros: strong local quality where focused.
  - Cons: too slow for Americas-wide mandate.

## ADR
- **Decision**: Execute Option B: inventory+verification+repair first, then add missing important sources in waves.
- **Drivers**: reliability baseline, drift control, scalable governance.
- **Alternatives considered**: Option A (raw growth first), Option C (country-at-a-time depth first).
- **Why chosen**: best tradeoff between near-term correctness and long-term expansion throughput.
- **Consequences**:
  - Early work emphasizes test/doc/catalog correctness and repair.
  - Source-count growth appears slower initially but with stronger trust.
- **Follow-ups**:
  1. Normalize tests/docs to multi-country reality.
  2. Track every important source status in inventory.
  3. Run recurring live accountability tests and prioritize top failures.

## Execution Scope (America phase)
### Workstream 1 — Inventory/accountability hardening
- Extend inventory status usage (`implemented`, `blocked`, `excluded`, `queued`) into planning/reporting workflow.
- Keep `docs/americas-source-inventory.json` synchronized with registry and status semantics.

### Workstream 2 — Regression truthfulness
- Remove outdated country/count assumptions from CLI/API/registry tests.
- Ensure fast regression reflects multi-country registry reality.

### Workstream 3 — Reliability recovery wave
- Use live-report evidence (`docs/test_results.md`) to prioritize high-impact broken sources.
- Focus on failures caused by HTML drift/CAPTCHA instability before adding large new volume.

### Workstream 4 — Expansion waves
- Add missing **important** Americas official sources across person/company/vehicle/fiscal classes.
- Keep each addition accountable in inventory status and tests.

## “Important source” selection rule
A source is “important” when all are true:
1. Official government/entity provenance.
2. Query is identifier-based and within person/company/vehicle/fiscal families.
3. Publicly accessible without violating non-goals.
4. Provides practical user value (high-demand public lookup or high-governance utility).

## Testable Acceptance Criteria
1. PRD and test-spec artifacts exist under `.omx/plans/`.
2. No legacy CO-only or “13 sources” assumptions remain in targeted regression tests.
3. `docs/americas-source-inventory.json` remains consistent with registry names (`tests/test_source_inventory.py`).
4. CLI `sources` and API `/api/v1/sources` are validated as multi-country outputs.
5. Live report can be regenerated and used to rank recovery backlog (`uv run python tests/e2e/run_real_queries.py`).
6. Expansion work records each evaluated important source as implemented/blocked/excluded/queued.

## Risks and Mitigations
- **Risk**: scope explosion.
  - Mitigation: strict “important source” rule + status accounting.
- **Risk**: flaky live endpoints reduce CI confidence.
  - Mitigation: keep fast regression separate from live accountability runs.
- **Risk**: docs drift from code reality.
  - Mitigation: derive counts/status from inventory/registry.

## Verification plan (high-level)
- Fast lane:
  - `uv run ruff check src/ tests/`
  - `uv run pytest --tb=short -q`
- Live accountability lane:
  - `uv run python tests/e2e/run_real_queries.py`

## Available-agent-types roster (known usable)
- `explore`, `planner`, `architect`, `critic`, `executor`, `debugger`, `test-engineer`, `verifier`, `writer`, `code-reviewer`, `security-reviewer`, `build-fixer`.

## Follow-up staffing guidance
### Ralph lane (sequential persistent owner)
- `executor` (high): implement small, verifiable slices.
- `test-engineer` (medium): evolve regression and live-accountability tests.
- `architect` (high): design and risk review checkpoints.
- `verifier` (high): completion evidence checks before close.

### Team lane (parallel)
- Lane A (catalog/inventory): `executor` + `writer`.
- Lane B (source repair/additions): `executor` + `debugger`.
- Lane C (verification/CI): `test-engineer` + `build-fixer`.
- Final sign-off: `architect` + `verifier`.

## Launch hints
- Ralph: `$ralph .omx/plans/prd-openquery-americas-expansion.md`
- Team: `$team .omx/plans/prd-openquery-americas-expansion.md`

## Team verification path
1. Team lanes complete with evidence (tests/docs/commands).
2. Unified fast regression green.
3. Inventory consistency checks green.
4. Live-accountability report regenerated.
5. Ralph/verifier performs final acceptance check against this PRD + test-spec.
