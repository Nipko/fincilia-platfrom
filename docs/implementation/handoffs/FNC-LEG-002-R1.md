---
task: FNC-LEG-002
status: REVIEW_PENDING
base_sha: b837261bbf943e6c3970bc9e992ef710c10be535
implementation_sha: 4e7d05f60947155e5ba54d39714457347c852317
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-LEG-002 R1 — publicación legal y consentimiento versionado

## Resultado

El centro legal público identifica a Parallext LLC como operador de Fincilia y
a Parallext.com como marca de desarrollo. Privacidad, términos, cookies,
seguridad, DPA, subencargados y eliminación publican versión y fecha de
vigencia. La política describe con precisión los datos mínimos recibidos de
Google (`openid email profile`) y excluye Gmail, Drive, publicidad y uso por
modelos de IA.

La alta Google exige dos decisiones separadas: aceptación de términos y
autorización de privacidad. V0056 activa `terms-2026-09-03` y
`privacy-2026-09-03` para altas nuevas, desactiva las versiones anteriores y no
reescribe ninguna aceptación histórica.

## Fuente y alcance

- Razón social, domicilio y teléfono fueron entregados explícitamente por el
  Founder el 2026-09-03.
- Canales publicados: `privacy@fincilia.com`, `legal@fincilia.com`,
  `security@fincilia.com` y `support@fincilia.com`.
- No se incorporaron EIN/NIT, representante legal ni afirmaciones de
  certificación o cumplimiento.
- El entorno y estos términos mantienen `synthetic_only`; este cambio no
  habilita documentos financieros ni operaciones reales.

## Evidencia reproducible

| Comando | Resultado |
| --- | --- |
| `npm run lint` en `apps/web` | exit 0 |
| `npm run typecheck` en `apps/web` | exit 0 |
| `npm run test:unit` en `apps/web` | 51 archivos, 289 pruebas, OK |
| `npm run build` en `apps/web` | 14 páginas estáticas, OK |
| `python -m unittest discover -s /app/tests -t /app/tests` en la imagen API | 188 pruebas, OK |
| `python -m unittest discover -s /app/db/tests -t /app` contra PostgreSQL y MinIO reales | 412 pruebas, OK, 1 omitida |
| aplicación de migraciones | primera ejecución en V0056 `mutated: true`; repetición `mutated: false` |
| `python3 -m tools.work_graph.validate` | 140 tareas, 371 aristas, `ok: true` |
| `python3 -m tools.runtime_config.validate` | 53 variables, `ok: true` |
| `python3 -m tools.web_functional_status.cli` | implementación 88%, `ok: true` |
| `python3 -m tools.quality_gate.cli` sobre el índice | cero hallazgos |
| `git diff --check` | exit 0 |

La primera corrida completa de base tuvo dos fallos y un error de limpieza
porque el worker local consumió trabajos pertenecientes a la suite. Se detuvo
API, web y worker sin borrar volúmenes; los dos casos se repitieron aislados
(incluido el techo de 100.000 movimientos en 36,6 s) y después la suite
completa pasó. No se relajó ninguna aserción.

## Revisión pendiente

La publicación técnica no equivale a asesoría ni aprobación jurídica. Se
requieren revisores nominales e independientes de Privacy/Legal, Security,
Product y Accessibility/QA. Deben confirmar, al menos:

1. ley de Florida y foro del Condado de Orange;
2. límite de responsabilidad: mayor entre pagos de doce meses y USD 100;
3. roles responsable/encargado y mecanismo de transferencias internacionales;
4. calendario L-01 y anexos definitivos del DPA;
5. recepción y capacidad de respuesta de todos los alias publicados;
6. ubicaciones y acuerdos vigentes de AWS, Google, Namecheap y Cloudflare.

El Founder no cuenta como revisor independiente. DRG-00 y DRG-01 no cambian de
estado por este handoff.

## Rollback

El código y los textos pueden volver al commit anterior, pero la migración es
forward-only. Para retirar estas versiones se debe crear una nueva migración
que las marque inactivas y active versiones sustitutas; no se borra ni modifica
la evidencia histórica de aceptación.
