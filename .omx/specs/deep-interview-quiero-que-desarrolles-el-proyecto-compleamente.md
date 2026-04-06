# Deep Interview Spec — quiero-que-desarrolles-el-proyecto-compleamente

## Metadata
- **Profile:** standard
- **Rounds:** 9
- **Final ambiguity:** 0.18
- **Threshold:** 0.20
- **Context type:** brownfield
- **Interview transcript:** `.omx/interviews/quiero-que-desarrolles-el-proyecto-compleamente-20260404T031227Z.md`
- **Context snapshot:** `.omx/context/quiero-que-desarrolles-el-proyecto-compleamente-20260404T024519Z.md`

## Clarity breakdown
| Dimension | Score |
|---|---:|
| Intent | 0.75 |
| Outcome | 0.85 |
| Scope | 0.90 |
| Constraints | 0.65 |
| Success | 0.80 |
| Context | 0.70 |

Readiness gates:
- **Non-goals:** explicit
- **Decision Boundaries:** explicit
- **Pressure pass:** complete

## Intent
Construir **OpenQuery** como un proyecto **OSS de referencia/global** para consultas oficiales por identificadores estructurados.

## Desired Outcome
Desarrollar el proyecto para cubrir consultas oficiales basadas en:
- identificación personal
- identificación de persona jurídica
- identificadores de vehículo (placa, matrícula, serial/VIN y equivalentes)
- documentos o identificadores fiscales

La visión es de **exhaustividad máxima**, pero ejecutada por fases.

## In-Scope
### Fase actual
- **América** completa como primera región objetivo.
- Descubrimiento en internet de fuentes oficiales relevantes, incluso si hoy no existen en el repo.
- Priorizar y desarrollar conectores/fuentes oficiales para personas, empresas, vehículos y fiscal.
- Mantener CLI/API como superficies de acceso del proyecto.
- Evaluar y desarrollar fuentes oficiales “importantes” hasta no dejar huecos relevantes sin trabajar dentro de América.

### Fases futuras
- Expandir a otros continentes después de la fase América.

## Out-of-Scope / Non-goals
Quedan explícitamente fuera, aunque existan en América:
- fuentes pagas
- fuentes no oficiales
- flujos con login humano obligatorio
- scraping que dependa de apps móviles
- datasets masivos para descargar como objetivo principal
- validaciones biométricas avanzadas

## Decision Boundaries
OMX/agent puede decidir sin volver a consultar al usuario:
- qué países priorizar primero dentro de América
- qué fuentes oficiales priorizar primero
- cómo ordenar el roadmap
- qué secuencia seguir para completar cobertura

Siempre que respete el alcance y non-goals anteriores.

## Constraints
- Proyecto brownfield existente en Python con CLI y REST API.
- Debe mantenerse el carácter OSS y de referencia.
- El proyecto no se considera “cerrado” globalmente; avanza por regiones/fases.
- El criterio de exhaustividad debe operar sobre **fuentes oficiales importantes**, no sobre cualquier URL marginal sin valor práctico.

## Testable acceptance criteria
La fase América se considera suficientemente desarrollada cuando:
1. Existe un inventario sistemático de fuentes oficiales relevantes en América para personas, empresas, vehículos y fiscal.
2. Las fuentes oficiales importantes detectadas han sido clasificadas al menos como: desarrolladas, bloqueadas justificadamente, descartadas por non-goals, o pendientes con razón explícita.
3. No quedan fuentes oficiales importantes sin evaluar ni sin plan de desarrollo.
4. El roadmap regional está explícito y permite continuar luego con otros continentes.
5. La implementación prioriza fuentes operativas y útiles antes que exhaustividad cosmética.

## Assumptions exposed + resolutions
- **Supuesto inicial:** “completo” significaba cubrirlo todo sin frontera operativa.
- **Resolución:** redefinido como **exhaustividad máxima por fases**: América primero, luego otros continentes.

- **Supuesto:** cualquier fuente oficial podría entrar.
- **Resolución:** se limitó por non-goals (sin pagas, no oficiales, login humano, móviles, datasets masivos, biometría avanzada).

## Pressure-pass findings
Se revisitó la idea de completitud total y se tensionó el supuesto de cierre. El usuario aceptó una reformulación operativa: **América primero; otros continentes después**. Esto convirtió una ambición infinita en una meta planificable por etapas.

## Brownfield evidence vs inference
### Evidence
- `README.md` describe OpenQuery como CLI + REST API para consultas de fuentes públicas.
- `pyproject.toml` confirma paquete Python, comando `openquery`, y stack FastAPI opcional.
- `src/openquery/sources/` ya contiene muchos conectores por país.
- Se verificaron ejemplos oficiales actuales externos como DIAN/RUT, Registraduría, CNPJ Brasil y REPUVE.

### Inference
- “Fuentes oficiales importantes” requerirá una metodología de priorización en planificación; no quedó listado exhaustivo todavía.
- La noción de “desarrollada” aún necesita convertirse en backlog, PRD y test-spec antes de implementación.

## Technical context findings
- Lenguaje principal: Python 3.12+
- Superficies actuales: CLI y API REST
- Arquitectura visible: `commands/`, `core/`, `server/`, `sources/`, `tests/`
- Área de expansión principal: `src/openquery/sources/`

## Source notes used during clarification
- DIAN / RUT (Colombia): https://www.dian.gov.co/impuestos/RUT/Paginas/Consultas-RUT.aspx
- Registraduría servicios (Colombia): https://servicios.registraduria.gov.co/
- Consultar CNPJ (Brasil): https://www.gov.br/pt-br/servicos/consultar-cadastro-nacional-de-pessoas-juridicas
- REPUVE ejemplo de portal oficial/enlace estatal (México): https://sesesp.morelos.gob.mx/repuve/

## Recommended execution bridge
### Recommended: `$ralplan`
Invoke with:
```bash
$plan --consensus --direct .omx/specs/deep-interview-quiero-que-desarrolles-el-proyecto-compleamente.md
```

Why recommended:
- Ya hay claridad suficiente para salir del modo entrevista.
- Aún falta traducir “fuentes oficiales importantes” en criterios de priorización, PRD y test-spec.
- El alcance es grande y necesita una fase de consenso/arquitectura antes de ejecutar.

## Other valid handoffs
- `$autopilot .omx/specs/deep-interview-quiero-que-desarrolles-el-proyecto-compleamente.md`
- `$ralph .omx/specs/deep-interview-quiero-que-desarrolles-el-proyecto-compleamente.md`
- `$team .omx/specs/deep-interview-quiero-que-desarrolles-el-proyecto-compleamente.md`
- Refine further
