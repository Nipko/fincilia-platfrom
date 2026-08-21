# Plan maestro de producto, arquitectura y operación

## Plataforma de conciliación y cierre financiero basada en evidencia

**Versión:** 1.0-rc1 — candidata congelada para revisión externa  
**Fecha del documento:** 21 de agosto de 2026  
**Fecha de corte de investigación:** 21 de agosto de 2026  
**Estado:** preconstrucción; decisiones propuestas, no compromisos irreversibles  
**Mercado inicial:** Colombia, con arquitectura preparada para expansión latinoamericana  
**Audiencia:** fundadores, producto, diseño, ingeniería, datos, seguridad, contabilidad, legal y agente revisor externo

---

## Mapa del documento

1. Estrategia, problema, segmentos, objetivos y límites.
2. Producto funcional completo: firma, importación, conciliación, cierre, riesgo, informes y móvil.
3. Arquitectura: componentes, celdas, bases, archivos, cachés, procesamiento, linaje e integraciones.
4. Seguridad, privacidad, identidad, roles, auditoría, incidentes y proveedores.
5. Gobierno de IA: casos permitidos, prohibidos, umbrales, gateway y evaluación.
6. Operación: SLO, observabilidad, calidad, entrega, build/buy y escala.
7. Tres planes, overages, unit economics, pilotos y validación.
8. Programa de 15–18 meses, equipo, gates y artefactos.
9. KPIs, riesgos, definición de producto completo y preguntas abiertas.
10. Evidencia, referencias y control de revisiones.

## 0. Cómo usar este documento

Este plan describe la visión completa del producto y su arquitectura objetivo. No es únicamente un alcance de MVP. La implementación se divide en etapas para controlar riesgo, pero cada etapa debe ser compatible con el sistema final.

Las decisiones se clasifican así:

- **Decidido:** debe preservarse salvo evidencia nueva.
- **Propuesto:** dirección recomendada que debe validarse mediante prototipo, prueba técnica o revisión externa.
- **Condicionado:** solo se adopta cuando se alcanza un umbral explícito.
- **Pendiente:** requiere una decisión comercial, jurídica o técnica antes de producción.

Este documento no reemplaza:

- Concepto jurídico sobre protección de datos, retención documental, integraciones bancarias o DIAN.
- Threat model detallado por componente.
- Especificaciones funcionales por épica.
- ADRs —registros de decisión arquitectónica—.
- Contratos de API y esquemas físicos de base de datos.
- Presupuesto financiero aprobado.

### 0.1 Decisiones que el revisor debe desafiar

1. Si el primer cliente económico debe ser la PYME o la firma contable.
2. Si el monolito modular con workers es la mejor base para el equipo disponible.
3. Si PostgreSQL puede permanecer como fuente operacional durante los primeros 24 meses.
4. Si los umbrales propuestos para automatización son suficientemente conservadores.
5. Si la separación de funciones web/móvil es correcta.
6. Si los tres planes comerciales son comprensibles y sostenibles.
7. Si el programa de 15–18 meses es compatible con equipo, capital y capacidad comercial.

### 0.2 Gate para aceptar datos financieros reales

**DRG-01 — Data Real Gate:** está prohibido recibir datos no anonimizados hasta aprobar y adjuntar evidencia de:

- Región, transferencias internacionales y subencargados.
- Roles Responsable/Encargado y DPA.
- Política de retención, legal hold, borrado y backups.
- Alcance PCI y rechazo/redacción de PAN o credenciales prohibidas.
- Threat model y pruebas cross-tenant.
- Cuarentena, antimalware, sandbox y límites de archivo.
- Minimización de auditoría y logs.
- Backup, restore y reconciliación de manifiestos.
- Respuesta a incidentes y matriz de notificación.
- Due diligence de todo proveedor que reciba datos.

Dueños: Legal, Security y Product. Los tres deben aprobar. Este gate es independiente de ventas o del calendario de ingeniería.

Registro de decisiones obligatorio:

| ID | Decisión | Estado | Dueño | Evidencia | Fecha límite | Gate afectado |
|---|---|---|---|---|---|---|
| DRG-01 | Aceptar datos no anonimizados | Pendiente | Legal/Security/Product | Checklist firmado | Antes del primer piloto real | Datos reales |
| L-01 | Retención por clase | Pendiente | Legal/Privacy | Matriz aprobada | Antes de Fase 1 productiva | Datos reales |
| A-01 | Stack de dominio | Propuesto | Engineering | ADR y spike | Antes del Sprint 1 | Construcción |
| AI-EDGE-01 | IA ligera en dispositivo | Condicionado | Mobile/ML/Security | POC, licencia y benchmark propio | Antes de habilitarla en producción | IA/móvil |
| C-01 | Precios públicos | Hipótesis | Product/Finance | Pilotos y COGS | Antes de GA | Comercial |

Ninguna fase comienza con un pendiente que bloquee su gate. El estado debe ser `Decidido`, `Propuesto`, `Condicionado` o `Pendiente`, con evidencia enlazada.

---

# Parte I — Estrategia de producto

## 1. Tesis y definición

### 1.1 Definición del producto

> Plataforma SaaS de conciliación y cierre financiero para PYMEs y firmas contables que recibe datos de fuentes heterogéneas, conserva su evidencia, los entiende y limpia, los normaliza, los concilia, identifica inconsistencias, coordina revisiones y produce un cierre reproducible.

La aplicación móvil acompaña a la plataforma web para capturar soportes, responder solicitudes, recibir alertas y tomar decisiones sencillas.

### 1.2 Promesa central

> Convertir datos financieros desordenados en decisiones conciliadas, explicables y auditables, sin obligar a la empresa a reemplazar su ERP o sistema contable.

### 1.3 Principios no negociables

1. **Toda cifra vuelve a su origen.** Archivo, página, hoja, fila, columna, celda, campo XML o transacción API.
2. **El original nunca se altera.** Limpiar produce una nueva versión.
3. **Desconocido es un estado válido.** El sistema no inventa certeza.
4. **La automatización debe mostrar evidencia.** No hay decisiones importantes de caja negra.
5. **La IA propone; las reglas validan; las personas certifican.**
6. **La firma ve su portafolio; cada empresa conserva su aislamiento.**
7. **Web para investigar; móvil para capturar y decidir.**
8. **Los archivos son un canal permanente.** No una solución provisional mientras llegan APIs.
9. **Seguridad y privacidad no dependen del plan pagado.** Los planes varían por escala, automatización y servicio.
10. **No somos un ERP ni un iniciador de pagos.** La neutralidad es parte del valor.

## 2. Problema y oportunidad

Las PYMEs y sus contadores reciben extractos, liquidaciones de pasarela, reportes de ventas, facturas, archivos del ERP, hojas de cálculo y soportes con formatos diferentes. El trabajo se fragmenta entre correo, Excel, portales, mensajería y el sistema contable.

El problema no termina al comparar dos tablas. El proceso completo es:

```text
Recibir → identificar → limpiar → normalizar → conciliar
        → investigar → aprobar → cerrar → informar → conservar evidencia
```

Las suites contables cubren partes de ese flujo dentro de su propio ecosistema. Alegra, por ejemplo, publica panel multiempresa, calendario, roles, conciliación y funciones DIAN para contadores. Esto valida la demanda, pero convierte esas capacidades en requisitos de entrada, no en una diferenciación suficiente: <https://www.alegra.com/colombia/contadores/>.

El espacio defendible es una capa neutral que una:

- Bancos colombianos y, progresivamente, latinoamericanos.
- Pasarelas, datáfonos y billeteras.
- Marketplaces y plataformas de ecommerce.
- Facturación electrónica y documentos DIAN.
- Siigo, Alegra, Odoo y otros ERP mediante acuerdos y APIs autorizadas.
- CSV, XLSX, OFX, MT940, ISO 20022, XML, PDF e imágenes.

## 3. Segmentos y cliente inicial

### 3.1 Segmentos

| Segmento | Dolor | Comprador | Usuario diario | Prioridad |
|---|---|---|---|---|
| PYME multicanal | Dinero sin explicar, fees y cierres lentos | Dueño / gerente financiero | Auxiliar / contador | Alta |
| Firma contable | Muchos clientes, archivos tardíos, carga dispersa | Socio / director | Preparadores y revisores | Muy alta |
| BPO financiero | Volumen, controles, SLA y auditoría | Director de operaciones | Equipos por cuenta | Media-alta |
| Empresa mediana | Integraciones y segregación | CFO / controller | Tesorería y contabilidad | Fase posterior |
| Corporativo | Personalización, aislamiento y compliance | Procurement / CFO | Equipos especializados | No foco inicial |

### 3.2 ICP inicial propuesto

- Comercio, ecommerce, servicios de recaudo o retail.
- Entre 500 y 50.000 movimientos mensuales.
- Dos o más canales de cobro.
- Al menos una cuenta bancaria y una pasarela.
- Contabilidad en Siigo, Alegra, Odoo o Excel.
- Cierre mensual con trabajo manual recurrente.
- El contador administra cinco o más empresas, o la PYME dedica al menos 20 horas al mes a conciliación.

### 3.3 Primer caso vertical

```text
Pedido o factura
↔ pago en pasarela / datáfono / billetera
↔ comisión, retención, devolución o contracargo
↔ liquidación
↔ abono bancario
↔ exportación o asiento en el sistema contable
```

## 4. Objetivos y exclusiones

### 4.1 Objetivos de negocio

- Reducir al menos 50% el tiempo total de conciliación y cierre.
- Hacer económicamente viable que una firma atienda más empresas por contador sin perder control.
- Construir una distribución B2B2B mediante firmas contables.
- Mantener margen bruto objetivo de 75–85% una vez estabilizado el producto.
- Convertir recetas, reglas, integraciones e históricos en costos de cambio legítimos, con portabilidad garantizada.

### 4.2 Objetivos de producto

- Importar información financiera conocida y desconocida con trazabilidad.
- Automatizar coincidencias de alta certeza.
- Concentrar las excepciones en una bandeja accionable.
- Formalizar ciclos, responsabilidades, revisiones y cierres.
- Exponer anomalías e inconsistencias con evidencia.
- Permitir colaboración segura entre firma y cliente.
- Producir informes y exportaciones reproducibles.

### 4.3 Fuera de alcance estratégico

- Custodia de fondos o iniciación de pagos en la primera línea de producto.
- Almacenamiento de credenciales bancarias, PAN, CVV o contraseñas DIAN.
- Libro contable o ERP general completo.
- Nómina, inventario, facturación o impuestos como productos autónomos.
- Contabilización o cierre autónomo por un LLM.
- Editor general de hojas de cálculo.
- Acusaciones automáticas de fraude.
- Scraping de portales que viole términos o requiera custodiar credenciales.
- Promesa de interpretar perfectamente cualquier PDF.

---

# Parte II — Producto funcional completo

## 5. Arquitectura funcional

```text
Firma / workspace
├── Portafolio multiempresa
├── Calendario y ciclos
├── Bandeja de tareas, excepciones y riesgo
├── Equipo, roles y carga de trabajo
├── Plantillas y recetas compartidas
├── Informes consolidados
├── Facturación y uso
├── Auditoría y seguridad
│
└── Empresa
    ├── Resumen
    ├── Fuentes y conexiones
    ├── Archivos y documentos
    ├── Estudio de Importación
    ├── Registros normalizados
    ├── Conciliación
    ├── Excepciones e investigaciones
    ├── Ciclos y cierres
    ├── Históricos e informes
    └── Configuración
```

## 6. Módulos y requisitos

### 6.1 Identidad, firma y empresas

- Crear una firma, grupo o empresa independiente.
- Crear y archivar empresas cliente sin borrar históricos.
- Asignar responsables y equipos por empresa.
- Mantener selector de empresa visible y contexto visual permanente.
- Invitar usuarios internos, clientes, auditores y cuentas de integración.
- Revocar acceso, sesiones y dispositivos.
- Administrar plan, consumo, facturas y entitlements.
- Soportar una persona con membresías diferentes en varias firmas.

### 6.2 Portafolio multiempresa

Debe contestar primero “¿dónde debo intervenir?”.

Indicadores:

- Empresas al día, en riesgo y vencidas.
- Fuentes faltantes o atrasadas.
- Porcentaje conciliado y monto sin explicar.
- Excepciones por severidad y antigüedad.
- Ciclos listos para revisión.
- Carga por preparador y revisor.
- Alertas críticas.
- Volumen y tiempo de cierre por empresa.

Acciones masivas autorizadas:

- Asignar responsable.
- Cambiar fecha interna.
- Enviar recordatorio agrupado.
- Solicitar documentos.
- Exportar estado del portafolio.

No se permitirán aprobaciones financieras masivas sin mostrar empresa, periodo, monto y evidencia.

### 6.3 Fuentes e integraciones

Tipos de fuente:

- Archivo manual.
- Buzón de correo dedicado.
- Cámara o carga móvil.
- SFTP o almacenamiento del cliente.
- API y webhook.
- Agregador bancario.
- Integración directa con banco, pasarela, marketplace o ERP.

Cada fuente tendrá:

- Empresa y cuenta asociadas.
- Responsable.
- Frecuencia esperada.
- Zona horaria y moneda.
- Método de autenticación.
- Alcances consentidos.
- Estado, frescura y última sincronización.
- SLA y salud de conexión.
- Historial de cambios.
- Política de retención.

### 6.4 Gestión de archivos y documentos

Capacidades:

- Carga individual y masiva.
- Drag and drop, correo, móvil, SFTP y API.
- Detección del formato por firma real y MIME, no solo extensión.
- Hash SHA-256 y control de duplicados.
- Antivirus, cuarentena y límites de expansión de ZIP.
- Estado de procesamiento y reintento idempotente.
- Vista, descarga y eliminación según permisos y retención.
- Versiones y relación entre original, extracción, limpio y exportación.
- Manifiesto con origen, parser, receta, usuario, fecha y conteos.

La carga recomendada es directa desde el cliente hacia cuarentena mediante una sesión autorizada y URL firmada de uso corto. El archivo no atraviesa el servidor web ni recibe credenciales de almacenamiento. Cada carga usa una clave nueva y opaca; nunca se reutiliza el nombre del usuario para sobrescribir un objeto.

Familias prioritarias:

