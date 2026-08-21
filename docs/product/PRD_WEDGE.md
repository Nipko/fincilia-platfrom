# PRD — wedge de conciliación y cierre con evidencia

| Campo | Valor |
|---|---|
| ID | FNC-PRD-001 |
| Estado | Draft; requiere FNC-GOV-001 y aprobación humana de Product y Accounting |
| Fase | F0 — validación y arquitectura ejecutable |
| Gate relacionado | S1-READY |
| Datos autorizados durante E0 | Exclusivamente sintéticos |
| Comprador prioritario | Firma contable pequeña o mediana con 5–25 empresas activas |
| Entidad servida | PYME; también puede ser compradora directa |
| Wedge | Factura/pedido emitido → pago → fee/retención/ajuste → liquidación → abono bancario → asiento/libro ERP → conciliación de movimientos y saldos → cierre con evidencia |

## 1. Propósito y promesa

Fincilia convierte datos financieros dispersos en cierres comprobables sin exigir el reemplazo del ERP ni del sistema contable. El primer wedge permite a una firma contable explicar, revisar y cerrar el recorrido completo entre una venta emitida y su reconocimiento bancario y contable, conservando el origen de cada cifra.

La promesa para el wedge es:

> Reducir el trabajo manual y el tiempo de cierre al concentrar evidencia, diferencias y decisiones en un flujo reproducible, sin ocultar datos parciales, desconocidos o no verificados.

El producto ayuda a proponer y comprobar; la persona autorizada certifica. Fincilia no mueve dinero, no reemplaza la contabilidad, no declara fraude y no convierte una coincidencia probable en un hecho sin evidencia y control humano.

## 2. Problema

Una venta puede producir varios registros con tiempos, identificadores y montos distintos: factura o pedido, intento de pago, cobro aprobado, comisión, retención, devolución, contracargo, liquidación agrupada, abono bancario y asiento contable. Hoy el equipo contable suele reunir exportaciones y soportes en hojas de cálculo, reconstruir relaciones manualmente, perseguir faltantes y repetir parte del análisis cada cierre.

El problema no es solo “emparejar dos filas”. El cierre debe responder, para cada periodo y fuente:

- qué universo se esperaba y si llegó completo;
- cómo se transforma el valor bruto en valor neto;
- qué movimientos explican cada liquidación y abono;
- qué quedó pendiente, por qué y quién debe resolverlo;
- si los saldos inicial, movimientos y saldo final cuadran;
- qué evidencia y decisión humana sostienen la conclusión;
- si el resultado puede reproducirse después sin alterar originales.

## 3. Segmentos y actores

### 3.1 Comprador prioritario: firma contable

Firma pequeña o mediana que administra de 5 a 25 empresas activas. Compra capacidad operativa, control y evidencia para atender más empresas sin mezclar datos ni depender de conocimiento tácito de una sola persona.

Condiciones que elevan el valor esperado:

- empresas con 500–12.000 movimientos económicos mensuales;
- dos o más canales de cobro;
- al menos una cuenta bancaria y una pasarela, datáfono, marketplace o billetera;
- contabilidad en ERP o Excel;
- 10–20 horas o más de trabajo manual mensual por empresa, o cierres recurrentemente tardíos;
- disposición a operar dos ciclos piloto cuando los gates permitan datos reales.

### 3.2 Entidad servida: PYME

La PYME conserva la frontera estable de sus datos financieros. Una firma accede mediante un engagement revocable. La PYME aporta fuentes, responde solicitudes, revisa excepciones de negocio y recibe un cierre explicable. Puede comprar directamente, pero ese no es el motion prioritario del lanzamiento.

### 3.3 Roles operativos

