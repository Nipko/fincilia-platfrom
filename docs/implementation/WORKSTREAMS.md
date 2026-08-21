# Workstreams y división entre agentes

## Carriles

| Carril | Responsabilidad | Rutas habituales |
|---|---|---|
| A0 Coordinator | Estado global, dependencias, gates e integración | raíz, docs/implementation |
| A1 Product | PRD, ICP, investigación y calendario | docs/product |
| A2 Domain | Dominio, ADR, contratos y esquemas | docs/domain, docs/architecture, packages/contracts |
| A3 Security | Seguridad, privacidad y pruebas negativas | docs/security, tests/security |
| A4 Platform | Toolchain, Docker, CI, scripts y lockfiles | infra, scripts, configuración raíz |
| A5 DataQA | Corpus sintético, fixtures, golden y harness | tests/fixtures, tests/golden, docs/testing |
| A6 UX | Design system, prototipos y usabilidad | docs/ux, apps/web, packages/ui |
| A7 Business | Legal, marca, proveedores y presupuesto | docs/business |

## Olas de ejecución

~~~text
Ola 0
├── A0: gobierno, repositorio y asignación de owners
├── A1: PRD y protocolo de investigación
├── A2: tenancy, dominio, contratos y C4
├── A3: RBAC, DFD y threat model
├── A5: taxonomía y política de datos sintéticos
└── A6: arquitectura de información

Ola 1, después de contratos base
├── A4: stack, Compose y CI sintético
├── A2: spike auth-context, RLS y outbox
├── A5: corpus/golden harness
└── A6: prototipo Portafolio/Clean/Close

Ola 2
└── Integración, pruebas contractuales y revisión S1-READY
~~~

## Regla de asignación

Cada tarea declara:

- Un implementador.
- Un accountable owner humano.
- Un revisor independiente cuando sea sensible.
- Rutas de escritura exclusivas.
- Dependencias ya integradas o mocks acordados.
- Evidencia y comandos de validación.

A0 es el único que cambia estados globales. A4 es el único que integra lockfiles y configuración raíz. A2 es owner de contratos, esquema y migraciones.

## Orden de integración

Decisión/ADR → contrato → esquema/migración → productor → consumidor → E2E.

No se asignan en paralelo tareas que escriban las mismas rutas. En filesystem compartido, el coordinador entrega scopes disjuntos y conserva Git.

