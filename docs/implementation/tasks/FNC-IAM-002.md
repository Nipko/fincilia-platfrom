---
id: FNC-IAM-002
title: Centro de cuenta y recorrido de identidad coherente
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: a1f03c7430e30c15ccf0a3ed411c3baf7d4e26bb
gate: DRG-00
gate_effect: none
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Product/UX, Accessibility/QA]
---

# Resultado

Una persona puede entender y controlar su sesion desde un centro de cuenta,
recorrer sus empresas y roles, acceder a la administracion autorizada de equipo
y salir de forma explicita. El recorrido conserva el adaptador sintetico local y
la preparacion Google/Cognito de FNC-IAM-001 sin convertir la web en autoridad de
credenciales reales.

# Rutas

- `apps/api/src/fincilia_api/routes.py` y pruebas de `/me`.
- `apps/web/src/app/cuenta/**`, shell, navegacion, cliente API y pruebas.
- Ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

1. `/me` expone solo modo de identidad, assurance y vencimiento de la sesion;
   no correo, subject externo, token, hash ni secreto.
2. `/cuenta` muestra nombre, modo de acceso, vencimiento y empresas/roles desde
   respuestas verificadas server-side.
3. Roles y empresas enlazan a los espacios autorizados; la web no infiere
   permisos nuevos ni acepta `company_id` como autoridad.
4. Google preparado se describe como administrado; local se marca sintetico y
   nunca apto para datos reales.
5. Salida elimina todas las cookies de sesion de Fincilia.
6. Estados 401/403 y expiracion fallan cerrados; no enumeran identidades.
7. Unitarias, tipos, build, Chromium y Axe aplicables quedan verdes.

# Fuera de alcance

Activar Google real, almacenar correo, recuperar passwords reales, MFA propio,
gestionar secretos desde la UI, mover DRG-00 o aceptar revisiones humanas.
