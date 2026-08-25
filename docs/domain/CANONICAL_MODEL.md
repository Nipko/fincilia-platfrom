# Modelo canónico v0.1 — fuentes, evidencia y finanzas

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-002 |
| Estado | Review pending |
| Gate | S1-READY |
| Owners requeridos | Architecture + Accounting |
| Revisores | Data Engineering + Security |
| Datos autorizados | Exclusivamente sintéticos |
| Modelo ejecutable | `docs/domain/canonical-model.json` |

Este contrato fija significado, ownership y reglas de persistencia. No es una migración ni el esquema SQL final. FNC-DOM-003 completa balances/completitud; DOM-004, dedupe/idempotencia; DOM-005, linaje/overlays/engine release. Ninguna tarea posterior puede convertir observaciones incompletas en hechos o relajar aislamiento/dinero exacto.

## 1. Fronteras conceptuales

```text
fuente configurada
  → artefacto/versión inmutable
  → documento y extracción fiel
  → dataset versionado
  → source_record (observación publicada)
  → movement_evidence_link
  → money_movement (hecho económico)
  → settlement / ledger / balance
```

Una carga exitosa solo demuestra recepción. Un `source_record` sigue siendo evidencia de una fuente; no adquiere identidad económica por estar tipado. Un `money_movement` puede reunir varias evidencias, y dos movimientos legítimos idénticos deben coexistir.

## 2. Tipos lógicos

| Tipo | Persistencia objetivo | Regla |
|---|---|---|
| `uuid` / `uuid_v7` | UUID | ID de aplicación; no codifica tenant |
| `money_decimal` | NUMERIC(38,12) o precisión aprobada equivalente | Nunca float; representación JSON como string |
| `currency_code` | CHAR(3)/dominio | ISO 4217 mayúscula; no inferir silenciosamente |
| `direction` | enum | `inflow`/`outflow` desde una cuenta declarada |
| `instant` | timestamptz | UTC; conserva timezone/offset original aparte |
| `local_date` | date | Fecha civil con semántica nombrada |
| `sha256` | bytes/hex validado | Hash exacto; no identidad económica |
| `json_document` | JSONB validado | Schema ref y límite de bytes obligatorios |
| `object_reference` | key/version opacos | El binario vive en object storage |
| `tokenized_identifier` | token/last4 | No almacena PAN ni credencial ni cuenta completa en claro |

Los importes normalizados son no negativos. La perspectiva se expresa con `direction`; en libro se usa `debit_credit`. El texto/signo original permanece en evidencia/linaje, nunca se descarta para “normalizar”.

## 3. Fechas diferentes

| Campo | Significado |
|---|---|
| `occurred_at` | instante económico observado |
| `posted_at` | instante de registro/publicación por la fuente |
| `value_date` | fecha de valor usada por la institución |
| `accounting_date` | fecha contable asignada o confirmada |
| `settled_at` | instante de liquidación |
| `issued_on` / `due_on` | emisión y vencimiento de obligación |

No se rellenan fechas faltantes copiando otra semántica. Toda inferencia queda como propuesta con origen, versión y confianza; las fechas ambiguas requieren confirmación.

## 4. Capas y entidades

### 4.1 Sources/control

- `data_source`: origen lógico por company, familia y finalidad.
- `source_expectation`: universo/frecuencia/cuenta/periodo esperado; no prueba completitud.
- `reference_dataset_version`: TRM, festivos, monedas o tarifas versionadas; nunca “dato actual” mutable.

### 4.2 Evidencia e ingesta

- `source_artifact`: recepción lógica por canal.
- `artifact_version`: bytes/payload exactos, hash y object version; nombre/extensión no son confiables.
- `document`: unidad semántica dentro de una versión.
- `processing_run`: intento reproducible con input y `engine_release`.
- `raw_record`: extracción fiel con localizador y texto original.
- `dataset_version`: resultado inmutable de extracción/receta/esquema.
- `source_record`: observación publicada desde dataset/fuente; no es movimiento económico.

### 4.3 Finanzas

- `counterparty`: contraparte company-scoped, con identificadores minimizados/versionados.
- `financial_account`: cuenta desde cuya perspectiva se define dirección; identificador tokenizado/last4.
- `obligation`: factura/nota/pedido u obligación con gross/tax/withholding/open balance.
- `money_movement`: entrada/salida económica con importe positivo, moneda, cuenta y fechas separadas.
- `movement_evidence_link`: vínculo N:M entre movimiento y observaciones, sin borrar evidencia.
- `settlement`: ecuación bruta→fee/impuesto/retención/refund→neto y payout asociado cuando existe.
- `ledger_entry` y `ledger_line`: asiento y líneas débito/crédito; la suma se valida por moneda.
- `account_balance`: observación de saldo por cuenta/instante/fuente.
- `external_reference`: namespace/valor/issuer ligado a un target; una referencia blanda no crea unicidad.

### 4.4 Conciliación y completitud

- `completeness_assessment`: evaluación inmutable de expectativa, dataset,
  fuente, cuenta opcional y periodo; un control requerido ausente deriva
  `unknown`, nunca un éxito implícito.
- `completeness_control_result`: resultado tipado, versionado y respaldado por
  evidencia de cada control evaluado.
- `reconciliation_statement`: versión reproducible de la ecuación banco,
  partidas confirmadas y libros, con diferencia no explicada explícita.
- `reconciling_item`: decisión append-only con monto positivo, lado explícito,
  evidencia, preparador y aprobación independiente cuando se confirma.

## 5. Company scope y claves foráneas

