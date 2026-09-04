---
task: FNC-PLT-017
status: REVIEW_PENDING
base_sha: 4687604
release_sha: 89145a75a1e16dc476e42f78af370f826aff037f
evidence_commit: 04aef1fbd51165e4819b65733311ef96c3f7ce11
data_ceiling: synthetic_only_until_gate
gate_effect: evidence_only
independent_reviewers: [Database, Security, Platform/SRE, QA]
---

# Handoff FNC-PLT-017 — bootstrap y migraciones temporales en AWS

## Resultado

Se demostró en la cuenta AWS autorizada el ciclo temporal completo
`cold → warm en cero → secretos → bootstrap → migraciones → cold`. Los cuatro
secretos de runtime se prepararon sin exponer valores; el bootstrap de roles y
el migrador terminaron en orden con código cero. Se aplicaron 57 migraciones
hasta `V0057`, sin ejecutar semillas, API o worker.

El cierre eliminó los 25 recursos efímeros autorizados, solicitó detener RDS y
conservó storage, claves, secretos, imágenes, logs, backups y auditoría. El plan
posterior quedó en 148 `no-op`, sin altas, cambios ni borrados. La foundation
permanece completa 36/36, el runtime ausente 0/11, NAT en cero y
`real_data_authorized=false`.

## Release y cadena de suministro

- Publicación inmutable `33915858477`, exitosa sobre
  `89145a75a1e16dc476e42f78af370f826aff037f`; API, web y worker fueron
  construidos, probados, escaneados y atestados antes de registrar sus digests.
- Candidato reproducible `33917287024`, exitoso sobre el mismo SHA.
- CI de integración `33921139146`, exitoso sobre `04aef1f`: todos los
  carriles obligatorios quedaron verdes; el carril de rendimiento bajo demanda
  permaneció omitido por diseño.
- Bundle, checkout y archivo verificados fuera del runner; procedencia SLSA y
  SBOM SPDX revalidadas contra workflow, rama y source digest exactos.
- La proyección durable vigente está en
  `docs/implementation/evidence/FNC-GAT-005-SUPPLY-CHAIN.json`.

## Hallazgos resueltos durante la ejecución

1. La aplicación podía materializarse antes del listener HTTPS. Ahora ambos
   requieren certificado listo y el servicio depende del listener.
2. La lectura de outputs OpenTofu no heredaba el perfil AWS. El controlador
   suministra perfil y región de forma explícita y cerrada.
3. AWS CLI no admite de forma fiable el JSON completo por `/dev/stdin`. Sólo el
   valor secreto viaja por stdin; selectores no sensibles usan JSON acotado.
4. PrivateLink con DNS privado bloqueaba al task de bootstrap porque su SG sólo
   aceptaba al worker. El SG de aplicación recibe HTTPS mínimo hacia endpoints.
5. El secreto maestro administrado por RDS sólo contiene usuario y contraseña.
   Host y puerto llegan desde atributos no secretos de la instancia.
6. RDS generó una contraseña maestra imprimible de 28 bytes. El bootstrap acepta
   ese mínimo exclusivamente para el master; los roles de runtime conservan 32.

## Hallazgo abierto

Un replay lanzado después de aplicar `V0057` volvió a ejecutar primero el
bootstrap y terminó con código uno. La clasificación redactada encontró una
denegación de permisos; no se recuperaron mensajes, consultas, DSN, ARN ni
credenciales. La ejecución inicial y el migrador habían terminado previamente
con código cero, por lo que este hallazgo no invalida la migración aplicada,
pero mantiene `FNC-PLT-016` en progreso: su criterio de idempotencia debe
demostrarse también después del esquema completo. No se ampliaron privilegios
para forzar el replay.

## Evidencia y verificaciones

- Plan warm inicial seguro y aplicación de task definitions por digest exacto.
- `prepare-secrets`: cuatro contenedores preparados, credenciales no expuestas,
  datos reales y valores de gate en falso.
- ECS one-off: bootstrap inicial `0`; migrador posterior `0`.
- Estado final: foundation 36/36; runtime 0/11; NAT 0; ALB y Valkey ausentes;
  servicios en cero; RDS detenido.
- Plan cold posterior: 148 `no-op`, validado.
- Controlador de bootstrap y contrato AWS: 54 pruebas verdes; roles: 6 pruebas
  verdes en contenedor con una integración local omitida sin DSN desechable.
- `tools.drg01_readiness`: 19 pruebas, modelo válido, 13 blockers y
  `real_data_authorized=false`.
- El quality gate del commit de evidencia pasó sobre el índice Git.

## Límites y revisión

Este ejercicio no acepta DRG-00/DRG-01, no admite documentos financieros reales,
no habilita tráfico público y no sustituye revisiones independientes. Database,
Security, Platform/SRE y QA deben revisar la separación de roles, conectividad,
evidencia de migración y cierre frío. El Founder no cuenta como su propia segunda
mirada.

## Rollback

El estado actual ya es el rollback operativo: runtime ausente y RDS detenido.
No usar `tofu destroy`. Si se revierte código, conservar la base, las versiones
de secretos, logs y backups; cualquier cambio de roles o esquema requiere una
migración de reversión revisada y nunca borrado manual.
