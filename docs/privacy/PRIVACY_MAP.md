# Mapa de privacidad, tratamiento, retención y borrado v0

## 1. Estado y autoridad

| Campo | Valor |
|---|---|
| Tarea | FNC-PRV-001 |
| Estado | Review pending |
| Gate | S1-READY |
| Owners requeridos | Privacy + Legal |
| Revisores | Security, Architecture y Product |
| Datos autorizados | `synthetic_only` |
| Región y proveedor | **A-02 pendiente** |
| Validación jurídica | `pending_human` |
| IA externa | `external_ai_enabled: false` |
| Modelo ejecutable | `docs/privacy/privacy-map.json` |
| Validador | `python -m tools.privacy_model.validate` |

Este documento **no acepta** decisiones legales, riesgos residuales, regiones,
proveedores ni gates. Un agente no puede firmar en nombre de Privacy, Legal, Security,
Architecture o Product. Cuando el modelo y este texto difieran, manda el modelo
ejecutable y la diferencia es un defecto que hay que corregir.

Aprobar este documento no supera S1-READY ni DRG-00 ni autoriza datos reales.

### 1.1 Dependencias heredadas que este mapa preserva, no resuelve

| ID | Hallazgo previo | Por qué afecta a privacidad | Owner |
|---|---|---|---|
| `UD-PRIMARY-OPERATOR` | `TST-TEN-001-N09` exige un único `primary_accounting_operator` y un kernel de política no garantiza concurrencia. | Ninguna garantía de segregación de datos puede apoyarse solo en una comprobación en memoria. Requiere constraint o índice único parcial en PostgreSQL y un Database Migration Owner. | Architecture |
| `UD-ISSUED-CONTEXT` | No existe la entidad canónica `issued_authorization_context`. | Revocación, export, portabilidad y borrado dependen de poder revalidar un contexto emitido. Debe portar `authorization_version`, company scope, purpose, subject o service principal, `issued_at` y `expires_at`. | Architecture |
| `UD-PORTFOLIO-CANDIDATES` | `resolvePortfolio` solo es seguro si la lista de companies candidatas viene de almacenamiento autoritativo. | Una enumeración desde caché consolidada reintroduce exposición cruzada después de revocar. | Backend |

Este mapa declara las tres como dependencias con owner y gate. **No las implementa ni
las corrige**: tenancy, autorización y migraciones están fuera de las rutas de esta tarea.

---

## 2. Principios

1. **Privacidad desde el diseño y por defecto.** La opción por defecto es no recolectar, no persistir y no transmitir.
2. **Minimización.** Se procesa el campo necesario para la finalidad declarada, no el documento completo por comodidad.
3. **Limitación por finalidad.** Un grant para una finalidad no autoriza ninguna otra.
4. **Segregación por company.** La frontera es la company, no la firma ni la organización.
5. **Necesidad de acceso.** Pertenecer no es acceder; administrar no es leer.
6. **Retención limitada.** Todo dato tiene clase, política y evento de expiración.
7. **Explicabilidad y trazabilidad.** Toda cifra publicada vuelve a su origen; toda decisión privilegiada deja evidencia.
8. **Revocación real.** Revocar invalida sesiones, jobs, enlaces, schedules y cachés, no solo una fila.
9. **Borrado verificable.** No se declara `completed` mientras exista una copia activa no justificada.
10. **Cero datos de negocio en logs por defecto.** Allowlist, nunca blacklist.
11. **Cero transmisión externa implícita.** Egress deny-by-default; ningún proveedor recibe datos antes de contrato, región y rol.

---

## 3. Roles de tratamiento

**Fincilia no es siempre Responsable ni siempre Encargado.** El rol depende de quién
determina finalidad y medios en cada actividad, y ninguna postura de esta tabla está
aceptada: todas son candidatas hasta concepto jurídico.

