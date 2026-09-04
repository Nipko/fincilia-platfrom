---
id: FNC-REL-001
title: Candidato de release reproducible y baseline operativo proveedor-neutral
epic: FNC-EP-PLATFORM
phase: F0
iteration: E1
type: implementation
status: review_pending
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Platform/SRE
implementer: Codex principal dev + Integration Steward
independent_reviewer: Security + QA + Architecture
plan_refs: [18, 26, 29, 32, 36, 54]
adr_refs: [ADR-001, ADR-002, ADR-020, ADR-023]
dependencies: [FNC-CFG-001, FNC-SUP-001, FNC-QA-010, FNC-PLT-009]
gate: DRG-00
gate_effect: none
allowed_data: synthetic_only
security_impact: high
privacy_impact: medium
risk_ids: [TM-005, TM-006]
---

# Resultado esperado

Fincilia puede producir un candidato de release proveedor-neutral con identidad
reproducible, inventario SPDX de dependencias, digests de fuentes y artefactos,
metadatos de build y evidencia de pruebas. La API y el worker emiten
observabilidad estructurada y correlacionable sin registrar payloads, secretos,
query strings ni identificadores financieros.

El resultado prepara la salida a producción, pero no la autoriza: A-02,
DRG-00/01, la raíz de firma, el proveedor de secretos, el IdP productivo y la
revisión independiente continúan bloqueantes.

# Contexto y decisión que habilita

- IMP-017 ratificó ADR-001/002/023, pero declara `production_authorized: false`.
- ADR-020 conserva proveedor y región sin decidir.
- FNC-SUP-001 inventaría pins, pero declara SBOM, firma y procedencia pendientes.
- El plan §§18, 26, 29, 32, 36 y 54 exige release reproducible, observabilidad
  redactada, SBOM, firma y pruebas de seguridad.

# Dentro de alcance

- Contrato y CLI de release candidate fail-closed.
- SPDX JSON determinista para locks Python y npm del producto.
- Manifiesto con commit, estado limpio, schema head, digests, versión de formato,
  clasificación de efecto y referencias de evidencia.
- Verificación offline de un bundle sin confiar en nombres de fichero.
- Middleware de request/correlation ID y logs JSON allowlisted en API.
- Metadatos no secretos de build/release en health endpoints.
- Logging JSON compatible en worker y propagación del identificador de trabajo.
- Workflow manual que construye y verifica sin publicar artefactos productivos.
- Smoke checks de imagen y documentación de rollout/rollback.

# Fuera de alcance

- Habilitar `staging` o `production` en runtime-config/settings.
- Elegir cloud, región, registry, KMS/Vault, IdP o backend de observabilidad.
- Firmar o publicar imágenes, aceptar una raíz de confianza o cerrar TM-005.
- Datos reales, conectores, IA externa, cambios financieros o migraciones.
- Declarar S1-READY, DRG-00, DRG-01 o GA-01 superados.

# Rutas permitidas

- `tools/release_candidate/**`
- `docs/platform/release-candidate.json`
- `docs/platform/RELEASE_CANDIDATE.md`
- `infra/release/**`
- `apps/api/src/fincilia_api/main.py`
- `apps/api/tests/test_api.py`
- `packages/platform/python/fincilia_platform/**`
- `packages/platform/python/tests/**`
- `docs/platform/runtime-config.json`
- `.env.example`
- `infra/local/compose.yaml`
- `workers/document/src/fincilia_worker/main.py`
- `workers/document/tests/**`
- `.github/workflows/release-candidate.yml`
- `.github/workflows/ci.yml`
- `docs/implementation/tasks/FNC-REL-001.md`
- `docs/implementation/handoffs/FNC-REL-001.md`
- registros centrales por Integration Steward.

# Rutas prohibidas

- Migraciones, seed y esquema canónico.
- Autorización, RLS, SoD, semántica financiera y linaje.
- Lockfiles y dependencias nuevas.
- Configuración que permita producción o datos reales.
- Estados humanos, gates y decisiones aún no aceptadas.

# Criterios de aceptación

