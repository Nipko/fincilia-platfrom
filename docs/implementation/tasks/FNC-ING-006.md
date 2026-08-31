---
id: FNC-ING-006
title: Ingesta PDF segura y OCR desacoplado
status: proposed
implementer: Codex principal dev + Integration Steward
base_sha: pending_after_cls_006
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