| Actividad | Postura provisional | Quién determina finalidad y medios | Qué falta |
|---|---|---|---|
| Datos financieros y documentales procesados por instrucción de la empresa (`PA-03`, `PA-04`…`PA-09`) | `processor_candidate` | La company instruye; la firma opera por delegación | DPA, instrucción documentada y alcance contractual |
| Administración de cuenta y autenticación (`PA-01`) | `controller_candidate` | Fincilia, para poder prestar el servicio de forma segura | Base jurídica y aviso de privacidad |
| Administración de company y engagement (`PA-02`, `PA-18`) | `joint_or_context_dependent` | La company autoriza; Fincilia define el mecanismo | Concepto sobre corresponsabilidad |
| Billing y uso (`PA-14`) | `controller_candidate` | Fincilia, finalidad propia de facturación | Obligación legal aplicable y plazo |
| Seguridad, fraude técnico e incidentes (`PA-12`) | `controller_candidate` | Fincilia, interés propio de integridad | Base jurídica y límites frente a derechos |
| Soporte (`PA-13`) | `joint_or_context_dependent` | La company autoriza el acceso; Fincilia lo ejecuta | Cláusula de soporte y JIT en el contrato |
| Notificaciones (`PA-11`) | `controller_candidate` | Fincilia define el canal; la company el destinatario | Proveedor, región y contrato |
| Analítica operativa (`PA-20`) | `controller_candidate` | Fincilia, para operar y mejorar el servicio | Límite de agregación y opt-out |
| Desarrollo y evaluación de modelos (`PA-22`) | `controller_candidate` | Fincilia, sobre corpus sintético únicamente | Base, contrato y DPIA si dejara de ser sintético |
| Conectores (`PA-10`) | `processor_candidate` | La company autoriza la fuente | Contrato con el proveedor y alcance del consentimiento |
| Export y portabilidad (`PA-09`, `PA-16`) | `processor_candidate` | La company solicita y define alcance | Formato contractual del paquete |
| Obligaciones legales y holds (`PA-24`) | `not_determined_pending_legal` | La obligación aplicable, no las partes | Identificación de la obligación concreta |
| IA externa (`PA-19`) | `not_determined_pending_legal` | Sin decidir; desactivada | L-02 completo |

---

## 4. Sujetos y partes

| Categoría | Naturaleza | Nota |
|---|---|---|
| `firm_accountant` | Persona natural | Profesional de la firma que opera bajo engagement |
| `firm_employee` | Persona natural | Personal de apoyo de la firma |
| `sme_administrator` | Persona natural | Autorizador de la company; controla el engagement |
| `sme_employee_or_contractor` | Persona natural | Aporta soportes y contexto de negocio |
| `third_party_natural_person_in_documents` | Persona natural | Aparece en facturas o movimientos **sin ser usuario** |
| `auditor_user` | Persona natural | Lectura de evidencia e históricos |
| `support_user` | Persona natural | Personal de Fincilia bajo acceso just-in-time |
| `service_principal_non_human` | Principal no humano | **No es titular** de datos personales y no ejerce derechos |
| `legal_entity_company` | Persona jurídica | Ver la advertencia siguiente |

> **Persona jurídica ≠ titular persona natural.** Una company no se convierte
> automáticamente en titular de datos personales por existir. Pero **sus documentos sí
> pueden contener información de personas naturales**: un empleado, un contratista, un
> proveedor persona natural o un tercero nombrado en una factura. El régimen aplicable a
> cada uno puede diferir y esa determinación corresponde a Legal.
>
> Con independencia de esa calificación, **los datos financieros empresariales se
> protegen contractualmente como sensibles** (`financial_sensitive`), aunque no todos
> sean datos personales bajo la misma ley.

La categoría `third_party_natural_person_in_documents` merece atención propia: son
personas que **no aceptaron nada** con Fincilia y cuya información llega dentro de un
soporte. Dispara `DPIA-08`.

---

## 5. Inventario por actividad

El inventario completo y autoritativo vive en `docs/privacy/privacy-map.json`, campo
`processing_activities`. Cada actividad declara 28 campos: `id`, `name`, `purpose_id`,
`actor`, `subject_categories`, `data_categories`, `classifications`, `source_flows`,
`company_scope`, `stores`, `recipients`, `provisional_role`, `legal_basis_state`,
`region_state`, `cross_border_state`, `retention_policy_ids`, `deletion_triggers`,
`legal_hold_behavior`, `external_ai`, `minimization_controls`, `allowed_log_fields`,
`forbidden_log_fields`, `rights_workflows`, `threat_refs`, `owner_role`,
`reviewer_roles`, `target_gate` y `status`.

Se documenta en JSON y no en prosa porque el validador debe poder comprobarlo, y porque
25 actividades por 28 campos no son legibles como texto corrido.