| Actor | Responsabilidad | Decisiones que conserva |
|---|---|---|
| Socio o administrador de firma | Compra, asigna cartera, controla capacidad y calidad | Autoriza acceso de su equipo dentro del engagement; no adquiere propiedad sobre datos de la PYME |
| Contador operador | Importa fuentes, corrige mapeos, investiga diferencias y prepara el cierre | Acepta o rechaza propuestas según permisos; documenta resolución |
| Revisor/aprobador contable | Revisa excepciones materiales y certifica el cierre | Aprueba, rechaza o solicita reapertura; debe respetar segregación de funciones |
| Administrador/autorizador de PYME | Controla el engagement y el acceso delegado | Otorga o revoca acceso de la firma; confirma responsables y fuentes |
| Colaborador de PYME | Aporta soportes y contexto de negocio | Responde solicitudes asignadas; no certifica por defecto |
| Responsable de fuente | Entrega exportaciones completas y explica cortes | Confirma periodo, cuenta/canal, zona horaria y universo esperado |
| Soporte Fincilia | Ayuda con operación técnica sin decidir semántica financiera | No confirma matches ni cierres y solo accede mediante controles autorizados |

Una misma persona puede ocupar más de un rol en una organización pequeña, pero el sistema debe identificar conflictos de segregación y exigir la política aplicable antes de aprobar un cierre.

## 4. Jobs to be done, dolores y valor

| Actor | Cuando… | Quiero… | Para… | Dolor observable | Indicador de valor |
|---|---|---|---|---|---|
| Socio de firma | distribuyo el cierre de varias empresas | ver estado, bloqueos y carga por empresa | intervenir antes de incumplir | seguimiento por chats y hojas separadas | menos cierres tardíos; más empresas por equipo sin degradar calidad |
| Contador operador | recibo exportaciones heterogéneas | normalizarlas sin perder el original ni el linaje | investigar una vez y reutilizar el aprendizaje controlado | copiar/pegar, fórmulas frágiles y reproceso | horas manuales por cierre; tasa de reutilización de recetas aprobadas |
| Contador operador | una liquidación agrupa ventas y deducciones | explicar bruto, fees, retenciones, ajustes y neto | relacionarla con el abono bancario y el ERP | diferencias sin causa visible | porcentaje de valor explicado y excepciones accionables |
| Revisor contable | recibo un cierre preparado | recorrer cifra, regla, evidencia y decisión | aprobar con confianza y reproducibilidad | revisión basada en archivos dispersos | tiempo de revisión; cobertura de linaje; reaperturas por defecto material |
| Colaborador de PYME | falta un soporte o contexto | responder una solicitud concreta desde móvil | desbloquear el cierre sin aprender todo el sistema | solicitudes ambiguas en canales distintos | tiempo de respuesta y solicitudes resueltas al primer intento |
| Administrador de PYME | cambio de firma o responsable | revocar y delegar acceso sin perder histórico | conservar control y continuidad | dependencia contractual/técnica del contador anterior | tiempo de transferencia y accesos revocados correctamente |

## 5. Resultado de producto

Al terminar un ciclo soportado, la firma debe disponer de:

1. inventario de fuentes esperadas, recibidas, parciales y faltantes;
2. originales inmutables y datos estructurados con linaje por campo publicado;
3. recorrido explicable desde factura/pedido hasta pago, deducciones, liquidación, banco y ERP;
4. conciliación de movimientos y comprobación de saldos;
5. cola de excepciones con razón, impacto, responsable y siguiente acción;
6. registro de propuestas, revisiones y decisiones humanas;
7. snapshot de cierre reproducible y paquete de evidencia exportable;
8. separación verificable entre empresas y engagements.

## 6. Fuentes y cobertura del wedge

### 6.1 Fuentes mínimas del recorrido

