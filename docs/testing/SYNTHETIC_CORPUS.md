# Corpus golden completamente sintético

| Campo | Valor |
|---|---|
| Tarea | FNC-DAT-002 |
| Estado | Review pending |
| Clasificación | `synthetic_financial_sensitive` |
| Generador | `fincilia-synthetic-corpus` 1.0.0 |
| Seed golden | `FNC-DAT-002-SEED-001` |
| Datos reales usados | No |
| Gate que habilita | Ninguno por sí solo |

## 1. Propósito

Este corpus proporciona evidencia reproducible para probar parsers, perfiles, completitud y controles de seguridad sin recibir ni transformar información de clientes. Los fixtures se generan desde escenarios escritos deliberadamente para Fincilia; no proceden de datos anonimizados, saneados, copiados o observados.

La etiqueta `synthetic: true` no se considera prueba suficiente. La comprobación combina:

1. generador versionado y determinista;
2. seed bajo namespace sintético;
3. inventario exhaustivo;
4. hash SHA-256 y longitud por archivo;
5. clasificación y procedencia fail-closed;
6. regeneración byte a byte;
7. tests negativos contra alteración y origen dudoso.

## 2. Componentes

| Ruta | Responsabilidad |
|---|---|
| `tools/synthetic_corpus/generator.py` | Construye bytes y manifiesto deterministas |
| `tools/synthetic_corpus/linter.py` | Verifica inventario, procedencia, encoding, locale, hash y contenido inseguro |
| `tools/synthetic_corpus/cli.py` | Expone `generate`, `lint` y `verify` |
| `tools/synthetic_corpus/test_corpus.py` | Pruebas positivas y negativas del harness |
| `tests/golden/synthetic/manifest.json` | Manifiesto autoritativo de este corpus sintético |
| `tests/golden/synthetic/files/` | Fixtures generados; no se editan manualmente |

El generador no elimina archivos. Si el directorio contiene una ruta desconocida, se detiene para evitar sobrescribir o absorber material de procedencia dudosa. También rechaza destinos y archivos symlink.

## 3. Cobertura inicial

| Fixture | Locale/encoding | Caso | Resultado esperado |
|---|---|---|---|
| `bank_es_co.csv` | es-CO / UTF-8 | Saldo corrido y dos movimientos legítimos con misma fecha, monto y referencia | Aceptar evidencia; proponer duplicidad, nunca imponerla |
| `payments_en_us.csv` | en-US / UTF-8 | Bruto − fee − retención = neto con strings decimales exactos | Aceptar |
| `ambiguous_es_mx_latin1.csv` | es-MX / Latin-1 | Fecha `03/04/2026`, coma decimal y columna desconocida | Exigir confirmación |
| `hostile_cells.csv` | en-US / UTF-8 | Fórmula de hoja de cálculo y markup inertes | Tratar como texto y advertir; nunca ejecutar |
| `partial_statement.csv` | en-US / UTF-8 | Hueco de secuencia y evidencia de saldo incompleta | Marcar parcial y bloquear uso certificado |

Las monedas iniciales son COP y USD. Los identificadores usan prefijo `SYN-`; los contactos y enlaces usan dominios reservados `example.com`, `.test` o `.invalid`.

## 4. Contrato del manifiesto

El manifiesto contiene, como mínimo:

- `schema_version`, `corpus_id`, `policy_version`;
- `synthetic: true` y clasificación exacta;
- nombre, versión, source y seed del generador;
- método `deterministic_generation`;
- `real_data_used: false` y `external_inputs: []`;
- cobertura declarada;
- por archivo: path seguro, bytes, SHA-256, encoding, locale, delimitador, filas, tipo y estado esperado.

`lint` valida integridad local. `verify` añade una regeneración en memoria y compara cada byte; es el comando requerido para CI.

## 5. Uso

Desde la raíz del repositorio, con Python 3.12:

```bash
python3 -m tools.synthetic_corpus.cli generate --output tests/golden/synthetic
python3 -m tools.synthetic_corpus.cli lint --root tests/golden/synthetic
python3 -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic
python3 -m unittest tools.synthetic_corpus.test_corpus -v
```

En Windows con el runtime WSL configurado:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app' && python3 -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic"
```

## 6. Fallos y advertencias

El linter falla, entre otros, por:

- manifiesto ausente o inválido;
- clasificación distinta a sintética;
- indicio de dato real, derivado o input externo;
- generador/versión no allowlisted;
- seed fuera del namespace declarado;
- path inseguro, symlink, archivo faltante o no inventariado;
- bytes, hash o número de filas distintos;
- encoding, locale o delimitador no allowlisted;
- marcador sintético ausente;
- dominio de Internet no reservado.

Una celda que comienza con un prefijo de fórmula produce `DAT-INERT-FORMULA-CELL`. Es una advertencia intencional del fixture hostil; cualquier exportador posterior debe neutralizarla. El harness nunca evalúa celdas, fórmulas, XML o markup.

## 7. Cambio controlado

Para añadir un escenario:

1. modificar únicamente el generador;
2. añadir aserciones positivas y negativas;
3. incrementar la versión si cambian bytes o semántica;
4. regenerar;
5. ejecutar `verify` y tests;
6. obtener revisión independiente de Data, Privacy y Accounting.

No se corrige un fixture editando el CSV generado. No se copian ejemplos encontrados en Internet, documentos propios, capturas, exportaciones ni datos “anonimizados”. Una especificación pública puede orientar un formato solo después de documentar licencia y procedencia; no convierte contenido de terceros en sintético.

## 8. Límites

- Este corpus cubre tablas pequeñas; todavía no cubre XLSX, OFX, MT940, XML DIAN, PDF, imagen u OCR.
- No prueba desempeño, escalabilidad ni exactitud contable universal.
- Los hashes prueban integridad respecto del generador actual, no aprobación legal o contable.
- Los fixtures no habilitan DRG-00, DRG-01, piloto ni datos reales.
- La integración obligatoria en CI corresponde a FNC-PLT-003; este entregable deja el comando reproducible listo.