- Toda entidad financiera tiene `company_id NOT NULL` e inmutable.
- Una FK entre entidades company-scoped incluye `(company_id, target_id)`.
- El servidor deriva company desde el recurso; el cliente no la autoriza.
- No hay `ON DELETE CASCADE` desde company hacia evidencia o finanzas.
- Cambiar de firma modifica engagement/grants, nunca `company_id` de los hechos.
- IDs UUIDv7 no llevan organization/company embebida y no prueban acceso.

La unicidad de cada ID company-scoped se materializa conceptualmente como `(company_id, id)`, además del ID técnico que defina la migración.

## 6. Idempotencia y dedupe

Claves duras permitidas:

- artefacto exacto: company + source + SHA-256;
- webhook/API: connection + provider event ID estable;
- ejecución: input version + engine release + receta/esquema;
- external reference declarada `provider_stable` dentro de su namespace/issuer/scope.

No son claves duras:

- fecha;
- monto;
- dirección;
- referencia visible;
- contraparte;
- combinación de esos campos.

Esos atributos generan `dedupe_candidate`. Un merge requiere decisión versionada y evidencia; nunca elimina el `source_record`. DOM-004 concreta candidatos, decisiones y pruebas de concurrencia.

## 7. Settlement y exactitud monetaria

La ecuación base es:

```text
gross_amount
  - fee_amount
  - tax_amount
  - withholding_amount
  - refund_amount
  + adjustment_amount
  = net_amount
```

Todos los componentes son decimales no negativos salvo `adjustment_amount`, cuya dirección/signo se modela explícitamente. Si la fuente no desglosa un componente, permanece desconocido; no se fuerza cero para cuadrar.

`settlement` no demuestra abono bancario. `payout_movement_id` es una relación opcional y revisable hasta que exista evidencia/decisión adecuada.

## 8. Ledger y balances

- `ledger_entry` agrupa líneas; no almacena un único “monto del asiento”.
- Cada `ledger_line` usa amount positivo y `debit_credit` explícito.
- Balance del asiento se calcula por moneda; no se ocultan diferencias por redondeo implícito.
- `account_balance` conserva `balance_type`, fecha/instante, moneda, cuenta y fuente.
- Un saldo observado no convierte una fuente en completa.
- Matches de movimientos no prueban conciliación de saldos.

DOM-003 fija `completeness_assessment`, resultados de control,
`reconciliation_statement`, partidas conciliatorias y el gate de diferencia no
explicada. Sus inputs se versionan; una nueva evaluación o decisión agrega una
versión y nunca reescribe el estado que sustentó un resultado anterior.

## 9. JSON, bytes y referencias

- Binario/payload grande vive en object storage y PostgreSQL guarda referencia opaca/versionada.
- Todo `json_document` declara `schema_ref` y `max_bytes`; contenido libre no se indexa como contrato.
- No se almacenan credenciales, PAN, CVV ni secretos dentro de JSONB.
- `source_payload` es evidencia acotada, no escape para evitar modelar campos esenciales.
- Los nombres originales y textos financieros no entran a logs.

## 10. Mutabilidad

| Política | Entidades típicas | Regla |
|---|---|---|
| `immutable_version` | artifact_version, dataset_version, source_record, reference_dataset_version, completeness_assessment, reconciliation_statement | Corregir crea nueva versión |
| `append_only` | processing_run, movement_evidence_link, reconciling_item, external_reference | Revocar/supersede, no reescribir historia |
| `controlled_state_machine` | source_artifact, document, money_movement, settlement, ledger_entry | Solo comando/transición auditada |
| `mutable_master_versioned` | data_source, source_expectation, counterparty, financial_account | Cambios relevantes generan versión/audit |

Obligation y balances conservan revisiones; reducir `open_amount` no edita la evidencia que originó el valor.

## 11. Clasificación y linaje

- Metadatos técnicos mínimos: `internal`.
- Identidad/configuración: `confidential`.
- Evidencia, movimientos, saldos, obligaciones y ledger: `financial_sensitive`.
- Secretos: solo vault/reference; `prohibited` no entra al modelo.
- Todo campo publicado en `source_record` y todo hecho financiero exige linaje a evidencia versionada.
- `engine_release_id`, canonical schema version y reference data version forman parte de reproducibilidad.

DOM-005 materializa localizadores y aristas; este contrato ya prohíbe publicar sin esa obligación.

## 12. Invariantes ejecutables

El JSON y su validador exigen:

1. ownership único y compatible con el modelo modular;
2. company scope y FK compuestas;
3. decimal exacto, moneda/dirección y fechas semánticas;
4. separación `source_record`/`money_movement` + evidence link;
5. dedupe fingerprint no único;
6. bytes fuera de PostgreSQL y JSON acotado;
7. account identifiers tokenizados;
8. mutabilidad declarada;
9. clasificación válida y ausencia de `prohibited`;
10. linaje/release requeridos en resultados publicados.

## 13. Decisiones abiertas

- Precision/scale SQL final y política de redondeo por moneda: Accounting/DOM-002 review.
- Constraints/migraciones y el índice parcial de operador primario: Database Migration Owner.
- Completeness/balance statement: DOM-003.
- Dedupe candidate/merge/idempotencia bajo concurrencia: DOM-004.
- Origin locator, overlays, engine release executable: DOM-005.
- Retención/borrado: PRV-001/L-01.
- Catálogos fiscales/contables: Accounting y reference data versionada.

## 14. Verificación y estado

```powershell
python -m tools.canonical_model.validate
python -m unittest tools.canonical_model.test_validate -v
```

Este artefacto permanece `Review pending` hasta revisión independiente de Architecture, Accounting, Data Engineering y Security. No es esquema productivo, no supera S1-READY y no autoriza datos reales.
