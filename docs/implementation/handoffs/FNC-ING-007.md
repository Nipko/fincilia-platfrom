---
task: FNC-ING-007
status: REVIEW_PENDING
base_sha: ea3c938
implementation_sha: e4e7dfd
data_ceiling: synthetic_only
gate_effect: none
independent_review: pending
---

# Handoff FNC-ING-007 — OCR local aislado

## Resultado

Los PDF sintéticos escaneados recorren admisión segura, OCR local, inspección
integral, promoción direccionada por contenido, perfil, extracción y acceso al
mapeo web. Tesseract y PDFium viven dentro del worker sin egress. El texto OCR
solo se almacena en un derivado canónico; PostgreSQL y la API exponen metadatos,
conteos, versión y localizadores, nunca el contenido reconocido.

V0062 agrega `pdf_ocr_result`, los vínculos compuestos al artefacto/ejecución y
el localizador `pdf_ocr`. V0063 permite únicamente al migrador mantener esos
metadatos bajo `FORCE RLS`; la aplicación no obtiene privilegios nuevos y el
worker conserva solo lectura/inserción company-scoped.

## Evidencia reproducible

| Superficie | Resultado |
|---|---|
| OCR/worker | 36 pruebas, OK; incluye Tesseract real sobre PDF raster sintético |
| API completa | 205 pruebas, OK |
| PostgreSQL focal | 4 pruebas, OK; RLS, ACL, cruce de empresa y localizador tipado |
| Migraciones | V0062/V0063 aplicadas; replay sin aplicaciones ni mutación, head V0063 |
| Web | lint, typecheck y 298 pruebas, OK |
| Navegador | PDF raster nuevo, OCR, perfil, acceso a mapeo y Axe, OK |
| Contratos | migration readiness, runtime config y workspace, OK |
| Índice Git | quality gate sin hallazgos |

La corrida integral PostgreSQL ejecutó 420 casos: 416 pasaron y cuatro casos
anteriores revelaron contaminación de estado/orden (limpieza de intentos de
notificación, dos fixtures con schema digest reutilizado y una búsqueda de
auditoría). Los cuatro quedan separados de esta entrega; las pruebas focales de
OCR y las suites completas de API/worker/web pasan.

## Seguridad, privacidad y límites

- El escaneo de secretos recorre todos los bloques aunque se haya alcanzado el
  máximo de hallazgos persistibles.
- Los límites de páginas, píxeles, tiempo, salida y memoria fallan cerrados.
- Un derivado con digest divergente nunca se perfila ni extrae.
- No se agregó proveedor externo, IA, decisión financiera, auto-match ni
  autorización de datos reales.
- La transcripción de tablas escaneadas es mapeable, pero la reconstrucción de
  columnas complejas requiere calibración futura con corpus autorizado.

Revisión independiente pendiente: Security, Privacy, Data, Architecture,
Database y QA. CI sobre el commit integrado también permanece pendiente.

## Rollback

Configurar `FINCILIA_OCR_PROVIDER=disabled` y volver al worker anterior. Las
migraciones son expand-only y permanecen instaladas sin productores. No borrar
ni reescribir V0062/V0063.
