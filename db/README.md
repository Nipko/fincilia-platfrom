# Base de datos

Este directorio está reservado para FNC-PLT-005 y tareas de dominio posteriores a ADR-002/003.

Estructura prevista:

~~~text
db/
├── migrations/
├── policies/
├── tests/
│   ├── migrations/
│   ├── rls/
│   └── invariants/
└── seeds/
    └── synthetic/
~~~

No crear migraciones productivas antes de:

- ADR-002 y ADR-003 aceptados.
- Owner de migraciones asignado.
- Modelo tenancy y diccionario revisados.
- Banda de numeración reservada.

La aplicación y workers no serán owner, superuser ni BYPASSRLS.

