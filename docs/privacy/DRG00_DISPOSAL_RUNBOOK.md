# Saneamiento y borrado reconciliado DRG-00

## Regla de entrada

El servicio rechaza cualquier purga si la política aplicable no está efectiva o
si el delete ledger no sobrevive a la ventana de backup. La política incluida en
el ensayo se llama `SYNTHETIC-TEST-POLICY` y jamás autoriza datos reales.

## Orden irreversible

1. Validar política y estado del inventario.
2. Escribir y hacer `fsync` del tombstone en el ledger separado.
3. Registrar `tombstone` en el inventario encadenado.
4. Eliminar cada copia activa conocida.
5. Registrar el recibo `purge` con las referencias retiradas.
6. Reconciliar inventario con cuarentena, evidencia, derivados, backup y scratch.

Un crash después del paso 2 conserva la intención y permite reanudar. Un crash
antes del paso 2 no elimina nada. La operación es idempotente.

## Restore

El entorno restaurado permanece cerrado y sin readiness. Primero carga el delete
ledger que vive fuera del restore ordinario, reaplica cada tombstone, reconcilia
las zonas y solo entonces escribe `restore-ready.json`. Una copia resucitada se
purga nuevamente.

## Evidencia y límites

Los recibos contienen referencias opacas, digests, conteos y estados. Nunca
contenido, nombres, cuentas, importes, correo o credenciales. L-01 y la revisión
de Legal/Privacy siguen pendientes; este runbook técnico no las suplanta.
