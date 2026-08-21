# Plan maestro unificado de Fincilia

## Plataforma de conciliación y cierre financiero con evidencia

**Versión:** 1.0-unificada  
**Fecha:** 21 de agosto de 2026  
**Estado:** documento autoritativo para iniciar; preconstrucción  
**Mercado inicial:** Colombia  
**Expansión prevista:** Latinoamérica  
**Producto:** plataforma web y aplicación móvil complementaria  
**Audiencia:** fundadores, producto, diseño, contabilidad, ingeniería, datos, seguridad, legal, comercial y operaciones

---

## 0. Autoridad, veredicto y forma de uso

Este es el único plan vigente del producto. Integra y sustituye como guía de trabajo a:

- `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` 1.0-rc1.
- `REVISION_CLAUDE_1.0-rc1.md`.
- Las investigaciones posteriores de arquitectura, datos, seguridad, IA, mercado y marca.

Los documentos anteriores se conservan como evidencia histórica congelada; no deben utilizarse para tomar decisiones de implementación cuando contradigan este plan.

Este documento describe la visión completa, no solamente un MVP. Las fases son acumulativas y ninguna debe introducir un atajo incompatible con el producto final.

### 0.1 Veredicto unificado

| Gate | Veredicto | Condición |
|---|---|---|
| Trabajo de descubrimiento y prototipos con datos sintéticos | **SÍ** | Puede comenzar inmediatamente |
| Construcción de fundamentos técnicos | **SÍ CON CONDICIONES** | Cerrar tenancy, modelo financiero, ADR de stack y threat model |
| Recepción acotada de documentos reales para corpus | **NO, hasta DRG-00** | Contratos, ambiente aislado, inventario, retención y borrado |
| Piloto con datos financieros reales | **NO, hasta DRG-01** | Controles técnicos, legales, pentest y restore demostrados |
| Venta general | **NO, hasta GA-01** | Producto, soporte, pricing, margen, exactitud y cumplimiento validados |

El dictamen externo de Claude —“aprobable con cambios mayores”— es correcto. La arquitectura base sobrevive; los cambios materiales se concentran en completitud y saldos, multitenancy, canales de ingesta, borrado/restauración, plano de nube, precios, datos locales de bancos y retiro de Needle 2 del camino crítico.

### 0.2 Resolución de la revisión de Claude

Se adoptan:

- `account_balance` y `reconciliation_statement` como núcleo de conciliación bancaria.
- Completitud por fuente, cuenta y periodo antes de certificar un cierre.
- Autenticación y procedencia del correo; controles específicos de SFTP y webhooks.
- `delete_ledger` fuera de la unidad restaurable y reaplicación de tombstones durante restore.
- Revalidación de informes, enlaces, exportaciones y programaciones contra permisos vigentes.
- Vistas PostgreSQL con `security_invoker`, RLS forzada y parcheo explícito.
- Control del plano de nube, elevación JIT y procedimiento break-glass.
- `engine_release` y versión del esquema dentro de todo cierre.
- DRG-00 para recibir un corpus real de forma acotada.
- Detección de deriva estructural, estadística y de totales.
- Retiro de Needle 2 del camino crítico.
- Revisión total de pricing, pilotos y unit economics.
- Marca, dominio y antecedentes como artefactos de Fase 0.

Se modifican, porque aplicarlas literalmente introduciría nuevos riesgos:

| Propuesta externa | Decisión unificada |
|---|---|
| Clave canónica `company + account + date + amount + direction + reference` | Es fingerprint de candidato, nunca constraint `UNIQUE`; dos pagos legítimos pueden ser idénticos |
| Bloquear toda publicación si falta completitud | Permitir dataset `partial/unverified` para investigar; bloquear auto-match, cierre y exportación certificada salvo excepción aprobada |
| SPF, DKIM y DMARC simultáneamente obligatorios | DMARC puede pasar por SPF **o** DKIM alineado; considerar ARC/forwarding y firma de contenido; lo dudoso va a cuarentena |
| Suspender un informe al salir su creador | La programación pertenece a la organización mediante principal de servicio y responsable vigente; el creador queda como procedencia |
| `security_invoker` para vistas materializadas | Solo para vistas normales; agregados materializados son proyecciones tenant-scoped sin acceso directo, expuestas por vista segura |
| PostgreSQL como única verdad de jobs | PostgreSQL es verdad del dominio y estado visible; Temporal es verdad de ejecución durable; Valkey solo progreso efímero |
| Negar KMS a todo humano sin excepción | Cero acceso permanente; recuperación únicamente por break-glass temporal, dual y registrada |
| Exigir cédula o tratar passkey como identidad civil | `subject_id` estable y niveles de assurance; no recopilar documento por defecto; passkey autentica credencial, no identidad civil |
| Regex + Luhn garantizan quedar fuera de PCI | No. Si PAN llega a cuarentena puede existir alcance; el gate exige diseño de streaming/aislamiento y concepto QSA |
| Excluir desastres del SLO | SLO interno los muestra; SLA contractual y objetivo DR se reportan por separado |

Se rechazan:

- **Cotejo como marca principal.** Es descriptivo, débil en inglés y sus dominios principales están ocupados.
- Una unicidad dura basada en fecha, monto y referencia.
- Identificar una persona mediante IP o dispositivo; son señales, no prueba.
- Ejecutar cierres o mutaciones financieras desde un modelo edge.

### 0.3 Estados de decisión

- **Decidido:** se implementa; cambiar exige ADR o nueva evidencia.
- **Propuesto:** dirección recomendada pendiente de spike o validación.
- **Condicionado:** solo se adopta al superar un umbral explícito.
- **Pendiente:** bloquea un gate y necesita responsable y fecha.

### 0.4 Gates de datos y negocio

#### DRG-00 — corpus real acotado

Antes del primer documento real para investigación:

- Contrato de tratamiento con cada participante.
- Finalidad exclusiva de observación, anonimización y corpus.
- Ambiente aislado, sin conexión a producción ni IA externa.
- Inventario nominal de cada artefacto recibido.
- Acceso mínimo, temporal y auditado.
- Retención máxima y borrado verificable.
- Matriz legal L-01 aprobada para este flujo.

#### DRG-01 — piloto real

Antes de operar un cierre real:

- Threat model y pruebas negativas cross-tenant en API, DB, objetos, caché e informes.
- Región, contrato de transmisión internacional, subencargados y DPA aprobados.
- Ingesta web, correo, SFTP, API y webhooks asegurados.
- RLS, vistas, scopes de workers y segregación probados.
- Control de nube, CloudTrail, KMS y break-glass ejercitados.
- Restore probado con reaplicación de tombstones.
- Alcance PCI evaluado por asesor competente.
- Retención, derechos del titular y respuesta a incidentes operables.
- Pentest focalizado sin hallazgos críticos o altos abiertos.
- Due diligence de todo proveedor que reciba datos.

#### GA-01 — venta general

- Dos cohortes completan al menos tres cierres consecutivos.
- Exactitud, defectos escapados, tiempo y valor cumplen §§54–56.
- Pricing, metering, soporte y margen se han medido a utilización completa.
- Facturación electrónica propia funciona.
- Portabilidad y cambio de firma están probados.
- SLO, DR, seguridad, privacidad y operación de cierre están demostrados.

### 0.5 Registro de decisiones inicial

| ID | Decisión | Estado | Dueño | Evidencia requerida | Fecha límite | Gate |
|---|---|---|---|---|---|---|
| M-01 | Marca **Fincilia** | Propuesto jurídicamente | Product/Legal | SIC/WIPO, fonética, dominios, tiendas y clases 9/42; evaluar 35/36 | Antes de contrato piloto | Construcción |
| P-01 | Firma contable como comprador inicial | Decidido | Product/Founder | Diez entrevistas y tres pilotos confirman o refutan | Fin Fase 0 | Comercial |
| D-01 | Empresa independiente de la firma mediante `engagement` | Decidido | Architecture/Product/Legal | ADR, modelo y prueba de cambio de contador | Antes de Sprint 1 | Construcción |
| A-01 | NestJS/TypeScript + workers Python | Propuesto | Engineering | Spike de contratos, jobs, RLS y despliegue | Semana 3 | Construcción |
| A-02 | AWS y región inicial | Pendiente | Platform/Legal | Benchmark `sa-east-1` vs `us-east-1`, costo y transmisión | Antes de DRG-00 | Datos reales |
| L-01 | Retención por clase y evento inicial | Pendiente | Legal/Privacy | Matriz aprobada | Antes de DRG-00 | Datos reales |
| L-02 | Transmisión, subencargados y roles | Pendiente | Legal/Privacy | Concepto y DPA | Antes de DRG-01 | Datos reales |
| S-01 | Alcance PCI del canal de archivos | Pendiente | Security/Legal | Arquitectura y concepto QSA | Antes de DRG-01 | Datos reales |
| C-01 | Precios públicos | Condicionado | Product/Finance | Pilotos, COGS, FX, utilización 100% | Antes de GA | Comercial |
| B-01 | Agregador bancario colombiano | Condicionado | Integrations/Founder | Tres cotizaciones con bancos, cuentas PYME, SLA y costo | Fin Fase 0 | Conectividad |
| AI-01 | Needle 2 | Decidido: fuera del camino crítico | ML/Mobile/Security | Reevaluar solo con binding mantenido y evidencia en español | 12 meses | IA/móvil |

---

# Parte I — Posicionamiento, cliente y marca

## 1. Definición y promesa

> **Fincilia es una plataforma SaaS de conciliación y cierre financiero con evidencia para firmas contables y PYMEs. Recibe datos heterogéneos, conserva el original, los estructura y limpia, verifica su completitud, concilia movimientos y saldos, coordina revisiones y produce cierres reproducibles.**

Promesa central:

> **Convertir datos financieros dispersos en cierres comprobables, sin obligar a reemplazar el ERP ni el sistema contable.**

Principios no negociables:

1. Toda cifra vuelve a su origen.
2. El original nunca se altera.
3. Desconocido, parcial y no verificado son estados válidos.
4. La automatización muestra razones y evidencia.
5. La IA propone; las reglas validan; las personas certifican.
6. La empresa es la frontera estable de sus datos; la firma recibe una delegación revocable.
7. Web sirve para investigar y operar en volumen; móvil para capturar, responder y decidir casos simples.
8. Los archivos son un canal permanente.
9. Seguridad, privacidad, segregación y exportación básica no dependen del plan.
10. Fincilia no es un ERP, banco, iniciador de pagos ni acusador automático de fraude.

## 2. Comprador, ICP y wedge

### 2.1 Comprador prioritario

La **firma contable pequeña o mediana que administra entre 5 y 25 empresas** es el comprador prioritario. La PYME es la entidad servida, colaboradora y, en algunos casos, compradora directa.

No se vende “un panel multiempresa”: Siigo y Alegra ya anclan esa expectativa en gratis o muy barato. Se vende:

- Conciliación multifuente y multilateral.
- Limpieza de archivos difíciles con linaje por campo.
- Cierre reproducible y paquete de evidencia.
- Gestión de excepciones y solicitudes a clientes.
- Cambio de contador y portabilidad sin perder el histórico.

### 2.2 ICP de lanzamiento

- Firma con 5–25 empresas activas o PYME multicanal.
- Empresa con 500–12.000 movimientos económicos mensuales durante lanzamiento.
- Dos o más canales de cobro.
- Al menos una cuenta bancaria y una pasarela, datáfono, marketplace o billetera.
- Contabilidad en Siigo, Alegra, Odoo, otro ERP o Excel.
- Al menos 10–20 horas mensuales de trabajo manual por empresa o cierre recurrentemente tardío.
- Evidencia disponible y disposición a operar dos ciclos piloto.

Empresas con mayor volumen se atienden mediante contrato privado hasta medir el multiplicador real entre movimientos económicos y registros de origen.

### 2.3 Primer flujo vertical

```text
Factura o pedido emitido desde ERP/proveedor autorizado
  ↔ pago en pasarela, datáfono, marketplace o billetera
  ↔ comisión, retención, devolución o contracargo
  ↔ liquidación
  ↔ abono bancario
  ↔ asiento/libro contable
  ↔ conciliación de movimientos y saldos
  ↔ cierre con evidencia
```

La fuente de facturas emitidas debe ser exportación ERP, API autorizada del proveedor tecnológico o integración equivalente. El buzón DIAN de `AttachedDocument` cubre principalmente documentos recibidos; no se confundirá con el lado de cuentas por cobrar.

## 3. Decisión de nombre y sistema de marca

### 3.1 Contraste final