| ID | Actividad | Finalidad | Flujos DFD | Rol provisional | Owner | Gate |
|---|---|---|---|---|---|---|
| PA-01 | Autenticación y sesión | `identity_and_access` | F01 | controller | Security | S1-READY |
| PA-02 | Administración de company y engagement | `company_administration` | — | joint | Architecture | S1-READY |
| PA-03 | Operación contable delegada | `delegated_accounting_operation` | F05, F06 | processor | Accounting | DRG-01 |
| PA-04 | Recepción de evidencia en cuarentena | `evidence_ingestion` | F02 | processor | Data Engineering | DRG-00 |
| PA-05 | Escaneo de contenido prohibido y promoción | `evidence_ingestion` | F03 | processor | Security | DRG-00 |
| PA-06 | Parseo y extracción | `parsing_and_mapping` | F04 | processor | Data Engineering | S1-READY |
| PA-07 | Mapeo, validación y publicación | `parsing_and_mapping` | F05 | processor | Backend | S1-READY |
| PA-08 | Conciliación y cierre | `reconciliation_and_close` | F06 | processor | Accounting | DRG-01 |
| PA-09 | Informes y export | `reporting_and_export` | F07 | processor | Reporting | S1-READY |
| PA-10 | Ingesta por conector o webhook | `connector_operation` | F09 | processor | Integrations | DRG-01 |
| PA-11 | Recordatorios y notificaciones | `reminders_and_notifications` | — | controller | Product | S1-READY |
| PA-12 | Auditoría de seguridad y digest | `security_and_audit` | F10 | controller | Security | S1-READY |
| PA-13 | Soporte y break-glass | `support_and_break_glass` | F10 | joint | Security | DRG-01 |
| PA-14 | Medición de uso y facturación | `usage_metering_and_billing` | — | controller | Finance | GA-01 |
| PA-15 | Borrado y tombstone | `deletion_and_portability` | F11 | joint | Privacy | DRG-00 |
| PA-16 | Portabilidad y cambio de firma | `deletion_and_portability` | F07, F13 | processor | Backend | DRG-01 |
| PA-17 | Backup y restore | `backup_and_disaster_recovery` | F12 | processor | Platform | DRG-01 |
| PA-18 | Revocación de engagement e invalidación | `company_administration` | F13 | joint | Security | S1-READY |
| PA-19 | IA desactivada por defecto | `ai_assistance_disabled_by_default` | F08 | no determinado | AI Platform | L-02 |
| PA-20 | Analítica operativa | `operational_analytics` | — | controller | Product | S1-READY |
| PA-21 | Vista de portafolio multiempresa | `delegated_accounting_operation` | F07 | processor | Backend | S1-READY |
| PA-22 | Desarrollo y evaluación de modelos | `ai_assistance_disabled_by_default` | — | controller | AI Platform | DRG-00 |
| PA-23 | Atención de derechos y solicitudes | `deletion_and_portability` | F11 | joint | Privacy | DRG-00 |
| PA-24 | Obligaciones legales y holds | `legal_obligation_compliance` | — | no determinado | Legal | L-01 |
| PA-25 | Manejo en dispositivo y cliente | `identity_and_access` | — | processor | Mobile | S1-READY |

Los trece flujos `F01`–`F13` del DFD están cubiertos. El validador lo comprueba.

---

## 6. Mapa de finalidades

`identity_and_access` · `company_administration` · `delegated_accounting_operation` ·
`evidence_ingestion` · `parsing_and_mapping` · `reconciliation_and_close` ·
`reporting_and_export` · `connector_operation` · `reminders_and_notifications` ·
`security_and_audit` · `support_and_break_glass` · `usage_metering_and_billing` ·
`deletion_and_portability` · `backup_and_disaster_recovery` ·
`ai_assistance_disabled_by_default` · `operational_analytics` ·
`legal_obligation_compliance`

> **Un grant para una finalidad no autoriza otra.** Es la misma regla que aplica el
> kernel de FNC-SEC-001 (`DENY_GRANT_PURPOSE_MISMATCH`): un permiso de `audit.read` no
> sirve para exportar ni para cerrar. Aquí se extiende al plano de privacidad: reutilizar
> un dato recogido para una finalidad en otra distinta es un tratamiento nuevo que exige
> su propia base.

---

## 7. Almacenamiento y copias

Cada store declara autoridad, clases permitidas y prohibidas, cifrado, alcance, borrado
y comportamiento ante restore. El detalle está en `stores` del modelo.

