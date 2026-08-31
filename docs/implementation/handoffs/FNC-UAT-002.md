---
task_id: FNC-UAT-002
status: REVIEW_PENDING
base_sha: ba91e70
implementation_shas: [1f4f2d7, 2bc936a]
tested_sha: 2bc936a
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [QA, Platform/SRE, Security]
---

# Handoff FNC-UAT-002 — aceptacion integral desde esquema vacio

## Resultado

El laboratorio desechable demuestra el recorrido de una instalacion nueva sin
usar la semilla de demo: crea una base vacia, aplica V0001-V0052, levanta API y
web, registra una identidad sintetica y crea su primer espacio. Elimina despues
ese runtime y ejecuta la regresion sembrada completa sobre una segunda base
limpia. Ninguna fase conecta, lee o modifica `fincilia-local`.

La secuencia fail-closed vive en `infra/local/test-web-isolated.ps1`: valida
constantes, limpia solo recursos allowlisted, construye, migra, verifica el alta
vacia, destruye la primera fase, crea la fase sembrada, ejecuta backend,
PostgreSQL, Chromium y Axe, y vuelve a probar la ausencia exacta de recursos.
El cleanup permanece en `finally` y tambien fue observado en fallos intermedios.

## Evidencia reproducible

Dos ejecuciones consecutivas sobre `2bc936a` terminaron limpias:

| Fase por corrida | Resultado |
|---|---|
| Esquema vacio | V0001-V0052 + alta publica desde cero: 1 prueba Chromium |
| Backend | 31 API + 16 dominio de conciliacion: 47 pruebas |
| PostgreSQL real | 9 pruebas focales de conciliacion y administracion |
| Navegador sembrado | 42 Chromium |
| Accesibilidad | 26 Axe |
| Cleanup | 0 contenedores, volumenes y redes E2E restantes |
| Duracion | 250,7 s y 247,1 s |

Comando principal:

```powershell
.\infra\local\test-web-isolated.ps1
```

Adicionalmente pasaron las 21 pruebas del contrato de runtime aislado y su
validador estructural. El runner invoca los dos ficheros backend reales y falla
si se omite, reordena o reemplaza una fase requerida.

## Hallazgos encontrados ejecutando

1. La suite backend no era importable como modulo desde la imagen productiva;
   el runner ejecuta ahora los dos scripts de prueba presentes en `/app/tests`.
2. La primera variante de una migracion comentaba una funcion despues de ceder
   su propiedad, por lo que el migrador ya no tenia autoridad. El comentario se
   fija antes del cambio de owner y la instalacion vacia lo prueba.
3. El fallo inicial del backend propago exit no-cero solo despues de eliminar
   todos los recursos E2E, confirmando el camino adverso del `finally`.

## Limites, revision y rollback

Toda identidad, empresa, archivo y movimiento usado por el runner es sintetico.
No hay evidencia sobre documentos financieros reales, volumen productivo, edge
publico ni operacion piloto. DRG-00 y DRG-01 permanecen cerrados.

QA debe revisar los recorridos y assertions; Platform/SRE el aislamiento y el
lifecycle destructivo exacto; Security que ninguna URL, volumen o red alcance la
demo persistente. El implementador no cuenta como revisor independiente.

Revertir `2bc936a` y `1f4f2d7` retira el runner ampliado y su contrato. El
rollback no debe ejecutar `down --volumes` contra `fincilia-local`.

## Rutas liberadas

Runner y documentacion local, contrato y validador del runtime aislado, pruebas
E2E de alta/cierre, ficha, handoff y registros centrales de FNC-UAT-002.