| Tramo | Fuente aceptable para el wedge | Información esperada |
|---|---|---|
| Factura emitida | Exportación del ERP, API autorizada del proveedor tecnológico o integración equivalente | ID de factura, fecha, tercero seudónimo/sintético, moneda, subtotal/impuestos/total, estado |
| Pedido, si precede a factura | Exportación o API autorizada del canal de venta | ID de pedido, fecha, total, estado y referencias cruzadas disponibles |
| Pago | Exportación de pasarela, datáfono, marketplace o billetera | ID de transacción, fecha, bruto, estado, medio y referencia |
| Fees, retenciones y ajustes | Detalle de transacción o liquidación de la fuente de pago | concepto, signo, monto, moneda y relación disponible |
| Liquidación | Reporte o exportación del proveedor de pago | ID, periodo/corte, componentes, neto y fecha de pago |
| Banco | Extracto o exportación autorizada | cuenta, periodo, saldo inicial/final, movimientos, fecha y monto |
| ERP/libro | Exportación o API autorizada | asiento/documento, cuenta, fecha, débito/crédito, referencia y periodo |

El buzón DIAN de `AttachedDocument` cubre principalmente documentos recibidos. No se presenta ni se utiliza como fuente suficiente de facturas emitidas o cuentas por cobrar. Para el lado emitido se requiere una fuente de ERP, proveedor tecnológico autorizado o integración equivalente.

Los archivos siguen siendo un canal permanente. El wedge no depende de conexiones continuas ni promete un feed bancario o comercial en tiempo real.

### 6.2 Estados de cobertura

Cada fuente y periodo debe distinguir como mínimo:

- `expected`: se espera según la configuración del cierre;
- `received`: fue recibida y pasó controles de aceptación aplicables;
- `partial`: el rango, secuencia, saldo o universo no está completo;
- `unknown`: no hay suficiente evidencia para determinar cobertura;
- `unverified`: llegó, pero su procedencia o integridad aún no fue verificada;
- `rejected`: no puede procesarse de forma segura o válida;
- `not_applicable`: no corresponde al recorrido de esa empresa y periodo, con justificación.

Los estados `partial`, `unknown` y `unverified` no alimentan auto-match, cierre ni reporte certificado. Deben permanecer visibles y bloquear o condicionar el ciclo según materialidad y política aprobada.

## 7. Flujo feliz end-to-end

| Paso | Resultado esperado | Actor principal | Canal dominante |
|---:|---|---|---|
| 1 | Selecciona empresa autorizada y abre un ciclo con periodo, moneda, fuentes y responsables esperados | Contador operador | Web |
| 2 | Carga exportaciones o recibe datos de una integración autorizada; el sistema conserva originales | Contador operador/responsable de fuente | Web; captura puntual en móvil |
| 3 | Verifica procedencia, periodo, cuenta/canal, duplicados técnicos y completitud antes de usar registros | Contador operador | Web |
| 4 | Revisa estructura y mapeo; corrige campos mediante una receta versionada sin modificar el original | Contador operador | Web |
| 5 | Visualiza candidatos y explicación del recorrido factura/pedido → pago → deducciones → liquidación → banco → ERP | Contador operador | Web |
| 6 | Confirma, rechaza o deja pendiente cada propuesta según evidencia y permisos; el sistema registra autor, razón y versión | Contador operador | Web; decisiones simples en móvil |
| 7 | Resuelve excepciones o asigna solicitudes con evidencia mínima requerida y fecha objetivo | Contador operador | Web |
| 8 | Aporta soporte o respuesta concreta a la solicitud | Colaborador de PYME | Móvil o web |
| 9 | Recalcula de forma determinista el recorrido, la cobertura de movimientos y la ecuación de saldos | Sistema gobernado por reglas | Web muestra el resultado |
| 10 | Revisa materialidad, faltantes, decisiones y paquete de evidencia | Revisor contable | Web |
| 11 | Aprueba el snapshot o devuelve el ciclo con razones; el sistema conserva la versión y auditoría | Revisor autorizado | Web |
| 12 | Consulta el estado y exporta evidencia/resultado permitido | Firma y PYME autorizadas | Web; móvil muestra estado resumido |

