---
task_id: FNC-WEB-005
status: REVIEW_PENDING
base_sha: e4a5764
reservation_sha: 021bfc0
implementation_shas: [bc0856f, c2a95de]
tested_head_sha: c2a95de
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Product, Accounting, Privacy, Accessibility/QA]
---

# Handoff FNC-WEB-005 — cierre funcional de capacidades web

## Resultado

Cuenta, Ciclos, Calidad y Documentos ya presentan una experiencia completa y
coherente para la capacidad que existe hoy. El usuario puede distinguir qué
está disponible, qué depende de configuración y qué sigue bloqueado, sin que la
interfaz venda como activa una integración inexistente.

- Planes muestra consumo contra límites publicados, estado comercial,
  historial y preparación de proveedor, impuestos y checkout. No inventa
  precios ni permite un pago ficticio.
- Ciclos muestra preferencia, resumen e historial de entregas, intentos y causa
  de supresión. La entrega externa apagada permanece visible.
- Documentos contiene la matriz exacta CSV/XLSX/ODS/PDF y separa PDF con texto
  de OCR requerido; un PDF escaneado permanece en cuarentena y no se transmite.
- Calidad enumera las ocho reglas deterministas vigentes y explica que una
  señal no es acusación ni prueba de fraude.
- Un componente común expresa `available`, `conditional`, `blocked` y
  `planned` con texto y estructura, nunca sólo con color.

No se modificaron API, worker, base, autorización, RLS, dinero, semántica
financiera, contratos server-side, dependencias ni configuración de proveedor.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| Unitarias web | 55 archivos / 297 pruebas, OK |
| ESLint | OK |
| TypeScript | OK |
| Build Next de producción | OK |
| Chromium focal | 1/1, OK |
| Axe focal | 1/1 recorrido; Cuenta, Ciclos, Calidad y Documentos; 0 violaciones |
| Migraciones locales | head V0057, `mutated: false` |
| Runtime local | seis servicios healthy; datos exclusivamente sintéticos |

Comandos principales:

```text
npm run test:unit
npm run lint
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/web-capability-closure.spec.ts
npm run test:a11y -- tests/e2e/web-capability-closure.a11y.spec.ts
python -B -m tools.work_graph.validate
python -B -m tools.quality_gate.cli
```

El primer recorrido Axe detectó una superposición transitoria de dos landmarks
`main` mientras Ciclos cambiaba del boundary de carga al contenido final. Se
retiró el landmark del fallback y la prueba espera el encabezado propio de cada
ruta y exige exactamente un contenido principal antes de ejecutar Axe.

## Límites y revisión

Esta entrega cierra pantallas y estados web, no las dependencias externas. OCR,
correo transaccional, detección avanzada de fraude y cobro real continúan como
trabajo de backend/proveedor, por lo que el inventario funcional global conserva
88 % de implementación hasta que esas capacidades sean reales y verificables.

Product debe revisar lenguaje y prioridades; Accounting la presentación de
límites y señales; Privacy el texto de transmisión y datos; Accessibility/QA
teclado, zoom y contraste percibido. Ninguna firma se presume. DRG-00, DRG-01 y
GA-01 no cambian y ningún dato financiero real fue autorizado.

Las rutas quedan liberadas. El rollback revierte `c2a95de` y `bc0856f`; no hay
migraciones, datos ni recursos externos que revertir.