| Store | Autoridad | Nunca almacena | Restore |
|---|---|---|---|
| `postgresql` | Operacional autoritativa | `secret`, `prohibited` | Se restaura y luego se reaplican tombstones |
| `object_storage_quarantine` | Zona no confiable | `secret`, `prohibited` | No se restaura como autoridad |
| `object_storage_raw` | Evidencia inmutable autoritativa | `secret`, `prohibited` | Se restaura y luego se reaplican tombstones |
| `object_storage_derived` | Derivado reproducible | `secret`, `prohibited` | Se regenera, no se restaura |
| `temporal` | Estado de ejecución de workflow | `financial_sensitive`, `secret` | No es autoridad financiera |
| `valkey` | Caché efímera y coordinación | `financial_sensitive`, `secret` | Se reconstruye, nunca se restaura |
| `analytics_projection` | Proyección derivada | `financial_sensitive`, `secret` | Se reconstruye, nunca se restaura |
| `security_archive` | Auditoría append-only | `financial_sensitive`, `secret` | **Fuera del restore ordinario** |
| `vault` | Autoridad de secretos | `financial_sensitive` | No se restaura con datos de negocio |
| `backups` | Copia de recuperación | `secret` | Reaplica tombstones antes de reabrir |
| `logs_traces` | Observabilidad | `confidential`, `financial_sensitive`, `secret` | No es autoridad |
| `mobile_device` | Caché de cliente | `financial_sensitive`, `secret` | No se restaura |
| `browser_storage` | Caché de cliente | `financial_sensitive`, `secret` | No se restaura |
| `email_push_delivery` | Canal externo | `confidential` y superior | No se restaura |
| `external_provider_future` | **No seleccionado** | Todo, hasta contrato y región | No aplica |

Tres consecuencias que conviene leer en voz alta:

- **`secret` solo persiste en `vault`.** El resto del sistema guarda una referencia opaca. Ninguna credencial bancaria, contraseña DIAN, PAN o CVV se persiste en ningún store.
- **Object Lock protege una versión, no una key** (ADR-004). Un actor con permiso de escritura puede añadir un delete marker y ocultar la versión sin borrarla. La inmutabilidad de evidencia no puede descansar solo en esa función.
- **Valkey, `analytics_projection`, `browser_storage`, `mobile_device`, `temporal`, `logs_traces` y `backups` nunca son autoridad financiera.** El validador lo comprueba en la regla `PRV-STORE-AUTHORITY`.

---

## 8. Retención

**Ninguna duración numérica está fijada.** L-01 es una decisión de Legal, no de
ingeniería, y el validador rechaza cualquier número de días, meses o años que aparezca en
una política (`PRV-RETENTION-DURATION`).

Cada política declara: clase, stores, inicio del cómputo, trigger de expiración,
`duration_state`, legal hold, derivados afectados, método de purga, evidencia de purga,
comportamiento en backup y restore, owner y decisión pendiente.

| Política | Clase | Inicio del cómputo | `duration_state` |
|---|---|---|---|
| `L-01-IDENTITY` | Identidad y sesión | Último evento de identidad o sesión | `pending_legal` |
| `L-01-QUARANTINE` | Artefacto no confiable | Recepción de la versión del artefacto | `pending_legal` |
| `L-01-RAW` | Evidencia original aceptada | Aceptación de la versión | `pending_legal` |
| `L-01-DERIVED` | Dataset y manifiesto derivados | Creación de la versión derivada | `pending_legal` |
| `L-01-FINANCIAL` | Registro financiero canónico | **Último asiento o documento relacionado** | `pending_legal` |
| `L-01-CLOSE` | Evidencia de cierre | Sellado del snapshot | `pending_legal` |
| `L-01-EXPORT` | Paquete efímero de export | Materialización del export | `pending_contract` |
| `L-01-SOURCE-EVENT` | Evento de fuente | Recepción del evento | `pending_legal` |
| `L-01-AUDIT` | Auditoría de seguridad y decisión | Escritura del evento | `pending_legal` |
| `L-01-DELETE-LEDGER` | Delete ledger y tombstone | Escritura del tombstone | `pending_legal` |
| `L-01-PRIVACY-REQUEST` | Solicitud de privacidad | Cierre de la solicitud | `pending_legal` |
| `L-01-AUTHORIZATION` | Evidencia de autorización y revocación | Cambio de estado de autorización | `pending_legal` |
| `L-01-AUDITABLE-DECISION` | Decisión operativa registrada | Registro de la decisión | `pending_legal` |
| `L-02-AI-CALL` | Registro minimizado de llamada IA | Registro de la llamada | `pending_contract` |
| `L-01-NOTIFICATION` | Envío de notificación | Despacho | `pending_contract` |
| `L-01-BILLING` | Facturación y uso | Cierre del periodo o factura | `pending_legal` |
| `L-01-BACKUP` | Copia de recuperación | Creación del set | `pending_contract` |
| `L-01-TELEMETRY` | Observabilidad y métrica | Emisión del evento | `pending_contract` |
| `L-01-DEVICE` | Estado local de cliente | Escritura local | `pending_contract` |

