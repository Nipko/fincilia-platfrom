---
task: FNC-GAT-008
status: REVIEW_PENDING
base_sha: 6ff3d64
implementation_sha: 7af724f
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-008 — estado funcional web

## Resultado

Doce dominios y cien puntos ponderados producen tres medidas distintas:

- implementacion funcional: 88 %;
- aceptacion sintetica: 59 %;
- operabilidad de produccion: 28 %.

Mobile queda expresamente fuera del denominador. Los factores estan versionados
y el validador recalcula el resultado; una edicion manual del porcentaje, un
archivo de evidencia ausente o un intento de declarar producción con GA cerrado
hacen fallar el contrato.

## Lectura correcta

El 88 % significa amplitud construida en `main`, no despliegue ni precision
contable real. El 59 % refleja E2E sintetico y componentes externos apagados. El
28 % refleja que diseño/pruebas no sustituyen observabilidad, restore, pentest,
proveedores ni aprobacion de gates.

## Verificacion

- `python -m unittest tools.web_functional_status.test_model -v`: 10, OK.
- `python -m tools.web_functional_status.cli`: inventario valido y porcentajes
  reproducidos.
- `python -m tools.quality_gate.cli`: cero hallazgos sobre el indice.

## Revision y rollback

Product y Accounting deben revisar pesos y semantica; QA, las evidencias. Ningun
porcentaje mueve DRG-00, DRG-01 o GA-01. Revertir `7af724f` retira exclusivamente
el inventario y su herramienta.
