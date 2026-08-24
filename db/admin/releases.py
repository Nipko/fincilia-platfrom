"""Herramienta administrativa de versiones del motor.

Aprobar una version del motor es una decision humana. `lineage-model.json` lo
dice sin rodeos —`agent_can_self_approve: false`— y esta herramienta existe para
que esa decision se pueda tomar, quede escrita y se pueda revisar. **No la toma
ella**: cada aprobacion exige que alguien se nombre y aporte la referencia que la
respalda.

    python -m db.admin.releases list
    python -m db.admin.releases show --release fnc-p3-mapping-0.1.0
    python -m db.admin.releases approve --release fnc-p3-mapping-0.1.0 \\
        --actor "nombre.apellido" --ref "ACTA-2026-02-14" \\
        --rationale "corpus adjudicado sin diferencias"
    python -m db.admin.releases supersede --release fnc-p3-mapping-0.1.0 \\
        --actor "nombre.apellido" --ref "ACTA-2026-05-02" \\
        --rationale "sustituida por 0.2.0"
    python -m db.admin.releases datasets --release fnc-p3-mapping-0.1.0

Corre con el rol migrador, que es el unico que escribe `engine_release`. Ni la
API ni el worker pueden aprobar nada: sus roles solo tienen `SELECT`, y eso es
una propiedad del motor, no una promesa de este fichero.

Cuatro cosas que se niega a hacer:

* **aprobar sin actor.** Una firma sin firmante no responde de nada;
* **aprobar una version flotante.** `latest` no nombra un binario;
* **reaprobar lo ya aprobado.** Cambiar de opinion es otra version;
* **aprobar componentes distintos de los que se muestran.** El digest se calcula
  sobre lo que la herramienta acaba de ensenar, y la base lo guarda: si alguien
  los cambia despues, la API deja de publicar y dice por que.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

from fincilia_contracts.release import FLOATING_TOKENS, digest_of

# Acciones que esta herramienta sabe escribir. `rejected` existe para poder
# cerrar una version que no pasa la evaluacion sin dejarla en borrador para
# siempre, que es como acaban aprobandose por cansancio.
ACTIONS = ("approved", "superseded", "rejected")

# El estado en el que queda la release tras cada accion.
RESULTING_STATE = {"approved": "approved", "superseded": "superseded",
                   "rejected": "draft"}


class AdminError(Exception):
    """La operacion no procede, y el motivo es de quien la pide."""


def _rows(cursor) -> list[dict]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def list_releases(connection: psycopg.Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.release_key, r.state, r.classification, "
            "       r.canonical_schema_version, r.approval_ref, r.created_at, "
            "       jsonb_array_length(r.components) AS components, "
            "       a.actor_identity AS approved_by, a.occurred_at AS approved_at "
            "FROM fincilia.engine_release r "
            "LEFT JOIN fincilia.release_approval a "
            "       ON a.release_id = r.release_id AND a.action = 'approved' "
            "ORDER BY r.created_at DESC")
        return [{**row, "created_at": row["created_at"].isoformat(),
                 "approved_at": row["approved_at"].isoformat()
                 if row["approved_at"] else None}
                for row in _rows(cursor)]


def _load(connection: psycopg.Connection, release_key: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT release_id, release_key, state, classification, "
            "       canonical_schema_version, approval_ref, components, created_at "
            "FROM fincilia.engine_release WHERE release_key = %s", (release_key,))
        rows = _rows(cursor)
    if not rows:
        raise AdminError(f"no engine release is registered as {release_key!r}")
    return rows[0]


def show_release(connection: psycopg.Connection, release_key: str) -> dict:
    """Que es exactamente esta version: sus componentes, sus digests y su firma.

    Es lo que una persona tiene que leer **antes** de aprobar. Si aprueba sin
    mirarlo, la herramienta no puede hacer nada al respecto; lo que si hace es
    que no pueda decir despues que no se lo ensenaron.
    """
    release = _load(connection, release_key)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT action, actor_identity, approval_ref, rationale, "
            "       components_digest, occurred_at FROM fincilia.release_approval "
            "WHERE release_id = %s ORDER BY occurred_at", (release["release_id"],))
        history = [{**row, "occurred_at": row["occurred_at"].isoformat()}
                   for row in _rows(cursor)]
    components = release["components"] or []
    return {
        "release_key": release["release_key"],
        "state": release["state"],
        "classification": release["classification"],
        "canonical_schema_version": release["canonical_schema_version"],
        "approval_ref": release["approval_ref"],
        "created_at": release["created_at"].isoformat(),
        "components": components,
        "components_digest": digest_of(components),
        "history": history,
    }


def datasets_of(connection: psycopg.Connection, release_key: str) -> list[dict]:
    """Que se produjo con esta version.

    Es la pregunta que hay que poder contestar antes de superseder: si algo sale
    mal con una release, lo primero es saber que alcance tiene.

    Se lee **sin contexto de empresa** a proposito. La consulta agrega por estado
    y no devuelve un solo identificador de empresa ni de dataset: quien opera la
    plataforma necesita el alcance, no los datos.
    """
    release = _load(connection, release_key)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT state, count(*) AS datasets, "
            "       coalesce(sum(movement_count), 0) AS movements "
            "FROM fincilia.dataset_version WHERE engine_release_id = %s "
            "GROUP BY state ORDER BY state", (release["release_id"],))
        return [{"state": row["state"], "datasets": int(row["datasets"]),
                 "movements": int(row["movements"])} for row in _rows(cursor)]


def record(connection: psycopg.Connection, *, release_key: str, action: str,
           actor: str, approval_ref: str, rationale: str) -> dict:
    """Escribe la decision de una persona y mueve el estado en la misma transaccion.

    Si una de las dos escrituras fallara sola quedaria o una release aprobada sin
    constancia de quien, o una constancia que no aprueba nada. Las dos o ninguna.
    """
    if action not in ACTIONS:
        raise AdminError(f"unknown action {action!r}; expected one of {ACTIONS}")
    if release_key.strip().lower() in FLOATING_TOKENS:
        raise AdminError(
            f"{release_key!r} is a floating token: it names whatever is there "
            "tomorrow, which is the opposite of reproducible")
    for label, value, low, high in (("actor", actor, 3, 120),
                                    ("ref", approval_ref, 3, 200),
                                    ("rationale", rationale, 3, 500)):
        if not value or not low <= len(value.strip()) <= high:
            raise AdminError(
                f"--{label} is required and must be between {low} and {high} "
                "characters: an approval without one does not answer for anything")

    release = _load(connection, release_key)
    if release["state"] == action:
        raise AdminError(
            f"{release_key} is already {action}; changing your mind is another "
            "release, not another signature on this one")
    if release["state"] == "approved" and action == "approved":
        raise AdminError(f"{release_key} is already approved")
    if release["state"] == "superseded":
        raise AdminError(
            f"{release_key} is superseded; it can still reproduce what it "
            "produced, but it does not start anything new")

    digest = digest_of(release["components"] or [])
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.release_approval (approval_id, release_id, "
            "action, actor_identity, approval_ref, rationale, components_digest) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)",
            (release["release_id"], action, actor.strip(), approval_ref.strip(),
             rationale.strip(), digest))
        cursor.execute(
            "UPDATE fincilia.engine_release SET state = %s, approval_ref = %s "
            "WHERE release_id = %s",
            (RESULTING_STATE[action],
             approval_ref.strip() if action == "approved" else release["approval_ref"],
             release["release_id"]))
    return {"release_key": release_key, "action": action,
            "state": RESULTING_STATE[action], "actor": actor.strip(),
            "approval_ref": approval_ref.strip(), "components_digest": digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Administracion de versiones del motor. No autoaprueba.")
    parser.add_argument("--dsn", default=os.environ.get("FINCILIA_MIGRATOR_URL", ""))
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="listar versiones y su estado")
    for name, help_text in (("show", "componentes, digests e historial"),
                            ("datasets", "que se produjo con esta version")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--release", required=True)
    for name, help_text in (("approve", "aprobar (exige actor y referencia)"),
                            ("supersede", "sustituir por otra version"),
                            ("reject", "cerrar una version que no pasa")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--release", required=True)
        sub.add_argument("--actor", required=True,
                         help="quien decide; una persona, no un servicio")
        sub.add_argument("--ref", required=True,
                         help="acta, ticket o documento que respalda la decision")
        sub.add_argument("--rationale", required=True)
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if not args.dsn:
        print(json.dumps({"ok": False,
                          "error": "--dsn or FINCILIA_MIGRATOR_URL required"}),
              file=sys.stderr)
        return 2

    action = {"approve": "approved", "supersede": "superseded",
              "reject": "rejected"}.get(args.command)
    try:
        with psycopg.connect(args.dsn, autocommit=False) as connection:
            if args.command == "list":
                report = {"releases": list_releases(connection)}
            elif args.command == "show":
                report = show_release(connection, args.release)
            elif args.command == "datasets":
                report = {"release_key": args.release,
                          "produced": datasets_of(connection, args.release)}
            else:
                report = record(connection, release_key=args.release, action=action,
                                actor=args.actor, approval_ref=args.ref,
                                rationale=args.rationale)
            connection.commit()
    except AdminError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(json.dumps({"ok": False, "error": type(error).__name__,
                          "detail": str(error).splitlines()[0]}, ensure_ascii=False),
              file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, **report}, indent=2, sort_keys=True,
                     ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
