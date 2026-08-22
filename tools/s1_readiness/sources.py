"""Lectura de fuentes estructuradas de verdad (FNC-GAT-003).

El repositorio declara explicitamente que, cuando el documento y el modelo
difieren, manda el modelo. Por eso aqui **solo** se leen fuentes estructuradas:
JSON y el front-matter YAML de las fichas de tarea. La prosa se cita, nunca se
convierte en estado.

Sobre el front-matter: no hay parser de YAML en la biblioteca estandar y no se
pueden anadir dependencias, asi que se lee un subconjunto estricto de una linea
por clave. Si aparece una construccion que ese subconjunto no entiende, se
reporta como no legible en vez de adivinar.

Determinista: sin red, reloj, hostname, entorno, Git ni aleatoriedad.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# `clave: valor`, `clave: [a, b]`, `clave: "valor"`.
FRONT_MATTER_LINE = re.compile(
    r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*(?P<value>.*?)\s*$")
LIST_VALUE = re.compile(r"^\[(?P<items>.*)\]$")
BLOCK_LIST_ITEM = re.compile(r"^\s+-\s+(?P<item>.+?)\s*$")
UNSUPPORTED_FRONT_MATTER = re.compile(r"^\s+\S+:")

# Claves de estado que usan las distintas fuentes para decir lo mismo.
STATUS_KEYS = ("status", "state", "readiness")
OWNER_KEYS = ("owner_role", "owner", "owners", "required_roles")
ACCEPTANCE_KEYS = ("acceptance", "human_acceptance", "approved_by")

MET_TOKENS = frozenset({"met", "accepted", "approved", "passed", "done", "closed",
                        "satisfied", "signed"})
UNASSIGNED_TOKENS = frozenset({"", "unassigned", "none", "null", "tbd", "pending"})


@dataclass(frozen=True, order=True)
class Observation:
    """Un hecho leido de una fuente, con su procedencia exacta."""
    subject_kind: str
    subject_id: str
    field_name: str
    value: str
    source_path: str
    locator: str
    source_digest: str
    detail: str = field(default="", compare=False)

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.lower() in {
        ".json", ".md", ".py", ".sql", ".toml", ".yaml", ".yml",
    }:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            payload = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def safe_relative(raw: str) -> bool:
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
    if candidate.is_symlink():
        return None
    return candidate


def normalise_status(value: Any) -> str:
    return str(value or "").strip().lower()


def is_met(value: Any) -> bool:
    """Solo un token explicito de aprobacion cuenta. Todo lo demas es `no`."""
    return normalise_status(value) in MET_TOKENS


def is_assigned(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value) and all(is_assigned(item) for item in value)
    return normalise_status(value) not in UNASSIGNED_TOKENS


def read_json(root: Path, relative: str) -> tuple[dict[str, Any] | None, str, str]:
    """Devuelve documento, digest y motivo de fallo si lo hubo."""
    resolved = resolve_inside(root, relative)
    if resolved is None:
        return None, "", "path is absolute, traverses, escapes the tree or is a symlink"
    if not resolved.is_file():
        return None, "", "file does not exist"
    digest = sha256_file(resolved)
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, digest, f"unreadable: {type(error).__name__}"
    if not isinstance(document, dict):
        return None, digest, "the document is not an object"
    return document, digest, ""


def read_front_matter(root: Path, relative: str) -> tuple[dict[str, Any], str, str]:
    """Front-matter YAML en el subconjunto soportado. Falla cerrado si no lo es."""
    resolved = resolve_inside(root, relative)
    if resolved is None or not resolved.is_file():
        return {}, "", "file is missing or unsafe"
    digest = sha256_file(resolved)
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return {}, digest, f"unreadable: {type(error).__name__}"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, digest, "the document has no front-matter"
    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        block.append(line)
    else:
        return {}, digest, "the front-matter is not closed"

    parsed: dict[str, Any] = {}
    pending_list_key: str | None = None
    for number, line in enumerate(block, start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Forma de bloque: `clave:` seguida de lineas `  - elemento`. Es un
        # subconjunto sin ambiguedad, asi que se lee en vez de rechazar la ficha
        # entera por una clave que ni siquiera hace falta.
        block_item = BLOCK_LIST_ITEM.match(line)
        if block_item:
            if pending_list_key is None:
                return {}, digest, f"line {number} starts a list without a key"
            parsed[pending_list_key].append(block_item.group("item").strip().strip("'\""))
            continue
        if UNSUPPORTED_FRONT_MATTER.match(line):
            return {}, digest, f"line {number} uses a construct this reader does not support"
        match = FRONT_MATTER_LINE.match(line)
        if not match:
            return {}, digest, f"line {number} is not a simple key: value pair"
        key = match.group("key")
        raw = match.group("value").strip()
        if raw == "":
            parsed[key] = []
            pending_list_key = key
            continue
        pending_list_key = None
        listed = LIST_VALUE.match(raw)
        if listed:
            items = [item.strip().strip("'\"") for item in listed.group("items").split(",")]
            parsed[key] = [item for item in items if item]
        else:
            parsed[key] = raw.strip("'\"")
    return parsed, digest, ""


def _first(document: dict[str, Any], keys: tuple[str, ...], default: str = "") -> Any:
    for key in keys:
        if key in document:
            return document[key]
    return default


def extract_gates(document: dict[str, Any], key: str, path: str,
                  digest: str) -> list[Observation]:
    """Lee la lista de gates que la fuente declara bajo `key`."""
    observations: list[Observation] = []
    entries = document.get(key)
    if not isinstance(entries, list):
        return observations
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("id", "")).strip()
        if not identifier:
            continue
        locator = f"$.{key}[{index}]"
        observations.append(Observation(
            "gate", identifier, "status", normalise_status(_first(entry, STATUS_KEYS)),
            path, locator, digest, str(entry.get("rule", ""))[:160]))
        owner = _first(entry, OWNER_KEYS)
        if owner:
            owner_value = ", ".join(owner) if isinstance(owner, list) else str(owner)
            observations.append(Observation(
                "gate", identifier, "owner_role", owner_value, path, locator, digest))
        acceptance = _first(entry, ACCEPTANCE_KEYS)
        if acceptance:
            observations.append(Observation(
                "gate", identifier, "acceptance", normalise_status(acceptance),
                path, locator, digest))
    return observations


def extract_decisions(document: dict[str, Any], key: str, path: str,
                      digest: str) -> list[Observation]:
    observations: list[Observation] = []
    entries = document.get(key)
    if not isinstance(entries, list):
        return observations
    for index, entry in enumerate(entries):
        locator = f"$.{key}[{index}]"
        if isinstance(entry, str):
            observations.append(Observation(
                "decision", entry.strip(), "status", "open", path, locator, digest))
            continue
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("id", "")).strip()
        if not identifier:
            continue
        # Una decision sin campo de estado esta abierta: ausencia no es aprobacion.
        observations.append(Observation(
            "decision", identifier, "status",
            normalise_status(_first(entry, STATUS_KEYS, "pending_human")),
            path, locator, digest, str(entry.get("question", ""))[:200]))
        owner = _first(entry, OWNER_KEYS)
        if owner:
            owner_value = ", ".join(owner) if isinstance(owner, list) else str(owner)
            observations.append(Observation(
                "decision", identifier, "owner_role", owner_value, path, locator, digest))
        blocks = entry.get("blocks", [])
        if isinstance(blocks, list):
            for gate in blocks:
                gate_id = str(gate).strip()
                if gate_id:
                    observations.append(Observation(
                        "decision", identifier, "blocks_gate", gate_id,
                        path, locator, digest))
    return observations


def extract_document_flags(document: dict[str, Any], path: str,
                           digest: str) -> list[Observation]:
    """Banderas de gobierno del propio documento, no de sus listas."""
    observations: list[Observation] = []
    identifier = str(document.get("task_id") or document.get("task") or path)
    for key in ("status", "human_acceptance", "data_ceiling", "agent_may_accept"):
        if key in document:
            observations.append(Observation(
                "contract", identifier, key, normalise_status(document[key]),
                path, f"$.{key}", digest))
    return observations


def extract_adr_readiness(document: dict[str, Any], path: str,
                          digest: str) -> list[Observation]:
    """`required_s1_adrs` mas el readiness de cada ADR inventariado."""
    observations: list[Observation] = []
    required = document.get("required_s1_adrs")
    if isinstance(required, list):
        for identifier in required:
            observations.append(Observation(
                "adr", str(identifier), "required_for_s1", "true", path,
                "$.required_s1_adrs", digest))
    for index, record in enumerate(document.get("adrs", []) or []):
        if not isinstance(record, dict):
            continue
        identifier = str(record.get("id", "")).strip()
        if not identifier:
            continue
        observations.append(Observation(
            "adr", identifier, "readiness", normalise_status(record.get("readiness")),
            path, f"$.adrs[{index}]", digest,
            ", ".join(str(item) for item in record.get("blockers", []) or [])[:200]))
    rule = document.get("release_rule")
    if isinstance(rule, dict):
        observations.append(Observation(
            "gate", str(rule.get("gate", "S1-READY")), "status",
            normalise_status(rule.get("state")), path, "$.release_rule", digest,
            "adr release rule"))
    return observations


def extract_task_cards(root: Path, glob: str) -> tuple[list[Observation], list[dict[str, str]]]:
    """Fichas de tarea: estado, gate, implementador y revisores independientes."""
    observations: list[Observation] = []
    unreadable: list[dict[str, str]] = []
    base = root.resolve()
    for absolute in sorted(base.glob(glob)):
        if not absolute.is_file() or absolute.is_symlink():
            continue
        relative = absolute.relative_to(base).as_posix()
        parsed, digest, reason = read_front_matter(root, relative)
        if reason:
            unreadable.append({"path": relative, "reason": reason})
            continue
        identifier = str(parsed.get("task") or parsed.get("id") or absolute.stem)
        for key in ("status", "gate", "implementer", "data_ceiling", "base_sha"):
            if key in parsed:
                value = parsed[key]
                observations.append(Observation(
                    "task", identifier, key,
                    ", ".join(value) if isinstance(value, list) else normalise_status(value),
                    relative, f"front-matter.{key}", digest))
        reviewers = parsed.get("independent_reviewers")
        if reviewers is not None:
            observations.append(Observation(
                "task", identifier, "independent_reviewers",
                ", ".join(reviewers) if isinstance(reviewers, list) else str(reviewers),
                relative, "front-matter.independent_reviewers", digest))
    return observations, unreadable


def extract_owner_slots(root: Path, relative: str) -> tuple[list[Observation], str]:
    """Slots de owner humano del front-matter de la fase vigente."""
    parsed, digest, reason = read_front_matter(root, relative)
    if reason:
        return [], reason
    observations = [
        Observation("owner_slot", key, "assigned_to", str(value), relative,
                    f"front-matter.{key}", digest)
        for key, value in sorted(parsed.items()) if key.endswith("_owner")
    ]
    for key in ("current_gate", "data_ceiling", "execution_stage"):
        if key in parsed:
            observations.append(Observation(
                "phase", "CURRENT_PHASE", key, str(parsed[key]), relative,
                f"front-matter.{key}", digest))
    return observations, ""
