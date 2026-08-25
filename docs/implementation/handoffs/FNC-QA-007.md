---
task_id: FNC-QA-007
status: REVIEW_PENDING
base_sha: 34cdb64
reservation_sha: f5a77eb
tested_head_sha: 7cecf96
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Security, QA, Web/UX]
---

# Handoff FNC-QA-007 — usuarios y roles por empresa

## Resultado

Owner y firm_admin pueden administrar desde la web los roles company-scoped de
miembros activos de la firma delegada. La identidad sigue llegando del IdP; en
local, la semilla crea cuatro personas sinteticas separadas. Fincilia no crea ni
almacena contrasenas productivas mediante esta funcion.

Los roles son acumulables. Owner administra todos; firm_admin no puede conceder
ni revocar owner o firm_admin; nadie se concede roles a si mismo y el ultimo owner
no puede revocarse. Cada cambio real eleva `authorization_version`, invalida
sesiones anteriores y entrega al BFF una sesion fresca para el administrador.
Concesiones, replays y negativas quedan auditados sin correo ni identidad externa.

## Superficies

- API: listado acotado a la firma y endpoints idempotentes POST/DELETE protegidos
  por `member.manage` y contexto server-side.
- PostgreSQL: usa `company_grant` y `authorization_version` existentes; no requiere
  migracion ni cambia RLS.
- Web: nueva ruta `/empresas/{companyId}/equipo`, visible solo con el permiso del
  servidor, con asignacion, revocacion, motivos y limites SoD explicitos.
- Local: Sofia owner; Ana preparer; Beto reviewer; Carla auditor en identidades
  distintas. Una misma persona fisica puede entrar con cada usuario para probar,
  sin fusionar sujetos ni auditoria.

## Evidencia ejecutada

| Verificacion | Resultado |
|---|---|
| PostgreSQL real `db.tests.test_member_roles` | **11**, OK |
| API completa dentro de imagen | **95**, OK |
| Web lint y TypeScript | OK |
| Web unitarias | **142 en 23 archivos**, OK |
| Build Next de imagen productiva | OK; ruta `/equipo` incluida |
| E2E Chromium de roles | **2**, OK |
| `tools.work_graph.validate` | `ok: true` antes de liberar reserva |
| `tools.quality_gate.cli` | `ok: true`, cero findings sobre indice probado |

El E2E encontro dos defectos que ya tienen regresion: un `LEFT JOIN` convertia la
ausencia de concesion en rol `null`, y un vocabulario importado desde un Client
Component no era estable en el Server Component. La prueba de auditoria encontro
ademas una importacion faltante antes de integrar. Los tres estan corregidos.

## Limites y revision pendiente

- El alta de identidad y la invitacion real pertenecen al IdP B2B futuro. Esta
  entrega administra miembros ya aprovisionados; no inventa autenticacion propia.
- El versionado vigente es company-wide: un cambio real exige renovar sesion a
  las demas personas de esa empresa. Es conservador y coherente con el contrato.
- SoD por objeto no se relaja: acumular preparer/reviewer no permite aprobar el
  trabajo propio.
- Security debe revisar auditoria denegada, ultimo owner y sesion fresca; QA y
  Web/UX, el recorrido y accesibilidad. S1-READY sigue `not_met`.

## Commits y rollback

1. `f5a77eb` — reserva inicial, luego precisada al alcance final solicitado.
2. `e2132f0` — dominio/API y pruebas PostgreSQL.
3. `46bc645` — correccion de ausencia de concesiones.
4. `e1e3b7c` — interfaz web, acciones y E2E.
5. `7cecf96` — auditoria persistente de negativas y tenancy de revocacion.

Revertir 5 retira el endurecimiento de negativas; revertir 4 retira solo la UI;
revertir 3 y 2 retira la API. No hay migracion, archivo financiero ni dato real
que restaurar. La semilla sintetica preexistente no fue modificada.
