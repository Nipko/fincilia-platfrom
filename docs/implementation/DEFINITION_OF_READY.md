# Definition of Ready

Una tarea solo puede pasar a Ready si cumple:

- ID estable, título y épica.
- Resultado observable y referencia exacta al plan.
- Owner humano, implementador y revisores.
- Dependencias resueltas o mocks/contratos acordados.
- Rutas de escritura y rutas prohibidas.
- Criterios de aceptación medibles.
- Datos permitidos por gate.
- Impacto financiero, tenancy, seguridad, privacidad, IA y accesibilidad evaluado.
- NFR y casos negativos aplicables.
- Contrato API/evento/esquema esperado.
- Migración, feature flag y rollback cuando correspondan.
- Comandos de validación esperados.
- Ninguna decisión bloqueante sin owner y fecha.

Una tarea que cruza varias fronteras protegidas se divide o integra primero un contrato independiente.

Draftable no significa Ready: permite producir un borrador que todavía requiere aprobación o dependencia.

