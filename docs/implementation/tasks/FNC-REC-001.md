---
id: FNC-REC-001
alias: FNC-P4.6
title: Explorador read-only de candidatos de conciliación
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 03c1524ed0f18765b687767fec4ca8059cba081e
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado esperado

La plataforma local permite comparar dos datasets autorizados de una empresa y
explorar pares candidatos con señales deterministas y evidencia navegable. El
resultado es una hipótesis read-only: no crea match, no fusiona movimientos, no
confirma decisiones y no alimenta cierre o reporte certificado.

# Autoridad y contratos

- ADR-015: atributos de negocio generan candidatos, nunca identidad dura.
- FNC-DOM-004 y `idempotency-dedupe.json`: candidato no es decisión y no borra
  evidencia.
- FNC-DOM-003/006: matching no demuestra completitud ni conciliación de saldos.
- PRD wedge §7–8: el operador visualiza candidatos y razones; la decisión humana
  queda separada.
- `CURRENT_PHASE.md`: auto-match y cierre productivo permanecen prohibidos.

# Definition of Ready

- V0016, API y web están integradas en la base declarada.
- FNC-QA-006 dejó un stack sintético limpio y verificable.
- El Integration Steward reserva las rutas antes de editar.
- No se requiere migración: la proyección se deriva de movimientos inmutables.
- Una necesidad de persistir o confirmar abre otra tarea y exige semántica
  Accounting/Architecture; no amplía ésta.

# Rutas permitidas

- `apps/api/src/fincilia_api/reconciliation.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/api/tests/**` y `db/tests/test_reconciliation_candidates.py`
- `apps/web/src/**`
- `apps/web/tests/**`
- `.github/workflows/ci.yml` sólo si hace falta incorporar una suite ya creada.
- Ficha, handoff y registros centrales de FNC-REC-001 por Integration Steward.

# Rutas prohibidas

- `db/migrations/**`, seeds y esquema canónico.
- `workers/**`, `apps/mobile/**`, contratos compartidos y permisos.
- Persistencia de candidato/decisión, confirmación, rechazo, merge o reversión.
- Auto-match, score probabilístico, tolerancia monetaria, agregación N:M o cierre.
- IA, servicios externos y datos reales.

# Alcance

1. Motor read-only que compara dos datasets distintos de la misma empresa.
2. Sólo datasets `validated|published`, completitud apta para sugerencias y
   linaje completo.
3. Señales obligatorias: importe decimal exacto, moneda, dirección opuesta y
   ventana explícita de fecha; referencia normalizada sólo ordena/explica.
4. Consulta acotada, estable y paginada; no materializa producto cartesiano.
5. Endpoint autorizado server-side que responde neutral ante IDs ajenos.
6. Estación web visual con selectores, resumen, filtros y enlaces a movimientos.
7. Estados vacíos y bloqueos explican por qué no hay candidatos.
8. Pruebas puras, PostgreSQL, API/web, E2E y Axe con datos sintéticos.

# Criterios de aceptación

- **AC-01.** Los datasets deben ser distintos, company-scoped y elegibles; un ID
  ajeno, inválido o no elegible no revela existencia.
- **AC-02.** Ambos movimientos tienen moneda e importe exactos iguales,
  direcciones opuestas, cuentas distintas y distancia de fecha dentro de 0–31.
- **AC-03.** No se usa `float`, tolerancia, redondeo ni conversión de dinero.
- **AC-04.** La referencia suma una señal explicativa, nunca decide ni excluye.
- **AC-05.** Dos movimientos legítimos iguales pueden aparecer en varios pares;
  el motor no impone uno-a-uno.
- **AC-06.** El orden es determinista: referencia, distancia, ordinales e IDs.
- **AC-07.** `limit` máximo 200 y offset acotado; la consulta no carga todos los
  movimientos ni construye un cartesiano en memoria.
- **AC-08.** La respuesta declara `candidate_only`, reglas, ventana, truncamiento
  y que no prueba conciliación de saldos.
- **AC-09.** El endpoint exige `movement.read` y se deshabilita fuera de
  `synthetic_only`.
- **AC-10.** La web conserva empresa/datasets/ventana/página en URL y nunca
  calcula candidatos ni permisos.
- **AC-11.** Cada candidato muestra ambos importes como strings, fechas,
  descripciones, señales y enlaces al linaje de ambos movimientos.
- **AC-12.** La UI no ofrece confirmar, aprobar, empatar automáticamente ni
  declarar conciliado; presenta un aviso inequívoco.
- **AC-13.** Estados 401/403/404/422/503, vacío y posiblemente truncado se
  distinguen sin convertir errores en listas vacías.
- **AC-14.** Pruebas cross-company, datasets incompletos, misma dirección,
  moneda/importe distintos, fuera de ventana y referencia duplicada muerden.
- **AC-15.** Lint, tipos, unitarias, build, PostgreSQL, E2E, Axe y validadores
  aplicables pasan; el handoff conserva gaps humanos y S1 real.

# Privacidad, seguridad y observabilidad

No se registran descripciones, referencias, importes o payloads. El endpoint sólo
devuelve valores que el mismo principal puede leer como movimientos. Los errores
cross-company son neutrales. La vista no transmite datos fuera del stack local.

# Rollout y rollback

Superficie experimental local y sintética. Revertir la ruta, módulo y pantalla la
retira sin tocar datos. No existe migración ni estado que revertir. Para habilitar
decisiones persistentes se requiere tarea posterior, revisión Accounting/Security
y los gates de implementación de FNC-DOM-004.

# Definition of Done

- AC-01..AC-15 tienen evidencia reproducible.
- Commits incrementales separan reserva, backend, web/pruebas y handoff.
- No se modifica persistencia, permisos, móvil, worker ni gates.
- Estado final `review_pending`; el implementador no se autoaprueba.

