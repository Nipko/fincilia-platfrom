# Catálogo inicial de pruebas

| ID | Prueba | Primer task |
|---|---|---|
| TST-META-001 | IDs únicos, referencias válidas y dependencias sin ciclos | FNC-GOV-003 |
| TST-LOCAL-001 | Arranque limpio, healthchecks, persistencia y parada | FNC-PLT-002 |
| TST-CI-001 | Formato, tipos, unit, secretos, dependencias y contenedores | FNC-PLT-003 |
| TST-TEN-001 | Transferir engagement sin mover datos ni conservar grants | FNC-DOM-001 |
| TST-RLS-001 | Empresa A no lee/escribe B en tabla, vista o función | FNC-PLT-005 |
| TST-RLS-002 | SET LOCAL no filtra contexto entre transacciones del pool | FNC-PLT-005 |
| TST-AUTH-001 | authorization_version obsoleta invalida contexto emitido | FNC-PLT-005 |
| TST-AUTH-002 | Contexto revocado, expirado o con purpose distinto falla cerrado | FNC-PLT-005 |
| TST-MON-001 | Decimal, moneda, locale, timezone, redondeo y fechas | FNC-DOM-002 |
| TST-CMP-001 | Unknown/partial bloquea auto-match, cierre y certificado | FNC-DOM-003 |
| TST-IDEM-001 | Replay no duplica registro ni metering | FNC-DOM-004 |
| TST-DED-001 | Dos pagos legítimos idénticos permanecen separados | FNC-DOM-004 |
| TST-LIN-001 | Campo publicado retorna a evidencia y versión | FNC-DOM-005 |
| TST-OUT-001 | Cambio de dominio y outbox son atómicos | FNC-ARC-004 |
| TST-OUT-002 | Falla inyectada revierte dominio y outbox | FNC-PLT-005 |
| TST-INB-001 | Replay con mismo digest produce un solo efecto visible | FNC-PLT-005 |
| TST-INB-002 | Mismo event ID con digest distinto se rechaza | FNC-PLT-005 |
| TST-RET-001 | Claims concurrentes tienen un dueño y ACK obsoleto queda cercado | FNC-PLT-005 |
| TST-PAR-001 | Parser reproducible por engine_release | FNC-QA-003 |
| TST-CON-001 | Conector tolera replay, cursor, corrección y degradación | FNC-ARC-005 |
| TST-DRG-001 | Egress IA denegado, acceso auditado y purga reconciliada | FNC-QA-001 |
| TST-A11Y-001 | Teclado, foco, encabezados y estados no solo por color | FNC-UX-001 |
| TST-AI-001 | Redacción fail-closed, abstención, rollback y presupuesto | Fase 4 |

Los tests todavía son especificaciones. Un ID solo cambia a Implemented cuando existe un comando reproducible y evidencia en CI.
