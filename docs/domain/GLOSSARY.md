# Glosario canónico v0

- Estado: Draftable
- Tarea: FNC-DAT-001
- Gate: S1-READY
- Datos autorizados: exclusivamente sintéticos
- Referencias del plan: §7, §15, §31 y §48
- Revisiones requeridas para aceptación: Accounting y Privacy

Este documento fija el vocabulario de datos para Fase 0. No sustituye el modelo
canónico ni concede permiso para recibir datos reales. Los nombres en código se
escriben en inglés; las etiquetas de interfaz pueden localizarse.

## 1. Distinciones obligatorias

Una fuente, un canal, una familia documental y un formato técnico son dimensiones
independientes:

~~~text
data_source
  --se recibe por--> ingestion_channel / connection
  --produce--> source_artifact
  --que contiene--> document de una document_family
  --serializado como--> technical_format
  --del que se extraen--> raw_record y source_record
  --que pueden evidenciar--> money_movement u otra entidad canónica
~~~

Ejemplo: `bank_account` es la familia de fuente; `web_upload` es el canal;
`bank_account_statement` es la familia documental y `pdf_native` es el formato.
`CSV`, `PDF`, `email` y `API` nunca identifican por sí solos el significado
financiero del contenido.

## 2. Identidad, tenancy y autorización

| Término | Nombre en código | Definición |
|---|---|---|
| Sujeto | `subject` | Persona lógica estable, independiente de sus credenciales, email o dispositivo. |
| Identidad | `user_identity` | Credencial OIDC/passkey asociada a un `subject`; no es identidad civil. |
| Organización | `organization` | Contenedor administrativo de una firma, BPO o PYME para membresías, billing y activos propios. |
| Empresa | `company` | Frontera financiera permanente. No cambia cuando cambia la firma contable. |
| Relación profesional | `engagement` | Delegación revocable, vigente y acotada de una organización hacia una empresa. |
| Permiso | `grant` | Autorización explícita por principal, empresa, recurso, acción, finalidad y vigencia. |
| Principal de servicio | `service_principal` | Actor no humano usado por una integración, job o programación. |
| Empresa activa | `active_company` | Empresa que cumple la definición contractual de procesamiento del periodo; no significa que la firma sea su propietaria. |

## 3. Origen, transporte y evidencia

| Término | Nombre en código | Definición |
|---|---|---|
| Fuente de datos | `data_source` | Origen lógico configurado para una empresa, cuenta, finalidad, frecuencia y periodo esperado. |
| Conexión | `connection` | Configuración técnica y autorización para acceder a una fuente. Conserva referencias a secretos, nunca el secreto en claro. |
| Expectativa de fuente | `source_expectation` | Declaración versionada de qué debe recibirse, para qué cuenta/periodo y con qué controles. |
| Canal de ingesta | `ingestion_channel` | Medio de recepción: web, móvil, email, SFTP, API, webhook o conector. No define semántica financiera. |
| Emisor | `issuer` | Entidad o sistema que produjo el contenido. Puede diferir del remitente o del transportador. |
| Procedencia | `provenance` | Evidencia sobre emisor, canal, autenticación, firma, hash, tiempo y cadena de recepción. |
| Artefacto fuente | `source_artifact` | Recepción lógica de un archivo, mensaje o payload. |
| Versión de artefacto | `artifact_version` | Binario/payload inmutable fijado por hash y `version_id`; el nombre original es metadato no confiable. |
| Documento | `document` | Unidad documental reconocida dentro de uno o más artefactos. Un ZIP o email puede contener varios documentos. |
| Familia documental | `document_family` | Clase semántica del contenido, independiente del formato y emisor. |
| Formato técnico | `technical_format` | Serialización detectada mediante firma/MIME/contenido, no solo extensión. |
| Plantilla | `document_template` | Estructura específica y versionada de emisor/familia/formato. No equivale a la familia documental. |
| Registro crudo | `raw_record` | Extracción fiel de una fila, bloque, tag o registro, conservando texto, locale y localizador. |
| Registro de origen | `source_record` | Evidencia estructurada y publicada desde una fuente. Sigue siendo una observación, no un evento económico deduplicado. |
| Versión de dataset | `dataset_version` | Resultado inmutable de extracción, receta, overlays y versión del esquema canónico. |
| Localizador de origen | `origin_locator` | Ubicación exacta: artefacto/versión, página/hoja, fila/columna/celda, caja, tag XML o registro API. |
| Arista de linaje | `lineage_edge` | Relación versionada que explica una transformación o dependencia entre valores/evidencias. |

## 4. Familias de fuente

Una instancia de `data_source` debe seleccionar una familia principal y puede
declarar capacidades adicionales. Las familias iniciales son:

