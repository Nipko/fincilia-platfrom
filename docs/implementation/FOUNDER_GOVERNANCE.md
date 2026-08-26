# Gobierno provisional del Founder

`FOUNDER-01` es el alias humano estable y seudónimo del fundador durante la etapa
fundacional. La correspondencia con su identidad civil se conserva fuera del
repositorio para no versionar datos personales.

El Founder asume provisionalmente la responsabilidad accountable de Integration,
Product, Accounting, Architecture, Security, Privacy y Legal. La acumulación no
fusiona los roles ni sus controles: una misma actuación puede requerir varias
responsabilidades, pero `FOUNDER-01` cuenta una sola vez como persona.

## Separación de funciones

`FOUNDER-01` no puede revisar de forma independiente una decisión que aprobó, un
cambio que implementó ni un control bajo su propia responsabilidad. Las revisiones
independientes de Accounting, Database, Security y Privacy/Legal permanecen como
`pending_distinct_humans` hasta registrar otras personas estables.

## Decisiones aprobadas el 25 de agosto de 2026

La fuente estructurada es `founder-governance.json`. Contiene las diez decisiones
técnicas, la ratificación de ADR-001..010 y ADR-023, y la aceptación específica de
ADR-024. Para ADR-002 selecciona el migrador SQL-first propio; para ADR-008 posterga
Temporal en favor del dispatcher, leases y workers respaldados por PostgreSQL.

La aprobación retira esos ítems de las listas `unresolved_decisions`; no acredita
por sí sola revisiones independientes, cadena de suministro, gates de datos ni
producción. ADR-026 y ADR-027 quedan expresamente fuera del paquete.

## Límites

- Solo datos sintéticos.
- S1-READY, DRG-00 y DRG-01 siguen fail-closed hasta cumplir el resto del checklist.
- No autoriza datos financieros reales, piloto, producción ni proveedores externos.
- La aplicación puede tener usuarios multirrol, pero esas identidades no sustituyen
  revisores humanos de gobierno.
