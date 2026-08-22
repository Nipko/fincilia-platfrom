# Handoff — FNC-SUP-001: baseline ejecutable de cadena de suministro

| Campo | Valor |
|---|---|
| Tarea | FNC-SUP-001 |
| Estado | **`REVIEW_PENDING`** |
| Base declarada | `48b21d1` — entregada por el Integration Steward, **no verificada** |
| Verificación de la base | No se usó Git en ninguna forma |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | Security |
| Revisores independientes | Platform, QA |
| Gate | DRG-00 — `not_met` |

---

## 1. Rutas creadas

| Ruta | Acción |
|---|---|
| `docs/security/supply-chain.json` | creada — contrato autoritativo |
| `docs/security/SUPPLY_CHAIN_BASELINE.md` | creada — documentación |
| `tools/supply_chain/__init__.py` | creada |
| `tools/supply_chain/discovery.py` | creada — extractores y contención de rutas |
| `tools/supply_chain/rules.py` | creada — validación del contrato y reconciliación |
| `tools/supply_chain/cli.py` | creada — `discover`/`validate`/`report` |
| `tools/supply_chain/test_validate.py` | creada — 68 pruebas |
| `docs/implementation/handoffs/FNC-SUP-001.md` | este documento |

**No se tocó** CI, `dependabot.yml`, `CURRENT_PHASE.md`, backlog, trazabilidad, work
graph, gates, decisiones, ownership, tareas, ADR, contratos existentes, Compose,
locks ni migraciones. QA-002..005, golden harness, mutation harness y catálogo se
consumieron **solo lectura**. Todas las rutas reservadas quedan liberadas.

---

## 2. Contrato y decisiones implementadas

- **Siete tipos de componente allowlisted** y **seis estados de evidencia**, exigidos
  como conjunto exacto por el validador.
- **`digest_semantics` ejecutable**: `proves_artifact_identity: true`, y `false` para
  autor, firma, procedencia y sustitución de verificación independiente. Poner
  cualquiera en `true` produce `SUP-DIGEST-AS-PROVENANCE`.
- **Política de pins**: action sha-40, OCI `@sha256:<64>`, runtime exacto.
- **Relación manifest ↔ lockfile** por alcance de directorio, con duplicados
  incompatibles detectados.
- **Escáner fail-closed**: anclas, alias y merge keys de YAML se declaran ilegibles en
  vez de omitirse en silencio.
- **Catálogo de excepciones vacío**, con nueve campos obligatorios y aprobación humana
  sin la cual la regla no se suspende.
- **TM-005 abierto** por contrato, con el validador rechazando cualquier cierre.
- **Cinco gaps declarados** que mantienen DRG-00 bloqueado.

Las 16 invariantes negativas del encargo tienen prueba que parte de una entrada
válida y la degrada exactamente una vez, más cinco metamórficas.

---

## 3. Comandos exactos y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.supply_chain.test_validate` | 0 | **68 pruebas, OK** |
| `python -m tools.supply_chain.cli discover` | 0 | 9 ficheros, 26 componentes, 0 ilegibles |
| `python -m tools.supply_chain.cli validate` | **1** | contrato válido, 7 hallazgos, 4 bloqueantes |
| `python -m tools.supply_chain.cli report` | **1** | por riesgo, owner y gate; sin nota agregada |

`validate` y `report` salen con 1 **porque la procedencia no está demostrada**, no
porque haya un pin roto. El bloqueo se rige por severidad declarada, como pide el
encargo. Contrato válido y repositorio limpio son dos hechos distintos, y el payload
los separa.

---

## 4. Estado medido

**Cero defectos de pin.** Las 5 actions están fijadas a sha de 40, las 7 imágenes por
digest, el runtime de CI es `3.12` exacto, los 2 manifests tienen lockfile hermano y
sin lifecycle scripts, y los 2 comandos de instalación son `npm ci --ignore-scripts`.

| Hallazgo | Cantidad | Severidad | Naturaleza |
|---|---:|---|---|
| `SUP-PROVENANCE-PENDING` | 4 | high | gap declarado (SBOM, firma, procedencia, origen) |
| `SUP-UPDATES-UNMONITORED` | 3 | medium | hueco de cobertura de actualizaciones |

---

## 5. Pruebas negativas y qué demostraron

