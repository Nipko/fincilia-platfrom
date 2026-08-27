---
task_id: FNC-WEB-004
status: REVIEW_PENDING
base_sha: 83d2392118136c547e63f1cda53db1f4bf68ad87
reservation_sha: 1f1e067ad073dad5a1f85a991728d42400aac534
implementation_shas: [dfd814b, 36bdc79, 136c422, 2a4f595]
tested_head_sha: 2a4f595191d4f2feee44a930152f3545f10cfc37
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Product, Accessibility/QA]
---

# Handoff FNC-WEB-004 — sistema visual y navegacion contextual web

## Resultado

La plataforma web tiene ahora una identidad y una jerarquia de navegacion
coherentes desde el ingreso hasta el trabajo por empresa. La barra persistente
de producto incluye marca, entorno y, con sesion activa, acceso a Portafolio,
Revisiones, Ciclos, Calidad, Informes, Cierre y Auditoria. El menu indica la
seccion actual y en movil usa desplazamiento local, sin ensanchar la pagina.

El portafolio dejo de presentar siete enlaces equivalentes en una misma linea:
ahora funciona como centro de trabajo, agrupa cada destino con proposito y
separa la vista transversal de las empresas. La portada de empresa conserva su
contexto, presenta sus modulos como navegacion operativa y prioriza carga y
documentos. Roles y permisos permanecen consultables, pero dentro de un detalle
secundario llamado `Acceso de esta cuenta`.

El cambio es solo web. No modifica API, base, permisos, RLS, SoD, contratos,
calculos, estados financieros ni gates. El menu recibe del servidor un booleano
de sesion; el token nunca llega al componente cliente y cada destino conserva
la autorizacion server-side existente.

## Sistema visual

- Marca compacta propia, barra sticky y etiqueta visible de entorno local.
- Escala tipografica, paleta, superficies, bordes, sombras, radios y espaciado
  unificados sin dependencia externa.
- Ancho de trabajo ampliado de 62 a 88 rem para tablas y estaciones densas.
- Tarjetas de accion, metricas, estados, formularios y tablas con jerarquia,
  hover y focus visibles; el significado no depende exclusivamente del color.
- Acceso redisenado como composicion de valor + formulario, con cuentas demo en
  un detalle desplegable para reducir ruido.
- Portafolio de dos columnas en escritorio y una en movil; navegacion de empresa
  fluida y despues de 448 px en una sola columna.
- Dark mode existente preservado y `prefers-reduced-motion` respetado.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| ESLint | OK |
| TypeScript | OK |
| Build Next de produccion | OK |
| Unitarias web completas | 35 archivos / 227 pruebas, OK |
| Chromium aislado final | 34/34, OK |
| Axe aislado final | 21/21, OK |
| Shell responsive nuevo | acceso, portafolio y empresa a 390 x 844, OK y sin overflow global |
| Limpieza E2E | `fincilia-e2e` sin contenedores, redes ni volumenes residuales |
| Navegador local real | acceso, portafolio, empresa y conciliacion revisados en escritorio y movil; consola sin warnings/errores |

Comandos principales:

```text
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test:unit
npm --prefix apps/web run build
npm --prefix apps/web exec playwright test tests/e2e/visual-shell.spec.ts --project=chromium
infra/local/test-web-isolated.ps1
python -B -m tools.work_graph.validate
python -B -m tools.test_catalog.cli validate
python -B -m tools.quality_gate.cli
```

La primera regresion detecto que dos pruebas de roles asumian que los permisos
tecnicos estaban siempre expuestos. Se corrigieron para abrir el detalle y
comprobar las mismas capacidades, sin relajar ninguna expectativa. La segunda
detecto un selector no exacto entre `Documentos` y `Abrir centro de documentos`;
se hizo exacto. El tercer entorno aislado termino con 55/55 recorridos verdes y
cleanup verificado en 173.6 segundos.

## Revision y limites

Product debe revisar densidad, lenguaje, prioridades y utilidad de los centros.
Accessibility/QA debe revisar teclado, zoom, contraste percibido y los cortes
responsive adicionales a la automatizacion. Ninguna de esas firmas se inventa;
la tarea queda `review_pending`.

El shell consulta la cookie en el layout para decidir si presenta el menu y por
eso todas las rutas Next quedan renderizadas dinamicamente. Es una consecuencia
deliberada y reversible de no exponer enlaces privados en el ingreso ni basar el
menu en estado cliente no validado.

El rollback revierte `dfd814b`, `36bdc79`, `136c422` y `2a4f595`; no hay datos,
migraciones ni artefactos financieros que revertir. Las rutas quedan liberadas
con este handoff y S1-READY no cambia de estado.
