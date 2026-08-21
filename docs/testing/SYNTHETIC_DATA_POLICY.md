# Política de datos sintéticos

- Estado: Draftable
- Tarea: FNC-DAT-001
- Gate actual: S1-READY
- Techo vigente: `synthetic_only`
- Revisiones requeridas para aceptación: Privacy y Accounting
- Referencias del plan: §7, §15, §31 y §48

Esta política gobierna fixtures, seeds, snapshots, ejemplos, golden files,
capturas, prompts, logs y artefactos de pruebas. Mientras `CURRENT_PHASE.md`
mantenga `synthetic_only`, no existe excepción por conveniencia técnica.

## 1. Definiciones

### 1.1 Dato completamente sintético

Dato creado desde cero mediante una plantilla propia o un generador controlado,
sin usar filas, valores, textos, nombres, imágenes, layouts singulares,
distribuciones calibradas a una empresa o documentos reales como entrada.

Para ser aceptable debe tener procedencia demostrable, manifiesto, generador o
proceso de autoría reproducible, identificadores de prueba y revisión. Que un dato
“parezca falso” no basta.

### 1.2 Dato real derivado

Sigue siendo dato real derivado cualquiera de estas variantes:

- Anonimizado, seudonimizado, enmascarado, tokenizado o redactado.
- Reordenado, truncado, perturbado, traducido o con fechas/montos desplazados.
- Captura, OCR, transcripción o copia parcial de un documento real.
- Estructura singular o distribución reconstruida desde una empresa/documento.
- Agregado del que todavía puede inferirse una fuente o cohorte identificable.

Un dato real saneado puede llegar a estar autorizado después de DRG-00, pero
nunca se reclasifica como `synthetic`.

### 1.3 Especificación pública

Un XSD, RFC, catálogo de campos o documentación técnica puede orientar una
plantilla propia si su licencia permite el uso. Un archivo de ejemplo publicado
por un proveedor no se presume sintético: queda excluido hasta demostrar origen,
licencia y ausencia de datos reales mediante revisión independiente.

## 2. Política por gate y ambiente

| Etapa | Local/dev/CI/repo | Corpus de investigación | Staging | Piloto/producción |
|---|---|---|---|---|
| Antes de DRG-00, incluido S1-READY | Solo sintético manifestado | No existe/denegado | Solo sintético | No permitido |
| DRG-00 aprobado | Sigue solo sintético | Real acotado solo en ambiente aislado, inventariado y con contrato | Sintético; real saneado solo mediante aprobación específica | No permitido |
| DRG-01 aprobado | Sigue solo sintético | Según finalidad/retención DRG-00 | Sintético o derivado real autorizado, segregado | Datos reales del piloto bajo DPA, controles y alcance aprobado |
| GA-01 aprobado | Sigue solo sintético | Según programa vigente | Según política aprobada; nunca copia libre de producción | Datos reales contractuales y controles productivos |

Reglas permanentes:

- Repo, paquetes publicados, CI y ejemplos documentales nunca contienen datos
  financieros o personales reales, aunque exista DRG-00/DRG-01/GA-01.
- Un gate no autoriza por sí solo un dataset: exige finalidad, owner, inventario,
  ambiente, acceso, retención y evidencia nominales.
- Datos de un ambiente superior no se copian hacia uno inferior.
- Ningún dato real o derivado se envía a IA externa antes del gate, DPIA/DPA y
  policy específicos.

## 3. Métodos permitidos antes de DRG-00

- Generador determinístico con PRNG y seed declarados.
- Escenario escrito manualmente desde requisitos genéricos, sin documento real
  abierto como referencia.
- Plantilla propia basada en un esquema técnico/licenciado, con valores creados
  desde cero.
- Property tests que generan valores efímeros en memoria.
- Documentos renderizados por el proyecto desde plantillas propias.
- Archivos hostiles inocuos creados para verificar límites, encoding, fórmulas,
  compresión o parser; nunca malware funcional.

Una salida generativa externa no es fixture aprobable por sí sola. Puede sugerir
una idea sin datos de cliente, pero el fixture final debe reconstruirse mediante
plantilla/generador determinístico, documentar que no usó datos reales y pasar la
misma revisión.

## 4. Métodos prohibidos

- Datos reales anonimizados, enmascarados o parcialmente editados.
- Seeds, dumps, logs, traces, respuestas API o snapshots de producción.
- Extractos, facturas, emails, XML, PDFs, imágenes o pantallas de clientes.
- Copiar un layout singular de banco/pasarela obtenido de un cliente antes de
  DRG-00.
