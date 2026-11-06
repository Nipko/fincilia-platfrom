"""Plantillas por banco para exportaciones CSV/XLSX colombianas. Solo biblioteca estandar.

ADR-039 §5: una plantilla reconoce las columnas de una exportacion conocida y
propone el mapeo para que una pyme no tenga que hacerlo a mano. Tres reglas:

1. **Las plantillas son hipotesis sinteticas.** Ningun banco publica la
   especificacion de columnas de sus exportaciones de movimientos, y antes de
   DRG-00 no se puede mirar un fichero real. Cada plantilla declara
   `calibration = 'synthetic_hypothesis'` y su fuente: la pagina publica que
   documenta que la exportacion existe, o `no_public_source`. Los nombres de
   columna son una hipotesis propia a calibrar con corpus autorizado.
2. **La deteccion es inequivoca o no es.** Solo se devuelve una plantilla si
   exactamente una encaja con todas sus cabeceras obligatorias y ninguna
   cabecera desconocida. Cualquier otra cosa devuelve `None` y se usa el mapeo
   manual de siempre. Adivinar entre dos bancos es elegir un convenio de signo
   por la persona.
3. **La propuesta usa el mapeo existente.** El resultado es un `ColumnMapping`
   y la `definition` que guarda la API; se valida con `validate_mapping` y se
   prueba con `apply` sobre las filas de muestra. Si un formato de fecha o de
   decimal admite dos lecturas distintas, no hay propuesta lista.
"""

from __future__ import annotations

import itertools
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Final, Iterable, Sequence

from .mapping import (CANONICAL_FIELDS, ColumnMapping, MappingError, apply,
                      validate_mapping)

CALIBRATION: Final[str] = "synthetic_hypothesis"
NO_PUBLIC_SOURCE: Final[str] = "no_public_source"
# Campos que una plantilla reconoce pero que el mapeo canonico aun no consume.
# Se informan aparte para que nadie los pierda ni los cuele como canonicos.
EXTRA_FIELDS: Final[tuple[str, ...]] = ("balance", "counterparty_id", "value_date",
                                        "branch")
MAX_HEADER_SCAN: Final[int] = 20
MAX_SAMPLE_ROWS: Final[int] = 200


