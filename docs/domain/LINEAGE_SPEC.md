# Especificación de linaje v0

- Estado: Seed
- Tarea: FNC-DOM-005
- ADR: ADR-005 y ADR-023

Origin locator identifica:

- artifact hash y version_id.
- página/hoja.
- fila, columna, celda o bounding box.
- tag XML o record API.
- parser/OCR/modelo y versión.
- receta, paso y overlay.
- campo canónico.

Lineage edge enlaza raw → extracted → clean → canonical → match/report/close.

## Invariantes

- El localizador original es inmutable.
- Una corrección crea overlay o nueva versión.
- Todo campo publicado tiene al menos un camino completo a evidencia.
- Toda decisión de match, excepción, saldo e informe referencia versiones.
- Engine release fija semver, commit, hash, SBOM y affects_results.
- Reprocesar crea dataset_version; no reescribe históricos.