| Opción | Ventajas | Desventajas | Veredicto |
|---|---|---|---|
| **Fincilia** | Acuñada, extensible, pronunciable, evoca finanzas + conciliar, mejor buscabilidad preliminar | No explica sola el producto; proximidad fonética menor con FinSicilia; exige descriptor | **Elegida** |
| **Cotejo** | Precisa en español; transmite comparación, original y auditoría | Descriptiva y jurídicamente débil; `.com/.co/.app` ocupados; sin lectura directa en inglés; difícil de dominar en SEO | Narrativa funcional, no marca |
| **Empata/Empate** | Acción memorable; signo `=` muy fértil visualmente | Dominio deportivo/apuestas; puede significar ambigüedad o “nadie ganó”; dominios ocupados; poco formal para auditoría | Recurso verbal/visual, no marca |

La conclusión de Claude a favor de **Cotejo** se rechaza. El manual de marcas aplicable en los países andinos explica que un signo exclusivamente descriptivo puede ser irregistrable; además, la búsqueda preliminar encontró el término y sus dominios saturados. Esto no prueba que Fincilia esté registrable: M-01 sigue pendiente hasta búsqueda jurídica formal.

### 3.2 Marca elegida

> # **Fincilia**
> **Conciliación y cierre financiero con evidencia**  
> *Evidence-backed reconciliation and financial close*

El descriptor acompaña siempre la marca durante los primeros 18–24 meses.

Eslogan principal:

- **ES:** Concilia. Cierra. Comprueba.
- **EN:** Reconcile. Close. Prove it.

Línea de posicionamiento:

- **ES:** Cada cifra vuelve a su origen.
- **EN:** Every number traces back to its source.

Narrativa de producto:

- **ES:** Coteja datos. Empata movimientos. Cierra con confianza.
- **EN:** Compare data. Match transactions. Close with confidence.

`Cotejo` y `Empatar` pueden vivir en onboarding y campañas. En registros, auditoría e informes se emplean los términos formales `coincidencia propuesta`, `conciliado`, `excepción` y `cierre aprobado`.

### 3.3 Concepto de logo elegido

**Concepto primario: F de igualdad.**

- El asta vertical de la `F` representa trazabilidad hasta el origen.
- Sus dos brazos forman un signo `=`: dos fuentes que terminan alineadas.
- Un punto o franja de acento marca la zona exacta de coincidencia.
- Debe funcionar a 16 px, en favicon, icono móvil, monocromo, invertido y sello de PDF.
- Puede animarse: dos filas desalineadas convergen y quedan iguales.

Conceptos secundarios para explorar:

1. **Zona probada:** dos documentos superpuestos; la intersección es la evidencia validada.
2. **Celdas conciliadas:** dos celdas de orígenes diferentes convergen y el espacio negativo forma una `F`.

Dirección visual inicial:

- Grafito o gris-verde oscuro para precisión y confianza.
- Fondo “papel” cálido.
- Latón como acento de coincidencia y certificación.
- Turquesa accesible para estado conciliado; ámbar para revisión; rojo solo para riesgo crítico.
- Tipografía candidata: IBM Plex Sans; IBM Plex Mono para localizadores, hashes y evidencia.
- Evitar azul fintech genérico, monedas, calculadoras, balanzas, manos, piezas de rompecabezas, varitas de IA y checks aislados.

El logo no debe contener permanentemente el eslogan. El lockup operativo es `Fincilia + descriptor`; el eslogan pertenece a marketing y onboarding.

### 3.4 Arquitectura de nombres

- **Fincilia Clean:** importación, limpieza y estructuración.
- **Fincilia Match:** conciliación y excepciones.
- **Fincilia Close:** ciclos, recordatorios y cierre.
- **Fincilia Insights:** informes, históricos y señales.
- **Fincilia Firms:** portafolio multiempresa.
- **Fincilia Mobile:** captura, solicitudes y decisiones simples.

Nombres para tiendas:

- ES: **Fincilia: Conciliación**.
- EN: **Fincilia: Reconcile & Close**.

## 4. Objetivos y exclusiones

### 4.1 Objetivos

- Reducir al menos 50% el trabajo manual de conciliación y 30–50% el tiempo de cierre.
- Permitir que una firma atienda más empresas sin perder segregación ni evidencia.
- Importar documentos conocidos y desconocidos con trazabilidad.
- Concentrar excepciones en una cola explicable y accionable.
- Producir conciliaciones de movimientos **y saldos**.
- Generar snapshots de cierre reproducibles.
- Mostrar señales de riesgo e inconsistencia sin declarar fraude.
- Mantener portabilidad contractual de datos, recetas y evidencia.
- Alcanzar margen bruto realizado de 75–85% cuando el producto se estabilice.

### 4.2 Fuera de alcance

- Custodia de fondos, iniciación de pagos o crédito.
- Almacenamiento de credenciales bancarias/DIAN, CVV o secretos del cliente.
- ERP, nómina, inventario, facturación o impuestos como productos autónomos.
- Scraping que viole términos o requiera custodiar credenciales.
- Contabilización, match, cierre, acceso o borrado autónomos por LLM.
- Interpretación universal y perfecta de cualquier PDF.
- Acusación automática de fraude.
- Managed service encubierto dentro del precio SaaS.

---

# Parte II — Producto y experiencia completa

## 5. Arquitectura funcional y navegación

```text
Fincilia Firms
├── Portafolio
│   ├── Empresas al día, en riesgo y vencidas
│   ├── Fuentes faltantes y ciclos próximos
│   ├── Excepciones, dinero no explicado y señales
│   └── Carga de trabajo y solicitudes
├── Plantillas de firma
├── Equipo y engagements
├── Informes consolidados
├── Uso y facturación
└── Auditoría y seguridad

Empresa
├── Resumen
├── Fuentes y documentos
├── Fincilia Clean / Estudio de Importación
├── Registros normalizados
├── Fincilia Match / Conciliación
├── Excepciones e investigaciones
├── Fincilia Close / Sala de cierre
├── Fincilia Insights / Históricos e informes
└── Configuración, acceso y portabilidad
```

La navegación web principal es:

`Portafolio → Empresa → Importación → Conciliación → Cierre → Señales → Informes → Administración`.

El selector de empresa, razón social, NIT, periodo y estado se mantiene visible. Cambiar de empresa exige confirmación contextual cuando existe trabajo sin guardar o cuando la propuesta proviene de IA.

## 6. Organización, empresa y portafolio

### 6.1 Organización y engagement

- Una `organization` representa una firma contable, BPO o PYME que administra usuarios, billing y activos propios.
- Una `company` representa la frontera financiera estable de una entidad conciliada.
- Un `engagement` concede temporalmente a una firma acceso a una empresa, con vigencia, alcance, responsables y base contractual.
- Revocar o transferir un engagement no reescribe ni mueve el histórico financiero.
- El portafolio de una firma es una proyección de engagements activos, no la propiedad de las empresas.
- La propiedad de plantillas, recetas y reglas se declara por activo: `company_owned`, `firm_owned`, `licensed_to_company` o `platform_standard`.
- El paquete de portabilidad incluye datos, evidencia, decisiones, recetas/plantillas exportables según titularidad y manifiesto de versiones.

### 6.2 Portafolio multiempresa

Debe responder primero: **“¿dónde debo intervenir?”**

Indicadores:

- Empresa al día, en riesgo, vencida o sin información suficiente.
- Fuentes esperadas, recibidas, incompletas o atrasadas.
- Porcentaje conciliado y monto no explicado.
- Estado de conciliación de saldos por cuenta.
- Excepciones por severidad, monto y antigüedad.
- Ciclos listos para preparación, revisión o aprobación.
- Solicitudes pendientes del cliente.
- Señales críticas y exposición financiera.
- Tiempo de ciclo y carga por equipo, solo con finalidad documentada.

Acciones masivas permitidas:

- Asignar responsable.
- Modificar fecha interna o SLA.
- Enviar recordatorio agrupado.
- Solicitar fuentes o documentos.
- Exportar estado del portafolio autorizado.

No se aprueban decisiones financieras masivamente sin mostrar empresa, periodo, monto, exposición y evidencia. “Bajo riesgo” debe estar definido por política versionada; no es una etiqueta libre.

### 6.3 Cambio de contador

Flujo obligatorio:

1. La empresa o titular autorizado inicia el cambio.
2. Se congela la creación de nuevas acciones del engagement saliente, sin bloquear lectura contractual.
3. Se genera paquete de portabilidad y estado de pendientes.
4. La firma saliente confirma entrega o vence un plazo controlado.
5. Se revocan grants, sesiones, jobs, enlaces, webhooks y programaciones de la firma saliente.
6. Se activa el nuevo engagement con scopes explícitos.
7. El histórico permanece en la misma `company` y todo evento queda auditado.

## 7. Fuentes, archivos e ingesta

### 7.1 Canales

- Carga web individual y masiva.
- Cámara/carga móvil.
- Buzón dedicado.
- SFTP administrado o almacenamiento del cliente.
- API y webhook.
- Pasarela, marketplace o ERP.
- Agregador bancario únicamente tras B-01.
- Integración directa de alto valor.

Cada fuente conserva empresa, cuenta, responsable, frecuencia, periodo esperado, zona horaria, moneda, autenticación, consentimiento, frescura, SLA, estado, retención, versión de conector y costo.

### 7.2 Procedencia del correo

- Alias aleatorio de al menos 128 bits, no derivado del nombre de la empresa, rotable y revocable.
- Validar SPF/DKIM/DMARC correctamente: DMARC pasa con SPF **o** DKIM alineado; ARC se considera en forwarding.
- Allowlist y remitentes verificados por fuente.
- Validar firma/hash del contenedor DIAN cuando exista mecanismo aplicable.
- Mensajes dudosos entran a cuarentena como `origin_unverified`; no crean obligación, no autoenrutan ni participan en auto-match.
- El usuario ve remitente, dominio, resultado de autenticación y motivo antes de aceptar.
- Rate limits, reputación, detección de replay y rotación del alias.

### 7.3 SFTP y webhooks

SFTP:

- Cuenta y carpeta por fuente; sin shell.
- Claves administradas, rotación y algoritmos modernos.
- IP allowlist cuando sea viable.
- Chroot/aislamiento, cuotas y límites.
- El archivo aterriza en cuarentena y sigue todos los controles normales.

Webhooks entrantes:

- HMAC o firma asimétrica, timestamp, nonce, replay protection e idempotencia.
- Esquema y tamaño limitados; DLQ y reenvío auditado.

Webhooks salientes:

- Destinos verificados por el cliente.
- HTTPS obligatorio, bloqueo de rangos privados/metadata y protección SSRF.
- Resolución DNS controlada, revalidación ante redirect y egress allowlist.
- Secretos rotables y payload minimizado.

### 7.4 Formatos

La prioridad definitiva sale del corpus real de Fase 0. Hipótesis inicial:

- Primera clase: CSV regional, XLS/XLSX, PDF nativo de bancos prioritarios y XML UBL/DIAN.
- Plantillas prioritarias: PDF de bancos/pasarelas encontrados en el corpus.
- Condicionados a presencia real: OFX, MT940, `camt.053` y otros ISO 20022.
- Asistido: PDF escaneado e imágenes.

No se promete parser universal. PDF protegido se desbloquea en el dispositivo o el cliente carga una copia permitida ya desbloqueada; Fincilia no almacena su contraseña.

## 8. Fincilia Clean — Estudio de Importación

### 8.1 Flujo

```text
Subir → verificar origen → aceptar → detectar → extraer
      → seleccionar estructura → mapear → limpiar → validar
      → comprobar completitud → comparar → guardar receta → publicar
```

Vistas sincronizadas:

1. **Original:** página, hoja, XML o registro API.
2. **Extracción fiel:** celdas, tokens, fórmulas no ejecutadas y bounding boxes.
3. **Dataset limpio:** transformaciones, tipos, errores y rechazos.
4. **Esquema canónico:** campos financieros destino.
5. **Calidad/completitud:** conteos, totales, saldos, nulos, drift y ambigüedades.

Seleccionar un valor limpio resalta página/hoja/fila/columna/celda o caja exacta del original.

### 8.2 Interacciones

- Marcar encabezado, rango, tabla o región PDF.
- Excluir títulos, subtotales y pies.
- Identificar saldo inicial/final y totales de control.
- Tipar columnas y confirmar locale.
- Corregir fila, columna o celda mediante overlay.
- Mostrar antes/después y deshacer cada operación.
- Separar/unir, transponer, rellenar, filtrar y deduplicar.
- Normalizar Unicode, fechas, zona, moneda, signos y decimales.
- Regex y mapeos de valores.
- Crear columna determinística.
- Redactar datos sensibles.
- Exportar limpio con manifiesto y hash.

