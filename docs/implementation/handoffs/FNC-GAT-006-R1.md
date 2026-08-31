---
id: FNC-GAT-006
status: REVIEW_PENDING
base_sha: 02efca9
data_ceiling: synthetic_only_until_DRG-01
---

# Corrección R1 — evidencia canónica entre plataformas

## Defecto demostrado

La evidencia adjudicada calculaba SHA-256 sobre bytes del working tree. Un
checkout Windows con CRLF producía un manifiesto distinto al checkout LF de
GitHub Actions, aunque el contenido fuente fuese el mismo. CI rechazó
correctamente `FNC-GAT-006.json`.

## Corrección

Las fuentes declaradas, todas textuales UTF-8, se normalizan a LF antes de
calcular el digest. Se añadió una prueba que exige el mismo SHA para una fuente
LF y CRLF, y se regeneró el manifiesto canónico. No se relajó ningún selector,
control, prueba PostgreSQL ni límite de datos.

## Verificación

- Evidencia técnica: digest `a4e69c80...fe38b`, 90 pruebas adjudicadas.
- Suite focal: 25 pruebas entre DRG-01, técnica y derechos/incidente, OK.
- Readiness: modelo válido, 14 blockers, datos reales denegados.

## Pendiente

Revisión independiente Security/Database/QA. Esta corrección no mueve DRG-00 ni
DRG-01.
