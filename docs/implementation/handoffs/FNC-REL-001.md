---
task_id: FNC-REL-001
status: REVIEW_PENDING
base_sha: d756b2b82c52d0a6de719e29193cb4eac726dff2
reservation_sha: ced7584
implementation_shas: [50d755f, 85ecd4c, bb89829]
tested_head_sha: bb89829ebb6e8e6aaff5a66e1192ed1d1347bd87
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA, Architecture]
---

# Handoff FNC-REL-001 — candidato reproducible y baseline operativo

## Resultado

Fincilia puede construir sin publicar las imágenes de API, worker y web y
producir un bundle portable ligado al commit completo, la cabeza de migraciones,
los blobs de fuente, los IDs locales de imagen y tres inventarios SPDX 2.3 de
dependencias. El bundle falla cerrado ante alteración, omisión, archivo extra,
ruta ambigua, imagen flotante, claims de aprobación o evidencia inválida.

La API y el worker emiten JSON estructurado mediante una allowlist. API propaga
un `X-Request-ID` canónico y registra método, plantilla de ruta, estado y
duración; worker liga el evento al `run_id`. Mensajes libres, cuerpos, query,
cookies, tokens, nombres de archivo y contenido financiero no entran al evento.
Las sondas exponen únicamente `release_id` y el SHA de build, nunca secretos.

El workflow es manual y construye, prueba, hace smoke y preserva evidencia, pero
no hace push, firma, promoción ni despliegue. El manifiesto conserva
`approved`, `published`, `signed`, `provenance_verified` y
`production_authorized` en `false` por construcción.

## Defecto adversarial corregido

El primer bundle (`85ecd4c`) pasó dentro del runner Linux, pero su verificación
desde el checkout Windows del mismo SHA falló. Git consideraba limpio el árbol,
aunque numerosos ficheros estaban materializados con CRLF y el runner con LF.
El generador leía el worktree y confundía el filtro local con código distinto.

`bb89829` calcula identidad de fuente y locks sobre los blobs Git de `HEAD` y
mantiene el chequeo de árbol limpio. Una prueba materializa CRLF bajo
`core.autocrlf`, refresca el índice y exige bundles idénticos. El bundle Linux
definitivo verificó íntegramente y contra la fuente desde Windows/WSL:

```text
{"ok": true, "revision": "bb89829ebb6e8e6aaff5a66e1192ed1d1347bd87", "schema_head": "V0038", "state": "candidate"}
{"ok": true, "revision": "bb89829ebb6e8e6aaff5a66e1192ed1d1347bd87", "schema_head": "V0038", "state": "candidate"}
```

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `tools.release_candidate.test_release_candidate` | 19/19 OK |
| `packages.platform.python.tests.test_observability` | 6/6 OK |
| API dentro de imagen reconstruida | 156/156 OK |
| Worker contra PostgreSQL/MinIO | 20/20 OK |
| Runtime config / Compose / compile | OK |
| Quality gate sobre índice | OK, 0 findings |
| Release candidate workflow | `33189803442`, success, 1m16s |
| Artefacto preservado | `fincilia-release-bb89829ebb6e8e6aaff5a66e1192ed1d1347bd87`, 109094 bytes |
| Verificación bundle Linux desde Windows/WSL | OK, bundle y fuente |
| CI general del SHA definitivo | `33189792888`, success, 11m55s el carril integral |

Workflow y evidencia: `https://github.com/Nipko/fincilia-platfrom/actions/runs/33189803442`.
CI general: `https://github.com/Nipko/fincilia-platfrom/actions/runs/33189792888`.

El escáner histórico `tools.supply_chain.cli validate --gate S1-READY` agotó
120 segundos en WSL/NTFS sin salida; no se rebajó su política. Su ejecución en
Linux nativo queda cubierta por CI general y el incidente se conserva como
riesgo de rendimiento local, no como evidencia de cadena de suministro.

## Rollout y rollback

El rollout actual consiste sólo en usar el workflow manual para candidatos
sintéticos y revisar el bundle descargado. Retirarlo o descartar el bundle
revierte el cambio; no existe migración ni estado productivo. El middleware y
los metadatos son expand-only. Revertir `85ecd4c` y `bb89829` retira logging y
verificación; `50d755f` retira el generador.

## Bloqueos que permanecen

- Security, QA y Architecture no han realizado revisión independiente.
- No hay registry seleccionado, raíz de firma, attestation verificable, KMS o
  proveedor de secretos.
- A-02, S-01/TM-005, retención/borrado y restore siguen abiertos.
- No hay IdP productivo, MFA/step-up ni autorización DRG-00/DRG-01.
- El bundle demuestra identidad e inventario; no demuestra autoría, seguridad
  de dependencias ni equivalencia fuente→imagen.

Ningún gate cambia. Las rutas se liberan al integrar este handoff y el siguiente
bloque debe abordar readiness de datos reales con fixtures sintéticos hasta que
Legal, Security y Product firmen el gate correspondiente.
