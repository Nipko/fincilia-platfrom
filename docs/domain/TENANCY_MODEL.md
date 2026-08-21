# Modelo de tenancy v0

- Estado: Draftable
- Tarea: FNC-DOM-001
- ADR: ADR-003

## Relaciones

~~~text
subject 1─N user_identity
subject N─M organization mediante organization_membership
subject N─M company mediante company_membership
organization N─M company mediante engagement
engagement 1─N engagement_assignment
principal N─M company/recurso mediante grant
~~~

## Invariantes

- Organization administra identidad, billing y activos administrativos.
- Company no contiene firm_id y no deriva su identidad de una firma.
- Crear engagement no concede acceso por sí mismo.
- Owner/Admin de organization no recibe finanzas implícitamente.
- Acceso exige principal, assurance, grant y membership directo o engagement vigente.
- Puede existir como máximo un primary_accounting_operator activo con permiso de escritura/cierre.
- Revocar engagement invalida grants, jobs, enlaces, schedules, service principals y caché mediante authorization_version.
- Revocación no elimina ni mueve el histórico.
- Responsabilidad legal, tratamiento, propiedad y autorización son dimensiones separadas.

## Regla de autorización

~~~text
ALLOW =
  principal activo
  AND assurance suficiente
  AND grant vigente para acción/recurso/finalidad
  AND (
    company_membership vigente
    OR organization_membership + engagement vigentes
  )
  AND ninguna prohibición SoD
~~~

El request solo identifica subject y recurso solicitado; el servidor calcula la autorización vigente.