Las operaciones se guardan como receta determinística versionada. Ninguna corrección modifica el raw.

### 8.3 Tipado e inferencia

Confianzas independientes:

- Formato técnico.
- Familia documental.
- Emisor/plantilla.
- Tabla/región.
- Tipo físico.
- Semántica financiera.
- Empresa, cuenta y periodo.
- Mapping por campo.

Tipos principales: fecha, datetime, decimal, moneda, entero, booleano, identificador, NIT, cuenta, factura, referencia, contraparte, bruto, fee, impuesto, retención, neto, saldo, pago, devolución, contracargo y liquidación.

Una inferencia expone valor sugerido, confianza calibrada, razones, validaciones, alternativas y ambigüedad. Fechas como `03/04/26`, signos o separadores dudosos obligan a confirmar.

### 8.4 Deriva

Suspende la aplicación automática cualquiera de:

- Cambio estructural de columnas, hojas, tags o regiones.
- Cambio estadístico relevante: nulos, signos, cardinalidad, longitud, rango, IQR, unidades o distribución.
- Cambio semántico: moneda, zona horaria, centavos/unidades, convención de débito/crédito.
- Fallo de conteos, sumas, saldo inicial/final o continuidad.

El usuario compara la versión anterior y la nueva antes de crear una revisión de plantilla.

## 9. Fincilia Match — Conciliación

### 9.1 Casos soportados

- 1:1, 1:N, N:1 y N:M con cota declarada por regla.
- Parciales y saldo pendiente.
- Liquidación neta.
- Fees, impuestos y retenciones.
- Devolución, reverso y contracargo.
- FX con tasa versionada y diferencia separada.
- Tolerancia explícita de fecha y redondeo.
- Diferencia aceptada con motivo y aprobador.

Secuencia:

1. Gates duros de empresa, cuenta, moneda, dirección y disponibilidad.
2. IDs estables exactos.
3. Reglas versionadas por fuente.
4. Candidatos por monto, fecha, referencia y contraparte.
5. Combinaciones acotadas.
6. Ranking explicable.
7. Propuesta, confirmación, rechazo o reversión.

Los estados son `unevaluated → proposed → confirmed | rejected → reversed`. Una decisión nunca se borra.

### 9.2 Conciliación bancaria de saldos

Cada cuenta y periodo produce un `reconciliation_statement`:

```text
saldo según banco
± partidas conciliatorias del banco
= saldo bancario ajustado

saldo según libros
± ajustes de libros
= saldo contable ajustado

saldo bancario ajustado - saldo contable ajustado
= diferencia no explicada
```

El cierre exige `unexplained_difference = 0`. Una excepción material solo puede cerrarse si la política lo permite, queda explícitamente aceptada, muestra monto/motivo/aprobador y sigue apareciendo en el paquete; nunca se oculta como “cuadrado”.

### 9.3 Excepciones y colaboración

- Cola por empresa, periodo, fuente, cuenta, monto, antigüedad, exposición y responsable.
- Comentarios, menciones y evidencia.
- Solicitud al cliente con respuesta móvil.
- Motivos normalizados más texto complementario.
- Resolución masiva solo sobre cohortes homogéneas y política de bajo riesgo aprobada.
- Convertir una excepción en regla exige simulación histórica y segundo control.

## 10. Fincilia Close — ciclos y cierre

Estados:

```text
planned → collecting → processing → reconciling
        → review → ready_to_close → closed → reopened → review
```

Cada ciclo define fuentes/documentos esperados, periodicidad, responsables, dependencias, tolerancias, SLA, horario silencioso, revisión y escalamiento.

Recordatorios orientados a estado:

- Falta una fuente o documento.
- La conexión está desactualizada.
- El dataset es parcial/no verificado.
- Hay excepción envejecida o señal crítica.
- La conciliación de saldo no cuadra.
- El ciclo está listo para revisión.
- La evidencia cambió después del cierre.

### 10.1 Condiciones de cierre

- Fuentes requeridas recibidas o excepción aprobada.
- Completitud verificada por cuenta/periodo.
- Conciliaciones de saldo sin diferencia no explicada.
- Excepciones materiales resueltas o aceptadas según política.
- Segregación efectiva y reviewer vigente.
- Evidencia accesible y con linaje completo.
- Versiones de parser, receta, reglas, datos de referencia, esquema y motor fijadas.
- Sin señal crítica sin investigar que la política declare bloqueante.

El snapshot incluye datos, originales, manifiestos, decisiones, informes, configuración del ciclo, `canonical_schema_version` y `engine_release` con semver y SHA-256. Reabrir crea revisión N+1, exige step-up, motivo y nueva aprobación.

## 11. Fincilia Insights — riesgo, históricos e informes

### 11.1 Señales de riesgo e inconsistencia

Fincilia no declara fraude. Genera señales explicables:

- Integridad: duplicado, faltante, periodo incompleto, salto de saldo, total incorrecto o drift.
- Financiera: payout sin ventas, venta sin abono, fee/retención atípica, duplicado, reverso extraño o atraso.
- Contraparte: cuenta/beneficiario nuevos o cambio abrupto.
- Proceso: overrides, reaperturas, sustituciones o cambios de regla antes del cierre.
- Acceso: exportación masiva, dispositivo nuevo, soporte o actividad privilegiada inusual.

Cada señal contiene severidad, confiabilidad, exposición, baseline, evidencia, explicación, acción sugerida, responsable, estado y resolución. Se agrupan para evitar fatiga; existen presupuestos por empresa, clase y día.

### 11.2 Informes

Operativos:

- Estado de conciliación de movimientos y saldos.
- Dinero no explicado.
- Excepciones y aging.
- Calidad/completitud por fuente.
- Fees, retenciones y diferencias.
- Estado del portafolio y ciclos.

Control:

- Paquete de cierre.
- Trazabilidad de cada cifra y match.
- Cambios de reglas/recetas/modelos.
- Accesos, descargas y exportaciones.
- Reaperturas, overrides e investigaciones.

Salidas: vista interactiva, CSV/XLSX, PDF versionado, API, webhook e informe programado.

Toda programación pertenece a la organización con principal de servicio, responsable vigente y conjunto de empresas recalculado en cada ejecución. Enlaces compartidos están ligados a destinatario, requieren autenticación/OTP, caducan, son revocables y registran accesos.

## 12. Fincilia Mobile

Incluye inicialmente:

- Selector de empresa con razón social y NIT visibles.
- Cámara y carga segura.
- Solicitudes, tareas y recordatorios.
- Confirmación sencilla de clasificación.
- Comentarios y evidencia resumida.
- Aprobar/rechazar una propuesta simple con tarjeta mínima de evidencia.
- Estado ejecutivo y monto pendiente.
- Biometría local opcional, step-up server-side, revocación y borrado local.

No incluye inicialmente:

- Mapping de tablas grandes.
- Recetas complejas.
- Conciliación o resolución masiva.
- Configuración de conectores.
- Constructor de informes.
- Cierre o reapertura final del periodo.

Una decisión móvil muestra empresa, NIT, periodo, cuenta, monto, contraparte, razón del match, evidencia y efecto. Push notifications no incluyen montos, NIT, contrapartes ni detalles financieros en la pantalla bloqueada.

La app mantiene versión mínima, kill switch por versión, borrado remoto y estado local cifrado. Un cambio de empresa propuesto por modelo siempre exige confirmación explícita.

## 13. Administración, soporte y facturación

- Entitlements como modelo de dominio: `Plan`, `Entitlement`, `Limit`, `Subscription`, `UsageEvent`, `OveragePolicy`.
- Ledger de consumo explicable y disputable.
- Alertas de uso al 70%, 90% y 100%.
- Estado de plataforma y conectores.
- Downgrade con lectura y exportación; nunca secuestrar evidencia.
- Acceso de soporte JIT ligado a ticket, empresa, recursos, aprobador, motivo y expiración.
- Portal de subencargados y avisos de cambio.
- Procedimiento de derechos del titular.
- Facturación electrónica de las propias suscripciones mediante proveedor habilitado; Fincilia no construye este subsistema.

---

# Parte III — Dominio financiero, datos y evidencia

## 14. Modelo de tenancy y autorización

Entidades:

- `subject`: persona lógica estable; puede tener varias credenciales.
- `user_identity`: credencial OIDC/passkey asociada al subject.
- `organization`: firma, BPO o PYME administradora.
- `organization_membership`: subject, organización, roles y vigencia.
- `company`: frontera financiera permanente.
- `company_membership`: acceso directo de la empresa.
- `engagement`: delegación firma–empresa con alcance, vigencia, responsables y contrato.
- `grant`: autorización efectiva por empresa, recurso, acción y finalidad.
- `service_principal`: integración, job o programación no humana.

Todo registro financiero lleva `company_id NOT NULL`. Los activos administrativos llevan `organization_id`. Los activos compartibles registran propietario y licencia.

La autorización se resuelve server-side contra memberships, engagements y grants vigentes. El token identifica subject/sesión, pero un `company_id` solicitado nunca se confía sin verificación.

La segregación se evalúa por `subject_id`, no por email. IP, dispositivo y sesión son señales de riesgo. Niveles de assurance:

1. Perfil invitado y email verificado.
2. MFA/passkey e invitación contractual.
3. Verificación reforzada definida por cliente para cierres, montos o roles de alto riesgo.

No se recopila documento de identidad por defecto.

## 15. Modelo financiero canónico

### 15.1 Entidades de evidencia y procesamiento

- `data_source`, `connection` y `source_expectation`.
- `source_artifact` y `artifact_version`.
- `document` y `document_classification`.
- `processing_run`, `job_checkpoint` y `engine_release`.
- `raw_record` y `source_record`.
- `schema_profile`.
- `mapping_template_version`.
- `transform_recipe_version` y `manual_overlay`.
- `dataset_version` con estado de completitud.
- `origin_locator` y `lineage_edge`.

### 15.2 Entidades financieras

- `obligation`: factura, pedido, cuenta por cobrar/pagar y saldo abierto.
- `credit_note` y `debit_note`, o subtipo explícito de obligación.
- `money_movement`: pago, débito, crédito, fee, refund, chargeback y ajuste.
- `movement_evidence_link`: N evidencias asociadas a un movimiento.
- `settlement`: agrupación de ventas, fees, retenciones, devoluciones y neto.
- `ledger_entry` y `ledger_line`.
- `counterparty`, `counterparty_alias` y eventos de merge/split.
- `financial_account`.
- `account_balance`.
- `external_reference`.
- `reference_dataset_version`: bancos, festivos, monedas, redondeos, tarifas/tasas autorizadas y TRM.
- `exchange_rate` con par base/cotizada, proveedor, instante efectivo, zona, versión y redondeo.

### 15.3 Conciliación y cierre

- `match_run`, `match_candidate` y `match_score_explanation`.
- `match_group`, `match_member` y `match_decision`.
- `dedupe_candidate` y `merge_decision`.
- `exception`.
- `reconciliation_statement` y `reconciling_item`.
- `close_cycle`, `close_task`, `close_approval` y `closed_snapshot`.
- `reminder_policy`.
- `anomaly_signal` e `investigation_case`.
- `report_definition_version` y `report_snapshot`.

### 15.4 Reglas de tipos

- Importes en decimal exacto, nunca `float`.
- Moneda ISO 4217.
- Monto positivo más dirección explícita.
- `occurred_at`, `posted_at`, `value_date` y **fecha contable** como conceptos separados.
- UTC más zona horaria original.
- Identificador original y normalizado.
- Cuenta tokenizada/last4 cuando baste.
- Valor original textual y locale conservados.
- FX nunca inferido silenciosamente.
- Todo campo publicado conserva linaje.
- Toda corrección es nueva versión u overlay con actor/motivo.

## 16. Pipeline, estados y completitud

```text
Fuente
  → verificación de procedencia
  → aceptación y análisis de contenido
  → quarantine
  → raw inmutable
  → extracción fiel
  → clasificación y perfilado
  → mapping/limpieza versionados
  → validación de esquema y totales
  → evaluación de completitud
  → publicación provisional o certificable
  → modelo financiero
  → conciliación de movimientos y saldos
  → revisión/segregación
  → cierre reproducible
  → informes y evidencia
```

Estados:

```text
Artifact: received → quarantined → accepted | rejected | purged
ImportJob: queued → running → waiting_for_mapping | failed | cancelled | completed
Dataset: draft → validated → partial_unverified | published_complete → superseded
MatchRun: queued → running → review_required → completed | failed | cancelled
Period: planned → collecting → reconciling → review → ready_to_close → closed → reopened
```

