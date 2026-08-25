---
task_id: FNC-AUD-001
status: REVIEW_PENDING
base_sha: 4983764
implementation_sha: c119f91
integration_sha: 56e72a5
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security/Privacy, Backend/Architecture, Web/Accessibility]
---

# Handoff FNC-AUD-001

## Resultado entregado

La plataforma web tiene un centro de accesos y auditoria para contadores que
trabajan con varias empresas. Cada empresa se consulta con su propio contexto de
autorizacion y RLS; la API no acepta una consulta SQL agregada entre empresas.
La vista identifica actor, accion, tipo de recurso, resultado e instante, con
filtros exactos y paginacion keyset estable.

No es SIEM, certificacion legal, detector de fraude ni export. No muestra el
`detail` append-only, `resource_ref`, valores de documentos, importes o secretos.

## Seguridad, privacidad y semantica

- El endpoint nuevo exige `audit.read` despues de resolver la empresa en el
  servidor. La consulta de repositorio no recibe `company_id`: depende del
  contexto PostgreSQL ya fijado y de su politica RLS.
- El cursor opaco solo representa `(occurred_at, audit_event_id)`, valida
  alfabeto, longitud, zona horaria y UUID y no contiene identidad ni datos
  financieros.
- Accion, resultado y tipo usan vocabulario/forma cerrados y limites de 100
  elementos por pagina. No existe busqueda libre sobre payload.
- La vista multiempresa llama company-by-company. Revocacion, restriccion y
  indisponibilidad son estados distintos y nunca se suman como cero actividad.
- El nombre del actor es dato de actividad laboral: solo llega a sujetos que ya
  poseen `audit.read`; su revision Privacy permanece pendiente.

## Evidencia ejecutada

- API dentro de la imagen reproducible: 111 pruebas unitarias, OK.
- PostgreSQL 17 + API + MinIO: 28 pruebas HTTP/autorizacion, OK; incluyen RLS,
  permiso, filtros fail-closed, actor y dos paginas sin solapamiento.
- Web: 28 archivos y 170 pruebas unitarias, OK; tipos, lint y build de produccion,
  OK. El build materializa `/auditoria` como ruta dinamica.
- Quality gate sobre el indice del commit funcional y `git diff --check`: OK,
  cero hallazgos.
- Navegador integrado: inicio de sesion sintetico y enlace de portafolio visibles.
  La inspeccion visual de la pagina completa no se declara superada: todos los
  contenedores del entorno terminaron simultaneamente con codigo 255 durante esa
  sesion. El mismo codigo paso luego las suites reproducibles y el stack se
  reconstruyo sano; el comportamiento del motor Docker/WSL queda como hallazgo
  de entorno, no como prueba omitida silenciosamente.

## Hallazgos de ejecucion

1. Un cursor solo acotado por longitud aun admitia caracteres fuera de base64url
   y podia convertir una URL manipulada en error interno. API y web ahora lo
   rechazan antes de consultar.
2. Un vacio multiempresa era ambiguo si una empresa habia sido revocada o estaba
   caida. La proyeccion conserva esos estados y la interfaz declara vista parcial.
3. La tabla append-only guarda detalle y referencia por necesidades de evidencia,
   pero la estacion operativa no los necesita. Una prueba de render garantiza que
   ambos permanecen fuera del DOM.
4. La prueba local amplia con Python del host no es una ejecucion valida porque
   ese interprete no tiene las dependencias bloqueadas. Se repitio en la imagen
   del proyecto y paso 111/111; el intento del host no se cuenta como evidencia.

## Revision requerida y limites

Security/Privacy debe revisar RLS, identidad laboral y minimizacion;
Backend/Architecture, keyset, joins, filtros y limites; Web/Accessibility, estados
parciales, lenguaje y recorrido visual. El implementador y `FOUNDER-01` no son
revisores independientes. Esta entrega no mueve S1-READY, DRG-00, DRG-01 ni
autoriza datos reales.

No hubo migracion, dependencia nueva, cambio financiero ni IA. La retencion y el
borrado siguen gobernados por el mapa de privacidad existente; este centro no
crea una segunda fuente de verdad ni un indice externo.

## Rollback

Revertir primero navegacion y pagina web, luego cliente y endpoint, y por ultimo
el helper de repositorio. El endpoint anterior `/audit` se preserva y delega al
nuevo paginador, por lo que el rollback no requiere transformar ni borrar datos.

## Rutas liberadas

Modulo y pruebas de auditoria API, repositorio/ruta, `db/tests/test_api_authorization.py`,
cliente/centro/pagina/pruebas web, navegacion y documentos de FNC-AUD-001.
