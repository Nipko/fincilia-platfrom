# Solicitud nominal de adjudicación DRG-00

Estado: `pending_independent_review` · Fecha del paquete: 2026-08-29.

La implementación técnica ya produce evidencia reproducible, pero DRG-00 no
puede abrirse sin completar dos controles técnicos y cuatro adjudicaciones
humanas. `FOUNDER-01` es accountable y autor de integración; no puede ocupar
ninguno de los slots independientes.

## Evidencia para revisar

- `docs/implementation/evidence/FNC-QA-001.json`: doce controles sintéticos.
- `docs/security/DRG00_LAB_RUNTIME.md`: aislamiento y límites del runtime.
- `docs/security/DRG00_CORPUS_INVENTORY.md`: inventario minimizado.
- `docs/privacy/DRG00_DISPOSAL_RUNBOOK.md`: borrado y restore.
- `docs/legal/TREATMENT_AGREEMENT_TEMPLATE.md`: paquete Legal.
- `docs/privacy/RETENTION_DELETION_MATRIX.md`: matriz L-01.
- `docs/architecture/REGION_TRANSMISSION_DECISION.md`: paquete A-02.

## Firmas que faltan

| Control | Decisión | Revisor nominal requerido | Estado |
|---|---|---|---|
| G00-LEGAL | Tratamiento/finalidad y aplicabilidad contractual | Abogado colombiano o Privacy independiente | Pendiente |
| G00-RETENTION | Plazos, eventos iniciales, backup y delete ledger L-01 | Legal + Privacy; Accounting para reloj financiero | Pendiente |
| G00-REGION | AWS `sa-east-1`, transmisión y subencargados para corpus | Legal/Privacy independiente y Architecture/Security | Pendiente |
| G00-INDEPENDENT-REVIEW | Dictamen consolidado de alcance, riesgos y evidencia | Legal y Security distintos de `FOUNDER-01` | Pendiente |

## Controles técnicos que faltan

| Control | Condición verificable | Estado |
|---|---|---|
| G00-SUPPLY-CHAIN | SBOM, firma, provenance y origen verificados contra raíz de confianza | Pendiente |
| G00-ISOLATED-ENV | Release admitida, IdP administrado y repetición del drill en el entorno objetivo | Pendiente |

Cada aceptación debe registrar identificador profesional estable, fecha,
alcance, evidencia revisada y condiciones. No se almacenan documento de
identidad, firma manuscrita, correo, matrícula ni secreto en el repositorio.

Hasta completar los cuatro controles, el resultado correcto es
`DRG-00: not_met`, `data_ceiling: synthetic_only` y
`real_data_authorized: false`.
