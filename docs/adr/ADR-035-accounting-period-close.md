# ADR-035 — cierre y reapertura de periodos contables

- Estado: **Proposed; implementación sintética autorizada, activación sujeta a revisión**
- Fecha: 2026-08-31
- Tarea: FNC-CLS-006
- Owners: Accounting + Architecture + Security, accountable FOUNDER-01
- Gates: S1-READY, DRG-00, DRG-01

## Contexto

FNC-CLS-001..005 construyeron diagnóstico, saldos, conciliación, linaje y un
expediente revisado, pero deliberadamente no crearon un estado de cierre. Un
botón que solo cambie una etiqueta sería engañoso: cerrar debe congelar la
evidencia observada y bloquear nuevas escrituras financieras del periodo.

## Decisión propuesta

- PostgreSQL es la fuente de verdad del estado de periodo.
- El cierre es una transición humana append-only que referencia exactamente un
  expediente `evidence_reviewed`, su digest, statements y versiones de linaje.
- El actor que cierra debe ser el revisor asignado y debe ser distinto del
  preparador. La IA, un worker o un rol administrativo nunca cierran.
- El periodo contable de un movimiento se deriva de `occurred_on` mientras el
  modelo canónico no tenga un campo explícito de periodo. Accounting debe revisar
  esta elección antes de activar datos reales.
- Un periodo cerrado impide por base de datos nuevas materializaciones de
  movimientos y nuevos statements que lo intersecten. No se mutan filas previas.
- Reabrir requiere solicitud motivada y decisión de otra persona; la aprobación
  no borra el cierre, crea una nueva transición. Un cierre posterior incrementa
  la versión.
- Lecturas, snapshots y auditoría son company-scoped, RLS forzada e inmutables.

## Consecuencias

El cierre queda reproducible y reversible sin alterar historia. Añade controles
de concurrencia, una migración forward-only y revisión independiente de
Accounting/Database/Security. No convierte informes en estados financieros
certificados ni autoriza datos reales.

## Configuración pendiente para el final

- Política exacta de periodo para `posted_on` frente a `occurred_on`.
- Títulos y alcance jurídico de “cerrado” y “certificado”.
- Revisores independientes nominales y step-up AAL2 productivo.