El cálculo monetario usa decimal exacto y reglas deterministas. La fecha, el monto, la dirección o una referencia generan candidatos; no constituyen por sí solos una unicidad dura. Un LLM no calcula dinero, confirma relaciones, autoriza acceso ni ejecuta el cierre.

## 8. Excepciones y comportamiento esperado

| Excepción | Tratamiento de producto | Responsable inicial | Condición de salida |
|---|---|---|---|
| Falta fuente de factura emitida | Marcar cobertura incompleta; explicar que DIAN recibido no sustituye CxC emitida | Contador/responsable ERP | Exportación autorizada recibida o exclusión justificada y aprobada |
| Archivo cifrado, corrupto o tipo no admitido | Rechazar de forma segura, conservar metadatos permitidos y solicitar alternativa | Responsable de fuente | Archivo aceptable y autorizado |
| Periodo o cuenta incorrectos | No mezclar con el ciclo; solicitar corrección | Contador operador | Fuente correcta verificada |
| Fuente parcial o secuencia con huecos | Marcar `partial`; excluir de certificación y mostrar impacto | Responsable de fuente | Completitud demostrada o tratamiento formal aprobado |
| Procedencia no verificable | Marcar `unverified`; impedir uso certificado | Contador/administrador | Procedencia verificada |
| Reingesta del mismo archivo/evento | Detectar idempotencia técnica sin borrar evidencia ni asumir duplicidad económica | Sistema + contador si hay ambigüedad | Ejecución única o excepción documentada |
| Filas parecidas o duplicado económico posible | Presentar candidato con razones; nunca imponer unicidad por fecha/monto/referencia | Contador operador | Decisión humana y evidencia |
| Pago parcial o múltiples pagos | Mantener relación parcial o N:1 como propuesta explicada | Contador operador | Diferencia explicada o excepción abierta |
| Liquidación agrupa múltiples operaciones | Desglosar bruto, deducciones y neto; permitir 1:N/N:1 como propuesta | Contador operador | Componentes y neto explicados |
| Fee o retención no identificados | Crear excepción de clasificación con impacto monetario | Contador/colaborador PYME | Concepto y tratamiento aprobados |
| Devolución o contracargo tardío | Relacionar con el periodo/origen sin reescribir el cierre anterior; evaluar reapertura | Revisor contable | Ajuste o reapertura autorizados |
| Diferencia de fecha, zona horaria o moneda | Mostrar regla aplicada y mantener la diferencia visible | Contador operador | Regla aprobada o excepción resuelta |
| Abono bancario no hallado | Mantener liquidación pendiente y verificar ventana/cuenta/completitud | Contador/responsable banco | Abono relacionado o excepción aprobada |
| Asiento ERP ausente o distinto | Abrir excepción; Fincilia no contabiliza autónomamente | Contador operador | Exportación actualizada o decisión contable documentada |
| Ecuación de saldos no cuadra | Bloquear aprobación certificada y mostrar fuentes/diferencia | Revisor contable | Saldos y movimientos explicados |
| Evidencia contradictoria | No seleccionar silenciosamente una fuente; elevar a revisión | Revisor contable | Fuente autoritativa y razón documentadas |
| Usuario sin acceso vigente | Denegar server-side y auditar; ignorar `company_id` del cliente | Administrador autorizado | Grant/engagement válido |
| Solicitud no respondida a tiempo | Escalar visualmente y conservar bloqueo/impacto | Responsable asignado | Respuesta suficiente o decisión formal |
| Reapertura después de aprobación | Crear nueva versión; nunca editar el snapshot aprobado | Revisor autorizado | Nuevo cierre aprobado con vínculo al anterior |

## 9. División web y móvil

### 9.1 Web

La web es el entorno de investigación y operación en volumen:

- portafolio multiempresa con estado y bloqueos;
- configuración del ciclo y fuentes esperadas;
- carga masiva, estructura, mapeo y recetas;
- revisión de completitud y procedencia;
- análisis de recorridos y relaciones 1:1, 1:N, N:1 y parciales;
- cola de excepciones, filtros, asignación y materialidad;
- conciliación de movimientos y saldos;
- revisión, aprobación, reapertura y exportación de evidencia;
- administración de engagements y permisos según rol.

