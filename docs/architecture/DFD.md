# DFD v0 — trust boundaries y flujos

- Estado: Draftable
- Tarea: FNC-ARC-002
- Gate: S1-READY
- Owners: Architecture + Security, UNASSIGNED

## Zonas de confianza

| Zona | Contenido | Postura |
|---|---|---|
| Z0 | Dispositivos y proveedores externos | No confiable |
| Z1 | Edge público | Autenticación, límites, WAF |
| Z2 | Aplicación/control privado | Autorización y dominio |
| Z3 | Workers de procesamiento | Aislados, capacidad acotada, sin egress por defecto |
| Z4 | PostgreSQL, objetos, caché y workflow | Acceso por identidad y scope |
| Z5 | Egress controlado | Solo AI Gateway/conectores aprobados |
| Z6 | Seguridad, auditoría y backups | Separado, acceso JIT |

## Flujos obligatorios

| ID | Flujo | Datos | Controles mínimos | Pendientes |
|---|---|---|---|---|
| F01 | Autenticación | Identidad/sesión | OIDC, MFA/assurance, sesión corta | IdP |
| F02 | Upload a quarantine | Binario no confiable | Presigned exacto, tamaño/MIME, hash | PCI S-01 |
| F03 | Scan y promoción a raw | Binario/metadatos | AV, CDR cuando aplique, decisión auditada | Proveedor AV |
| F04 | Parse/extracción | Tokens/celdas | Worker sin egress, límites, version_id | Runtime |
| F05 | Mapping/publicación | Dataset/linaje | Receta versionada, validación, completitud | Esquema v0.1 |
| F06 | Finanzas/reconciliación/cierre | Datos financieros | Decimal, RLS, SoD, evidencia | Modelos v0.1 |
| F07 | Informe/exportación | Derivado sensible | Revalidar grants, URL corta, audit event | Retención |
| F08 | OCR/IA | Fragmento minimizado | AI Gateway, redacción fail-closed, no training | L-02 |
| F09 | Conector/webhook | Eventos fuente | Firma/replay/idempotencia, scopes | B-01 |
| F10 | Auditoría/digest | Metadatos permitidos | Append-only, hash/digest, cuenta separada | Backend |
| F11 | Borrado/tombstone | Identificadores/alcance | Delete ledger fuera de restore | L-01 |
| F12 | Restore | Snapshot/versiones | Reaplicar tombstones, reconciliar | RPO/RTO |
| F13 | Revocación engagement | Grants/jobs/links | authorization_version e invalidación | Modelo final |

## Checklist por flujo

Antes de Accepted, cada flujo documenta:

- Actor y propósito.
- Clasificación y company_id.
- Protocolo, autenticación y cifrado.
- Persistencia, región, retención y borrado.
- Logs permitidos mediante allowlist.
- Amenazas, controles y prueba negativa.
- Owner y modo degradado.

TBD solo se acepta con un ID de decisión o tarea.

