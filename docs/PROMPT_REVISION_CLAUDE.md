# Encargo de revisión independiente para Claude

## Contexto

Debes revisar la versión congelada `1.0-rc1` del documento `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` como arquitecto principal, responsable de seguridad, líder de producto financiero y crítico comercial independiente.

La plataforma propuesta es un SaaS multitenant para firmas contables y PYMEs. Recibe archivos y datos financieros, conserva evidencia, limpia y normaliza, concilia, coordina cierres, produce informes y genera señales de riesgo. Incluye web y app móvil.

La revisión debe evaluar la arquitectura objetivo completa, no reducir el producto a un MVP. Sí debes cuestionar el orden de implementación, el costo y cualquier sobrediseño.

## Reglas de revisión

1. Antes de revisar, registra nombre, versión interna, fecha de corte y SHA-256 del archivo recibido. Lee el plan completo antes de emitir el veredicto.
2. No asumas que una afirmación es correcta porque está escrita con seguridad.
3. Diferencia hechos, inferencias, hipótesis y decisiones pendientes.
4. Verifica en fuentes primarias cualquier afirmación técnica, normativa o de precio que pueda haber cambiado.
5. No inventes cobertura de bancos, APIs, certificaciones, costos ni obligaciones legales.
6. Señala cuando una decisión requiere abogado, contador, responsable de seguridad o experimento con clientes.
7. Evalúa la visión completa y la ruta incremental por separado.
8. Prefiere recomendaciones concretas y verificables a frases generales.
9. Conserva los principios de evidencia, reversibilidad, neutralidad y segregación salvo que demuestres por qué deben cambiarse.
10. Si propones una tecnología distinta, compara costo total, operación, seguridad, lock-in y umbral de migración.
11. No edites silenciosamente el archivo original: entrega hallazgos y patch reproducible contra el hash revisado.
12. Para cada afirmación material, indica si es hecho verificado, inferencia, hipótesis o decisión; incluye fuente primaria y fecha de consulta cuando corresponda.

## Áreas obligatorias

### A. Producto y mercado

- ¿El problema, ICP y comprador están correctamente delimitados?
- ¿La combinación de importador, conciliación, cierre y riesgo sigue siendo coherente o demasiado amplia?
- ¿La propuesta es suficientemente distinta de Alegra, Siigo, Odoo, Cointab, Synder y Dext?
- ¿Qué flujo debe ser el wedge inicial sin mutilar la visión completa?
- ¿Qué módulos sobran, faltan o deben cambiar de orden?

### B. Arquitectura

- Revisa límites de módulos, acoplamiento y consistencia del monolito modular + workers.
- Revisa control plane, data plane, file plane, analytics plane y AI Gateway.
- Evalúa PostgreSQL, object storage, Redis/Valkey, DuckDB/Polars, Parquet y warehouse condicionado.
- Busca dos bases haciendo el mismo trabajo o una fuente de verdad ambigua.
- Revisa idempotencia, outbox, lineage, versionado y snapshots.
- Determina si los umbrales para adoptar warehouse, Temporal, OpenSearch o pgvector son razonables.
- Evalúa costos, disponibilidad, recuperación y dependencia de proveedores.

### C. Seguridad, roles y privacidad

- Intenta encontrar acceso cruzado entre firmas o empresas.
- Busca escalamiento de privilegios, BOLA/IDOR, roles incompatibles y admins con acceso implícito.
- Valida RBAC + ABAC, RLS, object IAM, scopes de workers, caché y analítica.
- Revisa preparador/revisor, cambios de reglas, cierre/reapertura y exportación.
- Revisa acceso del personal de soporte y break-glass.
- Evalúa uploads maliciosos, ZIP/CSV bombs, macros, XXE, SSRF y ransomware.
- Revisa cifrado, KMS, secretos, rotación, logs, audit WORM y supply chain.
- Revisa privacidad por diseño, roles Responsable/Encargado, transmisión internacional, retención, borrado, backups y subencargados.
- Distingue controles obligatorios de certificaciones opcionales.

### D. Inteligencia artificial

- Verifica que cada uso de IA tenga necesidad, riesgo, datos mínimos, evaluación, fallback y dueño.
- Detecta decisiones críticas indebidamente delegadas a modelos.
- Revisa umbrales de clasificación, mapping y auto-match.
- Revisa prompt injection desde archivos, data exfiltration, RAG multitenant y tool abuse.
- Evalúa el AI Gateway, model registry, prompts versionados, shadow/canary/rollback y kill switch.
- Revisa si reglas, ML clásico, OCR y LLM se usan en el lugar correcto.
- Exige métricas por slice, calibración, abstención y revisión humana real.
- Audita la decisión AI-EDGE-01: Needle 2, OCR nativo, adapter móvil, licencias, supply chain, batería, fallback y prohibición de side effects.
- Verifica de forma independiente las cifras/licencias vigentes de Needle y Cactus; no confundas el modelo Apache-2.0 con Cactus Engine.
- Determina si los gates del POC móvil prueban calidad semántica, no solo JSON válido, y si los modelos de sistema fragmentan injustificadamente iOS/Android.

### E. Datos y conciliación

- Revisa modelo canónico, dinero/moneda/tiempo, IDs y cuentas.
- Valida 1:1, 1:N, N:1, parciales, net settlements, fees, retenciones, refunds y reversos.
- Busca riesgos de deduplicar transacciones legítimas idénticas.
- Revisa trazabilidad por campo y reproducción de cierres.
- Revisa separación entre original, extracción, dataset limpio, normalizado y decisión.

### F. App, UX y operación

