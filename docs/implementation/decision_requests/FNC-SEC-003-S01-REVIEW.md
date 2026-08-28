# Solicitud de revisión S-01 — laboratorio aislado

## Decisión solicitada

Security, Privacy y Architecture deben revisar el diseño de
`isolated-real-data-lab.json` y registrar cambios requeridos antes de que
Platform implemente FNC-PLT-004. Esta revisión no autoriza datos reales.

## Revisión de identidad y enrolamiento

- Confirmar IdP administrado, invitaciones nominales y subject estable.
- Prohibir la autoridad local de contraseñas para cualquier entorno real.
- Confirmar MFA resistente a phishing, AAL2 de sesión y step-up AAL3.
- Confirmar roles server-side por company, revocación y contexto durable.
- Confirmar JIT de 60 minutos, doble control y revisión de break-glass.
- Seleccionar proveedor sólo mediante A-02/`UD-PROVIDERS`; no en este archivo.

## Revisión técnica

- Límites de seis zonas y ausencia total de red pública/egress actual.
- Cuarentena y scanner fail-closed antes de raw.
- Workload identity, imágenes, sandbox y scratch efímero.
- Separación de claves/stores, auditoría/delete ledger y restore.
- Allowlist de logs, incidentes, destrucción y evidencia digest-only.
- Cobertura de TM-005/TM-014 y de los 12 casos LAB-T01..T12.

## Evidencia nominal requerida

- Tres aliases distintos: Security, Privacy y Architecture.
- Fecha, versión y referencia externa de revisión.
- Riesgos rechazados, mitigados y remitidos; ninguno autoaceptado.
- Condiciones obligatorias para FNC-PLT-004 y QA-001.
- Confirmación de que A-02, L-01, supply chain y DRG-00 siguen cerrados.

## Prohibiciones durante la revisión

No desplegar cloud, crear usuarios/proveedores, abrir endpoints o usar un
documento real como “smoke test”. No copiar PII, secretos, configuraciones
sensibles, conceptos o firmas al repositorio o a prompts externos.
