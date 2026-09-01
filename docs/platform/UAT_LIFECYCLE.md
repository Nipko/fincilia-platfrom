# Ciclo de UAT, limpieza y promoción a producción

## Estado y frontera

`fincilia.com` se usa como superficie UAT mientras se valida el producto. UAT
es reiniciable y producción aún no está provisionada. Cambiar una etiqueta, un
DNS o una variable no convierte UAT en producción.

El techo de datos vigente continúa definido por `CURRENT_PHASE.md` y los gates
DRG-00/DRG-01. Nombrar el entorno UAT no autoriza documentos financieros reales.

Cada actualización in-place comprueba además que API, web y worker vienen del
ECR T0 por digest, conserva datos reales, IA externa y Google OIDC apagados hasta
DRG-00, y exige un backup menor a 26 horas y un restore-check menor a ocho días.
El reinicio solo se declara exitoso después de responder por HTTPS en
`/entrar`; entonces persiste evidencia minimizada bajo
`deployment-evidence/uat/<release_sha>/`. Si falla, restaura el bundle anterior.

## Promoción

La unidad de promoción es el digest inmutable del artefacto que superó UAT,
acompañado por SBOM, procedencia, resultados de pruebas y aceptación nominal.
Producción se crea con base, almacenamiento, caché, identidad, secretos, KMS,
backups y auditoría propios. No se copian cuentas, objetos ni base de UAT.

## Limpieza segura de UAT

La estrategia es reemplazar el plano de datos UAT, no recorrer tablas con
`DELETE` ni ofrecer un botón destructivo en la consola web.

1. Congelar altas, cargas y trabajos nuevos; registrar release y hora de corte.
2. Inventariar por ID/ARN todos los recursos y demostrar que ninguno pertenece
   a producción.
3. Crear backup cifrado y completar un restore drill desechable.
4. Generar un plan con allowlist exacta y un token de confirmación de máximo 15
   minutos. El plan debe fallar si aparece un patrón de producción.
   Mientras el plan está armado los escritores permanecen congelados. El mismo
   token permite cancelarlo incluso después de expirar y reanudar el plano sin
   cruzar el corte destructivo. Cualquier error de validación previo al corte
   invalida el plan y reanuda escritores; nunca deja un reset medio armado.
5. Provisionar un plano UAT vacío y aislado, aplicar migraciones desde cero y
   ejecutar sondas de RLS, tenancy, almacenamiento y colas.
6. Configurar de nuevo la referencia HMAC del correo Google del Founder. No se
   copia la asignación anterior; el primer login verificado reclama una sola vez
   el nuevo `platform_superadmin`.
7. Invalidar sesiones y retirar claves/recursos UAT anteriores solo después de
   que el nuevo plano esté sano y la evidencia esté guardada.
8. Conservar un manifiesto digest-only de la operación; no conservar payloads,
   correos, documentos ni secretos dentro de la evidencia.

Después de eliminar los volúmenes o rotar secretos ya no existe rollback por
simple reinicio. Un fallo posterior a ese corte mantiene la superficie detenida,
escribe un marcador digest-only `recovery_required` y exige restaurar el backup
verificado antes de reabrir. Reiniciar automáticamente un plano parcial está
prohibido.

## Controles de salida antes de producción

- UAT aceptado con el release exacto y defectos severos cerrados.
- Revisiones Security, Privacy/Legal, Architecture/Database, SRE y QA nominales.
- Ensayo de limpieza exitoso sobre un entorno desechable.
- Restore drill y rollback operativo demostrados.
- DRG-00/DRG-01 y controles de datos aplicables satisfechos.
- Producción creada desde cero y smoke test sin datos de UAT.

La primera limpieza pública continúa deshabilitada hasta completar las
revisiones y el ensayo. Este documento no autoriza ejecutarla.