Un dataset parcial puede utilizarse para investigar. No puede alimentar auto-match, cierre ni reporte certificado salvo una excepción explícita aprobada con impacto visible.

### 16.1 Reconciliación de completitud

Por fuente, cuenta y periodo se capturan, cuando el origen los ofrece:

- Número de movimientos.
- Suma de débitos.
- Suma de créditos.
- Saldo inicial.
- Saldo final.
- Páginas/secciones esperadas.
- Cursor/ventana de API y última secuencia.

Se comparan con lo ingerido. Los estados son `verified`, `mismatch`, `unknown` o `accepted_exception`. `unknown` no se transforma en “completo”. Una excepción contiene motivo, responsable, aprobador, alcance y fecha de expiración.

## 17. Identidad de movimientos e idempotencia

### 17.1 Separación obligatoria

- `source_record` es una evidencia recibida.
- `money_movement` es un evento económico canónico.
- `movement_evidence_link` enlaza N evidencias con un movimiento.
- `dedupe_candidate` representa una sospecha, no una eliminación.
- `merge_decision` registra por qué dos evidencias se unieron o se mantuvieron separadas.

### 17.2 Claves duras permitidas

- Archivo exacto: `company_id + source_id + sha256`.
- Webhook: `connection_id + provider_event_id`.
- Registro API con ID estable: `connection_id + provider_record_id + provider_version`.
- Extracción: `artifact_hash + parser_version + engine_release`.
- Dataset: `extraction_version + recipe_version + overlay_version + canonical_schema_version`.
- Exportación: `snapshot_id + report_definition_version`.

### 17.3 Fingerprint de candidato

`company + financial_account + posted/value datetime + amount + direction + normalized_reference` puede generar un candidato cross-source. Se enriquecen, cuando existen, ID del proveedor, running balance, secuencia, contraparte, canal y occurrence ordinal.

Ese fingerprint **no es único**. Transacciones legítimas idénticas permanecen separadas si no existe evidencia fuerte de identidad. Una nueva fuente puede aportar otra evidencia al mismo movimiento sin crear otro movimiento; la decisión es determinística cuando hay ID estable y, de lo contrario, revisable/auditada.

### 17.4 Metering e idempotencia

- Un duplicado de upload, replay o reintento no factura de nuevo.
- Evidencias genuinamente distintas de fuentes diferentes son registros de origen distintos y se muestran desglosadas.
- Un merge posterior no borra el evento de uso; una corrección causada por defecto de Fincilia genera crédito automático.
- El ledger de uso es append-only, disputable y trazable al source record.

## 18. Linaje, versionado y reproducibilidad

`origin_locator` identifica:

- Hash y versión del artefacto.
- Página/hoja.
- Fila/columna/celda o bounding box.
- Tag XML/record API.
- Parser/OCR/modelo y versión.
- Receta/paso/overlay.
- Campo canónico.

El linaje hacia match, informe o cierre se almacena como aristas separadas; el localizador original no se muta hacia adelante.

Objetos versionados:

- Parser y motor.
- OCR, clasificador y modelo.
- Esquema canónico.
- Plantilla de mapping.
- Receta y overlays.
- Regla de conciliación y su linaje.
- Datos de referencia.
- Política de anomalías.
- Prompt y proveedor/modelo de IA.
- Definición de informe.
- Configuración del ciclo.

`engine_release` incluye semver, commit, SHA-256 del artefacto, SBOM y clasificación `neutral` o `affects_results`. Una release que afecta resultados se reejecuta sobre corpus adjudicado antes de deploy y se registra en cierres posteriores.

## 19. Motor de matching y automatización

### 19.1 Reglas primero

1. Gates duros.
2. Identificadores exactos.
3. Reglas determinísticas versionadas.
4. Generación acotada de candidatos.
5. Ranking explicable mediante ML clásico si aporta valor.
6. Humano confirma/rechaza cuando no existe regla exacta aprobada.

Un LLM nunca calcula dinero ni confirma matches.

### 19.2 Evidencia por slice

Slices mínimos: `source_pair + rule_lineage_id + case_type + exposure_tier`. La exposición combina monto y política del tenant sin fragmentar tanto que haga imposible reunir evidencia.

- El criterio vinculante es límite inferior unilateral de Wilson al 95% ≥99,5%.
- Existe piso de 1.000 adjudicaciones; no garantiza pasar.
- Con precisión observada cercana a 99,8%, se esperan alrededor de 1.500 casos para superar el límite.
- Candidato único, margen suficiente sobre el segundo y ninguna señal bloqueante.
- Evidencia vigente de últimos 90 días o tres ciclos.
- Cambios cosméticos/restrictivos pueden heredar evidencia tras replay histórico; cambios expansivos no la heredan para nuevos casos.
- Auto-match se habilita gradualmente por límite monetario y se retira automáticamente ante drift, defecto escapado o degradación.

Las estadísticas que autorizan auto-match pertenecen al plano financiero de control, no al warehouse analítico.

### 19.3 Calidad externa

Medir además:

- Defecto material escapado descubierto después del cierre.
- Tasa de corrección humana.
- Concordancia entre revisores.
- Tiempo por revisión.
- Cobertura elegible y abstención.
- Reversiones por regla/modelo.

---

# Parte IV — Arquitectura técnica y almacenamiento

## 20. Principios y stack decidido

1. Monolito modular para dominio/control.
2. Workers aislados para parsing, OCR y cómputo.
3. PostgreSQL como fuente financiera operacional.
4. Object storage como fuente de evidencia binaria.
5. Temporal como fuente de ejecución de workflows durables.
6. Valkey como caché/progreso efímero, nunca autoritativo.
7. Asincronía para trabajo pesado.
8. Contratos, idempotencia, versiones y linaje desde el inicio.
9. Una celda al inicio; catálogo de routing desde el día uno.
10. Tecnología adicional solo mediante umbral medido.

Stack de referencia:

| Capa | Decisión |
|---|---|
| Web | TypeScript, React, Next.js |
| Móvil | React Native; módulos nativos para cámara/OCR/seguridad |
| Dominio/control | NestJS/TypeScript, monolito modular |
| Workers de datos | Python, Polars, DuckDB y Arrow |
| API/contratos | REST/OpenAPI, JSON Schema; eventos versionados |
| Contenedores | ECS/Fargate o equivalente administrado |
| Workflow durable | Temporal Cloud o equivalente gestionado |
| IaC | Terraform/OpenTofu |
| Telemetría | OpenTelemetry |

A-01 se confirma mediante spike corto, no mediante reabrir toda la arquitectura. Si el equipo disponible es predominantemente Python y ≤4 ingenieros, puede proponerse FastAPI para dominio, pero debe conservar contratos y límites modulares.

## 21. Vista lógica

```text
Web / Mobile / API / Email / SFTP
                  │
          CDN · WAF · API Gateway
                  │
       ┌──────────┴───────────┐
       │ Monolito modular     │
       │ org · company · auth │
       │ sources · close      │
       │ match · risk · usage │
       └──────┬─────────┬─────┘
              │         │
       PostgreSQL     AI Gateway ──► OCR/IA autorizada
              │
      transactional outbox
              │
       Queue / Temporal
              │
  ┌───────────┼───────────┬────────────┐
  │ parsers   │ OCR/data  │ matching   │ reporting
  │ workers   │ workers   │ workers    │ workers
  └────┬──────┴─────┬─────┴──────┬─────┘
       │            │            │
  S3 evidence    Valkey       Parquet/projections
       │
  Security account: audit chain · delete ledger · CloudTrail
```

### 21.1 Planos

- **Control:** organizaciones, empresas, engagements, grants, entitlements, fuentes y programaciones.
- **Financiero:** datasets, movimientos, saldos, matches, excepciones, cierres y estadísticas de automatización.
- **Evidencia:** originales, extracciones, derivados, manifiestos, exports y digest.
- **Analítico:** copias derivadas para históricos y simulaciones; nunca autoriza una acción.
- **Seguridad:** auditoría inmutable, delete ledger, logs de nube y material de recuperación.

La definición y derecho de ejecutar un job viven en control; la ejecución durable vive en Temporal; el estado de dominio visible vive en PostgreSQL; el porcentaje efímero vive en Valkey.

## 22. Arquitectura celular

```text
company_id → region_id → cell_id → database_id → storage_namespace → key_id
```

Una celda contiene PostgreSQL, namespaces de objetos, caché, cola/workflows y workers. El producto inicia con una celda.

Crear otra cuando:

- Un tenant supera un porcentaje medido de CPU, I/O, pool, cola o almacenamiento durante 30 días.
- Existen vecinos ruidosos no corregibles con cuotas.
- Un contrato exige aislamiento, región, clave, RPO o mantenimiento.
- La expansión geográfica lo exige.

“15–20% de capacidad” solo se usa si capacidad está definida como una combinación publicada de CPU, IOPS, conexiones, throughput de cola y costo. No se crea una base por PYME.

## 23. Estrategia de almacenamiento

| Tecnología | Uso autoritativo | Prohibido | Adopción |
|---|---|---|---|
| PostgreSQL administrado | Dominio, decisiones, metadatos, grants, auditoría indexada | Binarios grandes | Inicio |
| S3-compatible | Originales, extracción, Parquet, exports, manifests | Permisos como única fuente | Inicio |
| Valkey administrado | Caché, rate limit, progreso, locks con TTL | Roles, matches, saldos o estados finales | Fase 1/multiinstancia |
| DuckDB/Polars/Arrow | Procesamiento temporal por job | Estado compartido | Inicio |
| Parquet | Históricos y snapshots derivados | Decisión operacional | Inicio |
| Warehouse/ClickHouse | Analítica de gran volumen | Fuente financiera | Condicionado |
| PostgreSQL FTS/trigram | Búsqueda inicial | Original binario | Inicio |
| pgvector | Similitud tenant-scoped autorizada | Matching financiero | Condicionado |
| OpenSearch | Búsqueda documental compleja | Fuente de verdad | Condicionado |

### 23.1 Object storage

```text
quarantine/ → recepción restringida y efímera
raw/        → original aceptado, versionado e inmutable
extracted/  → tokens, celdas, tablas y cajas
curated/    → datasets limpios/Parquet
exports/    → entregables con expiración
audit/      → manifiestos y digest append-only/WORM
temporary/  → artefactos de job con TTL
```

Controles:

- Cuenta/bucket por ambiente; namespace opaco por empresa.
- Cifrado KMS, URLs firmadas cortas, acceso privado y versioning.
- El nombre original se conserva como metadato no confiable, escapado y nunca usado como path o HTML.
- Lifecycle hot/infrequent/archive según política; exports/temporary expiran.
- Object Lock protege una **versión**, no la clave; nuevas versiones y delete markers siguen siendo posibles. Todo acceso usa `version_id` fijado en manifiesto.
- Governance se usa solo con permisos de bypass restringidos; Compliance únicamente por obligación validada.
- Legal hold requiere control dual y revisión; no se asume protección contra todo insider.
- Inventario periódico verifica versiones, retención, delete markers y hashes.

### 23.2 PostgreSQL

- Versión soportada con `security_invoker`; mínimo técnico PostgreSQL 15 y versión productiva fijada en ADR-002.
- SLA de parcheo: crítico ≤7 días o antes si existe explotación; alto ≤30 días.
- Aplicación/workers no son owner, superuser ni `BYPASSRLS`.
- `FORCE ROW LEVEL SECURITY` en tablas company-scoped.
- Contexto por transacción con `SET LOCAL`; no `SET` persistente en pool.
- Índices comienzan por `company_id` cuando aplica.
- Constraints e idempotencia en DB.
- Dinero `numeric/decimal`; timestamps con zona.
- JSONB solo para payload fuente acotado/metadatos variables.
- Partición por tiempo/volumen, no una partición por empresa.
- Toda vista normal sobre tablas protegidas usa `security_invoker=true`.
- `SECURITY DEFINER` queda prohibido en plano financiero salvo excepción revisada y probada.
- Materialized views no se exponen directamente: son proyecciones tenant-scoped con tabla destino protegida y vista segura.
- Réplica de informes reproduce roles/policies del primario.
- Prueba negativa por vista, función, proyección y endpoint.

### 23.3 Caché

Namespace mínimo:

`environment + organization + subject/service + hash(companies_authorized) + grant_version + resource_version`.

- TTL obligatorio.
- Invalidación por cambio de membership, engagement, grant o empresa.
- No documentos, secretos ni payload financiero completo.
- Ninguna entrada company-scoped se comparte entre sujetos.
- Caída de Valkey degrada rendimiento, no integridad.

### 23.4 Analítica y escala

