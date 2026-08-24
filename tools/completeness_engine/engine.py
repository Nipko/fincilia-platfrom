"""Motor ejecutable de completitud y conciliacion de saldos (FNC-DOM-006).

Esto **no** es la implementacion de producto. Es una especificacion ejecutable de
`docs/domain/completeness-balances.json`: convierte sus reglas en funciones puras
para que las invariantes contractuales se puedan probar antes de Sprint 1, y para
que la implementacion de producto tenga contra que contrastarse despues.

Lo que aqui se decide, se decide como lo dice el contrato:

- el dinero es `Decimal` exacto; un `float` se rechaza, no se convierte;
- la precedencia de estado es mismatch > unknown > verified, y un control
  requerido que no se pudo evaluar produce `unknown`, jamas se salta en silencio;
- `balanced` exige cero exacto, no un cero redondeado;
- solo los items `confirmed` cuentan en un statement;
- una excepcion aceptada **no** cambia el estado base ni habilita auto-match.

Funciones puras. Sin red, reloj de pared, entorno, Git ni aleatoriedad. Las fechas
entran como dato; el motor nunca pregunta que hora es.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

# `numeric(38, 12)` en el modelo canonico.
MONEY_SCALE = 12
MONEY_QUANTUM = Decimal(1).scaleb(-MONEY_SCALE)
ZERO = Decimal(0).quantize(MONEY_QUANTUM)

ASSESSMENT_STATES = ("verified", "mismatch", "unknown", "accepted_exception")
CONTROL_OUTCOMES = ("match", "mismatch", "unknown", "not_applicable")
STATEMENT_STATES = ("draft", "review_required", "balanced", "exception_accepted",
                    "superseded")
RECONCILING_ITEM_STATES = ("proposed", "confirmed", "rejected", "reversed")
ADJUSTMENT_SIDES = ("add_to_bank", "deduct_from_bank")
EXCEPTION_BASE_STATES = ("mismatch", "unknown")

CLOSE_CONDITIONS = (
    "every_expected_source_has_assessment",
    "no_unhandled_mismatch_or_unknown",
    "statement_for_every_required_account_and_currency",
    "every_statement_balanced_or_explicit_exception_accepted",
    "no_hidden_unexplained_difference",
    "confirmed_items_have_evidence_and_sod",
    "all_published_fields_and_decisions_have_lineage",
    "engine_schema_reference_and_rule_versions_fixed",
    "authorization_revalidated_before_snapshot",
)


class MoneyError(ValueError):
    """Un importe no se puede interpretar como dinero exacto."""


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Dinero
# --------------------------------------------------------------------------- #

def parse_money(value: Any, location: str = "amount") -> Decimal:
    """Convierte a `Decimal` exacto. Un `float` se **rechaza**, no se redondea.

    Aceptar un float aqui seria aceptar que 0.1 + 0.2 no es 0.3 y que un cierre
    pueda cuadrar por suerte. El contrato dice `money_decimal`; esto lo cumple.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise MoneyError(f"{location}: money must not be a float; got {value!r}")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, int):
        candidate = Decimal(value)
    elif isinstance(value, str):
        try:
            candidate = Decimal(value.strip())
        except InvalidOperation as error:
            raise MoneyError(f"{location}: {value!r} is not an exact decimal") from error
    else:
        raise MoneyError(f"{location}: unsupported money type {type(value).__name__}")
    if not candidate.is_finite():
        raise MoneyError(f"{location}: money must be finite; got {value!r}")
    if -candidate.as_tuple().exponent > MONEY_SCALE:
        raise MoneyError(
            f"{location}: money carries more than {MONEY_SCALE} decimal places")
    return candidate.quantize(MONEY_QUANTUM)


def is_exact_zero(value: Decimal) -> bool:
    """Cero exacto. `balanced` no admite un cero conseguido por redondeo."""
    return value == ZERO


def format_money(value: Decimal) -> str:
    """Forma canonica en punto fijo, nunca notacion cientifica.

    `str(Decimal(0).quantize(...))` produce `0E-12`: numericamente correcto e
    ilegible, y suficiente para que dos representaciones del mismo importe dejen de
    compararse byte a byte. El contrato serializa dinero como cadena; esta es la
    unica cadena que vale.
    """
    return f"{value:.{MONEY_SCALE}f}"


# --------------------------------------------------------------------------- #
# Derivacion del estado de completitud
# --------------------------------------------------------------------------- #

