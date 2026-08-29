---
task: FNC-QA-001
status: REVIEW_PENDING
supersedes_handoff_only: docs/implementation/handoffs/FNC-QA-001.md
implementation_shas: [64242d3, 8fd6ac2, 46d57a3]
tested_head_sha: 46d57a3025d7402c7a90b4cb7e8002c50bc02a68
data_ceiling: synthetic_only
---

# Correccion del handoff FNC-QA-001

El primer handoff no incluia la ejecucion en un runner GitHub vacio. Dos fallos
de CI se corrigieron sin relajar el laboratorio:

1. CI precarga exactamente
   `python:3.12@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134`;
   la sonda conserva `--pull never` y `--network none`.
2. La CLI puede escribir la evidencia fuera del repositorio sin revelar la ruta
   del host en su resumen. El contenido sigue siendo byte-a-byte identico al
   artefacto adjudicado.

El workflow `33257678962` termino `success` sobre `46d57a3`: migraciones,
parser/eventos, RLS/worker, politica del repositorio y lifecycle local pasaron.
LAB-T01..T12 se reprodujeron 12/12 y el digest interno permanecio
`7f17c320cadae9c4f2287af0d9e721993e453ed69b609c82c372bfb3dda1ee47`.

Esto cierra la evidencia tecnica del drill, no DRG-00. Legal, retencion, region,
entorno objetivo y revision independiente siguen pendientes.
