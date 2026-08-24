"""INSERT multifila contra COPY a tabla temporal: medida y ocho comprobaciones.

El mandato de FNC-P3.6 pide comparar dos formas de meter cien mil filas en una
tabla con `FORCE ROW LEVEL SECURITY`:

**A.** `executemany` de `INSERT` multifila, que es lo que hace hoy el worker.

**B.** `COPY` a una tabla `TEMPORARY ... ON COMMIT DROP` y despues
`INSERT ... SELECT` hacia la tabla con RLS. `COPY` directo sobre la tabla con RLS
no es una opcion: PostgreSQL lo rechaza, y esa fue la conclusion de P3.5.

B **solo se adopta** si demuestra ocho cosas, y ninguna es opinable:

1. ninguna desactivacion de RLS;
2. tabla temporal aislada por sesion;
3. contexto de empresa verificado antes de crear y de cargar;
4. cero privilegios adicionales;
5. ninguna tabla de staging persistente compartida;
6. rollback completo;
7. cross-company imposible;
8. mejora medible.

Este modulo las comprueba una a una contra PostgreSQL real y mide las rutas. No
decide: imprime el resultado, y el veredicto lo escribe una persona leyendo los
numeros.

    python -m db.spikes.staging_benchmark --rows 100000 --company <uuid>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from typing import Any

import psycopg

LOCATOR_KIND = "tabular_delimited"

# Columnas de `raw_record` que escribe la ruta de extraccion. `raw_record_id` y
# `created_at` los pone la base.
COLUMNS = ("company_id", "artifact_id", "processing_run_id", "record_ordinal",
           "origin_locator", "raw_values", "values_digest")

INSERT_TAIL = (
    "INSERT INTO fincilia.raw_record (raw_record_id, company_id, artifact_id, "
    "processing_run_id, record_ordinal, origin_locator, raw_values, "
    "values_digest) ")

TEMP_TABLE = (
    "CREATE TEMPORARY TABLE staging_raw_record ("
    "  company_id uuid, artifact_id uuid, processing_run_id uuid,"
    "  record_ordinal integer, origin_locator jsonb, raw_values jsonb,"
    "  values_digest char(64)) ON COMMIT DROP")


def digest_of(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def synthetic_rows(count: int, *, company_id: str, artifact_id: str,
                   run_id: str, sha256: str, start: int = 1):
    """Filas sinteticas con la forma exacta que exige `ck_raw_locator_typed`."""
    for ordinal in range(start, start + count):
        values = [f"{(ordinal % 28) + 1:02d}/{(ordinal % 12) + 1:02d}/2026",
                  f"Movimiento sintetico {ordinal}", f"REF-{ordinal:06d}",
                  f"{1000 + (ordinal % 9000)},{ordinal % 100:02d}"]
        locator = {"locator_kind": LOCATOR_KIND, "artifact_sha256": sha256,
                   "record_ordinal": ordinal, "byte_start": ordinal * 64,
                   "byte_end": ordinal * 64 + 63, "field_count": len(values)}
        yield (company_id, artifact_id, run_id, ordinal,
               json.dumps(locator, ensure_ascii=False, sort_keys=True),
               json.dumps(values, ensure_ascii=False),
               digest_of(values))


# --------------------------------------------------------------------------- #
# Las rutas
# --------------------------------------------------------------------------- #

def _batched(rows, size: int):
    batch: list[tuple] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def insert_multirow(connection: psycopg.Connection, rows, *, size: int) -> int:
    """Ruta A: lo que hace hoy el worker. Una transaccion por tanda."""
    written = 0
    for batch in _batched(rows, size):
        with connection.cursor() as cursor:
            cursor.executemany(
                INSERT_TAIL + "VALUES (gen_random_uuid(), %s, %s, %s, %s, "
                "%s::jsonb, %s::jsonb, %s) "
                "ON CONFLICT (processing_run_id, record_ordinal) DO NOTHING",
                batch)
        connection.commit()
        written += len(batch)
    return written


def copy_through_temp(connection: psycopg.Connection, rows, *, size: int) -> int:
    """Ruta B: `COPY` a temporal y `INSERT ... SELECT` hacia la tabla con RLS.

    La temporal se crea `ON COMMIT DROP` **dentro** de la misma transaccion que
    la carga: no existe fuera de ella, no la ve otra sesion, y no queda nada que
    limpiar si el proceso muere en medio. El precio de esa propiedad es un
    `CREATE TEMPORARY TABLE` por tanda, y por eso la medida se toma tambien con
    tandas grandes: con tandas pequenas el coste fijo se paga muchas veces y la
    comparacion diria mas del tamano de la tanda que de la ruta.
    """
    written = 0
    for batch in _batched(rows, size):
        _load_batch(connection, batch, conflict=True)
        connection.commit()
        written += len(batch)
    return written


def _load_batch(connection: psycopg.Connection, batch: list[tuple], *,
                conflict: bool) -> None:
    with connection.cursor() as cursor:
        cursor.execute(TEMP_TABLE)
        with cursor.copy("COPY staging_raw_record (" + ", ".join(COLUMNS) +
                         ") FROM STDIN") as copy:
            for row in batch:
                copy.write_row(row)
        cursor.execute(
            INSERT_TAIL + "SELECT gen_random_uuid(), " + ", ".join(COLUMNS) +
            " FROM staging_raw_record" +
            (" ON CONFLICT (processing_run_id, record_ordinal) DO NOTHING"
             if conflict else ""))


# --------------------------------------------------------------------------- #
# Las ocho comprobaciones
# --------------------------------------------------------------------------- #

def security_checks(app_dsn: str, migrator_dsn: str, *, company_id: str,
                    other_company_id: str, artifact_id: str, run_id: str,
                    sha256: str) -> dict[str, Any]:
    """Las ocho, cada una con la evidencia que la sostiene."""
    findings: dict[str, Any] = {}

    with psycopg.connect(app_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            # 3. El contexto se verifica antes de crear y de cargar. Sin el, la
            #    politica de la tabla destino rechaza la fila: la temporal no
            #    abre un camino que lo esquive.
            cursor.execute("SELECT current_setting('fincilia.company_id', true)")
            findings["company_context_before_load"] = cursor.fetchone()[0] == company_id

            # 1. Ninguna desactivacion de RLS: la tabla destino sigue con la
            #    politica puesta y forzada mientras la ruta B trabaja.
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'fincilia.raw_record'::regclass")
            enabled, forced = cursor.fetchone()
            findings["rls_still_enabled"] = bool(enabled)
            findings["rls_still_forced"] = bool(forced)

            # 4. Cero privilegios adicionales. `TEMPORARY` sobre la base es un
            #    privilegio que PostgreSQL concede a PUBLIC por defecto, asi que
            #    la ruta B no pide nada nuevo. Se registra igualmente: apoyarse
            #    en un privilegio de PUBLIC no es lo mismo que no necesitar
            #    ninguno, y quien revise esto tiene que poder verlo.
            cursor.execute(
                "SELECT has_database_privilege(current_user, current_database(), "
                "       'TEMPORARY')")
            findings["temp_privilege_already_held"] = bool(cursor.fetchone()[0])
            cursor.execute(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE grantee = current_user AND table_schema = 'fincilia'")
            findings["table_grants"] = cursor.fetchone()[0]

    # 2 y 5. Aislada por sesion y sin staging persistente: se crea dentro de una
    #        transaccion, se carga, y al confirmar desaparece. Otra sesion no la
    #        ve mientras existe, y despues no existe para nadie.
    with psycopg.connect(app_dsn) as first, psycopg.connect(app_dsn) as second:
        with first.cursor() as cursor:
            cursor.execute("CREATE TEMPORARY TABLE staging_probe (n integer) "
                           "ON COMMIT DROP")
            cursor.execute("INSERT INTO staging_probe VALUES (1)")
        with second.cursor() as other:
            other.execute(
                "SELECT count(*) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = 'staging_probe' AND n.nspname LIKE 'pg_temp%'")
            findings["invisible_to_another_session"] = other.fetchone()[0] == 0
        first.commit()
        with first.cursor() as cursor:
            cursor.execute("SELECT to_regclass('staging_probe') IS NULL")
            findings["dropped_on_commit"] = bool(cursor.fetchone()[0])

    with psycopg.connect(migrator_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname LIKE 'staging%' AND n.nspname = 'fincilia'")
            findings["no_persistent_shared_staging"] = cursor.fetchone()[0] == 0

    # 6. Rollback completo: si la transaccion cae, ni la temporal ni las filas
    #    quedan. Se prueba levantando a proposito despues del `INSERT ... SELECT`.
    with psycopg.connect(app_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            cursor.execute("SELECT count(*) FROM fincilia.raw_record "
                           "WHERE processing_run_id = %s", (run_id,))
            before = cursor.fetchone()[0]
        _load_batch(connection, list(synthetic_rows(
            10, company_id=company_id, artifact_id=artifact_id, run_id=run_id,
            sha256=sha256, start=900_001)), conflict=True)
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            cursor.execute("SELECT count(*) FROM fincilia.raw_record "
                           "WHERE processing_run_id = %s", (run_id,))
            findings["rollback_leaves_nothing"] = cursor.fetchone()[0] == before
            cursor.execute("SELECT to_regclass('staging_raw_record') IS NULL")
            findings["rollback_drops_the_temp_table"] = bool(cursor.fetchone()[0])

    # 7. Cross-company imposible: con el contexto de otra empresa puesto, la
    #    politica de la tabla destino rechaza la fila aunque venga de la
    #    temporal. La temporal no lleva politica, y por eso importa que la
    #    frontera este en el destino y no en el staging.
    with psycopg.connect(app_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (other_company_id,))
        try:
            _load_batch(connection, list(synthetic_rows(
                5, company_id=company_id, artifact_id=artifact_id, run_id=run_id,
                sha256=sha256, start=800_001)), conflict=False)
            findings["cross_company_refused"] = False
        except psycopg.Error as error:
            findings["cross_company_refused"] = True
            findings["cross_company_error"] = type(error).__name__
        finally:
            connection.rollback()

    return findings


REQUIRED_CHECKS = (
    "rls_still_enabled", "rls_still_forced", "company_context_before_load",
    "temp_privilege_already_held", "invisible_to_another_session",
    "dropped_on_commit", "no_persistent_shared_staging",
    "rollback_leaves_nothing", "rollback_drops_the_temp_table",
    "cross_company_refused",
)


# --------------------------------------------------------------------------- #
# Montaje y desmontaje
# --------------------------------------------------------------------------- #

def prepare(migrator_dsn: str, company_id: str, marker: str,
            runs: int) -> dict[str, Any]:
    """Un artefacto sintetico y una ejecucion por ruta donde escribir."""
    sha256 = hashlib.sha256(marker.encode("utf-8")).hexdigest()
    with psycopg.connect(migrator_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            cursor.execute(
                "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
                "filename, byte_size, content_sha256, media_type, zone, "
                "object_key, status, uploaded_by) "
                "SELECT gen_random_uuid(), %s, %s, %s, %s, 'text/csv', 'raw', %s, "
                "'stored', s.subject_id FROM fincilia.subject s "
                "WHERE s.subject_kind = 'person' LIMIT 1 RETURNING artifact_id",
                (company_id, f"{marker}.csv", 1_000_000, sha256,
                 f"raw/{sha256}.csv"))
            artifact_id = str(cursor.fetchone()[0])
            identifiers = []
            for attempt in range(1, runs + 1):
                cursor.execute(
                    "INSERT INTO fincilia.processing_run (run_id, company_id, "
                    "artifact_id, kind, status, attempt, started_at) "
                    "VALUES (gen_random_uuid(), %s, %s, 'extract', 'running', "
                    "%s, now()) RETURNING run_id",
                    (company_id, artifact_id, attempt))
                identifiers.append(str(cursor.fetchone()[0]))
    return {"artifact_id": artifact_id, "sha256": sha256, "runs": identifiers}


def cleanup(migrator_dsn: str, company_id: str, context: dict[str, Any]) -> None:
    with psycopg.connect(migrator_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            cursor.execute("DELETE FROM fincilia.raw_record WHERE artifact_id = %s",
                           (context["artifact_id"],))
            cursor.execute("DELETE FROM fincilia.dispatch_pointer WHERE run_id IN ("
                           " SELECT run_id FROM fincilia.processing_run "
                           " WHERE artifact_id = %s)", (context["artifact_id"],))
            cursor.execute("DELETE FROM fincilia.run_attempt WHERE run_id IN ("
                           " SELECT run_id FROM fincilia.processing_run "
                           " WHERE artifact_id = %s)", (context["artifact_id"],))
            cursor.execute("DELETE FROM fincilia.processing_run WHERE artifact_id = %s",
                           (context["artifact_id"],))
            cursor.execute("DELETE FROM fincilia.source_artifact WHERE artifact_id = %s",
                           (context["artifact_id"],))


def peak_rss_mib() -> float:
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows
        return 0.0
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


PATHS = (
    ("insert_multirow_500", insert_multirow, 500),
    ("copy_through_temp_500", copy_through_temp, 500),
    ("copy_through_temp_5000", copy_through_temp, 5_000),
)


def run(rows: int, *, app_dsn: str, migrator_dsn: str, company_id: str,
        other_company_id: str) -> dict[str, Any]:
    marker = f"spike-{uuid.uuid4().hex[:12]}"
    context = prepare(migrator_dsn, company_id, marker, len(PATHS))
    try:
        measured: dict[str, Any] = {"rows": rows, "batch_note": (
            "B paga un CREATE TEMPORARY TABLE por tanda: es el precio de "
            "ON COMMIT DROP, y por eso se mide tambien con tandas grandes")}
        for (label, path, size), run_id in zip(PATHS, context["runs"]):
            with psycopg.connect(app_dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company_id,))
                connection.commit()
                before = peak_rss_mib()
                started = time.monotonic()
                written = path(connection, synthetic_rows(
                    rows, company_id=company_id,
                    artifact_id=context["artifact_id"], run_id=run_id,
                    sha256=context["sha256"]), size=size)
                elapsed = time.monotonic() - started
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company_id,))
                    cursor.execute(
                        "SELECT count(*), count(DISTINCT record_ordinal) "
                        "FROM fincilia.raw_record WHERE processing_run_id = %s",
                        (run_id,))
                    stored, distinct = cursor.fetchone()
            measured[label] = {
                "seconds": round(elapsed, 2), "batch_size": size,
                "rows_per_second": round(written / elapsed) if elapsed else None,
                "stored": stored, "distinct_ordinals": distinct,
                "peak_rss_mib": peak_rss_mib(),
                "rss_growth_mib": round(peak_rss_mib() - before, 1),
            }

        baseline = measured["insert_multirow_500"]["seconds"]
        for label in ("copy_through_temp_500", "copy_through_temp_5000"):
            other = measured[label]["seconds"]
            measured[f"speedup_{label}"] = round(baseline / other, 2) if other else None

        measured["security"] = security_checks(
            app_dsn, migrator_dsn, company_id=company_id,
            other_company_id=other_company_id,
            artifact_id=context["artifact_id"], run_id=context["runs"][0],
            sha256=context["sha256"])
        # El veredicto se compone de las diez comprobaciones, y todas tienen que
        # salir: una sola en falso basta para no adoptar la ruta B.
        measured["security_clean"] = all(
            measured["security"].get(name) for name in REQUIRED_CHECKS)
        return measured
    finally:
        cleanup(migrator_dsn, company_id, context)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare multi-row INSERT with COPY through a temporary table")
    parser.add_argument("--rows", type=int, default=20_000)
    parser.add_argument("--company", default=os.environ.get("FINCILIA_SPIKE_COMPANY"))
    parser.add_argument("--other-company",
                        default=os.environ.get("FINCILIA_SPIKE_OTHER_COMPANY"))
    arguments = parser.parse_args()

    app_dsn = os.environ.get("FINCILIA_DATABASE_URL", "")
    migrator_dsn = os.environ.get("FINCILIA_MIGRATOR_URL", "")
    if not app_dsn or not migrator_dsn or not arguments.company:
        print(json.dumps({"skipped": "app/migrator DSNs and a company are required"}))
        return 0
    result = run(arguments.rows, app_dsn=app_dsn, migrator_dsn=migrator_dsn,
                 company_id=arguments.company,
                 other_company_id=arguments.other_company or arguments.company)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
