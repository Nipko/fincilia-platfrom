---
id: FNC-ING-004
title: Bandeja web de carga multiple por fuente
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 8aaaca645ee0b33884a202971a5c09a2d7dbbdbe
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accessibility/QA, Security, Backend/Architecture]
---

# Resultado esperado

Un contador puede seleccionar varios documentos de una misma fuente, conocer
antes de enviar cuales son validos y cargar el lote con progreso y resultado por
archivo. Un fallo no oculta ni revierte los exitos de los otros documentos, y
cada resultado conserva un enlace al expediente exacto.

# Autoridad y dependencias

- FNC-ING-003 fija la fuente autoritativa, la idempotencia y el centro documental.
- ADR-003 mantiene `company` como frontera y exige autorizacion server-side.
- ADR-004 conserva cada original en object storage privado por zonas.
- ADR-015 separa recepcion logica, evidencia y evento economico.
- La API y el BFF existentes siguen siendo la autoridad de cada carga individual.

# Rutas reservadas

- `apps/web/src/app/empresas/[companyId]/upload.tsx` y su prueba unitaria.
- `apps/web/src/app/empresas/[companyId]/documentos/page.tsx` y sus pruebas.
- `apps/web/src/app/globals.css` solo para la presentacion de la bandeja.
- `apps/web/tests/e2e` para el recorrido Chromium y Axe focal.
- Ficha, handoff, backlog, fase y grafo por Integration Steward.

# Fuera de alcance

- Endpoint batch, atomicidad entre documentos, ZIP como contenedor de multiples
  documentos, carga de carpetas o reanudacion byte a byte.
- OCR/PDF, conectores, IA, auto-mapeo, auto-match, importes o cierre.
- Inferir una fuente, mezclar fuentes dentro de un lote o cambiar limites del API.
- Promover gates o sustituir revisiones independientes.

# Criterios de aceptacion

- **AC-01.** El selector admite de 1 a 10 archivos y conserva visible la fuente
  elegida. Nunca elige una fuente por defecto si el usuario no la indico.
- **AC-02.** Cada archivo se valida antes de la red: nombre no vacio, contenido,
  maximo 25 MiB y maximo 100 MiB por lote. Los invalidos se muestran sin impedir
  enviar los validos.
- **AC-03.** Como maximo dos cargas estan en vuelo. Cada request usa el BFF
  individual y la misma fuente; no se crea un contrato batch ni se confia en el
  navegador para autorizarla.
- **AC-04.** La bandeja distingue pendiente, subiendo, completado, ya recibido,
  fallido, invalido y cancelado. Cada exito tiene enlace al expediente exacto y
  los fallos reintentables no obligan a repetir los exitos.
- **AC-05.** Cancelar aborta trabajos en vuelo y no inicia los pendientes. Una
  sesion vencida aborta el lote y navega a ingreso; ningun cuerpo upstream se
  refleja en la interfaz.
- **AC-06.** Una sola carga exitosa conserva el recorrido existente hacia el
  expediente. Un lote permanece en el centro, actualiza el historico una sola vez
  y permite abrir cualquier resultado.
- **AC-07.** El componente funciona con teclado, expone progreso y resumen a
  tecnologias de asistencia y cumple Axe. Sin hidratacion no envia un formulario
  nativo incapaz de aplicar los controles.
- **AC-08.** Unitarias, tipos, lint, build, Chromium, Axe, quality gate y CI pasan
  con datos sinteticos. S1-READY no cambia.

# Rollout y rollback

Es una mejora web expand-only sin migracion ni dependencia nueva. El rollback
restaura el selector unitario; las recepciones ya confirmadas permanecen
intactas y direccionables porque cada envio usa el contrato individual vigente.
