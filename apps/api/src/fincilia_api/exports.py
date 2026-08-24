"""Exportacion canonica acotada, reproducible y sin persistir otra copia.

El CSV no vuelve a interpretar el documento original. Lee exclusivamente el
dataset publicado, en el orden de sus filas de origen, y conserva dinero como
decimal de punto fijo. Tampoco aplica overlays: una correccion aprobada exige una
nueva version publicada; mezclarla al vuelo produciria un archivo que ningun
dataset inmutable sostiene.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

import psycopg

from . import datasets


EXPORT_PROFILE = "canonical-v1"
CSV_BATCH_SIZE = 1_000
MAX_EXPORT_ROWS = datasets.MAX_DATASET_ROWS
CSV_HEADERS = (
    "record_ordinal",
    "movement_id",
    "occurred_on",
    "posted_on",
    "value_date",
    "accounting_date",
    "amount",
    "currency",
    "direction",
    "kind",
    "description",
    "reference",
    "state",
    "canonical_schema_version",
    "engine_release",
    "lineage_state",
)


class ExportError(Exception):
    """La exportacion no puede empezar; el codigo es estable para la API."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ExportDescriptor:
    dataset_version_id: str
    row_count: int
    canonical_schema_version: str
    reproduction_key: str

    @property
    def filename(self) -> str:
        # El ID ya fue resuelto en la base y contiene solo UUID ASCII. No se usa
        # nombre de archivo del cliente en Content-Disposition.
        return f"fincilia-canonico-{self.dataset_version_id[:12]}.csv"


def preflight_export(connection: psycopg.Connection,
                     dataset_version_id: str) -> ExportDescriptor:
    """Comprueba el sello completo antes de emitir una sola cabecera HTTP."""
    dataset = datasets.load_dataset(connection, dataset_version_id)
    if dataset is None:
        raise ExportError("dataset-unknown", "no such dataset version")

    manifest = dataset.get("manifest")
    eligible = (
        dataset.get("state") == "published"
        and dataset.get("completeness_state") == "verified"
        and dataset.get("lineage_state") == "complete"
        and isinstance(manifest, dict)
        and manifest.get("reproducible") is True
        and int(dataset.get("rejected_count") or 0) == 0
        and int(dataset.get("movement_count") or 0)
        == int(dataset.get("record_count") or 0)
    )
    if not eligible:
        raise ExportError(
            "dataset-export-unavailable",
            "only a published, verified and reproducible dataset can be exported",
        )

    row_count = int(dataset["movement_count"])
    if row_count > MAX_EXPORT_ROWS:
        raise ExportError(
            "dataset-export-too-large",
            f"an export carries at most {MAX_EXPORT_ROWS} canonical rows",
        )
    return ExportDescriptor(
        dataset_version_id=str(dataset["dataset_version_id"]),
        row_count=row_count,
        canonical_schema_version=str(dataset["canonical_schema_version"]),
        reproduction_key=str(manifest["reproduction_key"]),
    )


def spreadsheet_safe(value: Any) -> str:
    """Neutraliza formulas en campos de texto sin tocar dinero ni fechas.

    Excel y herramientas similares pueden ejecutar una celda cuyo primer
    caracter significativo sea `=`, `+`, `-` o `@`. El apostrofo es la defensa
    interoperable: la hoja muestra el texto y no evalua la formula.
    """
    if value is None:
        return ""
    text = str(value)
    significant = text.lstrip(" \t\r\n")
    if significant.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_row(row: tuple[Any, ...]) -> tuple[str, ...]:
    """Serializa una fila PostgreSQL sin conversiones de coma flotante."""
    return (
        str(int(row[0])),
        str(row[1]),
        row[2].isoformat(),
        row[3].isoformat() if row[3] else "",
        row[4].isoformat() if row[4] else "",
        row[5].isoformat() if row[5] else "",
        f"{row[6]:.12f}",
        str(row[7]),
        str(row[8]),
        str(row[9]),
        spreadsheet_safe(row[10]),
        spreadsheet_safe(row[11]),
        str(row[12]),
        str(row[13]),
        str(row[14]),
        str(row[15]),
    )


def csv_chunks(rows: Iterable[tuple[Any, ...]], *,
               batch_size: int = CSV_BATCH_SIZE) -> Iterator[bytes]:
    """Produce UTF-8 BOM + RFC 4180 en lotes acotados y deterministas."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect="excel", lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    buffered = 0
    first = True

    for row in rows:
        writer.writerow(export_row(row))
        buffered += 1
        if buffered >= batch_size:
            payload = buffer.getvalue()
            yield (("\ufeff" if first else "") + payload).encode("utf-8")
            first = False
            buffer.seek(0)
            buffer.truncate(0)
            buffered = 0

    payload = buffer.getvalue()
    if payload or first:
        yield (("\ufeff" if first else "") + payload).encode("utf-8")


def stream_dataset_csv(database, *, company_id: str, subject_id: str,
                       descriptor: ExportDescriptor) -> Iterator[bytes]:
    """Mantiene RLS y el cursor de servidor vivos durante el streaming."""
    cursor_name = f"dataset_export_{uuid.uuid4().hex}"
    with database.session(company_id=company_id,
                          subject_id=subject_id) as connection:
        # Releer dentro de la transaccion que emite evita exportar si el estado
        # dejo de ser elegible entre el preflight y el primer byte.
        current = preflight_export(connection, descriptor.dataset_version_id)
        if current != descriptor:
            raise ExportError(
                "dataset-export-changed",
                "the dataset export metadata changed before streaming",
            )
        with connection.cursor(name=cursor_name) as cursor:
            cursor.itersize = CSV_BATCH_SIZE
            cursor.execute(
                "SELECT r.record_ordinal, m.movement_id, m.occurred_on, "
                "       m.posted_on, m.value_date, m.accounting_date, m.amount, "
                "       m.currency_code, m.direction, m.kind, m.description, "
                "       m.reference_original, m.state, "
                "       m.canonical_schema_version, e.release_key, "
                "       m.lineage_state "
                "FROM fincilia.canonical_movement m "
                "JOIN fincilia.source_record s "
                "  ON s.source_record_id = m.source_record_id "
                " AND s.company_id = m.company_id "
                "JOIN fincilia.raw_record r ON r.raw_record_id = s.raw_record_id "
                "JOIN fincilia.engine_release e "
                "  ON e.release_id = m.engine_release_id "
                "WHERE m.dataset_version_id = %s "
                "ORDER BY r.record_ordinal, m.movement_id",
                (descriptor.dataset_version_id,),
            )
            emitted = 0

            def counted_rows() -> Iterator[tuple[Any, ...]]:
                nonlocal emitted
                for row in cursor:
                    emitted += 1
                    yield row

            for chunk in csv_chunks(counted_rows()):
                yield chunk
            if emitted != descriptor.row_count:
                raise ExportError("dataset-export-truncated",
                                  "the export did not emit every canonical row")