Dos precisiones de diseño, no de derecho:

1. **El reloj de `L-01-FINANCIAL` arranca en el último asiento o documento relacionado, no en la fecha de carga del archivo.** Si el lifecycle del object store contara desde `created_at`, borraría antes de tiempo el soporte de un periodo reabierto o de una carga tardía.
2. **`L-01-DELETE-LEDGER` debe exceder la ventana de backup más larga.** Si el ledger caduca antes que el backup que debe corregir, el tombstone deja de poder reaplicarse y la supresión se vuelve reversible.

Ambas requieren confirmación de Legal antes de fijarse.

---

## 9. Borrado y delete ledger

```text
request
  → identity_and_authority_verification
  → scope_resolution (autoritativa, por company, nunca desde caché)
  → legal_or_contract_hold_evaluation
  → tombstone
  → revoke_links_jobs_schedules_and_caches
  → purge_hot_stores
  → rebuild_or_drop_projections
  → inventory_reconciliation
  → backup_expiry_handling
  → delete_evidence_and_digest
  → final_status
```

Estados: `requested` · `verified` · `blocked_by_hold` · `tombstoned` ·
`purge_in_progress` · `backup_pending` · `reconciled` · `completed` · `failed`.

**`completed` solo se alcanza desde `reconciled`.** No existe atajo desde `requested`, y
el validador lo comprueba (`PRV-DELETE-SHORTCUT`).

Reglas no negociables:

- **El raw no se sobrescribe para «borrarlo».** Se marca con tombstone y se purga según política. Sobrescribir destruiría la evidencia sin dejar prueba de la supresión.
- **El delete ledger vive en `security_archive`, fuera del restore ordinario.** Si viviera en la misma base que se restaura, un restore legítimo revertiría el tombstone junto con el dato y nadie lo notaría.
- **El restore reaplica tombstones antes de reabrir el servicio.** Un backup que no puede reconciliarse contra supresiones no cuenta como restore exitoso.
- **No se afirma `deleted` mientras queden copias activas no justificadas.** El inventario incluye exports temporales, proyecciones, cachés y colas.
- **Un legal hold nunca se activa en silencio.** Exige fundamento documentado, alcance, owner y visibilidad en el flujo de borrado.
- **Caché y analítica se reconstruyen, no se restauran**, y nunca se consideran autoridad.

---

## 10. Portabilidad y cambio de firma

- La **company permanece estable**: conserva `company_id`, histórico, evidencia y linaje.
- **Revocar un engagement no reescribe datos.** Cambia autorización, no contenido.
- La **firma saliente pierde acceso** al incrementarse `authorization_version`; sesiones, jobs, enlaces, schedules y cachés dejan de servir.
- La **firma entrante no hereda nada**: necesita engagement y grants nuevos y explícitos.
- La **empresa puede obtener un paquete de portabilidad** versionado, con alcance explícito, manifiesto y hash, y TTL corto.
- El **export se revalida dos veces**: al crearlo y al descargarlo. Un enlace vigente criptográficamente no basta si la autorización cambió.
- El paquete **no incluye companies vecinas**. El portafolio se calcula desde la lista autoritativa, empresa por empresa.
- **Acceso histórico no equivale a propiedad.** Que una firma haya operado una company no le concede titularidad sobre su información.

Este apartado depende directamente de `UD-ISSUED-CONTEXT`: sin una entidad canónica de
contexto emitido, la revalidación online de enlaces y exports no tiene dónde apoyarse.

---

## 11. Derechos y solicitudes

Workflows candidatos, **todos pendientes de Legal**. No se promete que apliquen igual a
todas las categorías de sujeto ni a todas las jurisdicciones: `applicability_state` es
`pending_legal_by_category_and_jurisdiction`.