- CSV y variantes regionales.
- XLSX sin ejecución de macros.
- OFX 2.x.
- XML UBL/DIAN.
- MT940 e ISO 20022 `camt.053`.
- PDF con texto nativo.
- PDF escaneado e imagen mediante flujo asistido.

### 6.5 Estudio de Importación

Flujo:

```text
Subir → detectar → seleccionar estructura → mapear → limpiar
      → validar → comparar → guardar receta → publicar
```

Vistas:

1. Original: página, hoja, XML o registro fuente.
2. Extracción fiel: celdas, tokens y coordenadas.
3. Dataset limpio: transformaciones y errores.
4. Esquema canónico: campos financieros de destino.
5. Calidad: válido, vacío, error, desconocido y distribución.

Interacciones:

- Marcar fila de encabezado y rango de datos.
- Seleccionar tabla o región de PDF.
- Excluir títulos, subtotales y pies.
- Identificar saldo inicial/final y totales de control.
- Corregir columnas, filas y celdas.
- Mostrar origen al seleccionar un valor transformado.
- Comparar antes/después y deshacer cualquier paso.
- Guardar receta por empresa, fuente y versión de plantilla.
- Detectar `schema drift` y suspender aplicación automática.

Transformaciones iniciales y avanzadas:

- Trim, Unicode y caracteres invisibles.
- Quitar, mantener, renombrar y reordenar.
- Separar, unir, transponer y rellenar hacia abajo.
- Regex y mapeo de valores.
- Normalización de fecha, zona horaria, moneda y locale.
- Débito/crédito a importe con dirección explícita.
- Dedupe y filtro.
- Columna derivada con funciones determinísticas.
- Redacción de información sensible.
- Corrección manual como overlay, con autor y motivo.

La experiencia tomará como referencia el perfil de columnas de Power Query y la historia reversible de OpenRefine, sin exponer lenguajes técnicos al usuario: <https://learn.microsoft.com/en-us/power-query/data-profiling-tools> y <https://openrefine.org/docs/manual/transforming>.

### 6.6 Inferencia y clasificación

Capas independientes de confianza:

1. Formato técnico.
2. Familia documental.
3. Emisor y versión de plantilla.
4. Tabla o región.
5. Tipo físico.
6. Semántica financiera.
7. Empresa, cuenta y periodo.

Tipos semánticos:

- Fecha y fecha/hora.
- Importe, moneda, débito, crédito y saldo.
- NIT, cuenta, factura y referencia.
- Contraparte, canal y estado.
- Bruto, comisión, retención, impuesto y neto.
- Pago, devolución, contracargo y liquidación.

Toda inferencia debe incluir:

- Valor sugerido.
- Confianza calibrada.
- Razones y validaciones.
- Ambigüedades.
- Alternativas.
- Posibilidad de corrección.

### 6.7 Modelo financiero normalizado

El modelo no será una mega-tabla. Entidades principales:

- `obligation`: factura, pedido, nota y saldo pendiente.
- `money_movement`: pago, débito, crédito, fee, refund y chargeback.
- `settlement`: agrupación de pagos, descuentos y neto abonado.
- `ledger_entry` y `ledger_line`: asiento importado o exportado.
- `counterparty` y `financial_account`.
- `external_reference`.
- `match_group`, `match_member` y `match_decision`.
- `exception`, `anomaly_signal` e `investigation_case`.

Reglas de datos:

- Importes en decimal exacto, nunca `float`.
- Moneda ISO 4217.
- Monto positivo más dirección explícita cuando sea posible.
- UTC más zona horaria original.
- Identificador original y normalizado.
- Últimos cuatro dígitos o token para cuentas cuando baste.
- `exchange_rate`: moneda base/cotizada, tasa decimal, proveedor, fecha/hora efectiva, zona, versión y política de redondeo.
- Todo match multimoneda conserva importes originales, moneda funcional, tasa utilizada y diferencia FX separada; una tasa nunca se infiere silenciosamente.
- Linaje por campo hasta el origen.
- Identificadores inmutables y versiones para correcciones.

### 6.8 Conciliación

Casos:

- 1:1, 1:N, N:1 y N:M acotado.
- Parciales.
- Liquidación neta.
- Comisiones, impuestos y retenciones.
- Devolución, reverso y contracargo.
- Tolerancia de fecha, moneda o redondeo.
- Diferencias aceptadas con motivo.

Secuencia:

1. Filtros duros de empresa, moneda, dirección y saldo disponible.
2. IDs únicos exactos.
3. Reglas versionadas por fuente.
4. Candidatos por importe, fecha, referencia y contraparte.
5. Combinaciones acotadas.
6. Ranking explicable.
7. Revisión, aprobación, rechazo o reversión.

Estados:

```text
sin evaluar → propuesto → confirmado → rechazado → revertido
```

Una decisión nunca se borra. Se revierte con actor, motivo y nueva versión.

### 6.9 Excepciones y colaboración

- Bandeja única con filtros por empresa, periodo, fuente, monto, antigüedad y responsable.
- Asignación y SLA.
- Comentarios, menciones y archivos de soporte.
- Solicitud al cliente desde web y respuesta desde móvil.
- Motivos normalizados y texto libre complementario.
- Resolución masiva solo para excepciones homogéneas y de bajo riesgo.
- Conversión de excepción en regla únicamente después de simulación histórica.

### 6.10 Ciclos, recordatorios y cierre

Estados:

```text
planificado → recopilando → procesando → conciliando
            → en revisión → cerrado → reabierto
```

Cada ciclo define:

- Periodicidad y fechas.
- Fuentes y documentos esperados.
- Checklist y dependencias.
- Preparador y revisor.
- Tolerancias y umbral de cierre.
- Escalamiento y canales.
- Horario silencioso.

Los recordatorios serán orientados a estado:

- Falta fuente o documento.
- La conexión perdió frescura.
- Existen excepciones envejecidas.
- Hay una alerta crítica sin revisar.
- El ciclo está listo para aprobación.
- Se modificó evidencia después del cierre.

Cerrar genera un snapshot inmutable de datos, reglas, decisiones, archivos e informes. Reabrir exige permiso, motivo y nueva aprobación.

### 6.11 Riesgo e inconsistencias

El producto no etiqueta fraude como hecho. Genera señales para investigación.

Clases:

- Integridad: duplicados, faltantes, discontinuidad de saldo, totales incorrectos y cambio de esquema.
- Financiera: fee fuera de rango, payout sin ventas, venta sin abono, refund duplicado y atraso.
- Contraparte: beneficiario o cuenta nuevos, cambio abrupto o referencia incompatible.
- Proceso: demasiados overrides, documento sustituido, reaperturas repetidas y violación de segregación.
- Acceso: exportación masiva, dispositivo nuevo, actividad privilegiada inusual y acceso de soporte.

Cada señal incluye:

- Severidad.
- Confiabilidad.
- Exposición financiera.
- Evidencias y baseline.
- Acción sugerida.
- Responsable y estado.
- Resultado: confirmado, legítimo, error, falso positivo o escalado.

### 6.12 Históricos, analítica e informes

Informes operativos:

- Estado de conciliación.
- Dinero sin explicar.
- Excepciones y aging.
- Calidad por fuente.
- Fees y retenciones.
- Estado del portafolio.
- Cumplimiento de ciclos y SLA.
- Productividad del equipo.

Informes de control:

- Paquete de cierre.
- Trazabilidad de cada match.
- Cambios de reglas y recetas.
- Accesos, descargas y exportaciones.
- Hallazgos y resoluciones.
- Reaperturas y overrides.

Salidas:

- Vista interactiva con drill-down.
- CSV y XLSX.
- PDF versionado.
- Enlace de solo lectura con expiración.
- Envío programado.
- API y webhook.

### 6.13 Aplicación móvil

Incluye:

- Selector de empresa.
- Tareas y recordatorios.
- Cámara y carga de archivos.
- Confirmación de clasificación sencilla.
- Respuesta a solicitudes.
- Alertas y evidencia resumida.
- Aprobar, rechazar, comentar o pedir información.
- Estado ejecutivo y monto pendiente.
- Biometría, revocación de dispositivo y borrado local.

Excluye:

- Mapeo de tablas grandes.
- Construcción de recetas complejas.
- Conciliación masiva.
- Configuración de conectores.
- Constructor de informes.

### 6.14 Administración, soporte y facturación

- Gestión de entitlements separada del código de interfaz.
- Modelo explícito `Plan`, `Entitlement`, `Limit`, `Subscription`, `UsageEvent` y `OveragePolicy`; no condicionales dispersos en UI.
- Medición transparente por empresa activa, `source_record_published`, páginas OCR, conectores y almacenamiento.
- Alertas unificadas al 70%, 90% y 100%, con proyección, periodo de gracia y ledger visible.
- Estado de plataforma y conectores.
- Exportación de datos al terminar contrato.
- Downgrade con modo lectura temporal; nunca secuestrar evidencia.
- Acceso de soporte just-in-time, aprobado, limitado y auditado.

---

# Parte III — Arquitectura técnica objetivo

## 7. Principios arquitectónicos

1. Monolito modular para el dominio transaccional; workers aislados para archivos, OCR y cómputo.
2. Asincronía para todo proceso potencialmente pesado.
3. PostgreSQL como fuente de verdad operacional.
4. Almacenamiento de objetos como fuente de evidencia binaria.
5. Caché nunca autoritativa.
6. Formatos abiertos y exportables.
7. Idempotencia, versionado y linaje en todo el pipeline.
8. Separación estricta por ambiente y empresa.
9. Servicios adicionales solo cuando una métrica lo justifique.
10. Proveedores intercambiables para OCR, IA, correo y conectividad.

## 8. Vista de componentes

```text
Usuarios web / app / integraciones
                │
          CDN + WAF + API gateway
                │
   ┌────────────┴──────────────────────────────┐
   │ Aplicación modular                        │
   │ identidad · firmas · permisos · fuentes  │
   │ ciclos · conciliación · riesgo · billing │
   └────────────┬──────────────────────────────┘
                │
      PostgreSQL operacional
                │ transactional outbox
                ▼
         Cola / orquestación
                │
 ┌──────────────┼───────────────┬───────────────┐
 │ parsers      │ OCR/IA        │ matching      │ reporting
 │ workers      │ workers       │ workers       │ workers
 └──────┬───────┴──────┬────────┴──────┬────────┘
        │              │               │
 Object storage      Redis/Valkey    Parquet analítico
 raw/derived/export  caché/locks     + warehouse condicional
```

### 8.1 Stack de referencia propuesto

| Capa | Decisión propuesta | Alternativa condicionada |
|---|---|---|
| Web | TypeScript, React y Next.js | Ninguna sin ADR |
| Móvil | React Native | Nativo solo por requisito demostrado |
| Dominio/control | NestJS/TypeScript como monolito modular | FastAPI si el equipo inicial es ≤4 y predominantemente Python |
| Workers de datos | Python, Polars, DuckDB y Arrow | Runtime especializado por parser si se justifica |
| Contratos | OpenAPI y JSON Schema | Protobuf para alto volumen interno posterior |
| Contenedores | Servicio administrado tipo ECS/Fargate | Kubernetes solo con umbral operacional |
| Infraestructura | Terraform u OpenTofu | Herramienta equivalente aprobada por ADR |

La decisión TypeScript/Python debe cerrarse antes del primer sprint mediante ADR basado en experiencia del equipo. La propiedad intelectual no dependerá del framework: contratos, modelo canónico y eventos deberán aislar runtimes.

### 8.2 Arquitectura por celdas

El producto inicia con una sola celda de datos, pero el plano de control mantendrá desde el comienzo un catálogo de enrutamiento:

```text
tenant_id → region_id → cell_id → database_id → storage_namespace → key_id
```

Una celda contiene PostgreSQL, namespace de objetos, caché, colas/workflows y workers de un grupo de tenants. Esto permite trasladar un tenant a otra celda, ofrecer aislamiento dedicado y reducir el radio de impacto sin convertir cada módulo en microservicio.

Crear una nueva celda cuando:

- Un tenant consume sostenidamente 15–20% de capacidad compartida.
- Existe requisito contractual de aislamiento, residencia, clave, RPO o mantenimiento.
- Aparece un problema de vecino ruidoso no corregible con cuotas.
- La región o expansión comercial lo exige.

No se usará un esquema ni una base por cada PYME. Una celda dedicada es excepción comercial/técnica, no el modelo estándar.

## 9. Planos de datos

### 9.1 Plano de control

Contiene:

- Firma, empresa, membresía y rol.
- Entitlements y consumo.
- Fuentes, conexiones y secretos referenciados.
- Configuración, flags y versiones.
- Jobs, estados y programaciones.

En la primera celda, control y datos son límites lógicos dentro del mismo cluster. Al crear una segunda celda, el control global conserva identidad, membresías, entitlements y enrutamiento como fuente de verdad; cada celda recibe una proyección versionada de grants. La API autoriza la empresa solicitada contra membresía vigente y emite contexto interno firmado con `policy_version`; la celda falla cerrada ante versión inválida/revocada. No habrá transacciones distribuidas entre control y celdas.

### 9.2 Plano financiero

Contiene:

- Documentos y datasets.
- Obligaciones, movimientos y liquidaciones.
- Matches, excepciones y cierres.
- Señales e investigaciones.
- Informes y snapshots.

### 9.3 Plano de evidencia

Contiene:

- Archivo original.
- Extracción fiel.
- Dataset limpio.
- Exportaciones y manifiestos.
- Hashes y digest de auditoría.

### 9.4 Plano analítico

Contiene copias derivadas y versionadas para:

- Históricos.
- Tendencias.
- Simulación de reglas.
- Evaluación de modelos.
- Informes de portafolio.

Nunca se utiliza para autorizar una acción o reemplazar el dato operacional.

## 10. Estrategia de almacenamiento

### 10.1 Matriz de tecnologías

