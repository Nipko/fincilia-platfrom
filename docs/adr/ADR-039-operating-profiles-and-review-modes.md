# ADR-039 — perfiles operativos, modos de revisión y reglas aprobadas

- Estado: **Accepted por FOUNDER-01 (FNC-PRD-002); revisión independiente Accounting/Security/Database pendiente**
- Fecha: 2026-11-04
- Tareas: FNC-SMB-001..006
- Owners: Product + Accounting + Security, accountable FOUNDER-01
- Gates: S1-READY. No relaja DRG-00, DRG-01 ni GA-01; sigue rigiendo `synthetic_only`.

## Contexto

La SoD de dos personas está forzada por triggers en cruces, overrides,
correcciones, statements de saldo, expediente y cierre. Es correcta para una
firma contable, pero una pyme de una o dos personas no puede operar. Quitar SoD
violaría los invariantes; fingir una segunda persona sería peor. Se necesita que
el sistema permita operar solo **y diga honestamente** que no hubo revisión
independiente.

## Decisión

### 1. Perfil operativo por empresa

- `fincilia.company.operating_profile` ∈ {`simple`, `estricto`}, no nulo.
- Empresas existentes quedan en `estricto` (valor seguro). Una empresa nueva
  elige en el alta con una sola pregunta: «¿Cuántas personas revisan las
  finanzas?» (1–2 → `simple`; 3 o más → `estricto`, sugerido y editable).
- Solo el owner de la empresa cambia el perfil; cada cambio es una fila
  append-only con actor, motivo y fecha, más un evento de auditoría. El cambio
  no reescribe decisiones previas.
- La autorización se resuelve server-side desde la base; el cliente nunca envía
  el perfil para decidir.

### 2. Modo de revisión en cada decisión

Toda decisión financiera humana registra `review_mode`:

| Modo | Cuándo | Efecto |
|---|---|---|
| `independent` | quien decide es distinto de quien propuso | igual que hoy |
| `self_reviewed` | misma persona, solo permitido en perfil `simple` | válido para operar; visible como «autorrevisado» |
| `approved_rule` | confirmación aplicada por una regla aprobada por una persona | ver §4 |

En perfil `estricto` el trigger sigue rechazando la autoconfirmación. En perfil
`simple` la acepta y fija `self_reviewed`; nunca se infiere `independent` si el
actor coincide.

### 3. Cierre del dueño y certificación posterior

- En `simple`, el owner puede preparar, revisar y cerrar el periodo solo. El
  cierre queda con `certification = 'self_reviewed'`.
- Pasa a `certified` solo cuando un segundo usuario elegible (típicamente el
  contador vía engagement) registra una revisión independiente del mismo
  snapshot. La certificación es una fila nueva; no muta el cierre.
- En `estricto` el cierre exige revisor independiente y nace `certified`, como
  hoy (ADR-035).
- Informes y exportaciones muestran la certificación. `partial`, `unknown` y
  `unverified` siguen bloqueando cualquier cierre.

### 4. Cruce con tolerancias y reglas aprobadas

- El generador de candidatos agrega señales deterministas además de las
  exactas: diferencia de monto dentro de una tolerancia explícita (valor
  absoluto o porcentaje, decimal exacto), coincidencia de NIT/identificador del
  pagador, referencia contenida y referencia de pago Bre-B. Cada candidato trae
  una explicación en lenguaje llano compuesta de esas señales. No hay puntaje
  opaco ni LLM.
- Monto, fecha y referencia siguen generando **candidatos**, nunca unicidad
  dura. Una diferencia de monto queda visible como partida a explicar.
- Una **regla de conciliación** se crea desde una decisión humana
  («¿aplicar siempre?») y describe condiciones deterministas (patrón de
  descripción/contraparte, cuenta, signo, tolerancia). Nace `proposed`.
  - `simple`: el owner la aprueba en el mismo paso (`self_reviewed`).
  - `estricto`: la aprueba otra persona.
- Una regla `active` confirma automáticamente los candidatos que cumplen todas
  sus condiciones **y** cuyas fuentes están `verified` o `accepted_exception`.
  La decisión queda con `review_mode = 'approved_rule'`, `rule_id`,
  `rule_version` y `decided_by` = quien aprobó la regla. Toda aplicación es
  reversible por una decisión posterior y aparece en la bandeja.
- Pausar o retirar una regla no borra decisiones; las nuevas dejan de aplicarse.
- Esto no es auto-match libre: ningún sistema decide sin una regla que una
  persona aprobó, y un LLM nunca crea, aprueba ni aplica reglas.

### 5. Fuentes para pymes

- Facturas electrónicas DIAN (UBL 2.1 `Invoice` y `AttachedDocument`) se leen
  como contraparte del extracto para responder «quién me pagó / qué me falta
  cobrar». Sigue vigente que el buzón DIAN de documentos recibidos no sustituye
  facturas emitidas: la fuente emitida es el XML que la empresa exporta.
- Plantillas por banco detectan columnas de exportaciones conocidas y evitan el
  mapeo manual. Las plantillas son hipótesis sintéticas basadas en
  documentación pública hasta calibrarlas con corpus autorizado (DRG-00); si la
  detección no es inequívoca, se cae al mapeo actual.
- MT940 se admite como formato estructurado.

### 6. Aprobación del motor

La aprobación de `engine_release` deja de requerir CLI para el usuario final:
la plataforma publica releases aprobados por el operador de plataforma y la
empresa usa el vigente. El usuario nunca ve este paso.

## Consecuencias

- Una pyme concilia sola en tres pasos visibles (Subir → Revisar pendientes →
  Listo) y su contador certifica después sin bloquear la operación diaria.
- El ledger conserva por qué cada decisión es válida; ningún informe presenta
  como independiente lo que fue autorrevisado.
- Requiere migraciones forward-only, pruebas de triggers/RLS por perfil y
  revisión independiente de Accounting, Security y Database.
- Supera parcialmente las secciones de SoD de ADR-027, ADR-028 y ADR-035
  únicamente para el perfil `simple`; en `estricto` siguen intactas.

## Alternativas descartadas

- Quitar SoD: viola invariantes.
- Exigir siempre un segundo usuario: deja fuera a la pyme objetivo.
- Auto-match por puntaje: opaco e imprevisible; los usuarios de referencia
  piden limitar la automatización a sus propias reglas.