@dataclass
class AssessmentOutcome:
    state: str
    reasons: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    evaluated_controls: int = 0
    required_controls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reasons": sorted(self.reasons),
            "findings": [item.as_dict() for item in sorted(self.findings)],
            "evaluated_controls": self.evaluated_controls,
            "required_controls": self.required_controls,
        }


def derive_assessment_state(controls: list[dict[str, Any]],
                            expectation: dict[str, Any] | None = None
                            ) -> AssessmentOutcome:
    """Precedencia del contrato: mismatch > unknown > verified.

    Un control requerido que no aparece en los resultados **no se ignora**: cuenta
    como `unknown`. Saltarlo en silencio convertiria una evaluacion incompleta en
    un `verified` que nadie observo.

    `not_applicable` solo vale si una expectativa versionada lo predeclara con
    motivo. Si no, es `unknown`: declarar algo inaplicable sobre la marcha es la
    forma mas barata de hacer desaparecer un control incomodo.
    """
    expectation = expectation or {}
    outcome = AssessmentOutcome(state="unknown")
    findings: list[Finding] = []
    reasons: list[str] = []

    predeclared = {
        str(item.get("control_type")): item
        for item in expectation.get("not_applicable_controls", []) or []
    }
    expected_required = {str(item) for item in
                         expectation.get("required_control_types", []) or []}

    seen: set[str] = set()
    mismatch = False
    unknown = False

    for index, control in enumerate(controls):
        location = f"controls[{index}]"
        control_type = str(control.get("control_type", ""))
        if not control_type:
            findings.append(Finding("CMP-CONTROL-TYPE", location,
                                    "a control result must name its control type"))
            unknown = True
            continue
        seen.add(control_type)
        outcome_value = str(control.get("outcome", ""))
        if outcome_value not in CONTROL_OUTCOMES:
            findings.append(Finding("CMP-CONTROL-OUTCOME", location,
                                    f"unknown outcome {outcome_value!r}"))
            unknown = True
            continue
        required = bool(control.get("required", False))

        if outcome_value == "not_applicable":
            declaration = predeclared.get(control_type)
            if declaration is None or not declaration.get("reason") \
                    or not declaration.get("expectation_version"):
                findings.append(Finding(
                    "CMP-NOT-APPLICABLE", location,
                    f"{control_type} is reported not_applicable without a versioned "
                    "expectation declaring it, with a reason"))
                if required:
                    unknown = True
                    reasons.append(f"{control_type}:not_applicable_without_declaration")
            continue

        if not required:
            continue
        outcome.required_controls += 1
        outcome.evaluated_controls += 1
        if outcome_value == "mismatch":
            mismatch = True
            reasons.append(f"{control_type}:mismatch")
        elif outcome_value == "unknown":
            unknown = True
            reasons.append(f"{control_type}:unknown")

    for missing in sorted(expected_required - seen):
        if missing in predeclared:
            declaration = predeclared[missing]
            if declaration.get("reason") and declaration.get("expectation_version"):
                continue
        outcome.required_controls += 1
        unknown = True
        reasons.append(f"{missing}:absent")
        findings.append(Finding(
            "CMP-CONTROL-MISSING", f"required_control_types[{missing}]",
            f"{missing} is required by the expectation and no result reports it; an "
            "unevaluated control is unknown, never a silent pass"))

    if mismatch:
        outcome.state = "mismatch"
    elif unknown:
        outcome.state = "unknown"
    else:
        outcome.state = "verified"
    outcome.reasons = reasons
    outcome.findings = findings
    return outcome


# --------------------------------------------------------------------------- #
# Excepciones aceptadas
# --------------------------------------------------------------------------- #