Adoptar warehouse cuando:

- Más de 50 millones de movimientos activos o histórico que PostgreSQL no sirve interactivamente.
- Dashboard p95 >2 s pese a índices/réplica/materialización.
- Analítica consume >20% de recursos operacionales o afecta SLO.
- Costo total de separar es inferior al costo/risgo del primario.

Kafka se evalúa con >8–10 consumidores independientes, replay prolongado, CDC masivo o >1.000 eventos/s sostenidos. Kubernetes con 20–30 componentes, GPU/scheduling especial o equipo de plataforma capaz. Hasta entonces: outbox, cola, Fargate y Temporal.

## 24. Orquestación, retries y consistencia

- Outbox publica eventos desde la transacción de dominio.
- Adaptadores no reintentan: clasifican `retryable`, `fatal` o `requires_human` y fallan rápido.
- La cola posee backoff para trabajo stateless.
- Temporal posee retries/timers para workflow durable y espera humana.
- Circuit breaker abre/cierra; no duplica retries.
- Cada job tiene presupuesto máximo de intentos, tiempo y costo.
- Al agotarse: DLQ, estado visible, responsable y acción manual.
- Efectos internos son `effectively-once` mediante constraints/transacción.
- Efectos externos exigen idempotency key/ledger y reconciliación; sin idempotencia del proveedor no se reintenta ciegamente.

Restore consistente incluye PostgreSQL, objetos/versiones, manifests, workflows, secretos y KMS con un instante objetivo documentado.

## 25. Contrato de conectores

Todo conector define:

1. Autorización, revocación y scopes.
2. Cobertura nominal por institución/tipo de cuenta.
3. Backfill, incremental y ventanas históricas.
4. IDs estables e idempotencia.
5. Pending/posted y correcciones.
6. Paginación, rate limits y frescura.
7. Clasificación de errores; sin retries internos.
8. Firmas webhooks y replay protection.
9. Totales/completitud por periodo.
10. SLA, status y modo degradado.
11. Borrado, portabilidad y logs.
12. Región, subencargados, DPA y retención.
13. Precio por cuenta/refresco, mínimo y moneda.
14. Sandbox y pruebas contractuales/golden.

Orden de conectividad:

1. Archivos dominantes del corpus.
2. Facturas emitidas desde ERP/proveedor autorizado.
3. Buzón de documentos recibidos/reportes.
4. Pasarelas con API estable.
5. Exportación neutral hacia ERP.
6. Lectura ERP autorizada.
7. Agregador bancario solo tras B-01.
8. Integraciones directas con demanda pagada.

Los archivos siguen siendo fallback contractual aunque exista API.

## 26. Cloud, región y despliegue

Referencia inicial AWS, pendiente A-02:

- CDN/WAF/API Gateway.
- ECS/Fargate para app y workers.
- PostgreSQL Multi-AZ administrado.
- Valkey administrado.
- S3, SQS/EventBridge, KMS y Secrets Manager.
- Temporal Cloud antes de Fase 2.
- OpenTelemetry a backend administrado.
- Cuenta separada de seguridad/logs y cuenta separada de backup.

No existe región AWS en Colombia. Se comparan São Paulo (`sa-east-1`) y Norte de Virginia (`us-east-1`) con medición desde Colombia, servicio, costo, egress, resiliencia y contrato de transmisión. Ningún dato DRG-00 se carga antes de decidir.

El parseo Fargate se diseña conforme a la plataforma real:

- Aislamiento de microVM del runtime administrado.
- Usuario sin privilegios y filesystem raíz read-only.
- Almacenamiento efímero cifrado/limitado.
- Subred privada sin NAT por defecto.
- VPC endpoints solo hacia servicios necesarios.
- Sin privilegios elevados ni acceso general a secretos.
- CPU/RAM/tiempo/páginas/filas/expansión acotados.

Ambientes separados: local, dev sintético, staging con corpus saneado, producción, sandbox de integraciones, seguridad/logs y backups. IaC, migraciones forward-compatible, canary/blue-green, flags con dueño/fecha y previews sin producción.

---

# Parte V — Seguridad, privacidad y cumplimiento

## 27. Clasificación y responsables

| Nivel | Ejemplos | Controles mínimos |
|---|---|---|
| Público | Sitio/documentación | Integridad y publicación controlada |
| Interno | Roadmap, métricas saneadas | SSO y mínimo privilegio |
| Confidencial | Organizaciones, usuarios, configuración | Cifrado, RBAC, auditoría |
| Financiero sensible | Movimientos, facturas, cuentas, cierres | Cifrado, ABAC, masking, linaje y export control |
| Secreto | Tokens OAuth, API keys, claves | Vault/KMS, rotación, service-only |
| Prohibido | CVV, credenciales bancarias/DIAN, passwords | No recopilar ni persistir |

Responsables: comité de riesgo, Security owner, Privacy owner, comité de IA, data owners, model owners, experto contable y auditor independiente. Cada función debe asignarse nominalmente antes de DRG-01.

Cadencia:

- Acceso privilegiado interno: mensual.
- Acceso cliente: trimestral y ante offboarding.
- Proveedor crítico: anual y ante cambio.
- IA AI-2/AI-3: por versión y trimestral.
- Restore: trimestral; DR completo semestral.
- Tabletop de incidentes: semestral.
- Pentest focal antes de DRG-01; completo antes de Fase 3/GA y anual.

## 28. Identidad, autorización y segregación

- IdP B2B administrado con OIDC.
- MFA obligatorio para internos y roles privilegiados; passkeys preferidas.
- SSO/SCIM cuando el cliente lo requiere.
- Sesiones/dispositivos revocables.
- Step-up para exportar, cambiar roles, conectar fuente, reabrir/cerrar, cambiar retención o borrar.
- Cuentas de servicio sin login interactivo y scopes mínimos.
- Recuperación resistente a ingeniería social.

Roles base:

- Owner organización: gobierno, sin datos financieros implícitos.
- Admin seguridad: identidad/política/auditoría, sin payload financiero por defecto.
- Admin facturación: plan/pago, sin finanzas.
- Gerente portafolio: engagements/empresas asignadas.
- Preparador.
- Revisor/aprobador.
- Dueño PYME.
- Colaborador cliente.
- Auditor read-only.
- Cuenta de integración.

Reglas:

- Un `subject_id` no prepara y aprueba la misma corrección, regla, excepción, match o cierre.
- Un deny de SoD vence la unión de roles.
- Organización unipersonal registra `self_certified_without_independent_review` y lo muestra en cierre.
- Cambiar una regla y usarla en el mismo cierre exige segundo control.
- Soporte solo con grant JIT.
- Worker recibe scope por job/empresa.
- Owner/Admin requieren grant financiero separado.
- Toda programación y enlace entra en offboarding.

## 29. Defensa multitenant

Capas:

1. Autorización API.
2. Engagement/grant vigente.
3. RLS y constraints PostgreSQL.
4. IAM/namespaces de objetos.
5. Namespace de caché por subject/companies/grant version.
6. Scope en cola, Temporal y worker.
7. Proyecciones analíticas tenant-scoped.
8. Redacción de observabilidad.
9. Pruebas automáticas cross-tenant.

No existe consulta consolidada sin recalcular el conjunto de empresas autorizado.

## 30. Plano de nube y criptografía

- Cero roles humanos permanentes con acceso a datos productivos.
- Elevación JIT ligada a ticket, aprobador distinto, alcance, razón y duración ≤4 h.
- Sesión administrativa grabada y revisión posterior.
- Política KMS niega decrypt permanente a humanos; break-glass es temporal, dual y auditado.
- CloudTrail con S3 data events hacia cuenta de logs append-only.
- Controles organizacionales impiden desactivar trails o modificar claves sin proceso.
- Break-glass: doble aprobación, credencial sellada, expiración automática y revisión ≤24 h.
- TLS 1.2 mínimo; 1.3 preferido.
- Envelope encryption/KMS, claves por ambiente y rotación.
- Secret manager; no secretos en repo, logs, imágenes o app.
- Tokens OAuth cifrados y con scopes mínimos.
- Backups y discos cifrados; material KMS incluido en ejercicios de recuperación.

## 31. Seguridad de archivos y contenido

### 31.1 Aceptación

- Sesión autorizada y URL firmada de una sola clave opaca.
- Firma/MIME y allowlist.
- Tamaño, páginas, filas, columnas, compresión y tiempo.
- Antivirus y CDR donde corresponda.
- Protección ZIP/decompression bomb, XXE, polyglot, macros, objetos activos y PDF activo.
- Fórmulas no se ejecutan; al exportar se neutralizan prefijos `=`, `+`, `-`, `@`, tab y CR según formato.
- Original fuera del webroot; descarga con headers seguros.
- Workers sin internet ni vault general.

### 31.2 PAN, credenciales y PCI

- Escaneo determinístico en streaming o canal de aceptación aislado antes de promover a `raw/`.
- Detectores de PAN con patrón + Luhn; CVV, passwords, tokens y credenciales mediante patrones/secret scanner.
- Si se detecta, se rechaza o redacta mediante flujo aprobado; se conserva solo hash/metadato mínimo cuando sea legal.
- El original sospechoso no se libera de cuarentena y se purga según runbook.
- Fincilia no afirma quedar fuera de PCI hasta recibir concepto QSA sobre el flujo completo, incluida cuarentena.

## 32. Auditoría y evidencia de seguridad

Registrar login/MFA/dispositivo, vistas/descargas, exportaciones, roles, grants, fuentes, recetas, reglas, modelos, matches, overrides, cierres, reaperturas, retención, borrado, soporte y break-glass.

Evento mínimo: actor/subject, organización, empresa, acción, recurso/versión, propósito/motivo, sesión/IP/dispositivo, correlation ID y tiempo.

- Allowlist de `before/after`; no payload, secreto, binario o texto libre completo.
- Cadena append-only con `sequence`, `previous_hash` y digest firmado.
- Aplicación solo inserta/lee lo autorizado; no actualiza ni elimina auditoría.
- Streaming continuo de digest/manifiesto a cuenta WORM.
- Admin seguridad ve metadatos, no finanzas, salvo grant explícito.
- Acceso a observabilidad tiene RBAC, retención, allowlist de campos y auditoría propia.

## 33. Privacidad, retención y borrado

### 33.1 Programa

- Inventario de datos, finalidad, sensibilidad y owner.
- Rol Responsable/Encargado por flujo.
- DPA, subencargados y mecanismo de cambios con preaviso/objeción.
- Minimización y masking.
- Canal para acceso, corrección, portabilidad, revocación y supresión.
- Verificación proporcional de solicitante y enrutamiento cuando Fincilia es Encargado.
- Registro de plazos, respuesta y evidencia de cumplimiento.
- DPIA antes de IA externa, nuevos fines, fine-tuning o cambio material.

Precedencia:

`legal hold → obligación legal/contractual validada → instrucción del Responsable → configuración operativa`.

La retención de soporte contable se ancla, cuando aplique, al último asiento/documento/comprobante y no al `created_at` de la carga. Otros datos tienen relojes propios. El plan comercial define tier/latencia/costo, nunca acorta una obligación.

### 33.2 Delete ledger y restore

`delete_ledger` vive en la cuenta de seguridad, fuera de la unidad restaurable, append-only y con Object Lock. Contiene tombstone, alcance, subject/tenant, tablas, claves/versiones de objeto, derivados, fecha, fundamento, solicitante y hash. Su retención supera la del backup más largo.

Todo restore:

1. Recupera DB, objetos, manifests, workflows, secretos y KMS al instante objetivo.
2. Consulta el delete ledger externo.
3. Reaplica cada tombstone anterior al instante restaurado.
4. Purga derivados, cachés, índices, exports y proveedores.
5. Reconcilia conteos/hashes.
6. Solo entonces se declara exitoso.

## 34. Marco colombiano y límites legales

Requiere concepto jurídico, pero el diseño parte de:

- Ley 1581 de 2012: datos personales de personas naturales.
- Ley 1266 de 2008 cuando el flujo realmente sea información financiera/crediticia/comercial; puede cubrir persona jurídica.
- Circular SIC 002 de 2024 para IA: necesidad, proporcionalidad, precaución, privacidad e explicabilidad.
- Circular SIC 001 de 2025: validar alcance fintech y decisiones automatizadas desfavorables.
- Circular SIC 002 de 2025 y concepto 2026: transferencia/transmisión y tecnología/datasets con datos personales.
- Decreto 0368 de 2026: finanzas abiertas obligatorias para entidades vigiladas frente a terceros receptores vigilados; Fincilia no obtiene acceso universal automático.
- Resolución Única DIAN 000227 de 2025 y normativa compilada de facturación.
- Facturación electrónica propia de las suscripciones mediante proveedor habilitado.
- RNBD solo si se supera el criterio aplicable; el resto de obligaciones subsiste.

