---
id: FNC-ING-006
title: Ingesta PDF segura y OCR desacoplado
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 682e609
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Privacy, Data, Architecture, QA]
---

# Resultado esperado

Inspeccionar PDF en worker aislado, extraer texto embebido seguro por página y
producir un workspace revisable. Documentos activos, cifrados, ambiguos o sin
texto suficiente permanecen en cuarentena o `ocr_required`.

# Criterios de aceptación

Detección por firma, límites de bytes/páginas/objetos, rechazo de contenido
activo, salida versionada con coordenadas y confianza, cero publicación directa,
revisión humana, linaje exacto y pruebas adversariales. OCR externo permanece
desactivado hasta configuración final.

# Evidencia de implementación

V0047 amplía el localizador autoritativo con `pdf_text`. El worker fijado a
`pypdf 6.16.2` inspecciona la envolvente completa, niega contenido activo,
cifrado, firmado o ambiguo y limita bytes, páginas, objetos y bloques. Un PDF
pasivo con texto embebido produce bloques por página con caja normalizada,
confianza, digest y revisión humana obligatoria; uno sin texto queda
`ocr_required` en cuarentena. `DisabledOcrPort` impide cualquier transmisión
externa antes de la adjudicación final.
