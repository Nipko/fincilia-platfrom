---
id: FNC-QA-011
title: Aislamiento determinista de la suite PostgreSQL integral
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: c16e60d
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [QA, Database]
---

# Resultado esperado

Eliminar dependencias de orden y residuos entre las pruebas PostgreSQL que
ejercitan notificaciones y el recorrido vertical de documentos. Una corrida
integral debe procesar el artefacto recién creado hasta quiescencia y retirar
tablas hijas antes que sus padres, sin relajar ninguna restricción productiva.

# Rutas reservadas

- `db/tests/test_operational_reminders.py`
- `db/tests/test_p3_vertical.py`
- `db/tests/test_billing_plans.py`
- `infra/local/reset-empty.sh`
- `tools/local_stack/model.py`
- `tools/local_stack/test_validate.py`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Criterios de aceptación

1. La limpieza de notificaciones respeta las FK de feedback, intentos,
   entregas e intenciones en ese orden y permanece company-scoped.
2. El arnés vertical drena la cola global hasta quiescencia con un límite
   explícito y falla ruidosamente si lo agota.
3. Las lecturas que generan auditoría comprueban primero la respuesta HTTP, de
   modo que una preparación incompleta no se confunda con falta de auditoría.
4. Las pruebas focales y la suite PostgreSQL completa pasan en un esquema
   migrado, con almacenamiento de objetos real y sin consumidores concurrentes.
5. El caso de Stripe deshabilitado envía primero un contrato HTTP válido, y el
   reset vacío verifica las versiones legales canónicas activas para registro.
6. No se cambia código productivo, migraciones, RLS, permisos ni semántica
   financiera.

# Límites y rollback

Solo fixtures completamente sintéticas. Revertir la tarea restaura únicamente
el arnés de pruebas y sus registros; no requiere migración ni manipulación de
datos productivos. QA y Database conservan revisión independiente pendiente.
