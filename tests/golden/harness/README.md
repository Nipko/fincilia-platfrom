# Fixtures del golden harness

- Tarea: FNC-QA-003
- Clasificación: `synthetic_only`
- Procedencia: creados desde cero para este harness; no derivan de ningún documento real.

Estos fixtures existen para que el harness pueda ejercitar de extremo a extremo la
adjudicación de inputs, el oráculo estructurado y la allowlist de módulos sin depender de
otro validador.

`MANIFEST.json` inventaría cada fichero con su SHA-256. Un fichero sin entrada en el
manifiesto, o con digest distinto, hace fallar `python -m tools.golden_harness.cli verify`.

Los dominios usados son reservados por RFC 2606 (`example.invalid`). No hay correos, NIT,
cuentas, tokens ni identificadores de personas o empresas reales.

**No se modifican los cinco fixtures de FNC-DAT-002 bajo `tests/golden/synthetic/`.**