def validate_accepted_exception(exception: dict[str, Any], base_state: str,
                                as_of: date) -> list[Finding]:
    """Una excepcion no cambia el estado base, y expira.

    `as_of` entra como dato: el motor no consulta el reloj, para que dos maquinas
    obtengan el mismo veredicto sobre el mismo periodo.
    """
    findings: list[Finding] = []
    location = f"exception[{exception.get('scope', '?')}]"

    if base_state not in EXCEPTION_BASE_STATES:
        findings.append(Finding(
            "EXC-BASE-STATE", location,
            f"an exception only applies over {list(EXCEPTION_BASE_STATES)}; base state "
            f"is {base_state!r}"))

    for required in ("scope", "reason", "owner_subject_id", "approved_by", "approved_at",
                     "materiality_policy_id", "valid_from", "expires_at",
                     "allowed_actions", "evidence_refs", "audit_event_id"):
        if not exception.get(required):
            findings.append(Finding("EXC-REQUIRED-FIELD", f"{location}.{required}",
                                    f"an accepted exception needs {required}"))

    owner = exception.get("owner_subject_id")
    approver = exception.get("approved_by")
    if owner and approver and owner == approver:
        findings.append(Finding(
            "EXC-INDEPENDENT-APPROVER", f"{location}.approved_by",
            "the owner of an exception cannot approve it; that is the whole point of an "
            "independent approver"))

    expires = exception.get("expires_at")
    if expires:
        try:
            expiry = date.fromisoformat(str(expires))
        except ValueError:
            findings.append(Finding("EXC-EXPIRY", f"{location}.expires_at",
                                    f"{expires!r} is not an ISO date"))
        else:
            if expiry <= as_of:
                findings.append(Finding(
                    "EXC-EXPIRED", f"{location}.expires_at",
                    f"the exception expired on {expiry.isoformat()}; an expired "
                    "exception never authorises a new close"))

    actions = {str(item) for item in exception.get("allowed_actions", []) or []}
    if "auto_match" in actions:
        findings.append(Finding(
            "EXC-AUTO-MATCH", f"{location}.allowed_actions",
            "an accepted exception never enables auto-match"))
    if exception.get("changes_base_state"):
        findings.append(Finding(
            "EXC-BASE-STATE", f"{location}.changes_base_state",
            "the base state is preserved; an exception discloses a problem, it does not "
            "erase it"))
    if not exception.get("disclosed_in_snapshot", False):
        findings.append(Finding(
            "EXC-DISCLOSURE", f"{location}.disclosed_in_snapshot",
            "an accepted exception must be disclosed in the snapshot and the report"))
    return sorted(set(findings))


# --------------------------------------------------------------------------- #
# Conciliacion de saldos
# --------------------------------------------------------------------------- #

@dataclass
class StatementOutcome:
    state: str
    adjusted_bank_balance: Decimal
    unexplained_difference: Decimal
    confirmed_additions_to_bank: Decimal
    confirmed_deductions_from_bank: Decimal
    counted_item_ids: list[str] = field(default_factory=list)
    ignored_item_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "adjusted_bank_balance": format_money(self.adjusted_bank_balance),
            "unexplained_difference": format_money(self.unexplained_difference),
            "confirmed_additions_to_bank": format_money(self.confirmed_additions_to_bank),
            "confirmed_deductions_from_bank": format_money(
                self.confirmed_deductions_from_bank),
            "counted_item_ids": sorted(self.counted_item_ids),
            "ignored_item_ids": sorted(self.ignored_item_ids),
            "findings": [item.as_dict() for item in sorted(self.findings)],
        }


def validate_reconciling_item(item: dict[str, Any], statement: dict[str, Any],
                              location: str) -> list[Finding]:
    findings: list[Finding] = []
    if str(item.get("company_id", "")) != str(statement.get("company_id", "")):
        findings.append(Finding(
            "BAL-COMPANY-SCOPE", location,
            "a reconciling item from another company never enters this statement"))
    if str(item.get("statement_id", "")) != str(statement.get("statement_id", "")):
        findings.append(Finding("BAL-STATEMENT-SCOPE", location,
                                "the item belongs to another statement"))
    if str(item.get("currency_code", "")) != str(statement.get("currency_code", "")):
        findings.append(Finding(
            "BAL-CURRENCY", location,
            "a statement is single-currency; mixing currencies would add numbers that "
            "are not comparable"))
    side = str(item.get("adjustment_side", ""))
    if side not in ADJUSTMENT_SIDES:
        findings.append(Finding("BAL-ADJUSTMENT-SIDE", location,
                                f"unknown adjustment side {side!r}"))
    state = str(item.get("state", ""))
    if state not in RECONCILING_ITEM_STATES:
        findings.append(Finding("BAL-ITEM-STATE", location,
                                f"unknown reconciling item state {state!r}"))
    try:
        amount = parse_money(item.get("amount"), location)
    except MoneyError as error:
        findings.append(Finding("BAL-MONEY", location, str(error)))
    else:
        if amount <= ZERO:
            findings.append(Finding(
                "BAL-AMOUNT-POSITIVE", location,
                "a reconciling item amount is positive; the side carries the direction"))
    if state == "confirmed":
        for required in ("approved_by", "approved_at", "sod_check", "evidence_refs"):
            if not item.get(required):
                findings.append(Finding(
                    "BAL-CONFIRMED-EVIDENCE", f"{location}.{required}",
                    f"a confirmed item needs {required}"))
        if item.get("prepared_by") and item.get("approved_by") \
                and item["prepared_by"] == item["approved_by"]:
            findings.append(Finding(
                "BAL-SOD", f"{location}.approved_by",
                "whoever prepared a reconciling item cannot approve it"))
    return findings


