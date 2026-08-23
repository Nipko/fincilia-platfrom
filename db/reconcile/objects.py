"""Reconciliador entre PostgreSQL y el almacen de objetos.

Una subida escribe en dos sitios: primero el objeto, despues la fila. Entre las
dos hay una ventana, y una caida ahi deja un objeto sin fila. Al reves tambien es
posible si alguien borrara un objeto, que es justo lo que ningun rol puede hacer.

Este reconciliador **detecta y describe**; no borra nada. Un objeto direccionado
por contenido puede estar referenciado por una transaccion que todavia no
confirmo, y borrar lo que parece huerfano es como se pierde evidencia. Lo unico
que repara, y solo si se lo piden, es lo unico seguro de reparar: reencolar el
trabajo de un artefacto que quedo registrado sin trabajo vivo.

    python -m db.reconcile.objects --dsn "$FINCILIA_MIGRATOR_URL"
    python -m db.reconcile.objects --dsn ... --repair

Es idempotente: dos ejecuciones seguidas dan el mismo informe y la segunda no
cambia nada.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.settings import Settings

ZONES = ("quarantine", "raw")


def build_settings() -> Settings:
    """Ajustes explicitos, sin heredar el entorno.

    El contenedor que ejecuta esto lleva varias DSN -- una por rol, para las
    pruebas de privilegios -- y `Settings` prohibe variables `FINCILIA_*` que no
    declare. Leer lo que hace falta y construirlo a mano es mas honesto que
    relajar esa prohibicion, que existe para que nadie configure por accidente.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("FINCILIA_")}
    for key in saved:
        del os.environ[key]
    try:
        return Settings(
            env="local",
            service_name="fincilia-reconciler",
            database_url=saved.get("FINCILIA_DATABASE_URL", ""),
            cache_url=saved.get("FINCILIA_CACHE_URL", "redis://valkey:6379/0"),
            object_store_endpoint=saved.get("FINCILIA_OBJECT_STORE_ENDPOINT", ""),
            object_access_key=saved.get("FINCILIA_OBJECT_ACCESS_KEY", ""),
            object_secret_key=saved.get("FINCILIA_OBJECT_SECRET_KEY", ""),
        )
    finally:
        os.environ.update(saved)


def companies(connection: psycopg.Connection, declared: list[str]) -> list[str]:
    """Empresas a reconciliar.

    Toda tabla que lista empresas lleva RLS forzada, asi que **no existe** una
    consulta que las enumere sin contexto, y eso es deliberado. Lo que si es
    legible sin contexto es el puntero de despacho, que solo tiene trabajo
    pendiente. Por eso el alcance se pasa explicitamente cuando hace falta
    revisar mas que eso.

    Devolver una lista vacia y declarar «correcto» seria decir que todo esta bien
    tras no haber mirado nada.
    """
    if declared:
        return sorted(set(declared))
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT company_id::text FROM fincilia.dispatch_pointer")
        return sorted(row[0] for row in cursor.fetchall())


def scoped(connection: psycopg.Connection, company_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                       (company_id,))


def rows_without_objects(connection: psycopg.Connection, store: S3ObjectStore,
                         company_id: str) -> list[dict]:
    """Artefactos registrados cuyo objeto no esta donde la fila dice."""
    scoped(connection, company_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT artifact_id::text, zone, object_key, content_sha256 "
            "FROM fincilia.source_artifact")
        artifacts = cursor.fetchall()
    missing = []
    for artifact_id, zone, key, digest in artifacts:
        if not store.exists(zone, key):
            missing.append({"artifact_id": artifact_id, "zone": zone,
                            "content_sha256": digest})
    return missing


