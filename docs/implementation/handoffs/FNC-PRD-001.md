# Handoff FNC-PRD-001

- Estado: PARTIAL — borrador completo; aprobación bloqueada por FNC-GOV-001 y validación humana/empírica.
- Agente: A1 Product subagent `/root/e0_prd`.
- Accountable owner: UNASSIGNED.
- Revisores requeridos: Product, Accounting y Architecture; UX como revisión de uso.
- Base SHA: No capturado por el subagente; el Integration Steward es el único ejecutor de Git en modo orquestado.
- Head SHA: No aplica; no se ejecutó Git.
- Rama/worktree: Filesystem compartido; administrado por Integration Steward.
- Objetivo y resultado: Convertir el wedge factura/pedido→pago→fee/retención→liquidación→banco→ERP en un PRD accionable. Se entregaron actores diferenciados, JTBD, flujo feliz, excepciones, división web/móvil, fuentes, métricas, alcance, exclusiones, riesgos y 12 hipótesis con criterios de validación para 5 firmas y 10 cierres.
- Paths modificados: `docs/product/PRD_WEDGE.md`; `docs/implementation/handoffs/FNC-PRD-001.md`.
- Paths reservados que se liberan: `docs/product/PRD_WEDGE.md`; `docs/implementation/handoffs/FNC-PRD-001.md`.
- ADR/contratos afectados: Ninguno modificado. El PRD deja dependencias explícitas hacia tenancy, dominio financiero y RBAC/ABAC/SoD.
- Migraciones/eventos/flags: No aplica.
- Decisiones y supuestos: La firma contable con 5–25 empresas es el comprador prioritario; la PYME es la entidad servida y frontera estable de datos. Los archivos/exportaciones son canal permanente. Las metas de reducción son hipótesis hasta medir baseline y piloto. DIAN `AttachedDocument` recibido no se considera fuente suficiente de facturas emitidas/CxC.
- Riesgos de seguridad/privacidad/datos: Solo se usó un ejemplo completamente sintético. El documento no autoriza corpus real, conexiones reales, PII, secretos ni documentos financieros reales. Observación/corpus real queda condicionada a DRG-00 y controles aplicables.
- Compatibilidad y consumidores: Insumo provisional para FNC-DOM-001, FNC-ARC-001, FNC-SEC-001, FNC-DAT-001 y FNC-UX-001. Debe permanecer Draft hasta asignar owners y completar revisiones.
- Rollback: El Integration Steward puede excluir ambos archivos del conjunto de integración; no hay cambios de runtime, esquema ni infraestructura.
- Comandos ejecutados: Lectura con `Get-Content` de `AGENTS.md`, `CURRENT_PHASE.md`, ficha FNC-PRD-001, `OWNERSHIP.md`, `DEFINITION_OF_DONE.md`, plantilla de handoff y §§1–4/48 del plan; búsqueda de términos y marcadores con `rg`; validación PowerShell de 16 condiciones de aceptación, consistencia de columnas en tablas Markdown y balance de cercas. No se ejecutó Git.
- Resultado exacto de pruebas: 16/16 condiciones documentales `PASS`; todas las tablas Markdown tienen conteo de columnas consistente; 0 cercas desbalanceadas; 0 merge markers, `TODO`, `FIXME` o cadenas con forma de correo encontradas en los dos archivos. No aplican build, lint de código ni pruebas de runtime.
- Evidencia: `docs/product/PRD_WEDGE.md` contiene las secciones de actores, JTBD, fuentes, flujo, excepciones, web/móvil, alcance, anti-promesas, métricas, hipótesis, aceptación, dependencias, riesgos y ejemplo sintético.
- Fallos conocidos: No hay aprobación humana, baseline ni evidencia de 5 firmas/10 cierres. No se puede marcar COMPLETE ni Accepted.
- Trabajo pendiente con IDs: FNC-GOV-001 debe asignar owners; FNC-DOM-001 debe precisar tenancy y semántica financiera; FNC-SEC-001 debe precisar autorización y SoD; FNC-UX-001 debe validar flujos; la tarea autorizada de investigación debe recopilar evidencia tras los gates aplicables.
- Bloqueos, owner y condición de desbloqueo: FNC-GOV-001 (Founder) asigna Product/Accounting/Architecture; Product coordina evidencia de 5 firmas y 10 cierres; Legal/Security/Product firman DRG-00 antes de recibir corpus real; Product, Accounting y Architecture revisan y aprueban la versión resultante.

El handoff es reproducible sin consultar el historial del chat.