- **AC-01.** El bundle se genera sólo desde árbol Git limpio y commit completo.
- **AC-02.** Cada lock de producto produce un SPDX determinista; inputs, salidas
  y Dockerfiles quedan ligados por SHA-256. El validador extrae todos los
  orígenes locales de `COPY` y rechaza cualquier origen no cubierto o sintaxis
  que no pueda adjudicar sin ambigüedad.
- **AC-03.** Verificar detecta modificación, omisión, duplicado, ruta ambigua,
  digest inválido, versión flotante y evidencia inexistente.
- **AC-04.** El manifiesto separa `candidate` de `approved`; el agente nunca puede
  generar un estado aprobado ni afirmar firma/procedencia no demostrada.
- **AC-05.** API responde `X-Request-ID`, acepta sólo IDs acotados y registra
  método, plantilla de ruta, estado y duración sin cuerpo/query/auth/cookies.
- **AC-06.** Health expone release/revisión no secreta y conserva sondas sin
  filtrar DSN, claves o topología sensible.
- **AC-07.** Worker usa JSON allowlisted y correlaciona cada trabajo sin registrar
  contenido documental.
- **AC-08.** Workflow manual construye las tres imágenes, genera/verifica el
  bundle y smoke-testea imágenes sin push, firma ni datos reales.
- **AC-09.** Unitarias, integración aplicable, quality gate, catálogo y CI pasan.
- **AC-10.** Rollout, rollback y bloqueos externos/humanos quedan explícitos.

# Casos negativos y de abuso

- Árbol sucio, SHA corto, lock sin hash o Dockerfile no fijado.
- Bundle copiado con un fichero modificado o no declarado.
- `approved`, `signed` o `provenance_verified` introducidos manualmente.
- Request ID con CR/LF, Unicode, longitud excesiva o formato libre.
- Token, cookie, query o body nunca aparecen en logs aun ante error.
- `production`, datos reales o publicación externa permanecen imposibles.

# Plan de pruebas

- Unitarias del generador/verificador y mutaciones de cada regla crítica.
- API TestClient para request ID, logging y health metadata.
- Worker unitario para formatter/contexto de trabajo.
- Build de las tres imágenes y smoke local con configuración sintética.
- Quality gate, work graph, test catalog y CI final.

# Observabilidad y auditoría

Campos allowlisted: timestamp, level, service, event, request_id/job_id, método,
plantilla de ruta, status y duración. No se registran payload, query, cabeceras,
cookie, token, nombres de archivo, referencias bancarias ni texto libre de origen.

# Migración, rollout y rollback

No hay migración. El middleware y metadatos son expand-only. El workflow es sólo
manual y sin publicación. Rollback: retirar el workflow y volver a logging de
texto; ningún dato ni artefacto productivo requiere transformación.

# Evidencia requerida

- Base/head SHA y árbol limpio.
- Bundle reproducible verificado dos veces.
- Pruebas negativas de tamper y redacción.
- Builds/smoke de API, worker y web.
- CI verde y handoff con gaps de firma/procedencia aún abiertos.

# Evidencia obtenida

- Bundle íntegro y fuente verificados desde Windows/WSL contra el candidato
  construido en Linux para `bb89829ebb6e8e6aaff5a66e1192ed1d1347bd87`.
- Workflow manual `33189803442`: build de API, worker y web, ejecución dentro
  de imágenes, smoke web, doble generación determinista y artefacto preservado.
- 19 pruebas del generador/verificador, 6 de observabilidad, 156 de API y 20 de
  worker; quality gate del índice sin hallazgos.
- CI general `33189792888` quedó verde sobre el mismo SHA, incluidos PostgreSQL,
  API, worker, recorrido web Chromium y WCAG 2.2 AA automatizado.

# Handoff al siguiente agente

Security + QA + Architecture deben revisar formato SPDX, claims del manifiesto,
allowlist de observabilidad y workflow. Platform decidirá registry/raíz de firma
sólo después de A-02 y de una decisión humana específica.

# Trazabilidad

- Requisito: REQ-FNC-073-RELEASE-CANDIDATE
- ADR: ADR-001, ADR-002, ADR-020, ADR-023
- Tests: `tools.release_candidate`, API/worker unitarias y smoke de imágenes
- Gate: DRG-00, sin efecto automático