def objects_without_rows(connection: psycopg.Connection, store: S3ObjectStore,
                         company_id: str) -> list[dict]:
    """Objetos sin fila: la ventana entre escribir el objeto y registrar la fila.

    No se borran. Estan direccionados por contenido, asi que una subida posterior
    de los mismos bytes los reutiliza tal cual; y lo que parece huerfano puede ser
    de una transaccion que aun no confirmo.
    """
    scoped(connection, company_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT content_sha256 FROM fincilia.source_artifact")
        known = {row[0] for row in cursor.fetchall()}

    orphans = []
    prefix = f"company/{company_id}/"
    for zone in ZONES:
        for key in store.list_keys(zone, prefix):
            digest = key.rsplit("/", 1)[-1]
            if digest not in known:
                orphans.append({"zone": zone, "content_sha256": digest})
    return orphans


def artifacts_without_work(connection: psycopg.Connection, company_id: str) -> list[str]:
    """Artefactos promovidos que no tienen ni trabajo vivo ni trabajo terminado.

    Es el residuo de una caida entre registrar el artefacto y encolar su trabajo.
    """
    scoped(connection, company_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.artifact_id::text FROM fincilia.source_artifact a "
            "WHERE a.zone = 'raw' AND NOT EXISTS ("
            "  SELECT 1 FROM fincilia.processing_run r "
            "   WHERE r.artifact_id = a.artifact_id AND r.kind = 'profile')")
        return [row[0] for row in cursor.fetchall()]


def repair(connection: psycopg.Connection, company_id: str,
           artifact_ids: list[str]) -> list[str]:
    """Reencola lo que quedo sin trabajo. Idempotente por la funcion de despacho."""
    scoped(connection, company_id)
    requeued = []
    for artifact_id in artifact_ids:
        with connection.cursor() as cursor:
            cursor.execute("SELECT fincilia.enqueue_processing_run(%s, %s, 'profile')",
                           (company_id, artifact_id))
        requeued.append(artifact_id)
    return requeued


def reconcile(dsn: str, settings: Settings, *, do_repair: bool = False,
              scope: list[str] | None = None) -> dict:
    store = S3ObjectStore(settings)
    report: dict = {"ok": True, "companies": [], "repaired": [],
                    "rows_without_objects": [], "objects_without_rows": [],
                    "artifacts_without_work": [], "scope": "explicit" if scope else "pending_work"}
    with psycopg.connect(dsn, autocommit=True) as connection:
        for company_id in companies(connection, scope or []):
            report["companies"].append(company_id)
            for item in rows_without_objects(connection, store, company_id):
                report["rows_without_objects"].append({**item, "company_id": company_id})
            for item in objects_without_rows(connection, store, company_id):
                report["objects_without_rows"].append({**item, "company_id": company_id})
            pending = artifacts_without_work(connection, company_id)
            for artifact_id in pending:
                report["artifacts_without_work"].append(
                    {"company_id": company_id, "artifact_id": artifact_id})
            if do_repair and pending:
                report["repaired"].extend(
                    {"company_id": company_id, "artifact_id": artifact_id}
                    for artifact_id in repair(connection, company_id, pending))

    # Una fila sin objeto es una inconsistencia real: la evidencia que sostiene
    # el registro no esta. No se declara correcto un estado que no lo es.
    if not report["companies"]:
        # Sin alcance no se ha comprobado nada, y no comprobar nada no es estar
        # bien. Se dice, en vez de devolver un informe vacio en verde.
        report["ok"] = False
        report["error"] = ("no company was in scope: pass --company, or run it when "
                           "there is pending work in the dispatch table")
        return report
    report["ok"] = not report["rows_without_objects"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia intake reconciler")
    parser.add_argument("--dsn", default=os.environ.get("FINCILIA_MIGRATOR_URL", ""))
    parser.add_argument("--repair", action="store_true",
                        help="reencola artefactos promovidos sin trabajo de perfilado")
    parser.add_argument("--company", action="append", default=[],
                        help="empresa a revisar; repetible. Sin esto solo se revisa "
                             "lo que tiene trabajo pendiente")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if not args.dsn:
        print(json.dumps({"ok": False, "error": "--dsn or FINCILIA_MIGRATOR_URL required"}),
              file=sys.stderr)
        return 2
    report = reconcile(args.dsn, build_settings(), do_repair=args.repair,
                       scope=args.company)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