| Tecnología | Propósito | Sí almacena | No debe almacenar | Momento |
|---|---|---|---|---|
| PostgreSQL administrado | Fuente operacional | Configuración, metadatos, finanzas normalizadas, decisiones, auditoría indexada | Archivos binarios grandes | Desde el inicio |
| Object storage S3-compatible | Evidencia y derivados | Originales, extracción, Parquet, exports, digest | Permisos como única fuente | Desde el inicio |
| Redis o Valkey administrado | Velocidad y coordinación efímera | Caché, rate limits, progreso, locks con TTL | Matches, roles, auditoría o saldos autoritativos | Cuando exista más de una instancia o carga real |
| DuckDB + Polars/Arrow | Procesamiento local por job | Datos temporales del archivo en worker aislado | Estado compartido o definitivo | Desde el inicio |
| Parquet | Histórico columnar | Datasets derivados, snapshots y analítica | Decisiones transaccionales | Desde el inicio, sencillo |
| ClickHouse o warehouse gestionado | Analítica de gran volumen | Eventos y hechos denormalizados | Fuente financiera única | Condicionado por umbral |
| PostgreSQL FTS/trigram | Búsqueda inicial | Metadatos y textos permitidos | Archivo binario | Inicial |
| OpenSearch | Búsqueda documental compleja | Índices derivados y minimizados | Original autoritativo | Solo con necesidad probada |
| pgvector | Similitud de plantillas o conocimiento | Embeddings minimizados | Matching financiero autoritativo | Condicionado; sin DB vectorial separada inicialmente |

### 10.2 Zonas de object storage

```text
quarantine/  → archivo recién recibido, sin confianza
raw/         → original validado, inmutable y versionado
extracted/   → tokens, celdas, tablas y cajas
curated/     → datasets limpios y Parquet
exports/     → entregables con expiración
audit/       → manifiestos y digest append-only/WORM
temporary/   → artefactos de job con TTL corto
```

Reglas:

- Bucket, cuenta o prefijo por ambiente.
- Prefijo y política por tenant; ningún path decidido por filename del usuario.
- Cifrado KMS y acceso privado.
- URLs firmadas de corta duración.
- Versioning para originales.
- Object Lock/WORM donde la política de evidencia lo requiera. AWS documenta que Object Lock impide sobrescritura o eliminación durante una retención o legal hold: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html>.
- No aplicar WORM irreversible en cuarentena. Primero aceptar, clasificar y asignar base de retención. Usar governance al madurar controles; compliance solo cuando una obligación validada impida incluso el borrado administrativo.
- Lifecycle hot → infrequent access → archive según uso y contrato.
- Exports y temporales con eliminación automática.
- Restauración de archivo frío visible como proceso asíncrono.

### 10.3 PostgreSQL

Decisiones:

- Una instancia PostgreSQL administrada por celda y ambiente; inicialmente existe una sola celda.
- Todo registro tenant-owned tiene `workspace_id NOT NULL`; solo tablas company-scoped tienen `company_id NOT NULL`. Recursos globales y workspace-only viven separados.
- FK compuesta `(workspace_id, company_id)` impide asociar una empresa a otra firma.
- Row-Level Security con `FORCE ROW LEVEL SECURITY` en tablas sensibles.
- Aplicación/workers no son owner, superuser ni `BYPASSRLS`; migración, backup y break-glass usan identidades separadas.
- Cada request/job abre transacción y establece contexto con `SET LOCAL`; se prohíbe `SET` de sesión en conexiones pooled.
- El token identifica actor/sesión; membresía y autorización vigentes se resuelven server-side. `company_id` solicitado nunca se confía sin validación.
- Constraints, claves e idempotencia en base de datos.
- Réplica de lectura para informes cuando las lecturas compitan con escritura.
- Partición temporal de tablas masivas; evitar una partición por empresa.
- JSONB para payload original acotado y metadatos variables, no para todo el dominio.
- Dinero como `numeric/decimal`; fechas con zona horaria.
- Índices compuestos que comienzan por tenant/empresa en tablas de acceso frecuente.
- Particionar una tabla cuando llegue aproximadamente a 30–50 millones de filas, el mantenimiento de índices se degrade o el patrón temporal lo justifique; no particionar todo por anticipación.

PostgreSQL advierte que owner y superuser pueden eludir RLS, por lo que RLS no se considerará suficiente sin roles correctos y pruebas: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>.

### 10.4 Caché

Usos permitidos:

- Dashboard calculado con TTL corto.
- Estado de progreso de jobs.
- Rate limiting y antifuerza bruta.
- Locks efímeros.
- Catálogos no sensibles.
- Sesiones únicamente si el proveedor de identidad lo requiere y existe alternativa segura.

Controles:

- Key namespace por ambiente, workspace y versión de permisos.
- TTL obligatorio salvo excepción aprobada.
- Invalidación inmediata en cambios de rol o empresa.
- No cachear documentos completos ni secretos.
- Una caída de caché degrada rendimiento, no integridad.
- No usar Pub/Sub como registro durable de eventos.

### 10.5 Procesamiento rápido y en bruto

- Cada job trabaja en contenedor o proceso aislado.
- Disco temporal cifrado y limitado.
- DuckDB/Polars procesa muestras, joins, perfiles y Parquet sin cargar todo en memoria.
- Límites por filas, columnas, páginas, CPU, RAM, tiempo y expansión.
- Workers de parsing sin salida a internet por defecto.
- OCR o modelo externo solo mediante gateway autorizado.
- Borrado seguro del temporal al terminar.
- Resultados publicados únicamente tras validación y transacción de control.

### 10.6 Warehouse analítico

No se incorpora un warehouse complejo por anticipación. Activadores para ClickHouse o servicio equivalente:

- Más de 50 millones de movimientos activos o un histórico mucho mayor que deba consultarse interactivamente.
- Dashboards p95 superiores a dos segundos pese a índices, réplicas y materialized views.
- Consultas analíticas consumen más de 20% del primario o afectan el SLO operacional.
- Necesidad real de agregaciones cross-company autorizadas casi en tiempo real.
- Costo de cómputo PostgreSQL superior al costo total de separar serving analítico.

La migración se realizará con CDC/outbox hacia tablas derivadas. PostgreSQL seguirá siendo fuente operacional.

### 10.7 Búsqueda, vectores y streaming

- PostgreSQL FTS/trigram será la búsqueda inicial.
- OpenSearch se incorpora solo cuando el corpus OCR/documental y los filtros excedan capacidad/latencia demostrada de PostgreSQL.
- `pgvector` se admite para similitud de plantillas o conocimiento autorizado; embeddings nunca son evidencia ni motor principal de matching.
- No se introduce una base de grafos hasta existir un producto real de redes de riesgo.
- Kafka se evalúa cuando existan más de 8–10 consumidores independientes, replay prolongado, CDC masivo o más de 1.000 eventos/s sostenidos. Antes se usa outbox + cola/pub-sub administrados.
- Iceberg/Delta se evalúa con varios escritores, necesidad ACID en el lake, evolución frecuente de esquema o varios terabytes. Parquet con manifiestos basta antes.

## 11. Pipeline y estados

```text
Documento:      received → quarantined → accepted | rejected
ImportJob:      queued → running → waiting_for_mapping | failed | cancelled | completed
DatasetVersion: draft → validated → published → superseded
MatchRun:       queued → running → review_required → completed | failed | cancelled
Period:         planned → collecting → reconciling → review → closed → reopened
```

Un dataset publicado puede participar en varios `MatchRun`. `closed_snapshot` pertenece al periodo, no al job de importación. Parsing, clasificación, perfilado, mapping, transformación y normalización son etapas/checkpoints del `ImportJob`, no estados globales de todos los objetos.

Cada transición registra:

- Job y correlation ID.
- Actor o servicio.
- Entrada y salida versionadas.
- Parser, receta, regla o modelo.
- Métricas y errores.
- Aristas de linaje.

Jobs, mensajes y eventos usan entrega al menos una vez. Los efectos internos son idempotentes y `effectively-once` dentro de una transacción PostgreSQL mediante constraints y claves idempotentes. El outbox también puede reenviar. Todo efecto externo requiere idempotency key del proveedor, ledger local y reconciliación posterior; si el proveedor no ofrece idempotencia, no se reintenta ciegamente.

### 11.1 Orquestación

- Fase 1: cola administrada y estado persistente en PostgreSQL para imports cortos.
- Antes de Fase 2: adoptar Temporal o equivalente para ciclos, aprobaciones, timers, compensaciones y esperas humanas. Diez conectores es un activador de escala, no el gate inicial. Temporal representa workflows durables y reanudables: <https://docs.temporal.io/workflows>.
- No introducir Kafka hasta necesitar múltiples consumidores independientes, replay de alto volumen y operación capaz de mantenerlo; una cola y outbox cubren la primera etapa.

## 12. Linaje, versionado e idempotencia

### 12.1 Localizador de origen

Cada valor publicado enlaza:

- Hash y versión de archivo.
- Página/hoja.
- Fila/columna/celda o bounding box.
- Tag XML o record de API.
- Parser/OCR y versión.
- Receta y paso.
- Campo canónico.
- Match, informe y cierre que lo usaron.

### 12.2 Objetos versionados

- Parser.
- Clasificador.
- Modelo OCR.
- Esquema canónico.
- Plantilla de mapping.
- Receta.
- Regla de conciliación.
- Política de anomalías.
- Prompt/modelo de IA.
- Definición de informe.

Reprocesar crea una nueva versión; nunca reescribe un cierre previo.

### 12.3 Claves idempotentes

- Archivo: `company_id + source_id + sha256`.
- Webhook: `connection_id + provider_event_id`.
- Extracción: `artifact_hash + parser_version`.
- Dataset: `extraction_version + recipe_version`.
- Exportación: `snapshot + report_definition_version`.

Transacciones legítimas idénticas no se eliminan solo por tener igual fecha e importe.

## 13. Integraciones

### 13.1 Orden de conectividad

1. Archivos universales.
2. Buzón de facturas y reportes.
3. Pasarelas con API/webhook estable.
4. Exportación hacia ERP.
5. Lectura desde ERP mediante acuerdos autorizados.
6. Agregador bancario.
7. Integraciones directas de alto valor.

### 13.2 Contrato de conector

Todo conector implementa:

- Autorización y revocación.
- Alcances mínimos.
- Backfill e incremental.
- Idempotencia.
- Pending versus posted.
- Paginación y rate limits.
- Reintento y circuit breaker.
- Webhook firmado y protección de replay.
- Frescura, SLA y estado visible.
- Borrado, portabilidad y logs.
- Mapeo a modelo canónico.
- Sandbox y pruebas contractuales.

### 13.3 DIAN

- Buzón exclusivo/forwarding para ZIP `AttachedDocument` y PDF opcional.
- Parseo UBL, CUFE/CUDE, NIT, totales, impuestos, fechas y estados.
- Original y hash conservados.
- Sin scraping de MUISCA ni custodia de contraseña/certificado.
- Registro o transmisión de eventos DIAN solo mediante alcance jurídico validado o proveedor tecnológico habilitado.

La DIAN documenta el correo de recepción y el contenedor electrónico: <https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/presentacion-recepcion-de-facturas-electronica/>.

### 13.4 API pública y webhooks

- REST versionada y descrita con OpenAPI.
- OAuth2 con scopes por empresa y operación.
- `Idempotency-Key` en comandos.
- Cursor pagination, ETags y optimistic concurrency.
- Cargas, backfills y reportes como jobs asíncronos.
- Límites y errores estables/documentados.
- Sandbox con datos sintéticos.
- Webhooks HMAC con timestamp, nonce, protección de replay, reintento y DLQ.
- Rotación de secretos y reenvío manual auditado.
- SDKs solo después de estabilizar contratos.

### 13.5 Cloud, región y despliegue

Referencia AWS, sustituible mediante ADR:

- CDN/WAF y gateway en el edge.
- Contenedores administrados tipo ECS/Fargate.
- PostgreSQL Multi-AZ administrado.
- Redis/Valkey administrado.
- S3, SQS/EventBridge, KMS y Secrets Manager.
- Temporal Cloud o equivalente antes de Fase 2, cuando comienzan ciclos, timers y esperas humanas durables.
- OpenTelemetry hacia backend administrado.
- Cuenta separada para logs/seguridad y otra para backups.

No comenzar con Kubernetes. Evaluarlo al existir aproximadamente 20–30 componentes desplegables, scheduling especializado, GPU, sidecars obligatorios o un equipo de plataforma capaz de operarlo.

La región debe decidirse con una matriz que incluya latencia desde Colombia, disponibilidad de servicios, transmisión internacional, subencargados, costo de salida y DR. La infraestructura será portable mediante contenedores, PostgreSQL, APIs S3-compatible y OpenTelemetry, pero el producto no intentará operar tres nubes simultáneamente.

Ambientes mínimos y aislados:

- Desarrollo, con datos sintéticos.
- Staging, con corpus saneado.
- Producción.
- Sandbox de integraciones.
- Cuenta/proyecto de seguridad y logs.
- Backups en cuenta/proyecto separado.

Si se selecciona AWS, la disponibilidad de regiones debe verificarse en su catálogo oficial antes del ADR: <https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html>.

---

# Parte IV — Seguridad, privacidad y gobierno

## 14. Clasificación de datos

| Nivel | Ejemplos | Controles mínimos |
|---|---|---|
| Público | Sitio, documentación comercial | Integridad y publicación controlada |
| Interno | Métricas sin PII, roadmap | SSO y mínimo privilegio |
| Confidencial | Empresas, usuarios, configuraciones | Cifrado, RBAC, auditoría |
| Financiero sensible | Movimientos, facturas, cuentas, cierres | Cifrado, ABAC, masking, trazabilidad, export control |
| Secreto | Tokens OAuth, API keys, claves de cifrado | Vault/KMS, rotación, acceso de servicio |
| Prohibido | CVV, credenciales bancarias/DIAN, passwords en texto | No recopilar ni persistir |

### 14.1 Gobierno y responsables

| Función | Responsabilidad |
|---|---|
| Comité de riesgo y seguridad | Riesgo aceptado, prioridades, incidentes graves y proveedores críticos |
| Responsable de seguridad | Arquitectura, vulnerabilidades, controles y respuesta |
| Responsable de protección de datos | Derechos, DPIA, contratos, transferencias y RNBD aplicable |
| Comité de IA | Casos, modelos, datos, evals, límites y retiro |
| Data owner | Finalidad, calidad, sensibilidad y retención de un dominio |
| Model owner | Rendimiento, drift, costos, cambios y rollback |
| Experto contable | Corrección financiera y criterios de revisión |
| Auditor independiente | Accesos, segregación, evidencia y controles críticos |

