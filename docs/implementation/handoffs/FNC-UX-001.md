---
task: FNC-UX-001
status: REVIEW_PENDING
base_sha: 3989ea3
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-UX-001

## Entrega

- Arquitectura de información multiempresa y company-scoped.
- Prototipo navegable de Portafolio, Importación, Conciliación, Cierre, Señales, Informes y companion móvil.
- Import Studio con Original, Extracción fiel, Dataset limpio y Esquema canónico.
- Linaje visible a hoja/fila/columna/celda y fecha ambigua no resuelta silenciosamente.
- Estados vacío, error, degradado, parcial y ambiguo simulables.
- Contrato estático de accesibilidad, límites de producto y operación offline.

## Verificación

```powershell
python -m tools.ux_contract.validate
python -m unittest tools.ux_contract.test_validate -v
python -m http.server 4173 --directory docs/ux/prototypes
```

Resultado observado: 8/8 pruebas de contrato pasan; smoke HTTP devuelve 200 y confirma
Import Studio, techo sintético y skip link. La inspección visual automatizada quedó
pendiente porque el runtime de navegador local no inicializó; no se presenta como ejecutada.

## Revisión requerida

Product debe validar prioridad y lenguaje; Accessibility debe revisar WCAG 2.2 AA con
tecnologías de asistencia; Accounting debe revisar ecuaciones, cierre y materialidad. Las
pruebas de usabilidad con contadores/PYMEs pertenecen a FNC-UX-002.
