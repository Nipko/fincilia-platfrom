---
task: FNC-GOV-001
correction_of: docs/implementation/handoffs/FNC-GOV-001.md
status: BLOCKED_HUMAN
base_sha: c337fa4
correction_sha: see_git_commit_containing_this_handoff
implementer: Integration Steward
data_used: none
gate: S1-READY_not_met
---

# Corrección de handoff FNC-GOV-001

## Hecho corregido

La indicación de que «una sola persona hará varios roles» describe el uso de la
aplicación durante pruebas: una persona física necesita recorrer capacidades de owner,
preparer, reviewer y auditor mediante identidades o contextos sintéticos.

No asigna al Founder como Integration, Product, Accounting, Architecture, Security,
Privacy y Legal. Por tanto, el handoff original y los commits `c65a810`, `b6455b6` y
`c337fa4` no son estado de gobierno vigente.

## Estado restaurado

- Los siete owner slots humanos vuelven a `UNASSIGNED`.
- FNC-GOV-001 vuelve a `Blocked: founder`.
- Las diez decisiones humanas permanecen `pending_human` en sus contratos fuente.
- S1-READY continúa `not_met` y no se reclama el avance 36/40 medido bajo la
  interpretación incorrecta.
- El modelo y validador `founder-governance` se retiran para que ninguna herramienta
  pueda consumir esa interpretación.

## Diseño correcto para las pruebas de aplicación

Una persona física puede controlar varias **personas sintéticas locales** —por ejemplo,
preparador, revisor, auditor y owner— mediante un selector exclusivo del entorno local.
Cada persona conserva un `subject_id` distinto y la API continúa resolviendo permisos
server-side. Esto permite probar el recorrido completo sin debilitar estas reglas:

1. La misma identidad técnica no propone y confirma su propia conciliación.
2. La misma identidad técnica no prepara y aprueba su propio cierre.
3. Cambiar de persona deja una sesión y un actor auditables.
4. El selector no existe ni se habilita en producción.

La implementación del selector pertenece a una tarea de aplicación/QA independiente,
no a FNC-GOV-001.

## Verificación

```text
python -m tools.work_graph.validate
python -m unittest tools.work_graph.test_validate -q
python -m tools.quality_gate.cli   # sobre el índice Git
```

## Historial

No se reescribió ni borró el handoff entregado: esta corrección append-only lo
supersede. Los commits erróneos se conservan para auditoría y se neutralizan con el
commit correctivo.