Transmisión a encargado extranjero y transferencia entre responsables no son sinónimos. La región/productor se elige con contrato, finalidad, subencargados, medidas y mecanismo jurídico apropiado.

Fincilia no genera/transmite facturas del cliente ni eventos DIAN sin módulo jurídico separado y proveedor tecnológico habilitado. El buzón ingiere documentos por instrucción del cliente.

## 35. Incidentes, continuidad y dependencias

Registrar `detected_at`, `aware_at` y `confirmed_at`. Operativamente `aware_at` inicia el reloj interno de evaluación/reporte, sujeto a concepto jurídico; no se espera confirmación final para escalar.

Objetivos SEV-1:

- Page ≤15 min.
- Incident Commander ≤30 min.
- Contención inicial ≤1 h.
- Evaluación legal/privacidad ≤4 h.
- Aviso al Responsable afectado ≤24 h desde conocimiento razonable de incidente material confirmado o altamente probable, salvo plazo más estricto.

RPO/RTO:

| Indicador | Inicial | Maduro |
|---|---:|---:|
| RPO operacional | 15 min | 5 min |
| RTO central | 4 h | 2 h |
| Objeto hot | 1 h | 30 min |
| Restore | Trimestral | Mensual automatizado + trimestral completo |

SLO interno, SLA contractual y objetivo DR se reportan separados; un desastre no desaparece del SLO interno.

Modo degradado:

| Componente | Comportamiento |
|---|---|
| IdP | Sesiones vigentes continúan según riesgo; no login nuevo; SEV-1 si afecta cierre |
| KMS | Lectura/escritura de evidencia detenidas; no bypass inseguro |
| Temporal | Workflows en pausa y recuperación durable |
| S3 | Carga rechazada; nunca confirmación optimista |
| Email/push | Mensajes en cola; estado visible en app |
| Antivirus | Cuarentena no se libera |
| Conector | Frescura visible y fallback por archivo |
| OCR/IA | Reintento o flujo manual; núcleo determinístico disponible |

## 36. Secure SDLC y proveedores

- Branch protection, revisión y CI/CD federado.
- SAST, DAST, secrets, dependency, container e IaC scanning.
- SBOM y firma por release; imágenes fijadas por digest.
- Threat model por épica sensible.
- Datos sintéticos en desarrollo; staging solo con corpus autorizado/saneado.
- OWASP ASVS 5.0 como baseline, mapeado requisito por requisito.
- NIST CSF 2.0 y SSDF SP 800-218 v1.1.
- Feature flags con owner, fecha y rollback.

Proveedor crítico: región, personal, cifrado, subencargados, retención, training, incidente, SLA, RTO/RPO, DPA, portabilidad, exit plan, certificaciones, costo/moneda y budget cap.

Ruta de assurance: readiness interno → SOC 2 Type I si el mercado lo exige → Type II → ISO 27001/27701 según socios. No se compra una certificación como sustituto de controles.

---

# Parte VI — Gobierno de inteligencia artificial

## 37. Política

Antes de usar IA:

1. ¿Existe una solución determinística suficiente?
2. ¿Qué daño causa un error o fuga?
3. ¿La salida puede validarse automáticamente?
4. ¿Existe evidencia y revisión humana?
5. ¿El Responsable autorizó finalidad/proveedor/datos?
6. ¿Beneficio supera costo, latencia y riesgo?

Niveles:

| Nivel | Uso | Gobierno |
|---|---|---|
| AI-0 | Función determinística crítica | Pruebas tradicionales y auditoría |
| AI-1 | Ayuda sin datos financieros | Revisión básica |
| AI-2 | Extracción/clasificación reversible | Evals, confianza, override y opt-out |
| AI-3 | Recomendación financiera, señal de riesgo o control de fuga | DPIA/AIA, validación independiente y humano |
| AI-4 | Decisión autónoma sobre libros, acceso, fraude, derechos o dinero | **Prohibido** |

Antes de AI-2/AI-3: problema, alternativa determinística, datos mínimos, daño, reversibilidad, explicación, reviewer, fallback, métricas, drift, proveedor, región, costo y retiro.

## 38. Matriz de usos

| Caso | Baseline | IA | Efecto permitido |
|---|---|---:|---|
| MIME/formato | Firma/parser | No | Automático determinístico |
| OFX/XML/UBL | Parser/XSD | No | Automático validado |
| OCR | Modelo documental | Sí AI-2 | Extraer; campos críticos validados |
| Clasificar documento | Reglas + clasificador | Sí AI-2 | Autoenrutar solo con gate |
| Sugerir mapping | Reglas/embeddings/LLM | Sí AI-2 | Confirmación inicial |
| Crear receta | Asistente | Sí AI-2 | Solo genera DSL determinística; preview humano |
| Tipar datos | Perfil + modelo | Sí AI-2 | Ambigüedad se confirma |
| Candidatos match | Reglas/ML clásico | Sí AI-3 | Ranking, no decisión LLM |
| Confirmar match | Regla calibrada | LLM prohibido | Solo §19 |
| Dinero/impuesto/saldo | Decimal/reglas | Prohibida | Determinístico |
| Anomalía | Reglas/estadística/ML | Sí AI-3 | Señal, no veredicto |
| Declarar fraude | — | Prohibida | Nunca |
| Aprobar/cerrar/reabrir | Workflow humano | Prohibida | Actor autorizado |
| Acceso/retención/borrado | Política | Prohibida | Determinístico y aprobado |
| Resumen grounded | Consulta + LLM | Sí AI-2/3 | Borrador con links |
| Soporte interno | RAG documental | Sí | Sin datos financieros implícitos |
| Redacción pre-egreso | Determinístico + NER | Sí AI-3 seguridad | Falla cerrada; modelo solo añade detecciones |

## 39. AI Gateway

Único punto de egreso hacia OCR/IA externa:

- Verifica tenant, empresa, finalidad, policy, plan y base/instrucción.
- Clasifica/minimiza y aplica redacción.
- Reglas/checksums primero; modelo solo agrega detecciones.
- Selecciona proveedor/modelo/región permitidos.
- Prompt/schema/versiones fijados.
- Valida salida tipada.
- Mide costo, latencia, calidad y abstención.
- Registra proveedor/modelo/versión sin payload crudo.
- Fallback determinístico/humano.
- Kill switch por tenant/caso/modelo/proveedor.
- Budget duro por tenant/caso; al agotarse pasa a manual, no a sobrecosto silencioso.
- Sin prompts/respuestas crudos en logs generales.
- Sin cadena interna de razonamiento; solo explicación verificable.

Si falta policy, DPA, subencargado, región, retención, clase permitida o redactor, **no hay egreso**.

Datos prohibidos: secretos, credenciales, PAN/CVV, documento completo si bastan campos, información de otra empresa, datos fuera de finalidad y texto documental interpretado como instrucción.

## 40. Evals, despliegue y retiro

- Corpus gold separado por empresa/fuente/template/locale/calidad.
- Train/test separados por empresa y documento.
- Precisión/recall/calibración/abstención por campo y slice.
- Exactitud monetaria/fecha/NIT.
- Tasa de aceptación/corrección humana y defectos escapados.
- Prompt injection, exfiltración y tool abuse.
- Costo y latencia por tenant/plan.
- Model/data cards, registry, lineage y owner.

Shadow y canary deben declarar:

- Volumen/ciclos mínimos.
- Métricas y umbrales de promoción.
- Presupuesto de error.
- Cohorte, duración y rollback.
- Qué decisiones ya emitidas revisar/retirar si la versión se revierte.
- Corrección por multiplicidad cuando se comparan muchos slices.

Aprendizaje:

1. Modelos administrados sin training con datos del cliente.
2. Reglas/modelos clásicos por tenant.
3. Global solo con sintético, público licenciado o anonimización demostrada.
4. Fine-tuning de cliente mediante programa separado, DPIA, contrato, opt-out y finalidad específica.

## 41. IA móvil y Needle 2

Decisión:

> **Needle 2 no forma parte del producto, el data plane ni el roadmap crítico. Se reevalúa en 12 meses o cuando exista binding mantenido, evidencia fuerte en español y caso económico, lo que ocurra después.**

Razones verificadas:

- Confianza no fiable en español incluso en el modelo base.
- Fine-tuning deshabilita la señal nativa de confianza.
- Español consume aproximadamente 1,7× tokens y reduce la ventana efectiva.
- Binding React Native oficial archivado.
- Calidad insuficiente para acciones financieras.
- Ahorro cloud ilustrativo muy inferior al costo de integración/QA.

Se mantienen:

- OCR nativo Apple Vision/VisionKit y Google ML Kit para preview/captura.
- Intents locales determinísticos.
- Adapter `OnDeviceCapabilityProvider` desacoplado.
- AI Gateway como fallback autorizado.
- Ningún side effect desde modelo edge.

El OCR móvil no publica evidencia canónica: el servidor reprocesa el original. Offline solo crea borrador cifrado; nunca muestra una mutación como completada.

---

# Parte VII — Planes, pricing y economía

## 42. Principios comerciales

1. Solo tres planes públicos: Esencial, Control y Firma.
2. Seguridad fundamental, SoD, auditoría y exportación en todos.
3. No cobrar por usuarios, reglas ni reruns técnicos.
4. Métrica principal: empresa activa + banda transparente de registros de origen procesados.
5. `source_record_published` queda como ledger técnico/contractual, mostrado por fuente; nunca se llama “movimiento único”.
6. `ocr_page_processed` es segunda unidad limitada porque determina costo.
7. Feeds premium y conectores con costo externo se muestran por separado.
8. Duplicados, reintentos y correcciones de producto no vuelven a cobrar.
9. Exceso nunca bloquea lectura, auditoría, exportación o supresión.
10. Todo precio permanece hipótesis hasta C-01.

## 43. Tres planes propuestos para pruebas

Valores mensuales antes de IVA. Son **bandas de investigación**, no precios publicados.

| | Fincilia Esencial | Fincilia Control | Fincilia Firma |
|---|---:|---:|---:|
| Precio a probar | COP $129k–$169k | COP $349k–$449k | Base COP $399k–$599k |
| Comprador | PYME recurrente | PYME multicanal | Firma/BPO |
| Empresas activas | 1 | 1; expansión limitada | 3 incluidas; escala por empresa activa |
| Usuarios | Sin cobro, uso razonable | Sin cobro | Sin cobro |
| Registros de origen/mes | 5.000 | 25.000 | 30.000 compartidos iniciales |
| Fuentes | 5 | 15 | 30 compartidas |
| OCR candidato | 250 páginas | 1.000 páginas | 1.500 páginas compartidas |
| Feed bancario | No prometer hasta B-01 | No prometer hasta B-01 | Por cuenta o paquete tras B-01 |
| Ingesta | Archivo, correo, móvil | + SFTP, API/webhooks | + administración masiva |
| Conciliación | Dos lados, parciales, 1:N/N:1 | Multilateral, fee, retención, FX, reverso | Igual + plantillas portafolio |
| Cierre | Sí | Avanzado | Matriz multiempresa |
| Gobierno | Roles, SoD, evidencia, auditoría | Roles personalizados/API | Firma/cliente/equipo |
| Señales | Reglas esenciales | Estadística/políticas | Consolidado por empresa |
| Informes | Estándar | Programados/avanzados | Multiempresa/marca básica |

Empresa adicional de Firma a probar: **COP $85k–$99k/mes**, con cuota de registros/fuentes definida tras pilotos. Un feed no se incluye si su COGS impide margen incremental ≥70%; puede venderse como pass-through transparente.

El plan Firma cobra la capacidad de conciliar/cerrar una empresa, no el derecho de verla en un panel. Empresas archivadas sin procesamiento no facturan.

### 43.1 Posicionamiento por plan

- **Esencial:** banco-libros o pasarela-banco, autoservicio. No vender a quien ya está resuelto por su ERP.
- **Control:** producto héroe para factura/pedido → pasarela → liquidación → banco → ERP.
- **Firma:** sistema operativo de conciliación/cierre para cartera multiempresa; base + empresa activa, no bloque rígido de diez.

### 43.2 Límites y overage

Categorías:

1. Registros de origen adicionales.
2. OCR adicional.
3. Evidencia hot/archivo frío.
4. Feed/conector premium.
5. Servicios: backfill, receta compleja, onboarding, conector, celda o marca avanzada.

Reglas:

