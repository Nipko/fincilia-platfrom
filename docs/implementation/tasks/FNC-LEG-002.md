---
id: FNC-LEG-002
title: Centro legal público de Fincilia
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: b837261
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Privacy/Legal, Security, Product, Accessibility/QA]
---

# Resultado

Fincilia publica inicio, privacidad, términos, cookies, seguridad, DPA,
subencargados y eliminación de cuenta en `fincilia.com`. Los documentos
identifican a Parallext LLC como operador jurídico y a Parallext.com como marca
de desarrollo, y conservan revisión interna independiente sin presentar ese
estado de gobierno como un borrador público.

# Criterios de aceptación

1. Todas las páginas son públicas, navegables sin login, accesibles y enlazadas
   desde inicio, registro, ingreso y footer.
2. Privacidad explica categorías, finalidades, autorización y fundamentos
   aplicables, retención por criterios, derechos, transferencias,
   subencargados y contacto sin prometer compliance.
3. Google se limita a autenticación y scopes `openid email profile`; no se afirma
   acceso a Drive, Gmail o uso publicitario.
4. Cookies distingue estrictamente necesarias de analítica futura opt-in.
5. Eliminación explica verificación, alcance, retención legal y canal de solicitud.
6. DPA se presenta como plantilla a acordar, no contrato automáticamente firmado.
7. Cada página tiene versión, fecha de vigencia y estado público inequívoco.
8. Parallext LLC, su domicilio y teléfono figuran como responsable u operador
   según el contexto; Parallext.com figura como marca de desarrollo.
9. El alta Google exige por separado aceptación de términos y autorización de
   privacidad, y persiste los identificadores exactos de las versiones activas.
10. Las versiones anteriores permanecen como evidencia histórica y dejan de
    estar activas para nuevas altas mediante una migración forward-only.
11. La publicación pública destinada a revisión de marca está íntegramente en
    inglés, declara `lang=en`, tiene metadatos propios y usa las URLs canónicas
    inglesas configuradas en Google.
12. Las rutas anteriores en español redirigen permanentemente a sus equivalentes
    canónicos, sin duplicar contenido ni romper enlaces ya distribuidos.

# Fuera de alcance

Concepto jurídico independiente, firma de DPA, calendario L-01, aceptación de
DRG-00/01, promesa regulatoria, EIN/NIT o representación sobre registro
mercantil. La razón social, domicilio y teléfono de esta revisión fueron
entregados explícitamente por el Founder.

# Rutas de la revisión 2026-09-03

- `apps/web/src/app/{privacy,terms,cookies,security,dpa,subprocessors,delete-account}`
  y handlers 308 fail-closed desde las rutas anteriores.
- `apps/web/src/components/legal-document.tsx` y `apps/web/src/lib/legal-*`.
- Registro Google, callback y pruebas de consentimiento web/API.
- `db/migrations/V0056__publish_legal_documents_2026_09_03.sql`,
  `V0057__publish_english_legal_documents_2026_09_03.sql` y prueba PostgreSQL.
- Runbook Google, backlog, trazabilidad, fase vigente y handoff de revisión.

Las rutas canónicas públicas son `/privacy`, `/terms`, `/cookies`, `/security`,
`/dpa`, `/subprocessors` y `/delete-account`. `/privacidad`, `/terminos`,
`/seguridad`, `/subencargados` y `/eliminar-cuenta` se conservan exclusivamente
como redirecciones permanentes de compatibilidad.

# Enmienda de publicación inglesa

V0057 amplía el identificador versionado con un sufijo de idioma ISO 639-1 y
activa `terms-2026-09-03-en` y `privacy-2026-09-03-en`. No modifica V0056 ni
aceptaciones históricas. El resto de la interfaz puede permanecer en español;
cada documento legal declara explícitamente su contenido en inglés.