| ID | Workflow | Assurance del solicitante |
|---|---|---|
| `RW-ACCESS` | Consulta o acceso | AAL2 |
| `RW-RECTIFY` | Corrección | AAL2 |
| `RW-UPDATE` | Actualización | AAL2 |
| `RW-REVOKE` | Revocación de autorización | AAL3 |
| `RW-DELETE` | Supresión | AAL3 |
| `RW-PORTABILITY` | Portabilidad contractual | AAL3 |
| `RW-OBJECT` | Oposición o restricción cuando corresponda | AAL2 |
| `RW-PROOF_OF_AUTHORIZATION` | Prueba de autorización | AAL2 |
| `RW-COMPLAINT` | Incidente o reclamo | AAL2 |

Cada workflow declara: assurance, verificación de autoridad, resolución de alcance,
`sla_state` (`pending_legal`), búsqueda en stores, barrido del registro de destinatarios,
excepciones, formato de respuesta, evidencia, apelación y auditoría.

**Enrutamiento por rol.** Cuando Fincilia actúa como encargado candidato, **no responde
directamente al titular**: enruta al responsable y le da soporte. Responder por cuenta
propia sobre datos que trata por instrucción ajena sería, en sí mismo, un tratamiento sin
base.

---

## 12. Transmisión, transferencia y región

- **A-02 sigue pendiente.** No hay cloud, región ni proveedor elegido en este documento.
- **Usar nube exterior no es automáticamente transmisión ni transferencia.** Son figuras distintas con requisitos distintos, y la calificación se hace **por actividad y por rol**, no por proveedor.
- Existe un **registro de destinatarios** (`recipient_registry`) con ocho candidatos: IdP, correo, push, billing, IA, OCR, conector financiero y cloud. Ninguno está seleccionado.
- Cada destinatario externo declara `contract_state`, `region_state`, `role_state`, `deletion_support_state`, `rights_support_state`, `subprocessor_disclosure_state`, `security_assessment_state` y `egress_default: deny`. El validador exige que ninguno esté aceptado.
- **Egress deny-by-default.** Los workers no tienen salida a internet; el único camino autorizado sería el gateway.
- **IA y OCR externos deshabilitados hasta L-02.**
- **«El proveedor es compliant» no sustituye una evaluación jurídica.** Una certificación del proveedor no determina el rol de las partes, la base del tratamiento ni el régimen de transmisión aplicable.

---

## 13. Inteligencia artificial

`external_ai_enabled: false` durante E0. Cada actividad declara además su propio bloque
`external_ai` con `enabled: false`, `gateway_required: true`, `minimization_required: true`
y `fail_closed: true`.

Condiciones que deberían cumplirse **antes** de siquiera plantear habilitarla:

- **El AI Gateway es la única ruta.** No hay llamada directa desde un worker ni desde el cliente.
- **Prohibido el documento raw completo por defecto.** Se envía la región mínima necesaria.
- **Redacción y minimización fail-closed.** Si el redactor no está disponible, no hay egreso. Nota heredada de FNC-SEC-001: ese redactor es a su vez un modelo, así que debe tener detección determinística primero, umbral de recall publicado y prohibición de retirar detecciones.
- **No-training contractual.** Los datos del cliente no entrenan modelos del proveedor.
- **Región y subencargados pendientes.**
- **Prompts y outputs no son logs libres.** Muestreo saneado, restringido y con retención corta.
- **No se entrenan plantillas ni modelos con datos de clientes** sin consentimiento, base jurídica, contrato y gate propios.
- **El feedback y las etiquetas humanas son una finalidad nueva**, no la continuación de la anterior. Un clic no es una autorización de entrenamiento.
- **La salida del modelo es una propuesta**, nunca una decisión financiera. Un LLM no autoriza, no calcula dinero, no confirma matches y no cierra periodos.
- **Kill switch** por tenant, modelo, caso y proveedor; auditoría y versionado de política.

---

## 14. Móvil y web

- **Sin raw persistente en el dispositivo** después de confirmar el upload.
- **Secure storage solo para referencia de sesión y estado mínimo**, nunca para verdad financiera.
- **Push sin montos, cuentas, NIT ni descripciones financieras.** La notificación dice que hay una tarea; no dice cuánto ni de quién.
- **Clipboard, capturas de pantalla, backups del sistema operativo y archivos descargados** entran en el análisis: son rutas de salida que el producto no controla del todo y que deben documentarse ante el usuario.
- **URLs firmadas cortas**, de un solo alcance y revalidadas server-side.
- **Browser storage sin verdad financiera** ni tokens de larga vida.
- **Cierre de sesión y revocación limpian la caché local**, incluido el contexto de company.
- **Mapeo complejo y exports masivos permanecen en web** inicialmente: son operaciones que exigen evidencia visible y pantalla grande.