### 9.2 Móvil

Móvil es un companion para captura, respuesta y decisiones simples:

- recibir una solicitud asignada y su contexto mínimo;
- capturar o adjuntar evidencia puntual permitida;
- responder, aclarar o devolver una solicitud;
- confirmar o rechazar una propuesta simple cuando el rol y la política lo permitan;
- consultar estado resumido y bloqueos;
- recibir recordatorios operativos autorizados.

Móvil no ofrece mapeo tabular complejo, investigación multifuente, aprobación masiva ni certificación de un cierre complejo. Una decisión que requiera comparar varias fuentes, cambiar reglas o evaluar materialidad se deriva a web.

## 10. Alcance por etapa

### 10.1 F0 — este PRD y validación

- definir actores, flujo, fuentes, excepciones, métricas y prototipos;
- validar proceso y lenguaje sin recibir documentos reales antes de DRG-00;
- contrastar hipótesis con 5 firmas y observar 10 cierres cuando los gates de datos y investigación lo permitan;
- usar exclusivamente ejemplos y fixtures sintéticos durante E0;
- producir decisiones de producto, dominio y arquitectura antes de código funcional.

### 10.2 Capacidad acumulativa objetivo

| Fase | Capacidad objetivo, sujeta a gates y ADR |
|---|---|
| F1 | plataforma, aislamiento, carga/cuarentena, limpieza tabular, completitud, linaje, metering y evidencia |
| F2 | modelo financiero, conciliación gobernada, excepciones, cierre, portafolio y companion móvil |
| F3 | fuentes autorizadas prioritarias, automatización controlada y conectividad según evidencia de corpus |
| F4 | asistencia gobernada con evals y fallback; nunca decisiones financieras autónomas |

Este orden no es una promesa contractual ni habilita datos reales. Cada fase depende de su gate y aprobaciones.

## 11. Exclusiones y anti-promesas

El wedge no incluye ni promete:

- reemplazar ERP, facturación, impuestos, nómina o inventario;
- custodiar fondos, iniciar pagos, ofrecer crédito o almacenar credenciales bancarias/DIAN;
- scraping contrario a términos o basado en custodiar secretos del cliente;
- un feed bancario, de pasarela o ERP universal, continuo o en tiempo real;
- interpretar de forma universal y perfecta cualquier PDF, hoja o exportación;
- auto-match sin revisión, controles y política; durante la fase vigente no se construye como función autorizada;
- contabilización, aprobación de acceso, cierre o borrado autónomos por IA/LLM;
- declarar o acusar fraude; solo mostrar inconsistencias y señales explicables;
- convertir `partial`, `unknown` o `unverified` en resultados certificados;
- garantizar que fecha, monto, dirección o referencia identifican de manera única una operación;
- managed service contable oculto dentro del SaaS;
- precios públicos o definitivos durante la fase vigente.

## 12. Requisitos de confianza y control

Son criterios de producto, aunque su diseño técnico se resuelva en tareas posteriores:

- `Company` es la frontera financiera estable y todo registro financiero tiene `company_id` no nulo.
- La firma opera solo mediante engagement revocable y grants resueltos server-side.
- Ninguna pantalla o API confía en un `company_id` aportado por el cliente para autorizar acceso.
- Originales y snapshots aprobados son inmutables; correcciones producen versiones vinculadas.
- Todo campo publicado y toda decisión financiera trazan hasta evidencia, regla/versión, actor y tiempo.
- El dinero usa decimal exacto; la moneda y el signo son explícitos.
- Completitud precede al matching y al cierre certificado.
- Propuestas y decisiones quedan diferenciadas; rechazos y override requieren razón.
- La aprobación respeta segregación de funciones y materialidad configurada.
- Exportación básica, seguridad, privacidad y segregación no dependen del plan comercial.
- Logs, ejemplos y soporte no deben contener secretos, PII ni información financiera real durante E0.

