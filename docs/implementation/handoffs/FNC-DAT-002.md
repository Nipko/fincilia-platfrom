---
task: FNC-DAT-002
status: REVIEW_PENDING
base_sha: cef09d5
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-DAT-002

## Entrega

- Generador determinista Python 3.12 sin dependencias externas.
- Linter fail-closed de procedencia, inventario e integridad.
- CLI `generate`, `lint` y `verify`.
- Cinco fixtures golden y su manifiesto SHA-256.
- Doce pruebas positivas/negativas.
- Documentación de cobertura, regeneración y límites.

## Rutas

- `tools/synthetic_corpus/**`
- `tests/golden/synthetic/**`
- `docs/testing/SYNTHETIC_CORPUS.md`
- `docs/implementation/handoffs/FNC-DAT-002.md`

## Verificación ejecutada

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app' && python3 -m unittest tools.synthetic_corpus.test_corpus -v"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app' && python3 -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic"
```

Resultado observado:

- `unittest`: 12/12 PASS.
- `verify`: 5 archivos revisados, 0 errores.
- Advertencias: 2 `DAT-INERT-FORMULA-CELL`, ambas esperadas en el fixture hostil.
- Regeneración: bytes idénticos para versión/seed golden.

Los tiempos son evidencia funcional local, no benchmark.

## Casos negativos materializados

- manifiesto ausente;
- alteración de hash;
- clasificación real/derivada;
- `synthetic=false`;
- `real_data_used=true`;
- input externo declarado;
- dominio no reservado aun con hash actualizado;
- archivo no inventariado;
- symlink no inventariado;
- decodificación Latin-1 distinta de UTF-8.

## Riesgos y decisiones pendientes

- Privacy y Accounting deben revisar clasificación, escenarios y lenguaje antes de aceptar.
- El manifiesto es v1 documental/código; aún no tiene JSON Schema compartido.
- El corpus tabular es deliberadamente pequeño y no representa prioridad de formatos productivos.
- FNC-PLT-003 debe ejecutar `verify` en CI y proteger el resultado contra bypass.
- FNC-QA-003 ampliará el golden harness cuando existan modelos canónicos aceptados.

## Rollback

Todo el entregable es sintético y eliminable. Retirar las cuatro rutas anteriores no requiere migración ni purga de datos reales.

No se recibió, transformó, consultó ni almacenó información real. Esta entrega no supera S1-READY ni autoriza DRG-00.
