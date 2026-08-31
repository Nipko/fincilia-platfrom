---
id: FNC-PRV-004
title: Ensayo ejecutable de derechos e incidente previo a DRG-01
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 4d84858
gate: DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Privacy/Legal, Security, Platform, QA]
---

# Resultado

Un ensayo completamente sintético demuestra recepción opaca, verificación,
inventario, contención, revocación, tombstone previo a borrado, restore cerrado y
post-revisión separada sin inventar plazos ni decisiones jurídicas.

# Criterios de aceptación

1. Ningún correo, nombre, contenido o identificador legible entra en la evidencia.
2. Notificabilidad, SLA, aplicabilidad y excepciones permanecen `pending_legal`.
3. La revocación invalida acceso antes de remediar.
4. El tombstone precede todo unlink y sobrevive a restore.
5. La reapertura solo ocurre tras reconciliar inventario y tombstones.
6. El cierre exige tres referencias humanas distintas en el fixture.
7. Doce pruebas y evidencia adjudicada pasan sin autorizar datos reales.

# Fuera de alcance

Aceptar L-01, emitir concepto legal, notificar a terceros, usar información real o
declarar superado DRG-00/01.
