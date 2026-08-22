# Encargo principal Claude — FNC-QA-002 + FNC-QA-003

## Misión y continuidad

Actúa como principal dev de este carril durante una ejecución larga. Completa primero
FNC-QA-002 y luego FNC-QA-003; después ejecuta la suite conjunta, corrige regresiones y
entrega ambos handoffs. No te detengas al terminar un archivo ni solicites confirmación
entre etapas. Si una decisión humana está pendiente, represéntala como bloqueo fail-closed
y continúa con todo lo que no dependa de aceptarla.

Estado final permitido: `REVIEW_PENDING`. No declares gates, riesgos, ADR o decisiones
humanas como aceptados.

## Base y coordinación

- Base entregada y verificada por Integration Steward: `c227f1c`.
- No uses Git: no `status`, `diff`, `add`, `commit`, `checkout` ni lectura del índice.
- No edites rutas fuera de las reservadas en las fichas FNC-QA-002/003.
- El árbol es compartido. El Integration Steward trabajará simultáneamente en ADR,
  vocabularios de arquitectura, CI y archivos centrales.
- No edites `.github/workflows/ci.yml`, `CURRENT_PHASE.md`, `TEST_CATALOG.md`, backlog,
  trazabilidad, ADR, contratos de dominio/arquitectura/privacidad ni herramientas existentes.
- Datos exclusivamente sintéticos. Sin internet, conectores, credenciales ni documentos reales.

## Lectura obligatoria completa

1. `AGENTS.md`
2. `CURRENT_PHASE.md`
3. `docs/implementation/tasks/FNC-QA-002.md`
4. `docs/implementation/tasks/FNC-QA-003.md`
5. `docs/implementation/DEFINITION_OF_READY.md`
6. `docs/implementation/DEFINITION_OF_DONE.md`
7. `docs/implementation/OWNERSHIP.md`
8. `docs/testing/TEST_STRATEGY.md`
9. `docs/testing/TEST_CATALOG.md`
10. `docs/testing/SYNTHETIC_DATA_POLICY.md`
11. `docs/testing/SYNTHETIC_CORPUS.md`
12. `docs/implementation/TRACEABILITY.md`
13. `docs/implementation/handoffs/FNC-DAT-002.md`
14. `docs/implementation/handoffs/FNC-PLT-003.md`
15. `docs/implementation/handoffs/FNC-DOM-002.md`
16. `docs/implementation/handoffs/FNC-DOM-003.md`
17. `docs/implementation/handoffs/FNC-DOM-004.md`
18. `docs/implementation/handoffs/FNC-DOM-005.md`
19. `docs/implementation/handoffs/FNC-ARC-004.md`
20. `docs/implementation/handoffs/FNC-ARC-005.md`
21. `docs/implementation/handoffs/FNC-SEC-002.md`
22. `docs/domain/canonical-model.json`
23. `docs/domain/completeness-balances.json`
24. `docs/domain/idempotency-dedupe.json`
25. `docs/domain/lineage-model.json`
26. `docs/architecture/module-boundaries.json`
27. `docs/architecture/dfd-flows.json`
28. `docs/architecture/events-retries.json`
29. `docs/security/threat-model.json`
30. `docs/privacy/privacy-map.json`
31. `tools/synthetic_corpus/**`
32. `tools/quality_gate/**`
33. `.github/workflows/ci.yml` solo lectura

## Etapa A — FNC-QA-002

Amplía el seed, no crees una estrategia narrativa competidora. `test-strategy.json` será
la fuente estructurada autoritativa y debe incluir como mínimo:

- `schema_version`, task, status, data ceiling y human acceptance;
- taxonomía de capas y límites de responsabilidad;
- matriz riesgo → control → tipo de prueba → evidencia → gate;
- política de IDs y descubrimiento dinámico;
- contrato de caso de prueba y contrato de evidencia;
- tipos de oráculo: exacto, invariantes, metamórfico, property, snapshot adjudicado;
- política de datos y fixtures;
- política de mocks/fakes/emuladores y qué no pueden demostrar;
- test pyramid por módulo y frontera;
- CI lanes, dependencias y orden de gates;
- política de flaky/quarantine/skip/retry/waiver/known failure;
- mutation testing y prueba de que el validador “muerde”;
- seguridad: cross-company, pool leakage, replay, worker escape, egress, restore;
- contabilidad: Decimal, moneda, fechas semánticas, balances, completitud y SoD;
- IA: abstención, redacción fail-closed, datasets adjudicados, drift y cero autoridad;
- performance/SLO con estados `pending_human` cuando no exista presupuesto aprobado;
- accesibilidad y usabilidad sin afirmar pruebas humanas inexistentes;
- ownership y revisión independiente;
- required tests descubiertos dinámicamente de contratos ejecutables;
- gates y decisiones pendientes, nunca `accepted` por el agente.

Implementa `tools/quality_strategy/validate.py` y pruebas. Solo biblioteca estándar.
El validador debe cargar el modelo y contratos externos recibidos por rutas explícitas,
comprobar referencias cruzadas y aceptar objetos mutados desde tests.

Pruebas negativas mínimas:

