# ADR-028 — Propuestas manuales agrupadas sin asignaciones

- Estado: **Proposed**
- Fecha: 2026-08-26
- Tarea: FNC-REC-005
- Gate: S1-READY; efecto `none`
- Datos autorizados: exclusivamente sintéticos
- Revisión pendiente: Accounting, Security, Database, Architecture y Product

## Contexto

Los extractos y auxiliares reales suelen contener lotes o abonos que relacionan
un movimiento con varios. El ledger de ADR-027 solo representa pares y aplazó
grupos porque confirmar una relación N:M o repartir un importe exige semántica
contable todavía no aceptada.

La plataforma necesita, sin embargo, poder conservar el trabajo preparatorio de
una persona sin convertirlo en una decisión financiera. Un borrador compuesto
por movimientos canónicos completos es reversible, auditable y no requiere
inventar una asignación.

## Decisión propuesta

1. `match_group_candidate` conserva un movimiento ancla y un arreglo canónico
   ordenado de 2..49 movimientos relacionados. El lado del ancla determina si
   la vista representa 1:N o, al invertir datasets, N:1.
2. Todos los miembros son movimientos completos, de una empresa y moneda, con
   linaje completo y datasets elegibles (`validated|published`, completitud
   verificada o excepción aceptada). Debe haber al menos dos datasets para
   impedir agrupaciones internas ambiguas.
3. La composición es append-only y única por empresa, versión de regla, ancla y
   conjunto ordenado. Un recibo separado aporta idempotencia por actor.
4. La suma del lado relacionado y la diferencia frente al ancla se derivan de
   movimientos inmutables usando `numeric(38,12)`/Decimal. No se persisten como
   verdad nueva y no constituyen tolerancia, balance ni asignación.
5. En esta rebanada solo existe el estado `draft`. No hay decisión, reserva de
   miembros, confirmación, rechazo, reversal ni consumo desde cierre.
6. RLS forzada, FK company-scoped, privilegios mínimos, auditoría atómica y
   validación en PostgreSQL protegen la composición incluso ante escritura
   directa o concurrencia.

## Alternativas descartadas por ahora

- **N:M:** no hay un ancla inequívoca y exige un modelo de asignaciones.
- **Asignar importes parciales:** introduce redondeo, residuales y materialidad
  sin contrato contable aceptado.
- **Reutilizar `match_candidate`:** su esquema y exclusividad modelan exactamente
  dos miembros; sobrecargarlo debilitaría invariantes ya probadas.
- **Confirmar el grupo:** convertiría un borrador visual en efecto semántico sin
  reglas de supersession, cierre ni estados de cuenta.
- **Guardar totales:** duplicaría hechos financieros y permitiría drift.

## Consecuencias y deuda explícita

- Se cubre el trabajo manual 1:N/N:1 sin declarar una conciliación.
- Un movimiento puede aparecer en varios borradores y también en expedientes
  1:1; la exclusividad solo sigue aplicando a confirmaciones 1:1.
- Una futura decisión deberá definir asignaciones exactas, solapamiento,
  materialidad, reversals, N:M y efectos sobre statements/cierre.
- Implementar localmente con datos sintéticos no acepta este ADR ni mueve gates.

## Evidencia requerida

PostgreSQL real debe probar cardinalidad, canonización, RLS, pertenencia,
moneda, elegibilidad, append-only, idempotencia, concurrencia, auditoría y no
mutación. API/web deben probar permisos, neutralidad cross-company, Decimal
exacto, orientación 1:N/N:1, E2E y accesibilidad.
