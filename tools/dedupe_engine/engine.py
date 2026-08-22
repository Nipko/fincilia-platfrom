"""Motor ejecutable de identidad, idempotencia y dedupe (FNC-DOM-007).

Especificacion ejecutable de `docs/domain/idempotency-dedupe.json`. **No** es la
implementacion de producto: vive en `tools/` porque `product_code_allowed` sigue en
`false` hasta S1-READY.

La idea que ordena todo el modulo es que **identidad e igualdad no son lo mismo**, y
que confundirlas borra dinero:

- que dos bytes sean identicos prueba que es la misma entrega, no que sea el mismo
  hecho economico;
- que dos movimientos se parezcan muchisimo no prueba que sean el mismo movimiento:
  una empresa puede pagar dos veces el mismo importe el mismo dia al mismo
  proveedor, y ambas veces son reales;
- por eso fecha, monto, direccion y referencia **nunca** forman unicidad dura. Solo
  generan un candidato que un humano revisa.

Funciones puras. Sin red, reloj de pared, entorno, Git ni aleatoriedad.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import unicodedata
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

SHA256_HEX = 64

# Campos de negocio que NUNCA pueden formar una unicidad dura, por si solos o
# combinados. El contrato lo llama `NO-BUSINESS-COMPOSITE`.
FORBIDDEN_HARD_UNIQUE_FIELDS = frozenset({
    "posting_date", "occurrence_date", "value_date", "accounting_date",
    "amount", "direction", "reference", "counterparty", "description",
})
# Campos que identifican una cosa. `company_id`, `data_source_id` y
# `connection_id` NO estan aqui: son alcances, no identidades. Una unicidad dura
# sobre (company_id, currency) no identifica nada; solo agrupa.
IDENTITY_FIELDS = frozenset({
    "content_sha256", "provider_event_id", "artifact_version_id", "id",
})
SCOPE_FIELDS = frozenset({"company_id", "data_source_id", "connection_id"})

CANDIDATE_STATES = ("open", "confirmed_same_event", "confirmed_distinct", "dismissed",
                    "superseded")
INBOX_STATES = ("received", "processing", "succeeded", "retryable_failed",
                "terminal_failed", "conflict")
INBOX_TERMINAL = ("succeeded", "terminal_failed", "conflict")
# Un unico dueno del reintento. El contrato lo fija en el workflow durable.
RETRY_OWNER = "platform_durable_workflow"
NON_OWNERS = ("adapter", "circuit_breaker", "broker_redelivery", "client_library")


class IdentityError(ValueError):
    """La identidad no puede resolverse con seguridad."""


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Resolution:
    """Que hacer con algo que ya podria existir."""
    action: str
    reason: str
    findings: list[Finding] = field(default_factory=list)
    security_signal: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "security_signal": self.security_signal,
            "findings": [item.as_dict() for item in sorted(self.findings)],
        }


# --------------------------------------------------------------------------- #
# Normalizacion
# --------------------------------------------------------------------------- #

def normalise_text(value: Any, locale_version: str) -> str:
    """Normalizacion versionada y explicita.

    Sin version, dos maquinas con reglas distintas producirian huellas distintas
    del mismo dato y el bloqueo de candidatos dejaria de ser reproducible.
    """
    if not locale_version:
        raise IdentityError("normalisation requires an explicit locale version")
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return " ".join(text.split())


def canonical_features(features: dict[str, Any], locale_version: str) -> str:
    """Serializacion canonica y ordenada de los rasgos de un candidato."""
    prepared: dict[str, str] = {}
    for key in sorted(features):
        value = features[key]
        if isinstance(value, Decimal):
            prepared[key] = format(value, "f")
        elif isinstance(value, float):
            raise IdentityError(f"{key}: a float never enters a fingerprint")
        else:
            prepared[key] = normalise_text(value, locale_version)
    return json.dumps(prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Identidad dura
# --------------------------------------------------------------------------- #

def artifact_identity(company_id: str, data_source_id: str, content_sha256: str) -> str:
    """Identidad de un artefacto: compania, fuente y hash exacto de bytes.

    El hash es del contenido **antes** de cualquier transformacion. Si se calculara
    despues, dos normalizaciones distintas del mismo fichero darian dos artefactos.
    """
    if not company_id or not data_source_id:
        raise IdentityError("artifact identity is company and source scoped")
    digest = str(content_sha256).strip().lower()
    if len(digest) != SHA256_HEX or any(c not in "0123456789abcdef" for c in digest):
        raise IdentityError(f"content_sha256 is not a sha256 digest: {content_sha256!r}")
    return f"{company_id}|{data_source_id}|{digest}"


def resolve_artifact(existing: dict[str, Any] | None,
                     incoming: dict[str, Any]) -> Resolution:
    """Reentrega exacta contra colision de clave.

    Misma clave y mismo payload es una reentrega: se devuelve lo que ya hay, sin
    crear nada. Misma clave y **otro** payload no es idempotencia: es una colision
    que hay que tratar como senal de seguridad, no resolver adivinando.
    """
    key = artifact_identity(incoming["company_id"], incoming["data_source_id"],
                            incoming["content_sha256"])
    if existing is None:
        return Resolution("create_new_artifact_version", f"no artifact for {key}")
    existing_key = artifact_identity(existing["company_id"], existing["data_source_id"],
                                     existing["content_sha256"])
    if existing_key != key:
        return Resolution("create_new_artifact_version",
                          "the existing artifact has a different identity")
    if existing.get("raw_bytes_digest") != incoming.get("raw_bytes_digest"):
        return Resolution(
            "conflict", "same identity with different raw bytes",
            [Finding("IDM-IDENTITY-COLLISION", key,
                     "the same artifact identity arrived with different bytes; this is a "
                     "security signal, not something to resolve by guessing")],
            security_signal=True)
    return Resolution("return_existing_artifact_version",
                      "exact redelivery of bytes already stored")


def provider_event_identity(connection_id: str, provider_event_id: str) -> str:
    """Un id de proveedor solo identifica **dentro de su conexion**.

    Dos proveedores pueden reutilizar el mismo identificador, y un mismo proveedor
    puede reciclarlos entre entornos. Tratarlo como global mezclaria hechos de
    clientes distintos.
    """
    if not connection_id:
        raise IdentityError("a provider event id is meaningless without its connection")
    if not provider_event_id:
        raise IdentityError("provider_event_id is required")
    return f"{connection_id}|{provider_event_id}"


def resolve_provider_event(existing: dict[str, Any] | None,
                           incoming: dict[str, Any]) -> Resolution:
    key = provider_event_identity(incoming["connection_id"], incoming["provider_event_id"])
    if existing is None:
        return Resolution("accept_new_delivery", f"no delivery for {key}")
    if provider_event_identity(existing["connection_id"],
                              existing["provider_event_id"]) != key:
        return Resolution("accept_new_delivery", "different connection scope")
    if existing.get("payload_digest") != incoming.get("payload_digest"):
        return Resolution(
            "conflict", "same provider event id with a different payload",
            [Finding("IDM-PROVIDER-COLLISION", key,
                     "the provider reused a record id with different content; the id is "
                     "not proof of sameness")],
            security_signal=True)
    return Resolution("return_existing_receipt", "exact redelivery")


# --------------------------------------------------------------------------- #
# Unicidad dura prohibida
# --------------------------------------------------------------------------- #

def validate_hard_uniqueness(fields: list[str], location: str = "unique_constraint"
                             ) -> list[Finding]:
    """Rechaza una unicidad dura construida sobre rasgos de negocio.

    Una restriccion sobre fecha, monto, direccion y referencia haria imposible
    registrar dos pagos legitimos identicos el mismo dia. El sistema no perderia
    un duplicado: perderia un movimiento real.
    """
    findings: list[Finding] = []
    named = [str(item) for item in fields]
    business = sorted(set(named) & FORBIDDEN_HARD_UNIQUE_FIELDS)
    if business:
        findings.append(Finding(
            "IDM-BUSINESS-COMPOSITE", location,
            f"{business} are business features; a hard unique constraint over them would "
            "reject a second legitimate identical transaction"))
    if not set(named) & IDENTITY_FIELDS:
        findings.append(Finding(
            "IDM-NO-IDENTITY", location,
            "a hard unique constraint must rest on at least one stable identity field"))
    if "company_id" not in named:
        findings.append(Finding(
            "IDM-COMPANY-SCOPE", location,
            "a hard unique constraint that is not company scoped can collide across "
            "companies"))
    return sorted(set(findings))


# --------------------------------------------------------------------------- #
# Huella de candidato
# --------------------------------------------------------------------------- #

def candidate_fingerprint(features: dict[str, Any], *, secret: bytes,
                          secret_version: str, locale_version: str,
                          rule_version: str) -> str:
    """HMAC versionado sobre rasgos normalizados.

    Es un HMAC y no un hash porque un hash de rasgos de negocio es reversible por
    fuerza bruta: el espacio de fechas e importes plausibles es minusculo. Y va
    versionado porque rotar la clave o cambiar la normalizacion **debe** producir
    otra huella; si no, un cambio de reglas pasaria inadvertido.

    Una huella nunca es una anonimizacion y nunca es una restriccion de unicidad:
    solo sirve para bloquear y ordenar candidatos.
    """
    if not secret:
        raise IdentityError("a candidate fingerprint needs a key; a bare hash of business "
                            "features is brute-forceable")
    for version, name in ((secret_version, "secret_version"),
                          (locale_version, "locale_version"),
                          (rule_version, "rule_version")):
        if not version:
            raise IdentityError(f"{name} is required; an unversioned fingerprint cannot "
                                "be reproduced after a rotation")
    payload = "|".join([secret_version, locale_version, rule_version,
                        canonical_features(features, locale_version)])
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def fingerprint_usage_findings(usage: str, location: str) -> list[Finding]:
    if usage != "blocking_and_ranking_only":
        return [Finding(
            "IDM-FINGERPRINT-USAGE", location,
            f"fingerprint usage {usage!r}: a fingerprint blocks and ranks candidates; it "
            "never decides identity and never becomes a unique constraint")]
    return []


# --------------------------------------------------------------------------- #
# Candidatos de dedupe
# --------------------------------------------------------------------------- #

@dataclass
class CandidateOutcome:
    raised: bool
    reason: str
    automatic_effect: str = "none"
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "raised": self.raised,
            "reason": self.reason,
            "automatic_effect": self.automatic_effect,
            "findings": [item.as_dict() for item in sorted(self.findings)],
        }


def evaluate_candidate(left: dict[str, Any], right: dict[str, Any],
                       rule: dict[str, Any]) -> CandidateOutcome:
    """Levanta un candidato; **jamas** decide ni fusiona.

    Cross-company nunca produce candidato: comparar movimientos de dos companias
    seria filtrar informacion de una a la otra por el mero hecho de mirarlas juntas.
    """
    findings: list[Finding] = []
    findings.extend(fingerprint_usage_findings(
        str(rule.get("fingerprint_usage", "")), f"rule[{rule.get('id')}]"))

    if left.get("company_id") != right.get("company_id"):
        findings.append(Finding(
            "IDM-COMPANY-SCOPE", f"rule[{rule.get('id')}]",
            "a dedupe candidate never crosses companies; comparing them would leak one "
            "company's data into another's review queue"))
        return CandidateOutcome(False, "cross-company pair refused", "none", findings)

    if left.get("movement_id") == right.get("movement_id"):
        return CandidateOutcome(False, "same movement compared with itself", "none",
                                findings)

    features = [str(item) for item in rule.get("features", []) or []]
    if not features:
        findings.append(Finding("IDM-RULE-FEATURES", f"rule[{rule.get('id')}]",
                                "a candidate rule declares the features it compares"))
        return CandidateOutcome(False, "rule declares no feature", "none", findings)

    differing = [key for key in features
                 if str(left.get(key, "")) != str(right.get(key, ""))]
    if differing:
        return CandidateOutcome(False, f"features differ: {sorted(differing)}", "none",
                                findings)
    return CandidateOutcome(
        True,
        "every declared feature matches; both observations are preserved until a human "
        "reviews them",
        "none", findings)


def order_pair(left_id: str, right_id: str) -> tuple[str, str]:
    """`lower_uuid_then_higher_uuid`: el par no depende del orden de llegada."""
    return (left_id, right_id) if left_id <= right_id else (right_id, left_id)


# --------------------------------------------------------------------------- #
# Decisiones de dedupe
# --------------------------------------------------------------------------- #

REQUIRED_DECISION_FIELDS = (
    "company_id", "candidate_id", "left_movement_id", "right_movement_id", "decision",
    "reason_code", "evidence_refs", "decided_by", "decided_at", "rule_version",
    "engine_release_id", "audit_event_id",
)


def validate_decision(decision: dict[str, Any],
                      prior: dict[str, Any] | None = None) -> list[Finding]:
    """Historial append-only; una reversion es una decision nueva que cita la previa."""
    findings: list[Finding] = []
    location = f"decision[{decision.get('candidate_id', '?')}]"

    for required in REQUIRED_DECISION_FIELDS:
        if not decision.get(required):
            findings.append(Finding("IDM-DECISION-FIELD", f"{location}.{required}",
                                    f"a dedupe decision needs {required}"))
    state = str(decision.get("decision", ""))
    if state not in CANDIDATE_STATES:
        findings.append(Finding("IDM-DECISION-STATE", location,
                                f"unknown decision state {state!r}"))

    left, right = decision.get("left_movement_id"), decision.get("right_movement_id")
    if left and right and (left, right) != order_pair(str(left), str(right)):
        findings.append(Finding(
            "IDM-PAIR-ORDER", location,
            "the pair is stored lower id first; otherwise the same pair would produce two "
            "different candidates depending on arrival order"))

    if decision.get("physically_deletes_movement"):
        findings.append(Finding(
            "IDM-NO-PHYSICAL-DELETE", location,
            "a dedupe decision never physically deletes a movement; it records which of "
            "the two the company treats as authoritative"))
    if decision.get("deletes_source_evidence"):
        findings.append(Finding(
            "IDM-EVIDENCE-PRESERVED", location,
            "source evidence survives the decision that superseded it"))

    reverses = decision.get("reverses_decision_id")
    if prior is not None:
        if not reverses:
            findings.append(Finding(
                "IDM-REVERSAL-REFERENCE", f"{location}.reverses_decision_id",
                "a reversal is a new decision that names the one it reverses; editing the "
                "prior decision would erase the audit trail"))
        elif reverses != prior.get("decision_id"):
            findings.append(Finding("IDM-REVERSAL-REFERENCE",
                                    f"{location}.reverses_decision_id",
                                    "the reversal names a decision that is not the prior one"))
        if decision.get("decided_by") and decision.get("decided_by") == prior.get("decided_by"):
            findings.append(Finding(
                "IDM-REVERSAL-SOD", f"{location}.decided_by",
                "whoever took the original decision does not get to reverse it alone"))
    elif reverses:
        findings.append(Finding("IDM-REVERSAL-REFERENCE", f"{location}.reverses_decision_id",
                                "this decision reverses one that was not supplied"))
    return sorted(set(findings))


# --------------------------------------------------------------------------- #
# Maquina de estados del inbox y propiedad del reintento
# --------------------------------------------------------------------------- #

INBOX_TRANSITIONS = {
    ("received", "claim"): "processing",
    ("processing", "succeed"): "succeeded",
    ("processing", "retryable_failure"): "retryable_failed",
    ("processing", "terminal_failure"): "terminal_failed",
    ("processing", "conflict"): "conflict",
    ("retryable_failed", "claim"): "processing",
}


def inbox_transition(current: str, event: str, *, fencing_token: int | None = None,
                     latest_token: int | None = None) -> Resolution:
    """Transicion del inbox, con token de fencing cuando hay lease.

    Un worker que despierta despues de que su lease expiro no puede escribir: su
    token es viejo. Sin fencing, el trabajador zombi pisa el resultado del que
    tomo el relevo.
    """
    if current not in INBOX_STATES:
        raise IdentityError(f"unknown inbox state {current!r}")
    if current in INBOX_TERMINAL:
        return Resolution("ignore", f"{current} is terminal; nothing re-opens it")
    if fencing_token is not None and latest_token is not None \
            and fencing_token < latest_token:
        return Resolution(
            "reject_stale_worker",
            f"fencing token {fencing_token} is older than {latest_token}",
            [Finding("IDM-STALE-LEASE", "inbox",
                     "a worker whose lease expired does not get to write; its result is "
                     "from a run someone else already replaced")])
    target = INBOX_TRANSITIONS.get((current, event))
    if target is None:
        return Resolution("reject", f"{event!r} is not allowed from {current!r}")
    return Resolution(target, f"{current} -> {target}")


def retry_owners(layers: dict[str, bool]) -> tuple[list[str], list[Finding]]:
    """Exactamente un dueno del reintento.

    Si el adaptador reintenta, el circuit breaker reprograma y el broker reentrega,
    un fallo se multiplica por tres y el presupuesto de la operacion deja de
    significar nada.
    """
    owners = sorted(name for name, enabled in layers.items() if enabled)
    findings: list[Finding] = []
    if len(owners) > 1:
        findings.append(Finding(
            "IDM-RETRY-LAYERS", "retry_policy",
            f"{owners} all schedule retries; a failure would be multiplied and no budget "
            "would mean anything"))
    elif not owners:
        findings.append(Finding("IDM-RETRY-OWNERLESS", "retry_policy",
                                "nobody owns the retry; a failure would simply be lost"))
    elif owners[0] != RETRY_OWNER:
        findings.append(Finding(
            "IDM-RETRY-OWNER", "retry_policy",
            f"the retry owner is {owners[0]!r}; the contract fixes it at {RETRY_OWNER!r}"))
    return owners, sorted(set(findings))


def redacts_raw_values(log_record: dict[str, Any]) -> list[Finding]:
    """Ni valores crudos ni la huella en claro salen en un log."""
    findings: list[Finding] = []
    for key, value in sorted(log_record.items()):
        if key in ("amount", "reference", "counterparty", "description", "account_number"):
            findings.append(Finding(
                "IDM-FINGERPRINT-PRIVACY", f"log.{key}",
                f"{key} is a raw business value and never reaches a log"))
        if key.endswith("fingerprint") and isinstance(value, str) and len(value) == 64:
            findings.append(Finding(
                "IDM-FINGERPRINT-PRIVACY", f"log.{key}",
                "a fingerprint is not an anonymisation; logging it in full re-identifies "
                "the features it was built from"))
    return sorted(set(findings))
