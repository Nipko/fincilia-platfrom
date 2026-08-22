"""Extractores explícitos de identificadores de prueba (FNC-QA-004).

Deliberadamente pequeños y separados. **No** existe una regex global que busque
`TST-` y lo llame definición: cada extractor conoce la forma exacta que lee y
declara qué clase de fuente produce.

Solo biblioteca estándar. Determinista: sin red, reloj, entorno ni aleatoriedad.
El orden de salida es estable e independiente del orden del filesystem.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

EXTRACTOR_VERSION = "1"

TEST_ID_PATTERN = re.compile(r"TST-[A-Z0-9]{2,8}-\d{3}")
TEST_ID_EXACT = re.compile(r"^TST-[A-Z0-9]{2,8}-\d{3}$")
# `TST-CON-001..015` o `TST-LIN-001 a TST-LIN-006` son rangos narrativos.
RANGE_PATTERN = re.compile(
    r"TST-[A-Z0-9]{2,8}-\d{3}\s*(?:\.\.|…|\.\.\.|a|to|-)\s*(?:TST-[A-Z0-9]{2,8}-)?\d{3}"
)
CATALOG_ROW_PATTERN = re.compile(
    r"^\|\s*(TST-[A-Z0-9]{2,8}-\d{3})\s*\|\s*(?P<title>[^|]*?)\s*\|\s*(?P<task>[^|]*?)\s*\|\s*$"
)
PY_TEST_NAME_PATTERN = re.compile(
    r"^\s*def\s+(test_[A-Za-z0-9_]*?TST_([A-Z0-9]{2,8})_(\d{3})[A-Za-z0-9_]*)\s*\("
)

# Clases de fuente, en orden de precedencia decreciente.
SOURCE_CLASS_PRECEDENCE = (
    "contract_definition",
    "catalog_row",
    "implementation",
    "reference",
    "mention",
)

EXCLUDED_DIRECTORY_NAMES = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".idea", ".vscode",
})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".so", ".dll", ".exe", ".lock", ".png", ".jpg"})


@dataclass(frozen=True, order=True)
class Provenance:
    """Dónde y cómo se observó un identificador."""
    path: str
    locator: str
    source_class: str
    extractor_id: str
    extractor_version: str
    digest: str
    detail: str = field(default="", compare=False)

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "locator": self.locator,
            "source_class": self.source_class,
            "extractor_id": self.extractor_id,
            "extractor_version": self.extractor_version,
            "digest": self.digest,
            "detail": self.detail,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
        return True
    return relative.suffix.lower() in EXCLUDED_SUFFIXES


def discover_files(
    root: Path,
    include_globs: Iterable[str],
    excluded_path_globs: Iterable[str] = (),
) -> list[Path]:
    """Rutas relativas ordenadas. El orden del filesystem no altera el resultado."""
    seen: set[Path] = set()
    excluded = tuple(sorted(excluded_path_globs))
    for pattern in sorted(include_globs):
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            if candidate.is_symlink():
                continue
            relative = candidate.relative_to(root)
            if is_excluded(relative):
                continue
            if any(relative.match(pattern) for pattern in excluded):
                continue
            seen.add(relative)
    return sorted(seen, key=lambda p: p.as_posix())


# --------------------------------------------------------------------------- #
# Extractores de contrato (definiciones autoritativas)
# --------------------------------------------------------------------------- #

def _json_document(root: Path, relative: Path) -> Any | None:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def extract_required_tests_objects(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`$.required_tests[]` con objetos `{id, scenario, expected}`."""
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    entries = document.get("required_tests")
    if not isinstance(entries, list):
        return results
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        identifier = entry.get("id")
        if not isinstance(identifier, str):
            continue
        scenario = entry.get("scenario") or entry.get("expected") or ""
        results.append((identifier, Provenance(
            path=relative.as_posix(), locator=f"$.required_tests[{index}].id",
            source_class="contract_definition",
            extractor_id="json_required_tests_objects",
            extractor_version=EXTRACTOR_VERSION, digest=digest, detail=str(scenario)[:160],
        )))
    return results


