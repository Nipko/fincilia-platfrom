---
id: FNC-PLT-013-R1
corrects: FNC-PLT-013
status: REVIEW_PENDING
base_sha: d4c02bb1c2e7652ad561678a0cb26802d922d349
code_sha: f8a8c1577f757f0068363ebd0947238e523d2931
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, Privacy, QA]
---

# Handoff FNC-PLT-013-R1 — resolución reproducible de OpenTofu en WSL

## Corrección integrada

`pilotctl.ps1` ejecuta el controlador dentro de WSL. El binario oficial de
OpenTofu estaba instalado en `~/.local/bin`, pero el entorno cerrado del
controlador heredaba un `PATH` que no garantizaba esa ruta. El controlador ahora
antepone el directorio de binarios del usuario sin ampliar la lista de variables
permitidas ni reenviar secretos.

La distribución local utiliza OpenTofu 1.12.6 para `linux_amd64`, descargado de la
publicación oficial y cotejado contra su `SHA256SUMS` antes de instalarse. El
binario no se versiona en el repositorio.

## Evidencia reproducible

| Verificación | Resultado |
| --- | --- |
| `wsl tofu version` | `OpenTofu v1.12.6 on linux_amd64` |
| `wsl python3 -m unittest tools.aws_pilot_control.test_control tools.aws_private_pilot.test_validate` | 52 pruebas, OK |
| `pilotctl.ps1 status -AccountId 632144225293` | `cold`; base, runtime y servicios ausentes; cero NAT; datos reales deshabilitados |
| `pilotctl.ps1 plan-cold -AccountId 632144225293` | plan válido: 139 `create`, 9 `read`, cero `delete`; sin apply |
| `wsl python3 -m tools.quality_gate.cli` sobre el índice | OK, cero hallazgos |

La consulta de etiquetas `Environment=private-pilot` y el estado remoto de
OpenTofu no encontraron recursos ni estado aplicado. El plan se conserva en una
ruta ignorada y no contiene autorización para datos reales.

## Límite deliberado

No se aplicó el plan. Las 139 altas corresponden a la fundación separada del
piloto privado y no a la infraestructura UAT ya existente. Aplicarlo crea estado
externo y capacidad con costo potencial, por lo que requiere autorización
expresa sobre ese plan actualizado, imágenes publicadas por digest y controles
OIDC listos.

El `pilot.auto.tfvars` local continúa ignorado y no se considera fuente aprobada:
su release e imágenes deben actualizarse desde un candidato publicado y
verificado antes de cualquier apply.

## Riesgos y trabajo pendiente

- No existe todavía proveedor GitHub OIDC ni rol publicador ECR en la cuenta.
- Los repositorios ECR del piloto nacen con la fundación; las imágenes del
  candidato firmado aún no están publicadas.
- RDS, restore objetivo, runtime protegido y controles cloud siguen sin
  evidencia aplicada.
- DRG-00 y DRG-01 permanecen `not_met`; ningún documento financiero real está
  autorizado.
- Security, Platform/SRE, Privacy y QA deben revisar de manera independiente.

## Rollback

La corrección de código se revierte retirando la anteposición de
`~/.local/bin`; no hay rollback cloud porque no se creó ni modificó ningún
recurso AWS.
