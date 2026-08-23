"""Ciclos esperados: cuando debia llegar un documento y cuando llega tarde.

Un cierre contable se retrasa por lo que **no** llego, y nadie se entera hasta
que alguien lo busca. Declarar el ciclo convierte esa ausencia en un hecho con
fecha: este extracto se esperaba el dia 5, hoy es 12, y la gracia eran tres dias.

Todo el calculo es determinista y sin reloj propio: la fecha «de hoy» entra como
argumento. Una funcion que mirara el reloj daria un resultado distinto en cada
ejecucion y haria imposible probar que el atraso se calcula bien.

Aqui no hay envio de recordatorios. El vencimiento se calcula; avisar a alguien
por un canal externo es otra decision, con su propio consentimiento y su propio
gate.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

PERIODICITIES: Final[tuple[str, ...]] = ("monthly", "fortnightly", "weekly", "custom")

# Estados de una expectativa. `waived` existe porque a veces un periodo no
# genera documento por una razon legitima, y decirlo es mejor que dejarlo
# eternamente atrasado.
STATES: Final[tuple[str, ...]] = ("pending", "satisfied", "late", "waived")

MAX_PERIODS: Final[int] = 120


class CycleError(ValueError):
    """El ciclo no describe un calendario que se pueda recorrer."""


@dataclass(frozen=True)
class Period:
    """Un periodo esperado, con las dos fechas que deciden si algo llego tarde."""

    period_start: date
    period_end: date
    due_on: date
    late_after: date

    def state_on(self, today: date, *, satisfied: bool = False) -> str:
        """En que estado esta este periodo el dia `today`.

        `satisfied` gana siempre: un documento que llego tarde **llego**, y
        seguir llamandolo atrasado despues de recibirlo seria contar dos veces el
        mismo problema.
        """
        if satisfied:
            return "satisfied"
        return "late" if today > self.late_after else "pending"

    def as_dict(self) -> dict[str, str]:
        return {"period_start": self.period_start.isoformat(),
                "period_end": self.period_end.isoformat(),
                "due_on": self.due_on.isoformat(),
                "late_after": self.late_after.isoformat()}


def _end_of_month(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _next_start(start: date, periodicity: str, custom_days: int | None) -> date:
    if periodicity == "monthly":
        return _end_of_month(start) + timedelta(days=1)
    if periodicity == "fortnightly":
        return start + timedelta(days=15)
    if periodicity == "weekly":
        return start + timedelta(days=7)
    return start + timedelta(days=int(custom_days or 1))


def period_end_of(start: date, periodicity: str, custom_days: int | None) -> date:
    """El ultimo dia del periodo que empieza en `start`."""
    return _next_start(start, periodicity, custom_days) - timedelta(days=1)


def validate_cycle(periodicity: str, custom_days: int | None, due_day_offset: int,
                   grace_days: int) -> list[str]:
    """Motivos por los que este ciclo no describe un calendario recorrible."""
    problems: list[str] = []
    if periodicity not in PERIODICITIES:
        problems.append(f"{periodicity!r} is not a declared periodicity")
    if (periodicity == "custom") != (custom_days is not None):
        # `custom` sin numero de dias no dice nada, y un numero de dias sobre una
        # periodicidad con nombre propio dice dos cosas a la vez.
        problems.append("custom needs a day count, and a named periodicity refuses one")
    if custom_days is not None and not 1 <= int(custom_days) <= 366:
        problems.append("a custom period is between 1 and 366 days")
    if not 0 <= int(due_day_offset) <= 120:
        problems.append("the due offset is between 0 and 120 days after the period")
    if not 0 <= int(grace_days) <= 120:
        problems.append("the grace period is between 0 and 120 days")
    return problems


def periods_between(*, anchor: date, until: date, periodicity: str,
                    custom_days: int | None = None, due_day_offset: int = 5,
                    grace_days: int = 3) -> tuple[Period, ...]:
    """Los periodos que van del ancla hasta `until`, con sus fechas calculadas.

    Se generan **hasta** una fecha que entra como argumento, no hasta hoy: dos
    ejecuciones sobre el mismo ciclo tienen que producir los mismos periodos, y
    un generador que mirara el reloj produciria uno mas cada mes sin que nada lo
    pidiera.
    """
    problems = validate_cycle(periodicity, custom_days, due_day_offset, grace_days)
    if problems:
        raise CycleError("; ".join(problems))
    if until < anchor:
        return ()

    periods: list[Period] = []
    start = anchor
    while start <= until and len(periods) < MAX_PERIODS:
        end = period_end_of(start, periodicity, custom_days)
        due = end + timedelta(days=int(due_day_offset))
        periods.append(Period(period_start=start, period_end=end, due_on=due,
                              late_after=due + timedelta(days=int(grace_days))))
        start = _next_start(start, periodicity, custom_days)
    return tuple(periods)


def next_due(*, anchor: date, today: date, periodicity: str,
             custom_days: int | None = None, due_day_offset: int = 5,
             grace_days: int = 3) -> Period | None:
    """El primer periodo cuyo plazo todavia no ha vencido el dia `today`."""
    horizon = today + timedelta(days=366)
    for period in periods_between(anchor=anchor, until=horizon,
                                  periodicity=periodicity, custom_days=custom_days,
                                  due_day_offset=due_day_offset,
                                  grace_days=grace_days):
        if period.due_on >= today:
            return period
    return None


def days_late(period: Period, today: date) -> int:
    """Cuantos dias de atraso lleva, ya descontada la gracia. Cero si no llega."""
    return max(0, (today - period.late_after).days)