1. Riesgo crítico sin caso/evidencia.
2. ID requerido eliminado o duplicado.
3. Lista fija contradice catálogo/contratos.
4. Unit test usado como prueba de aislamiento PostgreSQL.
5. Mock usado como prueba de integración real.
6. Skip o quarantine de RLS, dinero, completitud, restore o seguridad.
7. Retry que oculta flaky.
8. Waiver sin owner, reviewer, motivo, expiración y gate.
9. Promedio de cobertura que oculta campo/empresa/formato fallido.
10. Float o comparación aproximada para dinero.
11. Snapshot actualizado automáticamente.
12. Expected output aprobado por el mismo actor que cambia el código.
13. Evidencia sin comando, versión, hash, clasificación o resultado.
14. Fixture real/derivado/no inventariado.
15. Test con red o dependencia temporal no controlada.
16. Umbral de performance inventado o marcado aceptado.
17. IA evaluada solo por JSON válido.
18. Modelo sin abstención/redacción/fallback seguro.
19. Accesibilidad declarada por existencia de componentes, sin prueba.
20. Gate marcado `met` o decisión humana cerrada por agente.

## Etapa B — FNC-QA-003

Implementa un golden harness genérico pero deliberadamente pequeño. No construyas parser,
matching ni producto. El registro `golden-harness.json` debe adjudicar inicialmente los
validadores offline ya existentes y la verificación del corpus sintético.

Contrato mínimo de caso:

- case ID estable, suite, owner/reviewer y risk/test IDs;
- runtime y argv exactos, nunca string de shell;
- cwd relativo al repo y allowlist de módulos;
- timeout y límite de salida;
- inputs con path relativo y SHA-256 adjudicado;
- data classification `synthetic_only`;
- expected exit code y oráculo estructurado;
- result-affecting versions exactas;
- estado `active`, nunca skip silencioso;
- evidencia y gate consumidores.

CLI requerida:

```text
python -m tools.golden_harness.cli list
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m tools.golden_harness.cli run --case CASE_ID
```

Reglas de ejecución:

- `subprocess` solo con lista argv, `shell=False`, cwd validado y timeout;
- entorno mínimo/allowlisted, sin heredar secretos ni proxies;
- cero red por contrato y comandos limitados a módulos locales adjudicados;
- no aceptar rutas absolutas, `..`, symlinks fuera del repo ni comandos arbitrarios;
- stdout/stderr acotados; los payloads no se copian al manifiesto;
- comparar salida JSON cuando el caso lo declare; normalizar solo campos explícitos;
- no normalizar diferencias financieras o semánticas;
- manifest de run con registry digest, case digest, input hashes, runtime, resultado y
  output digest; duración puede registrarse pero no entra al digest determinista;
- replay idéntico produce el mismo deterministic result digest;
- actualizar expected requiere un comando/flujo separado de adjudicación, fuera de la
  autoridad automática del runner. No implementes auto-update.

Incluye casos iniciales para los validadores de architecture, canonical, completeness,
connector, DFD, events, idempotency, lineage, privacy y threat model, más `synthetic_corpus
verify`. No metas Docker/WSL en este harness: PLT-001/005 conservan sus jobs de integración.

Pruebas negativas mínimas:

1. Registry/hash/input alterado.
2. Caso duplicado o sin owner/reviewer independiente.
3. Comando string o shell.
4. Ejecutable/módulo no allowlisted.
5. Ruta absoluta, traversal o symlink externo.
6. Fixture no sintético o no inventariado.
7. Timeout ausente/excesivo.
8. Output ilimitado.
9. Expected exit code ausente.
10. Oráculo `always_pass`, regex laxa o normalización financiera.
11. `latest`, `main`, `head`, `stable` o `current` como versión.
12. Caso skipped/quarantined que cuenta como PASS.
13. Diferente output con misma deterministic key.
14. Manifest que incluye secretos, env completo o payload raw.
15. Runner que modifica expected/fixture.
16. Un test fallido que deja exit 0.
17. Selección de case inexistente que queda vacía y exit 0.
18. Red/proxy heredado por el subprocess.

Usa fixtures nuevos únicamente bajo `tests/golden/harness/**`, inequívocamente sintéticos,
pequeños, con manifiesto/hash y dominio reservado cuando aplique. No modifiques los cinco
fixtures existentes de DAT-002.

## Definition of Done conjunta

- Ambos modelos JSON válidos, estrictos y sin claves desconocidas silenciosas.
- Ambos validadores offline y deterministas.
- Al menos 60 pruebas útiles combinadas; prioriza mutaciones reales, no conteo artificial.
- Todos los comandos documentados pasan desde raíz.
- Ejecuta todos los validadores hermanos y la suite Python integrada.
- No ejecutes ni declares quality gate sobre archivos nuevos no indexados; déjalo al Steward.
- Cero `TODO`/`FIXME` anónimo, secretos, correos, NIT, IP pública o datos reales.
- Handoffs separados con base, rutas, conteos, comandos/resultados, hallazgos, riesgos,
  decisiones abiertas, rollback, revisores y pasos exactos para el Integration Steward.
- Si descubres contradicciones fuera de scope, repórtalas con ruta/ID/owner; no las edites.

## Verificación obligatoria

```powershell
python -m tools.quality_strategy.validate
python -m unittest tools.quality_strategy.test_validate -v
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m unittest tools.golden_harness.test_harness -v
python -m tools.architecture_model.validate
python -m tools.canonical_model.validate
python -m tools.completeness_model.validate
python -m tools.connector_model.validate
python -m tools.dfd_model.validate
python -m tools.event_model.validate
python -m tools.idempotency_model.validate
python -m tools.lineage_model.validate
python -m tools.privacy_model.validate
python -m tools.threat_model.validate
python -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic
```

## Handoff

Entrega `FNC-QA-002.md` y `FNC-QA-003.md` por separado. Termina con una sección conjunta
que indique compatibilidad, comandos exactos, total real de pruebas, rutas reservadas que
liberas y los cambios centrales que debe hacer el Integration Steward. No uses Git.