- Usar nombres, NIT, cuentas, teléfonos, emails, referencias o contrapartes
  encontrados en internet o documentos reales.
- Calibrar montos, frecuencias, distribuciones o anomalías con un cliente real.
- Descargar datasets financieros “de prueba” sin verificar licencia y origen.
- Incluir secretos, PAN, CVV o credenciales reales en pruebas negativas.
- Introducir PII o datos financieros reales en prompts, issues, comentarios,
  handoffs, screenshots, artefactos CI o mensajes de error.
- Declarar sintético un fixture sin manifiesto o con procedencia desconocida.

## 5. Identificadores y contenido inequívocamente de prueba

- Empresas y personas: prefijo visible `FNC-SYN-`, por ejemplo “FNC-SYN Empresa
  Cascada 001”. No se usan nombres de clientes, fundadores o terceros reales.
- Dominios/email: `.test` o `.invalid`.
- Proveedores: `FNC-SYN Banco`, `FNC-SYN Pasarela`; nunca imitar marca/logo real.
- Cuentas y referencias: prefijo `SYN`, secuencia generada y sin uso fuera del
  harness. Si un formato exige solo dígitos, el manifiesto debe declarar esa
  limitación y el valor no se consulta ni transmite externamente.
- NIT: los fixtures generales usan tokens `FNC-SYN-NIT-*`. Las pruebas del
  algoritmo de verificación generan valores efímeros en memoria, sin consulta de
  registros y sin persistencia como identidad de una empresa.
- Tokens/secretos: marcadores deliberadamente inválidos; no deben tener forma de
  credencial utilizable.
- UUID: namespace/seed sintético declarado y estable.
- Fechas: ventanas fijas del escenario; no desplazar fechas de registros reales.
- Montos: generados mediante reglas declaradas y strings decimales, no floats.

La similitud accidental de un identificador numérico con uno existente no concede
permiso para resolverlo contra servicios externos. Ante sospecha razonable se
retira el fixture y se activa el procedimiento del §13.

## 6. Cobertura sintética mínima

La suite inicial debe cubrir, como escenarios separados y manifestados:

| ID de escenario | Caso | Expectativa clave |
|---|---|---|
| `SYN-HAPPY-1TO1` | Factura, pago, payout, banco y asiento 1:1 | Linaje completo; propuesta explicable. |
| `SYN-NET-SETTLEMENT` | Bruto - fee - impuesto - retención - devolución = neto | Decimal exacto y controles de liquidación. |
| `SYN-PARTIAL-GROUPS` | Parciales, 1:N, N:1 y N:M acotado | Saldos pendientes preservados. |
| `SYN-REVERSALS` | Refund, reverso y chargeback | Vínculo al movimiento original. |
| `SYN-FX` | COP/USD con tasa/version/redondeo | No inferir tasa ni moneda silenciosamente. |
| `SYN-LEGIT-IDENTICAL` | Dos pagos distintos con misma fecha, monto, dirección y referencia | Permanecen separados; fingerprint no único. |
| `SYN-EXACT-REPLAY` | Mismo upload/webhook repetido | Un solo efecto y un solo evento de uso. |
| `SYN-COMP-MISMATCH` | Conteos, totales o saldo final discordantes | `mismatch`; bloquea certificación. |
| `SYN-COMP-UNKNOWN` | Origen sin controles suficientes | `unknown`, nunca `verified`. |
| `SYN-DRIFT` | Cambio estructural, estadístico, semántico y de totales | Suspende receta automática. |
| `SYN-LOCALE` | Separadores y fecha `03/04/26` ambiguos | Requiere locale/confirmación. |
| `SYN-ENCODING` | UTF-8 BOM, Windows-1252, ISO-8859-1, NFC/NFD, LF/CRLF | Sin pérdida silenciosa de bytes. |
| `SYN-BALANCES` | Saldo banco/libros y partidas conciliatorias | Diferencia no explicada calculada. |
| `SYN-CROSS-COMPANY` | Dos empresas con IDs/referencias coincidentes | Cero lectura, link o merge cruzado. |
| `SYN-LINEAGE-OVERLAY` | Corrección de celda sin alterar raw | Nuevo overlay y camino completo. |
| `SYN-SAFE-HOSTILE` | MIME falso, zip bomb simulada, XXE/fórmula inocua | Rechazo/cuarentena sin ejecución. |

Estos escenarios especifican datos de prueba; no habilitan auto-match, cierre ni
otras funciones prohibidas en la fase vigente.

## 7. Matriz de locales y representaciones

Cobertura mínima por familia tabular:

