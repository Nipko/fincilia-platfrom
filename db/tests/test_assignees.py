"""Quien puede responder de un ciclo, contra PostgreSQL real.

La propiedad que sostiene todo: la elegibilidad se resuelve con **las mismas tres
condiciones** que usa el autorizador para dejar entrar. Dos definiciones de
«quien puede» acaban discrepando, y la que discrepa siempre es la que nadie
mira.

Y la segunda: se resuelve contra la base en cada peticion. Cachearla haria que
revocar a alguien tardara en notarse lo que tarde una entrada en caducar, y
durante ese rato la cache seria la autoridad.

    docker compose -f infra/local/compose.yaml -p fincilia-local \\
      --profile migrate run --rm migrate \\
      python -m unittest db.tests.test_assignees -v
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

OWNER = "sofia@demo.local"       # data_source.manage en las dos empresas
PREPARER = "ana@demo.local"      # no lo tiene
REVIEWER = "beto@demo.local"
AUDITOR = "carla@demo.local"

ANA = stable_id("subject", "ana")
BETO = stable_id("subject", "beto")
SOFIA = stable_id("subject", "sofia")
PROVISIONER = stable_id("subject", "provisioner")


class AssigneeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()
        cls.sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if not cls.sources:
            return
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for company in (ESPIGA, ANDINOS):
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (company,))
                    cursor.execute("DELETE FROM fincilia.source_expectation "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))
                    cursor.execute("DELETE FROM fincilia.source_cycle "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))
                    cursor.execute("DELETE FROM fincilia.data_source_account "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))
                    cursor.execute("DELETE FROM fincilia.data_source "
                                   "WHERE data_source_id = ANY(%s)",
                                   (list(cls.sources),))

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session",
                                    json={"username": username,
                                          "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def assignees(self, company: str = ESPIGA, user: str = OWNER):
        return self.client.get(f"/api/v1/companies/{company}/assignees",
                               headers=self.auth(user))

    def new_source(self, marker: str, company: str = ESPIGA) -> str:
        response = self.client.post(
            f"/api/v1/companies/{company}/sources", headers=self.auth(OWNER),
            json={"source_family": "bank_account",
                  "display_name": f"Fuente {marker} {RUN}",
                  "purpose_code": "operational", "timezone": "America/Bogota"})
        self.assertEqual(201, response.status_code, response.text)
        source = response.json()["data_source_id"]
        type(self).sources.add(source)
        return source

    def set_cycle(self, source: str, responsible: str, company: str = ESPIGA):
        return self.client.put(
            f"/api/v1/companies/{company}/sources/{source}/cycle",
            headers=self.auth(OWNER),
            json={"periodicity": "monthly", "due_day_offset": 5, "grace_days": 3,
                  "responsible_subject_id": responsible,
                  "timezone": "America/Bogota", "anchor_date": "2026-01-01"})

    # ------------------------------------------------------------- elegibilidad

    def test_the_list_has_everyone_with_a_live_grant_TST_P36_003(self) -> None:
        response = self.assignees()
        self.assertEqual(200, response.status_code, response.text)
        found = {item["subject_id"] for item in response.json()}
        # En Espiga la semilla concede a Sofia, Ana y Beto.
        self.assertEqual(found, {SOFIA, ANA, BETO})

    def test_a_service_principal_is_never_a_candidate_TST_P36_004(self) -> None:
        # El aprovisionador concede roles; no responde de que llegue un extracto.
        found = {item["subject_id"] for item in self.assignees().json()}
        self.assertNotIn(PROVISIONER, found)

    def test_the_list_carries_no_contact_detail_TST_P36_005(self) -> None:
        # Un selector de responsables no es un directorio de personas.
        people = self.assignees().json()
        self.assertTrue(people)
        for person in people:
            with self.subTest(person=person["display_name"]):
                self.assertEqual(set(person),
                                 {"subject_id", "display_name", "company_roles"})
        rendered = str(people)
        for leak in ("@demo.local", "secret_hash", "identity_binding", "firm_id"):
            self.assertNotIn(leak, rendered)

    def test_the_roles_are_the_ones_in_this_company_TST_P36_006(self) -> None:
        by_subject = {item["subject_id"]: item for item in self.assignees().json()}
        self.assertEqual(by_subject[ANA]["company_roles"], ["preparer"])
        self.assertEqual(by_subject[BETO]["company_roles"], ["reviewer"])
        # Carla es auditora en Andinos y **no** tiene nada en Espiga: no aparece.
        self.assertNotIn(stable_id("subject", "carla"), by_subject)

    def test_another_company_has_its_own_candidates_TST_P36_007(self) -> None:
        found = {item["subject_id"] for item in self.assignees(company=ANDINOS).json()}
        self.assertIn(stable_id("subject", "carla"), found)
        self.assertNotIn(BETO, found)

    # ------------------------------------------------------------------ permisos

    def test_listing_candidates_needs_the_permission_to_assign_TST_P36_008(self) -> None:
        # Es la lectura de quien va a asignar una tarea, no un `company.read`.
        for user in (PREPARER, REVIEWER, AUDITOR):
            with self.subTest(user=user):
                self.assertEqual(403, self.assignees(user=user).status_code)

    def test_listing_candidates_leaves_a_trail_without_naming_them_TST_P36_009(self) -> None:
        self.assignees()
        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=25",
                                 headers=self.auth(REVIEWER)).json()
        listed = [event for event in events if event["action"] == "assignee.list"]
        self.assertTrue(listed, "listing candidates left no trail")
        self.assertGreaterEqual(listed[0]["detail"]["candidates"], 3)
        # El actor que consulta si es un dato legitimo del evento. La propiedad
        # de privacidad es que el payload no copie la lista de candidatos.
        self.assertEqual("Sofia Owner", listed[0]["actor_name"])
        rendered = str(listed[0]["detail"])
        for name in ("Ana", "Beto", "Sofia"):
            self.assertNotIn(name, rendered)

    # ------------------------------------------------------------- asignacion

    def test_a_cycle_can_name_any_eligible_person_TST_P36_010(self) -> None:
        source = self.new_source("elegible")
        response = self.set_cycle(source, ANA)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(response.json()["responsible_subject_id"], ANA)

    def test_naming_a_responsible_leaves_a_trail_with_the_opaque_id_TST_P36_042(self) -> None:
        """Quien queda como responsable es el hecho que importa de la llamada.

        Se registra por su identificador opaco: el nombre no anade nada que el
        `subject_id` no resuelva, y si anade una copia de un dato personal donde
        no toca.
        """
        source = self.new_source("rastro")
        self.assertEqual(200, self.set_cycle(source, ANA).status_code)
        events = self.client.get(f"/api/v1/companies/{ESPIGA}/audit?limit=25",
                                 headers=self.auth(REVIEWER)).json()
        assigned = [event for event in events if event["action"] == "source.cycle"]
        self.assertTrue(assigned, "naming a responsible left no trail")
        self.assertEqual(ANA, assigned[0]["detail"]["responsible"])
        # Sofia ejecuta la asignacion y debe seguir visible como actor. Lo que no
        # puede duplicar nombres/contactos es el detalle financiero-operativo.
        self.assertEqual("Sofia Owner", assigned[0]["actor_name"])
        rendered = str(assigned[0]["detail"])
        for name in ("Ana", "Beto", "Sofia", "@demo.local"):
            self.assertNotIn(name, rendered)

    def test_a_cycle_cannot_name_someone_from_another_company_TST_P36_011(self) -> None:
        # Carla no tiene concesion en Espiga. Asignarla seria darle una tarea en
        # una empresa a la que no puede entrar.
        source = self.new_source("ajena")
        response = self.set_cycle(source, stable_id("subject", "carla"))
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(response.json()["type"].rsplit("/", 1)[-1],
                         "assignee-not-eligible")

    def test_a_cycle_cannot_name_a_service_principal_TST_P36_012(self) -> None:
        source = self.new_source("servicio")
        response = self.set_cycle(source, PROVISIONER)
        self.assertEqual(422, response.status_code, response.text)

    def test_a_cycle_cannot_name_someone_who_does_not_exist_TST_P36_013(self) -> None:
        source = self.new_source("inventado")
        response = self.set_cycle(source, str(uuid.uuid4()))
        self.assertEqual(422, response.status_code, response.text)

    def test_revoking_someone_keeps_the_cycle_and_flags_it_TST_P36_014(self) -> None:
        # Revocar no borra el calendario: la fuente se quedaria sin el justo el
        # dia que alguien se fue. Lo que cambia es que queda pendiente de
        # reemplazo, y la interfaz lo dice.
        source = self.new_source("revocado")
        self.assertEqual(200, self.set_cycle(source, BETO).status_code)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "UPDATE fincilia.company_grant SET revoked_at = now() "
                    "WHERE company_id = %s AND subject_id = %s", (ESPIGA, BETO))
        try:
            detail = self.client.get(
                f"/api/v1/companies/{ESPIGA}/sources/{source}",
                headers=self.auth(OWNER)).json()
            self.assertIsNotNone(detail["cycle"])
            self.assertEqual(detail["cycle"]["responsible_subject_id"], BETO)
            self.assertFalse(detail["cycle"]["responsible_eligible"])
            # Y ya no es candidato para una asignacion nueva.
            found = {item["subject_id"] for item in self.assignees().json()}
            self.assertNotIn(BETO, found)
            self.assertEqual(422, self.set_cycle(source, BETO).status_code)
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    cursor.execute(
                        "UPDATE fincilia.company_grant SET revoked_at = NULL "
                        "WHERE company_id = %s AND subject_id = %s", (ESPIGA, BETO))

    def test_transferring_the_engagement_changes_who_is_eligible_TST_P36_015(self) -> None:
        # La membresia se une a la firma **del engagement**. Si la empresa cambia
        # de firma, los miembros de la anterior dejan de valer el mismo dia, sin
        # que nadie tenga que acordarse de limpiar nada.
        other_firm = str(uuid.uuid4())
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fincilia.firm (firm_id, legal_name) "
                    "VALUES (%s, %s)", (other_firm, f"Otra Firma {RUN}"))
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "UPDATE fincilia.engagement SET firm_id = %s "
                    "WHERE company_id = %s", (other_firm, ESPIGA))
        try:
            # Nadie de la firma anterior sigue siendo elegible: su membresia es
            # de otra firma.
            self.assertEqual(self.assignees(user=OWNER).status_code, 403,
                             "the owner lost access with the engagement, as it should")
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    cursor.execute(
                        "UPDATE fincilia.engagement SET firm_id = %s "
                        "WHERE company_id = %s",
                        (stable_id("firm", "andes"), ESPIGA))
                    cursor.execute("DELETE FROM fincilia.firm WHERE firm_id = %s",
                                   (other_firm,))

    def test_an_expired_engagement_removes_every_candidate_TST_P36_016(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ANDINOS,))
                cursor.execute(
                    "UPDATE fincilia.engagement SET valid_to = %s "
                    "WHERE company_id = %s",
                    (date.today() - timedelta(days=1), ANDINOS))
        try:
            self.assertEqual(403, self.assignees(company=ANDINOS).status_code)
        finally:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ANDINOS,))
                    cursor.execute(
                        "UPDATE fincilia.engagement SET valid_to = NULL "
                        "WHERE company_id = %s", (ANDINOS,))

    def test_eligibility_is_never_read_from_the_cache_TST_P36_017(self) -> None:
        # Si Valkey fuera autoridad, revocar tardaria en notarse lo que tarde una
        # entrada en caducar. Se lee el fuente: la ruta no toca la cache.
        from pathlib import Path
        source = Path("/app/src/fincilia_api/onboarding.py").read_text(encoding="utf-8")
        block = source[source.index("def eligible_assignees"):]
        for cache in ("valkey", "redis", "cache", "throttle"):
            self.assertNotIn(cache, block.lower().split("def is_eligible")[0])


if __name__ == "__main__":
    unittest.main()
