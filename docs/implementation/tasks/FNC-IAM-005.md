---
id: FNC-IAM-005
title: Preflight redactado de activacion Google en UAT
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 378f6de76deb6da08030f940d6558b17c81d30a6
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Platform/SRE, QA]
---

# Resultado

Un operador puede comprobar el control plane Google/Cognito desde el estado
OpenTofu sin copiar identificadores a la terminal. El resultado distingue
configuracion valida de autorizacion: una sonda verde no activa el runtime, no
crea usuarios y no mueve DRG-00.

# Rutas reservadas

- `tools/identity_readiness/**`.
- `docs/platform/UAT_GOOGLE_ACTIVATION.md`.
- ficha, handoff, backlog, fase y trazabilidad por Integration Steward.

# Criterios de aceptacion

1. El CLI descubre pool, cliente y dominio desde outputs adjudicados de T0.
2. La salida nunca contiene IDs, ARNs, client secret, correo, usuario o token.
3. OpenTofu y AWS se invocan con vectores de argumentos y `shell=False`.
4. Rutas fuera del repositorio, traversal, outputs incompletos y respuestas
   truncadas fallan cerrados con mensajes neutros.
5. Los 16 controles live conservan `activation_authorized=false` aunque pasen.
6. La guia enumera el cierre tecnico y los bloqueos humanos sin sugerir que una
   bandera ambiental pueda aceptar DRG-00.

# Fuera de alcance

Aplicar infraestructura, encender OIDC, crear cuentas reales, almacenar secretos,
aceptar revisiones o habilitar documentos financieros reales.

# Evidencia integrada

- Implementacion: `6ff3d64`.
- 16 pruebas focales de identidad y descubrimiento: OK.
- Quality gate sobre el indice: cero hallazgos.
- Sonda live repetida tras renovar la sesion temporal AWS: 16/16, con evidencia
  redactada en `docs/implementation/evidence/FNC-IAM-005.json`.
