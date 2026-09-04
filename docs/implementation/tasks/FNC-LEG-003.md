---
id: FNC-LEG-003
title: Registro verificable de proveedores y subencargados UAT
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 38c785e
gate: A-02/DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Legal, Privacy, Security, Platform/SRE]
---

# Resultado esperado

Versionar el inventario factual de terceros que participan en la UAT de
Fincilia, separar proveedores de runtime de herramientas de desarrollo y dejar
explícitos datos, finalidad, ubicación conocida, contrato observado e incógnitas
que debe adjudicar un revisor humano.

# Rutas

- Permitidas: `docs/legal/subprocessor-register.json`,
  `docs/legal/SUBPROCESSOR_REGISTER.md`, `tools/subprocessor_register`, esta
  ficha, handoff, CI y archivos centrales por Integration Steward.
- Sólo lectura: centro legal público, contratos de privacidad, DFD, IaC de AWS
  y fuentes oficiales de los proveedores.
- Prohibidas: aceptar A-02/DRG-00/DRG-01, afirmar asesoría jurídica, enviar
  datos a un tercero, habilitar egress, cambiar proveedores o persistir PII.

# Criterios de aceptación

1. El registro incluye exactamente AWS, Google, Cloudflare, Namecheap y GitHub
   con alcance real, no con una etiqueta genérica de cumplimiento.
2. AWS es el único destino previsto de documentos y permanece bloqueado hasta
   DRG-01; `sa-east-1` no se extrapola a soporte o control plane global.
3. Google recibe únicamente identidad OIDC `openid/email/profile` y nunca
   documentos financieros, Gmail, Drive, contactos o calendarios.
4. Cloudflare permanece como DNS autoritativo sin proxy de aplicación; Namecheap
   sólo como correo de contacto; GitHub sólo como cadena de suministro.
5. Las fuentes son HTTPS, oficiales, fechadas y referenciadas sin copiar sus
   textos completos.
6. La divulgación pública enumera los cuatro proveedores visibles al usuario.
7. Todos los juicios de rol, transmisión, DPA y suficiencia permanecen
   `pending_independent_legal_review`.
8. El validador falla ante proveedor, finalidad, dato, región, alcance o gate
   ampliado silenciosamente.

# Verificación

- Pruebas adversariales del contrato y del contenido público.
- CLI offline de validación y reporte.
- Legal treatment, región, privacidad, grafo y quality gate.

# Fuera de alcance

Firmar DPA, adjudicar transferencia/transmisión, aprobar región o retención,
notificar a usuarios, activar runtime o autorizar datos reales.