## 13. Métricas

### 13.1 North star y guardrails

**North star:** porcentaje de cierres elegibles completados a tiempo con evidencia reproducible y sin defecto material escapado.

| Tipo | Métrica | Definición operativa | Dirección/umbral inicial |
|---|---|---|---|
| Resultado | Horas manuales de conciliación por empresa/ciclo | tiempo humano activo desde fuentes disponibles hasta paquete listo para revisión | reducir al menos 50% frente a baseline observado; hipótesis a validar |
| Resultado | Lead time de cierre | tiempo calendario entre disponibilidad acordada de fuentes y aprobación | reducir 30–50%; gate F2 exige al menos 30% en piloto |
| Resultado | Cierres a tiempo | cierres aprobados antes de fecha objetivo / cierres elegibles | aumentar frente a baseline de cada firma |
| Capacidad | Empresas activas por operador | empresas cerradas con calidad por FTE/ciclo | aumentar sin elevar defectos, reaperturas o accesos indebidos |
| Calidad | Cobertura de linaje publicada | campos publicados con origen localizable / campos publicados | 100% |
| Calidad | Valor explicado | valor de movimientos conciliados o excepcionados con razón / valor total elegible | medir por fuente y ciclo; no ocultar faltantes |
| Calidad | Completitud de fuentes | fuentes verificadas completas / fuentes esperadas | 100% para cierre certificado, salvo política/materialidad aprobada |
| Calidad | Defecto material escapado | cierres aprobados con error material detectado después | 0 en gate piloto F2 |
| Flujo | Tiempo de resolución de excepción | mediana y p90 desde creación hasta resolución | disminuir por tipo de excepción |
| Colaboración | Resolución al primer intento | solicitudes resueltas sin aclaración adicional / solicitudes respondidas | aumentar; segmentar por plantilla/tipo |
| Confianza | Tasa de reapertura | cierres reabiertos / cierres aprobados | observar; toda reapertura conserva versión y causa |
| Seguridad | Acceso cross-company indebido | lecturas/escrituras autorizadas incorrectamente entre empresas | 0 |

### 13.2 Instrumentación mínima

Para calcular métricas sin exponer contenido financiero, registrar eventos operativos con identificadores internos, empresa, ciclo, tipo de acción, estado anterior/nuevo, actor autorizado, marca de tiempo y versión de regla/receta. Montos agregados o campos sensibles solo se incluyen cuando sean necesarios, autorizados y protegidos por el modelo de datos aplicable.

Las métricas deben segmentarse por firma, empresa, fuente, tipo de excepción y ciclo, sin mezclar empresas ni usar proyecciones analíticas como fuente de verdad financiera.

## 14. Hipótesis a validar con 5 firmas y 10 cierres

Estas hipótesis permanecen abiertas. Durante E0 se pueden entrevistar procesos sin recibir documentos de clientes. La observación con corpus o evidencia real requiere DRG-00 y los controles aplicables.

