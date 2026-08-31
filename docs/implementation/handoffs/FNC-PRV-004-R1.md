---
id: FNC-PRV-004
status: REVIEW_PENDING
base_sha: 02efca9
data_ceiling: synthetic_only_until_DRG-01
---

# Corrección R1 — digest reproducible del drill

## Defecto demostrado

El drill ligaba sus fuentes a los saltos de línea físicos del sistema operativo.
El manifiesto generado en Windows no coincidía con el checkout LF de CI.

## Corrección

Las seis fuentes textuales UTF-8 se canonicalizan a LF antes de calcular sus
SHA-256. Una prueba nueva enfrenta bytes LF y CRLF y exige identidad. La
evidencia fue regenerada con digest `33e595d4...983def`; conserva doce pasos,
`pending_legal`, cero datos reales y los mismos límites jurídicos.

## Pendiente

Repetir en el runtime AWS protegido y obtener revisión independiente
Privacy/Legal, Security y QA. No se aceptó plazo, notificación ni gate humano.
