# Administración de plataforma

## Frontera

La administración de plataforma responde por la operación de Fincilia como
servicio. No hereda roles `owner`, `reviewer`, `auditor` ni ningún permiso de una
empresa. Un sujeto puede tener ambos tipos de rol, pero cada autorización se
resuelve por la frontera correspondiente y queda auditada.

| Capacidad | Superadmin | Operador | Auditor de plataforma |
|---|---:|---:|---:|
| Ver salud, versión, esquema y colas agregadas | Sí | Sí | Sí |
| Ver identidades y organizaciones sin datos financieros | Sí | Sí | Sí |
| Suspender/reactivar identidades | Sí | No | No |
| Administrar roles de plataforma | Sí, con controles de último admin | No | No |
| Ver auditoría de plataforma | Sí | Sí | Sí |
| Abrir documentos/movimientos/saldos de una empresa | No | No | No |
| Aprobar su propio break-glass | No | No | No |

## Bootstrap inicial

1. Un operador configura en PostgreSQL una referencia
   `hmac-sha256:v1:<digest>` calculada con la misma clave dedicada usada para el
   correo Google verificado.
2. La primera autenticación o alta de esa identidad intenta la reclamación.
3. PostgreSQL bloquea la fila singleton, compara la referencia con el binding
   verificado, comprueba que el sujeto esté activo y crea una sola asignación
   `platform_superadmin`.
4. La operación es idempotente para ese sujeto y falla cerrada para cualquier
   otro. No hay endpoint para autoconcederse el rol.
5. La referencia esperada y los bindings permanecen tokenizados; las respuestas
   y logs no muestran correo, `sub` externo ni secreto.

## Datos de diagnóstico autorizados

- estado y tiempo de actividad de servicios;
- release y revisión exactas;
- cabeza de esquema;
- conteos agregados de sujetos, firmas y empresas por estado;
- estado agregado de trabajos y almacenamiento, sin nombres de archivo ni
  contenido;
- eventos de administración y seguridad con identificadores internos.

Quedan fuera los montos, contrapartes, referencias bancarias, tax IDs, celdas,
documentos y cualquier exportación de tenant.

## Controles obligatorios

- sesión nominal administrada; sin superadmin local compartido;
- denegación uniforme para quien no tenga rol de plataforma;
- auditoría append-only de toda mutación;
- impedir suspenderse o revocarse si se deja la plataforma sin superadmin activo;
- no registrar secretos ni PII en detalles de auditoría;
- paginación y límites cerrados en listados;
- mutaciones de alto riesgo con step-up cuando el contrato de assurance quede
  aceptado;
- break-glass separado y deshabilitado hasta doble control real.