| ID | Hipótesis | Evidencia requerida | Criterio provisional de validación |
|---|---|---|---|
| H-PRD-01 | La firma contable es comprador prioritario y la PYME acepta colaborar mediante solicitudes acotadas | entrevistas con decisores y operadores de 5 firmas; mapa de compra/uso | al menos 4/5 firmas reconocen el problema como prioritario y distinguen comprador de empresa servida |
| H-PRD-02 | El recorrido emitido→pago→liquidación→banco→ERP explica un dolor frecuente y costoso | observación de 10 cierres y cronometraje por actividad | aparece materialmente en al menos 7/10 cierres y consume una parte medible del trabajo manual |
| H-PRD-03 | El baseline manual es de al menos 10–20 horas mensuales por empresa en el ICP | diario de tareas o reconstrucción contrastada por operador | al menos 3/5 firmas muestran empresas del ICP dentro o por encima del rango |
| H-PRD-04 | Archivos/exportaciones son un canal viable y permanente; no se necesita feed universal para entregar valor inicial | inventario de fuentes y fallback de 10 cierres | todos los cierres tienen una ruta autorizada de exportación para los tramos prioritarios o se identifica explícitamente el gap que invalida el wedge |
| H-PRD-05 | Las facturas emitidas pueden obtenerse de ERP/proveedor autorizado; DIAN recibido no cubre el lado CxC | inventario de origen de factura en 10 cierres | fuente emitida nominal identificada en al menos 8/10; los faltantes tienen costo/owner cuantificado |
| H-PRD-06 | Fees, retenciones, devoluciones y liquidaciones agrupadas causan diferencias que requieren modelo multilateral | muestra controlada de procesos y tipología de excepciones | al menos 6/10 cierres contienen uno de estos casos y el modelo bilateral resulta insuficiente |
| H-PRD-07 | Completitud y saldos son condiciones de confianza, no funciones opcionales | revisión de criterios de aprobación con operadores/revisores | 5/5 firmas exigen verificar universo o saldos antes de certificar al menos una fuente material |
| H-PRD-08 | Cola de excepciones con responsable y evidencia reduce coordinación fuera del sistema | prueba de prototipo con tareas representativas | al menos 80% de participantes completa asignación y entiende siguiente acción sin asistencia crítica |
| H-PRD-09 | Móvil aporta valor en captura/respuesta, pero web sigue siendo necesario para investigación y aprobación compleja | pruebas de prototipo con contadores y colaboradores PYME | participantes eligen móvil para respuestas simples y web para análisis complejo en al menos 8/10 escenarios definidos |
| H-PRD-10 | El paquete de evidencia y la reproducibilidad justifican adopción más allá de un “panel multiempresa” | entrevistas de valor y ranking de conceptos | al menos 4/5 decisores ubican evidencia/cierre reproducible entre los tres beneficios principales |
| H-PRD-11 | Es posible reducir 50% el trabajo manual y 30–50% el lead time sin elevar defectos | baseline de 10 cierres y prueba posterior sobre dos ciclos por piloto | dirección confirmada en prototipo/ensayo; objetivo cuantitativo se acepta solo con medición piloto F2 |
| H-PRD-12 | La transferencia de engagement preservando histórico es un diferenciador relevante | entrevistas sobre cambio de contador y prueba conceptual | al menos 3/5 firmas o PYMEs reportan riesgo/costo relevante y entienden la propuesta de revocabilidad |

### 14.1 Registro mínimo por cierre observado

Sin copiar contenido financiero a este repositorio, la investigación debe capturar:

- tipo de empresa y canales, en categorías no identificables;
- roles participantes y handoffs;
- fuentes esperadas y método autorizado de obtención;
- tiempo activo y espera por etapa;
- número y tipo de excepciones;
- pasos repetidos y herramientas usadas;
- criterio de completitud y aprobación;
- necesidad de saldos y materialidad;
- puntos donde se pierde evidencia o contexto;
- resultado de las tareas de prototipo.

La plantilla y repositorio de investigación deberán definirse bajo una tarea autorizada y cumplir el gate de datos; este PRD no autoriza recopilar corpus real.

## 15. Criterios de aceptación del wedge

El wedge queda listo para pasar de borrador a aprobación cuando:

- Product y Accounting humanos están asignados mediante FNC-GOV-001;
- comprador firma contable y PYME servida están confirmados o el PRD se corrige con evidencia;
- las fuentes de factura emitida están identificadas sin atribuir esa cobertura al buzón DIAN recibido;
- actores, permisos de decisión y división web/móvil son comprendidos en pruebas de prototipo;
- el flujo feliz y las excepciones cubren movimientos, saldos, completitud y linaje;
- las 12 hipótesis tienen evidencia de 5 firmas y 10 cierres o una decisión explícita de pivotar;
- existe baseline de horas y lead time con definición común;
- no se promete feed universal, parser universal, auto-match, cierre autónomo ni acusación de fraude;
- Architecture confirma que el alcance puede expresarse sin violar tenancy, trazabilidad o fases;
- Accounting revisa semántica de fees, retenciones, liquidación, banco, ERP y cierre;
- los prototipos y tareas posteriores referencian esta versión aprobada.

