# Revisión externa independiente — `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` 1.0-rc1

**Revisor:** Claude (Opus 5), en los roles de arquitecto principal, responsable de seguridad, líder de producto financiero y crítico comercial independiente.
**Fecha de la revisión:** 21 de agosto de 2026.
**Encargo:** `PROMPT_REVISION_CLAUDE.md`, SHA-256 `d846487f91d8355bbd6a22406cc806ddcd58d8c2eff8c9bc3b79f897d6bdf107` (coincide con el manifiesto).

---

## 0. Registro de recepción del artefacto revisado

| Campo | Valor |
|---|---|
| Archivo | `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` |
| Versión interna | 1.0-rc1 — candidata congelada para revisión externa |
| Fecha del documento | 21 de agosto de 2026 |
| Fecha de corte de investigación declarada | 21 de agosto de 2026 |
| SHA-256 recibido | `ee283d1e951d6739005a92b8bbb3ce05b41a128ba2fab8a9b698bf9a74b53fc8` |
| SHA-256 del manifiesto | `EE283D1E951D6739005A92B8BBB3CE05B41A128BA2FAB8A9B698BF9A74B53FC8` |
| Resultado | **COINCIDE.** Esta revisión sí es de 1.0-rc1. |
| Extensión | 2.186 líneas, 111.565 bytes |

**Validaciones mecánicas del manifiesto, reverificadas por el revisor:** 2.186 líneas ✅ · 22 fences de código, balanceados ✅ · secciones `## 0.` a `## 50.` todas presentes ✅ · 10 partes `# Parte I–X` ✅ · sin redacción heredada de anualidad a diez meses (la única aparición, L1818, es el rechazo explícito del escenario) ✅ · sin `1/3/10` ✅ · sin alertas `80/100` (L570 y L1721 dicen 70/90/100) ✅.

**Alcance y método.** Leí las 2.186 líneas completas antes de emitir veredicto. Después ejecuté una revisión distribuida: cuatro verificadores contra fuentes primarias en la web, cinco revisores por área (arquitectura/datos, seguridad/privacidad, IA, producto/UX/operación, pricing/programa), dos equipos de ataque conceptual y once refutadores adversariales que intentaron derribar cada hallazgo Bloqueador o Mayor. De 177 hallazgos brutos, **23 fueron descartados como falsos positivos** por el pase de refutación (§3.4 registra los principales, porque saber qué NO es un problema también tiene valor). Toda la aritmética de §8 la recalculé yo mismo.

**Limitaciones que el lector debe conocer.** Doce afirmaciones quedaron `NO VERIFICABLE` y están marcadas como tales en §2 — no las convierto en hallazgos. En particular no logré verificar en fuente primaria: (a) que algún banco colombiano del ICP exporte OFX, MT940 o camt.053; (b) tarifas de PayU, Mercado Pago y ePayco Colombia; (c) precios de agregadores bancarios con cobertura colombiana; (d) latencia real Bogotá→sa-east-1. Ninguna decisión de esta revisión depende de una cifra que no pude ver.

---

## 1. Veredicto ejecutivo

### 1.1 Tres veredictos de gate independientes, coherentes con DRG-01

| Gate | Veredicto | Síntesis |
|---|---|---|
| **CONSTRUCCIÓN SIGNIFICATIVA** | **SÍ CON CONDICIONES** | La arquitectura objetivo es correcta y no requiere rediseño. Faltan ocho decisiones de modelo y de límites que, si se toman después de escribir código, obligan a reproceso. |
| **PILOTO CON DATOS REALES** | **NO** | DRG-01 es circular y no puede aprobarse tal como está escrito. Además hay siete controles de seguridad y privacidad ausentes, no meramente incompletos, en rutas por las que sí van a pasar datos reales. |
| **GA / VENTA GENERAL** | **NO** | La hipótesis de precio está contradicha por precios de competidores verificados hoy en fuente primaria, el ICP declarado no cabe en los planes propuestos y dos precios publicados violan el piso de margen del propio plan. |

### 1.2 Veredicto global

> ## APROBABLE CON CAMBIOS MAYORES

No es «no aprobable». Este es un plan de calidad inusual: la disciplina de evidencia, el gobierno de IA y la política de retención están por encima de lo que se ve en productos ya vendidos. Los cambios son quirúrgicos y se concentran en tres zonas: la **Parte VII completa** (empaquetado comercial), **§27.1** (IA en dispositivo) y un **conjunto acotado de controles** de seguridad, borrado y completitud. La Parte III (arquitectura) y la Parte V (gobierno de IA) sobreviven casi intactas.

### 1.3 Cinco razones concretas

1. **El canal de correo acepta datos financieros de cualquier remitente.** `SPF`, `DKIM`, `DMARC`, «remitente» y «allowlist de remitentes» aparecen **cero veces** en 2.186 líneas, mientras el buzón dedicado se lista cinco veces como fuente de ingesta (§6.3 L275, §13.1 L888, §13.3 L914, Fase 3 L1907) y es el canal DIAN. Quien conozca la dirección inyecta documentos en una empresa, contamina un cierre y genera `source_record_published` facturables. Es el único punto del plan donde un desconocido escribe en el plano financiero.

2. **El borrado no sobrevive a un restore, y el plan cree que sí.** §20 L1174 afirma que «un tombstone impide que un restore reviva información eliminada». El documento nunca dice dónde vive ese tombstone y el lugar natural —la misma base PostgreSQL que se restaura— lo invalida por construcción. Con backups de 35 días (§20) y un derecho de supresión ejercido dentro de esa ventana, un restore legítimo resucita el dato y nada lo detecta. Ningún criterio de éxito de restore (§22 L1261, §30.5) exige reconciliar contra supresiones.

3. **La aritmética comercial no cierra con sus propias reglas.** Recalculé las tres tablas de §37.2: las cifras publicadas son exactas. Pero al 100% de utilización del plan —no al 65% supuesto— el margen anual cae a **72,7% / 74,2% / 73,3%**, por debajo del ≥75% que §34 exige para poder publicar la anualidad. La empresa adicional de Firma a $69.000 rinde **67,1%**, bajo el piso duro de 70% de §37.2. Y el crédito del 100% del piloto (§37.1) deja el margen del año 1 de Esencial en **65,0%**. Tres reglas del propio documento se incumplen con los números del propio documento.

4. **El precio ancla del comprador está a un orden de magnitud del plan Firma, y el plan no lo sabe.** Siigo publica hoy «Siigo contador — GRATIS — 1 Empresa» y «Siigo contador ilimitado — $44.658/mes — $535.900/año — **Empresas ilimitadas**». Alegra publica que el Espacio Contador es gratuito: «tú accedes a sus cuentas sin costo adicional». Firma pide $899.000/mes por diez empresas. Además, **Simetrik** —colombiana, Bogotá, Serie B de US$55M liderada por Goldman Sachs AM más B1 de US$30M, y la marca de «conciliación» en el país— no aparece en ninguna de las 2.186 líneas.

5. **Falta el artefacto que en Colombia se llama «conciliación bancaria».** §6.7 modela `obligation`, `money_movement`, `settlement` y `match_group`, pero no existe ninguna entidad de saldo ni la ecuación *saldo según extracto ± partidas conciliatorias = saldo según libros*. El saldo aparece tres veces, todas marginales: como interacción de importación (L343), como tipo semántico (L380) y como señal de anomalía (L497). Se puede conciliar el 100% de los movimientos y estar equivocado, porque nada obliga a que los saldos cuadren ni a que la ingesta esté completa (§13.2 no tiene cláusula de completitud).

---

## 2. Matriz de evidencia

Todas las consultas son del **2026-08-21**. `HECHO` = verificado en fuente primaria. Se omiten por brevedad 100 filas adicionales de resultado `CONFIRMADO` sin impacto correctivo.

### 2.1 Regulación y privacidad — Colombia

| Afirmación del plan | Tipo | Fuente primaria | Resultado | Impacto |
|---|---|---|---|---|
| §14.2 L1006 «Decreto 0368 de 2026 y desarrollo progresivo de finanzas abiertas» | hecho | funcionpublica.gov.co/eva/gestornormativo `?i=275576`; comunicado SFC 09-abr-2026 | **CONFIRMADO** | Existe: Decreto 0368 del **7 de abril de 2026** (MinHacienda), sustituye el Título 8 del Libro 35 Parte 2 del Decreto 2555 de 2010 y establece el Sistema de Finanzas Abiertas **obligatorio**, reemplazando el esquema voluntario del Decreto 1297 de 2022. El plan acierta al citarlo. |
| §14.2 lo caracteriza sólo como «desarrollo progresivo», sin decir a quién obliga | inferencia | Decreto 0368/2026 | **CONFIRMADO PARCIAL** | La obligatoriedad recae **únicamente** sobre entidades vigiladas por la SFC. Esta plataforma sería «Tercero Receptor de Datos **No Vigilado**»: accede sólo por esquemas voluntarios, sin inscripción obligatoria ni verificación previa. Cambia la lectura estratégica: finanzas abiertas **no** es una vía de acceso automática, es una negociación bilateral. |
| §14.2 L1004 «Ley 1266 de 2008 cuando el flujo realmente encaje» | decisión | Ley 1266/2008 art. 3 | **CONFIRMADO** | La cautela es correcta, pero por una razón que el plan no registra: la 1266 define titular como «persona natural **o jurídica**», mientras la 1581 sólo cubre naturales. Consecuencia falsable: si la plataforma alguna vez alimenta o consulta un operador de información, o genera un score, entra en 1266. |
| §14.2 L1005 Circular SIC 002 de 2024 sobre IA | hecho | sic.gov.co, expedida 21-ago-2024 | **CONFIRMADO** | Fecha y URL correctas. El PDF oficial es un escaneo sin capa de texto — no citable por búsqueda. |
| §14.2 resume la Circular 002/2024 como «privacidad desde el diseño» | inferencia | Circular SIC 002/2024 | **CONFIRMADO PARCIAL** | El resumen omite cuatro exigencias con consecuencia de diseño: ponderación previa documentada de idoneidad, necesidad, razonabilidad y proporcionalidad **antes** de usar IA; principio de precaución; estudio de impacto de privacidad obligatorio; explicabilidad. §23.1 sólo exige DPIA en AI-3. |
| §14.2 (omisión) circulares SIC posteriores | hecho | Circular Externa SIC **001 de 2025** (18-sep-2025, D.O. 53.248) y **002 de 2025** | **DESACTUALIZADO** | Faltan dos. La 001/2025 exige explicación clara y comprensible de toda decisión automatizada desfavorable a vigilados por la SIC en servicios financieros/fintech. La 002/2025 regula la transferencia de **datasets** y de **tecnología** que trate datos personales — alcanza directamente a §27 (fine-tuning, corpus gold) y §21.1 (proveedores de OCR/IA). |
| §22 L1238 «quince días hábiles» para reportar a la SIC | hecho | Concepto SIC rad. 21-17773, 20-abr-2021 | **CONFIRMADO** | 15 días hábiles, contados **desde que el incidente se detecta y se pone en conocimiento del área encargada** — no desde la confirmación. La tripleta `detected_at`/`aware_at`/`confirmed_at` de §22 es mejor que la práctica habitual; sólo falta designar cuál marca dispara el reloj legal. |
| §14.1 «RNBD aplicable» | decisión | Decreto 090 de 2018 | **CONFIRMADO PARCIAL** | Una startup pequeña **no** está obligada: el universo se redujo a entidades con activos > 100.000 UVT y personas jurídicas públicas. Evita trabajo innecesario en Fase 0. |
| §20 L1153 «transferencia/transmisión internacional» usados como sinónimos | decisión | Ley 1581 art. 25–26; Decreto 1074/2015 | **CONFIRMADO PARCIAL** | Son figuras distintas. El caso de la plataforma es **transmisión** (a un encargado en el exterior): no requiere consentimiento del titular si existe contrato de transmisión con las cláusulas exigidas. La **transferencia** sí exige nivel adecuado o autorización expresa. El plan asume la carga más pesada innecesariamente en un caso y la más ligera en el otro. |
| §20 retención expresada por clase y duración, sin evento de inicio | hecho | Ley 962/2005 art. 28 | **CONFIRMADO PARCIAL** | El reloj se ancla «a la fecha del último asiento, documento o comprobante», no a la fecha de carga. Si el lifecycle del object store cuenta desde `created_at`, se borra antes de tiempo el soporte de un periodo reabierto o de una carga tardía. |
| §6.14 / §32 (omisión): facturación electrónica propia | hecho | Resolución DIAN 000165 de 2023, arts. 7–8 | **DESMENTIDO por omisión** | La plataforma **debe** emitir factura electrónica por sus propias suscripciones. No aparece en §6.14 ni en la lista «Comprar» de §32. |
| §23 funda el gobierno de IA en NIST AI RMF | decisión | CONPES 4144, 14-feb-2025 | **CONFIRMADO** | No existe hoy ley vinculante de IA en Colombia; el CONPES 4144 es política pública, no norma. El marco elegido (Circular SIC 002/2024 vinculante + NIST AI RMF como estándar) es **correcto y suficiente**. |

### 2.2 Licencias, benchmarks y viabilidad de Needle 2 / Cactus

| Afirmación del plan | Tipo | Fuente primaria | Resultado | Impacto |
|---|---|---|---|---|
| §27.1 L1404 Needle 2, 45M parámetros, binario 14 MB, ~28 MB RAM, ventana 256 tokens | hecho | github.com/cactus-compute/needle README; huggingface.co/Cactus-Compute/needle2; PyPI `cactus-needle` 2.0.8 (2026-08-20) | **CONFIRMADO** | Las cifras coinciden literalmente. Omisión: las herramientas quedan **fijadas como KV sinks** y no rotan, así que 256 no es presupuesto libre. |
| §27.1 L1404 la ventana de 256 tokens, sin cualificar idioma | hecho | `doc/finetuning.md` | **DESMENTIDO** | Texto literal: *«Non English text fragments into roughly 1.7 times more tokens (measured on Spanish), which taxes both quality and the 256 token window.»* En español el presupuesto real es de ~150 tokens equivalentes, menos las herramientas. |
| §27.1 L1408/L1504 restringen el problema de `confidence` al modelo **ajustado** | hecho | `doc/finetuning.md` | **DESMENTIDO** | **Hallazgo crítico.** La misma doc advierte del modelo **base**: *«Non English deployments of the base model should also treat the score with caution (correct Spanish calls have been measured at confidence 0.0).»* El producto es en español colombiano y toda la arquitectura edge descansa en un umbral de confianza. |
| §27.1 L1406 «no existe validación independiente» | hecho | github.com/cactus-compute/needle/issues/61 | **DESMENTIDO** | Sí existe: issue #61, abierto el 2026-08-13, evaluación en 4 fases **realizada en español**. Concluye que el fine-tuning mejoró la recuperación de herramienta pero no proporcionalmente los argumentos. Es evidencia gratuita y directamente aplicable al POC. |
| §27.1 L1406 «42,6% global en BFCL v4» | hecho | cactuscompute.com/needle; gorilla.cs.berkeley.edu/leaderboard | **CONFIRMADO PARCIAL** | 42,6 corresponde al subconjunto **single-turn** (3.641 filas), no a BFCL v4 completo, que aporta justamente la evaluación agéntica. Ningún modelo Needle/Cactus figura en el leaderboard oficial. |
| §27.1 L1406 «63,7% exact-match en Mobile Actions» | hecho | cactuscompute.com/needle; dataset google/mobile-actions | **CONFIRMADO** | Cifra exacta (961 filas). Mobile Actions mide acciones del SO Android **en inglés**; su transferencia al dominio contable colombiano es una hipótesis sin evidencia. |
| §27.1 L1410 «Needle y sus pesos declaran Apache-2.0; Cactus Engine tiene licencia distinta» | hecho | LICENSE de ambos repos | **CONFIRMADO** | La distinción del plan es correcta y bien hecha. Mantener. |
| §27.1 asume que Needle es integrable en el stack React Native de §8.1 | hecho | api.github.com/repos/cactus-compute/cactus-react-native | **DESMENTIDO** | El repo oficial `cactus-react-native` está **ARCHIVADO** (`archived=true`, último push 2026-04-19). El único camino React Native oficial está sin mantenimiento. |
| §27.1 L1453 prohíbe «Cactus Cloud» | hecho | cactuscompute.com | **NO VERIFICABLE** | No existe producto con ese nombre. Hoy son tres: Cactus Hybrid (MIT), Cactus Needle y Cactus Engine. La prohibición apunta a un nombre inexistente. |
| §27.1 L1462 ExecuTorch como «alternativa condicionada» | hecho | github.com/pytorch/executorch releases | **DESACTUALIZADO** | v1.4.1 estable (2026-08-14). Ya no es apuesta temprana. |