def normalise_header(value: str) -> str:
    """Minusculas, sin tildes, sin espacios sobrantes ni puntuacion final."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    collapsed = " ".join(plain.replace(" ", " ").split()).lower()
    return collapsed.rstrip(".:").strip()


@dataclass(frozen=True)
class BankTemplate:
    """Firma de cabeceras de una exportacion y como se lee."""

    template_id: str
    bank: str
    product: str
    version: int
    # Campo (canonico o extra) -> cabeceras normalizadas aceptadas.
    columns: dict[str, tuple[str, ...]]
    required: tuple[str, ...]
    direction_mode: str
    date_formats: tuple[str, ...]
    decimal_formats: tuple[str, ...]
    thousands_separator: str
    currency: str
    source_url: str
    source_note: str
    calibration: str = CALIBRATION

    def as_dict(self) -> dict[str, Any]:
        return {"template_id": self.template_id, "bank": self.bank,
                "product": self.product, "version": self.version,
                "columns": {name: list(aliases) for name, aliases in self.columns.items()},
                "required": list(self.required), "direction_mode": self.direction_mode,
                "date_formats": list(self.date_formats),
                "decimal_formats": list(self.decimal_formats),
                "thousands_separator": self.thousands_separator,
                "currency": self.currency, "calibration": self.calibration,
                "source_url": self.source_url, "source_note": self.source_note}


# Las exportaciones XLSX entregan fechas como ISO (el lector convierte el serial)
# y numeros con punto; las CSV suelen venir en convenio colombiano. Por eso cada
# plantilla admite ambas lecturas y la muestra decide, o no hay propuesta.
_DATES = ("dmy", "iso")
_DECIMALS = ("comma", "dot")

TEMPLATES: Final[tuple[BankTemplate, ...]] = (
    BankTemplate(
        template_id="bancolombia-cuenta-movimientos", bank="Bancolombia",
        product="Sucursal Virtual Negocios - movimientos de cuenta", version=1,
        columns={"occurred_on": ("fecha",), "description": ("descripcion",),
                 "branch": ("sucursal",), "reference": ("documento", "dcto"),
                 "amount": ("valor",), "balance": ("saldo",)},
        required=("occurred_on", "description", "branch", "reference", "amount",
                  "balance"),
        direction_mode="signed_amount", date_formats=_DATES,
        decimal_formats=_DECIMALS, thousands_separator=".", currency="COP",
        source_url=("https://www.bancolombia.com/centro-de-ayuda/preguntas-frecuentes/"
                    "descargar-movimiento-de-cuenta-seccion-negocios"),
        source_note=("La pagina publica confirma la descarga de movimientos con "
                     "eleccion de formato; no publica nombres de columna. Las "
                     "cabeceras son hipotesis propias.")),
    BankTemplate(
        template_id="davivienda-empresas-movimientos", bank="Davivienda",
        product="Banca empresarial - movimientos", version=1,
        columns={"occurred_on": ("fecha de transaccion", "fecha transaccion"),
                 "description": ("descripcion de la transaccion",),
                 "reference": ("referencia 1",), "amount": ("valor total",),
                 "direction": ("naturaleza",), "counterparty_id": ("referencia 2",)},
        required=("occurred_on", "description", "reference", "amount", "direction"),
        direction_mode="explicit_direction", date_formats=_DATES,
        decimal_formats=_DECIMALS, thousands_separator=".", currency="COP",
        source_url=NO_PUBLIC_SOURCE,
        source_note=("No se encontro documentacion publica de columnas de la "
                     "exportacion de movimientos en Colombia.")),
    BankTemplate(
        template_id="bbva-colombia-net-cash-movimientos", bank="BBVA Colombia",
        product="BBVA Net Cash - consulta de movimientos", version=1,
        columns={"occurred_on": ("fecha operacion", "f. operacion"),
                 "value_date": ("fecha valor", "f. valor"),
                 "description": ("concepto",), "reference": ("referencia",),
                 "amount": ("importe",), "balance": ("saldo",)},
        required=("occurred_on", "value_date", "description", "amount"),
        direction_mode="signed_amount", date_formats=_DATES,
        decimal_formats=_DECIMALS, thousands_separator=".", currency="COP",
        source_url=NO_PUBLIC_SOURCE,
        source_note=("Sin especificacion publica para Colombia; la pareja fecha "
                     "operacion/fecha valor es el convenio generico de extractos "
                     "en espanol.")),
    BankTemplate(
        template_id="banco-de-bogota-empresas-movimientos", bank="Banco de Bogota",
        product="Banca Virtual Empresas - movimientos", version=1,
        columns={"occurred_on": ("fecha",), "description": ("transaccion",),
                 "branch": ("oficina",), "reference": ("documento",),
                 "debit": ("debitos",), "credit": ("creditos",),
                 "balance": ("saldo",)},
        required=("occurred_on", "description", "branch", "debit", "credit"),
        direction_mode="debit_credit_columns", date_formats=_DATES,
        decimal_formats=_DECIMALS, thousands_separator=".", currency="COP",
        source_url=NO_PUBLIC_SOURCE,
        source_note="No se encontro documentacion publica de la exportacion."),
    BankTemplate(
        template_id="nequi-negocios-movimientos", bank="Nequi Negocios",
        product="Nequi Negocios - movimientos", version=1,
        columns={"occurred_on": ("fecha del movimiento",),
                 "description": ("detalle",),
                 "direction": ("tipo de movimiento",), "amount": ("valor",),
                 "balance": ("saldo disponible",),
                 "counterparty_id": ("numero de celular",)},
        required=("occurred_on", "description", "direction", "amount"),
        direction_mode="explicit_direction", date_formats=_DATES,
        decimal_formats=_DECIMALS, thousands_separator=".", currency="COP",
        source_url=NO_PUBLIC_SOURCE,
        source_note=("La documentacion publica solo describe extractos PDF de la "
                     "cuenta personal.")),
)


@dataclass(frozen=True)
class TemplateMatch:
    template: BankTemplate
    header_row: int
    # Campo -> indice de columna (0-based) en la fila de cabecera.
    columns: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {"template_id": self.template.template_id,
                "header_row": self.header_row, "columns": dict(self.columns),
                "calibration": self.template.calibration}


@dataclass(frozen=True)
class TemplateProposal:
    """`ready` solo si el mapeo valida y la muestra entera aplica sin rechazos."""

    status: str
    match: TemplateMatch
    mapping: ColumnMapping | None
    definition: dict[str, Any] | None
    extra_columns: dict[str, int]
    findings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "match": self.match.as_dict(),
                "definition": self.definition, "extra_columns": dict(self.extra_columns),
                "findings": list(self.findings),
                "calibration": self.match.template.calibration,
                "source_url": self.match.template.source_url}


def _match_one(template: BankTemplate, headers: Sequence[str]) -> dict[str, int] | None:
    normalised = [normalise_header(item) for item in headers]
    present = [item for item in normalised if item]
    if len(present) != len(set(present)):
        # Una cabecera repetida hace ambiguo a que columna apunta el campo.
        return None
    alias_to_field: dict[str, str] = {}
    for name, aliases in template.columns.items():
        for alias in aliases:
            alias_to_field[alias] = name
    columns: dict[str, int] = {}
    for index, header in enumerate(normalised):
        if not header:
            continue
        name = alias_to_field.get(header)
        if name is None:
            # Una cabecera que la plantilla no conoce puede ser una version nueva
            # de la exportacion. No se ignora: se cae al mapeo manual.
            return None
        if name in columns:
            return None
        columns[name] = index
    if any(name not in columns for name in template.required):
        return None
    return columns


def detect_template(headers: Sequence[str], *,
                    templates: Iterable[BankTemplate] = TEMPLATES,
                    header_row: int = 1) -> TemplateMatch | None:
    """La unica plantilla que encaja con estas cabeceras, o `None`."""
    matches = []
    for template in templates:
        columns = _match_one(template, headers)
        if columns is not None:
            matches.append(TemplateMatch(template, header_row, columns))
    return matches[0] if len(matches) == 1 else None


def _values(row: Any) -> tuple[str, ...]:
    values = getattr(row, "values", row)
    return tuple("" if item is None else str(item) for item in values)


def find_header(rows: Sequence[Any], *,
                templates: Iterable[BankTemplate] = TEMPLATES,
                max_scan: int = MAX_HEADER_SCAN) -> TemplateMatch | None:
    """Busca la cabecera en las primeras filas (las exportaciones traen preambulo).

    `rows` son filas ya extraidas: tuplas de cadenas o registros con `values`
    (las filas de `extraction`, `spreadsheet` u `open_document`). Las filas se
    numeran desde 1, o con su `record_ordinal` si lo traen. Exige un unico par
    (fila, plantilla) en todo el tramo examinado.
    """
    catalogue = tuple(templates)
    found: list[TemplateMatch] = []
    for position, row in enumerate(rows[:max_scan], start=1):
        number = int(getattr(row, "record_ordinal", position))
        match = detect_template(_values(row), templates=catalogue, header_row=number)
        if match is not None:
            found.append(match)
        else:
            # Varias plantillas sobre la misma fila tambien es ambiguedad.
            if sum(_match_one(item, _values(row)) is not None for item in catalogue) > 1:
                return None
    return found[0] if len(found) == 1 else None


def propose_mapping(match: TemplateMatch, rows: Sequence[Any]) -> TemplateProposal:
    """Propone el mapeo de la plantilla y lo prueba sobre las filas de datos.

    `rows` son las filas **posteriores** a la cabecera en el orden del fichero.
    Se prueban todas las combinaciones de fecha y decimal que la plantilla
    admite; solo hay propuesta si las combinaciones viables leen exactamente los
    mismos movimientos. Si dos lecturas dan importes o fechas distintos, la
    eleccion es de una persona.
    """
    template = match.template
    canonical = {name: index for name, index in match.columns.items()
                 if name in CANONICAL_FIELDS}
    extra = {name: index for name, index in match.columns.items()
             if name not in CANONICAL_FIELDS}
    first_data_row = match.header_row + 1
    numbered: list[tuple[int, tuple[str, ...]]] = []
    for offset, row in enumerate(rows[:MAX_SAMPLE_ROWS]):
        number = int(getattr(row, "record_ordinal", first_data_row + offset))
        values = _values(row)
        if any(item.strip() for item in values):
            numbered.append((number, values))
    if not numbered:
        return TemplateProposal("needs_review", match, None, None, extra,
                                ("no_sample_rows",))

    viable: list[tuple[ColumnMapping, list[dict[str, Any]]]] = []
    findings: list[str] = []
    for date_format, decimal_format in itertools.product(template.date_formats,
                                                         template.decimal_formats):
        mapping = ColumnMapping(
            columns=dict(canonical), date_format=date_format,
            decimal_format=decimal_format, currency=template.currency,
            direction_mode=template.direction_mode, header_row=match.header_row,
            first_data_row=first_data_row)
        problems = validate_mapping(mapping)
        if problems:
            findings.extend(f"{item.code}:{item.location}" for item in problems)
            continue
        movements: list[dict[str, Any]] = []
        rejected = False
        for number, values in numbered:
            try:
                result = apply(mapping, [list(values)], first_row_number=number)
            except MappingError:
                rejected = True
                break
            if result.rejections:
                rejected = True
                break
            movements.extend(item.as_dict() for item in result.movements)
        if not rejected:
            viable.append((mapping, movements))

    if not viable:
        return TemplateProposal("needs_review", match, None, None, extra,
                                tuple(sorted(set(findings))) or ("sample_not_mappable",))
    reference = [_comparable(item) for item in viable[0][1]]
    if any([_comparable(item) for item in other[1]] != reference for other in viable[1:]):
        return TemplateProposal("needs_review", match, None, None, extra,
                                ("ambiguous_locale",))
    chosen = viable[0][0]
    definition = {
        "columns": dict(chosen.columns), "date_format": chosen.date_format,
        "decimal_format": chosen.decimal_format, "currency": chosen.currency,
        "direction_mode": chosen.direction_mode, "header_row": chosen.header_row,
        "first_data_row": chosen.first_data_row,
        # Las columnas que la plantilla reconoce sin consumirlas (saldo,
        # sucursal...) quedan declaradas como vistas e ignoradas, con el mismo
        # campo que usa la API para distinguirlas de una columna olvidada.
        "ignored_columns": sorted(extra.values()),
        "template": {"template_id": template.template_id, "version": template.version,
                     "calibration": template.calibration},
    }
    return TemplateProposal("ready", match, chosen, definition, extra)


def _comparable(movement: dict[str, Any]) -> tuple:
    # `source_column` no cambia entre lecturas; lo que importa es lo leido.
    return (movement["row_number"], movement["occurred_on"], movement["amount"],
            movement["direction"], movement["description"], movement["reference"])
