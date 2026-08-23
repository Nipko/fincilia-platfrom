"""Acceso a PostgreSQL con el contexto de tenancy puesto por el servidor.

Toda consulta del producto pasa por aqui, y aqui siempre se abre transaccion
antes de tocar nada. La razon es concreta: el contexto de RLS se fija con
`set_config(..., is_local => true)`, que se deshace al terminar la transaccion.
Si se fijara a nivel de sesion, la siguiente peticion que reutilizara esa
conexion del pool heredaria la empresa de la anterior, y el aislamiento se
convertiria en una loteria de reutilizacion de conexiones.

Cuando no hay empresa, el contexto se fija a cadena vacia en vez de dejarlo sin
definir. `current_setting('fincilia.company_id', true)` devolveria NULL, la
comparacion seria NULL y tampoco pasaria ninguna fila; pero fijarlo explicitamente
deja claro en el log de la sesion que se decidio no tener empresa, en vez de
parecer un olvido.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import IsolationLevel
from psycopg_pool import ConnectionPool

from .settings import Settings

def _read_committed(connection: psycopg.Connection) -> None:
    """Fija READ COMMITTED en cada conexion nueva del pool.

    No es un argumento de `connect()`: pasarlo ahi hace que **toda** conexion
    falle, el pool se quede vacio y la unica senal sea un `PoolTimeout` a los
    diez segundos, que no señala a la causa.

    Explicito y no heredado: la idempotencia de la subida se apoya en que el
    perdedor de un `ON CONFLICT` vea la fila que el ganador acaba de confirmar.
    Bajo REPEATABLE READ no la veria, y la API reportaria un fallo por una
    entrega que si existe. Depender del valor por defecto del servidor es
    depender de una configuracion que nadie de este lado controla.
    """
    connection.isolation_level = IsolationLevel.READ_COMMITTED


POOL_WAIT_SECONDS = 10.0
COMPANY_SETTING = "fincilia.company_id"
SUBJECT_SETTING = "fincilia.subject_id"


class Database:
    """Pool de conexiones con sesiones que declaran su alcance."""

    def __init__(self, settings: Settings, *, open_now: bool = True) -> None:
        self._settings = settings
        self._pool = ConnectionPool(
            # `str(...)`: `PostgresDsn` es un objeto de pydantic, y pasarlo tal cual
            # hace que el pool falle al conectar y reintente con espera creciente.
            # El sintoma es una peticion que no responde, no un error.
            conninfo=str(settings.database_url),
            min_size=settings.database_pool_min,
            max_size=settings.database_pool_max,
            # `autocommit=False` no basta: psycopg abre la transaccion al primer
            # comando. Lo que garantiza el alcance es `connection.transaction()`.
            kwargs={"autocommit": False},
            configure=_read_committed,
            # Esperar indefinidamente por una conexion convierte una base caida en
            # una API colgada. Mejor un error rapido que un cliente en el limbo.
            timeout=POOL_WAIT_SECONDS,
            check=ConnectionPool.check_connection,
            open=open_now,
            name="fincilia",
        )

    @property
    def pool(self) -> ConnectionPool:
        return self._pool

    @contextmanager
    def session(self, *, company_id: str | None = None,
                subject_id: str | None = None) -> Iterator[psycopg.Connection]:
        """Transaccion con el contexto de tenancy fijado y acotado a ella."""
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(self._settings.database_statement_timeout_ms),))
                    cursor.execute("SELECT set_config(%s, %s, true)",
                                   (COMPANY_SETTING, company_id or ""))
                    cursor.execute("SELECT set_config(%s, %s, true)",
                                   (SUBJECT_SETTING, subject_id or ""))
                yield connection

    def scalar(self, statement: str, params: tuple = ()) -> object:
        """Consulta sin alcance de empresa: solo para sondas y diagnostico."""
        with self.session() as connection, connection.cursor() as cursor:
            cursor.execute(statement, params)
            row = cursor.fetchone()
            return row[0] if row else None

    def close(self) -> None:
        self._pool.close()
