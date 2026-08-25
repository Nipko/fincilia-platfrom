# Gobierno fundacional de una sola persona

## Decisión confirmada

Durante la etapa actual una sola persona humana, identificada en el repositorio como
`FOUNDER-01` (`Founder`), asume provisionalmente Integración, Producto, Contabilidad,
Arquitectura, Seguridad, Privacidad y Legal.

Esto asigna responsabilidad y elimina el bloqueo de **owner ausente**. No crea
independencia: cambiar de sombrero no convierte a una persona en un segundo revisor.

## Qué permite

- Priorizar y continuar desarrollo local y CI con datos sintéticos.
- Ratificar dirección provisional de producto y arquitectura.
- Aceptar conscientemente el costo de una decisión reversible en etapa fundacional.
- Dejar cada decisión preparada para revisión especializada posterior.

## Qué no permite

- Declarar S1-READY, DRG-00, DRG-01 o GA-01 superados por autoaprobación.
- Usar documentos financieros reales, iniciar pilotos o desplegar producción.
- Cumplir revisión independiente de seguridad, privacidad, legal, migraciones o
  semántica financiera.
- Autorizar decisiones financieras automáticas o informes certificados.

## Paquete técnico pendiente de confirmación del Founder

El archivo `founder-governance.json` contiene las diez decisiones que actualmente
bloquean S1-READY, descubiertas desde sus contratos fuente. Cada una incluye una
recomendación concreta, consecuencia y rollback. Su confirmación habilitará la
implementación técnica provisional, pero la decisión seguirá marcada como pendiente de
un humano distinto donde el control requiera independencia.

## Regla de crecimiento

La primera persona adicional debe cubrir la revisión de mayor riesgo aplicable. Antes
de datos reales se requieren, como mínimo, validaciones independientes de Seguridad y
Privacidad/Legal; antes de efectos financieros o reportes certificados, revisión de
Contabilidad; antes de migraciones productivas, revisión técnica independiente.

La identidad nominal privada puede mantenerse fuera del repositorio. `FOUNDER-01` es
un alias estable y auditable, no una segunda persona ni un reemplazo de firma legal.