| Código | Origen lógico | Contenido esperado | Observación |
|---|---|---|---|
| `bank_account` | Banco o cooperativa | Movimientos y saldos de una cuenta | Feed no se promete hasta B-01; archivo es fallback permanente. |
| `payment_gateway` | Pasarela de pago | Cobros, devoluciones, contracargos, fees y liquidaciones | Distinguir transacción del payout. |
| `merchant_acquirer` | Adquirente/datáfono | Ventas, comisiones, retenciones y abonos | Puede liquidar varios comercios/canales. |
| `marketplace` | Marketplace | Pedidos, cobros, descuentos, fees, devoluciones y payout | El pedido no prueba el abono bancario. |
| `digital_wallet` | Billetera | Movimientos, saldo y transferencias | Cuenta y dirección deben quedar explícitas. |
| `billing_erp` | ERP/proveedor de facturación | Facturas emitidas, notas, pedidos y cartera | Fuente prioritaria para el lado emitido de CxC. |
| `accounting_ledger` | Sistema contable/ERP | Asientos, auxiliares, mayor y saldos en libros | No confundir con el extracto bancario. |
| `tax_documents_received` | Buzón/integración DIAN autorizada | Documentos electrónicos recibidos y eventos asociados | `AttachedDocument` recibido no sustituye la fuente de facturas emitidas. |
| `supporting_evidence` | Cliente/contador | Recibos, soportes y anexos | Evidencia asistida; no crea por sí sola una obligación. |
| `reference_data` | Proveedor autorizado | TRM, festivos, monedas, tarifas/tasas | Se versiona y nunca se infiere silenciosamente. |

Campos descriptivos mínimos de una fuente: `company_id`, familia, emisor,
cuenta/establecimiento, canal, responsable, frecuencia, periodo y zona esperados,
moneda, autenticación, frescura, SLA, retención, versión de conector,
capacidad de completitud y costo.

## 5. Familias documentales

| Código | Significado | Campos/control principales | Destino canónico candidato |
|---|---|---|---|
| `bank_account_statement` | Extracto periódico de cuenta | Cuenta, periodo, saldo inicial/final, débitos, créditos, movimientos | `financial_account`, `account_balance`, `source_record` |
| `bank_transaction_export` | Export tabular/API de movimientos | ID, fechas, referencia, monto/dirección, running balance | `source_record`, `money_movement` |
| `sales_invoice_export` | Facturas/pedidos emitidos | Número, emisión, vencimiento, cliente, moneda, bruto/impuestos/total, estado | `obligation` |
| `credit_debit_note_export` | Notas emitidas/recibidas | Documento relacionado, fecha, monto y motivo | `obligation`/ajuste relacionado |
| `payment_transaction_report` | Cobros individuales | ID proveedor, fecha, orden/factura, bruto, estado, medio | `money_movement` candidato |
| `settlement_payout_report` | Liquidación y abono | ID liquidación, periodo, bruto, fees, impuestos, retenciones, devoluciones, neto | `settlement`, movimientos relacionados |
| `refund_reversal_chargeback_report` | Disminuciones o reversos | ID original, fecha, tipo, importe, estado | `money_movement` relacionado |
| `fee_withholding_report` | Comisiones, impuestos y retenciones | Concepto, base, tasa, importe y liquidación | `money_movement`/`settlement` |
| `general_ledger_export` | Asientos/libro mayor/auxiliar | Cuenta, comprobante, fecha contable, débito, crédito, tercero, referencia | `ledger_entry`, `ledger_line` |
| `book_balance_report` | Saldos según libros | Cuenta, periodo, saldo inicial/movimiento/final | `account_balance` con perspectiva libros |
| `received_einvoice` | Factura/nota electrónica recibida | Identificadores UBL/DIAN, partes, fechas, moneda, totales, firma/validación | `obligation` de CxP/evidencia |
| `supporting_document` | Evidencia no transaccional | Emisor, fecha, concepto, referencias y localizadores | Evidencia; requiere clasificación humana cuando sea ambiguo |
| `control_manifest` | Conteos/totales/cursor declarados por origen | Conteo, débitos, créditos, saldos, páginas, secuencia | `completeness_assessment` |

Una clasificación desconocida usa `unknown_document`; nunca se fuerza a la
familia más parecida para habilitar procesamiento automático.

## 6. Formatos técnicos y contenedores