- Gracia candidata 15%.
- Primer exceso aislado: advertencia, no sorpresa.
- Avisos 70/90/100 con proyección de factura.
- Overage en bloques predecibles; declarar si es one-off o eleva la base.
- Legal hold nunca se rompe por límite; se cobra almacenamiento o se archiva con acceso compatible.
- Downgrade conserva lectura/exportación por ventana contractual.

## 44. Pricing discovery y comparación

Competidores que deben estar en cada revisión:

- Siigo contador: panel multiempresa con ancla muy baja/gratis.
- Alegra: ERP + espacio contador, bancos y conciliación.
- Dext: precio por cliente para firmas.
- Cointab y Synder: fuentes/transacciones.
- Odoo: usuarios; multiempresa/API en plan correspondiente.
- Simetrik: conciliación empresarial, competidor de categoría y capital.
- Reconcilio y otros especialistas de matching.

Fincilia no compite con “contabilidad incluida”. Su prueba de valor es:

- Fuentes heterogéneas sin reemplazar ERP.
- Importación visual y limpieza reproducible.
- Completitud y conciliación de saldos.
- Evidencia por cifra.
- Cierre reproducible y portabilidad.

Tabla competitiva debe registrar precio, moneda, IVA, unidad, usuarios, empresas, feeds, fecha, URL y TRM. Comparar COP/USD sin TRM está prohibido.

## 45. Pilotos pagados

Diseño recomendado:

- Tres firmas × 3–5 empresas.
- Cinco PYMEs independientes.
- 14–20 entornos totales.
- Dos ciclos reales, baseline previo y alcance congelado.
- Datos sintéticos/saneados antes de DRG-01; datos reales solo después.

Ofertas a probar:

| Oferta | Alcance | Banda inicial |
|---|---|---:|
| Piloto empresa, 60 días | 1 empresa, 3 fuentes, cuota alineada con Control, 2 ciclos | COP $0,9M–$1,2M |
| Piloto firma, 60–90 días | 3–5 empresas, 2 plantillas, 2 ciclos | COP $1,9M–$3,0M |
| Setup | Solo alcance incremental y documentado | Según horas y complejidad |

El crédito de piloto es máximo 50%, no apilable, sujeto a margen y aplicado de forma que el año 1 conserve piso ≥70%. Alternativa preferida: crédito contra renovación/año 2. No se promete conector no certificado.

Medir:

- SRP por movimiento económico.
- Páginas OCR por fuente.
- KB hot/frío por registro y empresa.
- Costo real de feed por cuenta/refresco.
- Horas de soporte/onboarding.
- Trabajo manual y duración de cierre antes/después.
- Valor recuperado/explicado.
- Disposición a pagar por empresa activa vs banda de volumen.

Experimentos:

- Dos anclas: empresa activa y volumen.
- Mostrar Firma junto a Siigo/Alegra sin defender el precio y registrar reacción.
- Conjoint de empresa, fuentes, OCR, soporte y automatización.
- Van Westendorp solo como señal.

## 46. Unit economics y guardrails

No se publica un precio hasta modelar:

- Infraestructura/base/auditoría.
- Ingesta/matching al 65% y 100% de uso.
- Feed por cuenta y refresh.
- OCR/IA por página/caso.
- S3 hot/frío, restores y egress.
- Temporal, IdP, email/push, antivirus, observabilidad.
- NAT/VPC endpoints.
- Soporte/onboarding/customer success.
- Recaudo por evento y medio.
- Facturación electrónica propia.
- Moneda de costo y sensibilidad FX ±10%/±25%.

Guardrails:

- Piso de margen bruto 70%; objetivo estable 75–85%.
- Anualidad solo si margen a **100% de utilización** ≥75%.
- Recaudo anual ≤1% mediante PSE/transferencia u opción demostrada; tarjeta no se asume.
- OCR/IA idealmente ≤10% del ingreso.
- COGS variable total objetivo ≤25%.
- Margen incremental de overage/empresa ≥70%.
- Crédito, anualidad, canal y descuento nunca se apilan bajo el piso.
- Costo internacional extraordinario es pass-through visible.

El modelo debe separar año 1 y cohortes estables; el crédito de piloto no desaparece del cálculo.

## 47. Canal firma–cliente

Antes de GA se decide contractualmente si la firma actúa como:

- Comprador principal.
- Revendedor.
- Referidor/agente.
- Encargado que opera por cuenta de la PYME.

Se define quién factura, quién es Responsable/Encargado, propiedad del engagement, atribución, comisión, no captación y efecto tributario. Grupo empresarial no puede simular firma para arbitraje sin cumplir definición de beneficiarios/empresas independientes.

---

# Parte VIII — Programa completo de construcción

## 48. Horizonte y fases

Horizonte: **18 meses**, releases acumulativos. GA inicial y producto completo son gates distintos; no se rebaja exactitud para cumplir calendario.

### Fase −1 / DRG-00 — semanas 0–3

Objetivo: poder recibir corpus real acotado sin fingir que anonimizar no es tratamiento.

Entregables:

- Contratos de tratamiento y finalidad.
- Matriz L-01 para corpus.
- Ambiente aislado.
- Inventario nominal y acceso mínimo.
- Procedimiento de saneamiento y borrado.
- Sin IA externa.

Gate: DRG-00 firmado por Legal, Security y Product.

### Fase 0 — validación y arquitectura ejecutable, meses 0–3

Esfuerzo: 18–22 persona-mes.

- Observar 10 cierres y 5 firmas.
- Corpus de 150–250 documentos con 3–5 bancos reales, 3 pasarelas, 2 ERP y DIAN.
- Obtener archivos/exportaciones reales y documentar PDF cifrado/formato dominante.
- Tres cotizaciones firmadas de agregadores con cobertura bancaria nominal y costo.
- Confirmar buyer, ICP, wedge y pricing discovery.
- Prototipos navegables de portafolio, importación, conciliación, cierre, solicitud móvil y seguridad.
- Modelo tenancy `organization/company/engagement`.
- Modelo canónico con saldos, completitud y dedupe seguro.
- Threat model, DFD, mapa de privacidad y RBAC/ABAC/SoD.
- ADRs bloqueantes y spike de stack.
- Búsqueda legal de Fincilia, dominios y sistema mínimo de marca.
- Presupuesto absoluto hasta Fase 2 +30%.
- Calendario fiscal/operativo colombiano.

Gate: artefactos bloqueantes aprobados y capital confirmado.

### Fase 1 — plataforma y evidencia, meses 3–7

- Identidad, organización, empresa, engagement y grants.
- RLS/vistas seguras, control de nube y break-glass.
- PostgreSQL, S3, outbox/cola, Valkey y auditoría.
- Upload/cuarentena, PAN/credenciales, idempotencia y delete ledger.
- Cuatro formatos dominantes del corpus; no asumir OFX.
- Fincilia Clean tabular, recetas, overlays, drift y export limpio.
- Completitud y linaje 100%.
- Metering desde el primer registro/página/feed.
- AI Gateway mínimo para cualquier OCR externo.
- Backup/restore con tombstones.
- Observabilidad, CI/CD, SLO y accesibilidad base.
- Pentest focalizado.

Gate: aislamiento y restore demostrados; ningún alto/crítico abierto; 100% de campos publicados con linaje.

### Fase 2 — conciliación y cierre, meses 7–10

- Modelo financiero completo, saldos y statement.
- Matching 1:1, 1:N, N:1, parcial y net settlement.
- Excepciones/colaboración.
- Ciclos, recordatorios, sala de cierre y reapertura.
- Temporal operativo.
- Portafolio multiempresa.
- Informes operativos/control.
- App companion para captura, solicitudes y decisiones simples.
- Piloto real controlado tras DRG-01.

Gate: dos ciclos por piloto, cero defecto material escapado, trabajo manual −40% y cierre −30%.

### Fase 3 — conectividad y automatización, meses 10–13

- Correo/DIAN con procedencia.
- Facturas emitidas desde ERP/proveedor autorizado.
- Primeras pasarelas y export ERP.
- PDF/OCR prioritarios según corpus.
- Reglas no-code controladas y simulación histórica.
- Informes programados, API/webhooks y SFTP.
- Entitlements, billing y facturación electrónica propia.
- Agregador bancario solo si B-01, legal y margen pasan.
- Pentest completo antes de ampliar cohortes.

Gate: conectores con SLA/fallback y COGS dentro de guardrail.

### Fase 4 — inteligencia gobernada, meses 13–16

- Clasificación/mapping asistidos.
- Señales estadísticas por empresa/fuente.
- AI Gateway completo, evals y registry.
- Narrativas grounded de informes.
- Shadow/canary/drift/rollback/retiro.
- Búsqueda y exploración histórica.
- Sin Needle 2.

Gate: todo modelo tiene eval, owner, policy, fallback, budget y defecto escapado dentro de umbral.

### Fase 5 — escala y madurez, meses 16–18

- SSO/SCIM y políticas avanzadas.
- Prueba de transferencia de engagement/cambio de contador.
- Catálogo de routing y migración entre celdas.
- Prueba sintética de 50 empresas; 10–20 reales operadas antes de afirmación comercial.
- Warehouse solo si se activa umbral.
- DR maduro, compliance readiness y vendor reviews.
- White-label básico si demuestra conversión.
- Optimización de margen, soporte y conectores pagados.

Gate: producto completo §55.

## 49. Equipo y capacidad

Curva orientativa:

| Meses | FTE efectivos | Composición principal |
|---|---:|---|
| 0–1 | 5–6 | Product/fundador, contador, diseño, arquitecto/backend, data, seguridad/privacy full-time, legal fraccional |
| 2–3 | 7–8 | + backend, Platform/SRE e Integrations |
| 3–7 | 9–10 | + QA/SDET, frontend; seguridad mantiene dedicación fuerte |
| 5–10 | 10–12 | + móvil desde mes 5, Customer Success |
| 10–18 | 10–12 | + ML/data según Fase 4 y segundo QA |

Roles:

- Product lead/fundador.
- Contador de dominio.
- Product designer con accesibilidad.
- Dos o tres backend/full-stack.
- Data engineer.
- Integrations engineer.
- Platform/SRE.
- Mobile engineer.
- QA/SDET.
- Security/Privacy lead.
- Legal externo especializado.
- Customer Success/onboarding.
- ML engineer solo cuando existe dataset/caso de Fase 4.

Seguridad/privacidad no puede ser media jornada durante Fase 0. Platform/SRE e Integrations entran desde mes 2; móvil desde mes 5.

## 50. Capital y liberación por gate

Antes de contratar construcción debe existir caja para terminar Fase 2 +30% de contingencia. El presupuesto presenta COP y USD, TRM y fecha.

Incluye:

- Nómina/cargas/contratistas.
- Cloud y ambientes.
- Temporal, IdP, observabilidad, antivirus y OCR.
- Legal, privacidad, QSA y marcas.
- Pentests y dispositivos.
- Corpus/pilotos/onboarding.
- Soporte y guardias.
- Contingencia FX.

No se cuenta ingreso proyectado no contratado como runway. Cada fase libera presupuesto al superar su gate.

## 51. Artefactos bloqueantes

### Antes de Sprint 1

- PRD general y del wedge.
- Modelo organization/company/engagement.
- Modelo canónico y diccionario con saldo/completitud/dedupe.
- C4 y DFD.
- Threat model.
- Matriz RBAC/ABAC/SoD.
- Especificación de linaje.
- Contrato de conector.
- Estados/eventos y retry ownership.
- ADR-001 a ADR-010 y ADR de engine release.
- Corpus sintético y golden tests iniciales.
- Design system/prototipo navegable.

### Antes de Fase 2/datos reales

- L-01, DPA, subencargados y región.
- Delete ledger/restore.
- Cloud control/break-glass.
- PCI/QSA.
- Plan de incidentes.
- Vendor due diligence.
- Evals del AI Gateway mínimo.
- Pentest focal.
- Paquete de portabilidad y cambio de contador diseñado.

### Antes de GA

- Pricing/COGS validados.
- Facturación electrónica propia.
- Contratos y canal B2B2B.
- Marca solicitada o estrategia jurídica aprobada.
- Pentest completo, SLO/DR y runbooks.
- Soporte/on-call dimensionados.

## 52. Primeros 30 días

### Semana 1

- Nombrar owners de Product, Contabilidad, Security, Privacy, Architecture y Legal.
- Abrir búsqueda formal de **Fincilia** y reservar dominios/handles solo tras verificación inicial.
- Reclutar 5 firmas y seleccionar 10 cierres observables.
- Cerrar plantilla contractual DRG-00.
- Crear repo, ADR template, estándares y CI sintético.

### Semana 2