def compute_statement(statement: dict[str, Any],
                      items: list[dict[str, Any]]) -> StatementOutcome:
    """Formula del contrato, con `Decimal` exacto y solo items `confirmed`.

        adjusted_bank = bank_closing + confirmed_additions - confirmed_deductions
        unexplained   = adjusted_bank - books_closing

    `balanced` exige `unexplained == 0` exacto. Un cero por redondeo no es cuadre:
    es una diferencia que nadie vio.
    """
    findings: list[Finding] = []
    try:
        bank_closing = parse_money(statement.get("bank_closing_balance"),
                                   "bank_closing_balance")
        books_closing = parse_money(statement.get("books_closing_balance"),
                                    "books_closing_balance")
    except MoneyError as error:
        findings.append(Finding("BAL-MONEY", "statement", str(error)))
        return StatementOutcome("review_required", ZERO, ZERO, ZERO, ZERO,
                                findings=findings)

    additions = ZERO
    deductions = ZERO
    counted: list[str] = []
    ignored: list[str] = []

    for index, item in enumerate(items):
        location = f"items[{item.get('item_id', index)}]"
        item_findings = validate_reconciling_item(item, statement, location)
        findings.extend(item_findings)
        identifier = str(item.get("item_id", index))
        # Solo `confirmed` cuenta, y solo si el item es valido: un item propuesto o
        # rechazado que sumara convertiria una hipotesis en un ajuste contable.
        if str(item.get("state")) != "confirmed" or item_findings:
            ignored.append(identifier)
            continue
        amount = parse_money(item.get("amount"), location)
        if str(item.get("adjustment_side")) == "add_to_bank":
            additions += amount
        else:
            deductions += amount
        counted.append(identifier)

    adjusted = (bank_closing + additions - deductions).quantize(MONEY_QUANTUM)
    unexplained = (adjusted - books_closing).quantize(MONEY_QUANTUM)

    if findings:
        state = "review_required"
    elif is_exact_zero(unexplained):
        state = "balanced"
    else:
        state = "review_required"
    return StatementOutcome(state, adjusted, unexplained, additions, deductions,
                            counted, ignored, findings)


def apply_statement_exception(outcome: StatementOutcome, exception: dict[str, Any] | None,
                              as_of: date) -> StatementOutcome:
    """Una diferencia sin explicar solo se cierra con excepcion aceptada valida."""
    if is_exact_zero(outcome.unexplained_difference) and not outcome.findings:
        return outcome
    if exception is None:
        outcome.findings.append(Finding(
            "BAL-UNEXPLAINED", "statement",
            f"unexplained difference {format_money(outcome.unexplained_difference)} without an "
            "accepted exception; a statement is never labelled balanced with a difference"))
        outcome.state = "review_required"
        return outcome
    problems = validate_accepted_exception(exception, "mismatch", as_of)
    if problems:
        outcome.findings.extend(problems)
        outcome.state = "review_required"
        return outcome
    outcome.state = "exception_accepted"
    return outcome


# --------------------------------------------------------------------------- #
# Compuerta de cierre
# --------------------------------------------------------------------------- #

@dataclass
class CloseOutcome:
    ready: bool
    state: str
    unmet_conditions: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "state": self.state,
            "unmet_conditions": sorted(self.unmet_conditions),
            "findings": [item.as_dict() for item in sorted(self.findings)],
        }


