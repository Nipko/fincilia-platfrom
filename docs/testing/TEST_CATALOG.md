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
| TST-LIN-002 | Campo publicado sin arista queda bloqueado | FNC-DOM-005 |
| TST-LIN-003 | Arista entre empresas se rechaza | FNC-DOM-005 |
| TST-LIN-004 | Ciclo de linaje se rechaza | FNC-DOM-005 |
| TST-LIN-005 | Locator fuera de límites se rechaza | FNC-DOM-005 |
| TST-LIN-006 | Formato desconocido no fabrica locator | FNC-DOM-005 |
| TST-OVR-001 | Overlay no muta evidencia de origen | FNC-DOM-005 |
| TST-OVR-002 | Overlay sobre base obsoleta entra en conflicto | FNC-DOM-005 |
| TST-OVR-003 | Undo crea otro overlay append-only | FNC-DOM-005 |
| TST-OVR-004 | Cadena de overlays se aplica determinísticamente | FNC-DOM-005 |
| TST-OVR-005 | Campo crítico exige segregación de funciones | FNC-DOM-005 |
| TST-OVR-006 | Overlay pendiente no alimenta publicación | FNC-DOM-005 |
| TST-OUT-001 | Cambio de dominio y outbox son atómicos | FNC-ARC-004 |
| TST-OUT-002 | Falla inyectada revierte dominio y outbox | FNC-PLT-005 |
| TST-INB-001 | Replay con mismo digest produce un solo efecto visible | FNC-PLT-005 |
| TST-INB-002 | Mismo event ID con digest distinto se rechaza | FNC-PLT-005 |
| TST-RET-001 | Claims concurrentes tienen un dueño y ACK obsoleto queda cercado | FNC-PLT-005 |
| TST-PAR-001 | Mismo manifest produce la misma reproduction key | FNC-DOM-005 |
| TST-PAR-002 | Release affects_results sin evaluación se rechaza | FNC-DOM-005 |
| TST-PAR-003 | Release neutral sin equivalencia se rechaza | FNC-DOM-005 |
| TST-PAR-004 | Build sucio o sin SBOM se rechaza | FNC-DOM-005 |
| TST-PAR-005 | Reprocess no sobrescribe versiones | FNC-DOM-005 |
| TST-PAR-006 | Snapshot conserva release y versiones originales | FNC-DOM-005 |
| TST-PAR-007 | Release revocada no inicia runs nuevos | FNC-DOM-005 |
| TST-PRV-001 | Tags de privacidad no bajan silenciosamente | FNC-DOM-005 |
| TST-DED-002 | Linaje no fusiona hechos legítimos idénticos | FNC-DOM-005 |
| TST-XCON-001 | Todo store lógico queda mapeado exactamente una vez | FNC-ARC-006A |
| TST-XCON-002 | Todo store DFD queda mapeado exactamente una vez | FNC-ARC-006A |
| TST-XCON-003 | Uso activo se deriva de persistencia declarada | FNC-ARC-006A |
| TST-XCON-004 | Zonas de object storage conservan aislamiento | FNC-ARC-006A |
| TST-XCON-005 | Clases canónicas igualan subconjunto financiero DFD | FNC-ARC-006A |
| TST-XCON-006 | Eje personal permanece ortogonal, pendiente y fail-closed | FNC-ARC-006A |
| TST-CON-001 | Conector tolera replay, cursor, corrección y degradación | FNC-ARC-005 |
| TST-DRG-001 | Egress IA denegado, acceso auditado y purga reconciliada | FNC-QA-001 |
| TST-A11Y-001 | Teclado, foco, encabezados y estados no solo por color | FNC-UX-001 |
| TST-A02-001 | Región, transmisión, stores, gates y selección permanecen fail-closed | FNC-ARC-003 |
| TST-AI-001 | Redacción fail-closed, abstención, rollback y presupuesto | Fase 4 |
| TST-DB-001 | Roles runtime sin superusuario/BYPASSRLS y tablas sensibles con FORCE RLS | FNC-PLT-005 |
| TST-BAL-001 | Ecuación de saldo conserva moneda, signo y periodo | FNC-DOM-003 |
| TST-BAL-002 | Estado de conciliación enlaza saldo, partidas y evidencia | FNC-DOM-003 |
| TST-CLOSE-001 | Diferencia no explicada bloquea cierre salvo excepción autorizada | FNC-DOM-003 |
| TST-CMP-002 | Completitud desconocida o parcial impide publicación automática | FNC-DOM-003 |
| TST-EXC-001 | Excepción conserva motivo, actor, aprobación y reverso | FNC-DOM-003 |
| TST-CON-002 | Conector rechaza firma o autorización inválida | FNC-ARC-005 |
| TST-CON-003 | Cursor avanza solo tras persistencia confirmada | FNC-ARC-005 |
| TST-CON-004 | Corrección del proveedor crea revisión y no sobrescribe evidencia | FNC-ARC-005 |
| TST-CON-005 | IDs reutilizados por proveedor producen conflicto visible | FNC-ARC-005 |
| TST-CON-006 | Ventana de replay permanece acotada y auditable | FNC-ARC-005 |
| TST-CON-007 | Backoff respeta deadline y presupuesto total | FNC-ARC-005 |
| TST-CON-008 | Circuit breaker no se convierte en dueño de reintentos | FNC-ARC-005 |
| TST-CON-009 | Credenciales nunca llegan a logs, eventos ni stores de negocio | FNC-ARC-005 |
| TST-CON-010 | Revocación detiene ingesta y tareas posteriores | FNC-ARC-005 |
| TST-CON-011 | Degradación conserva archivos como canal permanente | FNC-ARC-005 |
| TST-CON-012 | Movimientos pending y posted no se duplican silenciosamente | FNC-ARC-005 |
| TST-CON-013 | Cambio de esquema bloquea publicación y abre revisión | FNC-ARC-005 |
| TST-CON-014 | Conector no cruza empresa, cuenta ni autorización | FNC-ARC-005 |
| TST-CON-015 | Métricas y errores exponen estado sin filtrar datos financieros | FNC-ARC-005 |
| TST-DED-003 | Periodos de extracto solapados conservan ambas observaciones | FNC-DOM-004 |
| TST-DED-004 | Reverso de deduplicación es append-only y conserva evidencia | FNC-DOM-004 |
| TST-DED-005 | Similitud entre empresas no genera candidato | FNC-DOM-004 |
| TST-IDEM-002 | Misma clave y mismo payload retorna el resultado original | FNC-DOM-004 |
| TST-IDEM-003 | Misma clave y payload distinto genera conflicto sin segundo efecto | FNC-DOM-004 |
| TST-IDEM-004 | Caída tras commit permite entregar outbox sin duplicar dominio | FNC-DOM-004 |
| TST-IDEM-005 | Worker obsoleto tras expirar lease no puede publicar | FNC-DOM-004 |
| TST-IDEM-006 | Reutilización de ID del proveedor genera conflicto | FNC-DOM-004 |
| TST-IDEM-007 | Solo una capa posee cada política de reintento | FNC-DOM-004 |
| TST-DLQ-001 | Trabajo agotado llega a dead letter minimizada y visible | FNC-ARC-004 |
| TST-DLQ-002 | Replay reautoriza y conserva clave de idempotencia | FNC-ARC-004 |
| TST-DLQ-003 | Descartar exige actor, motivo y auditoría | FNC-ARC-004 |
| TST-EXE-001 | Pérdida de Valkey no pierde estado de dominio o reintento | FNC-ARC-004 |
| TST-EXE-002 | Historial de workflow nunca es autoridad financiera | FNC-ARC-004 |
| TST-EXT-001 | Resultado externo desconocido no se reintenta a ciegas | FNC-ARC-004 |
| TST-ORD-001 | Hueco en secuencia pausa efectos hasta resolver orden | FNC-ARC-004 |
| TST-OUT-003 | Entrega duplicada produce un solo efecto visible | FNC-ARC-004 |
| TST-OUT-004 | Mismo event ID con digest distinto genera conflicto | FNC-ARC-004 |
| TST-OUT-005 | Caída del consumidor revierte recibo y efecto juntos | FNC-ARC-004 |
| TST-RET-002 | Adaptador y circuit breaker no programan reintentos | FNC-ARC-004 |
| TST-RET-003 | Intentos consumen presupuesto temporal y de costo | FNC-ARC-004 |
| TST-RET-004 | Fencing token obsoleto no puede publicar | FNC-ARC-004 |
| TST-RET-005 | Retry-After del proveedor no excede presupuesto | FNC-ARC-004 |
| TST-SCH-001 | Esquema desconocido o incompatible no produce efecto | FNC-ARC-004 |
| TST-TEN-002 | Evento o dead letter no puede cruzar empresa | FNC-ARC-004 |
| TST-MUT-001 | Mutación contractual debe producir exactamente los hallazgos esperados | FNC-QA-005 |

Los tests todavía son especificaciones. Un ID solo cambia a Implemented cuando existe un comando reproducible y evidencia en CI.
