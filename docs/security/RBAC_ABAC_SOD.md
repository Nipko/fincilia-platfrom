# RBAC, ABAC y segregación v0

- Estado: Draftable
- Tarea: FNC-SEC-001

## Roles base

| Rol | Alcance | Capacidades | No implica |
|---|---|---|---|
| Organization Owner | Organización | Billing, miembros, configuración | Acceso financiero |
| Firm Admin | Firma | Equipo, engagements, asignaciones | Cerrar todas las empresas |
| Company Admin | Empresa | Equipo y configuración de empresa | Saltar SoD |
| Preparer | Empresa/ciclo | Importar, mapear, proponer, comentar | Aprobar su preparación |
| Reviewer | Empresa/ciclo | Revisar matches/excepciones | Cierre final automático |
| Close Approver | Empresa/ciclo | Aprobar cierre/reapertura | Preparar y aprobar mismo control |
| Auditor | Empresa/periodo | Lectura de evidencia/audit | Mutaciones |
| Viewer | Empresa | Lectura autorizada | Exportación privilegiada |
| Client Collaborator | Solicitud | Subir/responder/comentar | Ver cartera de firma |

## Atributos de decisión

- subject_id y assurance.
- organization_membership/company_membership.
- engagement y grant vigentes.
- company_id, recurso, acción y finalidad.
- ciclo/periodo y estado.
- assignment y ownership operativo.
- policy de SoD.
- authorization_version.

IP, dispositivo, hora y geografía son señales de riesgo, no identidad ni autorización primaria.

## SoD mínima

| Acción A | Acción B incompatible en mismo control |
|---|---|
| Preparar ajuste material | Aprobar ese ajuste |
| Crear/cambiar regla con impacto | Aprobar release de la regla |
| Solicitar reapertura | Aprobar reapertura |
| Administrar grant privilegiado | Auditarse como único revisor |
| Ejecutar break-glass | Aprobar/revisar su propio acceso |

Una operación unipersonal requiere política explícita, step-up, motivo y revisión posterior; no un bypass oculto.

## Revocación

Incrementar authorization_version e invalidar grants, sesiones, scopes de jobs, enlaces, exports programados, schedules, service principals y cachés derivados.