- Ejecutar tres entrevistas de proceso y mapear un cierre completo.
- Definir taxonomy de documentos/fuentes y plan de corpus.
- Prototipar Portafolio, Estudio de Importación y Sala de Cierre.
- Redactar DFD v0 y threat model v0.
- Diseñar organization/company/engagement y probar cambio de contador en papel.

### Semana 3

- Aprobar DRG-00.
- Iniciar recepción aislada/inventariada del corpus.
- Ejecutar spike NestJS/Python: auth context, RLS, outbox y job de parser.
- Conseguir exportaciones reales de bancos y pasarelas.
- Solicitar tres cotizaciones de agregador.

### Semana 4

- Publicar modelo canónico v0.1 con balances, statements y completeness.
- Etiquetar primeros golden files.
- Ejecutar test de usabilidad con contadores/PYMEs.
- Aprobar ADRs 001–005.
- Presentar presupuesto F0–F2 +30%.
- Realizar revisión ejecutiva: continuar, ajustar wedge o detener.

## 53. Plan 30–60–90

### Día 30

- DRG-00 operativo.
- Fincilia en clearance legal.
- ICP/wedge provisional confirmados.
- Primer corpus inventariado.
- Arquitectura y modelo canónico v0.1.

### Día 60

- 6–8 cierres observados.
- 100+ artefactos etiquetados.
- Cuatro formatos dominantes identificados.
- Prototipo navegable validado.
- Threat model/RBAC/retención en revisión.
- Cotizaciones y cobertura bancaria recibidas.
- Pricing interviews en marcha.

### Día 90

- Fase 0 gate.
- 10 cierres/5 firmas y corpus 150–250.
- ADRs bloqueantes aprobados.
- Modelo, golden suite y backlog Fase 1.
- Región/stack/marca decididos o con bloqueo explícito.
- Capital comprometido.
- No datos piloto reales hasta DRG-01.

---

# Parte IX — Calidad, métricas y definición de terminado

## 54. Requisitos no funcionales y pruebas

### 54.1 Objetivos maduros

| Área | Objetivo |
|---|---|
| Web/API | 99,9% mensual; conectores aparte |
| API lectura p95 | <400 ms consultas normales |
| Dashboard warm p95 | <2 s |
| Preview estructurado | <8 s perfil soportado |
| 100k filas | <3 min asíncrono |
| 1M filas | <15 min asíncrono según perfil |
| Job visible | actualización de progreso ≤5 s; estado durable |
| App crash-free | ≥99,5% sesiones piloto; objetivo ≥99,9% maduro |
| Linaje | 100% campos publicados/decisiones |
| Auditoría | 100% acciones privilegiadas/exportaciones |
| Accesibilidad | WCAG 2.2 AA, owner y gate por release |
| Localización | es-CO inicial; locale explícito |

Jobs asíncronos tienen SLO propio de inicio, progreso, finalización y notificación. Modo degradado es una experiencia diseñada, no solo una tabla de ingeniería.

### 54.2 Pruebas de datos/dominio

- Golden files por parser/template/version.
- Fuzzing, maliciosos, encodings, locales y fórmulas.
- Idempotencia y source overlap.
- Completeness y control totals.
- Drift estructural/estadístico/semántico.
- Linaje campo a campo.
- Property tests monetarios.
- 1:1, 1:N, N:1, parciales, netos, reversos y duplicados legítimos idénticos.
- Balances y reconciliation statements.
- FX, fecha contable, timezone y redondeo.
- Snapshot/reproducción con engine release.

### 54.3 Pruebas de seguridad

- Matriz positiva/negativa por rol/subject/engagement.
- Cross-tenant en API, RLS, cada vista, proyección, objeto, cache, queue, Temporal, search y analytics.
- Cambio/revocación de firma.
- Informes/programaciones/enlaces después de offboarding.
- Email spoofing/forwarding, SFTP y replay webhook.
- SSRF de webhooks salientes.
- PAN/credenciales, polyglots, XXE, ZIP bombs y PDF activo.
- Break-glass y KMS.
- Restore+tombstones.
- SAST/DAST/supply chain y pentest.

### 54.4 Pruebas de IA

- Baseline determinístico.
- Evals por slice/campo.
- Abstención y calibración.
- Prompt injection/exfiltración.
- Redactor fail-closed.
- Shadow/canary/rollback y retiro.
- Cost/latency budgets.
- Defecto escapado y calidad humana.

### 54.5 Accesibilidad y usabilidad

- Navegación completa por teclado y lector de pantalla.
- Contraste/estado no dependiente solo de color.
- Tablas grandes con foco y encabezados semánticos.
- Pruebas con al menos 5 contadores y 5 usuarios PYME por flujo crítico.
- Métricas: éxito, tiempo, error, confianza calibrada y comprensión de ambigüedad.

## 55. Gates de producto

### 55.1 GA inicial

Puede operar comercialmente de forma controlada cuando:

- Firma administra 10–20 empresas reales sin exposición cruzada.
- Fuentes conocidas se importan con <1 min humano.
- Tabular desconocido se mapea en <5 min dentro del perfil.
- Cuatro formatos dominantes y conectores certificados tienen fallback.
- 100% de campos/matches vuelven a evidencia.
- Conciliación de movimientos y saldos funciona.
- Matching puede permanecer en **sugerencia**; no se rebaja el umbral para auto-match.
- Ciclos, recordatorios, SoD, cierre/reapertura son auditables.
- Web/móvil cumplen responsabilidad definida.
- DRG-01, pentest, restore y SLO pasan.
- Pricing/metering/soporte funcionan y margen del piloto está medido.

### 55.2 Producto completo v1

Además:

- Carga sintética/aislamiento con 50 empresas y 10–20 reales operadas.
- Transferencia de empresa entre firmas probada.
- Paquete de portabilidad descargable.
- Facturación electrónica propia.
- Completitud por fuente/cuenta/periodo.
- Balance/statement y diferencia no explicada cero.
- `engine_release` reproducible.
- Auto-match por slice alcanza Wilson LB ≥99,5%, precisión observada ≥99,8%, cobertura elegible ≥70% y cero defectos materiales escapados en validación.
- Móvil muestra evidencia mínima y política de versión/kill switch.
- AI Gateway, evals, fallback y budgets operables.
- 100k filas <3 min y SLO cumplido.
- Margen bruto realizado ≥75% a utilización completa en cohortes estables.
- Dos cohortes de firmas cierran tres periodos con reducción de trabajo ≥50%.

## 56. KPIs

Producto:

- Tiempo archivo→dataset válido.
- Importaciones sin soporte.
- Mapping aceptado/corregido.
- Recetas reutilizadas sin error.
- Completeness verificada.
- Cobertura/precisión/abstención de match.
- Defectos escapados.
- Tiempo/exposición de excepciones.
- Tiempo hasta cierre.
- Empresas por contador.
- Respuesta móvil.

Riesgo/confianza:

- Overrides/reversiones.
- Alertas accionadas/falsos positivos.
- Campos sin linaje: objetivo cero.
- Drift no detectado.
- Accesos/exportaciones anómalos.
- Incidentes cross-tenant: objetivo cero.
- Autocertificaciones sin revisión independiente.

Negocio:

- Activación por empresa.
- Retención/expansión de firmas.
- Conversión piloto→contrato.
- CAC payback y LTV/CAC.
- Valor documentado ≥3× suscripción.
- COGS por 1.000 SRP, página OCR, empresa activa y feed.
- Margen después de descuento/crédito/recaudo/FX.
- Soporte por empresa activa.

## 57. Riesgos principales

| Riesgo | Impacto | Mitigación/trigger |
|---|---:|---|
| Convertirse en ERP | Alto | Scope y wedge; comité de producto |
| PDF/OCR consume roadmap | Alto | Corpus, templates y flujo asistido |
| Falso match o cierre parcial | Crítico | Completitud, balance, abstención, defecto escapado |
| Fuga cross-tenant | Crítico | Empresa estable, RLS, scopes, pruebas y pentest |
| Cambio de contador bloquea cliente | Alto | Engagement revocable y portabilidad |
| Feed inexistente/caro/inestable | Alto | B-01 y archivos permanentes |
| IA/OCR erosiona margen | Alto | Budgets, cuotas y reglas primero |
| Alert fatigue | Medio | Agrupación, presupuesto y feedback |
| Firma no paga | Alto | Diferenciación, pilotos y pricing discovery |
| Soporte se vuelve servicio gestionado | Alto | Clasificar y facturar servicios |
| Retención/borrado incorrectos | Crítico | L-01, delete ledger y restore |
| Costo FX | Alto | Moneda por costo y sensibilidad |
| Sobrediseño | Alto | Umbrales y ADR con TCO |
| Marca rechazada | Medio-alto | Clearance temprano y arquitectura visual desacoplada |

## 58. ADRs iniciales

1. Monolito modular + workers.
2. PostgreSQL, versión, RLS y vistas seguras.
3. Organization/company/engagement.
4. Object storage por zonas, version IDs y WORM.
5. Linaje por campo.
6. Recetas determinísticas/overlays.
7. Outbox, cola y retry ownership.
8. Temporal y verdad de ejecución.
9. AI Gateway y prohibiciones.
10. Web vs móvil.
11. Metering SRP/OCR/empresa.
12. IdP, subject y assurance.
13. RBAC/ABAC/SoD.
14. Completitud y conciliación de saldos.
15. Dedupe cross-source sin unicidad peligrosa.
16. Parquet/warehouse por umbral.
17. No Kafka/Kubernetes inicial.
18. OCR abstraído/fallback.
19. OpenTelemetry y audit log.
20. Región/transmisión/subencargados.
21. RPO/RTO/delete ledger/Object Lock.
22. Routing/celdas y transferencia.
23. Engine release/reproducibilidad.
24. Broker móvil sin side effects; Needle fuera.
25. Propiedad/portabilidad de recetas y reglas.

## 59. Fuentes primarias y evidencia mínima

Arquitectura/seguridad:

- PostgreSQL RLS: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>.
- PostgreSQL `security_invoker`: <https://www.postgresql.org/docs/current/sql-createview.html>.
- S3 Object Lock: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html>.
- OWASP File Upload: <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.
- OWASP ASVS: <https://owasp.org/www-project-application-security-verification-standard/>.
- NIST AI RMF: <https://www.nist.gov/itl/ai-risk-management-framework>.

Colombia:

- Ley 1581: <https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981>.
- Decreto 0368 de 2026: <https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=275576>.
- Circular SIC 001 de 2025: <https://sedeelectronica.sic.gov.co/transparencia/normativa/circular-externa-001-del-18-de-septiembre-de-2025>.
- Concepto Circular SIC 002 de 2025: <https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/alcance-de-la-circular-002-de-2025-sobre-transferencias-internacionales-de-datos>.
- DIAN normativa de facturación: <https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/normatividad/>.

Mercado:

- Alegra precios: <https://www.alegra.com/colombia/precios/>.
- Alegra bancos/conciliación: <https://ayuda.alegra.com/col/crear-conecta-y-concilia-tus-bancos>.
- Wompi tarifas: <https://wompi.com/es/co/planes-tarifas/>.
- Cointab: <https://www.cointab.net/business/reconciliation/faqs/>.
- Synder: <https://synder.com/pricing-accountants/>.

IA edge:

- Needle fine-tuning/español: <https://github.com/cactus-compute/needle/blob/main/doc/finetuning.md>.
- OCR Apple: <https://developer.apple.com/documentation/vision/recognizing-text-in-images>.
- OCR Android: <https://developers.google.com/ml-kit/vision/text-recognition/v2>.

Marca:

- Manual andino de marcas/SIC: <https://sedeelectronica.sic.gov.co/sites/default/files/otros/MANUAL_DE_MARCAS_COMPLETO_2_7e1411cef1.pdf>.
- Consulta de signos SIC: <https://serviciospub.sic.gov.co/Sic/PropiedadIndustrial/SignosDistintivos/Reportes/ConsultaSignos.php>.

## 60. Control de versiones

| Versión | Fecha | Cambio | Estado |
|---|---|---|---|
| 1.0-rc1 | 2026-08-21 | Plan congelado para revisión externa | Histórico |
| Revisión Claude | 2026-08-21 | Dictamen, evidencia y patches | Histórico/input |
| **1.0-unificada** | **2026-08-21** | Integra revisión, corrige patches peligrosos, decide Fincilia y habilita inicio | **Autoritativa** |

---

> **Decisión de inicio:** comenzar Fase −1/Fase 0 y el trabajo sintético de fundamentos. No recibir datos reales fuera de DRG-00, no ejecutar piloto real antes de DRG-01 y no publicar precios antes de C-01.
