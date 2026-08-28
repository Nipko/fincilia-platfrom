# ADR-029 — OpenTofu para el spike AWS T0

- Estado: **Proposed, autorizado solo como spike reversible**
- Fecha: 2026-08-28
- Tarea: FNC-PLT-010
- Gate: T0-SYNTHETIC

## Contexto

Fincilia necesita comprobar en AWS un control plane sintetico sin convertir la prueba en
arquitectura productiva ni operar recursos manualmente. El plan maestro historico acota la
familia de herramientas a Terraform/OpenTofu. La cuenta esta en Free Plan y no debe entrar
en Organizations o Control Tower.

## Decision del spike

Usar OpenTofu `1.12.6` con AWS provider `6.59.0`, autenticacion temporal de `aws login`,
estado S3 cifrado/versionado y locking nativo `use_lockfile`. El bootstrap del bucket de
estado usa estado local sin secretos, fuera del repositorio, y el estado principal nunca se
guarda deliberadamente en Git.

El control plane inicial no incluye runtime. EC2/RDS requieren una tarea y plan posteriores.
Esta eleccion puede revertirse destruyendo T0 y no acepta por si misma la herramienta de
produccion.

## Alternativas

- Terraform: valido tecnicamente, pero no aporta ventaja para este spike y agrega otra
  distribucion/licencia a evaluar.
- CloudFormation: evita binario externo, pero crearia una segunda representacion respecto
  de la direccion Terraform/OpenTofu.
- AWS CDK: introduce runtime, dependencias y generacion imperativa innecesaria.
- Cambios manuales/CLI: no producen plan, estado y destroy reproducibles.

## Consecuencias y controles

- Versiones y hashes de providers quedan en lockfiles.
- El plan JSON se valida contra una allowlist antes de cada apply.
- Account ID se aporta en entorno local y no se fija en codigo.
- Sin revisiones independientes, el ADR permanece Proposed y no se extrapola a produccion.
