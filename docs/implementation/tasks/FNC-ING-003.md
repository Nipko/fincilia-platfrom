---
id: FNC-ING-003
title: Ingesta ligada a fuente y centro historico de documentos
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 454da9db893c6974b246cfa94137896c69488b4e
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Data, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Cerrar la brecha entre la fuente elegida en la web y la evidencia persistida. Una
carga nueva queda ligada de forma inmutable a una fuente activa resuelta por el
servidor, y un contador puede consultar un centro de documentos paginado con
busqueda, filtros y estado operativo sin abrir cada archivo.

# Autoridad

- El modelo canonico declara `source_artifact.data_source_id` no nulo e
  inmutable; V0009 ya agrego la relacion company-scoped y dejo nulo solo para
  evidencia historica que no puede atribuirse honestamente.
- ADR-003 mantiene `company` como frontera. La ruta nunca acepta una fuente que
  no sea visible dentro del contexto autorizado de la empresa.
- ADR-004 conserva una sola copia de bytes por clave opaca; dos recepciones
  logicas pueden referir el mismo contenido sin mezclar sus fuentes.
- ADR-015 separa identidad de entrega, evidencia y evento economico. Mismos bytes
  en fuentes distintas no prueban que sea la misma recepcion logica.

# Rutas reservadas

- `db/migrations/V0038__source_bound_artifact_intake.sql` y pruebas de migracion
  y PostgreSQL focales.
- `apps/api/src/fincilia_api/repository.py`, `routes.py` y pruebas de documentos.
- `apps/web/src/lib/api.ts`, BFF de carga, pagina de empresa, nuevo centro de
  documentos y sus pruebas unitarias.
- `apps/web/tests/e2e` para carga por fuente, historico, paginacion y Axe.
- Ficha, handoff, backlog, fase y grafo por Integration Steward.

# Fuera de alcance

- Atribuir una fuente a filas legacy nulas, mutar evidencia o borrar documentos.
- OCR/PDF, conectores, carga masiva, IA, auto-mapeo, auto-match o cierre.
- Consolidar importes entre empresas o presentar conteos como saldo financiero.
- Cambiar ADR aceptados, promover gates o sustituir revision independiente.

# Criterios de aceptacion

- **AC-01.** La API exige `data_source_id` en cada carga nueva y valida bajo RLS
  que exista, pertenezca a la empresa y este activa. Omitirla, usar otra empresa
  o una fuente inactiva falla sin almacenar, encolar ni auditar valores.
- **AC-02.** `source_artifact.data_source_id` se persiste en el INSERT y no puede
  cambiar por el rol de aplicacion. Las filas legacy nulas siguen legibles y se
  rotulan como fuente historica no registrada; nunca se rellenan por inferencia.
- **AC-03.** La idempotencia dura usa empresa, fuente y SHA-256. Repetir los
  mismos bytes en la misma fuente devuelve la misma entrega; subirlos a otra
  fuente crea otra recepcion logica sin duplicar ni reescribir el objeto.
- **AC-04.** El BFF transmite la fuente validada a la API; no basta con conservar
  el identificador en la URL del navegador. Una llamada directa no puede saltar
  la regla.
- **AC-05.** El API de historico usa paginacion keyset estable y limites cerrados;
  permite filtrar por fuente, zona efectiva, estado de procesamiento y nombre
  acotado. Todos los filtros se aplican dentro de PostgreSQL bajo RLS.
- **AC-06.** Cada elemento presenta fuente, recepcion, tipo, zona, ultimo trabajo
  y version canonica mas reciente cuando existe. Los conteos son operativos y no
  agregan importes, descripciones, referencias ni celdas.
- **AC-07.** La web ofrece una pagina direccionable con filtros preservados,
  estados vacio/sin acceso/error distintos, paginacion anterior/siguiente y
  enlace al expediente exacto. Es operable con teclado y cumple Axe.
- **AC-08.** Negativas cross-company son neutrales; nombre y cursor malformados
  fallan con codigos estables. La lectura no expone object key, sujeto, hallazgos
  sensibles ni valores financieros.
- **AC-09.** Migracion limpia y replay, unitarias API/web, PostgreSQL real,
  Chromium, Axe, lint, tipos, build, quality gate y CI pasan. S1-READY no cambia.

# Rollout y rollback

Rollout local y sintetico. V0038 reemplaza la unicidad antigua por identidad por
fuente para filas nuevas y conserva una guarda separada para legacy nulo. El
rollback funcional retira el nuevo centro y vuelve a ocultar la fuente, pero no
desasocia recepciones ya creadas. La migracion solo se corrige hacia delante.
