# CI y quality gate inicial

| Campo | Valor |
|---|---|
| Tarea | FNC-PLT-003 |
| Estado | Review pending |
| Datos permitidos | Exclusivamente sintéticos |
| Workflow | `.github/workflows/ci.yml` |
| Política local | `python -m tools.quality_gate.cli` |
| Despliegue | Ninguno |

## 1. Objetivo

El gate evita que un cambio aparentemente documental o de scaffolding debilite las restricciones de E0. Se ejecuta localmente y en GitHub Actions, pero no publica artefactos, no despliega y no autoriza datos reales.

## 2. Jobs

### Repository and synthetic-data policy

1. checkout fijado a commit SHA;
2. Python 3.12 mediante action fijada a SHA;
3. política del repositorio sobre el índice Git;
4. tests de arquitectura, escáner y corpus;
5. validación del modelo ejecutable de módulos;
6. regeneración byte a byte del corpus golden.

### PostgreSQL RLS and worker spike

1. valida Compose;
2. inicia PostgreSQL y espera healthcheck;
3. instala npm con lockfile y `--ignore-scripts`;
4. ejecuta `npm audit --audit-level=high`;
5. ejecuta TypeScript typecheck y Vitest RLS/outbox;
6. ejecuta las pruebas del worker Python;
7. elimina contenedores y volúmenes incluso si falla un paso.

El segundo job valida únicamente `spikes/FNC-PLT-001`; no promueve ese código a producto.

## 3. Política del repositorio

El escáner falla por:

- archivos Git bajo `data/`, `uploads/`, `quarantine/`, `raw/`, `exports/`, `artifacts/` o `secrets/`;
- `.env` distinto de `.env.example`, llaves o contenedores de certificado;
- patrones de alta señal para private keys y tokens AWS, GitHub, Google, OpenAI, Slack o Stripe live;
- archivo superior a 5 MiB durante E0;
- symlink versionado;
- TODO/FIXME anónimo en comentarios de código;
- action GitHub no fijada a SHA de 40 caracteres;
- imagen Compose sin digest SHA-256;
- `pull_request_target`, `write-all`, `contents: write` o `id-token: write`;
- workflow sin `permissions: contents: read` en nivel superior.

Los tests prueban tanto aceptación como rechazo. Los ejemplos de token peligroso se construyen en memoria para no versionar una cadena con forma de secreto.

## 4. Supply chain

- `actions/checkout` está fijada al commit oficial de v7.0.1.
- `actions/setup-python` está fijada al commit oficial de v7.0.0.
- PostgreSQL y Node del spike están fijados por digest OCI.
- npm usa `package-lock.json`, instalación sin lifecycle scripts y auditoría high/critical.
- Dependabot propone actualizaciones semanales para Actions, npm y Docker; nunca hace auto-merge.

Cambiar un SHA o digest requiere PR, evidencia de procedencia, ejecución completa y revisión Platform/Security.

## 5. Ejecución local

Desde la raíz:

```bash
python3 -m tools.quality_gate.cli
python3 -m tools.architecture_model.validate
python3 -m unittest tools.architecture_model.test_validate tools.quality_gate.test_repo_policy tools.synthetic_corpus.test_corpus -v
python3 -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic
```

Stack local desde WSL:

```bash
cd spikes/FNC-PLT-001
docker compose config --quiet
docker compose up -d --wait
docker compose --profile test run --rm api-test sh -lc \
  "npm ci --ignore-scripts && npm audit --audit-level=high && npm run typecheck && npm test"
cd worker && python3 -m unittest -v
```

## 6. Operación en GitHub

Cuando exista remoto, el administrador debe proteger `main` y exigir los checks:

- `Repository and synthetic-data policy`;
- `PostgreSQL RLS and worker spike`.

También debe impedir push directo, exigir revisión independiente en rutas sensibles y limitar quién puede modificar workflows. Esta configuración externa no se presupone ni puede probarse desde el repositorio.

## 7. Límites

- El escáner es una defensa temprana de alta señal, no reemplaza secret scanning del proveedor, revisión humana, SAST, análisis de dependencias ni SBOM.
- Solo inspecciona archivos versionados en el índice Git; un archivo local no tracked sigue siendo responsabilidad del entorno y `.gitignore`.
- `npm audit` cubre el árbol npm del spike, no vulnerabilidades de imágenes o sistema operativo.
- No se ejecutó todavía una corrida en GitHub alojado; se reprodujeron localmente los comandos.
- No hay artifact upload deliberadamente. Cuando exista evidencia CI, debe contener solo estado, hashes y metadatos sintéticos permitidos.
- Branch protection, CODEOWNERS nominal y secret scanning administrado quedan pendientes de proveedor/owners humanos.
