# ADR-027 — Ledger de propuesta y decision humana de conciliacion

- Estado: **Proposed**
- Tarea: FNC-REC-002
- Gate: S1-READY; efecto `none`
- Datos autorizados: exclusivamente sinteticos
- Revision pendiente: Accounting, Security, Database y Architecture

## Contexto

FNC-REC-001 calcula pares explicables sin persistirlos. Para trabajar una cola
humana hace falta conservar quien propuso, quien decidio y con que evidencia,
sin convertir una coincidencia por importe/fecha/referencia en identidad dura ni
alterar los movimientos que la originaron.

El contrato de autorizacion ya separa `match.propose` de `match.confirm` y exige
que el mismo sujeto no ejerza ambos sobre el mismo objeto. El contrato de dedupe
exige historial append-only, par ordenado, idempotencia atomica y evidencia, y
bloquea el efecto financiero de una confirmacion hasta que Accounting y
Architecture definan supersession, grupos y saldos.

## Decision propuesta

1. `match_candidate` materializa una propuesta sobre dos movimientos ordenados
   por UUID y una version de regla. Guarda las señales deterministas, ventana,
   releases y versiones canónicas observadas; no guarda score ni copia valores.
2. `match_decision` es append-only y admite en esta rebanada `confirmed` o
   `rejected`. Una restriccion terminal por candidato deja reversal y reapertura
   para una migracion posterior, en vez de fingir su semantica.
3. Confirmar exige otro sujeto. Rechazar puede hacerlo quien tenga
   `match.reject`; no borra la propuesta ni evidencia.
4. `match_command_receipt` liga `(company, actor, idempotency_key)` con digest,
   accion y resultado. Un advisory transaction lock evita dos ganadores antes de
   la restriccion unica; misma clave/payload reproduce, clave reutilizada
   conflictua.
5. Candidate, decision y receipt llevan RLS forzada. El runtime solo puede
   `SELECT, INSERT`; triggers rechazan `UPDATE/DELETE` incluso para un camino con
   privilegios superiores.
6. La decision referencia un `audit_event` de la misma empresa. Auditoria y
   ledger se confirman en la misma transaccion.
7. El estado visible se deriva: sin decision es `open`; `confirmed` y `rejected`
   son terminales. Ninguno demuestra conciliacion de saldos.

## Sin efecto financiero

`confirmed` significa solamente «un revisor humano acepta que este par debe
tratarse como match en una futura semantica». No cambia `canonical_movement`, no
crea `match_group`, no asigna importes, no resuelve completitud, no alimenta
cierre y no certifica saldos. Esta limitacion forma parte de API y UI.

## Alternativas descartadas por ahora

- Actualizar movimientos a `confirmed`: mezcla el juicio de conciliacion con el
  estado del hecho financiero y hace dificil revertirlo.
- Guardar un booleano en el candidato: pierde historia, actor, motivo y replay.
- Confiar en la pareja enviada por la web: permite materializar una combinacion
  que nunca cumplio las reglas; la API la recalcula dentro de PostgreSQL.
- Crear grupos N:M en esta rebanada: requiere asignaciones exactas y semantica
  contable aún no aceptada.
- Habilitar confirmacion automatica: prohibido por contrato y por el gate actual.

## Consecuencias y deuda explicita

- Una misma pareja y version de regla tiene un expediente estable; atributos
  iguales siguen sin ser unicidad de movimientos.
- Dos movimientos pueden participar en varios candidatos: no hay restriccion
  uno-a-uno.
- Reversal, reapertura, grupos, asignaciones parciales y efecto sobre statements
  requieren ADR/migracion posterior y aceptacion Accounting/Architecture.
- Antes de datos reales se requiere revisar razones, retencion, exportacion,
  rendimiento y el tratamiento de decisiones durante borrado/restauracion.

## Evidencia requerida

PostgreSQL real debe probar RLS positiva/negativa, SoD en dominio y trigger,
append-only, replay/conflicto, concurrencia, auditoria atomica, decision terminal
y ausencia de mutacion en movimientos. API/web deben probar permisos, estados,
neutralidad cross-company, E2E y accesibilidad.

