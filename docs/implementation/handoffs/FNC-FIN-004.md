---
id: FNC-FIN-004
status: REVIEW_PENDING
base_sha: a4d10c07accb2749a5e0e5c26d6437c379c7de93
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_gate
author: Codex principal dev + Integration Steward
independent_reviewers: [Finance, Platform/SRE, Security, QA]
---

# Handoff FNC-FIN-004 — cuenta comercial y alertas brutas AWS

## Resultado

La cuenta se cambió directamente de `FREE` a `PAID` y se observó
`PAID/ACTIVE`. No se habilitaron AWS Organizations ni Control Tower. La
foundation se completó en modo frío y el presupuesto mensual administrado de
USD 120 quedó configurado como alarma account-wide de consumo bruto:

- ACTUAL mayor a 50 %.
- ACTUAL mayor a 80 %.
- FORECASTED mayor a 100 %.
- Créditos, descuentos y reembolsos no reducen la medida de la alarma.

AWS Budgets no es un hard cap. El alcance seguirá siendo account-wide hasta
que las etiquetas de asignación estén activas y hayan madurado en Billing; un
filtro prematuro podría omitir recursos nuevos.

## Hallazgo de seguridad y corrección

El primer plan posterior a la foundation reveló doce reglas de salida ausentes.
La causa era mezclar `egress = []` inline con recursos
`aws_vpc_security_group_egress_rule`. La documentación oficial del proveedor
advierte que esa combinación puede sobrescribir reglas y producir deriva
perpetua. Se retiraron los argumentos inline, se conservaron las reglas VPC
individuales y se añadió una prueba adversarial que impide reintroducir la
mezcla.

El plan correctivo validado contenía 12 altas, una actualización y cero
borrados. Después del apply, un segundo plan produjo `147 no-op`: no quedan
altas, cambios ni eliminaciones pendientes.

## Evidencia

| Verificación | Resultado |
| --- | --- |
| Plan comercial observado | `PAID/ACTIVE` |
| Foundation / runtime | `36/36` completa; `0/11` ausente |
| Servicios / NAT / ALB / cache | ECS 0; NAT 0; ALB y cache ausentes |
| RDS | detenido, privado, cifrado, protegido y backup de 14 días |
| Presupuesto | USD 120, sin filtro, costo bruto y umbrales 50/80/100 |
| Plan posterior | `147 no-op` |
| Pruebas focales | 69, OK |
| Contrato de infraestructura | `ok: true`; fuentes válidas |
| OpenTofu | formato y validación, OK |

Una consulta inicial usó por error el subcomando inexistente
`get-account-plan-status`; se corrigió a `get-account-plan-state` y la consulta
válida devolvió `PAID/ACTIVE`. Ninguna mutación dependió de la consulta fallida.

## Límites y revisiones

`real_data_authorized=false`. RDS permanece detenido, el plano runtime no está
materializado y no se cargó ningún dato financiero. DRG-00, DRG-01, drills del
target y revisiones independientes continúan pendientes. Finance debe revisar
el umbral; Platform/SRE y Security deben revisar la convergencia y la política
de red; QA debe reproducir las pruebas.

## Rollback

Un rollback de código debe restaurar una versión que mantenga reglas VPC
dedicadas; no debe reintroducir la mezcla inline. Reducir o eliminar alertas es
un cambio financiero explícito. El plano frío se conserva con ECS en cero y
RDS detenido; no se usa `tofu destroy` como mecanismo de reversión.
