# Threat model v0 — Fincilia

| Campo | Valor |
|---|---|
| Tarea | FNC-SEC-002 |
| Estado | Review pending |
| Método | STRIDE + abuso de negocio/contable + privacidad |
| Gate | S1-READY |
| Owners requeridos | Security + Architecture |
| Revisores | Privacy + Accounting según escenario |
| Datos usados | Exclusivamente sintéticos |
| Modelo ejecutable | `docs/security/threat-model.json` |

Este documento prioriza qué puede fallar y cómo demostrar que falla cerrado. El JSON asociado es la fuente verificable de scores, referencias y cobertura. El riesgo residual es una **proyección de diseño**, no riesgo aceptado ni eficacia productiva demostrada.

## 1. Alcance

Incluye los flujos F01–F13 del DFD: identidad, upload, scan, parsing, mapping/publicación, conciliación/cierre, export, IA/OCR, conectores, auditoría, borrado, restore y revocación. Incluye amenazas del plano cloud como abuso de workload y supply chain, pero no elige proveedor/región.

Excluye pagos/custodia, auto-match vinculante, producción, conectores reales y datos reales. Estas exclusiones son reducción de superficie, no evidencia de que el riesgo desapareció.

## 2. Activos críticos

| ID | Activo | Propiedad que se protege |
|---|---|---|
| A01 | Identidades, sesiones y assurance | Autenticidad, revocación y no suplantación |
| A02 | Company, engagement, grants y authorization version | Aislamiento y delegación revocable |
| A03 | Evidencia original, hash y provenance | Integridad, confidencialidad e inmutabilidad |
| A04 | Datos financieros, saldos y statements | Exactitud decimal, completitud y aislamiento |
| A05 | Linaje, recetas, overlays y engine release | Reproducibilidad y explicación |
| A06 | Matches, excepciones y cierres | SoD, integridad y no repudio |
| A07 | Exports, informes y enlaces | Scope, expiración y confidencialidad |
| A08 | Secretos y credenciales referenciadas | Confidencialidad y mínimo privilegio |
| A09 | Audit chain, digest y delete ledger | Integridad, disponibilidad y segregación |
| A10 | Backups, restore e inventario | Recuperación sin resurrección |
| A11 | Presupuesto/costo, jobs y metering | Idempotencia y disponibilidad económica |
| A12 | Contratos, imágenes y releases | Integridad de supply chain |

## 3. Método de puntuación

- Probabilidad e impacto: 1 (bajo) a 5 (máximo).
- Score: `probabilidad × impacto`.
- Severidad: 1–4 baja, 5–9 media, 10–16 alta, 17–25 crítica.
- Inherente: sin controles del diseño.
- Residual proyectado: suponiendo que los controles listados se implementan y validan.

No se reduce un score para “pasar” un gate. Un residual proyectado sigue abierto hasta tener prueba, owner humano y aceptación explícita. El validador prohíbe `accepted` o `closed` durante E0.

## 4. Resumen priorizado

| ID | Escenario | Inherente | Residual proyectado | Gate/tratamiento |
|---|---|---:|---:|---|
| TM-001 | Lectura/escritura cross-company por resolución o RLS | 25 crítico | 8 medio | S1-READY / mitigate |
| TM-002 | Contexto de pool o capability queda contaminado | 20 crítico | 8 medio | S1-READY / mitigate |
| TM-003 | Sesión, grant o service principal escalado | 20 crítico | 9 medio | S1-READY / mitigate |
| TM-004 | Revocación no invalida job/link/cache/sesión | 20 crítico | 8 medio | S1-READY / mitigate |
| TM-005 | Archivo hostil, PAN o contenido mal clasificado cruza raw | 20 crítico | 8 medio | DRG-00 / avoid+mitigate |
| TM-006 | Worker escapa, exfiltra o publica canónico | 20 crítico | 6 medio | S1-READY / mitigate |
| TM-007 | Dataset parcial/ambiguo llega a decisión o cierre | 25 crítico | 8 medio | S1-READY / mitigate |
| TM-008 | Dedupe colapsa dos movimientos legítimos | 20 crítico | 6 medio | S1-READY / avoid+mitigate |
| TM-009 | Replay/retry duplica efecto, dato o costo | 16 alto | 6 medio | S1-READY / mitigate |
| TM-010 | IA/archivo inyecta instrucciones o filtra información | 25 crítico | 8 medio | Fase 4 / avoid+mitigate |
| TM-011 | Telemetría expone datos financieros/identidad | 20 crítico | 6 medio | S1-READY / mitigate |
| TM-012 | Export sobrevive revocación o cambia de scope | 20 crítico | 8 medio | S1-READY / mitigate |
| TM-013 | Auditoría se omite, altera o permite auto-revisión | 16 alto | 8 medio | S1-READY / mitigate |
| TM-014 | Restore resucita datos borrados | 25 crítico | 8 medio | DRG-00 / mitigate |
| TM-015 | Release/dependencia manipulada cambia resultados | 20 crítico | 8 medio | S1-READY / mitigate |

