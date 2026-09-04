# Candidato de release reproducible

FNC-REL-001 produce una evidencia portable de **identidad**, no una aprobación
de producción. El bundle liga un commit Git limpio, los árboles de fuente que
entran en las tres imágenes, la cabeza de migraciones, los IDs SHA-256 de las
imágenes construidas, tres inventarios SPDX 2.3 por servicio y un inventario
SPDX agregado de la release.

## Qué demuestra

- Los bytes del bundle no cambiaron desde que se calcularon sus checksums.
- API, worker y web tienen identidades distintas y no flotantes.
- Los locks Python contienen versiones y hashes; npm aporta `integrity`.
- El commit, los inputs y la cabeza de migraciones son reproducibles.
- Cada origen local de cada instrucción `COPY` está dentro de un input
  adjudicado. El validador extrae los orígenes desde los Dockerfiles, ignora
  únicamente copias entre etapas y falla cerrado ante `ADD`, glob, variables,
  heredoc o sintaxis de flags que no pueda interpretar.
- Los inputs son árboles disjuntos, no una lista manual de algunos archivos:
  así también quedan ligados tests, configuración de build, bootstrap de base
  de datos y archivos públicos que efectivamente entran en las imágenes.
- El generador/verificador y el workflow de firma también son materiales
  adjudicados. Cambiarlos invalida la evidencia durable aunque los bytes de las
  imágenes permanezcan iguales.
- Los digests de fuente y locks se calculan sobre blobs Git, por lo que un
  checkout limpio con CRLF en Windows verifica el mismo commit construido con
  LF en Linux; el bundle no confunde filtros locales con código distinto.
- La evidencia se generó para el techo `synthetic_only`.

## Qué no demuestra

- No demuestra autoría, seguridad de una dependencia ni equivalencia source→wheel.
- El inventario describe dependencias fijadas; no afirma análisis de cada archivo
  ni sustituye un SBOM de filesystem/OS de la imagen.
- El ID local de imagen no es un digest publicado en un registry.
- El bundle interno no se autoafirma firmado. El workflow manual puede envolverlo
  en un archivo determinista, emitir attestations externas de procedencia y SBOM
  mediante GitHub OIDC/Sigstore y verificarlas contra el workflow y commit.
- No habilita staging, producción, datos reales ni promoción de engine releases.

El propio verificador rechaza cualquier bundle que cambie estos cinco campos a
verdadero: `approved`, `published`, `signed`, `provenance_verified` o
`production_authorized`.

## Uso

El árbol debe estar limpio y los tres IDs se obtienen de imágenes recién
construidas. El directorio de salida debe estar fuera del repositorio o ignorado.

```bash
python -m tools.release_candidate.cli create \
  --root . \
  --output "$RUNNER_TEMP/fincilia-release" \
  --revision "$GITHUB_SHA" \
  --api-image-id "sha256:<64 hex>" \
  --worker-image-id "sha256:<64 hex>" \
  --web-image-id "sha256:<64 hex>" \
  --ci-run-url "https://github.com/OWNER/REPO/actions/runs/RUN_ID"

python -m tools.release_candidate.cli verify \
  --bundle "$RUNNER_TEMP/fincilia-release"

python -m tools.release_candidate.cli verify-source \
  --root . \
  --bundle "$RUNNER_TEMP/fincilia-release"

python -m tools.release_candidate.cli archive \
  --bundle "$RUNNER_TEMP/fincilia-release" \
  --output "$RUNNER_TEMP/fincilia-release.tar.gz"

python -m tools.release_candidate.cli verify-archive \
  --bundle "$RUNNER_TEMP/fincilia-release" \
  --archive "$RUNNER_TEMP/fincilia-release.tar.gz"
```

`verify` sólo necesita el bundle y valida inventario, estructura, claims y
digests. `verify-source` añade comparación contra el checkout limpio exacto.

## Rollout hacia una release real

1. CI ejecuta toda la regresión sintética.
2. Construye las tres imágenes sin push y obtiene sus IDs locales.
3. Genera y verifica el bundle dos veces.
4. Security/QA/Architecture revisan claims, SPDX y evidencia.
5. El workflow firma por identidad OIDC una procedencia SLSA y el SPDX agregado;
   luego verifica ambos bundles Sigstore offline con `gh attestation verify`.
6. Security/QA revisan la identidad firmante y los SHA de actions. Después de
   A-02 se decide registry y secret provider; esta attestation no publica ni
   promueve imágenes.

## Rollback

El bundle es append-only y no cambia datos. Retirar el workflow o descartar el
candidato basta; nunca se reutiliza un número o digest para otros bytes. Una
release desplegada necesitará su propio runbook canary/rollback después de elegir
plataforma, algo deliberadamente fuera de esta tarea.
