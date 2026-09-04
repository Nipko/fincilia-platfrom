---
id: FNC-SUP-004
title: Cobertura cerrada de fuentes que entran en imágenes de release
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 7772605688e7226720f499559a3953c4c4612d7b
gate: DRG-00/DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Security, QA, Platform/SRE]
---

# Resultado esperado

La evidencia del candidato liga todos los orígenes locales que Docker copia en
API, web y worker. Añadir un nuevo `COPY` fuera de los árboles declarados o usar
una forma que el extractor no entienda impide crear la evidencia.

# Alcance autorizado

Corrección expand-only del contrato `FNC-REL-001`, su validador, pruebas y
documentación; registros centrales y handoff por el Integration Steward. No
modifica imágenes, dependencias, runtime, datos, gates ni autorizaciones.

# Criterios de aceptación

1. Los Dockerfiles de los tres artefactos se descubren y validan siempre.
2. Cada origen local `COPY` existe y está cubierto por un input adjudicado.
3. Las copias entre etapas se distinguen de las fuentes del repositorio.
4. `ADD`, rutas dinámicas, traversal, solapamientos y sintaxis no soportada
   fallan cerrados con pruebas adversariales.
5. Los árboles declarados cubren locks, tests, configuración, migraciones,
   bootstrap y fuentes que hoy entran en las imágenes.
6. El candidato y su evidencia se regeneran sobre el commit corregido; ninguna
   propiedad humana o autorización de datos cambia.

# Verificación

Unitarias y mutaciones del extractor, generación/verificación del candidato,
quality gate, catálogo, work graph y CI sobre el commit entregado.

# Rollback

Revertir esta corrección devuelve una evidencia incompleta y por ello invalida
los candidatos posteriores; no afecta datos ni recursos desplegados.
