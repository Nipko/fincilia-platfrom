# ADR-036 — PDF seguro y OCR desacoplado

- Estado: **Proposed; parser local sintético primero**
- Fecha: 2026-08-31
- Tarea: FNC-ING-006
- Owners: Data + Security + Privacy, accountable FOUNDER-01
- Gates: DRG-00, DRG-01

## Decisión propuesta

- PDF continúa entrando por cuarentena y se procesa únicamente en el worker
  aislado definido por ADR-001.
- La primera capacidad admite PDF estructuralmente seguro y extrae texto ya
  embebido sin JavaScript, acciones, adjuntos, formularios activos, cifrado,
  firmas dinámicas, URLs ni contenido ambiguo.
- Una capa de normalización produce páginas, bloques y celdas candidatas con
  coordenadas, confianza y digest; nunca publica movimientos directamente.
- Un documento sin texto suficiente queda `ocr_required`. No se inventa texto ni
  se promociona silenciosamente.
- OCR local y OCR externo implementan el mismo port. El externo solo puede
  activarse detrás del AI Gateway de ADR-009, con política por empresa,
  minimización, presupuesto, DPA y egress adjudicado.
- Toda extracción exige revisión humana antes de mapear o publicar.

## Configuración pendiente para el final

Proveedor OCR administrado, región, límites por página/costo, idiomas y política
de conservación del texto OCR. Hasta entonces solo se habilita el camino local
determinístico y sintético.