- Locales: `es-CO`, `en-US` y al menos otro locale latinoamericano.
- Decimales: `1.234,56`, `1,234.56`, sin separador de miles, negativos crudos y
  paréntesis contables.
- Fechas: ISO, DMY, MDY, serial de Excel, año bisiesto, frontera de periodo y fecha
  ambigua.
- Zonas: `America/Bogota`, UTC y un offset distinto para verificar conversión.
- Monedas: COP, USD y un caso FX; cada importe lleva moneda y perspectiva.
- Encodings: UTF-8 con/sin BOM, Windows-1252 e ISO-8859-1 donde aplique.
- Saltos/Unicode: LF, CRLF, NFC, NFD, espacios duros y caracteres acentuados.
- Identificadores: ceros iniciales, longitud extrema permitida y caracteres
  Unicode controlados.
- Saldos: apertura, débitos, créditos, cierre, running balance y continuidad entre
  periodos.

## 8. Manifiesto obligatorio por fixture

Cada artefacto fixture tiene un sidecar de manifiesto. El manifiesto cubre un
artefacto exacto; una colección puede sumar un manifiesto de escenario, pero no lo
reemplaza.

Campos obligatorios:

~~~yaml
fixture_schema_version: "1.0"
fixture_id: "FNC-SYN-NET-SETTLEMENT-CSV-001"
fixture_version: 1
synthetic: true
origin_class: "generated_from_scratch" # o hand_authored_from_scratch
classification: "synthetic_financial_sensitive"

generator:
  name: "fincilia-synthetic-generator"
  version: "0.1.0"
  source_hash: "<sha256 del generador/configuración>"
  seed: "fnc-syn-net-settlement-001"
  command: "<comando reproducible sin red>"

provenance:
  real_data_used: false
  customer_data_used: false
  public_record_data_used: false
  external_ai_used: false
  source_inputs:
    - kind: "project_owned_template"
      id: "settlement-v1"
      version: 1
      license: "project-internal"

scenario:
  id: "SYN-NET-SETTLEMENT"
  description: "Liquidación totalmente ficticia"
  company_fixture_id: "FNC-SYN-COMPANY-001"
  locale: "es-CO"
  timezone: "America/Bogota"
  currencies: ["COP"]

source_taxonomy:
  source_family: "payment_gateway"
  ingestion_channel: "web_upload"
  document_family: "settlement_payout_report"
  technical_format: "csv"
  template_version: "FNC-SYN-SETTLEMENT-v1"

representation:
  encoding: "utf-8"
  line_endings: "LF"
  decimal_style: "dot_decimal"
  date_style: "ISO-8601"

coverage:
  edge_cases: ["fee", "withholding", "refund", "net_settlement"]
  canonical_fields:
    - "gross_amount"
    - "fee_amount"
    - "withholding_amount"
    - "net_amount"

expected:
  dataset_state: "published_complete"
  record_count: 12
  control_totals:
    gross_amount: "1000000.00"
    fee_amount: "25000.00"
    withholding_amount: "15000.00"
    refund_amount: "10000.00"
    net_amount: "950000.00"
  allowed_for_auto_match: false
  allowed_for_close: false

artifact:
  relative_path: "<ruta permitida del fixture>"
  media_type: "text/csv"
  byte_size: "<entero generado>"
  sha256: "<64 hex del artefacto exacto>"

safety:
  contains_real_data: false
  contains_pii: false
  contains_usable_secrets: false
  contains_active_malware: false
  network_required_to_generate: false

attestation:
  authored_by: "<identidad del autor>"
  reviewed_by: "<revisor distinto>"
  reviewed_at: "<RFC3339>"
  review_task: "FNC-DAT-001 o tarea sucesora"
~~~

En JSON/YAML, los importes esperados son strings decimales. Un placeholder del
ejemplo anterior no es válido en un manifiesto real.

## 9. Cómo demostrar que un fixture es sintético

La etiqueta `synthetic: true` es necesaria pero insuficiente. CI/revisión debe
reunir estas evidencias:

1. Inventario completo de inputs y licencias del generador.
2. Atestación explícita de no uso de datos reales, públicos registrales o clientes.
3. Generación determinística sin red; misma versión + seed produce mismo hash.
4. Nombres, dominios, IDs, emisores y referencias usan namespaces de prueba.
5. Escaneo de secretos, PAN/credenciales, PII obvia y patrones prohibidos.
6. Revisor distinto del autor verifica procedencia y representatividad contable.
7. Hash, tamaño, conteos, totales y resultados concuerdan con el manifiesto.
8. Fixture no aparece sin sidecar ni sidecar huérfano.