Cadencia mínima:

- Accesos privilegiados internos: mensual.
- Acceso de clientes: trimestral.
- Proveedores críticos: anual y ante cambio material.
- IA de riesgo alto: cada versión y revisión trimestral.
- Restore: trimestral; DR completo semestral.
- Ejercicio de incidentes: dos veces al año.
- Pentest: antes de apertura comercial y al menos anual.

### 14.2 Mapa normativo inicial — requiere validación jurídica

- Ley 1581 de 2012 para protección de datos personales y derechos de titulares: <https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981>.
- Ley 1266 de 2008 cuando el flujo realmente encaje en información financiera, crediticia, comercial o de servicios; no asumir que toda transacción contable entra automáticamente: <https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?0=&i=34488>.
- Circular SIC 002 de 2024 para tratamiento de datos personales mediante IA y privacidad desde el diseño: <https://sedeelectronica.sic.gov.co/sites/default/files/normativa/Circular%20Externa%20No.%20002%20del%2021%20de%20agosto%20de%202024.pdf>.
- Decreto 0368 de 2026 y desarrollo progresivo de finanzas abiertas: <https://www.superfinanciera.gov.co/publicaciones/10116081/finanzas-abiertas-obligatorias-impulsaran-el-desarrollo-del-sistema-y-la-inclusion-financiera-en-el-pais/>.
- Conservación de libros y papeles de comercio que puede alcanzar diez años, sin extender ciegamente ese plazo a todo dato personal: <https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_20796_2006.htm>.

El producto será Responsable de datos propios de usuarios, seguridad y facturación. Normalmente será Encargado de archivos y transacciones procesados por instrucción de la firma/PYME. Una finalidad propia adicional, entrenamiento global o recepción bajo finanzas abiertas exige un análisis separado.

## 15. Identidad y acceso

### 15.1 Autenticación

- Proveedor de identidad administrado con OIDC.
- MFA obligatorio para roles internos y privilegiados.
- Passkeys preferidas; TOTP como alternativa.
- SSO SAML/OIDC y SCIM para clientes que lo requieran.
- Sesiones y dispositivos revocables.
- Step-up authentication para exportar en masa, cambiar roles, conectar fuentes, reabrir cierres, cambiar retención o borrar.
- Cuentas de servicio sin login interactivo, scopes reducidos y rotación.
- Recuperación de cuenta resistente a ingeniería social.

### 15.2 Roles base

| Rol | Alcance |
|---|---|
| Owner de firma | Gobierno global; sin acceso financiero o a secretos implícito |
| Admin de seguridad | Usuarios, políticas, dispositivos y auditoría |
| Admin de facturación | Plan, consumo y pagos; sin datos financieros por defecto |
| Gerente de portafolio | Empresas asignadas, ciclos, equipo e informes |
| Preparador | Importar, limpiar y proponer |
| Revisor/aprobador | Aprobar, rechazar y cerrar según límites |
| Dueño de PYME | Vista de su empresa, soportes y decisiones autorizadas |
| Colaborador de cliente | Solicitudes y carga limitada |
| Auditor | Solo lectura, evidencia e históricos |
| Cuenta de integración | API por empresa, fuente y operación |

Identidades de plataforma y de cliente pertenecen a dominios de confianza separados. Ningún rol interno se asigna como membresía de cliente ni omite RLS. Soporte recibe un grant JIT ligado a ticket, tenant, empresa, recursos, aprobador, propósito y expiración. Owner y Admin de seguridad requieren un grant de datos separado; autoasignarlo exige step-up, notificación y auditoría y nunca elude segregación.

Antes de Fase 1 debe existir la matriz exhaustiva acción × recurso × rol, incluyendo Owner, portafolio, facturación, integración, transferencia de propiedad, último Owner, baja de usuario y cuentas huérfanas.

### 15.3 Matriz resumida

| Acción | Preparador | Revisor | Dueño PYME | Auditor | Admin seguridad |
|---|---:|---:|---:|---:|---:|
| Cargar y mapear | Sí | Sí | Limitado | No | No |
| Proponer match | Sí | Sí | No | No | No |
| Aprobar decisión propia | Nunca | Solo si no participó en preparación | Según política y sin preparación propia | No | No |
| Cerrar periodo | No | Sí | Coaprobación opcional | No | No |
| Reabrir | No | Con step-up y motivo | Solicitar | No | No |
| Exportar | Según scope | Sí | Su empresa | Según scope | No por defecto |
| Ver auditoría | Limitado | Sí | Su empresa | Sí | Sí |
| Gestionar usuarios | No | No | Usuarios cliente limitados | No | Sí |
| Cambiar retención | No | No | Solicitar | No | Sí + owner |

### 15.4 ABAC y segregación

Además del rol se evalúan:

- Workspace y empresas asignadas.
- Fuente y sensibilidad.
- Estado del periodo.
- Monto y nivel de riesgo.
- Relación preparador/revisor.
- Dispositivo, ubicación y sesión.
- Propósito del acceso.

Reglas mínimas:

- Una misma identidad nunca prepara y aprueba la misma corrección, regla, excepción, match o cierre. Un deny de segregación prevalece sobre la unión de roles.
- En una organización unipersonal, la decisión se registra `autocertificada_sin_revision_independiente`, nunca “revisada”, y se muestra en cierre, informe y auditoría.
- El auto-match determinístico preaprobado se confirma por política, no como autoaprobación humana.
- Cambiar una regla y usarla en el mismo cierre requiere segundo control.
- Soporte no accede sin ticket, aprobación, duración y motivo.
- Facturación no implica acceso financiero.
- Un worker recibe scope por job, no acceso global.

## 16. Aislamiento multitenant

Capas obligatorias:

1. Autorización en API.
2. RLS y constraints en PostgreSQL.
3. IAM/prefijos en object storage.
4. Namespaces de caché.
5. Scopes en colas y workers.
6. Filtros autorizados en analítica.
7. Redacción y tenant ID en observabilidad.
8. Pruebas automáticas de acceso cruzado.

Una vista consolidada de firma agrega únicamente empresas incluidas en la autorización verificada.

## 17. Seguridad de archivos

- Allowlist de tipos y validación de firma/MIME.
- Filename generado por sistema.
- Límite de tamaño, páginas, filas, columnas y compresión.
- Antivirus y, donde aplique, content disarm/reconstruction.
- Protección contra ZIP bombs, XXE, fórmulas CSV, macros y objetos embebidos.
- Parseo en sandbox sin privilegios ni red.
- Archivo privado fuera del webroot.
- Descarga con `Content-Disposition` seguro y URL expirable.
- Cuarentena hasta finalizar controles.
- No renderizar HTML o scripts provenientes del archivo.
- Deduplicación por hash limitada al tenant; una deduplicación global podría revelar que dos clientes poseen el mismo documento.
- Fórmulas no se ejecutan al importar y se neutralizan al exportar CSV/XLSX.
- Workers sin acceso general a red, vault o datos de otras empresas.

Referencia: OWASP File Upload Cheat Sheet, <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.

## 18. Criptografía y secretos

- TLS 1.2 como mínimo; TLS 1.3 preferido.
- Cifrado administrado en base, objeto, backups y discos.
- Envelope encryption con KMS.
- Claves separadas por ambiente y rotación documentada.
- Clave por tenant de alta sensibilidad como opción futura.
- Secret manager; ningún secreto en repositorio, logs o imágenes.
- Tokens OAuth cifrados y con scopes mínimos.
- Firmas HMAC para webhooks.
- Passwords únicamente en IdP, con algoritmos modernos si alguna credencial local fuera inevitable.

## 19. Auditoría

Registrar:

- Login, fallo, MFA, dispositivo y revocación.
- Vista y descarga de documento sensible.
- Exportación.
- Invitación, rol y permiso.
- Conexión, consentimiento y revocación.
- Receta, regla y modelo.
- Match, override, aprobación y reversión.
- Cierre y reapertura.
- Cambio de retención y eliminación.
- Acceso de soporte o break-glass.

Cada evento guarda actor, workspace/empresa cuando aplique, acción, referencia/versiones del recurso, motivo, sesión/IP/dispositivo, correlation ID y timestamp. `Antes/después` se limita a allowlist de metadatos o hashes: nunca secretos, binarios, texto libre completo, montos innecesarios ni payload financiero. Valores restringidos se enmascaran o cifran. El evento semántico permanece en PostgreSQL bajo RLS; solo digest/manifiesto minimizado va a WORM con su clasificación y retención. Admin de seguridad ve metadatos de seguridad, no payload financiero, salvo rol explícito sobre la empresa.

## 20. Privacidad y ciclo de vida

- Inventario de datos y finalidades.
- Definición contractual de responsable/encargado por flujo.
- DPA y lista de subencargados.
- Instrucción/base jurídica documentada y, cuando corresponda, consentimiento granular para conectividad o IA externa.
- Minimización y masking.
- Acceso, corrección, portabilidad, revocación y eliminación.
- Retención por clase, contrato y obligación legal.
- Legal hold separado de retención ordinaria.
- Evidencia de eliminación en DB, objetos, cachés, índices y backups según política.
- Analítica de producto sin payload financiero identificable.
- Evaluación de transferencia/transmisión internacional antes de elegir región/proveedor.

La precedencia obligatoria de retención es: **legal hold → obligación legal o contractual validada → instrucción válida del Responsable → configuración operativa del plan**. El plan comercial solo puede definir tier, latencia y costo de almacenamiento; nunca acortar una obligación ni inventar por sí mismo un periodo legal. La decisión L-01 debe aprobarse antes de recibir datos reales.

Política técnica propuesta, sujeta a base jurídica y contrato:

| Categoría | Retención propuesta |
|---|---|
| Scratch y fragmentos | Minutos; máximo 24 horas |
| Caché | TTL de minutos u horas; máximo 24 horas |
| Archivo rechazado no malicioso | 7 días para recuperación |
| Malware | Conservar solo hash/metadatos cuando sea posible |
| Original y dataset financiero | Según clase documental y contrato |
| Soporte contable designado | Opción de hasta 10 años, validada por cliente/legal |
| Cierre y evidencia | Igual a soportes relacionados |
| Audit financiero | Igual a la decisión relacionada |
| Logs de seguridad | 12–24 meses como base |
| Export generado | 7–30 días, regenerable |
| Backup operacional | Rotación base de 35 días, con política documentada |
| Contexto temporal IA | No persistir en proveedor; debugging saneado y acotado |

Una eliminación debe propagarse a PostgreSQL, objetos/versiones, Parquet/lake, índices, embeddings, cachés, exportaciones, temporales y proveedores. Un tombstone impide que un restore reviva información eliminada. Legal hold suspende purga y debe mostrar fundamento, alcance y responsable.

**Pendiente legal L-01:** definir periodos exactos de retención para documentos contables, facturas, auditoría y backups en Colombia. No fijarlos únicamente por conveniencia técnica o por plan; L-01 bloquea DRG-01 y cualquier piloto con datos no anonimizados.

La SFC describe autorización específica, finalidad, duración, cifrado, monitoreo, vulnerabilidades, revocación y supresión para tratamiento de datos financieros: <https://www.superfinanciera.gov.co/publicaciones/10114731/innovasfcfinanzas-abiertasfinanzas-abiertas-colombiaconsumidor-financieropeguntas-frecuentes-10114731/Finanzas%20abiertas/>.

## 21. Secure SDLC y supply chain

- Repositorios protegidos, revisión obligatoria y branch protection.
- CI/CD con identidad federada, no claves largas.
- SAST, secret scanning, dependency scanning y IaC scanning.
- SBOM por release y firmas de artefactos.
- Imágenes mínimas, fijadas por digest y escaneadas.
- DAST y pentest focal antes de producción.
- Threat modeling por épica sensible.
- Política y SLA de vulnerabilidades.
- Feature flags con dueño y fecha de retiro.
- Datos sintéticos en desarrollo; producción no se copia libremente.
- Separación dev/staging/prod y acceso just-in-time a producción.

Baseline de verificación:

- NIST CSF 2.0 para gobierno, identificación, protección, detección, respuesta y recuperación.
- OWASP ASVS nivel 2 para la aplicación; nivel 3 en autenticación, autorización, criptografía, archivos, auditoría y funciones privilegiadas.
- NIST SSDF para desarrollo seguro.

Ruta de assurance propuesta:

1. Readiness interno y controles operables.
2. SOC 2 Type I cuando el mercado lo justifique.
3. SOC 2 Type II después de un periodo suficiente de evidencia.
4. ISO 27001/27701 si socios financieros o expansión lo exigen.
5. Permanecer fuera de PCI DSS evitando almacenar, procesar o transmitir datos de tarjeta; reabrir el análisis si cambia el producto.

### 21.1 Riesgo de proveedores

Antes de que un proveedor crítico reciba datos o soporte operación:

- Región, residencia, transferencias y subencargados.
- Cifrado, accesos del personal y seguridad demostrable.
- Retención, eliminación y uso para entrenamiento.
- Incidentes, SLA, RTO/RPO y continuidad.
- DPA, confidencialidad, portabilidad y plan de salida.
- Certificaciones y resultados de seguridad disponibles.
- Costos por volumen y capacidad de limitar gasto.

OCR e IA siempre se consumirán tras adaptadores/gateway para poder cambiar proveedor.

## 22. Respuesta a incidentes y continuidad

Capacidades:

- On-call y runbooks.
- Clasificación SEV-1 a SEV-4.
- Detección, contención, preservación de evidencia y recuperación.
- Matriz de notificación legal, contractual y a clientes.
- Status page y comunicación posterior.
- Postmortem sin culpa con acciones y fechas.
- Ejercicios semestrales y tabletop anual con legal.
- `SEV-1` incluye, como mínimo, exposición cruzada entre tenants, compromiso de claves privilegiadas, corrupción material de integridad y ransomware con alcance productivo.
- Registrar por separado `detected_at`, `aware_at` y `confirmed_at`; no sustituirlos con una única fecha administrativa.
- Objetivos internos SEV-1: page al on-call ≤15 minutos, Incident Commander ≤30 minutos, contención inicial ≤1 hora y evaluación legal/privacidad ≤4 horas.
- Objetivo contractual interno: avisar al Responsable/cliente afectado dentro de 24 horas desde conocimiento razonable de un incidente material confirmado o altamente probable, sin esperar a cerrar toda la investigación.
- Ningún SLA interno amplía ni sustituye un plazo legal, regulatorio o contractual más estricto.
- Evaluar y cumplir reporte a la SIC dentro del plazo aplicable; la orientación oficial menciona quince días hábiles para los casos correspondientes: <https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/cumplimiento-de-la-obligacion-del-reporte-de-incidentes-de-seguridad>.

