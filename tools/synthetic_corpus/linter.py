from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .common import sha256_bytes, tracked_files
from .generator import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    MANIFEST_NAME,
    build_corpus,
)

ALLOWED_CLASSIFICATION = "synthetic_financial_sensitive"
ALLOWED_LOCALES = {"es-CO", "en-US", "es-MX"}
ALLOWED_ENCODINGS = {"utf-8", "latin-1"}
ALLOWED_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
}
DOMAIN_PATTERN = re.compile(
    r"(?i)(?:https?://|mailto:)?(?:[a-z0-9_+.-]+@)?([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,})(?=\b|[/:])"
)
NUMERIC_PATTERN = re.compile(r"^-?\d+(?:[.,]\d+)?$")


@dataclass
class LintReport:
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    checked_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, code: str, message: str) -> None:
        self.errors.append({"code": code, "message": message})

    def warning(self, code: str, message: str) -> None:
        self.warnings.append({"code": code, "message": message})

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked_files": self.checked_files,
            "errors": self.errors,
            "ok": self.ok,
            "warnings": self.warnings,
        }


def _safe_relative_path(raw_path: Any) -> str | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = PurePosixPath(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in raw_path:
        return None
    return candidate.as_posix()


def _domain_is_reserved(domain: str) -> bool:
    normalized = domain.lower().rstrip(".")
    return (
        normalized in ALLOWED_DOMAINS
        or normalized.endswith(".example")
        or normalized.endswith(".test")
        or normalized.endswith(".invalid")
    )


def _scan_domains(text: str, path: str, report: LintReport) -> None:
    for match in DOMAIN_PATTERN.finditer(text):
        domain = match.group(1)
        if not _domain_is_reserved(domain):
            report.error("DAT-DOMAIN-NOT-RESERVED", f"{path}: non-reserved domain {domain!r}")


def _scan_formula_cells(rows: list[list[str]], path: str, report: LintReport) -> None:
    for row_number, row in enumerate(rows[1:], start=2):
        for column_number, cell in enumerate(row, start=1):
            stripped = cell.lstrip()
            if not stripped or stripped[0] not in "=+-@":
                continue
            if NUMERIC_PATTERN.fullmatch(stripped):
                continue
            report.warning(
                "DAT-INERT-FORMULA-CELL",
                f"{path}:{row_number}:{column_number} begins with a spreadsheet formula prefix",
            )


def lint_corpus(root: Path) -> LintReport:
    report = LintReport()
    manifest_path = root / MANIFEST_NAME
    if manifest_path.is_symlink():
        report.error("DAT-MANIFEST-SYMLINK", "manifest must not be a symlink")
        return report
    if not manifest_path.is_file():
        report.error("DAT-MANIFEST-MISSING", f"missing {MANIFEST_NAME}")
        return report

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        report.error("DAT-MANIFEST-INVALID", f"cannot parse manifest: {error}")
        return report

    if manifest.get("synthetic") is not True:
        report.error("DAT-NOT-SYNTHETIC", "manifest.synthetic must be true")
    if manifest.get("classification") != ALLOWED_CLASSIFICATION:
        report.error(
            "DAT-CLASSIFICATION-DENIED",
            f"classification must equal {ALLOWED_CLASSIFICATION!r}",
        )
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        report.error("DAT-PROVENANCE-MISSING", "provenance object is required")
    else:
        if provenance.get("method") != "deterministic_generation":
            report.error("DAT-PROVENANCE-DENIED", "only deterministic_generation is allowed")
        if provenance.get("real_data_used") is not False:
            report.error("DAT-REAL-DATA-DENIED", "real_data_used must be false")
        if provenance.get("external_inputs") != []:
            report.error("DAT-EXTERNAL-INPUT-DENIED", "external_inputs must be an empty list")

    generator = manifest.get("generator")
    if not isinstance(generator, dict):
        report.error("DAT-GENERATOR-MISSING", "generator object is required")
    else:
        if generator.get("name") != GENERATOR_NAME:
            report.error("DAT-GENERATOR-UNKNOWN", "generator name is not allowlisted")
        if generator.get("version") != GENERATOR_VERSION:
            report.error("DAT-GENERATOR-VERSION", "generator version differs from this linter")
        if not isinstance(generator.get("seed"), str) or not generator["seed"].startswith("FNC-DAT-002-"):
            report.error("DAT-SEED-INVALID", "seed must use the declared synthetic namespace")

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        report.error("DAT-FILES-MISSING", "manifest.files must be a non-empty list")
        return report

    manifest_paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            report.error("DAT-FILE-ENTRY-INVALID", f"files[{index}] must be an object")
            continue
        relative_path = _safe_relative_path(entry.get("path"))
        if relative_path is None:
            report.error("DAT-PATH-UNSAFE", f"files[{index}].path is unsafe")
            continue
        if relative_path in manifest_paths:
            report.error("DAT-PATH-DUPLICATE", f"duplicate manifest path {relative_path}")
            continue
        manifest_paths.add(relative_path)
        file_path = root / relative_path
        if file_path.is_symlink():
            report.error("DAT-FILE-SYMLINK", f"{relative_path} must not be a symlink")
            continue
        if not file_path.is_file():
            report.error("DAT-FILE-MISSING", f"missing declared file {relative_path}")
            continue

        content = file_path.read_bytes()
        report.checked_files += 1
        if entry.get("bytes") != len(content):
            report.error("DAT-BYTES-MISMATCH", f"{relative_path}: byte count differs")
        if entry.get("sha256") != sha256_bytes(content):
            report.error("DAT-HASH-MISMATCH", f"{relative_path}: SHA-256 differs")
        encoding = entry.get("encoding")
        if encoding not in ALLOWED_ENCODINGS:
            report.error("DAT-ENCODING-DENIED", f"{relative_path}: encoding {encoding!r} is not allowed")
            continue
        locale = entry.get("locale")
        if locale not in ALLOWED_LOCALES:
            report.error("DAT-LOCALE-DENIED", f"{relative_path}: locale {locale!r} is not allowed")
        try:
            text = content.decode(encoding)
        except UnicodeError as error:
            report.error("DAT-DECODE-FAILED", f"{relative_path}: {error}")
            continue
        if "SYN-" not in text:
            report.error("DAT-SYNTHETIC-MARKER-MISSING", f"{relative_path}: missing SYN- marker")
        _scan_domains(text, relative_path, report)

        delimiter = entry.get("delimiter")
        if delimiter not in {",", ";", "\t"}:
            report.error("DAT-DELIMITER-DENIED", f"{relative_path}: invalid delimiter")
            continue
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error as error:
            report.error("DAT-CSV-INVALID", f"{relative_path}: {error}")
            continue
        actual_rows = max(len(rows) - 1, 0)
        if entry.get("row_count") != actual_rows:
            report.error("DAT-ROW-COUNT-MISMATCH", f"{relative_path}: row count differs")
        _scan_formula_cells(rows, relative_path, report)

    actual_inventory = set(tracked_files(root)) - {MANIFEST_NAME}
    for unlisted in sorted(actual_inventory - manifest_paths):
        report.error("DAT-UNLISTED-FILE", f"unlisted file {unlisted}")
    for missing in sorted(manifest_paths - actual_inventory):
        if not (root / missing).exists():
            continue
        report.error("DAT-INVENTORY-MISMATCH", f"manifest path is not a regular tracked file: {missing}")

    return report


def verify_corpus(root: Path) -> LintReport:
    report = lint_corpus(root)
    expected = build_corpus()
    actual_paths = set(tracked_files(root))
    expected_paths = set(expected)
    for path in sorted(expected_paths | actual_paths):
        actual_file = root / path
        if path not in expected:
            continue
        if not actual_file.is_file():
            report.error("DAT-REPRODUCIBILITY-MISSING", f"reproducible output missing {path}")
            continue
        if actual_file.read_bytes() != expected[path]:
            report.error("DAT-REPRODUCIBILITY-MISMATCH", f"regeneration differs for {path}")
    return report
