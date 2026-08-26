---
id: FNC-QA-010
title: Estabilizacion de CI y monitoreo ejecutable de dependencias
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 6937f6e
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [QA, Database, Security, Platform]
---

# Resultado esperado

Dejar verde el workflow `fincilia-ci` de `main` sin relajar RLS, auditoria,
inmutabilidad, pruebas ni limites de rendimiento. Las suites que comparten una
base desechable deben poseer y retirar unicamente sus fixtures. El inventario de
funciones debe reflejar renames de migraciones y Dependabot solo debe declarar
alcances que GitHub puede procesar realmente.

# Diagnostico confirmado

- `ApiAuthorizationTests` crea artifact, capability y processing run sin
  retirarlos; una prueba posterior no puede transferir el engagement por el FK.
- `IssuedAuthorizationContextTests` intenta borrar todos los contextos de dos
  empresas, incluidos los de otras suites y sus processing runs.
- Dos pruebas de privacidad buscan nombres en todo el evento de auditoria y
  confunden el nombre legitimo del actor con el payload de candidatos/asignacion.
- El inventario ACL solo reconoce `CREATE FUNCTION`; V0033 renombra una funcion
  valida y por eso la base tiene un nombre que el extractor no declara.
- Cuatro entradas Docker de Dependabot apuntan a directorios con Compose pero
  sin Dockerfile/Kubernetes; GitHub termina con `dependency_file_not_found`.

# Rutas y limites

Se reservan las cuatro suites DB afectadas, `.github/dependabot.yml`, baseline y
herramientas de supply chain, contrato del lifecycle local, esta ficha, handoff
y registros centrales. La ampliacion al contrato local cubre un hallazgo de la
ejecucion: el E2E de cierre dependia de residuos de las suites PostgreSQL y debe
preparar su fixture sintetica de forma explicita despues de ellas. No se editaran
V0001-V0034, codigo financiero productivo, permisos, RLS, auditoria, datos
reales, gates, mobile, IA ni dependencias de aplicacion.

# Criterios de aceptacion

- **AC-01.** Cada suite retira solo artifacts, runs y contexts que ella creo, en
  orden referencial, y una doble ejecucion no depende de residuos.
- **AC-02.** La auditoria sigue mostrando al actor, pero el payload `detail` de
  candidatos y asignaciones no contiene nombres ni contactos.
- **AC-03.** El inventario de funciones interpreta `CREATE`, `OR REPLACE` y
  `ALTER FUNCTION ... RENAME TO` en orden y coincide con PostgreSQL real.
- **AC-04.** Dependabot no contiene directorios que producen
  `dependency_file_not_found`; la falta de monitor automatico para digests de
  Compose queda reportada como gap, no como cobertura ficticia.
- **AC-05.** Suite DB completa, contratos, supply-chain, web unitaria, quality
  gate y `fincilia-ci` sobre `main` quedan verdes.
- **AC-06.** Las PR automaticas anteriores se reconcilian solo despues de CI
  verde; ninguna actualizacion mayor se fusiona sin prueba propia.
- **AC-07.** El E2E de cierre prepara su fixture sintetica despues de la suite
  PostgreSQL y antes del navegador; el contrato del workflow falla si se omite o
  se reordena esa preparacion.

# Rollback

Revertir los commits de FNC-QA-010 restaura exclusivamente fixtures, extractor
y configuracion de automatizacion. No hay migracion ni ledger que revertir.
QA, Database, Security y Platform mantienen revision independiente pendiente.
