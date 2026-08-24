"""Alta de cuentas, fuentes, vinculos y ciclos, contra PostgreSQL real.

La propiedad que mas importa aqui no es que el alta funcione: es que **el
identificador no sobreviva a la peticion**. Ni en la fila, ni en el rastro de
auditoria, ni en el mensaje de un error. Lo demas —duplicados, aislamiento,
estados— protege que lo que se publique tenga contra que publicarse.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_onboarding -v
"""

from __future__ import annotations

import unittest
import uuid
from datetime import date, timedelta

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from fincilia_api.main import create_app

RUN = uuid.uuid4().hex[:10]
ESPIGA = stable_id("company", "espiga")
ANDINOS = stable_id("company", "andinos")

OWNER = "sofia@demo.local"       # tiene financial_account.manage
PREPARER = "ana@demo.local"      # no lo tiene
REVIEWER = "beto@demo.local"
AUDITOR = "carla@demo.local"

# Sintetico y sin correspondencia con ninguna cuenta real.
IDENTIFIER = "CO-0091-4455-7788"


class OnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()
        cls.accounts: set[str] = set()
        cls.sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if not cls.accounts and not cls.sources:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,))
                    cursor.execute(
                        "DELETE FROM fincilia.source_expectation "
                        "WHERE data_source_id = ANY(%s) "
                        "OR financial_account_id = ANY(%s)",
                        (list(cls.sources), list(cls.accounts)))
                    cursor.execute("DELETE FROM fincilia.source_cycle "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))
                    cursor.execute(
                        "DELETE FROM fincilia.data_source_account "
                        "WHERE data_source_id = ANY(%s) "
                        "OR financial_account_id = ANY(%s)",
                        (list(cls.sources), list(cls.accounts)))
                    cursor.execute("DELETE FROM fincilia.data_source "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))
                    cursor.execute("DELETE FROM fincilia.financial_account "
                                   "WHERE account_id = ANY(%s)",
                                   (list(cls.accounts),))

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def new_account(self, *, marker: str, company: str = ESPIGA,
                    identifier: str | None = None, user: str = OWNER,
                    family: str = "bank_account", currency: str = "COP"):
        response = self.client.post(
            f"/api/v1/companies/{company}/accounts", headers=self.auth(user),
            json={"account_family": family,
                  "display_name": f"Cuenta {marker} {RUN}",
                  "identifier": identifier or f"CO-{RUN}-{marker}",
                  "currency_code": currency, "timezone": "America/Bogota"})
        if response.status_code == 201:
            type(self).accounts.add(response.json()["account_id"])
        return response

    def new_source(self, *, marker: str, company: str = ESPIGA, user: str = OWNER,
                   family: str = "bank_account"):
        response = self.client.post(
            f"/api/v1/companies/{company}/sources", headers=self.auth(user),
            json={"source_family": family,
                  "display_name": f"Fuente {marker} {RUN}",
                  "purpose_code": "operational", "timezone": "America/Bogota"})
        if response.status_code == 201:
            type(self).sources.add(response.json()["data_source_id"])
        return response

    # ------------------------------------------------------------- tokenizacion

    def test_the_identifier_never_reaches_the_database_TST_P35_023(self) -> None:
        response = self.new_account(marker="token", identifier=IDENTIFIER)
        self.assertEqual(201, response.status_code, response.text)
        account = response.json()
        # Lo que vuelve: la cola visible, nunca el numero.
        self.assertEqual(account["identifier_last4"], "7788")
        self.assertNotIn("identifier", set(account) - {"identifier_last4"})

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT identifier_token, identifier_last4, "
                    "       identifier_key_version FROM fincilia.financial_account "
                    "WHERE account_id = %s", (account["account_id"],))
                token, last4, version = cursor.fetchone()
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertNotIn("0091", token)
        self.assertNotIn("4455", token)
        self.assertEqual(last4, "7788")
        self.assertEqual(version, 1)

    def test_the_audit_trail_does_not_carry_the_identifier_TST_P35_024(self) -> None:
        response = self.new_account(marker="audit", identifier="CO-7777-1234-9999")
        self.assertEqual(201, response.status_code, response.text)
        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=25",
                                 headers=self.auth(REVIEWER)).json()
        created = [event for event in events
                   if event["action"] == "account.create"
                   and event["resource_ref"] == response.json()["account_id"]]
        self.assertTrue(created, "the account creation left no trail")
        rendered = str(created[0])
        for fragment in ("7777", "1234", "CO-7777"):
            self.assertNotIn(fragment, rendered)
        # La cola visible si: es lo unico que una persona necesita para
        # reconocer la cuenta, y no la identifica.
        self.assertEqual(created[0]["detail"]["last4"], "9999")

    def test_a_refusal_does_not_quote_the_identifier_TST_P35_025(self) -> None:
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounts", headers=self.auth(OWNER),
            json={"account_family": "bank_account", "display_name": "Rota",
                  "identifier": "!!!!", "currency_code": "COP",
                  "timezone": "America/Bogota"})
        self.assertEqual(422, response.status_code, response.text)
        self.assertNotIn("!!!!", response.text)

    def test_the_same_account_twice_is_detected_without_storing_it_TST_P35_026(self) -> None:
        first = self.new_account(marker="dup", identifier="CO-5555-0000-1111")
        self.assertEqual(201, first.status_code, first.text)
        # Escrito de otra forma: separadores y mayusculas no hacen otra cuenta.
        second = self.new_account(marker="dup2", identifier="co 5555 0000 1111")
        self.assertEqual(409, second.status_code, second.text)
        self.assertEqual(second.json()["type"].rsplit("/", 1)[-1],
                         "account-already-exists")
        self.assertNotIn("5555", second.text)

    def test_the_same_number_in_two_companies_is_two_accounts_TST_P35_027(self) -> None:
        # Sofia es owner en las dos empresas de la demo.
        here = self.new_account(marker="cross", identifier="CO-3333-2222-1111")
        there = self.new_account(marker="cross", company=ANDINOS,
                                 identifier="CO-3333-2222-1111")
        self.assertEqual(201, here.status_code, here.text)
        self.assertEqual(201, there.status_code, there.text)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                tokens = []
                for company, account in ((ESPIGA, here.json()["account_id"]),
                                         (ANDINOS, there.json()["account_id"])):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,))
                    cursor.execute(
                        "SELECT identifier_token FROM fincilia.financial_account "
                        "WHERE account_id = %s", (account,))
                    tokens.append(cursor.fetchone()[0])
        # Si coincidieran, comparar tokens revelaria que dos empresas comparten
        # una cuenta, que es una relacion que nadie autorizo a conocer.
        self.assertNotEqual(tokens[0], tokens[1])

    # ---------------------------------------------------------------- permisos

    def test_a_preparer_cannot_create_an_account_TST_P35_028(self) -> None:
        response = self.new_account(marker="perm", user=PREPARER)
        self.assertEqual(403, response.status_code, response.text)

    def test_an_auditor_reads_accounts_but_does_not_write_them_TST_P35_029(self) -> None:
        listing = self.client.get(f"/api/v1/companies/{ANDINOS}/accounts",
                                  headers=self.auth(AUDITOR))
        self.assertEqual(200, listing.status_code, listing.text)
        written = self.new_account(marker="aud", company=ANDINOS, user=AUDITOR)
        self.assertEqual(403, written.status_code, written.text)

    def test_a_preparer_cannot_create_a_source_TST_P35_030(self) -> None:
        self.assertEqual(403, self.new_source(marker="perm", user=PREPARER).status_code)

    # ---------------------------------------------------------------- validacion

    def test_an_unsupported_currency_is_refused_TST_P35_031(self) -> None:
        response = self.new_account(marker="cur", currency="ARS")
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "invalid-currency")

    def test_an_unsupported_timezone_is_refused_TST_P35_032(self) -> None:
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounts", headers=self.auth(OWNER),
            json={"account_family": "bank_account", "display_name": "Zona",
                  "identifier": f"CO-{RUN}-tz", "currency_code": "COP",
                  "timezone": "Marte/Olympus"})
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "invalid-timezone")

    def test_a_ledger_has_no_visible_tail_TST_P35_033(self) -> None:
        response = self.new_account(marker="ledger", family="accounting_ledger",
                                    identifier="LIBRO-000123")
        self.assertEqual(201, response.status_code, response.text)
        # Cuatro digitos de un codigo contable no ayudan a reconocer nada.
        self.assertIsNone(response.json()["identifier_last4"])

    # ------------------------------------------------------------------ estados

    def test_closing_an_account_needs_a_reason_TST_P35_034(self) -> None:
        account = self.new_account(marker="close").json()["account_id"]
        without = self.client.patch(
            f"/api/v1/companies/{ESPIGA}/accounts/{account}",
            headers=self.auth(OWNER), json={"status": "closed"})
        self.assertEqual(422, without.status_code, without.text)
        with_reason = self.client.patch(
            f"/api/v1/companies/{ESPIGA}/accounts/{account}",
            headers=self.auth(OWNER),
            json={"status": "closed", "closed_reason": "la cuenta se cancelo"})
        self.assertEqual(200, with_reason.status_code, with_reason.text)
        self.assertEqual(with_reason.json()["status"], "closed")

    def test_an_account_is_never_deleted_only_closed_TST_P35_035(self) -> None:
        # No hay verbo de borrado: la evidencia detras de una cuenta no puede
        # quedarse apuntando a algo que ya no existe.
        account = self.new_account(marker="nodel").json()["account_id"]
        response = self.client.delete(
            f"/api/v1/companies/{ESPIGA}/accounts/{account}",
            headers=self.auth(OWNER))
        self.assertIn(response.status_code, (404, 405))

    # ------------------------------------------------------------------ vinculos

    def test_a_source_links_to_several_accounts_with_typed_roles_TST_P35_036(self) -> None:
        source = self.new_source(marker="multi").json()["data_source_id"]
        bank = self.new_account(marker="multi-bank").json()["account_id"]
        ledger = self.new_account(marker="multi-ledger",
                                  family="accounting_ledger").json()["account_id"]
        for account, role in ((bank, "primary"), (ledger, "ledger")):
            with self.subTest(role=role):
                response = self.client.post(
                    f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
                    headers=self.auth(OWNER),
                    json={"financial_account_id": account, "relation_role": role})
                self.assertEqual(201, response.status_code, response.text)
        links = self.client.get(
            f"/api/v1/companies/{ESPIGA}/links?data_source_id={source}",
            headers=self.auth(PREPARER)).json()
        self.assertEqual({item["relation_role"] for item in links},
                         {"primary", "ledger"})

    def test_only_one_primary_account_is_live_at_a_time_TST_P35_037(self) -> None:
        source = self.new_source(marker="onep").json()["data_source_id"]
        first = self.new_account(marker="onep-a").json()["account_id"]
        second = self.new_account(marker="onep-b").json()["account_id"]
        self.assertEqual(201, self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": first,
                  "relation_role": "primary"}).status_code)
        clash = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": second, "relation_role": "primary"})
        self.assertEqual(409, clash.status_code, clash.text)
        self.assertEqual(clash.json()["type"].rsplit("/", 1)[-1], "primary-already-set")

    def test_an_account_of_another_company_cannot_be_linked_TST_P35_038(self) -> None:
        source = self.new_source(marker="tenant").json()["data_source_id"]
        foreign = self.new_account(marker="tenant-far",
                                   company=ANDINOS).json()["account_id"]
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": foreign, "relation_role": "settlement"})
        self.assertIn(response.status_code, (403, 422), response.text)

    def test_a_closed_account_takes_no_new_links_TST_P35_039(self) -> None:
        source = self.new_source(marker="closedlink").json()["data_source_id"]
        account = self.new_account(marker="closedlink").json()["account_id"]
        self.client.patch(f"/api/v1/companies/{ESPIGA}/accounts/{account}",
                          headers=self.auth(OWNER),
                          json={"status": "closed", "closed_reason": "cerrada"})
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": account, "relation_role": "primary"})
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "link-inactive")

    def test_retiring_a_link_frees_the_primary_slot_TST_P35_040(self) -> None:
        source = self.new_source(marker="retire").json()["data_source_id"]
        first = self.new_account(marker="retire-a").json()["account_id"]
        second = self.new_account(marker="retire-b").json()["account_id"]
        link = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": first, "relation_role": "primary"}).json()
        retired = self.client.patch(
            f"/api/v1/companies/{ESPIGA}/links/{link['link_id']}",
            headers=self.auth(OWNER), json={"status": "closed"})
        self.assertEqual(200, retired.status_code, retired.text)
        self.assertIsNotNone(retired.json()["valid_to"])
        # El vinculo retirado sigue existiendo: dejo de valer, no dejo de estar.
        links = self.client.get(
            f"/api/v1/companies/{ESPIGA}/links?data_source_id={source}",
            headers=self.auth(PREPARER)).json()
        self.assertEqual(len(links), 1)
        self.assertEqual(201, self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": second,
                  "relation_role": "primary"}).status_code)

    # -------------------------------------------------------- ciclos esperados

    def test_a_cycle_generates_periods_with_due_and_late_dates_TST_P35_041(self) -> None:
        source = self.new_source(marker="cycle").json()["data_source_id"]
        cycle = self.client.put(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/cycle",
            headers=self.auth(OWNER),
            json={"periodicity": "monthly", "due_day_offset": 5, "grace_days": 3,
                  "responsible_subject_id": stable_id("subject", "ana"),
                  "timezone": "America/Bogota", "anchor_date": "2026-01-01"})
        self.assertEqual(200, cycle.status_code, cycle.text)
        generated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/expectations",
            headers=self.auth(OWNER), json={"until": "2026-03-31"})
        self.assertEqual(201, generated.status_code, generated.text)
        self.assertEqual(generated.json()["periods"], 3)
        self.assertEqual(generated.json()["created"], 3)

        expectations = self.client.get(
            f"/api/v1/companies/{ESPIGA}/expectations?data_source_id={source}",
            headers=self.auth(PREPARER)).json()
        january = [item for item in expectations
                   if item["period_start"] == "2026-01-01"][0]
        self.assertEqual(january["period_end"], "2026-01-31")
        self.assertEqual(january["due_on"], "2026-02-05")
        self.assertEqual(january["late_after"], "2026-02-08")

    def test_generating_the_same_horizon_twice_creates_nothing_TST_P35_042(self) -> None:
        source = self.new_source(marker="idem").json()["data_source_id"]
        self.client.put(f"/api/v1/companies/{ESPIGA}/sources/{source}/cycle",
                        headers=self.auth(OWNER),
                        json={"periodicity": "weekly", "due_day_offset": 2,
                              "grace_days": 1,
                              "responsible_subject_id": stable_id("subject", "ana"),
                              "timezone": "America/Bogota",
                              "anchor_date": "2026-01-05"})
        first = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/expectations",
            headers=self.auth(OWNER), json={"until": "2026-02-02"}).json()
        second = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/expectations",
            headers=self.auth(OWNER), json={"until": "2026-02-02"}).json()
        self.assertEqual(first["periods"], second["periods"])
        self.assertEqual(second["created"], 0)

    def test_a_past_period_reads_as_late_with_its_day_count_TST_P35_043(self) -> None:
        source = self.new_source(marker="late").json()["data_source_id"]
        long_ago = date.today() - timedelta(days=200)
        self.client.put(f"/api/v1/companies/{ESPIGA}/sources/{source}/cycle",
                        headers=self.auth(OWNER),
                        json={"periodicity": "monthly", "due_day_offset": 5,
                              "grace_days": 3,
                              "responsible_subject_id": stable_id("subject", "ana"),
                              "timezone": "America/Bogota",
                              "anchor_date": long_ago.replace(day=1).isoformat()})
        self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/expectations",
            headers=self.auth(OWNER),
            json={"until": (long_ago + timedelta(days=40)).isoformat()})
        expectations = self.client.get(
            f"/api/v1/companies/{ESPIGA}/expectations?data_source_id={source}",
            headers=self.auth(PREPARER)).json()
        self.assertTrue(expectations)
        overdue = [item for item in expectations if item["state"] == "late"]
        self.assertTrue(overdue, expectations)
        self.assertGreater(overdue[0]["days_late"], 0)
        # El estado guardado sigue siendo `pending`: se calcula al leer, no lo
        # marca un proceso nocturno que algun dia no correra.
        self.assertEqual(overdue[0]["stored_state"], "pending")

    def test_a_cycle_without_a_day_count_is_refused_TST_P35_044(self) -> None:
        source = self.new_source(marker="badcycle").json()["data_source_id"]
        response = self.client.put(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/cycle",
            headers=self.auth(OWNER),
            json={"periodicity": "custom",
                  "responsible_subject_id": stable_id("subject", "ana"),
                  "timezone": "America/Bogota", "anchor_date": "2026-01-01"})
        self.assertEqual(422, response.status_code, response.text)

    def test_expectations_need_a_cycle_first_TST_P35_045(self) -> None:
        source = self.new_source(marker="nocycle").json()["data_source_id"]
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/expectations",
            headers=self.auth(OWNER), json={"until": "2026-06-30"})
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1], "cycle-missing")

    # ---------------------------------------------------------------- aislamiento

    def test_an_account_of_another_company_is_not_readable_TST_P35_046(self) -> None:
        foreign = self.new_account(marker="iso", company=ANDINOS).json()["account_id"]
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/accounts/{foreign}",
            headers=self.auth(OWNER))
        self.assertEqual(403, response.status_code, response.text)
        invented = self.client.get(
            f"/api/v1/companies/{ESPIGA}/accounts/{uuid.uuid4()}",
            headers=self.auth(OWNER))
        # Indistinguible de que no exista.
        self.assertEqual(invented.status_code, response.status_code)
        self.assertEqual(invented.json()["detail"], response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
