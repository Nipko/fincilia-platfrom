---
id: FNC-QA-006
alias: FNC-P4.5
title: Aceptación web integral y arranque local coherente
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 774575cfc01529016e9ae189d760993376962ead
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Platform, QA, Security, Accessibility/Product]
---

# Resultado esperado

El entorno local construye y ejecuta una única revisión coherente de API, worker,
web y migrador, verifica el readiness de esquema después del arranque y ofrece
aceptación automatizada del límite multiempresa y de los roles preparador/revisor
en la plataforma web. La tarea no acepta decisiones humanas ni amplía el producto.

# Definition of Ready

- FNC-PLT-008, FNC-WEB-001, FNC-WEB-003 y FNC-CLN-001 están integradas y sus
  artefactos se pueden probar localmente.
- La base exacta está declarada y el árbol parte limpio.
- El Integration Steward reserva las rutas antes de editar.
- Sólo se usan identidades, empresas y documentos sintéticos sembrados localmente.
- S1-READY permanece `not_met`; levantar local no autoriza producción ni piloto.

# Rutas permitidas

- `infra/local/up.sh`
- `infra/local/compose.yaml` — únicamente para nombres de volúmenes de prueba
  parametrizables, conservando los nombres por defecto.
- `tools/local_stack/**`
- `apps/web/tests/e2e/**`
- `apps/web/playwright.config.ts` sólo si la estabilidad E2E lo exige.
- `docs/implementation/tasks/FNC-QA-006.md`
- `docs/implementation/handoffs/FNC-QA-006.md`
- Archivos centrales para registrar y liberar esta tarea, sólo por el Integration
  Steward.

# Rutas prohibidas

- `apps/api/**`, `apps/mobile/**`, `db/**`, `workers/**` y migraciones.
- Contratos públicos, modelo canónico, permisos y semántica financiera.
- ADR, gates o decisiones humanas aceptadas.
- Datos reales, aprobación de releases o decisiones financieras sintéticas que
  aparenten una aprobación humana.

# Alcance

1. Construir las imágenes actuales de API, worker, web y migrador antes de migrar.
2. Recrear servicios con esas imágenes sin borrar volúmenes ni datos locales.
3. Verificar `/health/ready` y la dependencia `schema` al terminar el arranque.
4. Hacer que el contrato ejecutable del stack falle si se elimina build/readiness.
5. Probar que el preparador ve sus dos empresas y el revisor sólo su portafolio.
6. Probar denegación neutral ante acceso directo a una empresa ajena.
7. Reejecutar carga sintética, recorrido web, accesibilidad y validadores globales.
8. Registrar evidencia manual de la estación de revisión sin ejecutar aprobar ni
   rechazar y declarar lo que aún requiera fixture formal.
9. Permitir una corrida limpia aislada con volúmenes sintéticos nombrados, sin
   borrar, renombrar ni reutilizar el volumen local preexistente.

# Criterios de aceptación

- **AC-01.** `up.sh` construye `api`, `worker`, `web` y `migrate` antes de ejecutar
  migraciones o iniciar aplicaciones.
- **AC-02.** El migrador ejecutado corresponde al árbol actual y Compose recrea
  servicios cuando cambia una imagen.
- **AC-03.** El arranque sólo termina exitosamente si `/health/ready` informa
  `ready` y la dependencia `schema` está `up`.
- **AC-04.** No se usa `down --volumes`, prune ni borrado destructivo.
- **AC-05.** Pruebas de mutación textual detectan la eliminación de build,
  migración, seed, inicio o readiness.
- **AC-06.** Ana ve exactamente las dos empresas sintéticas autorizadas.
- **AC-07.** Beto ve sólo Panadería y no descubre Transportes por navegación.
- **AC-08.** Una URL directa de Beto hacia Transportes produce respuesta neutral
  de acceso y no muestra sus datos.
- **AC-09.** La carga y navegación sintéticas existentes siguen pasando.
- **AC-10.** La suite Axe no tiene hallazgos críticos o serios.
- **AC-11.** La verificación manual confirma controles de revisión para Beto sin
  mutar una corrección, aprobar una release ni cerrar un dataset.
- **AC-12.** Quality gate, grafo, catálogo y pruebas pertinentes quedan verdes;
  cualquier gap de supply chain o gate humano se reporta sin rebajarlo.
- **AC-13.** El handoff contiene base/head, matriz de evidencia, comandos, riesgos,
  rollback y el estado real de S1-READY.
- **AC-14.** Los nombres de volúmenes conservan sus defaults y admiten overrides
  explícitos para aceptación aislada; una corrida no toca el volumen habitual.

# Plan de pruebas

- Unitarias del contrato local con mutaciones de cada paso obligatorio.
- Playwright E2E con sesiones independientes de Ana y Beto y seed determinista.
- Playwright/Axe del shell y pantallas empresariales.
- Arranque real sobre Docker/WSL, consulta de readiness y recorrido visible.
- Validadores globales, sin declarar verde un exit no cero esperado.

# Privacidad, seguridad y límites

No se agregan secretos, telemetría ni datos financieros reales. El test de acceso
ajeno sólo verifica respuesta neutral; no fuerza `company_id` en una operación de
escritura. El navegador no ejecuta acciones financieras irreversibles. Los datos
persistidos por pruebas siguen siendo sintéticos y locales.

# Rollout y rollback

El cambio de arranque es local y reversible. Revertir sus commits devuelve el
comportamiento anterior sin eliminar volúmenes. Los E2E y validadores no cambian
estado productivo. Si el build actual no puede migrar desde el volumen existente,
el script falla cerrado y conserva la evidencia para diagnóstico.

# Definition of Done

- AC-01..AC-14 tienen evidencia reproducible.
- Se realizan commits incrementales de contrato, arranque, E2E y handoff.
- No se tocan API, DB, móvil, worker ni semántica financiera.
- La tarea termina `review_pending`, con revisión independiente pendiente o
  registrada; el implementador no se autoaprueba.
- S1-READY, DRG-00, DRG-01, ADR y decisiones humanas conservan su estado real.

# Comandos de verificación

```bash
python3 -B -m unittest tools.local_stack.test_validate
python3 -B -m tools.local_stack.validate
sh infra/local/up.sh
cd apps/web && npm run test:e2e && npm run test:a11y
cd ../.. && python3 -B -m tools.work_graph.validate
python3 -B -m tools.test_catalog.cli validate
python3 -B -m tools.quality_gate.cli
```
