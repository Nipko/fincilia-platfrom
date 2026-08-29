# Runtime aislado DRG-00

FNC-PLT-004 materializa el diseño de FNC-SEC-003 sin habilitar datos reales.
`quarantine` y `processing` se prueban en contenedores con `network none`, sin
puertos, sin capacidades, como UID 65532 y con filesystem raíz read-only. El
pull está deshabilitado durante el ensayo.

El controlador exige manifiesto sintético, grant company-scoped vigente,
política de borrado efectiva y un scanner disponible. Intake siempre escribe en
cuarentena. Solo CSV/XLSX/ODS completamente inspeccionables pueden promocionarse;
los demás formatos y cualquier fallo permanecen cerrados.

El laboratorio implementa inventario encadenado, auditoría allowlisted,
derivados digest-only, backup, tombstone previo al unlink, purga reconciliada,
restore cerrado y destrucción final. La admisión de workloads reales exige
digest, firma y procedencia verificadas; la release actual no se presenta como
admitida.

El runtime es evidencia técnica para revisión. A-02, L-01, tratamiento,
procedencia y revisores humanos distintos del Founder continúan bloqueando
DRG-00 y mantienen `real_data_authorized=false`.
