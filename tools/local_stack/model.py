"""Contrato ejecutable del stack local (FNC-PLT-002, ampliado en FNC-PLT-008).

Las reglas son **generales**, no una lista de servicios concretos: el stack pasó
de dos contenedores a cinco y una regla escrita como "exactamente dos imagenes de
postgres" habria caducado en el primer commit de producto.

Lo que se comprueba y por que:

- Toda imagen fijada por digest. Una etiqueta puede reapuntarse a otros bytes.
- Todo puerto publicado ligado a `127.0.0.1`. Un `0.0.0.0` expone el stack de
  desarrollo a la red de la cafeteria.
- La base de datos y la cache **no** publican puerto. Docker ignora la publicacion
  en una red `internal`, asi que exponerlas obligaria a moverlas a una red con
  salida a internet, que es justo lo que no se quiere para los datos.
- Todo servicio de larga vida declara healthcheck: sin el, `up --wait` miente.
- Existe al menos una red `internal: true` y el worker vive solo en ella.
- Ningun contenedor privilegiado ni en `network_mode: host`.

Solo biblioteca estandar. Analisis orientado a lineas, sin parser de YAML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DIGEST_PINNED = re.compile(r"@sha256:[0-9a-f]{64}\s*$")
IMAGE_LINE = re.compile(r"(?m)^\s+image:\s+(\S+)\s*$")
SERVICE_LINE = re.compile(r"(?m)^  ([a-z][a-z0-9-]*):\s*$")
PORT_LINE = re.compile(r'(?m)^\s+-\s+"([^"]+)"\s*$')
# La clave exacta, no una subcadena: `disabled_healthcheck:` contiene
# `healthcheck:` y pasaria una comprobacion ingenua.
HEALTHCHECK_KEY = re.compile(r"(?m)^    healthcheck:\s*$")

# Servicios que guardan o sirven estado y nunca publican puerto al host.
NEVER_PUBLISHED = ("postgres", "valkey")
# Servicios de larga vida: todos menos los de un solo uso, que van por perfil.
ONE_SHOT_PROFILES = ("test", "migrate")
NEWLINE = chr(10)
# El migrador se invoca a mano. Un stack que migra en `up` migra una vez por
# replica y convierte un despliegue en un cambio de esquema.
MIGRATE_ENTRYPOINT = "db.migrate.apply"
# La web pinta lo que devuelve la API y no decide nada. Una credencial
# de base, de firma o de objetos en su entorno solo puede usarse para
# saltarse a la API.
WEB_MUST_NOT_HOLD = ("FINCILIA_DATABASE_URL", "FINCILIA_AUTH_SIGNING_KEY",
                     "FINCILIA_OBJECT_SECRET_KEY", "FINCILIA_MIGRATOR_URL")


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _service_blocks(text: str) -> dict[str, str]:
    """Trocea el fichero por servicio. El bloque llega hasta el siguiente servicio."""
    body = text.split("\nservices:\n", 1)
    if len(body) != 2:
        return {}
    region = body[1].split("\nvolumes:\n")[0].split("\nnetworks:\n")[0]
    marks = [(match.group(1), match.start()) for match in SERVICE_LINE.finditer(region)]
    blocks: dict[str, str] = {}
    for index, (name, start) in enumerate(marks):
        end = marks[index + 1][1] if index + 1 < len(marks) else len(region)
        blocks[name] = region[start:end]
    return blocks


def validate_compose(text: str) -> list[Finding]:
    findings: list[Finding] = []
    services = _service_blocks(text)
    if len(services) < 2:
        findings.append(Finding("LOCAL-SERVICES", "the stack declares no services"))
        return sorted(set(findings))

    for image in IMAGE_LINE.findall(text):
        if not DIGEST_PINNED.search(image):
            findings.append(Finding(
                "LOCAL-IMAGE-PIN",
                f"{image} is not pinned by digest; a tag can be repointed"))

    for name, block in sorted(services.items()):
        one_shot = any(f'profiles: ["{profile}"]' in block for profile in ONE_SHOT_PROFILES)

        published = PORT_LINE.findall(block) if "ports:" in block else []
        for port in published:
            if not port.startswith("127.0.0.1:"):
                findings.append(Finding(
                    "LOCAL-LOOPBACK",
                    f"{name} publishes {port} outside loopback"))
        if published and name in NEVER_PUBLISHED:
            findings.append(Finding(
                "LOCAL-DATA-EXPOSED",
                f"{name} must not publish a host port: reaching it needs a routable "
                "network, and giving the data store egress is the wrong trade"))

        if not one_shot and not HEALTHCHECK_KEY.search(block):
            findings.append(Finding(
                "LOCAL-HEALTHCHECK",
                f"{name} has no healthcheck; `up --wait` would report it ready blindly"))
        # Un healthcheck que no pregunta nada al servicio no es un healthcheck.
        # Se exige la sonda propia de cada dependencia, no una cualquiera.
        expected_probe = {"postgres": "pg_isready", "valkey": "valkey-cli ping",
                          "objectstore": "/minio/health/live",
                          "api": "/health/live", "web": "/entrar"}.get(name)
        if expected_probe and expected_probe not in block:
            findings.append(Finding(
                "LOCAL-HEALTHCHECK",
                f"{name} does not probe itself with {expected_probe!r}; a generic "
                "command would report healthy while the service is unusable"))
        if "privileged: true" in block or "network_mode: host" in block:
            findings.append(Finding(
                "LOCAL-PRIVILEGE",
                f"{name} runs privileged or on the host network"))
        if "networks:" not in block:
            findings.append(Finding(
                "LOCAL-NETWORK-MEMBERSHIP",
                f"{name} does not declare which network it joins"))
        if MIGRATE_ENTRYPOINT in block and "profiles:" not in block:
            findings.append(Finding(
                "LOCAL-MIGRATE-PROFILE",
                f"{name} applies migrations and declares no profile; it would run on "
                "every `up`, once per replica, without anyone deciding to migrate"))

    web = services.get("web")
    if web is not None:
        for secret in WEB_MUST_NOT_HOLD:
            if secret in web:
                findings.append(Finding(
                    "LOCAL-WEB-CREDENTIALS",
                    f"web receives {secret}; the interface never authorises and has "
                    "no business holding a credential it cannot need"))
    if not any(MIGRATE_ENTRYPOINT in block for block in services.values()):
        findings.append(Finding(
            "LOCAL-MIGRATE-MISSING",
            "no service applies migrations; the documented path would start an API "
            "against an empty schema and only fail at the first query"))
    if "internal: true" not in text:
        findings.append(Finding("LOCAL-INTERNAL-NETWORK",
                                "no internal network denies external routing"))
    worker = services.get("worker")
    if worker is not None and "fincilia_local_edge" in worker:
        findings.append(Finding(
            "LOCAL-WORKER-EGRESS",
            "the worker processes untrusted files and must stay off any routable "
            "network"))
    if "fincilia_local_pgdata:/var/lib/postgresql/data" not in text \
            or "name: ${FINCILIA_LOCAL_PGDATA_VOLUME:-fincilia_local_pgdata}" not in text:
        findings.append(Finding("LOCAL-NAMED-VOLUME",
                                "the PostgreSQL volume needs an explicit safe default "
                                "and an override for isolated synthetic acceptance"))
    if "fincilia_local_objectdata:/data" not in text \
            or "name: ${FINCILIA_LOCAL_OBJECTDATA_VOLUME:-fincilia_local_objectdata}" not in text:
        findings.append(Finding("LOCAL-NAMED-VOLUME",
                                "the object volume needs an explicit safe default and "
                                "an override for isolated synthetic acceptance"))
    if "name: ${FINCILIA_LOCAL_PRIVATE_NETWORK:-fincilia_local_private}" not in text \
            or "name: ${FINCILIA_LOCAL_EDGE_NETWORK:-fincilia_local_edge}" not in text:
        findings.append(Finding("LOCAL-NAMED-NETWORK",
                                "local networks need safe defaults and explicit "
                                "overrides for isolated synthetic acceptance"))
    if "./db/init:/docker-entrypoint-initdb.d:ro" not in text \
            or "./scripts:/checks:ro" not in text:
        findings.append(Finding("LOCAL-READONLY-MOUNTS",
                                "bootstrap and checks must be mounted read-only"))
    if 'profiles: ["test"]' not in text or "lifecycle-test:" not in text:
        findings.append(Finding("LOCAL-TEST-PROFILE",
                                "ephemeral lifecycle runner must be profile-gated"))
    if "synthetic" not in text.lower():
        findings.append(Finding("LOCAL-DATA-CEILING",
                                "synthetic-only marker is required"))
    return sorted(set(findings))


def validate_bootstrap(text: str) -> list[Finding]:
    findings: list[Finding] = []
    required = ["NOSUPERUSER", "NOBYPASSRLS", "NOCREATEDB", "NOCREATEROLE",
                "REVOKE CREATE ON SCHEMA public", "synthetic_only"]
    for token in required:
        if token not in text:
            findings.append(Finding("LOCAL-BOOTSTRAP-HARDENING", f"missing {token}"))
    for token in ("CREATE EXTENSION", "COPY "):
        if token in text:
            findings.append(Finding("LOCAL-BOOTSTRAP-FORBIDDEN",
                                    f"forbidden bootstrap token {token}"))
    if re.search(r"(?m)^\s+SUPERUSER\s*$", text) or \
            re.search(r"(?m)^\s+BYPASSRLS\s*;?\s*$", text):
        findings.append(Finding("LOCAL-BOOTSTRAP-PRIVILEGE",
                                "application role cannot bypass controls"))
    return sorted(set(findings))


def validate_bootstrap_script(text: str | None) -> list[Finding]:
    """El camino documentado tiene que existir y tiene que ser seguro.

    Dos cosas: que arranque el producto de verdad (migrar y permitir una demo
    opt-in, no solo levantar contenedores) y que **no** borre volumenes. El modo
    por defecto es vacio: una semilla de demostracion nunca puede reaparecer por
    un reinicio ordinario.
    """
    findings: list[Finding] = []
    if text is None:
        return [Finding("LOCAL-BOOTSTRAP-SCRIPT",
                        "the documented one-command path does not exist")]
    # Solo lo que se ejecuta. Un comentario que explica como empezar de cero no
    # es un comando, y confundirlos haria que documentar bien penalizara.
    text = NEWLINE.join(line for line in text.splitlines()
                        if not line.lstrip().startswith("#"))
    required_steps = (
        ("LOCAL-BOOTSTRAP-BUILD",
         "compose --profile migrate build api worker web migrate", True),
        ("LOCAL-BOOTSTRAP-MIGRATE",
         "compose --profile migrate run --rm migrate", True),
        ("LOCAL-BOOTSTRAP-SEED",
         "compose --profile migrate run --rm migrate python -m db.seed.local", True),
        ("LOCAL-BOOTSTRAP-START",
         "compose up -d --wait --force-recreate api worker web", True),
        ("LOCAL-BOOTSTRAP-READINESS", "/health/ready", False),
    )
    positions: list[int] = []
    executable_lines = text.splitlines()
    for code, required, exact_line in required_steps:
        position = next((index for index, line in enumerate(executable_lines)
                         if (line.strip() == required if exact_line
                             else required in line)), -1)
        if position < 0:
            findings.append(Finding(
                code,
                f"the bootstrap script never runs {required!r}; bringing containers "
                "up is not the same as leaving the current product revision usable"))
        else:
            positions.append(position)
    if len(positions) == len(required_steps) and positions != sorted(positions):
        findings.append(Finding(
            "LOCAL-BOOTSTRAP-ORDER",
            "build, migration, seed, application start and readiness must run in "
            "that order; otherwise old code can observe a new schema"))
    for required in ('payload.get("status") != "ready"',
                     'item.get("name") == "schema"',
                     'schema[0].get("status") != "up"'):
        if required not in text:
            findings.append(Finding(
                "LOCAL-BOOTSTRAP-READINESS",
                f"the readiness check is missing {required!r}; HTTP 200 alone does "
                "not prove that the expected schema is applied"))
    for destructive in ("--volumes", "-v ", "down --rmi", "prune"):
        if destructive in text:
            findings.append(Finding(
                "LOCAL-BOOTSTRAP-DESTRUCTIVE",
                f"the bootstrap script contains {destructive!r}; starting the stack "
                "must never be the same gesture as destroying data"))
    for required in ('MODE=${1:---empty}', '--empty) SEED_DEMO=false',
                     '--demo) SEED_DEMO=true'):
        if required not in text:
            findings.append(Finding(
                "LOCAL-BOOTSTRAP-DEMO-OPT-IN",
                f"the bootstrap script is missing {required!r}; ordinary startup "
                "must not recreate demonstration accounts"))
    if text.count('if [ "$SEED_DEMO" = true ]') != 2:
        findings.append(Finding(
            "LOCAL-BOOTSTRAP-DEMO-OPT-IN",
            "demo seeding and its user-facing result must both remain guarded; "
            "ordinary startup must not recreate demonstration accounts"))
    return findings


def validate_empty_reset_script(text: str | None) -> list[Finding]:
    """El reset local solo puede reemplazar dos volumenes adjudicados exactos."""
    if text is None:
        return [Finding("LOCAL-RESET-SCRIPT", "the empty reset script is missing")]
    findings: list[Finding] = []
    for required in (
        "PROJECT=fincilia-local",
        "PG_VOLUME=fincilia_local_pgdata",
        "OBJECT_VOLUME=fincilia_local_objectdata",
        'com.docker.compose.project',
        'com.docker.compose.volume',
        '/var/lib/docker/volumes/"$volume"/_data',
        '--execute)',
        '[ "$2" = "$PROJECT" ]',
        'docker volume rm "$PG_VOLUME" "$OBJECT_VOLUME"',
        'sh "$HERE/up.sh" --empty',
        "tablename NOT IN (",
        "'schema_history', 'subject', 'legal_document_version'",
        "object zones empty",
    ):
        if required not in text:
            findings.append(Finding(
                "LOCAL-RESET-ALLOWLIST",
                f"the reset script is missing the exact guard {required!r}"))
    for forbidden in ("--volumes", "docker system prune", "docker volume prune",
                      "rm -rf", "${PROJECT}_*", "fincilia_rec002"):
        if forbidden in text:
            findings.append(Finding(
                "LOCAL-RESET-BROAD-TARGET",
                f"the reset script contains broad or foreign target {forbidden!r}"))
    return sorted(set(findings))


# --------------------------------------------------------------------------- #
# Contrato del workflow de CI
# --------------------------------------------------------------------------- #

# Cada suite declara que dependencias necesita para poder correr. No es
# documentacion: se comprueba contra el orden real de los pasos del workflow.
# El origen de la regla es un fallo concreto -- las pruebas documentales se
# ejecutaron con solo PostgreSQL arriba y reventaron contra el almacen de
# objetos -- y el coste de descubrirlo fue una CI roja durante varios commits.
SUITE_DEPENDENCIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("/app/db/tests", ("postgres", "objectstore", "valkey")),
    ("db.seed.local", ("postgres",)),
    ("/app/tests -t /app/tests", ("postgres", "objectstore", "valkey")),
)
# Un paso que arranca servicios: o los nombra, o levanta el stack entero.
STARTS_EVERYTHING = ("up -d --wait" + NEWLINE, "up -d --wait" + NEWLINE, "sh up.sh")
DOCKER_BUILD_FILE = re.compile(r"docker build[^\n]*?-f\s+(\S+)")


def _ci_steps(text: str) -> list[tuple[str, str]]:
    """Pasos del job `local-platform`, en orden, como `(nombre, comando)`.

    Se trocea a mano en vez de con un parser de YAML: este validador corre en la
    biblioteca estandar, y lo que hace falta comprobar es el **orden**, que se
    lee igual de bien sobre el texto.
    """
    marker = NEWLINE + "  local-platform:" + NEWLINE
    if marker not in text:
        return []
    body = text.split(marker, 1)[1]
    # El job termina en la siguiente clave de nivel de job.
    for candidate in re.finditer(r"(?m)^  [a-z][a-z0-9-]*:$", body):
        body = body[:candidate.start()]
        break
    steps: list[tuple[str, str]] = []
    chunks = re.split(r"(?m)^      - name: ", body)
    for chunk in chunks[1:]:
        name, _, rest = chunk.partition(NEWLINE)
        steps.append((name.strip(), rest))
    return steps


def _services_started(command: str) -> set[str]:
    """Servicios que un comando deja arriba y sanos."""
    started: set[str] = set()
    if "sh up.sh" in command:
        # El camino documentado levanta el stack entero, incluida la web.
        return {"postgres", "valkey", "objectstore", "api", "worker", "web"}
    for line in command.splitlines():
        if "up -d --wait" not in line:
            continue
        tail = line.split("up -d --wait", 1)[1].strip()
        if not tail or tail.startswith("|"):
            # Sin nombres, `up --wait` levanta todos los servicios por defecto.
            return {"postgres", "valkey", "objectstore", "api", "worker", "web"}
        started |= {token for token in tail.split()
                    if re.fullmatch(r"[a-z][a-z0-9-]*", token)}
    return started


def validate_ci_workflow(text: str, root: Path | None = None) -> list[Finding]:
    """El orden de los pasos de CI tiene que sostener lo que cada suite necesita."""
    findings: list[Finding] = []
    steps = _ci_steps(text)
    if not steps:
        return [Finding("LOCAL-CI-JOB",
                        "the local-platform job is missing from the CI workflow")]

    running: set[str] = set()
    for name, command in steps:
        for needle, required in SUITE_DEPENDENCIES:
            if needle not in command:
                continue
            missing = sorted(set(required) - running)
            if missing:
                findings.append(Finding(
                    "LOCAL-CI-DEPENDENCIES",
                    f"step {name!r} runs a suite that needs {missing} but nothing "
                    "has started them yet; a suite that cannot reach its "
                    "dependencies fails on the dependency, not on the code"))
        running |= _services_started(command)

        for referenced in DOCKER_BUILD_FILE.findall(command):
            if root is None:
                continue
            # `-f` se resuelve desde el directorio de trabajo del job, no desde la
            # raiz del repositorio. Un `-f apps/web/Dockerfile` con
            # `working-directory: infra/local` no existe, y solo se descubre en CI.
            if not (root / "infra/local" / referenced).is_file():
                findings.append(Finding(
                    "LOCAL-CI-BUILD-CONTEXT",
                    f"step {name!r} builds with -f {referenced!r}, which does not "
                    "exist relative to the job working directory"))

    # Que se ejecuten de verdad: un workflow que deja de correr una suite pasa
    # igual de verde que uno que la corre y acierta.
    joined = NEWLINE.join(command for _, command in steps)
    for needle, _ in SUITE_DEPENDENCIES:
        if needle not in joined:
            findings.append(Finding(
                "LOCAL-CI-COVERAGE",
                f"no CI step runs {needle!r}; dropping a suite is not the same as "
                "passing it"))
    for expected in ("npm run lint", "/health/ready", "/api/v1/auth/session"):
        if expected not in joined:
            findings.append(Finding(
                "LOCAL-CI-COVERAGE", f"no CI step exercises {expected!r}"))

    # Una suite PostgreSQL aislada deja la base tan limpia como la encontro. El
    # E2E del navegador necesita, por tanto, una fixture propia y explicita. Si
    # se prepara antes de las pruebas de base, su cleanup la elimina; si se omite,
    # el navegador solo pasa cuando otra suite deja residuos por accidente.
    ordered_needles = (
        ("PostgreSQL schema suite", "/app/db/tests"),
        ("synthetic browser fixture", "/checks/e2e_fixture.py"),
        ("browser journey", "npm run test:e2e"),
    )
    positions = {
        label: next((index for index, (_, command) in enumerate(steps)
                     if needle in command), None)
        for label, needle in ordered_needles
    }
    if (any(position is None for position in positions.values())
            or not (positions["PostgreSQL schema suite"]
                    < positions["synthetic browser fixture"]
                    < positions["browser journey"])):
        findings.append(Finding(
            "LOCAL-CI-E2E-FIXTURE",
            "the synthetic browser fixture must run after the PostgreSQL schema "
            "suite and before the browser journey; E2E cannot consume another "
            "suite's residual rows"))
    return sorted(set(findings))


def validate_repository(root: Path) -> list[Finding]:
    compose = (root / "infra/local/compose.yaml").read_text(encoding="utf-8")
    bootstrap = (root / "infra/local/db/init/001_bootstrap.sql").read_text(encoding="utf-8")
    script_path = root / "infra/local/up.sh"
    script = script_path.read_text(encoding="utf-8") if script_path.is_file() else None
    reset_path = root / "infra/local/reset-empty.sh"
    reset_script = (reset_path.read_text(encoding="utf-8")
                    if reset_path.is_file() else None)
    workflow_path = root / ".github/workflows/ci.yml"
    workflow = (workflow_path.read_text(encoding="utf-8")
                if workflow_path.is_file() else "")
    return sorted(set(validate_compose(compose) + validate_bootstrap(bootstrap)
                      + validate_bootstrap_script(script)
                      + validate_empty_reset_script(reset_script)
                      + validate_ci_workflow(workflow, root)))