## 5. Controles transversales

- Identidad verificada, assurance/step-up y sesiones revocables.
- Resolución recurso→company server-side; FK compuestas y FORCE RLS con rol no-owner.
- `authorization_version` en jobs, links, sesiones y caches; revalidación antes de leer/publicar/descargar.
- Quarantine por versión exacta, límites y scan antes de raw; contenido siempre no confiable.
- Workers sin egress, capability por versión/company/budget y retorno exclusivo de manifiesto.
- Completitud, ambigüedad, linaje, decimal exacto, balance statement y SoD como gates separados.
- Dedupe como candidato; nunca UNIQUE por fecha/monto/dirección/referencia.
- Idempotency keys estables, inbox/outbox transaccional y ownership único de retries.
- AI Gateway fail-closed; minimización, redacción, no-training y cero autoridad financiera.
- Telemetría por allowlist, exports con TTL/scope/revalidación y auditoría append-only.
- Delete ledger segregado; restore reaplica tombstones y reconcilia inventario antes de abrir.
- Engine release fijado, SBOM, hash/firma, provenance, canary y rollback.

## 6. Evidencia actual y deuda de prueba

Evidencia ya reproducible en E0:

- Spike PostgreSQL: RLS cross-company, contexto de transacción y outbox.
- Kernel de autorización: 61 pruebas, incluidas revocación, SoD, worker y denegación uniforme.
- Corpus sintético: exact replay, movimientos idénticos legítimos y celdas hostiles inertes.
- DFD: 13 pruebas de mutación sobre egress, worker, logs, IA, delete ledger, restore y revocación.

Esto demuestra contratos/spikes, no eficacia productiva. El modelo JSON etiqueta la evidencia `passed_spike` o `planned`; un riesgo no se cierra por acumular pruebas unitarias.

## 7. Condiciones de gate

Antes de S1-READY:

- cada riesgo S1 debe tener owner humano nominal, tratamiento y revisor independiente;
- los controles de código deben probarse positivos y negativos;
- ningún residual alto/crítico puede aceptarse implícitamente;
- las brechas SEC-001 de role/action, principal de servicio y compatibilidad action/resource/purpose deben resolverse o quedar como blocker con fecha;
- engine release y supply chain deben tener contrato verificable.

Antes de DRG-00:

- TM-005 y TM-014 requieren pruebas sintéticas end-to-end de quarantine/PAN y restore+tombstones;
- L-01/S-01/A-02 deben estar decididos y revisados;
- cero riesgo crítico sin tratamiento, owner y fecha.

## 8. Riesgos no aceptables por política

- Cross-company conocido sin contención.
- Autoridad financiera o de acceso delegada a IA/worker/cliente.
- Dataset `unknown`, `partial` o `unverified` usado para cierre certificado.
- PAN/CVV/credenciales bancarias o DIAN persistidas en raw/logs.
- Borrado declarado sin delete ledger e inventario reconciliado.
- Cierre con diferencia no explicada oculta o SoD omitido.

La única respuesta admisible mientras exista uno es evitar/bloquear o mitigar con gate; no “aceptar por velocidad”.

## 9. Límites y revisión

FNC-SEC-002 queda `Review pending` hasta revisión independiente de Security y Architecture; Privacy revisa TM-005/010/011/012/014 y Accounting revisa TM-007/008. La aceptación residual requiere persona nominal, evidencia, fecha y alcance. Este documento no supera S1-READY ni autoriza DRG-00.