Objetivos iniciales y objetivo maduro:

| Indicador | Inicial | Producto maduro |
|---|---:|---:|
| RPO operacional | 15 min | 5 min |
| RTO servicio central | 4 h | 2 h |
| Restauración de objeto hot | 1 h | 30 min |
| Prueba de restore | Trimestral | Mensual automatizada + trimestral completa |

Comportamiento por componente:

| Componente | Pérdida tolerada | Degradación esperada |
|---|---|---|
| PostgreSQL | Dentro del RPO aprobado | Failover/solo lectura limitada |
| Original ya confirmado | RPO regional inicial ≤15 min y maduro ≤5 min; no se confirma al usuario hasta persistir objeto, hash y metadatos | Versionado y replicación; DR entre regiones asíncrono, por lo que no se promete RPO cero |
| Workflow confirmado | No perder estado; reanudar | Trabajo en cola |
| Redis | Se puede perder y reconstruir | Rendimiento menor |
| Analítica | Hasta 24 horas | Informes históricos demorados |
| IA/OCR | Se reintenta o pasa a manual | Núcleo determinístico disponible |
| Conector externo | No se asume saldo cero | Mostrar frescura y fallback por archivo |

Las pruebas de restauración incluyen PostgreSQL, objetos, manifests, workflows, secretos y material KMS. Un backup cifrado que no puede descifrarse y reconciliarse contra hashes no cuenta como restore exitoso.

---

# Parte V — Gobierno de inteligencia artificial

## 23. Política general

No se preguntará “¿podemos usar IA?”, sino:

1. ¿Existe una solución determinística suficiente?
2. ¿Qué daño causaría un error?
3. ¿Puede verificarse automáticamente la salida?
4. ¿Existe evidencia y revisión humana?
5. ¿El cliente autorizó el tratamiento y proveedor?
6. ¿El beneficio supera costo, latencia y riesgo?

El marco de gobierno se alineará con `Govern`, `Map`, `Measure` y `Manage` de NIST AI RMF: <https://www.nist.gov/itl/ai-risk-management-framework>.

### 23.1 Niveles de riesgo

| Nivel | Definición | Gobierno |
|---|---|---|
| AI-0 | Función crítica determinística | Pruebas tradicionales y auditabilidad |
| AI-1 | Ayuda general sin datos financieros del cliente | Revisión básica y monitoreo |
| AI-2 | Extracción/clasificación reversible | Evaluación, confianza, override y opt-out |
| AI-3 | Recomendación financiera o señal de riesgo | DPIA/AIA, validación independiente y humano obligatorio |
| AI-4 | Decisión autónoma sobre libros, acceso, fraude, derechos o dinero | Prohibido |

Antes de aprobar AI-2/AI-3 se documenta: problema, alternativa determinística, datos mínimos, daño posible, reversibilidad, explicación, reviewer, fallback, métricas, drift, proveedor, transferencias y plan de retiro.

## 24. Matriz de usos

| Caso | Tecnología preferida | IA permitida | Automatización permitida |
|---|---|---:|---|
| Detectar MIME/formato | Firma/parser | No necesaria | Sí, determinística |
| Parsear OFX/XML | Parser/XSD | No | Sí, validada |
| OCR | Modelo documental | Sí | Extraer; validar campos críticos |
| Clasificar documento | Reglas + clasificador | Sí | Autoenrutar con confianza calibrada |
| Sugerir mapping | Reglas, embeddings o LLM | Sí | Primera vez requiere confirmación |
| Crear receta | LLM como asistente | Sí | Ejecutar solo DSL determinística validada |
| Detectar tipos | Perfil estadístico + modelo | Sí | Confirmar ambigüedades |
| Generar candidatos de match | Reglas/ML | Sí | Solo ranking |
| Confirmar match | Motor determinístico/calibrado | LLM prohibido | Solo con umbral y controles |
| Calcular dinero, impuesto o saldo | Decimal y reglas | LLM prohibido | Sí, determinística |
| Detectar anomalías | Reglas + estadística/ML | Sí | Generar señal, no veredicto |
| Declarar fraude | — | Prohibido | Nunca |
| Aprobar/cerrar/reabrir | Workflow humano | Prohibido | Nunca sin actor autorizado |
| Decidir acceso/retención/borrado | Política | Prohibido | Determinística y aprobada |
| Resumir informe | LLM grounded | Sí | Borrador con enlaces a evidencia |
| Soporte interno | RAG sobre documentación | Sí | Sin acceso financiero implícito |

## 25. Umbrales y human-in-the-loop

- Clasificación: autoenrutamiento solo con confianza calibrada ≥98% y validaciones estructurales; en caso contrario, revisión.
- Mapping: una plantilla exacta y previamente aprobada puede autoaplicarse; una sugerencia nueva requiere confirmación.
- Match automático se habilita por slice `source_pair + rule_or_model_version + case_type`, no por un promedio global.
- Cada slice debe alcanzar precisión observada ≥99,8% y límite inferior unilateral de Wilson al 95% ≥99,5% sobre casos adjudicados en los últimos 90 días o tres ciclos, lo que represente mejor el patrón vigente.
- Antes de 1.000 casos adjudicados por slice, el resultado solo se sugiere. La excepción son reglas determinísticas exactas, únicas y formalmente aprobadas mediante evidencia y simulación histórica.
- Además exige candidato único, margen definido sobre el segundo, ninguna señal de riesgo activa y reversibilidad. Los reportes separan precisión, cobertura elegible y tasa de abstención.
- Anomalía: siempre crea señal; nunca bloquea por sí sola.
- Resumen: toda cifra proviene de consulta estructurada y mantiene link de origen.
- Cambios de modelo: shadow mode, comparación y rollback antes de producir decisiones.

Estos son umbrales iniciales de seguridad, no promesas comerciales. Se recalibrarán por fuente y caso.

## 26. AI Gateway

Toda llamada de IA pasa por una capa común que realiza:

- Verificación de tenant, finalidad, plan y política de tratamiento autorizada.
- Clasificación y minimización de datos.
- Redacción/tokenización.
- Selección de modelo y región.
- Plantilla/prompt versionado.
- Salida JSON con schema estricto.
- Validaciones y guardrails.
- Medición de costo, latencia y calidad.
- Registro de proveedor/modelo/versión sin exponer secretos.
- Fallback determinístico o revisión humana.
- Kill switch por modelo, caso, tenant o proveedor.
- Sin guardar prompts/respuestas crudos en logs generales; muestreo saneado, restringido y con retención corta para evaluación.
- No conservar cadena interna de razonamiento; guardar explicación breve, campos usados y evidencia verificable.
- Modelos de extracción/clasificación no reciben herramientas privilegiadas ni acceso directo a producción.

### 26.1 Datos prohibidos para LLM externo

- Credenciales o secretos.
- PAN/CVV.
- Documento completo cuando bastan campos redacted.
- Información de una empresa para ayudar a otra.
- Datos fuera de la finalidad autorizada.
- Texto de documentos tratado como instrucciones.

Todo proveedor externo debe ofrecer contrato/DPA, no entrenamiento con datos del cliente, retención controlable, región conocida, subencargados y eliminación verificable. Cada tenant puede desactivar usos externos sin perder el flujo básico.

Un “opt-in” de interfaz no sustituye base jurídica ni instrucción del Responsable. Antes de enviar datos a IA u OCR externos, el registro de política debe contener: instrucción válida del Responsable, finalidad y base jurídica, `policy_id`, DPA y subencargados, región/transferencia, retención, eliminación verificable y clases de datos permitidas. AI Gateway bloquea la llamada si falta cualquiera de estos requisitos. Si un proveedor no acepta las condiciones, no recibe datos restringidos.

Los documentos se consideran datos no confiables; cualquier instrucción incluida en ellos se ignora para prevenir prompt injection.

## 27. Evaluación y operación de modelos

- Corpus gold anonimizado por banco, fuente, locale y calidad.
- Métricas por campo y slice, no solo promedio.
- Precisión, recall, calibración y tasa de abstención.
- Exactitud numérica y de fechas.
- Tasa de aceptación/corrección humana.
- Falsos positivos de anomalía.
- Alucinaciones en resúmenes.
- Pruebas de prompt injection y data exfiltration.
- Coste por documento, empresa y plan.
- Model registry, data lineage, model card y dueño.
- Revisión periódica de drift.
- Feedback humano separado de consentimiento para entrenamiento.

Estrategia de aprendizaje:

1. Modelos administrados sin entrenamiento con datos del cliente.
2. Reglas y modelos clásicos por tenant con sus propios históricos.
3. Modelos globales solo con datos sintéticos, públicos licenciados o realmente anonimizados.
4. Fine-tuning con datos de cliente únicamente mediante programa separado, instrucción/base jurídica y contrato específicos, DPIA, no-training por defecto y derecho de salida; nunca se deriva de aceptar el servicio general.

Un clic humano no se trata automáticamente como verdad. Las etiquetas de error, legítimo, falso positivo o fraude confirmado deben tener procedencia y revisión.

## 27.1 Inferencia en dispositivo y evaluación de Needle 2

### Decisión

**Needle 2 queda como POC móvil condicionado, offline y no autoritativo. No se adopta como dependencia central, no ejecuta herramientas directamente y no entra al data plane financiero ni a los workers canónicos. Cactus Engine no se adopta al inicio.**

El valor posible no es “más inteligencia” ni un gran ahorro de tokens. Es:

- Respuesta local y offline para acciones cortas.
- Minimización de datos enviados fuera del teléfono.
- Menor latencia para navegación, prefill y clasificación sencilla.
- Soporte razonable en Android económicos si el benchmark propio lo confirma.

Economía ilustrativa, no forecast: con 500.000 interacciones elegibles/mes de 200 tokens de entrada y 30 de salida, un modelo cloud pequeño hipotético de USD 0,20–1/M input y USD 1–5/M output costaría aproximadamente USD 35–175/mes. Resolver 80% en local ahorraría solo USD 28–140. Con USD 2.000/mes de ingeniería, QA y mantenimiento amortizado, el break-even puramente por tokens aparecería alrededor de 7–36 millones de interacciones/mes. Se deben sustituir estos supuestos por cotizaciones y telemetría vigentes.

Por tanto, no se crea un plan comercial distinto ni se promete descuento por IA local. Es una optimización de experiencia, privacidad y resiliencia; el caso de negocio exige demostrar mejor finalización offline, menor tiempo de tarea o disposición de firmas a pagar por política estricta sin cloud.

### Qué demuestran —y qué no— los datos disponibles

Needle 2 se presenta como un modelo abierto de 45 millones de parámetros, especializado en **texto → llamada de función/JSON y extracción estructurada**, con binario de 14 MB, alrededor de 28 MB de RAM por sesión y ventana deslizante de 256 tokens. No recibe imágenes ni reemplaza un OCR. Sus cifras y benchmarks son del proveedor, no una validación independiente: <https://cactuscompute.com/needle> y <https://github.com/cactus-compute/needle>.

La conformidad de esquema es útil, pero no garantiza semántica correcta. El proveedor publica 63,7% exact-match en Mobile Actions y 42,6% global en BFCL v4; el desempeño cae en llamadas múltiples y APIs fuera de su distribución de entrenamiento. No existe benchmark oficial publicado para español colombiano, DIAN, COP, extractos, fechas locales o documentos ruidosos.

Hay una limitación crítica: la documentación indica que la confianza calibrada aplica al modelo base; después de fine-tuning el valor pasa a `None` porque el head de confianza no se actualiza. Un modelo ajustado al vocabulario contable necesitaría calibración, abstención y validadores externos: <https://github.com/cactus-compute/needle/blob/main/doc/apis.md#confidence>.

Al corte de investigación, Needle y sus pesos declaran Apache-2.0. Cactus Engine es un producto/runtime diferente, con bindings generales y una licencia que condiciona uso organizacional al superar umbrales de financiación o ingresos. Legal debe verificar la licencia vigente, SBOM y artefactos exactos antes de distribución: <https://github.com/cactus-compute/needle/blob/main/LICENSE> y <https://github.com/cactus-compute/cactus/blob/main/LICENSE>.

### Casos permitidos para el POC móvil

1. Convertir una orden breve en una **propuesta** de navegación o filtro: abrir empresa, periodo o cola.
2. Inferir familia documental desde un fragmento corto ya obtenido por OCR.
3. Extraer campos de texto corto a un borrador visual y editable.
4. Prefill de etiquetas, metadatos y comandos de accesibilidad offline.
5. Preparar una solicitud local que el backend validará de nuevo al recuperar conectividad.

### Casos excluidos

- OCR de imagen, PDF o tabla completa.
- Limpieza canónica de CSV/XLSX, cálculos de dinero, impuestos o saldos.
- Matching, auto-match, aprobación, cierre, reapertura o pagos.
- Anomalías/fraude, históricos, informes largos o procesamiento batch.
- Selección de tenant o autorización basada únicamente en salida del modelo.
- Cualquier herramienta con side effects invocada desde `agent.run()` o mecanismo equivalente.

### Arquitectura del adaptador edge

```text
Cámara/texto/comando
  → OCR nativo si aplica
  → reglas locales y minimización
  → OnDeviceIntentProvider (Needle u otro, feature flag)
  → IntentProposal tipada + versión/hash + confianza externa
  → schema y policy locales
  → vista previa/confirmación
  → API del backend
  → autenticación, tenant, RBAC/ABAC, SoD y reglas financieras se validan otra vez
```

`IntentProposal` nunca es una autorización. Navegar o rellenar un borrador puede ser inmediato; exportar, aprobar, cambiar configuración, cerrar o cualquier mutación sensible exige confirmación explícita y decisión server-side. Si no hay red, la app solo guarda un borrador cifrado y no representa la operación como completada.

El adaptador debe:

- Ocultar el SDK/modelo al dominio y permitir sustitución o desactivación remota.
- Resolver capacidades por dispositivo/OS/modelo disponible; con poca batería, ahorro de energía, presión de memoria o estado térmico adverso, usar reglas, flujo manual o AI Gateway según política.
- Fijar modelo/runtime por versión y SHA-256; generar SBOM, firma y rollback.
- No descargar binarios arbitrarios ni hacer cloud handoff automático.
- Mantener prompts, OCR, índices y resultados fuera de logs/telemetría identificable.
- Cifrar el estado local, usar almacenamiento seguro y purgarlo por TTL/logout/revocación.
- Escalar al AI Gateway solo mediante política autorizada y redacción; nunca por una API key de Cactus embebida.
- Mantener el flujo manual completo en dispositivos no elegibles; la IA local nunca es requisito para conciliar o cerrar.

### Alternativas por tarea

| Tarea | Primera opción | Alternativa | Decisión |
|---|---|---|---|
| OCR/cajas en iOS | Apple Vision/VisionKit | Proveedor OCR vía gateway | Preferir API nativa; procesa en dispositivo y retorna ubicaciones: <https://developer.apple.com/documentation/vision/recognizing-text-in-images> |
| OCR/cajas en Android | Google ML Kit Text Recognition v2 | Proveedor OCR vía gateway | Preferir API nativa; entrega bloques, líneas, elementos y bounding boxes: <https://developers.google.com/ml-kit/vision/text-recognition/v2> |
| Clasificador/NER pequeño propio | ONNX Runtime Mobile como baseline React Native | Core ML/LiteRT nativos o ExecuTorch si el modelo/backend lo justifica | ONNX ofrece paquete React Native oficial; seleccionar finalmente por modelo y dispositivos: <https://onnxruntime.ai/docs/get-started/with-javascript/react-native.html>, <https://developer.apple.com/documentation/CoreML>, <https://developers.google.com/edge/litert>, <https://pytorch.org/projects/executorch/> |
| Intent → JSON muy corto | Reglas/intents deterministas | Needle 2 directo, solo si gana el POC | Needle compite por tamaño/offline, no por autoridad financiera |
| LLM local general en iOS | Ninguno como baseline | Apple Foundation Models como adapter opcional | Requiere Apple Intelligence/dispositivo compatible y el modelo cambia con el SO; no garantiza paridad Android: <https://developer.apple.com/documentation/FoundationModels> |
| Runtime generativo cross-platform | No introducir inicialmente | Cactus Engine, ExecuTorch u otro tras benchmark/licencia | Evitar dependencia antes de necesitar VLM/ASR/LLM local real |
| Inferencia en servidor | Parsers/reglas; ONNX Runtime para modelos compactos | vLLM/Triton solo con volumen/modelos que lo justifiquen | Needle no es motor del pipeline; en servidor pierde su ventaja diferencial |

El OCR móvil solo sirve para preview, guía visual y captura offline. La evidencia canónica conserva el original y se vuelve a procesar/validar en servidor; no se publica un monto porque Vision o ML Kit lo hayan leído una vez en el teléfono.

Stack de inferencia server/self-hosted condicionado:

| Necesidad | Baseline | Escalamiento |
|---|---|---|
| OCR/layout/tablas | Parser nativo + proveedor OCR abstraído; evaluar PaddleOCR/PP-Structure en corpus propio | Servicio dedicado solo si gana en exactitud, privacidad y costo: <https://github.com/PaddlePaddle/PaddleOCR> |
| Clasificación, NER y redacción | Reglas + ONNX Runtime en worker privado | Acelerador/Execution Provider según benchmark: <https://onnxruntime.ai/docs/execution-providers/> |
| Resumen grounded/asistente | Proveedor administrado tras AI Gateway al inicio | vLLM self-hosted si privacidad/volumen/COGS lo justifican; nunca expuesto directamente: <https://docs.vllm.ai/en/latest/> |
| Varios modelos/GPU compartida | No introducir | Triton con batching, repositorio de modelos y métricas cuando exista carga suficiente: <https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/> |

La inconsistencia de documentación entre nombres/versiones de Needle/Cactus refuerza la regla: todo resultado registra runtime, modelo, cuantización, ABI, versión y hash; nunca basta el nombre comercial.

### POC de 4–6 semanas y gate AI-EDGE-01

El POC usa integración directa de Needle bajo Apache-2.0 detrás de `OnDeviceIntentProvider`, sin Cactus Cloud, sin side effects y con un runner equivalente en CI. Corpus mínimo: 3.000 casos gold separados por empresa/documento, con español colombiano, acentos, ruido OCR/ASR, COP/USD, separadores `1.234,56`/`1,234.56`, fechas ambiguas, NIT, multiempresa, fuera de alcance, prompt injection y abuso. Con el mismo corpus, preprocesamiento y scoring se comparan reglas deterministas, Needle base, Needle ajustado solo si hace falta, un modelo propio portable, modelo de sistema cuando exista y cloud pequeño; Needle gana únicamente si mejora calidad o UX total, no por tokens/segundo.

Debe cumplir **todos** los gates:

| Dimensión | Gate |
|---|---|
| Routing | Exact-match ≥98,5% y límite inferior 95% ≥98% |
| Activación indebida | ≤0,1% en off-topic y solicitudes sensibles |
| Cobertura | ≥80% de solicitudes elegibles resueltas localmente al umbral aprobado; el resto se abstiene/fallback |
| Campos críticos | Dinero/fecha/NIT exactos ≥99,5% o el caso se excluye |
| Autorización | 100% de mutaciones sensibles confirmadas y revalidadas por policy server-side |
| Dispositivos | Android de 4 GB, Android medio/alto e iPhone 12/13/15/actual |
| Tamaño/RAM | Descarga incremental ≤25 MB; RAM incremental p95 ≤60 MB |
| Latencia | Cold init p95 ≤1,5 s; turno corto warm p95 ≤500 ms |
| Estabilidad | 10.000 invocaciones sin crash, leak ni corrupción |
| Energía | 100 invocaciones ≤2% de batería y sin estado térmico serio |
| Privacidad | Captura de red demuestra cero egreso en modo local; logs sin PII/raw |
| Supply chain | SHA fijado, SBOM, firma, escaneo, canary y rollback probados |
| Producto | Tiempo de tarea ≥30% menor, finalización offline ≥80% y calidad humana no empeora >0,5 puntos porcentuales |
| Valor | Capturas completadas +10% en conectividad deficiente o evidencia equivalente; al menos 3 de 10 firmas validan valor de política sin cloud |

Si se hace fine-tuning, `confidence=None` obliga a abstención/calibración externa. Si el POC falla un gate, se conservan reglas/intents deterministas y AI Gateway; no se rebaja el umbral para justificar la tecnología.

### Decisión para servidor

Needle puede ejecutarse en Linux, pero no aporta valor suficiente al núcleo del servidor: su ventana y dominio son estrechos, mientras que parsers deterministas, reglas y modelos clásicos ofrecen más precisión y auditabilidad. Solo se permite un runner de CI para paridad con móvil o un experimento aislado de micro-routing que demuestre menor costo total **sin** degradar calidad. Para inferencia compacta portable se prefiere ONNX Runtime; Triton/vLLM se evalúan después cuando concurrencia, GPU y batching lo justifiquen, no antes.

---

# Parte VI — Operación, calidad y escala

## 28. Requisitos no funcionales

| Área | Objetivo de producto maduro |
|---|---|
| Disponibilidad web/API | 99,9% mensual; conectores medidos aparte |
| Lectura API p95 | <400 ms para consultas normales |
| Dashboard warm p95 | <2 s |
| Preview estructurado | <8 s para archivo dentro del perfil soportado |
| Archivo 100k filas | <3 min asíncrono |
| Archivo 1M filas | <15 min asíncrono, según reglas |
| Trazabilidad | 100% de campos publicados y decisiones |
| Auditoría | 100% de acciones privilegiadas y exportaciones |
| Accesibilidad | WCAG 2.2 AA |
| Idioma/localización | Español Colombia inicial; locale explícito |
| Recuperación | RPO/RTO según sección 22 |

Un SLO de conector distingue disponibilidad propia de indisponibilidad del proveedor externo.

## 29. Observabilidad

- Logs estructurados sin payload financiero innecesario.
- Métricas técnicas, de dominio y de costos.
- Tracing distribuido con correlation ID.
- Health por conector, parser, plantilla y modelo.
- Alertas basadas en SLO y burn rate.
- Dashboard de jobs, colas, errores, latencia y capacidad.
- Audit log separado de application log.
- Telemetría de producto sin PII o montos identificables.

Métricas de dominio:

- Tiempo de carga a dataset válido.
- Cobertura y precisión por regla.
- Excepciones y dinero sin explicar.
- Tiempo hasta cierre.
- Drift por plantilla.
- Overrides y reversiones.
- Alertas accionadas y falsos positivos.

## 30. Estrategia de pruebas

### 30.1 Datos y parsers

- Golden files por versión de formato.
- Fuzzing y archivos maliciosos.
- Fechas, decimales y encodings regionales.
- Fórmulas, merges y múltiples hojas.
- Reejecución e idempotencia.
- Comparación campo a campo y linaje.

### 30.2 Dominio financiero

- Property-based tests para ecuaciones monetarias.
- 1:1, 1:N, N:1, parcial y reversos.
- Conflictos y candidatos casi iguales.
- FX: par base/cotizada, timezone y fecha efectiva, redondeo por moneda, triangulación prohibida/no silenciosa, diferencia cambiaria y reproducción con la versión exacta de tasa.
- Periodo cerrado e intento de modificación.
- Versionado y reproducción de informe.

### 30.3 Seguridad

- Matriz de permisos positiva y negativa.
- Pruebas cross-tenant en API, DB, object store, caché y analítica.
- Abuse cases de exportación y soporte.
- SAST, DAST, dependency y container scanning.
- Pentest antes de GA y anual.

### 30.4 IA

- Evals offline antes de deploy.
- Shadow, canary y rollback.
- Casos adversariales y prompt injection.
- Validación de abstención.
- Comparación con baseline determinístico.

### 30.5 Resiliencia

- Restore de base y objetos.
- Caída de caché.
- Duplicación de mensajes.
- Timeout de proveedor.
- Región o servicio degradado.
- Backpressure en colas.

## 31. Entornos, entrega e infraestructura

- Local, desarrollo, staging y producción separados.
- Sandbox de integraciones separado.
- Infraestructura como código.
- Migraciones forward-compatible y rollback probado.
- Despliegue blue/green o canary para componentes sensibles.
- Feature flags por tenant y cohorte.
- Backward compatibility de API y eventos.
- Ventanas de mantenimiento comunicadas.
- Ambientes de preview sin datos productivos.

## 32. Build versus buy

Construir:

- Modelo financiero canónico.
- Linaje y evidencia.
- Recetas financieras y schema drift.
- Motor y decisiones de conciliación.
- Ciclos, cierre, riesgo y portafolio multiempresa.
- Política y gateway de IA.

Comprar/gestionar:

- Identidad.
- Object storage y KMS.
- PostgreSQL administrado.
- Cola, email, push y observabilidad base.
- Antivirus.
- OCR como proveedor intercambiable al inicio.
- Agregación bancaria si supera due diligence.

Evaluar híbrido:

- Importador genérico de CSV/XLSX para acelerar, sin delegar linaje ni modelo.
- Workflow engine durable.
- Warehouse analítico.
- Fraud/anomaly tooling de infraestructura, no lógica financiera propia.

---

# Parte VII — Empaquetado comercial

## 33. Principios de pricing

1. Solo tres planes públicos.
2. Seguridad fundamental incluida en todos.
3. Cobrar principalmente por valor: empresa activa y volumen normalizado.
4. No cobrar nuevamente por duplicados, reintentos o reprocesamiento técnico.
5. La única unidad de volumen es `source_record_published`; no cobrar por usuarios, reglas ni reruns.
6. Mostrar consumo y alertar antes de overage.
7. Conectores con costo externo extraordinario pueden trasladar costo de forma transparente.
8. Precio final se valida con entrevistas y pilotos; esta tabla es una hipótesis.

## 34. Tres planes propuestos

Precios mensuales indicativos en COP, antes de IVA. La anualidad candidata cobra once meses por doce de servicio; solo se publica si el costo de recaudo anual es ≤1% y el margen realizado, después de descuentos y recaudo, permanece ≥75%. Si no cumple, no hay descuento o se eleva el precio. Son hipótesis sujetas a pilotos.

| | Esencial | Control | Firma |
|---|---:|---:|---:|
| Precio mensual | $129.000 | $349.000 | $899.000 |
| Precio anual candidato | $1.419.000 | $3.839.000 | $9.889.000 |
| Cliente | PYME con conciliación recurrente | PYME multicanal | Firma/BPO multiempresa |
| Empresas activas | 1 | 1, ampliable a 4 | 10 incluidas |
| Usuarios | Sin cobro; uso razonable | Sin cobro; uso razonable | Sin cobro; uso razonable |
| `source_record_published`/mes | 5.000 | 25.000 | 50.000 compartidos |
| Fuentes activas | 5 | 15 | 50 compartidas |
| Feeds bancarios estándar | 1 | 2 | 6 compartidos |
| OCR | Telemetría piloto | Telemetría piloto | Telemetría piloto compartida |
| Evidencia hot | Tier candidato 10 GB | Tier candidato 50 GB | Tier candidato 200 GB compartidos |
| Histórico consultable en línea | 3 años | 7 años | 10 años/configurable |
| Ingesta | Archivo, correo y móvil | + SFTP, API y webhooks | + administración masiva |
| Conciliación | Dos lados, 1:N/N:1 y parciales | Multilateral, fees, retenciones, FX y reversos | Igual + plantillas por portafolio |
| Ciclos/cierre | Sí | Sí | Sí + matriz multiempresa |
| Gobierno | Evidencia, auditoría y roles base | Segregación, roles personalizados y API | Roles firma/cliente y carga de equipo |
| Anomalías | Reglas esenciales | Estadística y políticas | Consolidado y políticas por empresa |
| Salida | CSV/XLSX y plantillas ERP | Un write-back certificado o export estructurado | Conectores/exportaciones por cliente |
| Informes | Estándar | Programados y avanzados | Multiempresa y marca básica |
| Soporte objetivo | 1 día hábil | 8 horas hábiles | 4 horas hábiles para severidad alta |