## 16. Dependencias y decisiones abiertas

| Dependencia/decisión | Estado | Owner requerido | Impacto |
|---|---|---|---|
| FNC-GOV-001 — owners humanos y RACI | Bloqueante para aprobación | Founder | El PRD solo puede permanecer Draft |
| Modelo organization/company/engagement | Pendiente de tarea de dominio | Architecture + Accounting | Define acceso, transferencia y frontera financiera |
| Modelo financiero y semántica de saldos | Pendiente de tarea de dominio | Accounting + Architecture | Precisa candidatos, excepciones y certificación |
| RBAC/ABAC/SoD | Pendiente de tarea de seguridad | Security + Accounting | Precisa quién prepara, revisa, aprueba y reabre |
| Protocolo de investigación y DRG-00 | Pendiente de aprobaciones | Product + Legal + Security | Condiciona observación y corpus real |
| Arquitectura de información/prototipo | Pendiente de UX | Product + UX | Valida comprensión, web/móvil y workflows |
| Materialidad por fuente/empresa | Abierta; no asumir valor universal | Accounting | Determina bloqueos y escalamiento |
| Formatos y conectores prioritarios | Abierta hasta corpus permitido | Product + Data + Architecture | Evita prometer parser/feed universal |

## 17. Riesgos de producto y mitigación

| Riesgo | Señal temprana | Mitigación de producto |
|---|---|---|
| El wedge intenta cubrir demasiadas fuentes | cada firma requiere un flujo irrepetible | priorizar formatos dominantes demostrados y conservar carga manual autorizada como fallback |
| Se confunde candidato con match confirmado | usuarios aceptan propuestas sin revisar evidencia | separar estados, razones, materialidad y actor que decide |
| Un dashboard oculta incompletitud | indicadores “verdes” con fuentes parciales | mostrar cobertura antes de avance y bloquear certificación aplicable |
| La firma se percibe dueña del dato | dificultad al revocar o cambiar contador | hacer visible company/engagement y probar transferencia |
| Colaboración crea ruido | solicitudes vagas o duplicadas | plantillas por excepción, evidencia requerida, owner y fecha objetivo |
| Móvil intenta replicar toda la web | errores en decisiones complejas | restringir a captura, respuesta, estado y casos simples |
| Métricas premian velocidad sobre exactitud | cierre rápido con reaperturas/defectos | combinar lead time con linaje, completitud y defecto material |
| Se promete IA como decisión | pérdida de confianza o riesgo financiero | lenguaje explícito: IA propone; reglas validan; personas certifican |

## 18. Ejemplo sintético de referencia

La empresa ficticia `Comercio Sintético Andino S.A.S.` emite la factura `FAC-SYN-1042` por COP 119.000 desde un ERP de prueba. Una pasarela sintética registra un pago bruto de COP 119.000, descuenta un fee de COP 3.570 y una retención de COP 1.190, y agrupa el neto de COP 114.240 con otras operaciones en la liquidación `LIQ-SYN-77`. El banco sintético muestra el abono agrupado y el ERP sintético contiene el asiento del periodo.

Fincilia debe conservar cada origen, explicar la aritmética con decimal exacto, proponer relaciones con razones, exigir revisión humana y comprobar movimientos y saldos. Si falta el detalle de la liquidación o el extracto está parcial, el recorrido no puede presentarse como cierre certificado.

Este ejemplo es completamente ficticio y no define reglas contables universales ni tasas reales.