def evaluate_close_readiness(period: dict[str, Any], as_of: date) -> CloseOutcome:
    """Las nueve condiciones del contrato, de forma conjuntiva y fail-closed.

    Cobertura de matching **no** es completitud, y un movimiento emparejado no es
    una conciliacion de saldos: son preguntas distintas y confundirlas produce un
    cierre que parece completo sobre datos que nadie verifico.
    """
    unmet: list[str] = []
    findings: list[Finding] = []

    expected_sources = {str(item) for item in period.get("expected_source_ids", []) or []}
    assessed = {str(item.get("data_source_id")) for item in
                period.get("assessments", []) or []}
    if expected_sources - assessed:
        unmet.append("every_expected_source_has_assessment")
        findings.append(Finding(
            "CLOSE-SOURCE-COVERAGE", "expected_source_ids",
            f"no assessment for {sorted(expected_sources - assessed)}"))

    exceptions = {str(item.get("scope")): item
                  for item in period.get("accepted_exceptions", []) or []}
    for index, assessment in enumerate(period.get("assessments", []) or []):
        state = str(assessment.get("state"))
        scope = str(assessment.get("data_source_id"))
        if state in ("mismatch", "unknown"):
            exception = exceptions.get(scope)
            if exception is None:
                unmet.append("no_unhandled_mismatch_or_unknown")
                findings.append(Finding(
                    "CLOSE-UNHANDLED", f"assessments[{index}]",
                    f"{scope} is {state} and no accepted exception covers it"))
            else:
                problems = validate_accepted_exception(exception, state, as_of)
                if problems:
                    unmet.append("no_unhandled_mismatch_or_unknown")
                    findings.extend(problems)

    required_accounts = {(str(item.get("financial_account_id")),
                          str(item.get("currency_code")))
                         for item in period.get("required_accounts", []) or []}
    statements = period.get("statements", []) or []
    present = {(str(item.get("financial_account_id")), str(item.get("currency_code")))
               for item in statements}
    if required_accounts - present:
        unmet.append("statement_for_every_required_account_and_currency")
        findings.append(Finding(
            "CLOSE-STATEMENT-COVERAGE", "required_accounts",
            f"no statement for {sorted(required_accounts - present)}"))

    for index, statement in enumerate(statements):
        state = str(statement.get("state"))
        if state not in ("balanced", "exception_accepted"):
            unmet.append("every_statement_balanced_or_explicit_exception_accepted")
            findings.append(Finding("CLOSE-STATEMENT-STATE", f"statements[{index}]",
                                    f"statement state is {state!r}"))
        difference = statement.get("unexplained_difference", "0")
        try:
            value = parse_money(difference, f"statements[{index}]")
        except MoneyError as error:
            unmet.append("no_hidden_unexplained_difference")
            findings.append(Finding("CLOSE-MONEY", f"statements[{index}]", str(error)))
            continue
        if not is_exact_zero(value) and state != "exception_accepted":
            unmet.append("no_hidden_unexplained_difference")
            findings.append(Finding(
                "CLOSE-HIDDEN-DIFFERENCE", f"statements[{index}]",
                f"unexplained difference {format_money(value)} outside an accepted exception"))
        if state == "balanced" and not is_exact_zero(value):
            unmet.append("every_statement_balanced_or_explicit_exception_accepted")
            findings.append(Finding(
                "CLOSE-BALANCED-LABEL", f"statements[{index}]",
                "a statement labelled balanced must have an exact zero difference"))

    for index, item in enumerate(period.get("confirmed_items", []) or []):
        if not item.get("evidence_refs") or not item.get("sod_check"):
            unmet.append("confirmed_items_have_evidence_and_sod")
            findings.append(Finding("CLOSE-ITEM-EVIDENCE", f"confirmed_items[{index}]",
                                    "a confirmed item needs evidence and a SoD check"))

    for index, published in enumerate(period.get("published_fields", []) or []):
        if not published.get("lineage_ref"):
            unmet.append("all_published_fields_and_decisions_have_lineage")
            findings.append(Finding("CLOSE-LINEAGE", f"published_fields[{index}]",
                                    "a published field must carry lineage to evidence"))

    versions = period.get("fixed_versions", {}) or {}
    for key in ("engine_release_id", "canonical_schema_version", "rule_version"):
        value = str(versions.get(key, "")).strip().lower()
        if not value or value in ("latest", "main", "head", "stable", "current"):
            unmet.append("engine_schema_reference_and_rule_versions_fixed")
            findings.append(Finding(
                "CLOSE-VERSION", f"fixed_versions.{key}",
                f"{key} must be fixed to an exact version; got {versions.get(key)!r}"))

    if not period.get("authorization_revalidated_before_snapshot", False):
        unmet.append("authorization_revalidated_before_snapshot")
        findings.append(Finding(
            "CLOSE-AUTHORIZATION", "authorization_revalidated_before_snapshot",
            "authorization is revalidated server-side before the snapshot"))

    # Cobertura de matching no es completitud: si alguien la ofrece como prueba,
    # se dice explicitamente que no lo es.
    if period.get("matching_coverage_offered_as_completeness"):
        unmet.append("no_unhandled_mismatch_or_unknown")
        findings.append(Finding(
            "CLOSE-MATCHING-NOT-COMPLETENESS", "matching_coverage",
            "match coverage answers a different question than completeness; it never "
            "substitutes an assessment"))

    ordered = sorted(set(unmet))
    if ordered:
        return CloseOutcome(False, "not_ready", ordered, sorted(set(findings)))
    disclosed = any(True for _ in period.get("accepted_exceptions", []) or [])
    state = "closed_with_disclosed_exception" if disclosed else "ready"
    return CloseOutcome(True, state, [], [])