Todos incluyen: MFA, cifrado, aislamiento, auditoría esencial, backups, derechos de privacidad, eliminación, motor de exactitud, reglas, cola de excepciones, historial, exportación y app móvil. SSO/SCIM, claves o celda dedicadas y SIEM exportable pueden ser empresariales; la seguridad fundamental no. El histórico consultable es una prestación de acceso y tiering; la retención, archivo frío y eliminación obedecen la precedencia de la sección 20 y no al nombre del plan. OCR y evidencia hot se miden sin cobro separado durante pilotos; los bloques, archivo frío, límites y precios se publican antes de GA únicamente después de telemetría de costo, latencia y restauración.

### 34.1 Esencial

Para una PYME con banco-libros o pasarela-banco. Debe ser autoservicio y no es adecuado para una empresa con una sola fuente ya resuelta por su ERP.

### 34.2 Control — producto héroe

Para una operación que cruza pedido, factura, pasarela, comisión, retención, liquidación, banco y ERP. Incluye API, segregación y automatización avanzada. Incluye una empresa; admite hasta tres empresas adicionales, para un máximo de cuatro. Una quinta empresa requiere Firma.

### 34.3 Firma — canal de escala

Para contadores o BPO que operan varias empresas desde un portafolio. Fuentes y movimientos se agrupan para absorber estacionalidad entre clientes.

Incluye:

- Panel firma × empresa.
- Roles internos y colaboradores cliente.
- Asignación, carga y SLA de equipo.
- Plantillas de ciclos, recetas y reglas replicables con revisión.
- Informes de firma y marca básica.
- Ledger de uso por empresa.
- Onboarding estructurado.

Empresa adicional propuesta en Firma: **$69.000/mes**, con cinco fuentes, 5.000 `source_record_published` y un feed estándar sujeto al guardrail. En Control: **$119.000/mes**, hasta tres adicionales y cuatro empresas totales. Una firma mayor compra capacidad o contrato privado; no se agrega un cuarto plan público.

## 35. Overage y add-ons

Mantener tres categorías, aunque cada una tenga bloques publicados:

1. **Capacidad adicional:** 10.000 `source_record_published` por $59.000; bloque Firma de 50.000 por $199.000; hot storage, archivo frío y OCR solo después de medir costo.
2. **Fuentes/conectores:** cinco fuentes estándar por $49.000; feed premium desde $39.000/cuenta cuando el costo externo lo exija.
3. **Servicios profesionales:** backfill, onboarding, receta compleja, conector a medida, marca avanzada o celda dedicada.

Reglas de justicia comercial:

- 15% de gracia mensual.
- Primer exceso en seis meses: advertir, no cobrar.
- Después se agrega un bloque predecible, no tarifa unitaria sorpresiva.
- Avisos al 70%, 90% y 100% con proyección de factura.
- Nunca bloquear lectura, auditoría, exportación o eliminación por exceso/fallo de pago; usar modo solo lectura antes de suspensión.
- Tarifas extraordinarias de terceros se muestran separadas.

La tarifa definitiva de overage se fija después de medir COGS real. Regla financiera:

- Infraestructura + OCR + IA + conectores + soporte variable ≤25% del ingreso del plan.
- OCR/IA idealmente ≤10% del ingreso.
- Margen incremental del overage ≥70%.
- Si un workflow consume más, se degrada a revisión, se limita o se vende como servicio; no se subsidia silenciosamente.

### 35.1 Unidad facturable

Un evento `source_record_published` se emite una sola vez cuando un registro financiero válido de una fuente se publica por primera vez en el modelo canónico. Es el mismo concepto en producto, metering, contrato, factura y analítica; un ledger inmutable permite explicarlo y disputar errores.

No cuenta:

- Fila descartada antes de publicar.
- Duplicado detectado.
- Reintento técnico.
- Reprocesamiento por corrección del producto.
- Match, propuesta, alerta, fee derivado incluido o decisión humana.

Definiciones:

- Una misma venta presente en ERP, pasarela y banco genera hasta tres `source_record_published`, porque son tres evidencias de origen; conciliar o reprocesar esas evidencias no vuelve a facturarlas.
- Una fuente es una cuenta bancaria, pasarela, tienda marketplace, empresa ERP o feed recurrente.
- Empresa activa es la que mantiene feed habilitado o procesa información durante el periodo; archivada no factura.

## 36. Evidencia competitiva de precio

No son productos idénticos, pero delimitan el mercado:

- Alegra Contabilidad publica COP $74.900–$319.900/mes y compite como suite ERP/contable: <https://www.alegra.com/colombia/precios/>.
- Cointab publica USD $149–$749/mes según fuentes y filas por archivo para conciliación especializada: <https://www.cointab.net/business/reconciliation/faqs/>.
- Synder publica precios desde USD $65 hasta $599/mes y usa volumen de transacciones/conexiones: <https://synder.com/pricing-accountants/>.

La plataforma propuesta debe demostrar ahorro medible para justificar un precio superior a funciones aisladas de un ERP local.

## 37. Validación de pricing

Antes de publicar:

- 25 entrevistas de willingness-to-pay: 15 PYMEs y 10 firmas/BPO contables.
- Van Westendorp como señal, no decisión única.
- Conjoint simple de empresas, volumen, conectores y soporte.
- Ocho pilotos pagados de empresa y tres de firma.
- Medición de horas ahorradas, cierres adicionales y monto recuperado/explicado.
- Prueba de dos anclas de precio, sin descontar por improvisación.
- Cohortes de margen y soporte por segmento.

Piloto recomendado:

- Dos ciclos reales.
- Tarifa fija de implementación/piloto, acreditable al 100% contra el primer anual si se cumplen las condiciones publicadas.
- Objetivos escritos de precisión, cobertura y tiempo.
- Sin prometer conectores no certificados.

### 37.1 Onboarding y pilotos pagados

| Oferta | Alcance | Precio hipótesis |
|---|---|---:|
| Setup Esencial opcional | Configuración guiada | $390.000 |
| Setup Control | Hasta dos flujos; obligatorio si hay write-back | $990.000 |
| Setup Firma | Dos plantillas y hasta diez empresas | Desde $2.900.000 |
| Piloto empresa 60 días | Una empresa, tres fuentes, hasta 15.000 registros/mes y 30.000 totales, dos ciclos | $990.000 |
| Piloto firma 60 días | Cinco empresas, dos plantillas, hasta 25.000 registros/mes y 50.000 totales | $1.990.000 |

El 100% del piloto se acredita contra el primer anual si firma dentro de 15 días. No se apila con descuento fundador, canal u otra promoción. Los flujos ya configurados en el piloto no vuelven a pagar setup; un alcance incremental paga solo la diferencia acordada. Sandbox gratis: datos sintéticos o máximo 1.000 filas; no consultoría productiva gratuita.

Objetivos de implementación:

- Esencial: <45 minutos de soporte.
- Control: ≤8 horas humanas estándar.
- Firma: ≤24 horas para plantilla inicial y <45 minutos por empresa adicional.
- Si se exceden en tres implementaciones consecutivas, subir setup, automatizar o reducir alcance.

### 37.2 Unit economics — hipótesis a instrumentar

Escenario base con 65% de utilización y soporte estabilizado, miles de COP/mes:

| COGS | Esencial | Control | Firma |
|---|---:|---:|---:|
| Infraestructura/base/auditoría | 5 | 12 | 35 |
| Ingesta y matching | 3 | 8 | 18 |
| Feeds usados en promedio | 8 | 16 | 48 |
| IA/OCR | 3 | 8 | 18 |
| Soporte/éxito asignado | 6 | 20 | 55 |
| Recaudo | 4 | 10 | 27 |
| **COGS total** | **29** | **74** | **201** |
| **Margen bruto estimado** | **77,5%** | **78,8%** | **77,6%** |

Escenario anual candidato con once meses facturados y doce meses de COGS base:

| Métrica anual, miles COP | Esencial | Control | Firma |
|---|---:|---:|---:|
| Ingreso anual candidato | 1.419 | 3.839 | 9.889 |
| COGS anual base | 348 | 888 | 2.412 |
| Margen bruto implícito | 75,5% | 76,9% | 75,6% |

El escenario de diez meses pagados queda rechazado con estos COGS: habría producido aproximadamente 73,0%, 74,6% y 73,2%. El KPI vinculante es margen realizado después de descuentos, recaudo, créditos, soporte variable y costos de proveedor, no esta proyección.

No son costos observados. Deben convertirse en telemetría por tenant antes de fijar precio. Guardrails:

- Los límites de lanzamiento son 1/2/6 feeds. Un feed adicional solo se incluye después de una prueba de uso al máximo del plan; con COGS >$12.000/mes pasa a premium.
- Piso de margen bruto 70%; objetivo 75–85%.
- IA no se ejecuta sobre cada movimiento si una regla basta.
- Medir soporte, CPU, OCR, tokens, storage y transferencia por tenant.
- Backfill sucio y conectores especiales se venden como servicio.

### 37.3 Gates comerciales

1. Entrevistar 15 PYMEs y 10 firmas con procesos reales.
2. Ejecutar ocho pilotos empresa y tres firma, pagados.
3. Cinco de ocho empresas deben lograr resultado y cuatro comprar anual a precio de lista.
4. Dos de tres firmas deben ampliar a diez empresas en 90 días.
5. Reducción ≥50% de trabajo manual y ≥30% del cierre.
6. Valor mensual conservador documentado ≥3× suscripción.
7. No construir un conector nuevo hasta aparecer en tres clientes pagadores, salvo integración estratégica aprobada.
8. Auto-match, medido por `source_pair + rule/model_version + case_type`: precisión observada ≥99,8%, límite inferior unilateral Wilson 95% ≥99,5%, cobertura ≥70% de casos elegibles y cero falsos positivos materiales durante el piloto; por debajo de 1.000 adjudicaciones por slice permanece en sugerencia salvo regla exacta aprobada.

### 37.4 Red-team comercial y operativo

- Una PYME con un banco y Alegra/Siigo funcionando no es ICP; no forzar la venta.
- APIs y write-back solo se anuncian con autorización, sandbox, contrato y fallback por archivo.
- Cada personalización “pequeña” se clasifica como estándar, receta pagada o conector; evitar managed service accidental.
- Cierre de mes concentra soporte y fallas externas; no prometer 24/7 antes de poder operarlo.
- Posicionar Firma como capacidad y margen para el contador, con propiedad de su relación y cláusula de no captación.
- Evitar que un grupo empresarial use Firma como arbitraje de volumen: definir beneficiario final y empresa cliente independiente.
- Reglas de comisión/retención se versionan y no se presentan como asesoría tributaria.
- No apilar anualidad, descuento fundador y comisión de canal por debajo del piso de margen.
- Simular aumentos de precio, mínimos mensuales y fallas de cada proveedor de feed; evitar que la promesa comercial dependa de un costo externo no controlado.
- Facturar en COP y revisar precios anualmente; costos internacionales extraordinarios son pass-through visible.
- Colombia primero; cada nuevo país exige análisis bancario, fiscal, privacidad, soporte y pricing.
- Si el equipo concilia rutinariamente por el cliente, registrar y vender el servicio por separado del SaaS.

---

# Parte VIII — Programa completo de construcción

## 38. Estrategia de entrega

La visión completa se construye por releases acumulativos. “Completo” significa cumplir los criterios de la sección 44, no lanzar cada integración imaginable.

Horizonte recomendado: **15–18 meses** con equipo promedio de 9–10 FTE, pico máximo de 12 y acompañamiento contable, jurídico y de seguridad.

### Fase 0 — Validación y arquitectura ejecutable, meses 0–2

- Observar diez cierres y cinco firmas.
- Corpus anonimizado de 150–250 documentos.
- Tres bancos, tres pasarelas, dos ERP y DIAN XML.
- Modelo canónico y taxonomía.
- Threat model y mapa de privacidad.
- Prototipos de seis flujos.
- ADRs iniciales.
- Pilotos y acuerdos de tratamiento.
- Unit economics y pricing discovery.

**Gate:** corpus, esquema, usuarios piloto, riesgos críticos y decisiones legales mínimas aprobados.

### Fase 1 — Plataforma y evidencia, meses 2–5

- Firma/empresa, identidad y roles.
- PostgreSQL, object storage, cola, auditoría y linaje.
- Upload seguro, cuarentena e idempotencia.
- CSV, XLSX, OFX y XML.
- Estudio de Importación tabular.
- Recetas, versiones, export limpio y schema drift.
- Metering mínimo desde el primer registro publicado: ledger `source_record_published`, OCR, storage y conectores, aunque todavía no se facture overage.
- Gateway mínimo de egreso para cualquier OCR/IA externa: política, minimización, proveedor/región, costo, auditoría y kill switch.
- CI/CD, observabilidad, backup y restore.

**Gate:** aislamiento verificado, 100% de lineage en campos publicados y procesamiento reproducible.

### Fase 2 — Conciliación y cierre, meses 5–8

- Modelo financiero completo.
- Matching 1:1, 1:N, N:1, parcial y net settlement.
- Excepciones y colaboración.
- Ciclos, recordatorios, cierre y reapertura.
- Temporal o equivalente ya operativo para esperas humanas, timers, reintentos y compensaciones; no es opcional en esta fase.
- Portafolio multiempresa.
- Informes operativos, control y acceso.
- App móvil para captura, solicitudes y aprobaciones.

**Gate:** dos ciclos reales por piloto, precisión demostrada y reducción ≥40% del tiempo.

### Fase 3 — Conectividad y automatización, meses 8–11

- Buzón de correo y DIAN.
- Primeras pasarelas y export ERP.
- Agregador bancario elegido por due diligence.
- Reglas no-code controladas y simulación histórica.
- PDF de plantillas prioritarias y OCR asistido.
- Informes programados, API y webhooks.
- Entitlements, metering y billing.

**Gate:** conectores con SLA visible, fallback por archivo y margen variable dentro de objetivo. Ningún agregador entra a producción sin concepto jurídico escrito sobre rol y obligaciones, participante/registro cuando aplique, alcance/duración/revocación de autorizaciones, DPA/transferencias, incidentes y garantía de que la plataforma no recibe ni registra credenciales bancarias.

