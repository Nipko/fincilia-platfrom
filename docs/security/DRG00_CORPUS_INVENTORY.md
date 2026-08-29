# Inventario de corpus DRG-00

El inventario de FNC-DAT-003 es un ledger NDJSON append-only. Identifica cada
artefacto, empresa y operación mediante referencias opacas SHA-256; no almacena
nombre de fichero, correo, razón social, cuenta, importe ni contenido.

Cada evento cubre con su digest todos sus campos y enlaza el digest anterior.
Las transiciones, referencias a objetos y operaciones idempotentes se validan al
leer y al escribir. Cualquier línea truncada, alterada o fuera de orden bloquea
el laboratorio.

`reconcile` compara las copias activas declaradas con cuarentena, evidencia,
derivados, backup y scratch. Una diferencia nunca se convierte en cero ni en un
éxito parcial: es un blocker de purga y destrucción.

El contrato está implementado y probado exclusivamente con datos sintéticos.
No autoriza DRG-00 ni reemplaza las aprobaciones Legal, Privacy y Security.
