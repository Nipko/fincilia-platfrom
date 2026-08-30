---
id: FNC-ADM-001
status: REVIEW_PENDING
base_sha: 501f65415182bed42494e66abe0ddac75ef38747
implementation_sha: 90f833fba83b876cd5a4b0a736876c85b9e0911d
integration_sha: 9ba610f75f327967382653c7306cc0f36f7ecc6e
data_ceiling: current_gate_remains_authoritative
---

# Handoff FNC-ADM-001 — plano de control y superadmin inicial

## Resultado

Fincilia dispone de un plano administrativo propio, separado de los roles
contables y de la autorización company-scoped:

- el primer `platform_superadmin` se reclama una sola vez al iniciar sesión con
  el correo Google verificado cuya referencia HMAC fue preconfigurada;
- los roles llegan desde PostgreSQL, nunca desde el navegador o un claim IdP;
- superadmin, operador y auditor tienen capacidades distintas y fail-closed;
- la consola muestra salud, release, identidades, firmas y auditoría minimizada;
- administrar la plataforma no concede documentos, movimientos, saldos,
  matches, cierres, KMS decrypt ni break-glass.

## Persistencia y privilegios

`V0044` crea el bootstrap, asignaciones y ledger administrativo, más funciones
acotadas `SECURITY DEFINER`. `V0045` corrige la ambigüedad detectada durante la
ejecución real, revoca escritura directa del rol de aplicación sobre identidad
y añade grant/revoke auditados. Ambas migraciones son forward-only.

El último superadmin no puede ser suspendido ni revocado y una autoridad no
puede suspenderse a sí misma. `fincilia_app` no accede directamente a las tablas
del plano de control.

## API y web

La API publica overview, identidades autorizadas, organizaciones, auditoría,
diagnósticos y mutaciones de rol/estado. `/me` incorpora únicamente roles
internos. La navegación y `/plataforma` fallan cerradas; un auditor puede leer
diagnóstico/auditoría sin que la página intente consultar identidades.

La verificación visual local confirmó login, enlace condicional “Control
central”, salud de PostgreSQL/esquema/Valkey/object storage y acciones de
superadmin. No se ejecutó ninguna mutación administrativa en esa verificación.

## Evidencia

| Verificación | Resultado |
|---|---|
| PostgreSQL 17 focal | 7 pruebas, OK |
| API unitaria | 182 pruebas, OK |
| Web unitaria completa / corrección focal | 269 / 3, OK |
| Web typecheck/lint/build | OK; ruta `/plataforma` incluida |
| Runtime local | schema head V0045; PostgreSQL, Valkey y 4 buckets `up` |
| Reclamación concurrente | una sola asignación inicial |
| Privilegios negativos | sujeto ordinario y acceso directo denegados |
| Migration readiness | 66 pruebas y contrato de 22 funciones privilegiadas, OK |

## Activación UAT pendiente

1. Configurar `FINCILIA_PLATFORM_BOOTSTRAP_EMAIL` y la clave HMAC únicamente en
   el canal privado de secretos; el correo no se pega en chat ni se versiona.
2. Ejecutar `db.admin.platform_admin configure-bootstrap` desde un contexto
   operacional autorizado y comprobar `status` sin imprimir el correo.
3. Desplegar V0044/V0045 y el release por digest; iniciar sesión Google una vez
   y verificar que `bootstrap_claimed=true`.
4. Obtener revisiones Security, Privacy/Legal, Architecture/Database, SRE y QA.

## Riesgos y límites

- Break-glass continúa deshabilitado. Un flujo futuro requiere AAL3, aprobador
  distinto, empresa/alcance explícitos, expiración y revisión posterior.
- El seed local `sofia@demo.local` es sintético; no es el mecanismo cloud.
- La implementación no supera DRG-00/DRG-01 ni autoriza datos reales.

## Rollback

Retirar navegación/rutas y revocar ejecución de funciones conserva
asignaciones y auditoría para investigación. Las migraciones no se revierten ni
se reescriben; cualquier corrección posterior es una versión nueva.

## Revisores requeridos

Security, Privacy/Legal, Architecture/Database, SRE y QA deben ser personas
distintas del Founder accountable antes de aceptar la decisión.
