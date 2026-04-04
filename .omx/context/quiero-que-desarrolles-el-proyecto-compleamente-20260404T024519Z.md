# Context Snapshot

- **Task statement:** El usuario quiere que desarrolle el proyecto completamente.
- **Desired outcome:** Convertir una petición amplia en una especificación ejecutable antes de planificar o implementar.
- **Stated solution:** `$deep-interview "quiero que desarrolles el proyecto compleamente"`
- **Probable intent hypothesis:** Quiere llevar OpenQuery a un estado percibido como “terminado” o mucho más completo, pero aún no definió qué significa “completamente” en términos de alcance, prioridad, calidad, ni límites.

## Known facts / evidence
- Repositorio brownfield existente en Python: `openquery`.
- `README.md` describe un CLI + REST API para consultar fuentes públicas y scraping automatizado.
- `pyproject.toml` indica paquete Python 3.12+, CLI `openquery`, FastAPI opcional y pruebas con pytest.
- Estructura principal detectada: `src/openquery/app.py`, `src/openquery/commands/*`, `src/openquery/core/*`, `src/openquery/server/*`, `src/openquery/sources/*`, `tests/*`, `docs/*`.
- `src/openquery/sources/` ya contiene múltiples conectores por país, incluyendo una gran superficie en `co/`.
- `omx explore` no estuvo disponible porque falta `cargo`; se hizo inspección local directa como fallback.

## Constraints
- Modo activo: `deep-interview`; no implementar todavía.
- Debe hacerse una sola pregunta por ronda.
- Hay que reducir ambigüedad antes de pasar a planificación/ejecución.
- Deben quedar explícitos non-goals y decision boundaries antes del handoff.

## Unknowns / open questions
- Qué significa “completamente” para este usuario.
- Qué problema quiere resolver primero y para quién.
- Qué partes del proyecto son prioritarias: fuentes, API, dashboard, OCR, face verification, docs, CI, producción, etc.
- Qué queda explícitamente fuera de alcance.
- Qué decisiones puede tomar OMX sin confirmación.
- Cómo se medirá éxito y definición de terminado.

## Decision-boundary unknowns
- Si se puede cambiar arquitectura, roadmap, APIs públicas o UX sin aprobación.
- Si se debe priorizar shipping rápido vs robustez/producción.
- Si se puede eliminar, simplificar o posponer features existentes.

## Likely codebase touchpoints
- `README.md`
- `pyproject.toml`
- `src/openquery/app.py`
- `src/openquery/commands/`
- `src/openquery/core/`
- `src/openquery/server/`
- `src/openquery/sources/`
- `tests/`
- `docs/`
