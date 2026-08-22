"""Semilla sintetica del entorno local: una firma y dos empresas de demo.

Idempotente y determinista. Los identificadores salen de `uuid5` sobre un espacio
de nombres fijo, asi que volver a sembrar no duplica nada y dos maquinas
distintas producen la misma demo: un enlace a una empresa sigue funcionando
despues de recrear el volumen.

**Todo aqui es sintetico.** Ni los NIT, ni los nombres, ni las contrasenas
corresponden a nada real, y la tabla `local_credential` solo existe en el entorno
local. Si `FINCILIA_REAL_DATA_ENABLED` estuviera encendido, este script se niega
a correr.

    python -m db.seed.local --dsn "$FINCILIA_MIGRATOR_URL"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import psycopg

from fincilia_platform.identity import ALGORITHM, ITERATIONS, hash_secret

# Espacio de nombres fijo del entorno local. No identifica nada fuera de la demo.
NAMESPACE = uuid.UUID("5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e")
DEFAULT_SECRET = "fincilia-demo-only"

FIRM_NAME = "Contadores Andes SAS"
COMPANIES = (
    {"key": "espiga", "legal_name": "Panaderia La Espiga SAS", "country_code": "CO"},
    {"key": "andinos", "legal_name": "Transportes Andinos SAS", "country_code": "CO"},
)
# El aprovisionador es un principal de servicio, no una persona: hace falta
# alguien que conceda el primer rol, y `ck_grant_not_self` impide que el dueno se
# lo conceda a si mismo.
PROVISIONER = {"key": "provisioner", "display_name": "Aprovisionador local",
               "kind": "service_principal"}
PEOPLE = (
    {"key": "sofia", "username": "sofia@demo.local", "display_name": "Sofia Owner",
     "firm_role": "owner", "grants": {"espiga": "owner", "andinos": "owner"}},
    {"key": "ana", "username": "ana@demo.local", "display_name": "Ana Preparadora",
     "firm_role": "member", "grants": {"espiga": "preparer", "andinos": "preparer"}},
    {"key": "beto", "username": "beto@demo.local", "display_name": "Beto Revisor",
     "firm_role": "member", "grants": {"espiga": "reviewer"}},
    {"key": "carla", "username": "carla@demo.local", "display_name": "Carla Auditora",
     "firm_role": "member", "grants": {"andinos": "auditor"}},
)


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def set_company_context(cursor, company_id: str | None) -> None:
    cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                   (company_id or "",))


def seed(dsn: str, *, secret: str) -> dict[str, object]:
    firm_id = stable_id("firm", "andes")
    created: list[str] = []

    with psycopg.connect(dsn, autocommit=False) as connection:
        with connection.cursor() as cursor:
            # -- sujetos --------------------------------------------------- #
            for person in (PROVISIONER, *PEOPLE):
                subject_id = stable_id("subject", person["key"])
                cursor.execute(
                    "INSERT INTO fincilia.subject (subject_id, subject_kind, display_name) "
                    "VALUES (%s, %s, %s) ON CONFLICT (subject_id) DO NOTHING",
                    (subject_id, person.get("kind", "person"), person["display_name"]))
                if cursor.rowcount:
                    created.append(f"subject:{person['key']}")

            # -- credenciales locales -------------------------------------- #
            for person in PEOPLE:
                subject_id = stable_id("subject", person["key"])
                # La sal es determinista para que resembrar no cambie el hash; el
                # coste de derivacion es el mismo que en un alta real.
                salt = uuid.uuid5(NAMESPACE, f"salt:{person['key']}").hex
                cursor.execute(
                    "INSERT INTO fincilia.local_credential (subject_id, username, "
                    "algorithm, iterations, salt, secret_hash) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (subject_id) DO NOTHING",
                    (subject_id, person["username"], ALGORITHM, ITERATIONS, salt,
                     hash_secret(secret, salt=salt, iterations=ITERATIONS)))
                if cursor.rowcount:
                    created.append(f"credential:{person['username']}")

                cursor.execute(
                    "INSERT INTO fincilia.identity_binding (subject_id, issuer, "
                    "external_subject_ref) VALUES (%s, 'local', %s) "
                    "ON CONFLICT (subject_id) DO NOTHING",
                    (subject_id, person["username"]))

            # -- firma y membresias ---------------------------------------- #
            cursor.execute(
                "INSERT INTO fincilia.firm (firm_id, legal_name) VALUES (%s, %s) "
                "ON CONFLICT (firm_id) DO NOTHING", (firm_id, FIRM_NAME))
            if cursor.rowcount:
                created.append("firm:andes")
            for person in PEOPLE:
                cursor.execute(
                    "INSERT INTO fincilia.membership (membership_id, subject_id, "
                    "firm_id, firm_role) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (subject_id, firm_id) DO NOTHING",
                    (stable_id("membership", person["key"]),
                     stable_id("subject", person["key"]), firm_id, person["firm_role"]))

            # -- empresas -------------------------------------------------- #
            for company in COMPANIES:
                company_id = stable_id("company", company["key"])
                # Con FORCE RLS, aprovisionar tambien declara sobre que empresa
                # se actua. No hay via privilegiada que se salte la politica.
                set_company_context(cursor, company_id)
                cursor.execute(
                    "INSERT INTO fincilia.company (company_id, legal_name, "
                    "tax_id_token, country_code) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (company_id) DO NOTHING",
                    (company_id, company["legal_name"],
                     # El NIT nunca se guarda en claro; en la demo no existe NIT.
                     stable_id("tax_token", company["key"]), company["country_code"]))
                if cursor.rowcount:
                    created.append(f"company:{company['key']}")
                cursor.execute(
                    "INSERT INTO fincilia.authorization_version (company_id, version) "
                    "VALUES (%s, 1) ON CONFLICT (company_id) DO NOTHING", (company_id,))
                cursor.execute(
                    "INSERT INTO fincilia.engagement (engagement_id, firm_id, "
                    "company_id, valid_from) VALUES (%s, %s, %s, DATE '2026-01-01') "
                    "ON CONFLICT (engagement_id) DO NOTHING",
                    (stable_id("engagement", company["key"]), firm_id, company_id))

                for person in PEOPLE:
                    role = person["grants"].get(company["key"])
                    if role is None:
                        continue
                    # El dueno recibe su rol del aprovisionador; el resto, del
                    # dueno. Nadie se concede nada a si mismo.
                    granter = PROVISIONER["key"] if person["key"] == "sofia" else "sofia"
                    cursor.execute(
                        "INSERT INTO fincilia.company_grant (grant_id, company_id, "
                        "subject_id, company_role, granted_by) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (company_id, subject_id, company_role) DO NOTHING",
                        (stable_id("grant", f"{company['key']}:{person['key']}"),
                         company_id, stable_id("subject", person["key"]), role,
                         stable_id("subject", granter)))
                    if cursor.rowcount:
                        created.append(f"grant:{company['key']}:{person['key']}")
            set_company_context(cursor, None)
        connection.commit()

    return {
        "ok": True,
        "firm": {"firm_id": firm_id, "legal_name": FIRM_NAME},
        "companies": [{"company_id": stable_id("company", item["key"]),
                       "legal_name": item["legal_name"]} for item in COMPANIES],
        "users": [{"username": item["username"], "roles": item["grants"]}
                  for item in PEOPLE],
        "created": sorted(created),
        "mutated": bool(created),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fincilia local synthetic seed")
    parser.add_argument("--dsn", default=os.environ.get("FINCILIA_MIGRATOR_URL", ""))
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if os.environ.get("FINCILIA_REAL_DATA_ENABLED", "false").lower() == "true":
        print(json.dumps({"ok": False,
                          "error": "synthetic seed refuses to run with real data enabled"}),
              file=sys.stderr)
        return 2
    if not args.dsn:
        print(json.dumps({"ok": False, "error": "--dsn or FINCILIA_MIGRATOR_URL required"}),
              file=sys.stderr)
        return 2
    secret = os.environ.get("FINCILIA_LOCAL_DEMO_SECRET", DEFAULT_SECRET)
    try:
        report = seed(args.dsn, secret=secret)
    except psycopg.Error as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
