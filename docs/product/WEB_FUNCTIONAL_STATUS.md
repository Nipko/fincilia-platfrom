# Estado funcional de la plataforma web

El inventario ejecutable mide doce dominios de la plataforma web. Mobile queda
fuera del denominador porque el Founder decidio terminar primero la web.

## Resultado actual

- **88 % de implementacion funcional ponderada.** El nucleo contable esta
  construido; OCR, notificaciones externas, fraude avanzado y cobro real siguen
  parciales.
- **59 % de aceptacion sintetica ponderada.** Existen recorridos E2E amplios,
  pero Google real esta bloqueado y las integraciones externas solo tienen
  componentes o adaptadores apagados.
- **28 % de operabilidad de produccion ponderada.** Hay diseño y pruebas de
  controles, pero no se ha demostrado operacion real, DRG-00/01 ni GA-01.

Estos porcentajes no miden precision sobre documentos reales ni certifican un
cierre contable. La fuente calculable es
`docs/product/web-functional-status.json`; `tools.web_functional_status.cli`
recalcula los valores y falla si cambian pesos, evidencia o gates sin actualizar
la declaración.

## Lo grande que falta

1. Identidad Google live y entorno UAT apto para identidad nominal.
2. DRG-00 y DRG-01 con revisores independientes para empezar casos reales.
3. Entrega externa de recordatorios y correo transaccional.
4. OCR para PDFs escaneados y reglas antifraude calibradas.
5. Checkout, webhooks, impuestos y conciliacion del propio cobro SaaS.
6. Operacion productiva: despliegue separado, observabilidad, restore, pentest,
   soporte y evidencia de GA.

La funcionalidad movil permanece deliberadamente al final y no reduce el 88 %
de la plataforma web.