### Fase 4 — Inteligencia gobernada, meses 11–14

- Clasificación y mapping asistidos.
- Anomalías estadísticas por empresa/fuente.
- Ampliación del gateway mínimo hacia AI Gateway completo, evals, model registry y políticas de autorización por finalidad.
- Narrativas grounded de informes.
- Drift, shadow mode y feedback.
- Búsqueda y exploración histórica.
- POC AI-EDGE-01 de 4–6 semanas para intents/extracción corta móvil; no se habilita si falla cualquier gate de calidad, privacidad, energía o producto de la sección 27.1.

**Gate:** ningún modelo productivo sin eval, trazabilidad, fallback y dueño; falsos positivos dentro de rango acordado.

### Fase 5 — Escala y madurez, meses 14–18

- SSO/SCIM y políticas avanzadas.
- Entorno o claves aisladas para clientes justificados.
- Catálogo de enrutamiento y prueba de migración de tenant entre celdas.
- Warehouse si se activaron umbrales.
- DR mejorado, pentest, compliance readiness y vendor reviews.
- White-label básico para firma.
- Optimización de margen y soporte.
- Expansión de conectores según datos comerciales.

**Gate:** criterios de producto completo, SLO, restauración, seguridad, margen y soporte satisfechos.

## 39. Equipo

### 39.1 Equipo inicial, meses 0–5

- Product lead/fundador.
- Contador de dominio.
- Product designer.
- Dos ingenieros full-stack/backend.
- Ingeniero de datos/plataforma.
- QA automation.
- Seguridad/privacidad y legal part-time.

### 39.2 Equipo de expansión, meses 5–18

- Segundo ingeniero de datos/ML.
- Ingeniero móvil.
- Platform/SRE.
- Integrations engineer.
- Customer success/onboarding.
- Segundo QA o SDET.
- Security lead fraccional, luego interno según crecimiento.

Estimación: 135–180 persona-mes para la visión completa, con promedio de 9–10 FTE y pico de 12; depende de compra de componentes, cantidad de conectores y madurez exigida.

### 39.3 Presupuesto y runway por gate

| Fase | Persona-mes orientativos | Liberación de presupuesto |
|---|---:|---|
| Descubrimiento y riesgo | 8–12 | Corpus, DRG-01, pricing discovery y ADRs |
| Fase 1 | 30–38 | Aislamiento, evidencia, metering y restore probados |
| Fase 2 | 27–34 | Dos ciclos reales, exactitud y workflow durable |
| Fase 3 | 25–34 | Contratos/conectores, fallback y margen |
| Fase 4 | 23–30 | Evals, autorización, drift y beneficio medido |
| Fase 5 | 22–32 | SLO, seguridad, compliance readiness y escala |
| **Total** | **135–180** | Visión completa |

Antes de contratar el equipo de construcción debe existir caja comprometida al menos hasta completar Fase 2, más 30% de contingencia sobre ese tramo. Cada fase tiene presupuesto separado para personal, cloud, proveedores, legal/compliance, seguridad, dispositivos de prueba y soporte piloto; ningún ingreso proyectado pero no contratado se cuenta como runway.

## 40. Workstreams

| Stream | Dueño | Dependencias |
|---|---|---|
| Producto y dominio | Product + contador | Pilotos y modelo canónico |
| UX web/móvil | Diseño + frontend | Investigación y accesibilidad |
| Plataforma e identidad | Backend/platform | IdP, cloud, seguridad |
| Ingesta y documentos | Data engineering | Corpus, parsers, object store |
| Conciliación | Backend/data | Modelo canónico y reglas |
| Integraciones | Integrations engineer | Partners, sandbox, contratos |
| IA y riesgo | ML/data + risk owner | Históricos, labels, gateway |
| Seguridad y privacidad | Security/legal | Arquitectura y proveedores |
| Comercial y soporte | Founder/CS | Planes, metering y pilotos |

## 41. Artefactos obligatorios antes de construcción significativa

- PRD general y PRD por épica.
- Modelo canónico y diccionario.
- Arquitectura C4.
- Threat model y data flow diagrams.
- Catálogo de eventos, contratos y estados de importación/conciliación/cierre.
- Matriz RBAC/ABAC detallada.
- Política de retención.
- ADRs 001–020.
- Especificación de linaje.
- Contrato de conector.
- Inventario de proveedores, subencargados y plan de salida.
- Corpus gold y suite de golden tests.
- Design system y prototipo navegable.
- Plan de observabilidad y SLO.
- Modelo de costos y metering.
- DPA, términos y vendor due diligence.

## 42. ADRs iniciales

1. ADR-001: monolito modular + workers.
2. ADR-002: PostgreSQL como fuente operacional.
3. ADR-003: aislamiento multitenant y RLS.
4. ADR-004: object storage por zonas e inmutabilidad.
5. ADR-005: modelo de linaje por campo.
6. ADR-006: motor de recetas determinístico.
7. ADR-007: transactional outbox e idempotencia.
8. ADR-008: AI Gateway y usos prohibidos.
9. ADR-009: web versus móvil.
10. ADR-010: metering por empresa y `source_record_published`.
11. ADR-011: identidad administrada y MFA/passkeys.
12. ADR-012: RBAC + ABAC y segregación.
13. ADR-013: cola inicial y adopción de workflow durable.
14. ADR-014: Parquet para histórico; warehouse por umbral.
15. ADR-015: no Kafka ni Kubernetes inicialmente.
16. ADR-016: proveedor OCR abstraído y fallback.
17. ADR-017: OpenTelemetry y separación audit/application log.
18. ADR-018: región, transmisión internacional y subencargados.
19. ADR-019: RPO/RTO, backups, WORM y retención.
20. ADR-020: catálogo de enrutamiento y evolución por celdas.
21. ADR-021: broker de capacidades móvil, Needle 2 condicionado y prohibición de side effects desde modelos edge.

Cada ADR contiene contexto, decisión, alternativas, consecuencias, costo y condición explícita de revisión.

---

# Parte IX — Métricas, riesgos y definición de completitud

## 43. KPIs

### Producto

- Tiempo de archivo a dataset válido.
- Importaciones sin soporte.
- Aceptación de mappings sugeridos.
- Recetas reutilizadas sin corrección.
- Cobertura y precisión del auto-match.
- Tiempo y valor de excepciones.
- Tiempo hasta cierre.
- Empresas por contador.
- Respuesta del cliente desde móvil.

### Riesgo y confianza

- Overrides y reversiones.
- Alertas accionadas y falsos positivos.
- Campos sin linaje.
- Drift no detectado.
- Accesos/exportaciones anómalos.
- Incidentes cross-tenant: objetivo cero.

### Negocio

- Activación por empresa.
- Retención de firmas y expansión de empresas.
- CAC payback y LTV/CAC.
- Margen bruto realizado después de descuentos, créditos, recaudo y costo variable; costo por 1.000 `source_record_published`.
- Soporte por empresa activa.
- Conversión de piloto a anual.

## 44. Definición de producto completo v1

La primera visión se considera completa cuando:

1. Una firma opera al menos 50 empresas desde un portafolio sin exposición cruzada.
2. Una fuente conocida se importa de forma recurrente en menos de un minuto de trabajo humano.
3. Un archivo tabular desconocido puede mapearse en menos de cinco minutos.
4. CSV, XLSX, OFX, DIAN XML, PDF prioritario y al menos cuatro conectores productivos tienen fallback.
5. Cada campo publicado y cada match retorna a evidencia.
6. El sistema soporta casos 1:1, 1:N, N:1, parcial, fee, retención, refund y reverso.
7. Auto-match, por slice, alcanza precisión observada ≥99,8%, límite inferior unilateral Wilson 95% ≥99,5%, cobertura ≥70% de casos elegibles, abstención reportada y cero falsos positivos materiales en la validación; antes de 1.000 casos adjudicados por slice solo sugiere, salvo regla exacta aprobada.
8. Los ciclos, recordatorios, segregación, cierre y reapertura son auditables.
9. Web y móvil cubren sus flujos definidos.
10. Riesgo combina reglas y baseline estadístico sin acusar fraude.
11. IA opera solo mediante gateway, evals, política de tratamiento autorizada y fallback.
12. 100.000 filas se procesan en menos de tres minutos dentro del perfil soportado.
13. Disponibilidad, RPO/RTO, pentest y restore cumplen objetivos.
14. Los tres planes, metering, overage y exportación contractual funcionan.
15. El margen bruto realizado de cohortes estables, después de descuentos, recaudo y costos variables, es ≥75%.
16. Dos cohortes de firmas cierran tres periodos consecutivos con reducción de tiempo ≥50%.

## 45. Riesgos principales

| Riesgo | Prob. | Impacto | Mitigación |
|---|---:|---:|---|
| Alcance se convierte en ERP | Alta | Alto | Límites y North Star; comité de alcance |
| PDF/OCR consume roadmap | Alta | Alto | Familias priorizadas, flujo asistido y proveedor abstraído |
| Falsos matches | Media | Crítico | Umbrales, calibración, shadow y evidencia |
| Fuga cross-tenant | Baja-media | Crítico | Defensa en profundidad y pruebas negativas |
| Conectores inestables | Alta | Alto | Archivos como fallback, SLA por fuente y circuit breaker |
| Restricciones de API ERP | Media | Alto | Partner agreements y exportación neutral |
| Costo IA/OCR erosiona margen | Media | Alto | Gateway, budgets, cache seguro y límites por plan |
| Proveedor de feed sube precio o degrada cobertura | Alta | Alto | Límite 1/2/6, prueba a máximo uso, premium transparente, fallback por archivo y salida contractual |
| Alertas producen fatiga | Alta | Medio | Severidad, agrupación, feedback y simulación |
| Firmas no pagan precio | Media | Alto | Piloto pagado y pricing research antes de escalar |
| Falta de datos etiquetados | Alta | Medio | Reglas primero, gold corpus y feedback explícito |
| Sobrediseño técnico | Media | Alto | Umbrales de adopción y ADR con costo total |
| Retención legal incorrecta | Media | Crítico | Concepto jurídico y configuración por clase |

## 46. Preguntas abiertas

### Producto/comercial

- ¿Quién firma y paga primero: PYME o firma?
- ¿Cuántas empresas y movimientos hacen rentable el plan Firma?
- ¿Qué fuentes causan 80% del trabajo en los pilotos?
- ¿Cuál es el ahorro demostrable por ciclo?
- ¿White-label aumenta conversión o añade soporte?

### Tecnología

- ¿Cloud y región iniciales?
- ¿FastAPI/Python para todo el backend o dominio TypeScript + workers Python?
- ¿Proveedor de identidad y soporte B2B?
- ¿Redis o Valkey según servicio administrado y licencia?
- ¿Proveedor OCR y condiciones de no entrenamiento/residencia?

### Legal/seguridad

- Roles de responsable/encargado por flujo.
- Retención exacta por clase.
- Requisitos contractuales de cada banco/agregador.
- Transferencia internacional y subencargados.
- Alcance de informe de auditoría/certificación requerido por mercado.

### IA

- Casos y finalidades autorizadas por Responsable/tenant; base jurídica, DPA y política registrada.
- Datos que pueden salir de región.
- Umbral de beneficio frente a costo por caso.
- Quién aprueba modelos y evals.

---

# Parte X — Evidencia y referencias principales

## 47. Referencias de producto y datos

- Power Query, perfilado de calidad y distribución: <https://learn.microsoft.com/en-us/power-query/data-profiling-tools>.
- OpenRefine, transformaciones y reversibilidad: <https://openrefine.org/docs/manual/transforming>.
- OneSchema, importación guiada, templates y feeds recurrentes: <https://docs.oneschema.co/docs/intro>.
- Apache Parquet, almacenamiento columnar: <https://parquet.apache.org/>.
- DIAN, recepción de facturas electrónicas: <https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/presentacion-recepcion-de-facturas-electronica/>.

## 48. Referencias técnicas y de seguridad

- PostgreSQL Row-Level Security: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>.
- AWS S3 Object Lock/WORM: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html>.
- OWASP File Upload Cheat Sheet: <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.
- NIST AI Risk Management Framework: <https://www.nist.gov/itl/ai-risk-management-framework>.
- SFC, privacidad y seguridad en finanzas abiertas: <https://www.superfinanciera.gov.co/publicaciones/10114731/innovasfcfinanzas-abiertasfinanzas-abiertas-colombiaconsumidor-financieropeguntas-frecuentes-10114731/Finanzas%20abiertas/>.
- Needle 2, modelo/API/licencia: <https://github.com/cactus-compute/needle>, <https://github.com/cactus-compute/needle/blob/main/doc/apis.md> y <https://github.com/cactus-compute/needle/blob/main/LICENSE>.
- Cactus Engine, licencia separada: <https://github.com/cactus-compute/cactus/blob/main/LICENSE>.
- OCR móvil: <https://developer.apple.com/documentation/vision/recognizing-text-in-images> y <https://developers.google.com/ml-kit/vision/text-recognition/v2>.
- Runtimes edge: <https://onnxruntime.ai/docs/get-started/with-mobile.html>, <https://pytorch.org/projects/executorch/> y <https://developers.google.com/edge/litert>.
- Inferencia server: <https://github.com/PaddlePaddle/PaddleOCR>, <https://docs.vllm.ai/en/latest/> y <https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/>.

## 49. Referencias de mercado y pricing

- Alegra Colombia: <https://www.alegra.com/colombia/precios/>.
- Cointab: <https://www.cointab.net/business/reconciliation/faqs/>.
- Synder para firmas: <https://synder.com/pricing-accountants/>.

---

## 50. Control de revisiones

| Versión | Fecha | Autor/revisor | Cambio | Decisión |
|---|---|---|---|---|
| 0.9 | 2026-08-20 | Equipo fundador / Codex | Primer plan maestro completo | En revisión |
| 0.95 | 2026-08-21 | Codex + auditorías especializadas | Celdas, estados, RLS, pricing, IA, seguridad y programa | Sustituida |
| 1.0-rc1 | 2026-08-21 | Codex; pendiente Claude | Cierre de hallazgos blocker y paquete de revisión independiente | Candidata congelada |