---

## 15. Incidentes

Sin inventar plazos legales. La secuencia operativa es:

1. **Detectar** y registrar `detected_at`, `aware_at` y `confirmed_at` por separado.
2. **Contener** sin destruir evidencia.
3. **Clasificar** severidad y alcance.
4. **Preservar evidencia** en `security_archive`.
5. **Identificar companies y sujetos** afectados, empresa por empresa.
6. **Evaluar el deber de notificación** — decisión de Legal, no de ingeniería.
7. **Coordinar Responsable y Encargado** según el rol de cada actividad implicada.
8. **Notificar** según la decisión de Legal.
9. **Remediar**.
10. **Reconciliar borrado y logs**: un incidente puede haber generado copias no inventariadas.
11. **Postmortem** sin culpa, con acciones, owner y fecha.

El plazo concreto ante autoridad y la calificación de «incidente notificable» quedan
`pending_legal`. Ningún SLA interno amplía ni sustituye un plazo legal.

---

## 16. Disparadores de DPIA/PIA

| ID | Disparador | Gate |
|---|---|---|
| `DPIA-01` | IA u OCR externo habilitado | L-02 |
| `DPIA-02` | Nuevo conector o fuente de datos | DRG-01 |
| `DPIA-03` | Nueva región o proveedor cloud | A-02 |
| `DPIA-04` | Biometría o passkeys | S1-READY |
| `DPIA-05` | Scoring o anomalías sobre personas naturales | DRG-01 |
| `DPIA-06` | Monitoreo de productividad de empleados | GA-01 |
| `DPIA-07` | Tratamiento de alto volumen de datos personales | DRG-01 |
| `DPIA-08` | Datos de terceros que no son usuarios | DRG-00 |
| `DPIA-09` | Nuevo subencargado | DRG-01 |
| `DPIA-10` | Combinación de fuentes que habilita una inferencia nueva | DRG-01 |
| `DPIA-11` | Acceso de soporte a evidencia raw | DRG-01 |
| `DPIA-12` | Export masivo o multiempresa | S1-READY |
| `DPIA-13` | Entrenamiento o evaluación con datos no sintéticos | DRG-00 |

`DPIA-06` merece una nota: el producto mide productividad del equipo de la firma
(`PA-20`). Eso es tratamiento de datos de actividad laboral de personas naturales y no
puede tratarse como una métrica de producto neutra.

---

## 17. Gates

| Gate | Alcance | Estado | Owner |
|---|---|---|---|
| `S1-READY` | Habilita Sprint 1 interno | `not_met` | Integration Steward |
| `DRG-00` | Solo corpus real de investigación | `not_met` | Legal |
| `DRG-01` | Piloto con datos financieros reales | `not_met` | Legal |
| `GA-01` | Venta general | `not_met` | Product |
| `L-01` | Matriz de retención y borrado | `not_met` | Legal |
| `L-02` | Base jurídica de IA y OCR externos | `not_met` | Legal |
| `A-02` | Cloud, región y transmisión | `not_met` | Architecture |
| `S-01` | Preparación de seguridad para datos reales | `not_met` | Security |

**Ninguno está superado.** Ningún agente los firma.

---

## 18. Verificación

```bash
python -m tools.privacy_model.validate
python -m unittest tools.privacy_model.test_validate -v
```

El validador comprueba treinta familias de reglas sobre el modelo, incluyendo cobertura
de `F01`–`F13`, de todos los stores del DFD, de todas las políticas de retención usadas
por el DFD y de los riesgos `TM-005`, `TM-010`, `TM-011`, `TM-012` y `TM-014`; ausencia de
clase `prohibited`; `secret` solo en `vault`; scope de company verificado para
`financial_sensitive`; estado contractual completo de destinatarios externos; IA externa
desactivada; ninguna base legal aceptada; cero duraciones numéricas; delete ledger fuera
del restore; reaplicación de tombstones; máquina de estados de borrado sin atajos;
independencia entre owner y revisor; y existencia real de las rutas de evidencia.
