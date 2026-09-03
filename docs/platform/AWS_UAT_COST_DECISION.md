# Decisión técnica de costo para UAT AWS

## Resultado

La opción recomendada es conservar y endurecer el host UAT que ya sirve
`fincilia.com`. Su base fija regional es **USD 31,826/mes**. El volumen de 16 GB
del laboratorio T1 detenido añade **USD 2,432/mes** a la cuenta, para una base
actual de **USD 34,258/mes**, antes de uso variable.

El `private-pilot` administrado no cabe en el mismo sobre: su plano frío parte
de USD 36,20/mes; crear el plano caliente manteniendo servicios detenidos lo
lleva a USD 257,36/mes; con las dos tareas Fargate mínimas activas llega a USD
319,264/mes. Estos valores excluyen LCU, transferencia, logs y solicitudes.

## Por qué

La diferencia no viene principalmente de cómputo. NAT Gateway, seis endpoints
de interfaz y la entrada ALB/WAF representan la mayor parte del salto. Ese
aislamiento es valioso para una etapa posterior, pero quemaría los USD 100 de
crédito en menos de un mes sin dar mayor cobertura funcional de UAT.

## Control recomendado

Se propone una alerta bruta de USD 45/mes para cubrir la base de USD 34,258 y
un margen pequeño de S3, ECR, logs y transferencia. AWS Budgets alerta; no corta
recursos. Cambiar el presupuesto, retirar el laboratorio o aplicar recursos
requiere autorización separada.

Los créditos y ajustes del programa pueden reducir el cobro neto temporalmente,
pero no cambian el costo bruto ni constituyen un límite de gasto.

## Límites

- Evidencia de inventario y facturación reducida; no conserva IDs, ARN ni cuenta.
- Ninguna escritura AWS ni `apply` fue ejecutada.
- DRG-00 y DRG-01 no cambian; sólo datos sintéticos.
- La recomendación no convierte el host único en arquitectura de producción.
- Producción requerirá una decisión de disponibilidad, backup y separación de datos.