| Código | Tipo | Estado inicial | Consideraciones de prueba |
|---|---|---|---|
| `csv`, `tsv` | Tabular delimitado | Primera clase hipotética | Delimitador, quoting, BOM, locale, saltos y encoding. |
| `xlsx`, `xls` | Libro tabular | Primera clase hipotética | Hojas, celdas combinadas, fórmulas no ejecutadas, fechas seriales. |
| `pdf_native` | Documento con texto | Primera clase según corpus | Páginas, tablas, cajas, texto superpuesto y protegido. |
| `pdf_scanned` | Imagen dentro de PDF | Asistido | OCR, rotación, ruido y abstención. |
| `png`, `jpeg`, `heic` | Imagen | Asistido/móvil | EXIF, orientación, resolución y OCR. |
| `xml_ubl_dian` | XML estructurado | Primera clase hipotética | Namespace, XSD, firma, `AttachedDocument`; XXE prohibido. |
| `json_api`, `json_webhook` | Registro estructurado | Por conector | Schema, IDs, paginación, replay y versiones. |
| `ofx`, `mt940`, `camt_053` | Financiero estructurado | Condicionado al corpus | No se declara prioritario sin evidencia local. |
| `eml`, `mime_message` | Contenedor de correo | Canal/contenedor | Autenticación, adjuntos, forwarding y contenido activo. |
| `zip` | Contenedor comprimido | Restringido | Expansión, nesting, rutas, cuotas y zip bomb. |

La extensión declarada puede diferir de la firma real. Un contenedor no hereda
automáticamente la confianza a sus adjuntos.

## 7. Taxonomía de campos

| Grupo | Campos canónicos representativos | Regla |
|---|---|---|
| Tenancy/procedencia | `company_id`, `data_source_id`, `connection_id`, `issuer_id`, `artifact_version_id` | `company_id` es obligatorio en todo registro financiero. |
| Identificadores externos | `provider_record_id`, `invoice_number`, `order_id`, `settlement_id`, `external_reference` | Son texto opaco; conservar original y normalizado. |
| Tiempo | `occurred_at`, `posted_at`, `value_date`, `accounting_date`, `period_start`, `period_end`, `original_timezone` | No colapsar fechas distintas ni inferir zona silenciosamente. |
| Dinero | `amount`, `direction`, `currency`, `gross_amount`, `fee_amount`, `tax_amount`, `withholding_amount`, `net_amount` | Decimal exacto; en JSON se representa como string decimal. Nunca `float`. |
| Saldo/control | `opening_balance`, `closing_balance`, `running_balance`, `record_count`, `debit_total`, `credit_total`, `page_count`, `cursor_start`, `cursor_end` | Declarar perspectiva, cuenta, periodo y procedencia. |
| Cuenta/parte | `financial_account_id`, `account_token`, `account_last4`, `counterparty_id`, `merchant_id`, `payer_reference`, `payee_reference` | Tokenizar/minimizar; una cadena numérica no se trata como número. |
| Calidad | `raw_text`, `parsed_value`, `locale`, `confidence`, `validation_status`, `rejection_reason` | Valor crudo se conserva; confianza no sustituye validación. |
| Linaje/versiones | `origin_locator_id`, `recipe_version_id`, `overlay_version_id`, `canonical_schema_version`, `engine_release_id` | Todo campo publicado conserva un camino a evidencia. |
| Seguridad/privacidad | `data_classification`, `retention_class`, `purpose`, `legal_hold_status` | No incluir secretos o PAN como metadato de negocio. |

`direction` se expresa como `inflow` o `outflow` desde la perspectiva declarada de
la cuenta. `debit` y `credit` se reservan para asientos/columnas contables y para
los totales tal como los publica la fuente. El importe normalizado es no negativo;
el signo original permanece en `raw_text`/linaje.

## 8. Locales, encoding y representación

- Locale inicial: `es-CO`; cada valor ambiguo conserva locale detectado/sugerido.
- Matriz sintética mínima: `es-CO`, `en-US` y un locale latinoamericano adicional.
- Separadores a cubrir: `1.234,56`, `1,234.56`, espacios duros y ausencia de miles.
- Fechas a cubrir: ISO 8601, `DD/MM/YYYY`, `MM/DD/YYYY`, fecha serial de hoja,
  año bisiesto, medianoche y `03/04/26` deliberadamente ambiguo.
- Encodings a cubrir: UTF-8 con/sin BOM, Windows-1252 e ISO-8859-1 cuando el
  formato lo admita; normalización Unicode NFC/NFD y saltos LF/CRLF.
- Monedas mínimas: COP y USD; FX incluye par, proveedor sintético, instante,
  precisión y regla de redondeo.
- Los identificadores preservan ceros iniciales.
- Un fallo de decode nunca se corrige descartando bytes silenciosamente.

## 9. Evidencia, movimiento y deduplicación

| Concepto | Nombre en código | Regla |
|---|---|---|
| Registro de origen | `source_record` | Una observación de una fuente; dos fuentes producen dos evidencias aunque describan el mismo hecho. |
| Movimiento económico | `money_movement` | Evento financiero canónico que puede estar respaldado por N evidencias. |
| Vínculo de evidencia | `movement_evidence_link` | Relaciona evidencia y movimiento sin borrar la evidencia. |
| Redelivery exacto | `exact_redelivery` | Mismo archivo/evento/ID duro; se controla mediante idempotencia. |
| Candidato de dedupe | `dedupe_candidate` | Hipótesis de que evidencias representan lo mismo; no elimina ni fusiona. |
| Decisión de merge | `merge_decision` | Determinación versionada y auditada de unir o mantener separado. |
| Duplicado legítimo idéntico | `legitimate_identical_movement` | Dos eventos reales distintos con iguales fecha, monto, dirección y referencia; deben poder coexistir. |

