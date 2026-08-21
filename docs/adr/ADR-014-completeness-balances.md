# ADR-014 — Completitud y conciliación de saldos

- Status: Accepted
- Date: 2026-08-21
- Owners: Accounting + Data + Product, UNASSIGNED
- Gate: S1-READY
- Task: FNC-DOM-003
- Plan refs: §9.2, §16.1

## Decision

Por fuente/cuenta/periodo se evalúan conteo, débitos, créditos, saldo inicial/final, páginas/secciones y cursor/secuencia cuando existen.

Estados: verified, mismatch, unknown y accepted_exception.

Unknown nunca significa completo. Dataset partial/unverified sirve para investigar, pero bloquea auto-match, cierre y reporte certificado salvo excepción explícita con responsable, aprobador, alcance y expiración.

El cierre exige:

~~~text
saldo extracto ± partidas conciliatorias = saldo libros
~~~

## Verification

TST-CMP-001 y reconciliation statement con diferencia no explicada cero.

