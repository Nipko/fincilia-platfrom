from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .common import atomic_write, pretty_json_bytes, sha256_bytes, tracked_files

GENERATOR_NAME = "fincilia-synthetic-corpus"
GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = "FNC-DAT-002-SEED-001"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class Fixture:
    path: str
    content: bytes
    encoding: str
    locale: str
    delimiter: str
    fixture_type: str
    row_count: int
    expected_status: str
    notes: tuple[str, ...]


def _csv_bytes(
    headers: list[str],
    rows: Iterable[list[str]],
    *,
    delimiter: str,
    encoding: str,
) -> tuple[bytes, int]:
    buffer = io.StringIO(newline="")
    writer = csv.writer(
        buffer,
        delimiter=delimiter,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerow(headers)
    materialized_rows = list(rows)
    writer.writerows(materialized_rows)
    return buffer.getvalue().encode(encoding), len(materialized_rows)


def _fixtures() -> list[Fixture]:
    bank_content, bank_rows = _csv_bytes(
        [
            "source_row_id",
            "fecha",
            "referencia",
            "descripcion",
            "debito",
            "credito",
            "saldo",
            "moneda",
            "synthetic_marker",
        ],
        [
            ["SYN-BANK-000", "2026-03-01", "SYN-OPEN", "Saldo inicial sintético", "", "", "1000000,00", "COP", "SYN-ONLY"],
            ["SYN-BANK-001", "2026-03-04", "SYN-DUP", "Transferencia sintética A", "50000,00", "", "950000,00", "COP", "SYN-ONLY"],
            ["SYN-BANK-002", "2026-03-04", "SYN-DUP", "Transferencia sintética B", "50000,00", "", "900000,00", "COP", "SYN-ONLY"],
            ["SYN-BANK-003", "2026-03-05", "SYN-LIQ-77", "Abono de liquidación sintética", "", "114240,00", "1014240,00", "COP", "SYN-ONLY"],
        ],
        delimiter=";",
        encoding="utf-8",
    )
    payments_content, payment_rows = _csv_bytes(
        [
            "transaction_id",
            "date",
            "gross",
            "fee",
            "withholding",
            "net",
            "currency",
            "status",
            "synthetic_marker",
        ],
        [
            ["SYN-PAY-1042", "2026-03-04", "119000.00", "3570.00", "1190.00", "114240.00", "COP", "settled", "SYN-ONLY"],
            ["SYN-PAY-USD-01", "2026-03-05", "125.50", "3.77", "0.00", "121.73", "USD", "settled", "SYN-ONLY"],
        ],
        delimiter=",",
        encoding="utf-8",
    )
    ambiguous_content, ambiguous_rows = _csv_bytes(
        [
            "fila_sintetica",
            "fecha_ambigua",
            "importe",
            "descripción",
            "columna_sorpresa",
            "expected_semantics",
        ],
        [
            ["SYN-MX-001", "03/04/2026", "1.234,56", "Operación sintética con acento", "SYN-UNKNOWN-A", "requires_confirmation"],
            ["SYN-MX-002", "04/03/2026", "-25,00", "Débito sintético", "SYN-UNKNOWN-B", "requires_confirmation"],
        ],
        delimiter=";",
        encoding="latin-1",
    )
    hostile_content, hostile_rows = _csv_bytes(
        ["row_id", "untrusted_text", "contact", "expected_handling", "synthetic_marker"],
        [
            ["SYN-HOSTILE-001", "=HYPERLINK(\"https://example.invalid\",\"SYN\")", "contabilidad@example.invalid", "escape_on_export", "SYN-ONLY"],
            ["SYN-HOSTILE-002", "<!DOCTYPE synthetic [<!ENTITY x \"SYN\">]>", "soporte@example.test", "treat_as_text", "SYN-ONLY"],
            ["SYN-HOSTILE-003", "@SUM(1+1)", "auditoria@example.com", "escape_on_export", "SYN-ONLY"],
        ],
        delimiter=",",
        encoding="utf-8",
    )
    partial_content, partial_rows = _csv_bytes(
        [
            "statement_id",
            "period_start",
            "period_end",
            "sequence",
            "opening_balance",
            "closing_balance",
            "completeness",
            "synthetic_marker",
        ],
        [
            ["SYN-PARTIAL-01", "2026-03-01", "2026-03-31", "1", "1000.00", "", "partial", "SYN-ONLY"],
            ["SYN-PARTIAL-01", "2026-03-01", "2026-03-31", "3", "", "1120.00", "partial", "SYN-ONLY"],
        ],
        delimiter=",",
        encoding="utf-8",
    )

    return [
        Fixture(
            path="files/bank_es_co.csv",
            content=bank_content,
            encoding="utf-8",
            locale="es-CO",
            delimiter=";",
            fixture_type="bank_statement_with_legitimate_duplicates",
            row_count=bank_rows,
            expected_status="accepted_with_duplicate_candidates",
            notes=(
                "SYN-BANK-001 and SYN-BANK-002 deliberately share date, amount and reference.",
                "Opening plus movements equals the final running balance.",
            ),
        ),
        Fixture(
            path="files/payments_en_us.csv",
            content=payments_content,
            encoding="utf-8",
            locale="en-US",
            delimiter=",",
            fixture_type="settlement_equation",
            row_count=payment_rows,
            expected_status="accepted",
            notes=("gross - fee - withholding = net using exact decimal strings",),
        ),
        Fixture(
            path="files/ambiguous_es_mx_latin1.csv",
            content=ambiguous_content,
            encoding="latin-1",
            locale="es-MX",
            delimiter=";",
            fixture_type="ambiguous_locale_and_unknown_column",
            row_count=ambiguous_rows,
            expected_status="requires_confirmation",
            notes=("Dates are intentionally ambiguous and must never be inferred silently.",),
        ),
        Fixture(
            path="files/hostile_cells.csv",
            content=hostile_content,
            encoding="utf-8",
            locale="en-US",
            delimiter=",",
            fixture_type="inert_hostile_tabular_cells",
            row_count=hostile_rows,
            expected_status="accepted_as_untrusted_text_with_warnings",
            notes=("Formula and markup strings are inert test text; never execute them.",),
        ),
        Fixture(
            path="files/partial_statement.csv",
            content=partial_content,
            encoding="utf-8",
            locale="en-US",
            delimiter=",",
            fixture_type="partial_statement_with_sequence_gap",
            row_count=partial_rows,
            expected_status="partial_blocks_certified_use",
            notes=("Sequence 2 is deliberately absent and the opening/closing evidence is incomplete.",),
        ),
    ]


def build_corpus(seed: str = DEFAULT_SEED) -> dict[str, bytes]:
    fixtures = _fixtures()
    file_entries: list[dict[str, Any]] = []
    corpus: dict[str, bytes] = {}
    for fixture in fixtures:
        corpus[fixture.path] = fixture.content
        file_entries.append(
            {
                "bytes": len(fixture.content),
                "delimiter": fixture.delimiter,
                "encoding": fixture.encoding,
                "expected_status": fixture.expected_status,
                "fixture_type": fixture.fixture_type,
                "locale": fixture.locale,
                "notes": list(fixture.notes),
                "path": fixture.path,
                "row_count": fixture.row_count,
                "sha256": sha256_bytes(fixture.content),
            }
        )

    manifest = {
        "classification": "synthetic_financial_sensitive",
        "corpus_id": "FNC-DAT-002-GOLDEN-001",
        "coverage": {
            "currencies": ["COP", "USD"],
            "encodings": ["utf-8", "latin-1"],
            "locales": ["es-CO", "en-US", "es-MX"],
            "scenarios": [
                "ambiguous_dates",
                "balance_continuity",
                "delimiter_variation",
                "formula_injection_text",
                "legitimate_duplicate_candidates",
                "partial_source",
                "settlement_equation",
                "unknown_columns",
            ],
        },
        "files": file_entries,
        "generator": {
            "name": GENERATOR_NAME,
            "seed": seed,
            "source": "tools/synthetic_corpus/generator.py",
            "version": GENERATOR_VERSION,
        },
        "policy_version": "FNC-DAT-001-v0",
        "provenance": {
            "external_inputs": [],
            "method": "deterministic_generation",
            "real_data_used": False,
            "review_required": True,
        },
        "schema_version": 1,
        "synthetic": True,
    }
    corpus[MANIFEST_NAME] = pretty_json_bytes(manifest)
    return corpus


def generate_corpus(output: Path, seed: str = DEFAULT_SEED) -> dict[str, bytes]:
    if output.is_symlink():
        raise ValueError(f"refusing to generate into symlink: {output}")
    corpus = build_corpus(seed)
    allowed_paths = set(corpus)
    unexpected = set(tracked_files(output)) - allowed_paths
    if unexpected:
        raise ValueError(f"refusing to overwrite directory with unknown files: {sorted(unexpected)}")

    for relative_path, content in sorted(corpus.items()):
        atomic_write(output / relative_path, content)
    return corpus
