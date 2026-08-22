"""Descubrimiento de componentes de cadena de suministro (FNC-SUP-001).

Lee ficheros; **nunca** ejecuta nada de lo que encuentra. Una action, una imagen,
un script de lifecycle o un paquete descubierto son datos, no comandos.

Sobre YAML: la biblioteca estándar no trae parser de YAML y el encargo prohíbe
añadir dependencias. El escáner es **orientado a líneas** y por eso *falla
cerrado*: si un fichero usa anclas, alias o merge keys, el escáner no puede
garantizar lo que ve y lo reporta como no escaneable en vez de callar. Un
inventario que silenciosamente pierde referencias es peor que no tener inventario.

Determinista: sin red, sin reloj, sin hostname, sin entorno, sin Git, sin random.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DISCOVERY_VERSION = "1"

# --------------------------------------------------------------------------- #
# Formas reconocidas
# --------------------------------------------------------------------------- #

# `uses: owner/repo@ref  # comentario`
USES_PATTERN = re.compile(
    r"^\s*(?:-\s*)?uses:\s*(?P<quote>['\"]?)(?P<ref>[^\s'\"#]+)(?P=quote)\s*(?:#\s*(?P<comment>.*))?$"
)
# `image: name:tag@sha256:...`
IMAGE_PATTERN = re.compile(
    r"^\s*(?:-\s*)?image:\s*(?P<quote>['\"]?)(?P<ref>[^\s'\"#]+)(?P=quote)\s*(?:#.*)?$"
)
# Referencia OCI escrita a mano dentro de un `run:` (por ejemplo `docker run ... node:...`).
INLINE_IMAGE_PATTERN = re.compile(
    r"(?<![\w./:@-])(?P<ref>[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64})"
)
# `python-version: "3.12"` / `node-version: 22.20.0`
RUNTIME_PATTERN = re.compile(
    r"^\s*(?P<key>[a-z][a-z0-9-]*-version):\s*(?P<quote>['\"]?)(?P<value>[^\s'\"#]+)(?P=quote)\s*(?:#.*)?$"
)
# `runs-on: ubuntu-24.04`
RUNS_ON_PATTERN = re.compile(
    r"^\s*runs-on:\s*(?P<quote>['\"]?)(?P<value>[^\s'\"#\[]+)(?P=quote)\s*(?:#.*)?$"
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
OCI_DIGEST = re.compile(r"^(?P<name>[a-z0-9][a-z0-9._/-]*):(?P<tag>[A-Za-z0-9._-]+)@sha256:(?P<digest>[0-9a-f]{64})$")
SEMVER_EXACT = re.compile(r"^\d+(\.\d+){1,3}$")
RUNNER_EXACT = re.compile(r"^[a-z0-9]+(-[0-9]+\.[0-9]+)$")

# Construcciones YAML que un escáner de líneas no puede resolver con honestidad.
# Un alias solo es alias en posición de valor: `clave: *ancla` o `- *ancla`. Un
# glob de shell dentro de un `run:` (`spikes/*/test/*.test.mjs`) no lo es, y
# confundirlos declararía ilegible un fichero perfectamente legible.
UNSUPPORTED_YAML = (
    (re.compile(r"^\s*(?:-\s+)?[\w.-]+:\s*&[\w.-]+\s*$"), "anchor"),
    (re.compile(r"^\s*(?:-\s+|[\w.-]+:\s+)\*[\w.-]+\s*$"), "alias"),
    (re.compile(r"^\s*<<\s*:"), "merge_key"),
)

FLOATING_RUNTIME_TOKENS = frozenset({
    "latest", "current", "stable", "main", "head", "lts", "*", "x", "latest-stable",
})

LIFECYCLE_SCRIPT_NAMES = ("preinstall", "install", "postinstall", "prepare", "prepublish")

# Se capturan todos los comandos de instalación, acotados o no. Capturar solo los
# malos dejaría ciega la regla de lifecycle scripts, que necesita ver los buenos.
INSTALL_COMMAND = re.compile(
    r"(?<![\w-])(?:npm\s+(?:ci|install|i)(?![\w-])|pnpm\s+(?:install|add)|yarn\s+(?:install|add)"
    r"|pip3?\s+install)"
)
BOUNDED_INSTALL = re.compile(
    r"(?<![\w-])(?:npm\s+ci(?![\w-])|pnpm\s+install\s+--frozen-lockfile"
    r"|yarn\s+install\s+--frozen-lockfile|pip3?\s+install\s+-r\s+\S+"
    r"|pip3?\s+install\s+--require-hashes)"
)

VENDORED_PARTS = frozenset({
    "node_modules", "vendor", ".venv", "venv", "__pycache__", ".git", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages",
})


class DiscoveryError(Exception):
    """El árbol no puede recorrerse con seguridad."""


@dataclass(frozen=True, order=True)
class Component:
    """Un componente observado, con su procedencia exacta."""
    component_type: str
    identifier: str
    path: str
    line: int
    source_digest: str
    reference: str = ""
    detail: str = field(default="", compare=False)
    attributes: tuple[tuple[str, str], ...] = field(default=(), compare=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "identifier": self.identifier,
            "reference": self.reference,
            "path": self.path,
            "line": self.line,
            "source_digest": self.source_digest,
            "detail": self.detail,
            "attributes": dict(self.attributes),
            "discovery_version": DISCOVERY_VERSION,
        }


# --------------------------------------------------------------------------- #
# Contención de rutas
# --------------------------------------------------------------------------- #

def safe_relative(raw: str) -> bool:
    """Rechaza absolutas, unidades de Windows y `..`, aunque `..` resolviese dentro.

    Dos grafías del mismo fichero harían ambigua la contabilidad de digests.
    """
    if not raw or raw.startswith(("/", "\\")):
        return False
    if len(raw) > 1 and raw[1] == ":":
        return False
    return ".." not in Path(raw).parts


def resolve_inside(root: Path, relative: str) -> Path | None:
    if not safe_relative(relative):
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def is_vendored(relative: Path) -> bool:
    return any(part in VENDORED_PARTS for part in relative.parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(root: Path, patterns: list[str]) -> list[Path]:
    """Rutas relativas ordenadas. El orden del filesystem no altera el resultado.

    Un symlink se descarta: seguirlo permitiría inventariar ficheros de fuera del
    árbol como si fueran propios.
    """
    seen: set[Path] = set()
    for pattern in sorted(patterns):
        for candidate in root.glob(pattern):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative = candidate.relative_to(root)
            if is_vendored(relative):
                continue
            seen.add(relative)
    return sorted(seen, key=lambda item: item.as_posix())


def read_text(root: Path, relative: Path) -> str | None:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def unsupported_yaml_constructs(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        for pattern, name in UNSUPPORTED_YAML:
            if pattern.search(stripped):
                found.append((number, name))
    return sorted(set(found))


# --------------------------------------------------------------------------- #
# Extractores
# --------------------------------------------------------------------------- #

def extract_actions(text: str, relative: Path, digest: str) -> list[Component]:
    """`uses:` en un workflow. Una action local (`./…`) no es un componente externo."""
    components: list[Component] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = USES_PATTERN.match(line)
        if not match:
            continue
        reference = match.group("ref")
        if reference.startswith((".", "/")) or reference.startswith("docker://"):
            kind = "local_or_docker"
        else:
            kind = "registry"
        name, separator, ref = reference.partition("@")
        components.append(Component(
            component_type="github_action",
            identifier=name,
            reference=reference,
            path=relative.as_posix(),
            line=number,
            source_digest=digest,
            detail=(match.group("comment") or "").strip(),
            attributes=(("ref", ref if separator else ""), ("form", kind)),
        ))
    return components


def extract_images(text: str, relative: Path, digest: str) -> list[Component]:
    """`image:` declarado y referencias OCI escritas dentro de un `run:`."""
    components: list[Component] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = IMAGE_PATTERN.match(line)
        if match:
            reference = match.group("ref")
            components.append(Component(
                component_type="oci_image",
                identifier=reference.split("@", 1)[0].split(":", 1)[0],
                reference=reference,
                path=relative.as_posix(),
                line=number,
                source_digest=digest,
                attributes=(("form", "declared"),),
            ))
            continue
        stripped = line.split("#", 1)[0]
        if IMAGE_PATTERN.match(stripped):
            continue
        for inline in INLINE_IMAGE_PATTERN.finditer(stripped):
            reference = inline.group("ref")
            components.append(Component(
                component_type="oci_image",
                identifier=reference.split("@", 1)[0].split(":", 1)[0],
                reference=reference,
                path=relative.as_posix(),
                line=number,
                source_digest=digest,
                attributes=(("form", "inline_command"),),
            ))
    return components


def extract_runtimes(text: str, relative: Path, digest: str) -> list[Component]:
    """`*-version:` y `runs-on:`: lo que determina con qué se ejecuta un resultado."""
    components: list[Component] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = RUNTIME_PATTERN.match(line)
        if match:
            components.append(Component(
                component_type="runtime",
                identifier=match.group("key"),
                reference=match.group("value"),
                path=relative.as_posix(),
                line=number,
                source_digest=digest,
                attributes=(("form", "setup_action_input"),),
            ))
            continue
        runner = RUNS_ON_PATTERN.match(line)
        if runner:
            components.append(Component(
                component_type="runtime",
                identifier="runs-on",
                reference=runner.group("value"),
                path=relative.as_posix(),
                line=number,
                source_digest=digest,
                attributes=(("form", "runner_image"),),
            ))
    return components


def extract_manifests(root: Path, relative: Path, digest: str) -> list[Component]:
    """`package.json`: nombre, workspaces y scripts de lifecycle declarados."""
    text = read_text(root, relative)
    if text is None:
        return []
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return [Component(
            component_type="package_manifest",
            identifier=relative.as_posix(),
            reference="unparseable",
            path=relative.as_posix(),
            line=1,
            source_digest=digest,
            attributes=(("parse", "failed"),),
        )]
    if not isinstance(document, dict):
        document = {}
    scripts = document.get("scripts") or {}
    lifecycle = sorted(name for name in LIFECYCLE_SCRIPT_NAMES
                       if isinstance(scripts, dict) and name in scripts)
    dependency_counts = {
        section: len(document.get(section) or {})
        for section in ("dependencies", "devDependencies", "optionalDependencies",
                        "peerDependencies")
        if isinstance(document.get(section), dict)
    }
    return [Component(
        component_type="package_manifest",
        identifier=relative.as_posix(),
        reference=str(document.get("name") or relative.parent.as_posix()),
        path=relative.as_posix(),
        line=1,
        source_digest=digest,
        detail=str(document.get("version") or ""),
        attributes=(
            ("ecosystem", "npm"),
            ("lifecycle_scripts", ",".join(lifecycle)),
            ("workspaces", "yes" if document.get("workspaces") else "no"),
            ("declared_dependencies", str(sum(dependency_counts.values()))),
        ),
    )]


def extract_lockfiles(root: Path, relative: Path, digest: str) -> list[Component]:
    """Lockfile: su alcance es el directorio en el que vive."""
    ecosystem = {
        "package-lock.json": "npm", "npm-shrinkwrap.json": "npm",
        "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn",
        "poetry.lock": "poetry", "Pipfile.lock": "pipenv",
    }.get(relative.name, "unknown")
    lockfile_version = ""
    if relative.name in ("package-lock.json", "npm-shrinkwrap.json"):
        text = read_text(root, relative)
        try:
            document = json.loads(text or "{}")
            lockfile_version = str(document.get("lockfileVersion", ""))
        except json.JSONDecodeError:
            lockfile_version = "unparseable"
    return [Component(
        component_type="lockfile",
        identifier=relative.as_posix(),
        reference=relative.name,
        path=relative.as_posix(),
        line=1,
        source_digest=digest,
        detail=lockfile_version,
        attributes=(("ecosystem", ecosystem), ("scope", relative.parent.as_posix())),
    )]


def extract_install_commands(text: str, relative: Path, digest: str) -> list[Component]:
    """Comandos de instalación en CI: acotados o no. No se ejecutan, se leen."""
    components: list[Component] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        if not INSTALL_COMMAND.search(stripped):
            continue
        bounded = bool(BOUNDED_INSTALL.search(stripped))
        ignores_scripts = "--ignore-scripts" in stripped
        components.append(Component(
            component_type="external_build_service",
            identifier="install_command",
            reference=stripped.strip()[:200],
            path=relative.as_posix(),
            line=number,
            source_digest=digest,
            attributes=(
                ("bounded", "yes" if bounded else "no"),
                ("ignore_scripts", "yes" if ignores_scripts else "no"),
            ),
        ))
    return components


def extract_update_monitors(root: Path, relative: Path, digest: str) -> list[Component]:
    """`dependabot.yml`: qué ecosistemas y directorios están vigilados."""
    text = read_text(root, relative)
    if text is None:
        return []
    components: list[Component] = []
    ecosystem = None
    ecosystem_line = 0
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        eco = re.match(r"^\s*-?\s*package-ecosystem:\s*['\"]?([^\s'\"]+)", stripped)
        if eco:
            ecosystem = eco.group(1)
            ecosystem_line = number
            continue
        directory = re.match(r"^\s*directory:\s*['\"]?([^\s'\"]+)", stripped)
        if directory and ecosystem:
            components.append(Component(
                component_type="generated_artifact",
                identifier="update_monitor",
                reference=f"{ecosystem}:{directory.group(1)}",
                path=relative.as_posix(),
                line=ecosystem_line,
                source_digest=digest,
                attributes=(("ecosystem", ecosystem), ("directory", directory.group(1))),
            ))
            ecosystem = None
    return components


# --------------------------------------------------------------------------- #
# Inventario
# --------------------------------------------------------------------------- #

def discover(model: dict[str, Any], root: Path) -> dict[str, Any]:
    """Inventario estable y ordenado del árbol dado. Nunca ejecuta lo descubierto."""
    root = root.resolve()
    rules = model.get("discovery_rules", {})
    components: list[Component] = []
    scanned: list[dict[str, str]] = []
    unscannable: list[dict[str, Any]] = []
    unsafe: list[str] = []

    def scan(kind: str) -> list[Path]:
        return collect_files(root, list(rules.get(kind, {}).get("include_globs", [])))

    workflow_files = scan("workflows")
    compose_files = scan("compose")
    manifest_files = scan("package_manifests")
    lockfile_files = scan("lockfiles")
    monitor_files = scan("update_monitors")

    every = sorted({*workflow_files, *compose_files, *manifest_files,
                    *lockfile_files, *monitor_files},
                   key=lambda item: item.as_posix())

    for relative in every:
        posix = relative.as_posix()
        if resolve_inside(root, posix) is None:
            unsafe.append(posix)
            continue
        digest = sha256_file(root / relative)
        scanned.append({"path": posix, "sha256": digest})

        if relative in workflow_files or relative in compose_files:
            text = read_text(root, relative)
            if text is None:
                unscannable.append({"path": posix, "reason": "unreadable"})
                continue
            broken = unsupported_yaml_constructs(text)
            if broken:
                unscannable.append({
                    "path": posix, "reason": "unsupported_yaml",
                    "constructs": sorted({name for _, name in broken}),
                    "lines": sorted({number for number, _ in broken}),
                })
                continue
            components.extend(extract_images(text, relative, digest))
            if relative in workflow_files:
                components.extend(extract_actions(text, relative, digest))
                components.extend(extract_runtimes(text, relative, digest))
                components.extend(extract_install_commands(text, relative, digest))
        if relative in manifest_files:
            components.extend(extract_manifests(root, relative, digest))
        if relative in lockfile_files:
            components.extend(extract_lockfiles(root, relative, digest))
        if relative in monitor_files:
            components.extend(extract_update_monitors(root, relative, digest))

    ordered = sorted(components)
    return {
        "root": root.as_posix(),
        "discovery_version": DISCOVERY_VERSION,
        "scanned_files": scanned,
        "scanned_file_count": len(scanned),
        "unscannable_files": sorted(unscannable, key=lambda item: item["path"]),
        "unsafe_paths": sorted(unsafe),
        "components": [component.as_dict() for component in ordered],
        "component_count": len(ordered),
        "counts_by_type": {
            kind: sum(1 for component in ordered if component.component_type == kind)
            for kind in sorted({component.component_type for component in ordered})
        },
    }


def component_dicts(inventory: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [item for item in inventory.get("components", [])
            if item.get("component_type") == kind]


def as_error(component: Component) -> dict[str, Any]:
    return asdict(component)
