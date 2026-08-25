# Ownership provisional

`FOUNDER-01` es el alias humano estable del fundador y asume provisionalmente todas
las responsabilidades accountable indicadas abajo. La identidad civil se conserva
fuera del repositorio. Esta acumulación no convierte al Founder en revisor
independiente de su propia decisión o implementación. Las personas sintéticas usadas
para probar roles dentro de la aplicación tampoco son owners ni revisores de gobierno.

| Área | Accountable owner | Escritura principal | Revisión obligatoria |
|---|---|---|---|
| Integración y gobierno | FOUNDER-01 / Integration Steward | raíz, docs/implementation | Architecture; Security si afecta CI; persona distinta pendiente |
| Producto | FOUNDER-01 (Product + Accounting) | docs/product | UX, Architecture; persona distinta pendiente cuando el gate lo exija |
| Dominio y contratos | FOUNDER-01 (Architecture + Accounting) | docs/domain, packages/contracts | Backend, Data, Security; persona distinta pendiente |
| API y control | Backend | apps/api | Architecture, Security |
| Datos e ingesta | Data Engineering | workers, tests/golden | Accounting, Security |
| Web y UI | Web/UX | apps/web, packages/ui | Product, Accessibility/QA |
| Móvil | Mobile | apps/mobile | Security, Product |
| Plataforma | Platform/SRE | infra, Compose, CI | Security, Architecture |
| Seguridad y privacidad | FOUNDER-01 (Security/Privacy/Legal) | docs/security, tests/security | Architecture y Legal/Privacy; persona distinta obligatoria |
| Calidad | QA/SDET | docs/testing, tests | Owner del área |
| ADR y plan | FOUNDER-01 (Architecture/Product) | docs/adr, plan maestro | Owners afectados; `FOUNDER-01` no cuenta como segunda mirada |

## Revisiones independientes aún vacantes

| Control | Revisor requerido | Estado |
|---|---|---|
| Semántica financiera y ADR-026/027 | Accounting humano distinto | Pendiente |
| Migraciones, RLS y funciones privilegiadas | Database/Security humano distinto | Pendiente |
| Privacidad, retención y tratamiento | Privacy o Legal humano distinto | Pendiente |
| Release reproducible y cadena de suministro | Security y QA humanos distintos | Pendiente |

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
