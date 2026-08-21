# Ownership provisional

Los nombres humanos siguen sin asignar. Un agente puede preparar evidencia, pero no sustituir una aprobación de Product, Accounting, Security, Privacy, Legal o Finance.

| Área | Accountable owner | Escritura principal | Revisión obligatoria |
|---|---|---|---|
| Integración y gobierno | Integration Steward | raíz, docs/implementation | Architecture; Security si afecta CI |
| Producto | Product + Accounting | docs/product | UX, Architecture |
| Dominio y contratos | Architecture + Accounting | docs/domain, packages/contracts | Backend, Data, Security |
| API y control | Backend | apps/api | Architecture, Security |
| Datos e ingesta | Data Engineering | workers, tests/golden | Accounting, Security |
| Web y UI | Web/UX | apps/web, packages/ui | Product, Accessibility/QA |
| Móvil | Mobile | apps/mobile | Security, Product |
| Plataforma | Platform/SRE | infra, Compose, CI | Security, Architecture |
| Seguridad y privacidad | Security/Privacy | docs/security, tests/security | Architecture; Legal humano |
| Calidad | QA/SDET | docs/testing, tests | Owner del área |
| ADR y plan | Architecture/Product | docs/adr, plan maestro | Owners afectados |

## Rutas protegidas

Requieren reserva exclusiva e integración por su owner:

- Archivos raíz.
- Plan maestro y CURRENT_PHASE.
- Backlog, gates y ownership.
- ADR Accepted.
- OpenAPI, JSON Schema y eventos compartidos.
- Migraciones, esquema canónico y seeds.
- Compose, CI, lockfiles e IaC compartida.

## Reglas

- Un owner preserva coherencia; no necesita escribir todo.
- Un implementador no es su único revisor en tareas sensibles.
- Solo un Database Migration Owner asigna una migración a la vez.
- CODEOWNERS se crea cuando existan usuarios reales del proveedor Git; antes sería decorativo.

