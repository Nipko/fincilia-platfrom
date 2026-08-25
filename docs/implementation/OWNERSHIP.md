# Ownership provisional

Durante la etapa fundacional una sola identidad humana, `FOUNDER-01` (`Founder`),
asume provisionalmente todos los roles accountable. Un agente puede preparar evidencia,
pero no sustituye la decisión del Founder. La misma persona usando roles distintos no
constituye revisión independiente ni satisface SoD; véase
`docs/implementation/FOUNDER_GOVERNANCE.md`.

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

## Asignación humana vigente

| Slot | Principal | Condición |
|---|---|---|
| Integration Steward | `FOUNDER-01` | Provisional |
| Product | `FOUNDER-01` | Provisional |
| Accounting | `FOUNDER-01` | Provisional; no es revisión financiera independiente |
| Architecture | `FOUNDER-01` | Provisional |
| Security | `FOUNDER-01` | Provisional; no es revisión de seguridad independiente |
| Privacy | `FOUNDER-01` | Provisional; no es revisión de privacidad independiente |
| Legal | `FOUNDER-01` | Provisional; no sustituye asesoría o firma jurídica requerida |

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
