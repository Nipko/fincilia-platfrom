---
task: FNC-RPT-001
status: REVIEW_PENDING
base_sha: 1211f17
tested_head_sha: a18afcf
implementation_commits: [daf852a, 3bb4ec8, 5df883c, 5aa913a, f7c637d, a18afcf]
data_ceiling: synthetic_only
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado

Centro web de informes operativos e historicos para el portafolio de un
contador. Consulta cada empresa con autorizacion y RLS propias, permite rangos
UTC de 30, 90, 180 o 365 dias y presenta documentos, datasets, filas,
conciliaciones, calidad, actividad mensual e importes publicados por moneda.
La misma serie monetaria se exporta como CSV determinista.

No es un balance, cierre ni informe certificado. No consolida importes entre
empresas o monedas, no decide conciliaciones y permanece restringido a datos
sinteticos.

# Implementacion

- `report.read` y `report.export` estan en el contrato final de roles. La
  empresa siempre se resuelve en servidor y cada consulta corre con su contexto
  PostgreSQL company-scoped.
- Solo alimentan la serie monetaria datasets publicados, verificados, con
  completitud y linaje validos. El dinero sale de `numeric(38,12)` como cadenas
  de doce decimales; no atraviesa `float`.
- La vista multiempresa consulta company-by-company con concurrencia maxima de
  tres y solo agrega conteos operativos. Cada importe conserva su empresa y
  moneda.
- La interfaz ofrece filtros, resumen de portafolio, alertas de completitud,
  grafico de actividad, tabla monetaria exacta, datasets recientes y enlaces a
  evidencia. El CSV pasa por un BFF con token httpOnly y limite de respuesta.
- La auditoria registra rango y numero de filas de serie; una prueba contra la
  base demuestra que no guarda importes, monedas, movimientos ni IDs de
  dataset.

# Evidencia ejecutada

- Contrato de tenancy: 19 pruebas enfocadas OK.
- API: 106 pruebas unitarias OK.
- PostgreSQL 17 + MinIO: 2 recorridos OK, incluidos RLS cross-tenant, permisos,
  decimal exacto, CSV y contenido cerrado de auditoria.
- Web: typecheck/build de produccion y lint OK; 155 pruebas unitarias OK.
- Navegador: 1 recorrido E2E Chromium y 1 analisis Axe automatizado OK.
- `tools.work_graph.validate` y `tools.quality_gate.cli`: OK, cero hallazgos.
- GitHub Actions `fincilia-ci` se verifica sobre el commit final de integracion;
  el resultado del proveedor es parte de la entrega del Integration Steward.

# Limites y revision requerida

No hubo migraciones ni dependencias nuevas. La grafica muestra conteos, no
importes; la tabla exacta es la representacion accesible del volumen monetario.
No se habilito IA, dato real, balance, cierre, certificacion o agregacion
financiera del portafolio.

Product/Accounting debe revisar significado y lenguaje; Security, RLS,
auditoria y exportacion; Backend/Architecture, consultas y limites;
Accessibility/QA, el recorrido visual. Ninguna revision fue autoaceptada y este
handoff no mueve S1-READY, DRG-00, DRG-01 ni ADR-002.

# Rollback

Revertir en orden: consumidores web, BFF, rutas/API y finalmente permisos de
contrato. No hay esquema que compensar ni datos que migrar. Revocar la
navegacion web no altera la fuente de verdad financiera.