Las claves duras admitidas son hash exacto por empresa/fuente, ID de evento del
proveedor o ID/version estable del registro. El fingerprint basado en cuenta,
fecha, monto, dirección y referencia solo genera candidatos y nunca es `UNIQUE`.

## 10. Completitud, conciliación y cierre

| Término | Nombre en código | Definición |
|---|---|---|
| Evaluación de completitud | `completeness_assessment` | Comparación versionada por fuente, cuenta y periodo contra controles disponibles. |
| Verificado | `verified` | Conteos/totales/saldos/secuencias aplicables concuerdan. |
| Discrepancia | `mismatch` | Al menos un control esperado no concuerda. |
| Desconocido | `unknown` | El origen no permite demostrar completitud. No equivale a completo. |
| Excepción aceptada | `accepted_exception` | Falta conocida aprobada con motivo, alcance, aprobador y expiración. |
| Parcial/no verificado | `partial_unverified` | Dataset investigable, pero inelegible para auto-match, cierre o reporte certificado. |
| Estado conciliatorio | `reconciliation_statement` | Ecuación versionada entre saldo banco, partidas, saldo libros y diferencia no explicada. |
| Snapshot cerrado | `closed_snapshot` | Cierre reproducible e inmutable con datos, evidencia, decisiones, esquema y release fijados. |

Los matches de movimientos no prueban por sí solos que una cuenta esté
conciliada. `unexplained_difference = 0` es una condición independiente.

## 11. Procesamiento y reproducibilidad

| Término | Nombre en código | Definición |
|---|---|---|
| Ejecución de proceso | `processing_run` | Intento trazable sobre inputs inmutables y versiones declaradas. |
| Perfil de esquema | `schema_profile` | Descripción de estructura, tipos, controles y distribución de una fuente/template. |
| Receta | `transform_recipe_version` | Secuencia determinística versionada de transformaciones. |
| Overlay manual | `manual_overlay` | Corrección reversible con actor, motivo, localizador y versión. |
| Deriva | `drift` | Cambio estructural, estadístico, semántico o de totales respecto al perfil aprobado. |
| Release de motor | `engine_release` | Semver, commit, hash de artefacto, SBOM y clasificación de impacto que produjo resultados. |
| Registro de origen publicado | `source_record_published` | Unidad técnica de metering por evidencia publicada; no es “movimiento único”. |

## 12. Clasificación de datos

| Código | Ejemplo | Uso en fixtures actuales |
|---|---|---|
| `public` | Documentación publicada | Permitido si no introduce datos reales en fixtures. |
| `internal` | Configuración de pruebas | Permitido. |
| `confidential` | Identidad/configuración de cliente | Solo equivalente sintético antes de DRG-00. |
| `financial_sensitive` | Movimientos, cuentas y cierres | Solo equivalente sintético antes de DRG-00. |
| `secret` | Token OAuth/API key | Nunca usar secretos reales; fixtures usan tokens obviamente inválidos. |
| `prohibited` | CVV, contraseñas, credenciales bancarias/DIAN | No persistir ni siquiera como ejemplo real; pruebas usan marcadores sintéticos inocuos y aislados. |

## 13. Términos prohibidos o ambiguos

- `tenant` sin precisar `organization` o `company`.
- `customer` sin precisar firma compradora, empresa servida o sujeto.
- `movement` para `source_record` y `money_movement` indistintamente.
- `duplicate` para un `dedupe_candidate`.
- `complete` para `unknown`, `partial_unverified` o una mera carga exitosa.
- `reconciled`/`cuadrado` si el statement de saldos no da cero o existe una
  excepción material oculta.
- `fraud` para una señal de riesgo o inconsistencia.
- `owner` sin precisar dueño administrativo, legal, de activo o de dato.
- `published` como “público”; en datasets significa disponible para la siguiente
  etapa autorizada.
- `delete` sin precisar solicitud, tombstone, purga de derivados, borrado de
  versión o expiración de backup.

## 14. Pendientes de aceptación

- FNC-PRD-001 debe confirmar qué familias entran en el wedge inicial.
- Accounting debe validar nombres, perspectiva de dirección, controles y destinos.
- Privacy debe validar clasificación, minimización y vocabulario de datos derivados.
- El corpus posterior a DRG-00 determinará formatos y plantillas prioritarios; la
  lista actual es una taxonomía, no una promesa de soporte.
