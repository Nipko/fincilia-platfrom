# Gates operativos

El plan maestro conserva la definición normativa. Este archivo indica cómo comprobarla.

## S1-READY

Habilita Sprint 1 de producto, no datos reales ni piloto.

- Artefactos del checklist CURRENT_PHASE completos.
- ADR bloqueantes aceptados.
- Contratos y esquema v0 revisados.
- Entorno sintético reproducible.
- Cero datos reales.
- Riesgos críticos tratados.

## DRG-00

Habilita exclusivamente corpus real de investigación:

- Contrato de tratamiento.
- Finalidad acotada.
- Ambiente aislado.
- Inventario nominal.
- Acceso mínimo y auditado.
- Retención y borrado verificables.
- Matriz L-01.
- Firmas humanas de Legal, Security y Product.

## DRG-01

Habilita piloto con datos financieros:

- Pruebas cross-tenant y de canales.
- RLS, objetos, caché, jobs e informes asegurados.
- Región, DPA y subencargados aprobados.
- Restore con tombstones.
- PCI evaluado.
- Pentest sin altos/críticos abiertos.

## GA-01

Habilita venta general:

- Cohortes y cierres comprobados.
- Exactitud y defectos escapados dentro de umbral.
- Pricing, metering, soporte y margen medidos.
- Portabilidad, facturación propia, SLO y DR operables.

Ningún agente firma gates legales, contables, de seguridad o negocio por sí mismo.

