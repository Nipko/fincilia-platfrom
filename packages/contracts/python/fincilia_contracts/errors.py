"""Errores de API en formato RFC 7807, sin filtrar datos sensibles.

Un mensaje de error nunca lleva importes, referencias, nombres de contraparte ni
rutas de fichero: quien recibe un 403 no debe aprender de el que la fila existe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROBLEM_BASE = "https://fincilia.local/problems"


@dataclass(frozen=True)
class ProblemDetail:
    type: str
    title: str
    status: int
    detail: str
    instance: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        extras = payload.pop("extras")
        payload.update(extras)
        if not payload.get("instance"):
            payload.pop("instance")
        return payload


def problem(slug: str, title: str, status: int, detail: str,
            **extras: Any) -> ProblemDetail:
    return ProblemDetail(f"{PROBLEM_BASE}/{slug}", title, status, detail, extras=extras)
