---
id: FNC-BET-001
title: Beta cerrada sintetica con dominio propio
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 93dac84
gate: BETA-01
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Security, Platform/SRE, Privacy/Legal, QA]
---

# Resultado

Fincilia puede ser usada por un grupo invitado desde un dominio HTTPS propio
para evaluar onboarding, usabilidad, aislamiento y comportamiento, sin datos
personales o financieros reales y sin presentar el entorno como producción.

# Alcance

- Entorno AWS separado del laboratorio T1 y de cualquier futuro entorno real.
- Único ingreso público por HTTPS; base, cache, objetos y API no se publican.
- Administración por SSM, sin SSH, y secretos generados fuera de Git.
- Registro sintético, aviso persistente y aceptación expresa de uso de datos
  inventados antes de crear una cuenta.
- Backups, restore ensayado, monitoreo mínimo, presupuesto y rollback.
- Despliegue por digest y migraciones separadas del arranque de aplicaciones.

# Criterios de aceptación

1. Dominio y certificado válidos, redirección HTTP→HTTPS y cookies `secure`.
2. Solo 80/443 públicos; SSH, PostgreSQL, Valkey, objetos y API no son públicos.
3. Alta, login, empresa inicial, carga sintética y cierre de sesión funcionan E2E.
4. La UI y los términos dicen claramente `beta cerrada · solo datos sintéticos`.
5. Rate limiting, límites de carga, logs redactados y health checks están activos.
6. Backups y restauración sintética tienen evidencia reproducible.
7. Alarmas de disponibilidad/costo y runbooks de incidente/rollback existen.
8. No se habilitan Google real, documentos reales, conectores o IA externa.
9. Security/Platform/Privacy/QA revisan antes de invitar a terceros.

# Fuera de alcance

DRG-00, DRG-01, datos reales, producción, GA, billing, SLA, conectores, OCR/IA
externa o aprobación jurídica definitiva.