Un linter no puede probar por sí solo ausencia de datos reales. Cualquier duda de
procedencia falla cerrado: el fixture se rechaza y se trata como potencial dato
real.

## 10. Validaciones previstas para CI

La tarea actual solo define la política; la automatización corresponde a una tarea
posterior del backlog de QA/Platform.

La futura validación debe:

- Rechazar fixture sin manifiesto o schema/version desconocidos.
- Validar IDs únicos, rutas relativas seguras y hashes.
- Regenerar una muestra o toda la suite y comparar hashes.
- Ejecutar secret scan y detectores preventivos de PAN/credenciales.
- Detectar dominios no reservados, logos/marcas, nombres y prefijos no sintéticos.
- Prohibir red durante generación.
- Verificar dinero decimal, moneda, locale, encoding y controles.
- Confirmar que dos pagos legítimos idénticos permanecen distintos.
- Confirmar que `unknown`/`partial_unverified` no sean elegibles para auto-match,
  cierre o informe certificado.
- Publicar solo hashes/IDs sintéticos en logs de CI.

## 11. Golden files y snapshots

- Golden file fija input, manifiesto, resultado esperado, parser/template,
  `canonical_schema_version` y `engine_release`.
- Rebaselinar exige diff explicado y revisión; nunca actualizar snapshots a ciegas.
- Un cambio `affects_results` vuelve a ejecutar toda la suite adjudicada aplicable.
- El resultado esperado conserva localizadores y linaje campo a campo.
- Los artefactos grandes tienen límite y justificación; no se ocultan en binarios
  sin manifiesto.
- Property tests pueden generar datos efímeros, pero registran seed al fallar y no
  imprimen payload completo.

## 12. Sanitización posterior a DRG-00

Esta sección diseña el gate; no autoriza ni implementa el flujo ahora.

Un corpus real solo podrá recibirse tras DRG-00 con contrato, finalidad, ambiente
aislado, inventario nominal, acceso mínimo, retención y borrado verificable. La
sanitización debe:

1. Registrar original, titular/fuente, finalidad, owner, hash y reloj de retención.
2. Ejecutarse en el ambiente aislado, sin IA externa ni salida a repo/CI/local.
3. Eliminar secretos y campos directos no necesarios.
4. Tratar texto libre, imágenes, metadatos, nombres de archivo y quasi-identificadores.
5. Generalizar/sustituir valores conforme a finalidad y medir riesgo residual de
   reidentificación o singularidad.
6. Conservar un manifiesto de transformaciones y derivados para borrado.
7. Obtener revisión independiente de Privacy y Accounting; Security revisa el
   ambiente y egress.
8. Etiquetar el resultado `authorized_real_sanitized`, nunca `synthetic`.
9. Mantenerlo fuera de repo y CI, con TTL, acceso auditado y purga reconciliada.

Si se necesita un fixture permanente inspirado en aprendizajes del corpus, se usa
un proceso clean-room: un primer equipo documenta solo requisitos genéricos
aprobados; otro autor crea un escenario nuevo sin acceso a filas/documentos. Privacy
verifica que no se copiaron layout singular, valores o distribución. El nuevo
fixture obtiene procedencia propia y nunca referencia el artefacto real como input.

## 13. Respuesta ante dato real o procedencia dudosa

1. Detener uso, generación y publicación; no abrir ni imprimir más contenido.
2. Aislar el artefacto mediante el proceso de Security, sin copiarlo a otra ruta.
3. Notificar a Integration Steward, Security y Privacy con ID/ruta/hash, no payload.
4. Determinar alcance en filesystem, logs, CI, cachés y servicios externos.
5. Si contiene secreto, iniciar rotación y tratamiento de incidente.
6. Purgar mediante procedimiento aprobado y conservar evidencia mínima del evento.
7. Solo reanudar cuando Privacy/Security determinen clasificación y disposición.

Un agente no reescribe historia Git ni destruye evidencia por iniciativa propia;
el Integration Steward coordina la remediación.

## 14. Criterios de aprobación de esta política

- FNC-PRD-001 confirma familias y escenarios del wedge.
- Accounting valida ecuaciones, saldos, dirección y casos límite.
- Privacy valida definición de sintético, datos derivados y clean-room.
- Security valida respuesta a hallazgo, secretos y archivos hostiles.
- QA/Platform asigna tarea para schema/linter/generador y aporta ejecución CI.
- Integration Steward confirma que ninguna ruta/artefacto real fue creado durante
  FNC-DAT-001.