### 2.3 Competidores y precios

| Afirmación del plan | Tipo | Fuente primaria | Resultado | Impacto |
|---|---|---|---|---|
| §36 L1751 Alegra COP $74.900–$319.900/mes | hecho | alegra.com/colombia/precios | **CONFIRMADO PARCIAL** | Correcto como lista mensual. La misma página publica pago anual con 25% OFF → **$56.175–$239.925/mes equivalente**, que es el precio con el que compite de verdad. |
| §36 (omisión) entitlement de feeds bancarios de Alegra | hecho | alegra.com/colombia/precios, tabla «Compara nuestros planes» | **HALLAZGO NUEVO** | Fila «Conexión con bancos y conciliaciones»: **– / 1 / 3 / 5**. Alegra **Pro** entrega **3 conexiones bancarias por $250.900/mes de lista**. §34 entrega **2 feeds en Control por $349.000**. El plan está por debajo en la métrica más cara y más visible. |
| §2 L126 «Alegra publica panel multiempresa… para contadores» | hecho | alegra.com/colombia/contadores | **CONFIRMADO y agravado** | El Espacio Contador es **gratuito**: *«Tus clientes solo pagan por el plan de Alegra Contabilidad que necesiten, y tú accedes a sus cuentas sin costo adicional.»* §34.3 cobra $899.000/mes por la misma promesa de portafolio. |
| §36 (omisión) precio de Siigo, el competidor local más grande | hecho | siigo.com/precios-siigo | **DESMENTIDO por omisión** | **El hallazgo más grave del bloque competitivo.** La misma página publica «Siigo contador — GRATIS — 1 Empresa» y «Siigo contador ilimitado — **$44.658/mes · $535.900/año · Empresas ilimitadas**». El ancla mental del contador colombiano para «portafolio multiempresa» es ~$536k/**año**; Firma pide $10,8M/año. |
| §36 (omisión) Alegra segmenta por ingresos del cliente | hecho | alegra.com/colombia/precios | **HALLAZGO NUEVO** | Tiers por «Ingresos hasta $10M / $40M / $180M / $500M mensuales». Es una métrica de valor radicalmente distinta a `source_record_published` y explica por qué el mercado no está educado en «registros publicados». |
| §36 L1752 Cointab USD $149–$749/mes | hecho | cointab.net/business/reconciliation/faqs | **CONFIRMADO** | Exacto. Detalle útil: Starter $149 (5 fuentes / 50k filas), Growth $249 (10 / 100k), Professional $499 (15 / 250k), Enterprise $749 (20 / 500k); todos con reconciliation runs ilimitados. |
| §36 L1753 Synder USD $65–$599/mes «por transacciones/conexiones» | hecho | synder.com/pricing-accountants | **CONFIRMADO PARCIAL** | Cifras correctas en mensual. La unidad real es *synced sales transactions/month* (500/3.000/20.000/40.000); los integration slots sólo separan Basic. Con pago anual el rango baja. |
| Encargo pto. 5 — Dext | hecho | dext.com pricing (Rest of the World) | **NO CITADO POR EL PLAN** | «Practice Essentials from **$17.70 per client/month**», «Practice Advanced from $19.20», ambos con mínimo de 10 clientes; add-ons a $7,5/cliente. Es el **competidor estructural directo** del modelo Firma y no aparece en el plan. |
| Encargo pto. 6 — Odoo | hecho | odoo.com/pricing | **NO CITADO POR EL PLAN** | Standard $7,90/usuario/mes, Custom $10,90. **Multi-Company y External API sólo existen en Custom.** Cualquier escenario de firma o de write-back por API obliga al cliente a Custom — dato que cambia la conversación de integración. |
| Encargo pto. 6 — conciliación de Odoo en Colombia | hecho | odoo documentation, bank synchronization | **CONFIRMADO** | Proveedores listados: Plaid (EE.UU./Canadá), Yodlee (Europa), Salt Edge, Ponto, Enable Banking, Basiq. **Colombia y LatAm no aparecen.** |
| Encargo pto. 7 — Simetrik | hecho | prensa de financiación, sitio corporativo | **AUSENTE DEL PLAN** | Colombiana (Bogotá, 2019). Serie B US$55M liderada por Goldman Sachs Asset Management (feb-2024) + B1 US$30M. Es *la* marca de conciliación en el país y no se menciona en 2.186 líneas. |
| §36 compara COP contra USD | hecho | el propio §36 L1751-1755 | **DESMENTIDO (defecto metodológico)** | El documento no contiene «TRM», «tasa de cambio» ni supuesto de conversión. Cointab a USD 149 y Alegra a COP 74.900 no son comparables en la página. |

### 2.4 Conectividad bancaria y recaudo

| Afirmación del plan | Tipo | Fuente primaria | Resultado | Impacto |
|---|---|---|---|---|
| §13.1 L892 / §32 L1629 asumen un agregador bancario contratable con cobertura colombiana | hipótesis | developers.belvo.com — «Available Institutions» | **DESMENTIDO** | La página oficial lista **únicamente** instituciones de 🇧🇷 Brasil y 🇲🇽 México. Cero coincidencias para «Colombia», «Bancolombia», «Davivienda», «Nequi», «Daviplata». Contradice el material de marketing de Belvo. No afirmo que Belvo haya salido de Colombia; afirmo que **la cobertura no está documentada** y que Fase 3 depende de ello. |
| §37.2 L1803 «Feeds usados en promedio 8 / 16 / 48 mil COP/mes» | hipótesis | — | **NO VERIFICABLE** | Ningún proveedor con cobertura colombiana publica precio por cuenta/mes. Belvo sólo publica piso de USD 1.000/mes; Finerio Connect no publica precios; Fintoc no cubre Colombia. La línea de COGS **más grande de Firma** (48 de 201 = 24%) carece de fuente. |
| §34 L1655 «la anualidad sólo se publica si el costo de recaudo anual es ≤1%» | hipótesis | wompi.com/es/co/planes-tarifas | **DESMENTIDO para tarjeta** | Tarifa pública Wompi (Bancolombia): Plan Avanzado **2,65% + $700 + IVA**. Aplicado a la anualidad de Esencial ($1.419.000) da ~**3,2%**. El gate ≤1% sólo es alcanzable por PSE/transferencia con tarifa fija — el plan no lo dice y no restringe el medio de pago. |
| §37.2 (omisión) retenciones sobre recaudo | hecho | epayco.com/tarifas, letra pequeña | **HALLAZGO NUEVO** | «Retención de IVA 15% sobre el IVA de la venta. Renta del 1,5% sobre el valor base. Rete ICA del 0,2%», más costo de retiro de fondos. Son efectos de caja y de costo que §37.2 no modela. |
| §6.4 L313-320 familias prioritarias: OFX 2.x, MT940, camt.053 | hipótesis | bancolombia.com centro de ayuda | **NO VERIFICABLE — riesgo alto** | Lo **único** confirmado en fuente primaria del propio banco es que Bancolombia ofrece descarga de extractos en **PDF y XLS**. No pude confirmar que ningún banco colombiano del ICP exporte OFX, MT940 o camt.053 a clientes PYME. §44.4 convierte OFX en criterio de producto completo. |
| §6.4 (omisión) PDF de extracto protegido por contraseña | inferencia | — | **NO VERIFICABLE** | Fuentes secundarias coinciden en que Bancolombia entrega extractos como PDF cifrado con la cédula del titular. No lo afirmo. Si es cierto, el plan no tiene ningún control: pedir la contraseña al usuario colisiona con §14 «Prohibido: credenciales». Se resuelve con **un archivo real en Fase 0**. |
| §6.4 L316 «OFX 2.x» como estándar vivo | hecho | Financial Data Exchange (FDX) | **CONFIRMADO** | FDX absorbió el consorcio OFX en 2019; vigentes OFX Banking 2.3 y OFX Tax Extension 2026.0. El estándar está vivo — el problema es la adopción bancaria local, no el formato. |

### 2.5 Stack, versiones y controles técnicos

| Afirmación del plan | Tipo | Fuente primaria | Resultado | Impacto |
|---|---|---|---|---|
| §13.5 L950 «matriz de región con latencia desde Colombia» | decisión | docs.aws.amazon.com global-infrastructure regions | **CONFIRMADO PARCIAL** | Hecho que el plan nunca declara: **no existe región AWS en Colombia ni anuncio de una**. Únicas LatAm: `sa-east-1` (São Paulo, por defecto) y `mx-central-1` (México, **opt-in requerido**). Chile anunciada, no lanzada. La transmisión internacional no es una opción de diseño: es obligatoria. |
| §10.2 L735 «Object Lock impide sobrescritura o eliminación» | hecho | docs.aws.amazon.com object-lock-overview | **CONFIRMADO PARCIAL** | Omite el matiz que rompe el plano de evidencia: *«Retention periods and legal holds don't prevent new versions of the object from being created, or delete markers to be added on top of the object.»* Object Lock protege **la versión, no la clave**. |
| §20 L1174 legal hold como control fuerte | hecho | misma doc | **CONFIRMADO PARCIAL** | *«Legal holds can be freely placed and removed by any user who has the `s3:PutObjectLegalHold` permission.»* No protege contra un insider privilegiado. |
| §10.2 L736 modo compliance sólo si una obligación impide el borrado administrativo | decisión | misma doc | **CONFIRMADO — decisión sólida** | *«In compliance mode, a protected object version can't be overwritten or deleted by any user, including the root user.»* La cautela del plan es exactamente la correcta. **Conservar.** |
| §10.3 L748 RLS con `FORCE ROW LEVEL SECURITY`, app no owner ni `BYPASSRLS` | hecho | postgresql.org ddl-rowsecurity | **CONFIRMADO — control suficiente en su eje** | Cita literal correcta. No requiere cambio. |
| §10.3 L753 «réplica de lectura para informes» + §16 L1092 vista consolidada de firma | hecho | postgresql.org CREATE VIEW / rules | **VACÍO CRÍTICO VERIFICADO** | *«permission checks and policies for the tables which are referenced by a view will use the **view owner's rights**… except if the view is defined using the `security_invoker` option.»* Una vista de informes creada por un rol privilegiado **elude RLS** para todos sus consumidores. Es exactamente donde el plan pone los informes. |
| §16 L1084 RLS como capa 2 | hecho | postgresql.org CREATE POLICY | **CONFIRMADO PARCIAL** | Las políticas se aplican antes de las cualificaciones del usuario **salvo** para funciones y operadores marcados `LEAKPROOF`. Canal lateral conocido, no mencionado en §30.3. |
| §10.3 L745 «una instancia PostgreSQL administrada por celda» sin versión mínima | hecho | CVE-2025-8713 (2025-08-14) | **HALLAZGO NUEVO** | *«PostgreSQL optimizer statistics allow a user to read sampled data within a view that the user cannot access… that a row security policy intended to hide.»* El plan no fija en ningún punto (§10.3, §31, ADR-002) una versión mínima ni una política de parcheo para la capa que sostiene el aislamiento. |
| §10.1 L714 pgvector; §10.7 L809 «embeddings nunca son evidencia» | hecho | github.com/pgvector/pgvector | **CONFIRMADO — control suficiente** | *«With approximate indexes, filtering is applied after the index is scanned.»* Bajo RLS el filtro actúa como post-filtro **antes de devolver filas al cliente**: se degrada el recall, **no se filtra contenido**. Busqué issues de fuga cross-tenant y no encontré ninguna. El riesgo real es de diseño (índice global), no de mecanismo. |
| §11.1 L840 / §13.5 L944 Temporal antes de Fase 2 | decisión | temporal.io/pricing y docs | **CONFIRMADO — decisión razonable** | Precios públicos: Essentials desde **USD 100/mes**, Business desde **USD 500/mes**, cobro por Actions con 1M incluido. El caso de uso (esperas humanas de días, timers, compensaciones) es exactamente el que Temporal resuelve. El costo real no es la licencia: es el **determinismo** que impone al código de workflow, y eso el plan no lo presupuesta. Self-hosted queda descartado por la propia doc del proveedor. |
| §46 L2129 «¿Redis o Valkey?» como pregunta abierta | decisión | redis.io/legal; aws.amazon.com/elasticache | **YA TIENE RESPUESTA — no requiere investigación** | Redis OSS ≥8.0.0 es tri-licencia RSALv2/SSPLv1/**AGPLv3** (única aprobada por OSI). ElastiCache soporta Valkey, Redis OSS y Memcached, y AWS publica **20% menos de precio en Valkey node-based y 33% en Serverless**. Es una decisión de 10 minutos, no una pregunta abierta. |
| §28 L1523 «1M filas <15 min» sobre Fargate | hecho | docs.aws.amazon.com ECS task definition parameters | **CONFIRMADO — no hay obstáculo** | Fargate llega a 16 vCPU / 120 GB y 32 vCPU / 244 GB; almacenamiento efímero 20–200 GiB cifrado con AES-256. La decisión de **no empezar con Kubernetes es correcta** por este requisito. |
| §17 L1102 «parseo en sandbox sin privilegios ni red» sobre Fargate | hecho | misma doc | **CONTRADICCIÓN VERIFICADA** | En Fargate **no son válidos** `dockerSecurityOptions` (sin seccomp, AppArmor ni SELinux propios), `privileged`, `ipcMode`, `maxSwap` ni `swappiness`; de `linuxParameters` *«the only capability you can add is CAP_SYS_PTRACE»*. El aislamiento real de Fargate es de microVM, que es **más fuerte**, pero el vocabulario de control del plan no corresponde a la plataforma elegida. |
| §10.5 L788 «workers sin salida a internet por defecto» | hecho | misma doc | **CONFIRMADO — con costo no presupuestado** | Requiere NAT gateway o VPC endpoints de interfaz para ECR; ambos tienen costo por hora y por GB que §37.2 no incluye. |
| §21 L1197 «OWASP ASVS nivel 2 / nivel 3 en autenticación, autorización, criptografía, archivos, auditoría» | decisión | github.com/OWASP/ASVS, 5.0.0 (2025-05-30) | **CONFIRMADO PARCIAL** | La nomenclatura L1/L2/L3 **sobrevive** en ASVS 5.0.0. Lo que cambió es la estructura de capítulos, de modo que el mapeo por nombre de dominio del plan ya no corresponde uno a uno. Requiere reexpresarse contra los capítulos de 5.0. |
| §21 L1196 NIST CSF 2.0 y SSDF | hecho | nist.gov | **CONFIRMADO** | CSF 2.0 vigente y las seis funciones citadas son las correctas. SSDF: la versión final es **SP 800-218 v1.1** (feb-2022); existe borrador 800-218r1. Citar la versión. |
| §28 L1526 «WCAG 2.2 AA» | decisión | w3.org | **CONFIRMADO — objetivo correcto** | WCAG 2.2 es Recomendación vigente (2023-10-05, act. 2024-12-12). WCAG 3.0 sigue en borrador temprano: **no debe influir en este plan.** |

---

## 3. Tabla de hallazgos

Severidades según el encargo. Cada hallazgo sobrevivió a un pase de refutación adversarial explícito.

### 3.1 Bloqueadores (12)

| ID | Sección | Hallazgo | Evidencia / razón | Cambio propuesto | Responsable | Gate |
|---|---|---|---|---|---|---|
| **BL-01** | §6.3 L275, §13.3 L914, Fase 3 L1907 | El buzón de correo dedicado no tiene ningún control de autenticación del remitente. | `SPF`, `DKIM`, `DMARC`, «remitente» y «allowlist» aparecen **0 veces** en el documento. §6.3 L288 promete «método de autenticación» por fuente pero no define ninguno para correo. Cadena: la dirección es semipública por diseño (se entrega a proveedores y se configura como forwarding DIAN) → un tercero envía un ZIP `AttachedDocument` válido → §17 valida el **contenido**, nadie valida el **origen** → se crea `obligation` y se emite `source_record_published` facturable. | Bloque «Autenticación del canal de correo» en §6.3 y §13.3: parte local aleatoria ≥128 bits no derivada del nombre de la empresa, rotable y revocable; verificación obligatoria de SPF, DKIM y alineación DMARC; allowlist de dominios remitentes por fuente; estado `origen_no_verificado` que **impide** autoenrutamiento (§25 L1315), auto-match (§25 L1317) y creación de `obligation`. | Security + Integrations | Datos reales |
| **BL-02** | §20 L1174, §22 L1247, §30.5 L1591 | El registro de tombstones no puede cumplir su función porque no se declara fuera de la unidad restaurable. | §20 afirma que «un tombstone impide que un restore reviva información eliminada». El documento nunca dice dónde vive; el lugar natural es la misma PostgreSQL que se restaura. Con backups de 35 días, una supresión del 10-mar y un restore al 05-mar resucitan el dato **y el tombstone**. Ningún criterio de éxito de restore (§22 L1261, §30.5) exige reconciliar contra supresiones. | El `delete_ledger` vive en la cuenta de seguridad, append-only con Object Lock, con `tombstone_id`, alcance (tenant, sujeto, tablas, claves de objeto, ids derivados), `deleted_at`, `basis`, solicitante; su retención excede la del backup más largo. **Job obligatorio de reconciliación post-restore** que reaplica todo tombstone anterior al instante restaurado, como criterio de éxito del restore, no como tarea posterior. | Security + Privacy | Datos reales |
| **BL-03** | §6.12 L541, §34 L1676, §15.4 L1077 | Los informes programados y los enlaces de solo lectura sobreviven a la revocación de acceso. | §15.4 fija el scope del worker **al crear el job**; §10.4 obliga a invalidar caché ante cambio de rol pero no menciona programaciones. Un preparador crea un envío programado de un informe multiempresa, sale de la firma, su membresía se revoca y el informe sigue llegando a su correo. El enlace de solo lectura es además una capacidad **al portador**, reenviable, que anula el control de §10.3 («`company_id` solicitado nunca se confía sin validación»). | (a) Toda programación se **revalida en cada ejecución** contra la membresía vigente del creador y se suspende si perdió acceso a cualquier empresa incluida; el conjunto de empresas se recalcula, nunca se congela. (b) El enlace de solo lectura pasa a estar **ligado a identidad** (destinatario nominado, autenticación o código de un solo uso), con revocación, registro de accesos y caducidad máxima. (c) Ambos entran en la lista de offboarding y en la revisión trimestral de accesos de §14.1. | Security + Product | Datos reales |
| **BL-04** | §10.3 L753, §16 L1092, §6.12 | Las vistas de informes eluden RLS por diseño de PostgreSQL, y el plan pone los informes exactamente ahí. | Verificado en doc oficial: las políticas de las tablas referenciadas por una vista usan **los derechos del propietario de la vista**, salvo `security_invoker`. §10.3 ordena réplica de lectura para informes y §16 exige vista consolidada de firma. Si esas vistas las crea un rol privilegiado sin `security_invoker`, todo consumidor lee sin RLS. Agravante: el plan no fija versión mínima de PostgreSQL ni política de parcheo, y CVE-2025-8713 permite leer datos muestreados que una política RLS pretendía ocultar. | Añadir a §10.3: «Toda vista, vista materializada y función que toque tablas tenant-owned se define con `security_invoker = true`; se prohíbe `SECURITY DEFINER` sobre el plano financiero salvo excepción aprobada con revisión de seguridad. La réplica de lectura hereda las mismas políticas y roles que el primario. Se fija versión mínima de PostgreSQL y SLA de parcheo en ADR-002; los avisos de seguridad del proyecto se revisan en cada release.» Añadir a §30.3 una prueba negativa por cada vista de informes. | Backend + Security | Datos reales |
| **BL-05** | §18, §13.5 L946, §10.3 L749, §19 | No existe ningún control sobre el plano de nube: quién puede leer S3 y la base desde la consola. | `CloudTrail` aparece 0 veces. No hay política de clave KMS que niegue principales humanos, no hay SCP, no hay «cero acceso permanente a producción» más allá de una mención suelta en §21. El grant JIT de §15.2 protege el plano de **aplicación**; el atacante interno usa el que lo rodea. Complemento: `break-glass` aparece dos veces (§10.3 L749, §19 L1137) y **no tiene procedimiento** — ni doble control, ni límite de tiempo, ni revisión posterior. | Subsección «Control del plano de nube» en §18 y §13.5: (a) cero roles humanos permanentes con permisos de plano de datos en producción; todo acceso por elevación temporal con ticket, aprobador distinto, duración ≤4 h y grabación de sesión; (b) política de clave KMS que **niega** `Decrypt` a principales humanos, permitiéndolo sólo a roles de servicio; (c) CloudTrail con data events de S3 hacia la cuenta de logs, append-only; (d) SCP que impide desactivar CloudTrail o alterar políticas de clave; (e) procedimiento de break-glass con doble aprobación, credencial sellada, expiración automática y revisión obligatoria en ≤24 h. | Security + Platform | Datos reales |
| **BL-06** | §0.2 L59, §38 Fase 0 L1866, §20 L1176 | DRG-01 es circular y sus fechas se contradicen: no se puede anonimizar sin recibir primero. | L59 prohíbe recibir datos no anonimizados hasta aprobar el checklist, pero Fase 0 (meses 0–2) exige «observar diez cierres y cinco firmas» y construir un «corpus anonimizado de 150–250 documentos». Anonimizar es tratar. Además L79 fija L-01 «antes de Fase 1 productiva» mientras §20 L1176 declara que **L-01 bloquea DRG-01**, cuyo plazo es «antes del primer piloto real» — la dependencia está invertida. | Crear **DRG-00 «recepción acotada para descubrimiento y anonimización»** con controles propios y menores: contrato de tratamiento firmado con cada firma participante, finalidad única de construcción de corpus, ambiente aislado sin producción, retención máxima declarada, borrado verificable al terminar, inventario nominal de documentos recibidos y prohibición de uso comercial. Adelantar L-01 a **antes de DRG-00** y corregir su fecha límite. | Legal + Security + Product | Datos reales |
| **BL-07** | §12.3 L875-881, §6.3, §6.7, §35.1 | La misma cuenta bancaria conectada por dos caminos publica movimientos dobles: la idempotencia está anclada a la **fuente**, no a la **cuenta**. | Las cinco claves de §12.3 son por fuente (`company_id + source_id + sha256`) o por conexión (`connection_id + provider_event_id`); ninguna referencia `financial_account`. §6.3 permite simultáneamente archivo manual, correo, SFTP, API y agregador. Cuando la firma sube el extracto en PDF **y** el agregador entra en producción para la misma cuenta, se publican dos movimientos canónicos por transacción. Doble impacto: el saldo no cuadra y §33.4 («no cobrar de nuevo por duplicados») se incumple facturando dos `source_record_published`. | Sexta clave en §12.3, de nivel **canónico** y no de fuente: `company_id + financial_account_id + value_date + amount + direction + normalized_reference`. Una transacción económica admite N evidencias de origen y exactamente **un** `money_movement`; las evidencias adicionales se enlazan como `external_reference`, no se republican, y no vuelven a facturar. Añadir a §6.3 la detección de «cuenta ya conectada por otra fuente» al crear una conexión. | Data + Backend | Construcción |
| **BL-08** | §13.2 L897-910, §11 L819, §6.11 | No existe control de completitud de la ingesta. Un `DatasetVersion` puede pasar a `published` sin verificar que sea **todo** lo que la fuente tenía para el periodo. | El contrato de conector exige backfill, incremental, pending vs posted, paginación, frescura e idempotencia — nada obliga a comparar contra los totales del origen. §6.11 vigila «discontinuidad de saldo» como **señal**, no como precondición. En un producto de conciliación, la ingesta incompleta produce el peor fallo posible: un cierre que cuadra sobre datos parciales. | «Reconciliación de completitud» como obligación 13 del contrato de conector y como **precondición de `published`**: registrar por fuente y periodo los totales declarados por el origen (número de movimientos, suma de débitos y créditos, saldo inicial y final), compararlos contra lo ingerido y bloquear la publicación ante discrepancia, con excepción explícita y motivada. Para fuentes de archivo, usar los totales de control que §6.5 L343 **ya captura**. | Data + Integrations | Construcción |
| **BL-09** | §6.7 L397-406, §6.8, §6.10 L489 | Falta la entidad de saldo y, con ella, el artefacto que en Colombia constituye la conciliación bancaria. | El modelo concilia **movimientos**; nunca establece *saldo según extracto ± partidas conciliatorias = saldo según libros*. El saldo aparece como interacción de importación (L343), tipo semántico (L380) y señal de anomalía (L497), nunca como entidad ni como condición de cierre. §6.10 L489 permite cerrar un periodo sin que ningún saldo cuadre. | Añadir a §6.7: `account_balance` {`financial_account_id`, fecha contable, origen ∈ extracto\|libros\|sistema, tipo ∈ inicial\|final, importe, moneda, `source_locator`} y `reconciliation_statement` {`period_id`, `financial_account_id`, saldo extracto, saldo libros, partidas conciliatorias enlazadas, diferencia}. Añadir a §6.10 la condición de cierre: **ningún periodo se cierra con diferencia no explicada distinta de cero**; una diferencia aceptada exige motivo, monto y aprobador. Añadir el estado de conciliación de saldos al paquete de cierre y a §44. | Product + Contador + Data | Construcción |
| **BL-10** | §12.2 L858-871, §6.10 L489, §30.2 | La versión del **software** no es un objeto versionado ni forma parte del snapshot de cierre: los cierres no son reproducibles. | §12.2 versiona parser, clasificador, modelo OCR, esquema canónico, plantilla, receta, regla, política de anomalías, prompt e informe — pero no el binario que los ejecuta. Un cambio en el motor de matching, en el redondeo o en una librería de fechas altera el resultado sin cambiar ningún objeto versionado, y §6.10 promete «snapshot inmutable». La promesa central del producto («reproducible») descansa sobre la única pieza no versionada. | Añadir `engine_release` (semver + SHA del artefacto) y `canonical_schema_version` a `DatasetVersion`, `MatchRun`, informe y `closed_snapshot`. Clasificar cada release como «neutral» o «afecta resultados»; las segundas exigen simulación sobre el corpus adjudicado y anotación en los periodos afectados. Nuevo ADR-022 «Versionado del motor y reproducibilidad de cierres». | Engineering | Construcción |
| **BL-11** | §21 L1206, §10.2 L719, §14 L976, §26 | El alcance «fuera de PCI DSS» no se sostiene con el pipeline descrito. | §21 promete «permanecer fuera de PCI DSS evitando almacenar, procesar o transmitir datos de tarjeta», pero §10.2 hace que **todo archivo aterrice primero en `quarantine/`**, es decir en su almacenamiento, antes de cualquier detección. Un archivo de datáfono con PAN completo ya fue almacenado cuando se detecta. §26 promete «clasificación y minimización» dentro del AI Gateway, es decir **después** de la cuarentena. | Declarar el orden de operaciones en §10.2 y §17: detección determinística de PAN (regex + Luhn), credenciales y CVV **en el mismo paso de aceptación**, antes de cualquier copia a `raw/`; ante detección positiva, rechazo o redacción destructiva con registro de sólo hash y metadatos, notificación al tenant y prohibición de retención del original. Documentar el alcance PCI resultante con el asesor correspondiente y registrar la decisión en el registro de §0.2. | Security + Legal | Datos reales |
| **BL-12** | §26 L1333, §26.1, §27.1 L1475 | Dependencia circular no declarada: el control que hace cumplir la prohibición de egreso es **un modelo de IA** que no está gobernado. | §26.1 prohíbe enviar datos prohibidos a un LLM externo; §27.1 L1475 implementa «Clasificación, NER y **redacción**» con «Reglas + ONNX Runtime». Es decir, un modelo decide si datos prohibidos salen. Ese uso no aparece como fila en §24, no tiene nivel de riesgo, no tiene umbral de recall, no tiene fallback y no tiene dueño — pese a ser el único control entre el dato prohibido y un tercero. | Añadir fila en §24: «Redacción y minimización pre-egreso — **AI-2 con función de seguridad**». Regla técnica: (1) detección **determinística primero** (regex + checksum para NIT, Luhn para PAN, patrones de cuenta, IBAN, correo y credencial); (2) el modelo sólo puede **añadir** detecciones, nunca retirarlas; (3) umbral de recall medido sobre corpus adversarial con gate publicado; (4) si el clasificador no está disponible, **no hay egreso** — fallo cerrado, no degradado. | ML + Security | Datos reales |

### 3.2 Mayores (21)

| ID | Sección | Hallazgo | Cambio propuesto | Responsable | Gate |
|---|---|---|---|---|---|
| **MA-01** | §3.2 L152 vs §34 L1664 vs §35.1 L1743 | **El ICP declarado no cabe en los planes.** Con el multiplicador de 2–3× que el propio §35.1 define, Control (25.000 SRP) cubre 8.300–12.500 movimientos económicos: el **cuartil inferior** de un ICP declarado de 500–50.000. Una empresa en el extremo alto necesita 100.000–150.000 SRP → Control + 8 a 13 bloques de overage = **$821.000–$1.116.000/mes**, es decir hasta **1,24× el precio de Firma** por una sola empresa. | Elegir una de tres: (a) reducir el ICP publicado al rango que los planes sirven (500–12.000 movimientos) y decir explícitamente que arriba se vende contrato; (b) recalibrar las cuotas al multiplicador real medido en pilotos; (c) cambiar la unidad facturable a movimiento económico conciliado y dejar `source_record_published` como métrica interna de costo. **Recomiendo (a) para el lanzamiento y (b) tras los pilotos.** | Product + Finance | GA |
| **MA-02** | §34 L1655 vs §37.2 L1806 | **La anualidad se contradice a sí misma en el recaudo.** §34 la condiciona a «costo de recaudo anual ≤1%»; §37.2 calcula el COGS anual como 12× el mensual, arrastrando 12 cobros de recaudo (~3%). Verificado: 348 = 29×12, 888 = 74×12, 2.412 = 201×12. Y la tarifa pública de Wompi (2,65% + $700 + IVA) da ~3,2% sobre la anualidad de Esencial. | Separar la línea «Recaudo» del resto del COGS y modelarla por **evento de cobro**, no por mes. Declarar el medio de pago que hace viable el gate ≤1% (PSE o transferencia con tarifa fija) y publicar la anualidad **sólo** para ese medio. Recalcular las tres columnas anuales con recaudo real. | Finance | GA |
| **MA-03** | §34.3 L1703, §37.2 | **La empresa adicional de Firma viola el piso de margen del propio plan.** COGS marginal recalculado con la tabla de §37.2: feed 8,00 + infra 3,50 + ingesta 1,80 + IA 1,80 + soporte 5,50 + recaudo 2,07 = **22,67** → margen **67,1%** sobre $69.000, contra un piso declarado de 70% y una regla de «margen incremental del overage ≥70%». Al 100% de utilización cae a 64,3%. | Subir a **$85.000–$89.000/mes** (margen 73–75%), o reducir la cuota incluida (quitar el feed estándar y venderlo aparte, que es la línea de costo dominante). Nota de contraste: el precio marginal **sí** es defendible frente a Alegra Pyme ($163.900 de lista con 1 conexión bancaria) — el problema es de COGS, no de mercado. | Finance | GA |
| **MA-04** | §37.1 L1783, §34 L1655, §44.15 | **El crédito del 100% del piloto rompe el margen del año 1.** Con la caja real y el COGS de §37.2: Esencial **65,0%** (bajo el piso duro de 70%), Control **73,0%**, Firma **73,6%** (ambos bajo el objetivo de 75%). §37.4 L1848 prohíbe apilar anualidad, descuento fundador y comisión de canal bajo el piso, pero **no incluye el crédito de piloto en esa lista**. | Añadir el crédito de piloto a la regla de no apilamiento de §37.4. Limitar el crédito al **50%** o acreditarlo contra el **segundo** año. Declarar explícitamente que el KPI de §44.15 se mide sobre cohortes en su **segundo** año de contrato y publicar también el margen del año 1 como métrica separada. | Finance | GA |
| **MA-05** | §34 L1662, §3.2 L154, §44.1 | **Firma reparte 6 feeds entre 10 empresas (0,6 por empresa)** mientras el ICP exige al menos una cuenta bancaria por empresa. Cuatro de cada diez empresas quedan sin feed y vuelven a la carga manual — justo en el plan que se vende como «canal de escala». Peor con §44.1 (50 empresas por firma): 1.000 SRP y 0,12 feeds por empresa. | Rediseñar Firma como **precio base + precio por empresa activa** en vez de bloque de 10 con recursos compartidos; o subir feeds incluidos a 10 y trasladar el costo al precio. Y corregir §44.1: o el criterio de producto completo baja a un número que el plan sirve, o se publica el escalón de precio para 50 empresas. | Product + Finance | GA |
| **MA-06** | §36 completo | **La evidencia competitiva no sostiene el precio y omite a los competidores que sí lo fijan.** §36 cita tres comparables en dos monedas sin TRM, sin fecha y sin normalizar IVA. Omite: Siigo contador ilimitado ($535.900/año, empresas ilimitadas), el Espacio Contador gratuito de Alegra, el entitlement de 3 feeds de Alegra Pro por $250.900/mes, Dext ($17,70/cliente/mes) y **Simetrik**. | Reescribir §36 como tabla con columnas Competidor · Precio · Moneda · Unidad de cobro · Feeds incluidos · Fecha de consulta · URL, incluyendo los seis anteriores. Declarar la TRM de referencia y su fecha. Añadir Simetrik y Dext al red-team de §37.4 y a §45 como riesgo competitivo nombrado. | Product + Founder | GA |
| **MA-07** | §32 L1629, §13.1 L892, §37.2 L1803, Fase 3 | **La conectividad bancaria es un supuesto sin fuente.** La doc oficial de Belvo lista sólo Brasil y México; ningún proveedor con cobertura colombiana publica precio por cuenta/mes. La línea de COGS más grande de Firma (48 de 201) no tiene origen, y el gate de Fase 3 depende de un agregador que no está identificado. | Convertir la conectividad en **entregable de Fase 0**: tres cotizaciones firmadas con precio por cuenta conectada/mes, mínimo mensual, tarifa de refresco y **cobertura nominal por banco colombiano**. Hasta tenerlas, marcar la fila «Feeds» de §37.2 como `NO MEDIDO` y no publicar límites de feeds. Declarar el archivo como canal primario y el feed como mejora — que es lo que ya dice §1.3.8. | Founder + Integrations | GA |
| **MA-08** | §6.4 L313-320, §44.4 | **Las familias de formato prioritarias pueden no existir en el mercado objetivo.** Lo único verificado en fuente primaria de un banco colombiano es descarga en **PDF y XLS**. OFX, MT940 y camt.053 no están confirmados para clientes PYME, y §44.4 convierte OFX en criterio de producto completo. Riesgo derivado no verificado pero barato de comprobar: extractos PDF **protegidos con contraseña**. | Reordenar §6.4 tras el corpus de Fase 0, no antes. Mover OFX/MT940/camt.053 a «soportados si el corpus los encuentra» y elevar **XLS/XLSX y PDF nativo** a familias de primera clase. Añadir a §17 el manejo de PDF cifrado: nunca solicitar ni almacenar la contraseña como credencial; descifrado en el cliente o carga del PDF ya desprotegido, con la decisión registrada. Sustituir el criterio §44.4 por «los cuatro formatos que el corpus de Fase 0 demuestre dominantes». | Data + Product | Construcción |
| **MA-09** | §11 L835, §11.1 L840, §13.2 L906, §13.4 L931 | **Cuatro capas pueden reintentar el mismo trabajo y ninguna es declarada dueña:** outbox, cola administrada con su propio redrive, política de reintentos de Temporal y «reintento y circuit breaker» de cada conector, más DLQ de webhooks. No hay presupuesto máximo de intentos ni asignación de propiedad. | ADR-013bis «Propiedad de reintentos»: (1) el adaptador de conector **no reintenta**, clasifica el error en {`retryable`, `fatal`, `requires_human`} y falla rápido; el circuit breaker sólo abre y cierra; (2) el backoff vive en una sola capa por tipo de trabajo — cola para el trabajo sin estado, Temporal para el trabajo con estado; (3) presupuesto máximo de intentos y de tiempo por job, con destino explícito al agotarse. | Backend | Construcción |
| **MA-10** | §9.4 L698 vs §25 L1317 vs §37.3 L1837 | **Contradicción directa sobre el plano analítico.** §9.4 afirma que «nunca se utiliza para autorizar una acción», pero la precisión observada y el límite de Wilson por slice —que **habilitan el auto-match**— se calculan sobre casos adjudicados históricos, que es contenido del plano analítico. | Declarar en §9.4 la excepción y darle garantías: «las estadísticas de habilitación de automatización son un **control**, no analítica; viven en el plano financiero, están versionadas, son auditables y se recalculan con la misma disciplina de linaje que una decisión». O mover el cómputo al plano financiero. Cualquiera de las dos, pero escrita. | Data + Backend | Construcción |
| **MA-11** | §25 L1317-1319 | **Trinquete que puede impedir automatizar para siempre.** El slice incluye `rule_or_model_version`: cualquier ajuste de una regla crea un slice con cero adjudicaciones y devuelve el caso a sugerencia. Combinado con §15.4 L1074 y con la práctica de afinar reglas cada ciclo, las adjudicaciones nunca se acumulan y §44.7 (cobertura ≥70%) queda inalcanzable. | Herencia de evidencia entre versiones: añadir `rule_lineage_id` y `change_class` ∈ {cosmético, restrictivo, expansivo}, clasificado automáticamente **reejecutando la nueva versión sobre el corpus adjudicado histórico** — capacidad que §6.9 L459 ya exige para convertir excepciones en reglas. Un cambio cosmético o restrictivo hereda las adjudicaciones; uno expansivo las pierde sólo para los casos nuevos que habilita. | ML + Data | Construcción |
| **MA-12** | §25 L1318 (aritmética) | **El umbral de «1.000 casos adjudicados» subestima el n realmente necesario.** Recalculado con Wilson unilateral 95% (z = 1,645): con **0 errores** basta n = 539 y con **1 error** n = 894 — es decir, en n = 1.000 la conjunción **sí** se cumple si el slice es casi perfecto. Pero un slice que se sitúe **exactamente** en el piso declarado de 99,8% (2 errores en 1.000) da LB = **99,397% y falla el gate**. Para pasar en el punto que el plan declara aceptable hace falta n ≈ **1.500**. El número que gobierna no es 1.000: es el límite de Wilson. | Reescribir §25 y §37.3.8 así: «El criterio vinculante es el límite inferior unilateral de Wilson al 95% ≥ 99,5%. El mínimo de 1.000 casos adjudicados es un piso de tamaño muestral, no una condición suficiente: un slice con precisión observada de 99,8% requiere aproximadamente 1.500 adjudicaciones para superarlo.» Publicar la tabla n-mínimo por número de errores. | ML | Construcción |
| **MA-13** | §6.5 L348, §6.11 L497 | **La detección de `schema drift` es sólo estructural y el término nunca se define.** Un cambio de convención de signo, de unidad (centavos a unidades), de zona horaria o de moneda pasa sin alterar nombres, orden, número ni tipos de columna. La receta antigua se aplica sobre un formato semánticamente distinto y §6.11 lo trata como señal, no como bloqueo. | Definir el detector en §6.5 con señales enumeradas y falsables: cambio de esquema; **cambio de perfil estadístico por columna** (proporción de signos, cardinalidad, rango intercuartílico, tasa de nulos, longitud media) contra la línea base de la plantilla; y **fallo de los totales de control**, que §6.5 L343 ya captura. Cualquiera de las tres suspende la aplicación automática. | Data | Construcción |
| **MA-14** | §15.4 L1071, §6.1 L243 | **La segregación se evalúa por identidad, no por persona, y el plan habilita el bypass.** §15.4 dice «una misma **identidad** nunca prepara y aprueba»; §6.1 exige soportar «una persona con membresías diferentes en varias firmas»; §15.3 permite al Dueño PYME gestionar «usuarios cliente limitados». `person_id`, «persona natural» y «cédula» aparecen 0 veces. Una persona con dos correos prepara con uno y aprueba con otro. | Introducir `subject_id` de persona natural, distinto del `user_id` de credencial, y evaluar **todo deny de segregación a nivel `subject_id`**. Poblarlo con verificación proporcional: para roles que aprueban o cierran, exigir un factor de identidad fuerte (passkey vinculada, o documento verificado). Donde no exista verificación, activar detección de correlación (mismo dispositivo, misma IP, misma sesión) y marcar la decisión como `posible_autocertificacion`. | Security + Product | Construcción |
| **MA-15** | §34 fila «Gobierno» L1673, §34.2 L1687 vs §1.3.9, §15.4 | **La segregación de funciones se vende como característica del plan Control, contradiciendo el principio 9 y §15.4.** La fila «Gobierno» pone «Segregación» sólo en Control, §34.2 dice «incluye API, **segregación** y automatización avanzada», y la lista «Todos incluyen» de L1679 **no la menciona**. Pero §1.3.9 declara «seguridad y privacidad no dependen del plan pagado» y §15.4 L1071 la enuncia como invariante absoluto («un deny de segregación prevalece sobre la unión de roles»). En un producto de control financiero, esto es exactamente lo que no se puede vender por tramos. | Mover «segregación de funciones y registro `autocertificada_sin_revision_independiente`» a la lista «Todos incluyen» de L1679. Reescribir la fila «Gobierno» de Control como «**roles personalizados** y API» y la de Firma como «roles firma/cliente, carga de equipo y matriz multiempresa». La segregación es motor, no entitlement. | Product | GA |
| **MA-16** | §22 L1245 vs §28 L1518 | **RTO y disponibilidad son aritméticamente incompatibles.** Presupuesto de 99,9% mensual = **43,2 min**. RTO inicial de 4 h = 240 min = **5,6× el presupuesto mensual completo** y **46% del presupuesto anual en un solo evento**. RTO maduro de 2 h = 2,8× el mensual. | Separar y escribir tres conceptos: (1) SLO/SLA de disponibilidad mensual **con exclusión explícita y auditable de eventos de desastre formalmente declarados**; (2) objetivo de recuperación ante desastre, medido aparte; (3) presupuesto de error operacional que gobierna el ritmo de despliegue. Añadir que un evento DR declarado consume presupuesto de DR, no de SLO, y que la declaración es auditable. | SRE + Product | GA |
| **MA-17** | §38 Fase 0 L1864 vs §39.3 L1971 vs §41 | **Fase 0 está subestimada entre 2× y 3×.** Estimé los 16 artefactos de §41 en ~17,5 persona-mes y el resto del alcance declarado de Fase 0 (observar 10 cierres y 5 firmas, corpus de 150–250 documentos, 3 bancos + 3 pasarelas + 2 ERP + DIAN, 6 prototipos, acuerdos de tratamiento, pricing discovery) en ~7 más: **~24,5 PM contra 8–12 presupuestados**. Complemento verificado: seguridad y privacidad está a media jornada (~1 PM) frente a 4–6 PM de entregables obligatorios suyos. | Dividir §41 en «bloqueantes de Fase 1» (modelo canónico, threat model, matriz RBAC/ABAC, contrato de conector, política de retención, ADRs 001-010, corpus gold) y «bloqueantes de Fase 2» (el resto). Extender Fase 0 a **3 meses con 18–22 PM**, o recortar explícitamente el alcance y decir qué se aplaza. Subir seguridad/privacidad a dedicación completa durante Fase 0. | Product + Eng | Construcción |
| **MA-18** | §39.1 L1944 vs §39.3 L1971 | **La plantilla y el presupuesto se contradicen en la fase más cargada.** Fase 1 (meses 2–5, 3 meses) requiere **10,0–12,7 FTE**; §39.1 define un equipo inicial de ~7,5 FTE hasta el mes 5 y §39.2 sitúa la expansión en el mes 5. Déficit de 8–16 PM justo antes del primer gate de construcción, y el extremo superior **excede el pico máximo de 12 FTE** declarado en §38 — en la fase más temprana. | Adelantar al mes 2 las contrataciones de Platform/SRE e Integrations, o reperfilar Fase 1 a 4 meses (meses 2–6) desplazando el resto. Publicar la curva de FTE por mes junto a la tabla de persona-mes, para que la incoherencia sea visible en una sola vista. | Founder + Eng | Construcción |
| **MA-19** | §13.3 L914 vs §3.3 L162 | **La integración DIAN cubre cuentas por pagar mientras el caso vertical primario es cuentas por cobrar.** §13.3 describe recepción de `AttachedDocument` — documentos que terceros emiten hacia la empresa. §3.3 define el caso primario como *pedido/factura propia → pago en pasarela → liquidación → abono bancario*. Las facturas **emitidas** por la empresa, que son el ancla de ese flujo, no tienen origen declarado en ninguna parte. | Declarar explícitamente la fuente del lado de cuentas por cobrar: exportación del ERP, API del proveedor tecnológico de facturación del cliente, o mecanismo DIAN autorizado. Añadirla al orden de conectividad de §13.1 con la prioridad que corresponde al caso vertical, no después de él. Registrar la restricción jurídica correspondiente. | Product + Legal | Construcción |
| **MA-20** | §17 L1102 vs §13.5 L940 | **El vocabulario de aislamiento del sandbox no corresponde a la plataforma elegida.** En Fargate no son válidos `dockerSecurityOptions` (sin seccomp, AppArmor ni SELinux propios), `privileged`, `ipcMode`, `maxSwap` ni `swappiness`; de `linuxParameters` sólo puede añadirse `CAP_SYS_PTRACE`. El aislamiento real es de microVM, **más fuerte** que un perfil seccomp — pero el plan promete controles que no puede configurar, y un auditor lo leerá como incumplimiento. | Reescribir §17 L1102 como: «Parseo en tarea aislada con aislamiento de microVM del runtime administrado, sin privilegios elevados, sin acceso a red saliente por defecto (subred privada sin NAT, endpoints de interfaz sólo hacia ECR y S3), con almacenamiento efímero cifrado y limitado, usuario sin privilegios dentro del contenedor y sistema de archivos raíz de sólo lectura.» Presupuestar en §37.2 el costo de NAT gateway o VPC endpoints. | Platform + Security | Construcción |
| **MA-21** | §41 L1994-2011, §0.2 L82, §37.1 L1783, §6.14 | **El producto no tiene nombre, y la marca no figura entre los artefactos obligatorios.** En 2.186 líneas se le llama «la plataforma» o «el producto». §41 enumera 16 artefactos previos a construcción significativa y ninguno es nombre, marca, dominio ni búsqueda de antecedentes. Pero el nombre entra antes que casi todo lo demás: va en el DPA y en los términos, en los contratos de los once pilotos pagados de §37.1, en la interfaz que ve el cliente y en un registro marcario cuyo trámite ante la SIC se mide en meses. Renombrar después de firmar once pilotos es reproceso comercial y jurídico enteramente evitable. | Añadir «Nombre, marca, dominio y búsqueda de antecedentes en clases 9 y 42» a §41, y una fila **M-01** al registro de decisiones de §0.2: dueño Product/Legal, evidencia = búsqueda SIC más disponibilidad de dominio, fecha límite anterior al primer contrato de piloto, gate Construcción. Trabajo desarrollado en el **Anexo A**. | Product + Legal | Construcción |

### 3.3 Medios y menores

Sobrevivieron 122 hallazgos adicionales (98 Medio, 44 Menor menos los promovidos). No los transcribo íntegros; agrupo los que cambian una decisión y dejo el resto como anexo de trabajo.

**Arquitectura y datos:** ambigüedad Redis/PostgreSQL sobre progreso de job, resuelta por §7.5 pero no escrita en §10.4 · Temporal introduce un tercer almacén de estado (su historia de eventos) no reconciliado con §11 · el diagrama de §8 y los cuatro planos de §9 no son mutuamente consistentes y el diagrama omite el AI Gateway · `pgvector` vive en la instancia operacional que §10.6 quiere proteger de carga analítica · el disparador de celda («15–20% de capacidad sostenida») no es medible porque «capacidad» no se define en ninguna parte · falta fecha contable distinta del instante UTC · `N:M acotado` sin declarar la cota ni el algoritmo · el localizador de origen contiene una referencia hacia adelante («match, informe y cierre que lo usaron») que obliga a mutar un registro declarado inmutable · las correcciones manuales como overlay no entran en la clave idempotente del dataset · faltan notas crédito/débito modeladas, fusión de contrapartes, gestión de datos de referencia (calendario de festivos, tarifas de retención, catálogo de bancos) y transición de salida desde `reopened`.

**Seguridad y privacidad:** namespace de caché sin sujeto ni conjunto de empresas autorizadas · webhooks salientes sin control de destino (SSRF) · SFTP vendido en Control con cero controles asociados · nombre de archivo **original** conservado como dato controlado por el atacante y renderizado en UI · polyglots y PDF activo fuera del alcance de §17 · neutralización de fórmulas sin conjunto de disparadores declarado · material KMS en pruebas de restore con ambigüedad peligrosa · sin mecanismo de cambio de subencargado · sin procedimiento de derechos del titular (canal, verificación, plazos, enrutamiento Responsable/Encargado) · observabilidad sin control de acceso, retención ni allowlist · pentest programado en Fase 5 mientras los datos reales entran en Fase 2.

**IA:** el bucle de autoconfirmación no está cerrado (la precisión se mide sobre adjudicaciones producidas por el mismo bucle) · multiplicidad y miradas repetidas sin corrección al comparar decenas de slices · «plantilla exacta» sin definir qué significa exacta · el corpus de 3.000 casos de §27.1 está subdimensionado ~2× para los gates escritos, y «activación indebida ≤0,1%» no es demostrable con cero eventos observados · no hay control de latencia ni presupuesto duro de costo por tenant, sólo medición · «shadow, canary y rollback» sin duración, volumen ni criterio · no existe procedimiento de retirada para decisiones ya producidas por una versión revertida · «RAG sobre documentación, sin acceso financiero implícito» es demasiado débil para el mayor vector de fuga interna.

**Producto y operación:** se puede cerrar un periodo desde el teléfono sin evidencia mínima definida · «bajo riesgo» para resolución masiva no está definido ni tiene dueño · WCAG 2.2 AA declarada sin presupuesto, gate, artefacto ni rol · sin SLO de app móvil ni de jobs asíncronos vistos por el usuario · el contenido de las notificaciones push puede exponer datos clasificados como financiero sensible · el modo degradado existe como tabla de ingeniería, no como experiencia de producto · sin política de versión mínima de la app ni kill switch por versión · **el cambio de contador** —el evento comercial más frecuente del segmento— es estructuralmente imposible: la FK compuesta `(workspace_id, company_id)` impide asociar una empresa a otra firma y no existe procedimiento de transferencia · el paquete de portabilidad propio no está especificado pese a exigírselo a cada proveedor · la propiedad de recetas y reglas creadas por el cliente no está decidida · el programa ignora la estacionalidad del calendario tributario colombiano · la rotación de guardia no está dimensionada ni presupuestada.

**Comercial:** el bloque de overage no define si es cargo único o si eleva la base · «fuente» tiene dos definiciones distintas y su relación con «feed bancario estándar» nunca se declara · el piloto de empresa vende 15.000 registros/mes, **3× el cap de Esencial**, empujando a un overage inmediato al convertir · el modelo de canal B2B2B es estrategia sin mecanismo (quién contrata, quién factura, figura jurídica de la firma, atribución de cuenta) · el COGS no tiene dimensión de moneda: precios en COP fijos por doce meses contra costos mayoritariamente en USD, sin fila de sensibilidad FX · el producto mide productividad individual de empleados de la firma cliente sin que ese tratamiento exista en §14, §20 ni el DPA.

### 3.4 Hallazgos descartados por refutación adversarial (muestra)

Registro estos porque saber qué **no** hay que cambiar evita reescritura innecesaria. De 177 hallazgos brutos, 23 se cayeron. Los más relevantes:

- **«El slice no declara si es global o por tenant»** — falso: §27 L1379 lo resuelve fuera de §25 («reglas y modelos clásicos **por tenant** con sus propios históricos»).
- **«El índice pgvector no declara alcance»** — falso: §10.3 L746 fija la regla de `workspace_id NOT NULL` para todo registro tenant-owned, que aplica a la tabla de embeddings.
- **«§16 no cubre índices vectoriales ni cachés de prompt»** — falso: caen dentro de las capas 2, 4 y 6 ya definidas.
- **«El linaje por campo no escala al NFR»** — falso: la aritmética del refutador confirma que sí, y el hallazgo atribuía al plan una implementación que el plan no prescribe.
- **«§36 no sostiene el precio de §34»** — descartado como defecto: §33 principio 8 dice explícitamente que la tabla es hipótesis y que el precio se valida con pilotos. (El defecto real de §36 es otro y está en MA-06.)
- **«Temporal se adopta por calendario y no por umbral»** — falso: §13.5 L944 fija un activador funcional («cuando comienzan ciclos, timers y esperas humanas durables»), no una fecha.
- **«§44.1 exige 50 empresas y no hay precio»** — falso: §34.3 L1703 publica el precio de empresa adicional. (El problema real es de recursos incluidos, MA-05.)
- **«Los dos umbrales estadísticos son mutuamente inconsistentes»** — **parcialmente falso, y lo corrijo en MA-12**: «≥99,8%» es una cota inferior, no una igualdad; en n = 1.000 con 0 o 1 errores la conjunción sí se satisface. El hallazgo válido es más fino: el número que gobierna es el límite de Wilson, no el 1.000.

---

## 4. Ataques conceptuales obligatorios

Los quince escenarios del encargo. **Ninguno resultó plenamente controlado**: 13 tienen control insuficiente y 2 carecen de control. Esto no es señal de un plan malo — es señal de que los controles están escritos como principios y todavía no como mecanismos.

| # | Escenario | Estado | Por dónde ocurre | Referencia |
|---|---|---|---|---|
| 1 | Un contador ve la empresa equivocada | **INSUFICIENTE** | La clave de caché de §10.4 L775 es «ambiente + workspace + versión de permisos»: no incluye el **sujeto** ni el conjunto de empresas autorizadas. Dos usuarios de la misma firma con carteras distintas comparten entrada de dashboard de portafolio. No viola RLS, por eso las pruebas cross-tenant de §16 capa 8 no lo ven. | §3.3, patch P-07 |
| 2 | Una exportación incluye datos no autorizados | **AUSENTE** | Informes programados que congelan el scope al crear el job y enlaces de solo lectura al portador. | **BL-03** |
| 3 | Un archivo manipula al sistema o a un modelo | **INSUFICIENTE** | Inyección por el buzón sin autenticación de origen; y el asistente de recetas de §24, cuya DSL se valida sintácticamente mientras la **semántica** la elige el modelo a partir de un archivo no confiable. | **BL-01**, §3.3 |
| 4 | Una receta antigua se aplica a un formato cambiado | **INSUFICIENTE** | La deriva **semántica** sin cambio estructural no dispara el detector, y los totales de control son interacción de UI, no validación bloqueante. | **MA-13** |
| 5 | Un match de alta confianza es incorrecto | **INSUFICIENTE** | El slice no estratifica por **exposición financiera**: acumula sus 1.000 adjudicaciones con micropagos y luego autoriza un movimiento de cien millones bajo la misma estadística. | §3.3, patch P-05 |
| 6 | Un usuario prepara y aprueba combinando roles | **INSUFICIENTE** | Segregación anclada a `identidad` y a «la misma» decisión; dos identidades de una persona la eluden. | **MA-14** |
| 7 | Soporte accede a un documento sin permiso | **INSUFICIENTE** | El grant JIT protege el plano de aplicación; break-glass, consola de nube y acceso directo a S3 lo rodean. | **BL-05** |
| 8 | Un borrado se revierte al restaurar un backup | **INSUFICIENTE** | El tombstone comparte destino con el dato que debe suprimir. | **BL-02** |
| 9 | Un embedding o índice filtra información de otra empresa | **INSUFICIENTE** | El mecanismo **no** filtra: verificado que pgvector aplica el filtro tras el index scan pero antes de devolver filas, de modo que la confidencialidad se preserva y sólo se degrada el recall. El riesgo es de **diseño**: el valor de negocio de «similitud de plantillas» empuja a un índice global, y un índice global de plantillas derivadas de archivos de clientes es exactamente «información de una empresa para ayudar a otra», prohibido en §26.1. | §3.3, patch P-06 |
| 10 | Un costo de OCR/IA vuelve no rentable un plan | **INSUFICIENTE** | §34 pone «OCR: telemetría piloto» en los tres planes: **no hay cuota de páginas**. §33 declara que la única unidad de volumen es `source_record_published`, que no correlaciona con el consumo de OCR. Un tenant con 5.000 registros y documentos escaneados de 40 páginas rompe el techo de COGS ≤25% de §35 sin superar ningún límite contractual. | §3.3, patch P-09 |
| 11 | Una caída de proveedor impide cerrar | **INSUFICIENTE** | La matriz de §22 tiene siete filas y **omite** proveedor de identidad, KMS, workflow durable, object storage, email/push, CDN/WAF y antivirus — todos clasificados como «comprar» en §32. Si cae el IdP, nadie entra; si cae KMS, nada se descifra. Ninguno tiene modo alterno. | §3.3, patch P-08 |
| 12 | Una integración duplicada crea movimientos dobles | **AUSENTE** | La idempotencia está anclada a la fuente, no a la cuenta. | **BL-07** |
| 13 | Un modelo local selecciona la empresa equivocada | **INSUFICIENTE** | La **mutación** está genuinamente bloqueada y el diseño de §27.1 es correcto en ese eje. Pero el **cambio de contexto de empresa** no es una mutación, y por tanto no exige confirmación explícita: un `IntentProposal` cambia la empresa activa y el usuario sigue trabajando sobre la equivocada. | §3.3, patch P-10 |
| 14 | Un fine-tune pierde calibración y se interpreta como confiable | **INSUFICIENTE** | El plan detecta el problema pero deja indefinida la «confianza externa» que lo sustituye (§27.1 L1437). Y la verificación de fuente primaria lo **agrava**: la confianza no es fiable en español ni siquiera en el modelo base. | **P-11**, §2.2 |
| 15 | Un límite de plan contradice una obligación de retención | **INSUFICIENTE** | El **principio** está bien resuelto (§20 precedencia; §34 L1679 «el histórico consultable es tiering, no retención»). Falta la aritmética: 10/50/200 GB divididos por el volumen incluido a lo largo del histórico prometido dan **55,6 / 23,8 / 33,3 KB por registro** — insuficiente para el mix documental que §34.2 promete (PDF escaneado con OCR). No está escrito quién paga cuando el tenant excede el tier hot y tiene legal hold. | §3.3, patch P-09 |

---

## 5. Controles ausentes, agrupados

**Producto.** Entidad de saldo y estado de conciliación como condición de cierre · control de completitud de ingesta · procedimiento de transferencia de empresa entre firmas · paquete de portabilidad propio, especificado y descargable en cualquier momento · modo degradado como experiencia con marcado del cierre afectado · definición operativa de «bajo riesgo» para resolución masiva · presupuesto de alertas por empresa y por día · evidencia mínima obligatoria antes de aprobar desde móvil.

**Arquitectura.** Enforcement del límite entre módulos (propiedad de tablas, linting de imports, prueba de arquitectura en CI) · propiedad única del reintento · `engine_release` en el snapshot de cierre · versión mínima de PostgreSQL y SLA de parcheo · `security_invoker` obligatorio en vistas · QoS, control de admisión y cuota por tenant en cola y pool de workers · conjunto de restauración con instante objetivo único entre almacenes · definición medible de «capacidad de celda».

**Seguridad.** Autenticación del canal de correo · control del plano de nube (CloudTrail con data events, política KMS que niega principales humanos, SCP, cero acceso permanente) · procedimiento de break-glass · encadenamiento de la auditoría (`seq` + `prev_hash`, GRANT sólo INSERT/SELECT, streaming continuo a WORM) · detección de PAN en el paso de aceptación, antes de `raw/` · control de destino en webhooks salientes · controles de SFTP · manejo de PDF cifrado · versión mínima de app móvil y kill switch por versión.

**Privacidad.** Registro de tombstones fuera de la unidad restaurable y reconciliación post-restore como criterio de éxito · procedimiento de derechos del titular (canal, verificación de identidad, plazos, enrutamiento Responsable/Encargado) · evento de inicio del reloj de retención anclado al último asiento, no a `created_at` · mecanismo de cambio de subencargado con preaviso y derecho de objeción · clasificación y finalidad declarada para las métricas de productividad individual · designación de qué marca temporal dispara el plazo de 15 días hábiles ante la SIC · incorporación de las Circulares SIC 001 y 002 de 2025 al mapa normativo.

**IA.** Fila de §24 para el redactor pre-egreso con nivel, umbral de recall y fallo cerrado · presupuesto duro de costo y objetivo de latencia por tenant · parámetros operables de shadow/canary/rollback · procedimiento de retirada de decisiones ya emitidas por una versión revertida · corrección por multiplicidad al evaluar decenas de slices · estratificación del slice por exposición financiera · definición de «plantilla exacta» · métrica de calidad de la revisión humana (tasa de corrección, tiempo por decisión, concordancia entre revisores) · métrica de **defecto escapado**, la única validación externa de los umbrales.

**Datos.** Clave idempotente canónica por cuenta · gestión de datos de referencia versionados (bancos, tarifas de retención, festivos, redondeo por moneda) · fecha contable distinta del instante UTC · fusión y división de contrapartes como evento con alias · notas crédito/débito modeladas · cota declarada para `N:M acotado` · proveedor y licencia de la TRM.

**Comercial.** Cuota y unidad facturable de OCR (`ocr_page_processed`) · dimensión de moneda y sensibilidad FX en el COGS · definición de si el bloque de overage es cargo único o eleva la base · mecanismo antiarbitraje entre Control+adicionales y Firma · programa de canal (figura jurídica, facturación, atribución, comisión y su efecto en el piso de margen) · reglas de downgrade cuando una firma con 10 empresas baja a un plan de 4 · facturación electrónica propia ante la DIAN · **nombre, marca, dominio y búsqueda de antecedentes marcarios** (Anexo A).

**Operación.** Rotación de guardia dimensionada y presupuestada · calendario de operación con hitos fiscales colombianos, usado para fechar pilotos, gates y ventanas de mantenimiento · pruebas de carga y de facturación en §30 · SLO de app móvil y de jobs asíncronos · dueño, fecha y gate para cada uno de los 16 artefactos de §41 · asignación nominal de los ocho roles de gobierno de §14.1 a personas del equipo de §39.

---

## 6. Decisiones que deben conservarse

Esta lista existe para evitar que una revisión con 154 hallazgos se lea como una invitación a reescribir. **No toquen esto:**

1. **La disciplina de evidencia como principio de producto** (§1.3.1-4, §12.1). «Toda cifra vuelve a su origen» y «el original nunca se altera» son la única barrera real contra un producto de conciliación que no se puede auditar. Es también la propiedad intelectual defendible.
2. **`Desconocido` como estado válido** (§1.3.3) y la abstención como salida legítima en toda la Parte V. Es lo que separa este diseño de un producto que inventa certeza.
3. **La jerarquía «la IA propone, las reglas validan, las personas certifican»** (§1.3.5) y la prohibición absoluta del nivel AI-4 (§23.1). Verificado: el marco elegido —Circular SIC 002/2024 como norma vinculante más NIST AI RMF como estándar— es correcto y suficiente para Colombia hoy; el CONPES 4144 es política, no norma.
4. **El AI Gateway como punto único de egreso con registro de política obligatorio** (§26), y en particular la regla de que un opt-in de interfaz no sustituye base jurídica. Es más estricto que lo que exige la norma y es correcto.
5. **La prohibición de LLM en confirmación de match y en cálculo de dinero** (§24). No negociable.
6. **`FORCE ROW LEVEL SECURITY` con aplicación no-owner, no-superuser, sin `BYPASSRLS`, `SET LOCAL` en transacción y prohibición de `SET` de sesión en conexiones pooled** (§10.3). Verificado contra la doc de PostgreSQL: la cita es exacta y el control es suficiente en su eje. Es de las páginas más maduras del plan.
7. **La FK compuesta `(workspace_id, company_id)`** (§10.3). Impide asociar una empresa a otra firma a nivel de base. (El coste es que hace falta un procedimiento de transferencia — §3.3 — pero el control es el correcto.)
8. **La reserva del modo compliance de Object Lock** «sólo cuando una obligación validada impida incluso el borrado administrativo» (§10.2 L736). Verificado: en modo compliance ninguna versión puede borrarse **ni siquiera por el usuario root**. La cautela del plan es exactamente la que evita una trampa irreversible.
9. **La zona `quarantine/` sin WORM y el orden aceptar → clasificar → asignar base de retención** (§10.2). Correcto y bien pensado.
10. **La tripleta `detected_at` / `aware_at` / `confirmed_at`** con prohibición de sustituirla por una fecha administrativa (§22). Verificado contra el concepto de la SIC: es exactamente lo que permite defender el cómputo de los 15 días hábiles. Mejor que la práctica habitual del mercado.
11. **La precedencia de retención** legal hold → obligación validada → instrucción del Responsable → configuración del plan (§20), y la declaración de que el histórico consultable es tiering y no retención (§34 L1679). Resuelve bien un conflicto que la mayoría de los SaaS resuelve mal.
12. **La separación de dominios de confianza** entre identidades de plataforma y de cliente, con grant JIT ligado a ticket, aprobador, propósito y expiración (§15.2). El mecanismo es correcto; lo que falta son las rutas que lo rodean (BL-05).
13. **El catálogo de enrutamiento desde el día uno con una sola celda** (§8.2). Esa indirección es barata ahora y carísima después. Decisión de arquitectura acertada.
14. **No empezar con Kubernetes ni con Kafka** (§13.5, §10.7). Verificado: Fargate llega a 16 vCPU/120 GB y 32 vCPU/244 GB, más que suficiente para el requisito de 1M filas. La decisión es correcta **por este requisito**, no sólo por prudencia.
15. **Los umbrales condicionados en general** (warehouse, OpenSearch, pgvector, Iceberg, Temporal). Cada uno tiene un disparador funcional o métrico, no una fecha. Es la mejor defensa contra el sobrediseño y funciona.
16. **La adopción de Temporal antes de Fase 2** (§11.1, §13.5). Verificado: el caso de uso —esperas humanas de días, timers, compensaciones— es exactamente el que Temporal resuelve, construirlo a mano costaría más, y el self-hosted queda descartado por la propia documentación del proveedor. Lo que falta presupuestar no es la licencia (USD 100–500/mes) sino el **determinismo** que impone al código.
17. **`source_record_published` como unidad única, con ledger inmutable y sin cobro por usuarios, reglas ni reruns** (§33, §35.1). El **concepto** es correcto y es una ventaja competitiva verificada: Odoo cobra por usuario, Synder incluye 1–2, Alegra 1–8, Siigo 1–5. En un cliente de seis personas la diferencia es material y hoy no está argumentada en ninguna parte del plan. Lo que hay que corregir es la **calibración** de las cuotas (MA-01), no la unidad.
18. **La regla de que la seguridad no depende del plan pagado** (§1.3.9) y la lista «todos incluyen» de §34. Es correcta y es defendible comercialmente. Sólo hay que hacerla verdadera moviendo la segregación a esa lista (MA-15).
19. **El red-team comercial de §37.4.** Es autocrítica genuina y anticipa varios de los riesgos reales (arbitraje de grupo empresarial, managed service accidental, dependencia de costo externo). Ampliarlo, no recortarlo.
20. **La decisión de dejar Needle 2 como POC condicionado, offline, no autoritativo, sin herramientas y fuera del data plane** (§27.1), junto con la distinción entre la licencia Apache-2.0 del modelo y la licencia distinta de Cactus Engine. Verificado: la distinción de licencias es correcta y la economía ilustrativa (USD 35–175/mes de costo cloud, break-even en 7–36M de interacciones) es **aritméticamente exacta**. El plan llega a la conclusión correcta —no adoptarlo como dependencia central— por el razonamiento correcto. Lo que cambia con la verificación es que el POC probablemente ya no valga la pena (P-11).

---

## 7. Propuesta de arquitectura revisada

No hay rediseño. La arquitectura objetivo se conserva; se añaden seis piezas y se corrigen dos fronteras.

```text
                        ┌─────────────────────────────────────────┐
  correo dedicado ─────►│ ① VERIFICACIÓN DE ORIGEN                │  ◄── NUEVO
  SFTP / API / móvil    │ SPF·DKIM·DMARC · allowlist por fuente   │
  carga web             │ estado origen_no_verificado             │
                        └──────────────────┬──────────────────────┘
                                           ▼
                        ┌─────────────────────────────────────────┐
                        │ ② ACEPTACIÓN                            │
                        │ firma/MIME · límites · antivirus        │
                        │ DETECCIÓN DE PAN/CREDENCIAL ◄── NUEVO   │
                        │ (antes de cualquier copia a raw/)       │
                        └──────────────────┬──────────────────────┘
                                           ▼
     quarantine/ ──► raw/ ──► extracted/ ──► curated/ ──► exports/
                                           │
                                           ▼
                        ┌─────────────────────────────────────────┐
                        │ ③ PUBLICACIÓN DE DATASET                │
                        │ receta versionada + engine_release ◄─NEW│
                        │ RECONCILIACIÓN DE COMPLETITUD ◄── NUEVO │
                        │ (totales del origen vs ingerido)        │
                        │ drift estructural + ESTADÍSTICO ◄── NEW │
                        └──────────────────┬──────────────────────┘
                                           ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ PLANO FINANCIERO — PostgreSQL, RLS FORCE, vistas security_invoker │
   │                                                                   │
   │  obligation · money_movement · settlement · ledger_entry           │
   │  counterparty · financial_account · external_reference             │
   │  ► account_balance          ◄── NUEVO                             │
   │  ► reconciliation_statement ◄── NUEVO                             │
   │  ► reference_dataset        ◄── NUEVO (bancos, tarifas, festivos) │
   │  match_group · exception · anomaly_signal                          │
   │                                                                   │
   │  clave canónica: company_id + financial_account_id + value_date    │
   │                 + amount + direction + normalized_reference ◄──NEW │
   │  → N evidencias de origen, UN money_movement, UN cobro            │
   │                                                                   │
   │  ► estadísticas de habilitación de auto-match  ◄── MOVIDO AQUÍ    │
   │    (son un control, no analítica: §9.4 deja de aplicarles)        │
   └────────────────────────┬──────────────────────────────────────────┘
                            │  cierre: exige diferencia explicada = 0
                            ▼
   closed_snapshot = datos + reglas + decisiones + archivos + informes
                   + cycle_config_version + engine_release  ◄── NUEVO

   ┌──────────────────────────────────────────────────────────────────┐
   │ CUENTA DE SEGURIDAD  (separada, append-only, Object Lock)        │
   │  ► delete_ledger / tombstones   ◄── NUEVO — fuera del restore    │
   │  ► audit chain: seq + prev_hash ◄── NUEVO                        │
   │  ► CloudTrail data events de S3 ◄── NUEVO                        │
   │  política KMS que NIEGA Decrypt a principales humanos ◄── NUEVO  │
   └──────────────────────────────────────────────────────────────────┘

   restore = base + objetos + manifiestos + workflows + secretos + KMS
           + REAPLICACIÓN DE TOMBSTONES  ◄── criterio de éxito, no tarea posterior
```

**Las dos fronteras que se corrigen:**

1. **Plano analítico vs control de automatización.** §9.4 dice que el plano analítico «nunca autoriza una acción». Las estadísticas por slice **sí** autorizan el auto-match. Se mueven al plano financiero con versionado y linaje, o §9.4 declara la excepción con garantías. No pueden quedarse ambiguas.

2. **Estado de job: control vs celda.** §9.1 pone «jobs, estados y programaciones» en el plano de control (global); §8.2 pone «colas/workflows y workers» dentro de la celda. Se divide: en **control** viven la programación y el derecho de ejecución (definición de ciclo, cron, entitlements, cuotas); en la **celda** vive el estado de ejecución. La vista de portafolio lee una proyección, no consulta cada celda en línea. Y el estado autoritativo del job es PostgreSQL: Redis sólo lleva el porcentaje de progreso, nunca una transición.

---

## 8. Revisión de planes y unit economics

### 8.1 Verificación de las cifras publicadas — todas correctas

Recalculé las tres tablas de §37.2. **La aritmética del plan es exacta**, incluido el escenario de diez meses que declara rechazado:

| | Esencial | Control | Firma |
|---|---:|---:|---:|
| COGS mensual | 29 | 74 | 201 |
| Margen mensual publicado / recalculado | 77,5% / **77,5%** | 78,8% / **78,8%** | 77,6% / **77,6%** |
| Margen anual publicado / recalculado | 75,5% / **75,5%** | 76,9% / **76,9%** | 75,6% / **75,6%** |
| Escenario 10 meses publicado / recalculado | 73,0% / **73,0%** | 74,6% / **74,6%** | 73,2% / **73,2%** |

Esto merece decirse con claridad: el modelo es internamente consistente y el escenario de diez meses fue correctamente rechazado. Los problemas están en los **supuestos**, no en las cuentas.

### 8.2 Los tres escenarios que el plan no calculó

**(a) Al 100% de utilización.** El escenario base asume 65%. Escalando las líneas variables (ingesta/matching e IA/OCR) por 1/0,65 y dejando fijos feeds y recaudo:

| | Esencial | Control | Firma |
|---|---:|---:|---:|
| COGS mensual al 100% | 32,2 | 82,6 | 220,4 |
| Margen mensual | 75,0% | 76,3% | 75,5% |
| **Margen anual (11 meses facturados, 12 de COGS)** | **72,7%** | **74,2%** | **73,3%** |

Los tres caen bajo el ≥75% que §34 exige para poder publicar la anualidad. Y hay **selección adversa**: el cliente que más se acerca a su límite es precisamente el que más valor obtiene y el más propenso a comprar anual.

**(b) Año 1 con el crédito del 100% del piloto.**

| | Caja año 1 | COGS año 1 | Margen |
|---|---:|---:|---:|
| Esencial | 1.419 | 496 | **65,0%** ← bajo el piso duro de 70% |
| Control | 3.839 | 1.036 | **73,0%** |
| Firma | 9.889 | 2.612 | **73,6%** |

**(c) Empresa adicional de Firma a $69.000.** COGS marginal 22,67 → margen **67,1%**, contra un piso de 70% y una regla de «margen incremental del overage ≥70%». Al 100% de utilización, 64,3%.

### 8.3 El ICP no cabe en los planes

Con el multiplicador que el propio §35.1 define (una venta en ERP + pasarela + banco = hasta 3 SRP):

| Plan | SRP por empresa | Movimientos económicos cubiertos |
|---|---:|---|
| Esencial | 5.000 | 1.700 – 2.500 |
| Control | 25.000 | 8.300 – 12.500 |
| Firma | 5.000 (50.000 ÷ 10) | 1.700 – 2.500 |

Contra un ICP declarado de **500 – 50.000 movimientos/mes**. Y el escalón de overage produce una escalera absurda:

| ICP | SRP (×2 / ×3) | Precio Control + overage | Relación con Firma |
|---|---|---:|---:|
| 10.000 mov | 20.000 / 30.000 | $349k / $408k | 0,39× / 0,45× |
| 25.000 mov | 50.000 / 75.000 | $526k / $644k | 0,59× / 0,72× |
| **50.000 mov** | 100.000 / 150.000 | **$821k / $1.116k** | 0,91× / **1,24×** |

Una sola empresa en el extremo alto del ICP paga más que diez empresas en Firma.

### 8.4 Arbitraje

- 4 empresas por Control + 3 adicionales = **$706.000/mes**; Firma (10 empresas) = **$899.000**. El punto de indiferencia sería 5,62 empresas, pero Control topa en 4 — así que el salto de 4 a 5 empresas cuesta $193.000 y trae 6 empresas de headroom gratis.
- Costo por empresa en Firma al máximo: **$89.900** vs Esencial **$129.000**. Diez PYMEs que se federen en una «firma» ahorran **30% cada una**. §37.4 lo advierte pero no da mecanismo.

### 8.5 Recomendaciones concretas

| # | Cambio | Estado |
|---|---|---|
| 1 | Reducir el ICP publicado al rango que los planes sirven (500–12.000 movimientos) hasta medir el multiplicador real | **Conclusión** — se sigue de la aritmética del propio plan |
| 2 | Subir la empresa adicional de Firma a $85.000–$89.000, o quitarle el feed incluido | **Conclusión** — el margen actual viola el piso propio |
| 3 | Limitar el crédito de piloto al 50%, o acreditarlo contra el segundo año, y añadirlo a la regla de no apilamiento de §37.4 | **Conclusión** |
| 4 | Mover la segregación de funciones a «todos incluyen» | **Conclusión** — se sigue de §1.3.9 y §15.4 |
| 5 | Publicar la anualidad sólo para el medio de pago que haga cierto el gate de recaudo ≤1% | **Conclusión** |
| 6 | Crear `ocr_page_processed` como segunda unidad medida y limitada, antes de GA | **Conclusión** — sin cuota, la regla de COGS de §35 es inejecutable |
| 7 | Rediseñar Firma como base + precio por empresa activa, en vez de bloque de 10 con recursos compartidos | **Hipótesis** — probar contra el ancla de Siigo contador ilimitado |
| 8 | Reposicionar contra el ancla real: no «más barato que Alegra» sino «lo que Alegra y Siigo no hacen» — multifuente, evidencia y cierre reproducible | **Hipótesis** — validar en las 25 entrevistas |
| 9 | Añadir a §37.2 columna de moneda por línea y fila de sensibilidad FX (±10%, ±25%) | **Conclusión** |
| 10 | Instrumentar antes de fijar: SRP y páginas OCR por tenant, horas de soporte por empresa activa, costo de feed por cuenta, multiplicador real SRP/movimiento | **Conclusión** — es el gate de toda la Parte VII |

**Experimentos previos a fijar precios públicos:** (a) medir el multiplicador SRP/movimiento en los ocho pilotos antes de publicar cualquier cuota; (b) prueba de dos anclas —precio por empresa activa vs precio por volumen— en mitades de la muestra de entrevistas; (c) presentar a cinco contadores el precio de Firma junto al de Siigo contador ilimitado y registrar la reacción sin defender; (d) Van Westendorp sólo como señal, como ya dice §37.

---

## 9. Roadmap corregido

Cambios respecto de §38. El horizonte total se mantiene en 15–18 meses; se redistribuye el esfuerzo y se adelantan tres gates.

| Fase | Cambio | Razón |
|---|---|---|
| **Fase −1 — DRG-00, semanas 0–3** | **Nueva.** Contrato de tratamiento con cada firma participante, finalidad única de corpus, ambiente aislado, retención declarada, borrado verificable, inventario nominal. Cierra **L-01** antes de tocar el primer documento. | BL-06: no se puede anonimizar sin recibir. Hoy Fase 0 viola DRG-01 en su primer entregable. |
| **Fase 0 — 3 meses (era 2), 18–22 PM (era 8–12)** | Seguridad/privacidad a dedicación completa. §41 se divide en bloqueantes de Fase 1 y de Fase 2. Se añaden como entregables: **tres cotizaciones firmadas de agregador con cobertura por banco**, **archivos reales de los cinco bancos del ICP** (para decidir §6.4 con evidencia y descubrir el problema del PDF cifrado), calendario de operación fiscal colombiano, y el ADR de stack A-01 cerrado. | MA-17, MA-07, MA-08, X-16. |
| **Fase 1 — 4 meses (meses 3–7), sin cambio de PM** | Se añaden como criterios de salida: prueba negativa de RLS **por cada vista de informes**, versión mínima de PostgreSQL fijada, `delete_ledger` fuera de la unidad restaurable **con reconciliación post-restore probada**, autenticación del canal de correo, control del plano de nube y break-glass documentado, detección de PAN en aceptación. **Pentest focalizado** (autenticación, autorización, multitenancy, carga de archivos) al cierre. | BL-01 a BL-06, BL-11, X-13: hoy el pentest está en Fase 5 y los datos reales entran en Fase 2. |
| **Fase 2 — meses 7–10** | Se añaden: `account_balance` y `reconciliation_statement` con la condición de cierre «diferencia explicada = 0»; clave idempotente canónica por cuenta; `engine_release` en el snapshot; reconciliación de completitud como precondición de `published`. El ingeniero móvil entra en el **mes 5**, no en el 7. | BL-07 a BL-10, MA-18, F-13. |
| **Fase 3 — meses 10–13** | El agregador entra sólo con las cotizaciones y el concepto jurídico de Fase 0 en mano. Si no hay proveedor con cobertura documentada, **la fase se ejecuta sin agregador** y el archivo queda como canal primario — lo que §1.3.8 ya dice. Pentest completo antes de abrir la fase. | MA-07. |
| **Fase 4 — meses 13–16** | **Se elimina el POC AI-EDGE-01 del camino crítico.** La verificación independiente lo dejó sin base: el binding React Native oficial está archivado, la confianza es inutilizable en español incluso en el modelo base, el corpus de 3.000 casos está subdimensionado ~2× y el propio plan cifra el ahorro en USD 28–140/mes. Se sustituye por intents deterministas locales más AI Gateway. Se reevalúa en 12 meses. | P-11, §2.2. |
| **Fase 5 — meses 16–18** | Sin cambios estructurales. Se añade la prueba de migración de tenant entre celdas y la de 50 empresas por firma, si §44.1 se mantiene. | MA-05. |

**Equipo.** Publicar la curva de FTE por mes junto a la tabla de persona-mes: hoy la incoherencia de Fase 1 (10,0–12,7 FTE requeridos contra 7,5 disponibles, con un pico declarado de 12) sólo es visible haciendo la división. Adelantar Platform/SRE e Integrations al mes 2.

**Capital.** §39.3 exige «caja comprometida hasta completar Fase 2 más 30%» sin dar **ninguna cifra absoluta**. Sin ella, «financiable» no es evaluable. Con el alcance corregido, Fases −1 a 2 suman ~85–105 persona-mes más nube, legal, proveedores, dispositivos y pentest. **Recomiendo publicar la cifra en COP y USD con la TRM de referencia y su fecha** — no la estimo yo porque los costos salariales que manejaría serían de segunda mano.

---

## 10. Preguntas pendientes

Ordenadas por impacto. Cada una bloquea una decisión concreta.

1. ¿Existe **algún** agregador con cobertura documentada de los bancos del ICP colombiano, a qué precio por cuenta/mes? *(Bloquea Fase 3, la fila de COGS más grande de Firma y el límite de feeds de los tres planes.)*
2. ¿Qué formatos exportan realmente los cinco bancos del ICP a clientes PYME, y sus PDF vienen cifrados? *(Bloquea §6.4, §44.4 y el diseño del importador. Se resuelve con cinco archivos reales.)*
3. ¿Cuál es el multiplicador real `source_record_published` / movimiento económico en los pilotos? *(Bloquea toda la Parte VII: sin él, las cuotas son arbitrarias.)*
4. ¿El comprador es la firma o la PYME? §3.1 marca la firma como «muy alta» pero §37.3 asigna 8 de 11 pilotos a empresas. *(Decide el wedge, la asignación de Fase 0 y el modelo de canal.)*
5. Frente a «Siigo contador ilimitado, $535.900/año, empresas ilimitadas» y al Espacio Contador gratuito de Alegra, ¿qué justifica $10,8M/año por Firma, en dinero recuperado o en horas ahorradas? *(Bloquea GA.)*
6. ¿Qué hace la plataforma cuando Simetrik aparece en un proceso competitivo? *(No hay respuesta en el plan porque el competidor no está en el plan.)*
7. ¿Cuál es la cifra absoluta de capital comprometido hasta Fase 2, más 30%? *(Sin ella no hay gate de contratación.)*
8. ¿Qué medio de pago hace cierto el gate de «recaudo anual ≤1%», y se restringe la anualidad a ese medio? *(Bloquea la publicación de precios anuales.)*
9. Región y proveedor: dado que **no existe región AWS en Colombia**, ¿São Paulo o Norte de Virginia, y con qué contrato de transmisión internacional? *(Bloquea ADR-018 y DRG-01.)*
10. ¿La empresa está obligada a revisor fiscal en el ICP, y hay que modelar al certificador externo? *(Requiere contador. Afecta §15.2 y el paquete de cierre.)*
11. ¿Quién es el dueño de las recetas, plantillas y reglas creadas por el cliente, y puede llevárselas? *(Requiere abogado. Afecta §4.1, §34.3 y el paquete de portabilidad.)*
12. En el modelo B2B2B: ¿la firma es revendedor, agente o referidor, quién factura a quién? *(Requiere abogado y contador. Efectos fiscales y de facturación electrónica.)*
13. ¿Cuál marca temporal —`detected_at` o `aware_at`— dispara el plazo de 15 días hábiles ante la SIC? *(Requiere abogado. Una línea en §22.)*
14. ¿Las Circulares SIC 001 y 002 de 2025 alcanzan a la plataforma? *(Requiere abogado. La 002/2025 toca directamente el fine-tuning de §27.)*
15. ¿Cuál es el alcance PCI resultante dado que los archivos aterrizan en `quarantine/` antes de detectar PAN? *(Requiere QSA o asesor. Bloquea DRG-01.)*
16. ¿A qué se compromete el producto cuando cae el proveedor de identidad? *(Bloquea el gate de Fase 1. Hoy no hay fila en §22.)*
17. ¿Cuánta evidencia hot consume realmente un registro según el mix documental? Las cuotas actuales dan 55,6 / 23,8 / 33,3 KB por registro. *(Bloquea la publicación de límites de almacenamiento.)*
18. ¿Se conserva §44.1 («50 empresas por firma») y, si sí, con qué precio y qué recursos? *(Hoy da 1.000 SRP y 0,12 feeds por empresa.)*
19. ¿Cómo se transfiere una empresa entre firmas cuando el cliente cambia de contador? *(Evento comercial frecuente, hoy estructuralmente imposible.)*
20. ¿Se mantiene el POC AI-EDGE-01 tras saber que el binding React Native oficial está archivado y que la confianza es inutilizable en español incluso en el modelo base? *(Recomiendo no. Ver P-11.)*

---

## 11. Patch recomendado

Cambios textuales listos para aplicar contra el hash `ee283d1e…3fc8`. Sólo se muestra lo que cambia.

**P-01 · §6.3, después de L288 (tabla de atributos de fuente) — NUEVO**

> **Autenticación del canal de correo.** Un buzón dedicado tiene parte local aleatoria de al menos 128 bits, no derivada del nombre de la empresa, rotable y revocable por el tenant. Todo mensaje entrante debe superar SPF, DKIM y alineación DMARC, y su dominio remitente debe estar en la allowlist de la fuente. Un mensaje que no supere estas verificaciones se acepta en cuarentena con estado `origen_no_verificado`: no autoenruta, no participa en auto-match, no crea `obligation` y requiere confirmación humana explícita con el remitente visible. La misma regla aplica al forwarding DIAN de §13.3.

**P-02 · §20, sustituir la frase de L1174 «Un tombstone impide que un restore reviva información eliminada»**

> El registro de supresiones (`delete_ledger`) vive **fuera de la unidad restaurable**: en la cuenta de seguridad, append-only con Object Lock, con `tombstone_id`, alcance (tenant, sujeto, tablas, claves de objeto, identificadores derivados), `deleted_at`, fundamento, solicitante y hash. Su retención excede la del backup más largo. **Todo restore ejecuta, como parte de su criterio de éxito y no como tarea posterior, la reaplicación de cada tombstone anterior al instante restaurado, con reconciliación verificable.** Un restore que no puede demostrar esa reaplicación no cuenta como restore exitoso.

**P-03 · §6.12, después de L541 «Envío programado» — NUEVO**

> Toda programación de informe y todo enlace compartido se revalidan **en cada ejecución y en cada acceso** contra la membresía y el conjunto de empresas vigentes del creador; el alcance se recalcula, nunca se congela. Una programación cuyo creador pierda acceso a cualquier empresa incluida se suspende y notifica. Los enlaces de solo lectura están ligados a identidad (destinatario nominado más autenticación o código de un solo uso), son revocables, registran cada acceso y tienen caducidad máxima declarada. Programaciones y enlaces activos entran en el offboarding y en la revisión trimestral de accesos de §14.1.

**P-04 · §10.3, añadir tras la viñeta de réplica de lectura (L753)**

> Toda vista, vista materializada y función que toque tablas tenant-owned se define con `security_invoker = true`; se prohíbe `SECURITY DEFINER` sobre el plano financiero salvo excepción aprobada con revisión de seguridad y prueba negativa. La réplica de lectura hereda las mismas políticas y roles que el primario. ADR-002 fija la versión mínima de PostgreSQL y el SLA de aplicación de parches de seguridad; los avisos del proyecto se revisan en cada release. Se añade a §30.3 una prueba de acceso cruzado por cada vista de informes.

**P-05 · §25, sustituir las viñetas de umbral (L1317-1319)**

> El auto-match se habilita por slice `source_pair + rule_lineage_id + case_type + banda_de_monto`, donde la banda se fija por percentiles de la distribución del tenant y cada banda acumula su propia evidencia. El criterio vinculante es el **límite inferior unilateral de Wilson al 95% ≥ 99,5%** sobre casos adjudicados de los últimos 90 días o tres ciclos. El mínimo de 1.000 adjudicaciones es un piso de tamaño muestral, **no una condición suficiente**: con cero errores el límite se alcanza en n ≈ 539, con un error en n ≈ 894, y un slice situado en la precisión mínima declarada de 99,8% requiere n ≈ 1.500. Un cambio de versión clasificado como cosmético o restrictivo —verificado reejecutando la nueva versión sobre el corpus adjudicado histórico— **hereda** la evidencia del linaje; uno expansivo la pierde sólo para los casos nuevos que habilita.

**P-06 · §10.7, sustituir la viñeta de `pgvector` (L809)**

> `pgvector` se admite para similitud de plantillas o conocimiento autorizado; los embeddings nunca son evidencia ni motor principal de matching. **La similitud vectorial, como la deduplicación por hash de §17, se limita al tenant.** Un índice compartido entre workspaces requiere aprobación del Comité de riesgo, DPIA y prueba de no-inferencia, y sólo puede construirse sobre rasgos de estructura desidentificados, nunca sobre contenido de documentos de clientes. Nota operativa: con índices aproximados el filtro se aplica **después** del recorrido del índice, de modo que una política RLS degrada el recall; los umbrales de recuperación deben medirse bajo RLS, no sin ella.

**P-07 · §10.4, sustituir la viñeta de namespace (L775)**

> Key namespace por ambiente, workspace, **sujeto** (`user_id` o `service_id`), **hash ordenado del conjunto de empresas autorizadas** y versión de grant del sujeto. Ninguna entrada derivada de datos company-scoped se comparte entre sujetos. El estado autoritativo de un job vive en PostgreSQL; la caché sólo lleva el porcentaje de progreso y nunca una transición de estado.

**P-08 · §22, ampliar la tabla «Comportamiento por componente» con las dependencias de §32**

| Componente | Pérdida tolerada | Degradación esperada |
|---|---|---|
| Proveedor de identidad | Ninguna | Sesiones vigentes siguen; **sin login nuevo**. Modo alterno documentado y probado; SEV-1 si supera 1 h en horario de cierre |
| KMS | Ninguna | Sin descifrado: lectura y escritura de evidencia detenidas. Ejercicio de indisponibilidad regional obligatorio |
| Workflow durable | No perder estado | Ciclos y esperas humanas en pausa; los timers se recuperan al restablecer |
| Object storage | Dentro del RPO | Carga rechazada con mensaje explícito; nunca confirmación optimista |
| Email / push | Hasta 4 h | Recordatorios y solicitudes en cola; el estado se muestra en la app |
| CDN / WAF | Ninguna | Origen protegido con límites propios; ruta de emergencia documentada |
| Antivirus | Ninguna | Cuarentena **no** se libera; los archivos esperan, no pasan |

**P-09 · §34, sustituir las filas «OCR» y «Evidencia hot»**

> `ocr_page_processed` es la segunda unidad medida y limitada, con cuota incluida por plan y bloque de overage publicado. El tier de evidencia hot se dimensiona a partir del supuesto declarado de KB por registro según mix documental, verificado con telemetría antes de publicarse. Exceder el tier hot **nunca** impide retener, exportar, auditar ni borrar: el excedente se factura como bloque o se degrada a archivo frío con latencia declarada, y la elección entre ambos es del cliente. Un tenant con legal hold vigente no puede degradarse a un tier que impida cumplirlo.

**P-10 · §27.1, añadir a la lista de «Casos excluidos» (L1420)**

> El **cambio de contexto de empresa** propuesto por un modelo nunca se aplica de forma inmediata: exige confirmación explícita del usuario mostrando razón social completa y NIT. Un cambio de empresa no es una mutación, pero produce el mismo daño que una, porque todo el trabajo posterior se ejecuta sobre el tenant equivocado. Además, el estado local cifrado se purga al cambiar de firma, no sólo al cerrar sesión o al revocar el dispositivo.

**P-11 · §27.1, sustituir la sección «Decisión» (L1387-1400)**

> **Needle 2 queda descartado como dependencia del producto y se retira del camino crítico del programa.** La verificación independiente del 21 de agosto de 2026 encontró cuatro hechos que la versión anterior de esta sección no tenía:
>
> 1. El binding oficial React Native (`cactus-compute/cactus-react-native`) está **archivado**, con último push el 19 de abril de 2026. §8.1 fija React Native como stack móvil: no existe camino de integración mantenido.
> 2. La confianza del modelo **no es utilizable en español ni siquiera en el modelo base**. La documentación del proveedor advierte: *«Non English deployments of the base model should also treat the score with caution (correct Spanish calls have been measured at confidence 0.0).»* El problema no se limita al fine-tuning, como se afirmaba.
> 3. El texto en español consume ~1,7× más tokens, de modo que la ventana efectiva es de ~150 tokens equivalentes, menos las definiciones de herramientas fijadas como KV sinks.
> 4. Existe una evaluación pública independiente en español (issue #61 del repositorio, 13 de agosto de 2026) que concluye que el fine-tuning mejoró la recuperación de herramienta pero no proporcionalmente la exactitud de argumentos. La afirmación de que «no existe validación independiente» era incorrecta.
>
> Sumado a que el propio plan cifra el ahorro en USD 28–140 al mes y el break-even en 7–36 millones de interacciones mensuales, el POC de 4–6 semanas con corpus de 3.000 casos gold no se justifica. **Se conservan intents deterministas locales, OCR nativo de plataforma (Apple Vision y ML Kit) y AI Gateway.** ADR-021 se reescribe como «broker de capacidades móvil y prohibición de side effects desde modelos edge», sin nombrar proveedor. La decisión se reevalúa en 12 meses o cuando exista un binding mantenido para el stack elegido, lo que ocurra primero.

**P-12 · §34 L1673 y L1679 — corregir el reparto de la segregación**

> Fila «Gobierno»: Esencial «Evidencia, auditoría, roles base **y segregación de funciones**» · Control «**Roles personalizados** y API» · Firma «Roles firma/cliente, carga de equipo y matriz multiempresa».
> Lista «Todos incluyen», añadir tras «auditoría esencial»: «**segregación de funciones con registro `autocertificada_sin_revision_independiente` cuando no exista revisión independiente**».

**P-13 · §12.3, añadir sexta clave**

> - **Movimiento canónico:** `company_id + financial_account_id + value_date + amount + direction + normalized_reference`. Una transacción económica admite N evidencias de origen y exactamente **un** `money_movement`; las evidencias adicionales se enlazan como `external_reference`, no se republican y no vuelven a facturar. Al crear una conexión, el sistema detecta y advierte si la cuenta ya está siendo ingerida por otra fuente.

**P-14 · §13.2, añadir obligación 13 al contrato de conector**

> - **Reconciliación de completitud.** Por fuente y periodo se registran los totales declarados por el origen —número de movimientos, suma de débitos y créditos, saldo inicial y final— y se comparan contra lo ingerido. Un `DatasetVersion` **no puede pasar a `published`** con discrepancia no explicada; una excepción exige motivo, aprobador y registro. Para fuentes de archivo se usan los totales de control que §6.5 ya captura.

**P-15 · §12.2, añadir a la lista de objetos versionados**

> - Release del motor (`engine_release`: semver más SHA-256 del artefacto) y `canonical_schema_version`, presentes en `DatasetVersion`, `MatchRun`, informe y `closed_snapshot`. Cada release se clasifica como «neutral» o «afecta resultados»; las segundas exigen simulación sobre el corpus adjudicado y anotación en los periodos afectados. Nuevo ADR-022.

**P-16 · §14.2, añadir al mapa normativo**

> - Circular Externa SIC **001 de 2025** (18 de septiembre de 2025): explicación clara y comprensible de toda decisión automatizada desfavorable, para vigilados por la SIC en servicios financieros y fintech.
> - Circular Externa SIC **002 de 2025**: transferencia de datasets y de tecnología que trate datos personales. Alcanza a §27 (corpus, fine-tuning) y a §21.1 (proveedores de OCR e IA).
> - Resolución DIAN **000165 de 2023**: la plataforma está obligada a expedir factura electrónica por sus propias suscripciones. Añadir «facturación electrónica propia» a la lista «Comprar» de §32.
> - Precisión sobre el **Decreto 0368 del 7 de abril de 2026**: establece el Sistema de Finanzas Abiertas obligatorio, pero la obligación recae únicamente sobre entidades vigiladas por la SFC. Una plataforma no vigilada es «Tercero Receptor de Datos No Vigilado» y accede sólo por esquemas voluntarios, sin inscripción obligatoria. Finanzas abiertas **no** es una vía de acceso automática.
> - Precisión sobre §20 L1153: **transmisión** (a un encargado en el exterior, que es este caso) y **transferencia** son figuras distintas con requisitos distintos; la transmisión no exige consentimiento del titular si existe contrato de transmisión con las cláusulas exigidas.
> - Precisión sobre §22: designar `aware_at` como la marca que dispara el plazo de quince días hábiles ante la SIC.
> - Precisión sobre §20: el reloj de retención de soportes contables se ancla a la fecha del último asiento, documento o comprobante (Ley 962 de 2005, art. 28), **no** a la fecha de carga del archivo.

**P-17 · §36, reescribir la sección completa como tabla con fecha y fuente**

> | Competidor | Precio vigente | Moneda | Unidad de cobro | Feeds bancarios | Consultado |
> |---|---|---|---|---|---|
> | Siigo contador | Gratis (1 empresa) | COP | Por contador | — | 2026-08-21 |
> | Siigo contador ilimitado | $44.658/mes · $535.900/año | COP | **Empresas ilimitadas** | — | 2026-08-21 |
> | Alegra Contabilidad | $74.900–$319.900/mes lista; $56.175–$239.925/mes con pago anual | COP | Por empresa, **segmentado por ingresos del cliente** | – / 1 / 3 / 5 | 2026-08-21 |
> | Alegra Espacio Contador | Gratis | COP | Por contador | — | 2026-08-21 |
> | Dext Practice | Desde US$17,70/cliente/mes (mín. 10 clientes) | USD | **Por cliente** | — | 2026-08-21 |
> | Odoo | US$7,90–13,60/usuario/mes; multiempresa y API sólo en Custom | USD | Por usuario | Sin proveedor LatAm | 2026-08-21 |
> | Cointab | US$149–749/mes | USD | Fuentes y filas por archivo | — | 2026-08-21 |
> | Synder | US$65–599/mes | USD | Transacciones sincronizadas/mes | — | 2026-08-21 |
> | **Simetrik** | No público | — | Conciliación empresarial, colombiana, Serie B US$55M + B1 US$30M | — | 2026-08-21 |
>
> TRM de referencia: declarar valor y fecha. Añadir Simetrik y Dext a §37.4 y a §45 como riesgo competitivo nombrado.

**P-18 · §0.2, corregir el registro de decisiones**

> Normalizar el estado de C-01 a `Pendiente` (hoy usa «Hipótesis», un quinto estado no definido en L84). Añadir **DRG-00** con dueño Legal/Security/Product y fecha límite anterior a Fase 0. Corregir la fecha de **L-01** a «antes de DRG-00», ya que §20 L1176 declara que L-01 bloquea DRG-01. Añadir una fila por cada una de las siete decisiones que §0.1 pide desafiar, con dueño, evidencia requerida, fecha límite y gate afectado. Añadir además:
>
> | ID | Decisión | Estado | Dueño | Evidencia | Fecha límite | Gate afectado |
> |---|---|---|---|---|---|---|
> | M-01 | Nombre, marca y dominio | Propuesto | Product/Legal | Búsqueda de antecedentes SIC clases 9 y 42 + disponibilidad de dominio | Antes del primer contrato de piloto | Construcción |

**P-19 · §41, añadir a los artefactos obligatorios**

> - **Identidad de marca:** nombre decidido, símbolo y sistema mínimo (color, tipografía, uso en monocromo e invertido), dominio asegurado y búsqueda de antecedentes marcarios ante la SIC en clases 9 y 42. El nombre entra en el DPA, en los términos, en los contratos de piloto de §37.1 y en la interfaz; el registro marcario tiene plazo de trámite propio y debe iniciarse en Fase 0. El **símbolo puede decidirse antes que el nombre** —ver Anexo A— de modo que el diseño no quede bloqueado por el resultado de la búsqueda.

---

## Anexo A — Nombre, marca y posicionamiento

Este anexo no formaba parte del encargo original. Lo añado porque la revisión encontró un vacío que ninguna de las once secciones cubría (**MA-21**) y porque la respuesta se deriva directamente de la evidencia competitiva ya verificada en §2.3, no de una opinión estética independiente.

### A.1 El hueco de posicionamiento, deducido de la evidencia verificada

Los precios y marcas que verifiqué el 21 de agosto de 2026 delimitan tres territorios, y dos ya tienen dueño:

| Territorio | Quién lo ocupa | Cómo suena |
|---|---|---|
| Suite contable cálida y cercana | Alegra, Siigo, Loggro | Nombres amables, prometen facilidad |
| Conciliación empresarial abstracta | Simetrik (Serie B US$55M, Goldman Sachs AM), Conciliac, Cointab | Sufijos `-ik`, `-ac`, `-tab`; prometen escala |
| **Instrumento de precisión** | **Vacío** | Promete exactitud demostrable |

El tercero es el único coherente con los principios de §1.3: evidencia obligatoria, ausencia de caja negra, neutralidad. Un nombre que suene a suite te mete en la comparación que pierdes —«un ERP más caro»—; uno que suene a Simetrik te mete en una pelea de capital que no puedes financiar. El producto no es amable ni corporativo: es **exacto**, y el nombre debería decirlo.

### A.2 Los tres candidatos

| | Qué dice en español | Qué lee un angloparlante | Eslogan principal |
|---|---|---|---|
| **Cotejo** | *Cotejar* = confrontar una copia contra su original | Nada directo | **«Cada cifra, contra su origen.»** |
| **Empata** | Verbo imperativo: *haz que cuadre*. «Empatar cuentas» | «=» se lee en cualquier idioma | **«Nada queda suelto.»** |
| **Fincilia** | Acuñado: *fin*anzas + con*cilia* | Neutro | **«Concilia. Cierra. Comprueba.»** |

Eslogan transversal, que sirve bajo cualquiera de los tres y ataca directamente el hueco de **MA-06**: **«Conciliar es fácil. Probarlo, no.»** Es la única línea que te separa de Alegra y Siigo sin nombrarlos.

Sobre el requisito bilingüe: conviene un **cognado**, no un anglicismo. Un anglicismo (*Ledger*, *Match*, *Proof*) es extranjero en español y genérico en inglés — pierde por los dos lados. Y el ccTLD de Colombia es `.co`, que globalmente se lee como dominio de startup: una palabra española más `.co` da marca local y legibilidad internacional en el mismo activo.

### A.3 Cómo cada elemento de la marca traduce una decisión del plan

Esta es la parte que importa: las marcas no son decoración, son las decisiones del documento hechas visibles.

| Elemento | Decisión del plan que traduce |
|---|---|
| **El acento sobre la zona de coincidencia** (los tres) | §6.8 estados de match y §6.11 «dinero sin explicar». El color de marca es el mismo que la interfaz usa para *conciliado*: marca y producto hablan el mismo vocabulario de estado. |
| **Cotejo — dos documentos superpuestos** | §6.5 Estudio de Importación: las vistas «Original» y «Extracción fiel» puestas una contra otra. Es la pantalla principal del producto convertida en símbolo. |
| **Cotejo — la franja compartida en acento** | §1.3.1 «Toda cifra vuelve a su origen» y §12.1 localizador de origen. El acento no adorna: marca el único sitio donde vive la verdad. |
| **Empata — el signo igual** | **BL-09**, la entidad que el plan no modela: `saldo extracto ± partidas conciliatorias = saldo libros`. El símbolo dibuja exactamente el artefacto que la revisión encontró ausente. |
| **Empata — dos barras de distinta procedencia, mismo largo** | §35.1 («una misma venta en ERP, pasarela y banco genera hasta tres `source_record_published`») y **BL-07** (N evidencias de origen, **un** `money_movement`). N fuentes, un valor. |
| **Fincilia — el igual colgado del asta de la F** | Hace visible la raíz «concilia» que el nombre entierra. También expone su debilidad: un nombre acuñado no significa nada, así que el símbolo carga todo el peso. |
| **Latón sobre gris-verde de papel contable** | Rechaza deliberadamente el azul fintech (territorio Simetrik) y el verde cálido de suite (territorio Alegra/Siigo), ambos verificados como ocupados en §2.3. El latón es el fiel de la balanza y el sello: instrumento y registro. |
| **«Suena a instrumento, no a app»** | §1.3.4 «la automatización debe mostrar evidencia; no hay decisiones importantes de caja negra» y §1.3.10 neutralidad. |

### A.4 Riesgos por nombre

- **Cotejo** — sin lectura en inglés; el eslogan tiene que traducirla. A cambio es el más distintivo y por tanto el más fácil de registrar.
- **Empata** — «empate» arrastra el sentido deportivo de *nadie ganó*, y en registro coloquial colombiano puede tener lecturas que conviene descartar antes de invertir. Usar el verbo en imperativo resuelve la mitad; la otra mitad se prueba en una tarde con diez contadores, escuchando la **primera** reacción.
- **Fincilia** — «fin-» es el prefijo más saturado de la categoría y en Colombia arrastra la asociación con *finca*. Aunque entierra «concilia», la raíz sigue ahí y Conciliac opera en la misma categoría. A favor: por acuñado, el más limpio de registrar.

### A.5 Recomendación

**Cotejo.** Nombra el acto central del producto, nadie lo ocupa, y ocupa el único territorio libre. Un contador —que es el comprador prioritario según §3.1— lo entiende sin explicación.

Pero el hallazgo operativo del ejercicio es otro, y es el que reduce el riesgo de **M-01**: **el mejor símbolo no pertenece al mejor nombre.** Los tres marcos salen del mismo gesto —dos cosas puestas de acuerdo— y el signo igual de Empata funciona bajo cualquiera de los tres. Eso permite **cerrar el diseño en Fase 0 sin esperar el resultado de la búsqueda marcaria**, y desacopla la única decisión de marca con plazo legal largo del resto del trabajo.

Marcas, eslóganes y pruebas a 16 px, invertido y monocromo: <https://claude.ai/code/artifact/89445026-b398-486e-9b1d-d2dc33edc65b>

---

## Criterio de éxito de esta revisión — autoevaluación

| Criterio del encargo | Estado |
|---|---|
| Cero bloqueadores ambiguos | ✅ 12 bloqueadores, cada uno con cadena concreta, cambio redactado, responsable y gate |
| Dueño y gate para cada cambio crítico | ✅ En §3.1 y §3.2 |
| Arquitectura sin fuentes de verdad contradictorias | ✅ Dos fronteras corregidas en §7; el resto se conserva |
| Límites de IA inequívocos | ⚠️ Los de §24-§26 sí; §27.1 requiere P-11 para dejar de ser ambiguo |
| Seguridad básica en todos los planes | ⚠️ Requiere P-12: hoy la segregación se vende sólo en Control |
| Pricing marcado como validado o hipótesis | ✅ §8.5 separa conclusión de hipótesis fila por fila |
| Ruta de construcción completa y financiable | ⚠️ Completa en §9; **no financiable de forma evaluable** hasta publicar la cifra de capital (pregunta 7) |
| Lista clara de decisiones que requieren evidencia | ✅ §10, veinte preguntas |
| Tres veredictos de gate independientes y coherentes con DRG-01 | ✅ §1.1 |
| Hash/versión revisados y matriz de evidencia trazable | ✅ §0 y §2, con URL y fecha por fila |

---

*Revisión emitida contra `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` SHA-256 `ee283d1e951d6739005a92b8bbb3ce05b41a128ba2fab8a9b698bf9a74b53fc8`. Consultas web del 21 de agosto de 2026. Esta revisión no reemplaza concepto jurídico, dictamen contable, threat model por componente ni evaluación de un QSA.*
