# Estado funcional de la plataforma web

El inventario ejecutable mide doce dominios de la plataforma web. Mobile queda
fuera del denominador porque el Founder decidio terminar primero la web.

## Resultado actual

- **98 % de implementacion funcional ponderada.** El nucleo contable, las
  senales de riesgo, el despacho durable de correo y el OCR local aislado estan
  construidos; el cobro real sigue parcial.
- **62 % de aceptacion sintetica ponderada.** Existen recorridos E2E amplios y
  el protocolo de correo se probo con roles PostgreSQL reales; Google y SES
  permanecen apagados por los gates de datos y revision.
- **30 % de operabilidad de produccion ponderada.** Hay diseño y pruebas de
  controles, pero no se ha demostrado operacion real, DRG-00/01 ni GA-01.

Estos porcentajes no miden precision sobre documentos reales ni certifican un
cierre contable. La fuente calculable es
`docs/product/web-functional-status.json`; `tools.web_functional_status.cli`
recalcula los valores y falla si cambian pesos, evidencia o gates sin actualizar
la declaración.

## Lo grande que falta

1. Identidad Google live y entorno UAT apto para identidad nominal.
2. DRG-00 y DRG-01 con revisores independientes para empezar casos reales.
3. Activacion operativa de SES, feedback, reputacion y runbook de correo.
4. Calibracion autorizada de OCR/tablas escaneadas y senales de riesgo.
5. Checkout, webhooks, impuestos y conciliacion del propio cobro SaaS.
6. Operacion productiva: despliegue separado, observabilidad, restore, pentest,
   soporte y evidencia de GA.

La funcionalidad movil permanece deliberadamente al final y no reduce el 98 %
de la plataforma web.
