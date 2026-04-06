# ADR — OpenQuery Wave 1 (Americas)

## Decision
Wave 1 extends the existing America inventory in place, hardens autodiscovery diagnostics, and keeps public counts/docs aligned to `docs/americas-source-inventory.json`.

## Drivers
- The repo already has autodiscovery and an America inventory path, so migration would add unnecessary risk.
- America completeness needs a stable source of truth for implemented vs backlog entries.
- Live accountability (`docs/test_results.md`) must remain separate from inventory counts.
- Wave 1 should stay focused; repo-wide typecheck gating is deferred to a later wave.

## Alternatives considered
- Migrate to a new catalog package/data location — rejected for wave 1 because current docs/tests already depend on the existing inventory path.
- Repair sources first and leave inventory/docs mostly alone — rejected because it leaves the America control plane underdefined.

## Consequences
- Existing inventory/docs consumers must stay compatible with the in-place schema extension.
- `INTL` runtime connectors remain callable but outside America completeness counting.
- Typecheck gating is intentionally deferred; the current baseline remains `ruff` + `pytest` + live accountability.

## Follow-ups
1. Keep `docs/sources.md`, `README.md`, and `docs/americas-source-inventory.json` synchronized.
2. Update `docs/adding-sources.md` when adding or repairing America sources.
3. Revisit typecheck gating in a later wave if the verification contract expands.
