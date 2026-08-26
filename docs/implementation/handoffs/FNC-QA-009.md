---
task_id: FNC-QA-009
status: REVIEW_PENDING
base_sha: 8846157
reservation_sha: 282e349
contract_sha: 7270f2a
runtime_sha: b835620
fixture_sha: 406816b
ci_sha: b02fbd7
browser_tested_sha: 406816b
contract_tested_sha: b02fbd7
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [QA, Platform/SRE, Security]
---

# Handoff FNC-QA-009 — regresion web aislada de la demo

## Resultado

La regresion web completa ya no usa la base persistente del fundador. El comando
`infra/local/test-web-isolated.ps1` crea `fincilia-e2e` con volumenes, redes y
puertos exclusivos, aplica V0001-V0033, siembra solo datos sinteticos, prepara
evidencia de aceptacion, ejecuta Chromium y Axe desde Windows y elimina todos sus
recursos desde `finally` tanto en exito como en fallo.

El runtime persistente conserva sus defaults y su lifecycle no destructivo. Los
contenedores E2E se inspeccionan antes del navegador: solo pueden montar los dos
volumenes allowlisted, pertenecer a las dos redes E2E y publicar en loopback. Los
nombres destructivos no son parametros ni variables aportadas por el invocador.

## Recursos y secuencia exacta

| Frontera | Demo persistente | Regresion desechable |
|---|---|---|
| Proyecto | `fincilia-local` | `fincilia-e2e` |
| PostgreSQL | `fincilia_local_pgdata` | `fincilia_e2e_pgdata` |
| MinIO | `fincilia_local_objectdata` | `fincilia_e2e_objectdata` |
| Redes | `fincilia_local_private`, `fincilia_local_edge` | `fincilia_e2e_private`, `fincilia_e2e_edge` |
| Web/API | 53000 / 58080 | 53100 / 58180 |
| MinIO | 59000 / 59001 | 59100 / 59101 |

La secuencia cerrada es: validar constantes, preclean exacto, build, dependencias,
migraciones, semilla de demo, fixture de aceptacion, aplicaciones, readiness,
inspeccion de aislamiento, Chromium, Axe, cleanup y prueba de ausencia. El helper
WSL no ejecuta Node; el orquestador PowerShell fija ambas URL E2E para Playwright
y restaura el entorno original al salir.

## Hallazgos encontrados ejecutando

1. Seis recorridos usaban `FINCILIA_E2E_BASE_URL` para la web pero caian al API
   persistente 58080. Con la demo apagada fallaban por `ECONNREFUSED`; ahora el
   orquestador fija tambien `FINCILIA_E2E_API_URL=...:58180`.
2. La aparente repetibilidad de QA-008 ocultaba una dependencia en residuos:
   datasets publicados y expedientes eran creados por suites PostgreSQL previas.
   El fixture E2E ahora crea dos datasets con linaje, los publica con SoD, deja un
   ledger de revision y crea un periodo, todo sintetico y dentro del volumen que
   se destruye al final.
3. Las redes de Compose tenian nombre global fijo. Cambiar solo `-p` y los
   volumenes aun conectaba ambos proyectos a las mismas redes. Compose conserva
   los defaults, pero admite ahora dos nombres de red E2E explicitos.
4. Calidad buscaba `/senales visibles/` y en una base vacia coincidian el contador
   y el mensaje de vacio. El selector exige el contador exacto.
5. Preparacion de cierre exigia siempre una columna `Statement`. Una base fresca
   puede tener periodo y aun ninguna cuenta ligada; la prueba exige ahora o la
   tabla versionada o el bloqueo explicito “No hay cuentas asignadas”, y en ambas
   ramas confirma que no existe accion de cierre.

El primer fallo tambien demostro el camino adverso: tras 10 fallos Chromium, el
`finally` elimino contenedores, redes y volumenes E2E antes de propagar el error.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Corrida aislada verde 1 | 26/26 Chromium + 15/15 Axe; 116,3 s; cleanup verificado |
| Corrida aislada verde 2 | 26/26 Chromium + 15/15 Axe; 100,8 s; cleanup verificado |
| No interferencia | identidades de 6 contenedores, 2 volumenes y 2 redes persistentes iguales antes/despues |
| Fixture PostgreSQL real por corrida | 1 prueba REC-002, 2 datasets publicados, 1 periodo sintetico |
| Contratos de runtime/stack | 59 pruebas, OK; ambos validadores `ok: true` |
| Herramientas del repositorio | 1382 pruebas por modulo, OK |
| Web | typecheck, lint, 198/198 unitarias y build de 23 rutas, OK |
| Golden / mutaciones | 14/14 golden y 68/68 mutaciones verificadas |
| Catalogo / grafo / quality gate | OK, sin bloqueantes ni hallazgos en indice |
| S1-READY | evaluacion valida: 39 machine pass, 1 revision humana pendiente |

Comando principal:

```powershell
.\infra\local\test-web-isolated.ps1
```

Los validadores y su suite estan integrados en la lane de contratos de CI. El
contrato falla ante colision de proyecto, volumen, red o puerto; bind publico;
entrada libre de recursos; omision/reorden de fases; falta de `finally`; URL API
persistente; una suite omitida o ausencia de cleanup.

## Limites, revision y rollback

No se modificaron API productiva, migraciones, esquema, semilla de demo, RLS,
SoD, auditoria, gates, mobile ni IA. La fixture usa las superficies y pruebas
reales existentes; toda aprobacion de release lleva las marcas
`SYNTHETIC-TEST-FIXTURE` y `FIXTURE-NOT-A-HUMAN-APPROVAL`. Nada de esto autoriza
datos reales o operacion piloto.

La comparacion de la demo acredita identidad de recursos y la inspeccion E2E
acredita ausencia de mounts/redes compartidos; no se abrieron ni hashearon los
datos internos de los volumenes persistentes. QA debe revisar independencia y
estados vacios, Platform/SRE el lifecycle y Security los limites destructivos.
`FOUNDER-01` y el implementador no cuentan como revisores independientes.

Revertir, en orden, `b02fbd7`, `406816b`, `b835620` y `7270f2a` retira CI,
fixture, runner y contrato. El rollback no debe ejecutar `down --volumes` sobre
`fincilia-local`; los recursos E2E ya quedaron ausentes. S1-READY permanece en
`not_met` por la revision humana independiente preexistente.

## Rutas liberadas

Compose y README local, ambos entrypoints E2E, fixture sintetica, dos specs web,
contrato/validador, CI, ficha, handoff y registros centrales de FNC-QA-009.
