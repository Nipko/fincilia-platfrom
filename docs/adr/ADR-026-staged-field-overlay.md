# ADR-026 — Overlay tipado por etapas

- Status: Proposed
- Date: 2026-08-24
- Owners: Data + Architecture, UNASSIGNED
- Approvers: Accounting + Security + Database, UNASSIGNED
- Gate: S1-READY
- Tasks: FNC-CLN-001, FNC-CLN-002
- Supersedes: none
- Plan refs: §18

## Contexto

ADR-006 exige correcciones manuales como overlays append-only y no destructivos.
`LINEAGE_SPEC.md` exige valor tipado, digest base esperado, actor, motivo,
versiones y revisión independiente en campos críticos. V0012 materializa
`lineage_row_override`, pero deliberadamente guarda solo digests y describe una
desviación **ya aplicada** al construir un movimiento canónico.

Guardar una corrección propuesta en `lineage_row_override` perdería el valor que
debe revisar Accounting. Actualizar el movimiento actual violaría su
inmutabilidad y haría que el dataset histórico cambiara bajo la misma identidad.

## Propuesta

Separar dos momentos con identidades inmutables:

1. `field_overlay` guarda la propuesta tipada y su base esperada bajo RLS. Su
   revisión vive en una fila append-only separada y exige segregación de
   funciones.
2. Una aplicación posterior crea un nuevo `processing_run` y
   `dataset_version`, reproduce determinísticamente el movimiento, materializa
   `lineage_row_override` con los digests anterior/resultante y conserva el
   dataset base intacto.

Una aprobación solo significa “autorizada para aplicar”; nunca muta ni publica.
Mientras una propuesta esté pendiente, o aprobada sin aplicación, el dataset
base queda bloqueado para publicación. Una propuesta rechazada no se aplica y no
bloquea.

La primera rebanada restringe los valores a tipos determinísticos y campos
críticos soportados: importe decimal exacto, moneda ISO de tres letras,
dirección cerrada y fechas ISO. No se acepta código, fórmula, JSON arbitrario,
float ni un locator aportado por cliente.

## Alternativas descartadas

- **UPDATE del movimiento:** rompe inmutabilidad, reproducción y auditoría.
- **Valor nuevo solo en audit log:** mezcla evidencia operativa con fuente de
  verdad y aumenta exposición en logs.
- **Digest sin valor en la propuesta:** el revisor no puede conocer ni validar
  lo que aprueba.
- **Aprobar y aplicar en una transacción web:** mezcla autorización humana con
  procesamiento y oculta fallos o drift posteriores.

## Consecuencias

- Hay una cola explícita de trabajo aprobado-pendiente-de-aplicar.
- El valor propuesto es información financiera y recibe RLS, mínimos
  privilegios, retención y lectura autorizada; no se replica a Valkey ni logs.
- Reprocesar cuesta más que actualizar, pero conserva históricos y hace visible
  el impacto.
- El contrato físico sigue propuesto hasta revisión independiente. Implementar
  el prototipo local sintético no acepta este ADR ni mueve un gate.

## Verificación requerida

- PostgreSQL real: RLS positiva/negativa, SoD, append-only, concurrencia
  optimista y blockers de publicación.
- Pruebas tipadas: decimales extremos, float rechazado, fechas y enum cerrados.
- FNC-CLN-002: reproducción a nueva versión, digest del conjunto ordenado,
  `lineage_row_override` y no mutación del dataset base.
