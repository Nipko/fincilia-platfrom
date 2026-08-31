---
id: FNC-ING-006
status: REVIEW_PENDING
base_sha: 682e609
integration_sha: pending
data_ceiling: synthetic_only
independent_reviewers: [Security, Privacy, Data, Architecture, QA]
---

# Entrega

PDF pasivo con texto embebido ya recorre cuarentena, inspección integral,
promoción, perfilado y extracción. V0047 permite localizadores `pdf_text` con
página, bloque, caja, confianza y release del parser. La API expone únicamente
el manifiesto sin valores y la web explica estado, límites y revisión humana.

PDF activo, cifrado, firmado, enlazado, malformado o fuera de límites se
rechaza. PDF sin texto queda `ocr_required`; el original permanece en
cuarentena. El puerto externo no tiene proveedor ni egress configurado.

# Evidencia ejecutada

- Build del worker con hashes obligatorios: OK.
- Migración V0047 sobre PostgreSQL 17 real: aplicada.
- Worker: 28 pruebas, OK; incluye seis adversariales PDF.
- Admisión compartida: 55 pruebas, OK sin instalar el parser en la API.
- Esquema y privilegios: 27 pruebas, OK sobre PostgreSQL real.
- API: 186 pruebas, OK.
- Web: `typecheck` y build de producción, OK.

# Riesgos y decisiones pendientes

- ADR-036 continúa `Proposed`; esta entrega no lo acepta.
- OCR externo sigue deshabilitado hasta proveedor/región/DPA/retención/costo.
- La caja PDF procede de operadores de texto, no de render OCR; siempre exige
  revisión humana antes de mapear.
- Datos reales y gates DRG-00/DRG-01 no cambian.

# Rollback

Retirar productor/consumidores PDF y dejar de emitir `internal_type=pdf`. V0047
es expand-only y puede permanecer sin productores; no reescribir migraciones ya
aplicadas.