| Invariante | Cómo se degradó una entrada válida | Regla que mordió |
|---|---|---|
| 1 | action con `v4`, `main`, sha corto y sin ref | `SUP-ACTION-UNPINNED` (4 variantes) |
| 2 | imagen sin digest, con `latest`, con digest mal formado | `SUP-IMAGE-UNPINNED` |
| 3 | runtime `latest/current/stable/main`, `^3.12`, `3.x`, runner `-latest` | `SUP-RUNTIME-FLOATING` |
| 4 | se borra el lockfile hermano | `SUP-MANIFEST-NO-LOCKFILE` |
| 5 | se borra el manifest; se añade un `pnpm-lock.yaml` al mismo alcance | `SUP-LOCKFILE-ORPHAN` |
| 6 | `npm install` en vez de `npm ci` | `SUP-INSTALL-UNBOUNDED` |
| 7 | manifest con `postinstall` e install sin `--ignore-scripts` | `SUP-LIFECYCLE-SCRIPTS` |
| 8 | se borra la entrada de ownership de un tipo | `SUP-COMPONENT-UNOWNED` |
| 9 | `proves_provenance: true` y sus tres hermanos | `SUP-DIGEST-AS-PROVENANCE` |
| 10 | claim `sbom_pending` marcado `satisfied` | `SUP-EVIDENCE-UNSUPPORTED` |
| 11 | excepción sin owner, revisor, expiración, gate o motivo | `SUP-EXCEPTION-INCOMPLETE` |
| 12 | glob `node_modules/*/package.json` en el modelo | `SUP-VENDORED-SOURCE` |
| 13 | ruta absoluta, `..` que resuelve dentro, symlink | `SUP-PATH-UNSAFE` |
| 14 | dos ejecuciones sobre el mismo árbol | inventario idéntico |
| 15 | workflow con `SYNTHETIC_TOKEN` en `env:` | ni nombre ni valor aparecen en la salida |
| 16 | `tm_005.state: resolved`, `closed_by_this_tool: true` | `SUP-TM005-CLOSED` |

**Mutación manual adicional:** una excepción completa pero con
`approved_by_human: false` no suspende la regla, y con `true` suspende exactamente la
suya y ninguna otra.

---

## 6. Hallazgos fuera de scope

| Ruta | Regla | Impacto | Owner |
|---|---|---|---|
| `.github/dependabot.yml` | cobertura de ecosistemas | `spikes/FNC-PLT-005/api` (npm), `spikes/FNC-PLT-005` y `infra/local` (docker) no tienen entrada de vigilancia. Un digest fijado nunca se mueve solo; por eso hace falta que alguien avise cuando debería. | Platform |
| `.github/workflows/ci.yml` | `runs-on: ubuntu-24.04` | Una etiqueta versionada de runner hosted sigue sin ser un artefacto inmutable. Se declara como `GAP-SUP-RUNNER`, no como pin. | Platform |

Ninguno se corrigió: son rutas protegidas.

---

## 7. Riesgos y gaps que permanecen

| ID | Riesgo | Owner | Gate |
|---|---|---|---|
| `GAP-SUP-SBOM` | sin SBOM no se conoce el árbol transitivo real | Security | DRG-00 |
| `GAP-SUP-SIGNING` | no hay firma ni raíz de confianza declarada | Security | DRG-00 |
| `GAP-SUP-PROVENANCE` | no hay attestation de build | Security | DRG-00 |
| `GAP-SUP-RUNNER` | los runners hosted no son fijables por digest | Platform | DRG-00 |
| `GAP-SUP-TRANSITIVE` | el lockfile fija versiones, no verifica que el tarball corresponda al código anunciado | Platform | DRG-00 |

TM-005 sigue **abierto**. Este baseline no puede cerrarlo.

---

## 8. Rollback

Eliminar `tools/supply_chain/`, `docs/security/supply-chain.json` y
`docs/security/SUPPLY_CHAIN_BASELINE.md`. Ningún otro fichero depende de ellos y no
se modificó nada ajeno, así que el rollback es total y sin residuo. La única
dependencia entrante es el check `security-supply-chain` de FNC-PLT-007 y el
`chk-supply-chain` de FNC-GAT-003; si se revierte SUP-001, hay que retirar esas dos
entradas de sus contratos.

---

## 9. Compatibilidad

No altera ningún contrato existente: solo los lee. Añade dos consumidores nuevos
(dev CLI y agregador S1) que lo invocan como comando allowlisted.

---

## 10. Pasos para el Integration Steward

1. **Indexar** las rutas de §1.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí y no se
   declara exitoso: los ficheros son nuevos y el gate opera sobre el índice.
3. **CI**: decidir si `supply_chain validate` entra como bloqueante. Hoy sale 1 por
   gaps de procedencia declarados; entrarlo como bloqueante equivale a decidir que
   DRG-00 bloquea el pipeline.
4. **Catálogo y trazabilidad**: este contrato no declara `required_tests`, así que no
   introduce IDs nuevos ni drift en `TEST_CATALOG.md`. Conviene confirmarlo con
   `python -m tools.test_catalog.cli validate` tras indexar.
5. **Digests golden/mutation**: ninguno deriva de este cambio; `supply-chain.json` no
   es input de ningún caso golden ni de ninguna mutación registrada.
6. **Trasladar a Platform** los tres alcances sin vigilar de `dependabot.yml`.
7. **Liberar reservas** de FNC-SUP-001.

Estado final: **`REVIEW_PENDING`**. No se declara aceptación, integración, head SHA,
CI remoto ni revisión humana inexistentes. TM-005 no se cierra.
