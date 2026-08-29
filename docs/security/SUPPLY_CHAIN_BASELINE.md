# Baseline ejecutable de cadena de suministro

| Campo | Valor |
|---|---|
| Tarea | FNC-SUP-001 |
| Estado | Review pending |
| Gate | DRG-00 — `not_met` |
| Owner | Security |
| Revisores independientes | Platform, QA |
| Contrato autoritativo | `docs/security/supply-chain.json` |
| CLI | `python -m tools.supply_chain.cli` |
| Red | Ninguna. El baseline nunca contacta un registro. |

---

## 1. Qué pregunta responde

Una sola, para cada cosa de la que depende un resultado:

> ¿Está fijada a bytes concretos, y sabemos de dónde salió?

Son **dos** preguntas distintas y el repositorio solo puede contestar la primera hoy.
Confundirlas es el error que este baseline existe para impedir.

---

## 2. Un digest no es una firma

| Lo que un digest `sha256` demuestra | Lo que **no** demuestra |
|---|---|
| Que los bytes observados son esos bytes | Quién los produjo |
| Que el artefacto no cambió bajo el mismo nombre | Con qué código fuente se construyeron |
| Que dos máquinas ven lo mismo | Que la cadena de construcción fuese íntegra |

El contrato declara esto de forma ejecutable en `digest_semantics`, y el validador
rechaza cualquier intento de poner `proves_provenance: true`. Un baseline que
tratara un pin como una acreditación de origen daría una falsa sensación de
cobertura justo donde el riesgo vive.

---

## 3. Qué se descubre y cómo

Cinco reglas de descubrimiento con globs exactos, no una lista de ficheros que
alguien tenga que acordarse de actualizar:

| Regla | Lee | Produce |
|---|---|---|
| `workflows` | `uses:`, `image:`, `*-version:`, `runs-on:`, comandos de instalación | actions, imágenes, runtimes, instalaciones |
| `compose` | `image:` | imágenes OCI |
| `package_manifests` | `package.json` | manifests con sus lifecycle scripts |
| `lockfiles` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`… | locks con su alcance |
| `update_monitors` | `dependabot.yml` | pares ecosistema:directorio vigilados |

Todo resultado lleva **ruta canónica, línea y digest de la fuente escaneada**. Los
symlinks se descartan: seguirlos permitiría inventariar ficheros de fuera del árbol
como si fueran propios. Un fichero bajo `node_modules`, `vendor` o una caché nunca
cuenta como fuente propia, y un glob que lo incluyera se rechaza en el contrato.

### El escáner falla cerrado

La biblioteca estándar no trae parser de YAML y el encargo prohíbe dependencias
nuevas, así que el escáner es **orientado a líneas**. Cuando encuentra una ancla,
un alias o una merge key, no adivina: declara el fichero no escaneable y emite
`SUP-YAML-UNSCANNABLE`. Un inventario que pierde referencias en silencio es peor
que uno que dice lo que no pudo leer.

Durante la construcción esta misma regla encontró un falso positivo propio —un glob
de shell `*.test.mjs` dentro de un `run:` parecía un alias YAML— y se corrigió el
patrón para que un alias solo cuente en posición de valor.

---

## 4. Política de pins

| Componente | Forma exigida | Motivo |
|---|---|---|
| GitHub Action | sha de 40 hex | un tag puede reapuntarse a otro commit sin cambiar de nombre |
| Imagen OCI | `nombre:tag@sha256:<64 hex>` | sin digest los bytes pueden cambiar bajo el mismo nombre |
| Runtime | versión exacta | `latest` haría que el mismo commit construyera contra otro runtime mañana |

Un sha corto **no** basta y se reporta como tal. Una etiqueta de runner `*-latest`
flota y se reporta; una etiqueta versionada sigue sin ser inmutable, y por eso vive
como gap declarado (`GAP-SUP-RUNNER`) en vez de fingirse un pin.

---

## 5. Manifest ↔ lockfile

El alcance de ambos es **su propio directorio**. Todo manifest necesita un lockfile
hermano y todo lockfile necesita un manifest hermano. Dos lockfiles de ecosistemas
distintos en el mismo alcance dejan indefinido cuál resuelve el árbol, y eso se
reporta.

Sobre lifecycle scripts: si **algún** manifest del repositorio los declara, todo
`install` de CI debe pasar `--ignore-scripts`. De lo contrario se ejecuta código
arbitrario de terceros durante la instalación, que es una de las formas más baratas
de comprometer una cadena de suministro.

---

## 6. Estado medido del repositorio

57 componentes en 23 ficheros escaneados:

| Tipo | Cantidad | Estado |
|---|---:|---|
| `github_action` | 9 | **todas fijadas a sha de 40** |
| `oci_image` | 15 | **todas fijadas por digest** |
| `runtime` | 9 | versiones exactas o runner versionado con gap declarado |
| `package_manifest` | 8 | con lockfile hermano |
| `lockfile` | 5 | un ecosistema por alcance |
| `external_build_service` | 3 | instalaciones acotadas y sin lifecycle scripts |
| `generated_artifact` | 8 | entradas válidas de vigilancia de actualizaciones |

**Ningún defecto de pin.** Los hallazgos que quedan son de otra naturaleza:

| Hallazgo | Cantidad | Severidad | Clasificación |
|---|---:|---|---|
| `SUP-PROVENANCE-PENDING` | 4 | high | gap declarado |
| `SUP-UPDATES-UNMONITORED` | 5 | medium | gap declarado para alcances Compose |

### Cobertura de actualizaciones

`dependabot.yml` cubre los alcances npm, pip y GitHub Actions que el inventario
descubre. GitHub Dependabot no interpreta referencias de imágenes dentro de
Docker Compose: declarar esos directorios como ecosistema `docker` produce
`dependency_file_not_found`, no vigilancia. Por eso los cinco alcances Compose
permanecen fijados por digest pero se reportan como `SUP-UPDATES-UNMONITORED` hasta
adoptar un monitor compatible o una revisión operativa demostrable. `.next` se
excluye mediante el contrato, no mediante una regla ad hoc: es salida generada de
Next.js y sus manifests transitivos no son fuentes mantenidas por el repositorio.

---

## 7. Evidencia externa FNC-SUP-002

El candidato `1aa44c29af51709e7f675cdeee76c453fc30f416` generó un archivo
determinista, un SPDX agregado y dos bundles Sigstore mediante GitHub OIDC. La
corrida `33256843904` verificó dentro del runner y una segunda verificación local
comprobó el mismo sujeto SHA-256, workflow, commit, ref, predicate y prohibición
de runner autohospedado. La evidencia acotada está en
`docs/implementation/evidence/FNC-SUP-002.json`.

Esto satisface técnicamente SBOM, firma y procedencia **del archivo candidato**.
No afirma que las imágenes locales estén publicadas, ni que cada dependencia
upstream sea auténtica, ni constituye revisión independiente.

## 8. Por qué `validate` sigue saliendo distinto de cero

El `SUP-PROVENANCE-PENDING` restante es de severidad `high`, y el bloqueo se rige
por **severidad declarada**, no por una nota agregada ni por la clasificación. Que un
gap esté previsto no lo hace menos bloqueante:

| Evidencia | Estado | Por qué |
|---|---|---|
| SBOM | `sbom_attested` | SPDX por servicio y agregado, firmado y verificado para el candidato |
| Firma | `signature_attested` | dos bundles Sigstore verificados contra la identidad OIDC del workflow |
| Procedencia | `provenance_attested` | SLSA liga sujeto ↔ commit ↔ ref ↔ workflow ↔ runner |
| Origen verificado | `source_verified_pending` | el sha de una action se copió de upstream sin verificación independiente |

Rebajar cualquiera de esas severidades para que el comando quedara verde sería
exactamente la aritmética optimista que este baseline existe para impedir.

---

## 9. TM-005 sigue abierto

El contrato lo declara de forma ejecutable y el validador **rechaza** cualquier
intento de cerrarlo:

```json
{"state": "open", "closed_by_this_tool": false, "owner_role": "Security", "gate": "DRG-00"}
```

El candidato ya aporta SBOM, firma y procedencia. TM-005 sigue abierto porque la
observación automatizada de tags no es revisión Security independiente, el runner
hosted no es una imagen fijada y no se ha probado equivalencia fuente→paquete para
cada proveedor.

---

## 10. Excepciones

El catálogo empieza **vacío**. Una excepción solo suspende una regla si declara id,
componente, regla, motivo, owner, revisor, expiración, gate y aprobación humana. Un
agente no puede crear ni aprobar ninguna: `approved_by_human: false` deja la regla
intacta, y hay prueba de que así ocurre.

---

## 11. CLI

```bash
python -m tools.supply_chain.cli discover
python -m tools.supply_chain.cli validate
python -m tools.supply_chain.cli validate --gate S1-READY
python -m tools.supply_chain.cli report
```

- `discover` — inventario estable y ordenado, con procedencia y digest.
- `validate` — validez del contrato **más** reconciliación completa; continúa saliendo
  1 mientras el origen independiente siga abierto.
- `validate --gate S1-READY` — conserva todos los hallazgos en la salida, pero solo
  usa como exit code los bloqueantes cuyo `gate` sea S1-READY. Un gate desconocido
  falla cerrado.
- `report` — blockers y gaps por riesgo, owner y gate. `aggregate_score` es `null` a
  propósito: un porcentaje ocultaría justo el blocker.

`--root` y `--model` son inyectables y quedan confinados al árbol. Nada de lo
descubierto se ejecuta jamás: una action, una imagen o un paquete son datos.

---

## 12. Límites honestos

1. Un inventario en verde prueba que las referencias están fijadas, **no** que sean seguras.
2. Un digest identifica el artefacto observado; no acredita quién lo produjo.
3. No se lee el árbol transitivo: un lockfile fijado puede contener un paquete comprometido.
4. No sustituye al escáner de secretos ni al análisis de vulnerabilidades.
5. El escáner de YAML es un subconjunto; lo que no puede leer lo declara.
6. Los runners hosted de GitHub no son artefactos fijables por digest.

## 13. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-SUP-SBOM-TOOL` | Qué generador de SBOM se adopta y dónde se almacena | Security |
| `UD-SUP-SIGNING-ROOT` | Qué raíz de confianza y mecanismo de firma para artefactos propios | Security |
| `UD-SUP-RUNNER-POLICY` | Si se aceptan runners hosted o se exige runner propio reproducible | Platform |
| `UD-SUP-UPDATE-CADENCE` | Quién revisa y aprueba las actualizaciones de pins, y con qué cadencia | Platform |
