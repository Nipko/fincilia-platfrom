---
task_id: FNC-UX-003
revision: R1
status: REVIEW_PENDING
base_sha: 0535499e96b4432086dc5ccc935105b4f91c10b2
implementation_shas: [7661def, 1faef05]
tested_head_sha: 1faef05
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Product/UX, Accessibility/QA, Legal/Brand]
---

# Handoff FNC-UX-003-R1 — identidad visual Fincilia R2

## Resultado integrado

La plataforma adopta el concepto **Desfase exacto**: dos documentos a distinta
altura y una fila verde que conecta ambos, representando el cotejo entre fuentes
heterogeneas. El simbolo se integra como componente accesible en el shell web y
como familia de activos para favicon, PWA, Apple touch icon y la consola OAuth de
Google. No se agregaron dependencias ni se modificaron API, permisos, migraciones
o semantica financiera.

Los activos fuente son SVG; las exportaciones raster se generaron a partir de la
misma geometria. La variante invertida mantiene contraste sobre la navegacion
oscura, y la monocromatica sirve para usos de una tinta.

## Rutas y activos

- `apps/web/src/components/brand-mark.tsx`: componente semantico y reutilizable.
- `apps/web/src/app/globals.css`: color, escala y variantes del simbolo.
- `apps/web/src/app/layout.tsx`: iconos, manifest y color de interfaz.
- `apps/web/src/app/icon.svg` y `apps/web/src/app/manifest.ts`: metadatos Next.
- `apps/web/public/brand/**`: marca principal, invertida, monocromatica, icono de
  aplicacion y PNG cuadrado para Google OAuth.
- `apps/web/public/icons/**`: iconos 192, 512 y Apple touch.
- Pruebas unitarias y E2E de identidad bajo `apps/web`.

## Evidencia

- TypeScript, ESLint, 264 pruebas unitarias y build de produccion: verdes.
- Inspeccion visual real en escritorio y viewport 390x844: simbolo legible,
  proporcion estable y sin overflow.
- `TST-UX-BRAND-001`: componente, manifest, favicon y activo OAuth servidos desde
  una compilacion de produccion.
- Axe sobre `/entrar`: sin impactos serios o criticos.
- Quality gate sobre el indice Git: sin hallazgos.

## Limites y revisiones pendientes

La eleccion visual del Founder autoriza su implementacion en la plataforma, pero
no equivale a busqueda marcaria ni a autorizacion legal de registro. FNC-BRD-001
y la revision independiente Legal/Brand permanecen pendientes. El cambio tampoco
acepta S1-READY, DRG-00, DRG-01 ni habilita datos reales.

## Google OAuth

Usar `apps/web/public/brand/fincilia-google-oauth.png` como logotipo de la
aplicacion OAuth. El activo es cuadrado, no incluye datos personales y comparte
la geometria de produccion; su carga en Google sigue siendo una accion humana.

## Rollback

Revertir los commits declarados en `implementation_shas` restaura la identidad
anterior sin afectar cuentas, sesiones, datos, API, base de datos ni workers.