def extract_required_tests_strings(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`$.required_tests[]` como lista de cadenas."""
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    entries = document.get("required_tests")
    if not isinstance(entries, list):
        return results
    for index, entry in enumerate(entries):
        if isinstance(entry, str):
            results.append((entry, Provenance(
                path=relative.as_posix(), locator=f"$.required_tests[{index}]",
                source_class="contract_definition",
                extractor_id="json_required_tests_strings",
                extractor_version=EXTRACTOR_VERSION, digest=digest,
            )))
    return results


def extract_required_test_scenarios(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`$.required_test_scenarios[]`, la forma que usa el contrato de completitud."""
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    entries = document.get("required_test_scenarios")
    if not isinstance(entries, list):
        return results
    for index, entry in enumerate(entries):
        identifier = entry if isinstance(entry, str) else (
            entry.get("id") if isinstance(entry, dict) else None)
        if isinstance(identifier, str):
            results.append((identifier, Provenance(
                path=relative.as_posix(), locator=f"$.required_test_scenarios[{index}]",
                source_class="contract_definition",
                extractor_id="json_required_test_scenarios",
                extractor_version=EXTRACTOR_VERSION, digest=digest,
            )))
    return results


# --------------------------------------------------------------------------- #
# Extractores de referencia (citan, no definen)
# --------------------------------------------------------------------------- #

def extract_strategy_references(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`$.risk_control_matrix[].test_ids` cita pruebas; no las define."""
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    for index, row in enumerate(document.get("risk_control_matrix", []) or []):
        if not isinstance(row, dict):
            continue
        for position, identifier in enumerate(row.get("test_ids", []) or []):
            if isinstance(identifier, str):
                results.append((identifier, Provenance(
                    path=relative.as_posix(),
                    locator=f"$.risk_control_matrix[{index}].test_ids[{position}]",
                    source_class="reference", extractor_id="json_strategy_test_ids",
                    extractor_version=EXTRACTOR_VERSION, digest=digest,
                    detail=str(row.get("risk_id", "")),
                )))
    return results


def extract_harness_references(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`$.cases[].test_refs` cita pruebas adjudicadas por el golden harness."""
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    for index, case in enumerate(document.get("cases", []) or []):
        if not isinstance(case, dict):
            continue
        for position, identifier in enumerate(case.get("test_refs", []) or []):
            if isinstance(identifier, str):
                results.append((identifier, Provenance(
                    path=relative.as_posix(),
                    locator=f"$.cases[{index}].test_refs[{position}]",
                    source_class="reference", extractor_id="json_harness_test_refs",
                    extractor_version=EXTRACTOR_VERSION, digest=digest,
                    detail=str(case.get("case_id", "")),
                )))
    return results


def extract_mutation_references(root: Path, relative: Path,
                                digest: str) -> list[tuple[str, Provenance]]:
    """`$.mutations[].test_refs` cita las pruebas que respaldan cada mutación.

    Existe porque el arnés de mutaciones ancla sus referencias en `mutations[]`,
    no en `cases[]`: sin este extractor, un contrato nuevo y elegible quedaría
    invisible y el inventario parecería completo justo donde no lo está.
    """
    document = _json_document(root, relative)
    results: list[tuple[str, Provenance]] = []
    if not isinstance(document, dict):
        return results
    for index, mutation in enumerate(document.get("mutations", []) or []):
        if not isinstance(mutation, dict):
            continue
        for position, identifier in enumerate(mutation.get("test_refs", []) or []):
            if isinstance(identifier, str):
                results.append((identifier, Provenance(
                    path=relative.as_posix(),
                    locator=f"$.mutations[{index}].test_refs[{position}]",
                    source_class="reference", extractor_id="json_mutation_test_refs",
                    extractor_version=EXTRACTOR_VERSION, digest=digest,
                    detail=str(mutation.get("mutation_id", "")),
                )))
    return results


# --------------------------------------------------------------------------- #
# Catálogo Markdown
# --------------------------------------------------------------------------- #

def extract_catalog_rows(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """Filas autoritativas del catálogo. Una mención en prosa no es una fila."""
    try:
        text = (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    results: list[tuple[str, Provenance]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = CATALOG_ROW_PATTERN.match(line)
        if not match:
            continue
        results.append((match.group(1), Provenance(
            path=relative.as_posix(), locator=f"line:{number}",
            source_class="catalog_row", extractor_id="markdown_catalog_row",
            extractor_version=EXTRACTOR_VERSION, digest=digest,
            detail=f"{match.group('title')} | {match.group('task')}",
        )))
    return results


def extract_narrative_mentions(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """Menciones en prosa. Cuentan como mención, nunca como definición.

    Un rango narrativo (`TST-CON-001..015`) se marca y **no** se expande: expandirlo
    inventaría cobertura que nadie escribió.
    """
    try:
        text = (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    results: list[tuple[str, Provenance]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if CATALOG_ROW_PATTERN.match(line):
            continue
        is_range = bool(RANGE_PATTERN.search(line))
        for match in TEST_ID_PATTERN.finditer(line):
            results.append((match.group(0), Provenance(
                path=relative.as_posix(), locator=f"line:{number}:col:{match.start() + 1}",
                source_class="mention", extractor_id="markdown_narrative_mention",
                extractor_version=EXTRACTOR_VERSION, digest=digest,
                detail="narrative_range_not_expanded" if is_range else "narrative",
            )))
    return results


# --------------------------------------------------------------------------- #
# Implementación en Python
# --------------------------------------------------------------------------- #

def extract_python_test_names(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """Nombres de método que materializan un ID: `def test_..._TST_LIN_001_...`."""
    try:
        text = (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    results: list[tuple[str, Provenance]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = PY_TEST_NAME_PATTERN.match(line)
        if not match:
            continue
        identifier = f"TST-{match.group(2)}-{match.group(3)}"
        results.append((identifier, Provenance(
            path=relative.as_posix(), locator=f"line:{number}",
            source_class="implementation", extractor_id="python_test_method_name",
            extractor_version=EXTRACTOR_VERSION, digest=digest, detail=match.group(1),
        )))
    return results


JS_TEST_NAME_PATTERN = re.compile(
    r"""^\s*(?:test|it)\s*\(\s*[`'"](?P<title>[^`'"]*?(TST-[A-Z0-9]{2,8}-\d{3})[^`'"]*)"""
)


def extract_javascript_test_names(root: Path, relative: Path, digest: str) -> list[tuple[str, Provenance]]:
    """`test('TST-TEN-001-P01 · …')` en las suites de spike.

    Existe porque ignorarlas convertiría implementaciones reales en huecos
    inventados: el extractor de Python no lee `.mjs`.
    """
    try:
        text = (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    results: list[tuple[str, Provenance]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = JS_TEST_NAME_PATTERN.match(line)
        if not match:
            continue
        for found in TEST_ID_PATTERN.finditer(match.group("title")):
            results.append((found.group(0), Provenance(
                path=relative.as_posix(), locator=f"line:{number}",
                source_class="implementation", extractor_id="javascript_test_name",
                extractor_version=EXTRACTOR_VERSION, digest=digest,
                detail=match.group("title")[:160],
            )))
    return results


EXTRACTORS: dict[str, Callable[[Path, Path, str], list[tuple[str, Provenance]]]] = {
    "json_required_tests_objects": extract_required_tests_objects,
    "json_required_tests_strings": extract_required_tests_strings,
    "json_required_test_scenarios": extract_required_test_scenarios,
    "json_strategy_test_ids": extract_strategy_references,
    "json_harness_test_refs": extract_harness_references,
    "json_mutation_test_refs": extract_mutation_references,
    "markdown_catalog_row": extract_catalog_rows,
    "markdown_narrative_mention": extract_narrative_mentions,
    "python_test_method_name": extract_python_test_names,
    "javascript_test_name": extract_javascript_test_names,
}

# Qué extractores se aplican a qué familias de fichero. Explícito: un fichero
# JSON nuevo bajo docs/ entra automaticamente por los extractores de contrato,
# de modo que un contrato nuevo elegible no puede pasar inadvertido.
EXTRACTOR_APPLICABILITY: dict[str, tuple[str, ...]] = {
    ".json": ("json_required_tests_objects", "json_required_tests_strings",
              "json_required_test_scenarios", "json_strategy_test_ids",
              "json_harness_test_refs", "json_mutation_test_refs"),
    ".md": ("markdown_catalog_row", "markdown_narrative_mention"),
    ".py": ("python_test_method_name",),
    ".mjs": ("javascript_test_name",),
}