- Valida que web y móvil tengan responsabilidades correctas.
- Revisa fatiga de alertas, ambigüedad y confianza excesiva en automatización.
- Revisa accesibilidad, localización, soporte, onboarding y operación multiempresa.
- Revisa SLO, observabilidad, incidentes, restore, DR y modo degradado.

### G. Pricing y economía

- Revisa solo tres planes: Esencial, Control y Firma.
- Evalúa si empresas, movimientos, fuentes, OCR, almacenamiento y usuarios son límites entendibles.
- Revisa el precio de referencia frente a competidores y valor generado.
- Detecta incentivos perversos en metering u overage.
- Evalúa si COGS, margen, onboarding, conectores y soporte son sostenibles.
- Recalcula margen mensual y anual después de descuentos/recaudo, y prueba feeds al máximo de 1/2/6.
- Verifica que `source_record_published` signifique exactamente lo mismo en producto, contrato, ledger, overage y factura.
- Propón experimentos antes de fijar precios públicos.

### H. Programa de construcción

- Revisa dependencias, gates y duración de 15–18 meses.
- Evalúa equipo y persona-meses.
- Señala qué debe existir antes de aceptar datos reales, pilotos, IA y conectividad bancaria.
- Busca trabajo crítico sin dueño, criterio de salida o artefacto.
- Identifica elementos que se pueden comprar y los que constituyen propiedad intelectual.

## Ataques conceptuales obligatorios

Intenta demostrar al menos una forma en que podría ocurrir cada caso:

1. Un contador ve la empresa equivocada.
2. Una exportación incluye datos no autorizados.
3. Un archivo manipula al sistema o a un modelo.
4. Una receta antigua se aplica a un formato cambiado.
5. Un match de alta confianza es incorrecto.
6. Un usuario prepara y aprueba mediante combinación de roles.
7. Soporte accede a un documento sin permiso.
8. Un borrado se revierte al restaurar un backup.
9. Un embedding o índice filtra información de otra empresa.
10. Un costo de OCR/IA vuelve no rentable un plan.
11. Una caída de proveedor impide cerrar.
12. Una integración duplicada crea movimientos dobles.
13. Un modelo local selecciona la empresa equivocada o ejecuta una mutación sin autorización server-side.
14. Un fine-tune de Needle pierde calibración y la aplicación interpreta su salida como confiable.
15. Un límite de histórico/almacenamiento del plan contradice una obligación de retención o borrado.

Para cada uno indica si el plan ya lo controla, si el control es insuficiente o si falta.

## Formato de respuesta requerido

### 1. Veredicto ejecutivo

- Emite **tres veredictos separados**: `CONSTRUCCIÓN SIGNIFICATIVA`, `PILOTO CON DATOS REALES` y `GA/VENTA GENERAL`.
- Para cada uno usa `SÍ`, `SÍ CON CONDICIONES` o `NO`, y enumera condiciones/gates pendientes.
- Añade un veredicto global: `APROBABLE`, `APROBABLE CON CAMBIOS MAYORES` o `NO APROBABLE AÚN`.
- Cinco razones concretas.

### 2. Matriz de evidencia

| Afirmación/decisión | Tipo: hecho/inferencia/hipótesis | Fuente primaria | Fecha consultada | Resultado | Impacto en el plan |
|---|---|---|---|---|---|

Incluye como mínimo: regulación/privacidad, conectividad bancaria, licencias Needle/Cactus, benchmarks edge, stack/versiones, retención, competidores/precios y unit economics.

### 3. Tabla de hallazgos

| ID | Severidad | Sección | Hallazgo | Evidencia/razón | Cambio propuesto | Responsable | Gate |
|---|---|---|---|---|---|---|---|

Severidades:

- **Bloqueador:** no comenzar construcción significativa o no aceptar datos reales.
- **Mayor:** puede provocar reproceso, incidente, pérdida financiera o modelo inviable.
- **Medio:** afecta calidad, costo, operación o claridad.
- **Menor:** mejora deseable sin cambiar la viabilidad.

### 4. Contradicciones y supuestos ocultos

Lista numerada con referencias precisas a secciones.

### 5. Controles ausentes

Agrupa por producto, arquitectura, seguridad, privacidad, IA, datos, comercial y operación.

### 6. Decisiones que deben conservarse

Indica qué decisiones son sólidas y por qué, para evitar una reescritura innecesaria.

### 7. Propuesta de arquitectura revisada

Entrega un diagrama lógico y los cambios mínimos necesarios. No rediseñes todo si no hace falta.

### 8. Revisión de planes y unit economics

Propón cambios concretos en límites, métricas, precio o validación. Separa hipótesis de conclusiones.

### 9. Roadmap corregido

Muestra fases, dependencias, gates, equipo y duración revisados.

### 10. Preguntas pendientes

Máximo 20 preguntas, ordenadas por impacto.

### 11. Patch recomendado

Entrega cambios textuales listos para aplicar al plan, identificando sección de destino. No es necesario repetir lo que no cambia.

## Criterio de éxito de la revisión

La revisión es útil si deja:

- Cero bloqueadores ambiguos.
- Dueño y gate para cada cambio crítico.
- Arquitectura sin fuentes de verdad contradictorias.
- Límites de IA inequívocos.
- Seguridad básica en todos los planes.
- Pricing marcado como validado o hipótesis.
- Ruta de construcción completa y financiable.
- Lista clara de decisiones que todavía requieren evidencia.
- Tres veredictos de gate independientes y coherentes con DRG-01.
- Hash/versión revisados y matriz de evidencia trazable.
