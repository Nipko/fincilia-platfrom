# ADR-004 — Object storage por zonas de evidencia

- Status: Accepted; retention pending L-01
- Date: 2026-08-21
- Owners: Architecture + Security + Privacy, accountable FOUNDER-01
- Gates: S1-READY, DRG-00
- Plan refs: §23.1

## Decision

Zonas:

~~~text
quarantine
raw
extracted
curated
exports
audit
temporary
~~~

- Bucket/cuenta por ambiente y namespace opaco por company.
- Hash, versioning, cifrado y acceso privado.
- Todo acceso a evidencia fija version_id.
- Raw aceptado es inmutable; correcciones crean derivados/versiones.
- Exports y temporary tienen TTL.
- Object Lock protege una versión, no una key.

## Consequences

Reproducibilidad y aislamiento claros a cambio de lifecycle, inventario y costos. MinIO local no demuestra WORM/Object Lock productivo.

## Verification

Promoción controlada quarantine→raw, URLs cortas, inventario de versiones y rechazo cross-company.
