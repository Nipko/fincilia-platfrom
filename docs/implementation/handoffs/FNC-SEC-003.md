---
task_id: FNC-SEC-003
status: REVIEW_PENDING
base_sha: 3d37b7e4030437691efbbfdbf3d591c53b1d8126
reservation_sha: 18ecad5
implementation_sha: 7922972
tested_head_sha: 7922972c72404362328f3344d920a0ce45311a07
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy, Architecture]
---

# Handoff FNC-SEC-003 — diseño del laboratorio aislado

## Resultado

Quedó definido y validado el límite de seguridad que FNC-PLT-004 deberá
materializar antes de recibir un corpus real: seis zonas sin IP pública ni
egress, 37 controles de identidad/red/cómputo/datos/storage/observabilidad y 12
pruebas obligatorias. Threat model, privacy-map, A-02 y L-01 están ligados por
digest; una nueva amenaza DRG-00 o cambio de postura hace fallar el contrato.

La salida válida conserva explícitamente:

```text
implemented=false
deployment_enabled=false
real_data_authorized=false
provider_selected=false
region_selected=false
managed_idp_selected=false
passed_test_count=0
satisfied_prerequisite_count=0
```

Por tanto no existe un entorno real, una cuenta, un endpoint o una habilitación
oculta detrás del `ok: true`.

## Identidad y roles

Los roles company-scoped, autorización server-side, RLS, revocación y contexto
durable ya existentes forman la capa de autorización. Para datos reales se
prohíbe la autoridad local de contraseñas usada por la demo: el contrato exige
IdP administrado, usuarios nominales, MFA resistente a phishing, step-up AAL3,
JIT máximo 60 minutos, workload identity corta y break-glass con dos personas.

El proveedor no fue elegido. A-02/`UD-PROVIDERS` debe decidirlo junto con región,
KMS, secretos y endpoints. No se creó un modo especial “sólo para pruebas”; el
diseño es el esperado para el entorno final.

## Camino de datos y controles

Un manifiesto aprobado entra por broker nominal a objeto opaco en cuarentena.
Antes de raw debe superar en modo fail-closed malware, contenido activo, PAN y
contenido prohibido. El worker efímero corre sin red, host mounts, privilegios o
instalación dinámica; raw es inmutable y los derivados conservan linaje digest.

Audit/delete ledger queda fuera del restore ordinario. Backups esperan A-02/L-01
y un restore reaplica tombstones/reconcilia antes del health ready. Logs sólo
admiten metadatos allowlisted.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `python3 -B -m unittest tools.isolated_lab.test_model` | 34/34 OK |
| Seguridad + privacidad + legal | 89/89 OK |
| `python3 -B -m tools.isolated_lab validate` | exit 0; diseño sin implementación/autorización |
| Threat model | OK, sin regresión |
| Privacy model | OK, sin regresión |
| Quality gate sobre índice | OK, 0 findings |
| `git diff --cached --check` | OK |

Las mutaciones prueban apertura de egress/IP pública, proveedor/IdP/región
prematuros, shared accounts, password-only, claves estáticas, JIT largo, host
mount, IA externa, control/test/prerrequisito falsamente aprobado y gate
autoaceptado.

## Bloqueos y siguiente implementación

- Security/Privacy/Architecture deben revisar nominalmente el diseño.
- FNC-LEG-001 necesita abogado; L-01 necesita 19 plazos y cuatro signoffs.
- A-02 necesita proveedor/región/data planes; `UD-PROVIDERS` incluye IdP.
- Supply chain aún carece de firma/procedencia demostrada.
- FNC-PLT-004 debe desplegar; FNC-QA-001 debe ejecutar LAB-T01..T12.
- La divergencia de owner DRG-00 entre Legal/Security sigue abierta.

Ningún documento real debe usarse como smoke test mientras esos puntos no estén
consolidados en DRG-00.

## Rollback

Revertir `7922972` retira el contrato, herramienta y solicitud; revertir
`18ecad5` retira la reserva. No hay infraestructura, usuarios, secretos,
firewalls, migraciones ni datos que destruir.
