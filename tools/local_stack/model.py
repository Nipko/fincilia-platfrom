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
# El migrador se invoca a mano. Un stack que migra en `up` migra una vez por
# replica y convierte un despliegue en un cambio de esquema.
MIGRATE_ENTRYPOINT = "db.migrate.apply"


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
                          "objectstore": "/minio/health/live"}.get(name)
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
            or "name: fincilia_local_pgdata" not in text:
        findings.append(Finding("LOCAL-NAMED-VOLUME",
                                "explicit named persistence volume is required"))
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


def validate_repository(root: Path) -> list[Finding]:
    compose = (root / "infra/local/compose.yaml").read_text(encoding="utf-8")
    bootstrap = (root / "infra/local/db/init/001_bootstrap.sql").read_text(encoding="utf-8")
    return sorted(set(validate_compose(compose) + validate_bootstrap(bootstrap)))
