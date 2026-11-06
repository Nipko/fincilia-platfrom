"""FNC-SMB-001 contra PostgreSQL real: perfil operativo y modo de revision.

ADR-039 secciones 1 a 3. Cada clase deja ESPIGA y ANDINOS en `estricto` al
terminar, porque el resto de suites prueba la segregacion historica. El cambio
de perfil es append-only: las filas de historial que dejan estas pruebas son la
traza correcta de lo que ocurrio, no residuos que haya que borrar.

Solo datos sinteticos.
"""

from __future__ import annotations

import datetime as dt
import json
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests import test_balance_reconciliation_statements as balance_tests
from db.tests import test_field_overlays as overlay_tests
from db.tests import test_reconciliation_candidates as rec
from db.tests import test_row_overrides as override_tests
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN, build_settings
from db.tests.test_p3_vertical import (
    ACCOUNT,
    ANDINOS,
    ESPIGA,
    OWNER,
    PREPARER,
    REVIEWER,
    statement_csv,
)
from fincilia_api.main import create_app


OWNER_ID = stable_id("subject", "sofia")
PREPARER_ID = stable_id("subject", "ana")
REVIEWER_ID = stable_id("subject", "beto")
REASON = "Prueba sintetica FNC-SMB-001 del perfil operativo"


def slug(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


def stored_profile(company_id: str) -> str:
    with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                           (company_id,))
            cursor.execute("SELECT operating_profile FROM fincilia.company "
                           "WHERE company_id = %s", (company_id,))
            return str(cursor.fetchone()[0])


def force_profile(company_id: str, profile: str) -> None:
    """Red de seguridad: devuelve la empresa al perfil pedido por la via legal.

    Usa el rol runtime y una fila de historial firmada por el owner sintetico;
    nunca desactiva una guarda ni escribe la columna directamente.
    """
    if not MIGRATOR_DSN or not RUNTIME_DSN:
        return
    if stored_profile(company_id) == profile:
        return
    with psycopg.connect(RUNTIME_DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                           (company_id,))
            cursor.execute("SELECT operating_profile FROM fincilia.company "
                           "WHERE company_id = %s", (company_id,))
            current = str(cursor.fetchone()[0])
            cursor.execute(
                "SELECT COALESCE(max(version), 0) + 1 "
                "FROM fincilia.company_operating_profile_change WHERE company_id = %s",
                (company_id,))
            version = int(cursor.fetchone()[0])
            audit_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "subject_id, action, resource_kind, resource_ref, outcome) "
                "VALUES (%s, %s, %s, 'company.operating_profile.change', "
                "'company', %s, 'allowed')",
                (audit_id, company_id, OWNER_ID, company_id))
            cursor.execute(
                "INSERT INTO fincilia.company_operating_profile_change "
                "(company_id, version, from_profile, to_profile, reason, "
                " changed_by, audit_event_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (company_id, version, current, profile, REASON, OWNER_ID, audit_id))


def tearDownModule() -> None:  # noqa: N802 - nombre de unittest
    for company in (ESPIGA, ANDINOS):
        force_profile(company, "estricto")


class ProfileSwitch:
    """Cambia el perfil por la API, como lo haria el owner."""

    def switch(self, profile: str, *, company: str = ESPIGA, user: str = OWNER):
        response = self.client.put(
            f"/api/v1/companies/{company}/operating-profile",
            headers=self.auth(user),
            json={"operating_profile": profile, "reason": REASON})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(profile, response.json()["operating_profile"])
        return response.json()


def _without_inherited_tests(cls: type) -> type:
    """Hereda el montaje de otra suite sin volver a ejecutar sus pruebas."""
    for name in dir(cls):
        if name.startswith("test") and not name.startswith("test_smb"):
            setattr(cls, name, None)
    return cls


# --------------------------------------------------------------------------- #
# 1. Perfil: owner, historial append-only y aislamiento
# --------------------------------------------------------------------------- #

class OperatingProfileLedgerTests(ProfileSwitch, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls.client = TestClient(create_app(build_settings()))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        for company in (ESPIGA, ANDINOS):
            force_profile(company, "estricto")

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/session", json={
            "username": username, "secret": DEFAULT_SECRET})
        self.assertEqual(200, response.status_code, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_smb_existing_companies_stay_strict_and_expose_profile(self) -> None:
        for company in (ESPIGA, ANDINOS):
            self.assertEqual("estricto", stored_profile(company))
        detail = self.client.get(f"/api/v1/companies/{ESPIGA}",
                                 headers=self.auth(OWNER))
        self.assertEqual(200, detail.status_code, detail.text)
        self.assertEqual("estricto", detail.json()["operating_profile"])
        owner_view = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operating-profile", headers=self.auth(OWNER))
        self.assertEqual(200, owner_view.status_code, owner_view.text)
        self.assertEqual("estricto", owner_view.json()["operating_profile"])
        self.assertTrue(owner_view.json()["can_change"])
        reviewer_view = self.client.get(
            f"/api/v1/companies/{ESPIGA}/operating-profile",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, reviewer_view.status_code, reviewer_view.text)
        self.assertFalse(reviewer_view.json()["can_change"])

    def test_smb_only_the_owner_changes_the_profile(self) -> None:
        for user in (REVIEWER, PREPARER):
            refused = self.client.put(
                f"/api/v1/companies/{ESPIGA}/operating-profile",
                headers=self.auth(user),
                json={"operating_profile": "simple", "reason": REASON})
            self.assertEqual(403, refused.status_code, refused.text)
            self.assertEqual("operating-profile-owner-required", slug(refused))
        missing_reason = self.client.put(
            f"/api/v1/companies/{ESPIGA}/operating-profile",
            headers=self.auth(OWNER),
            json={"operating_profile": "simple", "reason": "corto"})
        self.assertEqual(422, missing_reason.status_code, missing_reason.text)
        self.assertEqual("estricto", stored_profile(ESPIGA))

        # La base no confia en la API: un no-owner tampoco puede por SQL, y un
        # UPDATE directo de la columna no pasa sin su fila de historial.
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                audit_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "subject_id, action, resource_kind, resource_ref, outcome) "
                    "VALUES (%s, %s, %s, 'company.operating_profile.change', "
                    "'company', %s, 'allowed')",
                    (audit_id, ESPIGA, REVIEWER_ID, ESPIGA))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "INSERT INTO fincilia.company_operating_profile_change "
                        "(company_id, version, from_profile, to_profile, reason, "
                        " changed_by, audit_event_id) "
                        "VALUES (%s, 1, 'estricto', 'simple', %s, %s, %s)",
                        (ESPIGA, REASON, REVIEWER_ID, audit_id))
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.company SET operating_profile = 'simple' "
                        "WHERE company_id = %s", (ESPIGA,))
        self.assertEqual("estricto", stored_profile(ESPIGA))

    def test_smb_profile_history_is_append_only_audited_and_isolated(self) -> None:
        try:
            changed = self.switch("simple", company=ANDINOS)
            self.assertTrue(changed["changed"])
            latest = changed["history"][0]
            self.assertEqual(("estricto", "simple"),
                             (latest["from_profile"], latest["to_profile"]))
            self.assertEqual(OWNER_ID, latest["changed_by"])
            unchanged = self.switch("simple", company=ANDINOS)
            self.assertFalse(unchanged["changed"])
            self.assertEqual("estricto", stored_profile(ESPIGA))

            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)", (ANDINOS,))
                    cursor.execute(
                        "SELECT audit_event_id FROM fincilia.company_operating_profile_change "
                        "WHERE change_id = %s", (latest["change_id"],))
                    audit_id = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT action, subject_id, detail FROM fincilia.audit_event "
                        "WHERE audit_event_id = %s", (audit_id,))
                    action, subject, detail = cursor.fetchone()
                    self.assertEqual("company.operating_profile.change", action)
                    self.assertEqual(OWNER_ID, str(subject))
                    self.assertEqual("simple", detail["to_profile"])
                    # Append-only aun para el dueno del esquema.
                    with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                        cursor.execute(
                            "UPDATE fincilia.company_operating_profile_change "
                            "SET reason = %s WHERE change_id = %s",
                            ("Motivo reescrito sintetico", latest["change_id"]))
                    with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                        cursor.execute(
                            "DELETE FROM fincilia.company_operating_profile_change "
                            "WHERE change_id = %s", (latest["change_id"],))

            with psycopg.connect(RUNTIME_DSN) as connection:
                with connection.cursor() as cursor:
                    # Otra empresa no ve la fila.
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                    cursor.execute(
                        "SELECT count(*) FROM fincilia.company_operating_profile_change "
                        "WHERE change_id = %s", (latest["change_id"],))
                    self.assertEqual(0, cursor.fetchone()[0])
                    # Ni puede escribir en ella con su propio contexto: la empresa
                    # ajena es invisible para la guarda y la politica la rechaza.
                    with self.assertRaises((psycopg.errors.InsufficientPrivilege,
                                            psycopg.errors.ForeignKeyViolation)):
                        cursor.execute(
                            "INSERT INTO fincilia.company_operating_profile_change "
                            "(company_id, version, from_profile, to_profile, reason, "
                            " changed_by, audit_event_id) VALUES "
                            "(%s, 99, 'simple', 'estricto', %s, %s, %s)",
                            (ANDINOS, REASON, OWNER_ID, audit_id))
                connection.rollback()
                with connection.cursor() as cursor:
                    # Un cambio que no parte del perfil vigente se rechaza.
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)", (ANDINOS,))
                    stale_audit = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                        "subject_id, action, resource_kind, resource_ref, outcome) "
                        "VALUES (%s, %s, %s, 'company.operating_profile.change', "
                        "'company', %s, 'allowed')",
                        (stale_audit, ANDINOS, OWNER_ID, ANDINOS))
                    cursor.execute(
                        "SELECT COALESCE(max(version), 0) + 1 FROM "
                        "fincilia.company_operating_profile_change WHERE company_id = %s",
                        (ANDINOS,))
                    version = int(cursor.fetchone()[0])
                    with self.assertRaises(psycopg.errors.CheckViolation):
                        cursor.execute(
                            "INSERT INTO fincilia.company_operating_profile_change "
                            "(company_id, version, from_profile, to_profile, reason, "
                            " changed_by, audit_event_id) VALUES "
                            "(%s, %s, 'estricto', 'simple', %s, %s, %s)",
                            (ANDINOS, version, REASON, OWNER_ID, stale_audit))
                connection.rollback()
        finally:
            self.switch("estricto", company=ANDINOS)
        self.assertEqual("estricto", stored_profile(ANDINOS))


# --------------------------------------------------------------------------- #
# 2. Cruces 1:1
# --------------------------------------------------------------------------- #

@_without_inherited_tests
class SimpleProfileMatchDecisionTests(ProfileSwitch, rec.ReconciliationCandidateTests):
    # Conjuntos propios: los de la clase base son compartidos y su limpieza
    # intentaria borrar fuentes que este ledger append-only sigue referenciando.
    accounts: set[str] = set()
    sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        # El ledger es append-only y referencia movimientos con RESTRICT, igual
        # que en test_reconciliation_decisions: esta base es desechable.
        cls.client.__exit__(None, None, None)
        force_profile(ESPIGA, "estricto")

    def _candidates(self):
        source, account = self.second_channel()
        marker = uuid.uuid4().hex[:8]
        left = self.dataset([
            ("13/02/2026", "Pago sintetico A", f"REF-SMB-A-{marker}", "-1.234,56"),
            ("14/02/2026", "Pago sintetico B", f"REF-SMB-B-{marker}", "-500,00"),
            ("15/02/2026", "Pago sintetico C", f"REF-SMB-C-{marker}", "-750,00"),
        ], marker=f"smb-left-{marker}", source=rec.SOURCE, account=rec.ACCOUNT)
        right = self.dataset([
            ("14/02/2026", "Abono sintetico A", f"REF-SMB-A-{marker}", "1.234,56"),
            ("15/02/2026", "Abono sintetico B", f"REF-SMB-B-{marker}", "500,00"),
            ("16/02/2026", "Abono sintetico C", f"REF-SMB-C-{marker}", "750,00"),
        ], marker=f"smb-right-{marker}", source=source, account=account)
        query = {"left_dataset_id": left, "right_dataset_id": right,
                 "max_days": 3, "limit": 20}
        explored = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/candidates",
            headers=self.auth(PREPARER), params=query)
        self.assertEqual(200, explored.status_code, explored.text)
        pairs = explored.json()["candidates"]
        self.assertEqual(3, len(pairs))
        query.pop("limit")
        return query, pairs

    def _propose(self, query, pair, user):
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews",
            headers={**self.auth(user),
                     "Idempotency-Key": f"smb001-propose-{uuid.uuid4().hex}"},
            json={**query, "left_movement_id": pair["left"]["movement_id"],
                  "right_movement_id": pair["right"]["movement_id"]})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["candidate_id"]

    def _confirm(self, candidate_id, user):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews/{candidate_id}/decision",
            headers={**self.auth(user),
                     "Idempotency-Key": f"smb001-confirm-{uuid.uuid4().hex}"},
            json={"decision": "confirmed", "reason_code": "documented_counterpart"})

    def test_smb_self_confirmation_follows_the_company_profile(self) -> None:
        query, (first, second, third) = self._candidates()
        own = self._propose(query, first, OWNER)

        strict_refusal = self._confirm(own, OWNER)
        self.assertEqual(409, strict_refusal.status_code, strict_refusal.text)
        self.assertEqual("segregation-of-duties", slug(strict_refusal))

        try:
            self.switch("simple")
            self_confirmed = self._confirm(own, OWNER)
            self.assertEqual(200, self_confirmed.status_code, self_confirmed.text)
            self.assertEqual("self_reviewed",
                             self_confirmed.json()["decision"]["review_mode"])

            other = self._propose(query, second, PREPARER)
            independent = self._confirm(other, OWNER)
            self.assertEqual(200, independent.status_code, independent.text)
            self.assertEqual("independent",
                             independent.json()["decision"]["review_mode"])

            third_candidate = self._propose(query, third, OWNER)
            with psycopg.connect(MIGRATOR_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                                   (ESPIGA,))
                    # `approved_rule` esta reservado: nadie lo escribe todavia.
                    audit_id = self._audit(cursor)
                    with self.assertRaises(psycopg.errors.CheckViolation):
                        self._insert_decision(cursor, third_candidate, third,
                                              audit_id, "approved_rule")
                connection.rollback()
        finally:
            self.switch("estricto")

        # De vuelta en estricto, ni forzando el modo por SQL se autoconfirma.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                audit_id = self._audit(cursor)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    self._insert_decision(cursor, third_candidate, third, audit_id,
                                          "self_reviewed")
            connection.rollback()
        # La decision previa conserva su modo: cambiar de perfil no reescribe nada.
        kept = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews/{own}",
            headers=self.auth(OWNER))
        self.assertEqual(200, kept.status_code, kept.text)
        self.assertEqual("self_reviewed", kept.json()["decision"]["review_mode"])

    @staticmethod
    def _audit(cursor) -> str:
        audit_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO fincilia.audit_event (audit_event_id, company_id, subject_id, "
            "action, resource_kind, resource_ref, outcome) VALUES "
            "(%s, %s, %s, 'match.confirm', 'match_candidate', 'smb001', 'allowed')",
            (audit_id, ESPIGA, OWNER_ID))
        return audit_id

    @staticmethod
    def _insert_decision(cursor, candidate_id, pair, audit_id, mode) -> None:
        # La evidencia debe nombrar el par en el orden guardado por el candidato.
        del pair
        cursor.execute(
            "SELECT left_movement_id, right_movement_id FROM fincilia.match_candidate "
            "WHERE candidate_id = %s", (candidate_id,))
        left, right = (str(value) for value in cursor.fetchone())
        cursor.execute(
            "INSERT INTO fincilia.match_decision (company_id, candidate_id, decision, "
            "reason_code, evidence_refs, decided_by, audit_event_id, review_mode) "
            "VALUES (%s, %s, 'confirmed', 'documented_counterpart', %s::jsonb, %s, %s, %s)",
            (ESPIGA, candidate_id, json.dumps([
                {"kind": "movement", "ref": left},
                {"kind": "movement", "ref": right}]), OWNER_ID, audit_id, mode))


# --------------------------------------------------------------------------- #
# 3. Correcciones tipadas
# --------------------------------------------------------------------------- #

@_without_inherited_tests
class SimpleProfileCorrectionTests(ProfileSwitch, overlay_tests.FieldOverlayTests):
    @classmethod
    def tearDownClass(cls) -> None:
        force_profile(ESPIGA, "estricto")
        super().tearDownClass()

    def test_smb_author_reviews_own_correction_only_in_simple(self) -> None:
        dataset, movement, _ = self.dataset(f"smb-correction-{uuid.uuid4().hex[:6]}")
        created = self.propose(dataset, movement["movement_id"], "occurred_on",
                               "2026-03-02", user=OWNER)
        self.assertEqual(201, created.status_code, created.text)
        overlay_id = created.json()["overlay_id"]
        review_url = f"/api/v1/companies/{ESPIGA}/corrections/{overlay_id}/review"

        strict = self.client.post(review_url, headers=self.auth(OWNER), json={
            "decision": "approved", "rationale": "autorrevision sintetica"})
        self.assertEqual(409, strict.status_code, strict.text)
        self.assertEqual("segregation-of-duties", slug(strict))
        try:
            self.switch("simple")
            simple = self.client.post(review_url, headers=self.auth(OWNER), json={
                "decision": "approved", "rationale": "autorrevision sintetica"})
            self.assertEqual(200, simple.status_code, simple.text)
            self.assertEqual("self_reviewed", simple.json()["review_mode"])
        finally:
            self.switch("estricto")

        second = self.propose(dataset, movement["movement_id"], "amount", "2000.25")
        self.assertEqual(201, second.status_code, second.text)
        independent = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{second.json()['overlay_id']}/review",
            headers=self.auth(REVIEWER),
            json={"decision": "rejected", "rationale": "revision independiente"})
        self.assertEqual(200, independent.status_code, independent.text)
        self.assertEqual("independent", independent.json()["review_mode"])
        listed = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(REVIEWER))
        modes = {item["overlay_id"]: item["review_mode"] for item in listed.json()}
        self.assertEqual("self_reviewed", modes[overlay_id])


# --------------------------------------------------------------------------- #
# 4. Overrides por fila y publicacion de dataset
# --------------------------------------------------------------------------- #

@_without_inherited_tests
class SimpleProfileOverrideAndPublicationTests(ProfileSwitch,
                                               override_tests.OverrideHarness):
    @classmethod
    def tearDownClass(cls) -> None:
        force_profile(ESPIGA, "estricto")
        super().tearDownClass()

    def test_smb_override_self_approval_follows_profile(self) -> None:
        dataset_id, record_id, published = self.dataset_with_a_row(
            f"smb-ovr-{uuid.uuid4().hex[:6]}")
        created = self.override(dataset_id, record_id, user=OWNER,
                                resulting_value_digest=published)
        self.assertEqual(201, created.status_code, created.text)
        override_id = created.json()["override_id"]
        strict = self.approve(override_id, user=OWNER)
        self.assertEqual(409, strict.status_code, strict.text)
        self.assertEqual("segregation-of-duties", slug(strict))

        # Forzar `self_reviewed` por SQL en estricto choca con el mismo CHECK.
        with override_tests.as_migrator() as cursor:
            with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                cursor.execute(
                    "UPDATE fincilia.lineage_row_override "
                    "SET approved_by = created_by, approved_at = now(), "
                    "    review_mode = 'self_reviewed' WHERE override_id = %s",
                    (override_id,))
            self.assertEqual("ck_override_segregation",
                             raised.exception.diag.constraint_name)
        try:
            self.switch("simple")
            approved = self.approve(override_id, user=OWNER)
            self.assertEqual(200, approved.status_code, approved.text)
        finally:
            self.switch("estricto")
        with override_tests.as_migrator() as cursor:
            cursor.execute("SELECT review_mode, approved_by FROM "
                           "fincilia.lineage_row_override WHERE override_id = %s",
                           (override_id,))
            mode, approver = cursor.fetchone()
        self.assertEqual(("self_reviewed", OWNER_ID), (mode, str(approver)))

    def test_smb_dataset_self_publication_follows_profile(self) -> None:
        artifact = self.promoted(statement_csv(f"smb-pub-{uuid.uuid4().hex[:8]}"),
                                 f"smb-publicacion-{uuid.uuid4().hex[:6]}.csv")
        mapping = self.validated_mapping(artifact)
        prepared = self.prepared(artifact, mapping, user=OWNER)
        self.assertIn(prepared.status_code, (200, 201), prepared.text)
        dataset_id = prepared.json()["dataset_version_id"]
        strict = self.publish(dataset_id, user=OWNER)
        self.assertEqual(409, strict.status_code, strict.text)
        self.assertEqual("segregation-of-duties", slug(strict))
        try:
            self.switch("simple")
            published = self.publish(dataset_id, user=OWNER)
            self.assertEqual(200, published.status_code, published.text)
            self.assertEqual("self_reviewed", published.json()["review_mode"])
        finally:
            self.switch("estricto")

        other = self.promoted(statement_csv(f"smb-pub-{uuid.uuid4().hex[:8]}"),
                              f"smb-publicacion-{uuid.uuid4().hex[:6]}.csv")
        other_mapping = self.validated_mapping(other)
        other_dataset = self.prepared(other, other_mapping).json()["dataset_version_id"]
        independent = self.publish(other_dataset, user=REVIEWER)
        self.assertEqual(200, independent.status_code, independent.text)
        self.assertEqual("independent", independent.json()["review_mode"])


# --------------------------------------------------------------------------- #
# 5. Partidas, expediente, cierre, certificacion y reapertura
# --------------------------------------------------------------------------- #

@_without_inherited_tests
class SimpleProfileCloseTests(ProfileSwitch,
                              balance_tests.BalanceReconciliationDatabaseTests):
    # Conjuntos propios para no mezclar la limpieza con la suite base.
    reconciliation_roots: set[str] = set()
    assessments: set[str] = set()
    expectations: set[str] = set()
    lineage_entities: set[str] = set()
    accounting_closes: set[str] = set()
    close_packets: set[str] = set()
    certifications: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        force_profile(ESPIGA, "estricto")
        if cls.certifications:
            with psycopg.connect(MIGRATOR_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                                   (ESPIGA,))
                    # La certificacion es append-only y referencia el cierre con
                    # RESTRICT; la limpieza sintetica la retira antes y repone la
                    # guarda en la misma transaccion.
                    cursor.execute(
                        "ALTER TABLE fincilia.accounting_period_close_certification "
                        "DISABLE TRIGGER accounting_period_close_certification_append_only")
                    cursor.execute(
                        "DELETE FROM fincilia.accounting_period_close_certification "
                        "WHERE certification_id = ANY(%s::uuid[])",
                        (list(cls.certifications),))
                    cursor.execute(
                        "ALTER TABLE fincilia.accounting_period_close_certification "
                        "ENABLE TRIGGER accounting_period_close_certification_append_only")
        super().tearDownClass()

    def _self_published_evidence(self) -> tuple[str, str, str, str, str]:
        artifact = self.promoted(
            statement_csv(f"statement-{uuid.uuid4().hex[:8]}"),
            f"estado-sintetico-{uuid.uuid4().hex[:8]}.csv")
        mapping = self.validated_mapping(artifact)
        dataset = self.prepared(artifact, mapping, user=OWNER).json()["dataset_version_id"]
        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
            headers=self.auth(OWNER))
        self.assertEqual(200, published.status_code, published.text)
        self.assertEqual("self_reviewed", published.json()["review_mode"])
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT s.source_record_id, d.artifact_id, s.data_source_id, "
                    "       s.engine_release_id, s.canonical_schema_version "
                    "FROM fincilia.source_record s "
                    "JOIN fincilia.dataset_version d "
                    "  ON d.dataset_version_id = s.dataset_version_id "
                    "WHERE s.dataset_version_id = %s "
                    "ORDER BY s.created_at LIMIT 1", (dataset,))
                source_record, artifact_id, source_id, release_id, schema = cursor.fetchone()
        return (str(dataset), str(source_record), str(artifact_id), str(source_id),
                f"{release_id}|{schema}")

    def test_smb_owner_closes_alone_and_accountant_certifies_later(self) -> None:
        self.switch("simple")
        try:
            self._simple_flow()
        finally:
            self.switch("estricto")

    def _simple_flow(self) -> None:
        dataset, source_record, artifact, source, version = (
            self._self_published_evidence())
        release_id, schema = version.split("|", 1)
        period_start = "2026-03-31"
        period_end_date = dt.date(2026, 3, 31) + dt.timedelta(
            days=20 + int(uuid.uuid4().hex[:5], 16) % 2400)
        period_end = period_end_date.isoformat()
        expectation = str(uuid.uuid4())
        self.expectations.add(expectation)
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute(
                    "INSERT INTO fincilia.source_expectation "
                    "(expectation_id, company_id, data_source_id, financial_account_id, "
                    "period_start, period_end, due_on, late_after, expected_controls, "
                    "state, satisfied_by, satisfied_at) VALUES "
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, "
                    "'satisfied', %s, now())",
                    (expectation, ESPIGA, source, ACCOUNT, period_start, period_end,
                     (period_end_date + dt.timedelta(days=1)).isoformat(),
                     (period_end_date + dt.timedelta(days=2)).isoformat(),
                     json.dumps({"controls": ["provenance_integrity"]}), artifact))
                bank = self._insert_balance(
                    cursor, source_record=source_record, balance_type="closing",
                    amount="2500.000000000000", release_id=release_id, schema=schema)
                books = self._insert_balance(
                    cursor, source_record=source_record, balance_type="ledger",
                    amount="2500.000000000000", release_id=release_id, schema=schema)

        assessment = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/assessments",
            headers=self.auth(OWNER), json={"expectation_id": expectation})
        self.assertEqual(201, assessment.status_code, assessment.text)
        self.assessments.add(assessment.json()["assessment_id"])
        self.assertEqual("verified", assessment.json()["state"])
        statement_response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/statements",
            headers=self.auth(OWNER), json={
                "bank_balance_id": bank, "books_balance_id": books,
                "assessment_ids": [assessment.json()["assessment_id"]]})
        self.assertEqual(201, statement_response.status_code, statement_response.text)
        statement = statement_response.json()
        self.reconciliation_roots.add(statement["statement_root_id"])
        self.assertEqual("balanced", statement["state"])

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute(
                    "UPDATE fincilia.canonical_movement SET accounting_date=%s "
                    "WHERE company_id=%s AND dataset_version_id=%s",
                    (period_start, ESPIGA, dataset))

        # El owner prepara, se asigna y revisa su propio expediente.
        packet_response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/close-review/packets",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-packet-{uuid.uuid4()}"},
            json={"period_start": period_start, "period_end": period_end,
                  "assigned_reviewer_id": OWNER_ID})
        self.assertEqual(201, packet_response.status_code, packet_response.text)
        packet = packet_response.json()
        type(self).close_packets.add(packet["packet_id"])
        self.assertEqual("self_reviewed", packet["review_mode"])
        reviewed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/close-review/packets/"
            f"{packet['packet_id']}/decision",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-review-{uuid.uuid4()}"},
            json={"decision": "evidence_reviewed", "reason_code": "controls_reviewed"})
        self.assertEqual(201, reviewed.status_code, reviewed.text)
        self.assertEqual("self_reviewed", reviewed.json()["decision_review_mode"])

        closed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounting-periods/close",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-close-{uuid.uuid4()}"},
            json={"packet_id": packet["packet_id"]})
        self.assertEqual(201, closed.status_code, closed.text)
        accounting_close = closed.json()
        type(self).accounting_closes.add(accounting_close["close_id"])
        self.assertEqual("closed", accounting_close["status"])
        self.assertEqual("self_reviewed", accounting_close["review_mode"])
        self.assertEqual("self_reviewed", accounting_close["certification"])
        self.assertIsNone(accounting_close["certification_record"])
        self.assertFalse(accounting_close["certifies_financial_statements"])

        # El bloqueo del periodo cerrado sigue en PostgreSQL, igual que antes.
        with psycopg.connect(MIGRATOR_DSN) as blocked:
            with blocked.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                    self._insert_balance(
                        cursor, source_record=source_record, balance_type="closing",
                        amount="2501.000000000000", release_id=release_id,
                        schema=schema)

        certify_url = (f"/api/v1/companies/{ESPIGA}/accounting-periods/"
                       f"{accounting_close['close_id']}/certification")
        self_certified = self.client.post(certify_url, headers=self.auth(OWNER))
        self.assertEqual(409, self_certified.status_code, self_certified.text)
        self.assertEqual("accounting-period-segregation-of-duties",
                         slug(self_certified))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                audit_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "subject_id, action, resource_kind, resource_ref, outcome) VALUES "
                    "(%s, %s, %s, 'accounting.period.certify', 'accounting_period', "
                    "%s, 'allowed')",
                    (audit_id, ESPIGA, OWNER_ID, accounting_close["close_id"]))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "INSERT INTO fincilia.accounting_period_close_certification "
                        "(company_id, close_id, observed_snapshot_digest, certified_by, "
                        " audit_event_id) VALUES (%s, %s, %s, %s, %s)",
                        (ESPIGA, accounting_close["close_id"],
                         accounting_close["snapshot_digest"], OWNER_ID, audit_id))
            connection.rollback()

        certified = self.client.post(certify_url, headers=self.auth(REVIEWER))
        self.assertEqual(201, certified.status_code, certified.text)
        record = certified.json()["certification_record"]
        type(self).certifications.add(record["certification_id"])
        self.assertEqual("certified", certified.json()["certification"])
        self.assertEqual(REVIEWER_ID, record["certified_by"])
        replay = self.client.post(certify_url, headers=self.auth(REVIEWER))
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(record["certification_id"],
                         replay.json()["certification_record"]["certification_id"])

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                # La certificacion no muta el cierre: la fila nace y queda.
                cursor.execute(
                    "SELECT certification, review_mode FROM fincilia.accounting_period_close "
                    "WHERE close_id = %s", (accounting_close["close_id"],))
                self.assertEqual(("self_reviewed", "self_reviewed"), cursor.fetchone())
                with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                    cursor.execute(
                        "UPDATE fincilia.accounting_period_close_certification "
                        "SET certified_at = now() WHERE certification_id = %s",
                        (record["certification_id"],))
                with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                    cursor.execute(
                        "DELETE FROM fincilia.accounting_period_close_certification "
                        "WHERE certification_id = %s", (record["certification_id"],))
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ANDINOS,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.accounting_period_close_certification "
                    "WHERE certification_id = %s", (record["certification_id"],))
                self.assertEqual(0, cursor.fetchone()[0])

        # Reapertura: en simple el owner pide y decide; queda autorrevisada.
        reopen = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounting-periods/"
            f"{accounting_close['close_id']}/reopen-requests",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-reopen-{uuid.uuid4()}"},
            json={"reason_code": "late_evidence",
                  "rationale": "Nueva evidencia sintetica documentada para la prueba."})
        self.assertEqual(201, reopen.status_code, reopen.text)
        request_id = reopen.json()["reopen_request"]["request_id"]
        reopened = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounting-periods/reopen-requests/"
            f"{request_id}/decision",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-approve-{uuid.uuid4()}"},
            json={"decision": "approved", "reason_code": "documented_basis_confirmed"})
        self.assertEqual(201, reopened.status_code, reopened.text)
        self.assertEqual("reopened", reopened.json()["status"])
        self.assertEqual("self_reviewed",
                         reopened.json()["reopen_request"]["review_mode"])

        # Partidas conciliatorias: autorrevision y revision independiente.
        own_item = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/statements/"
            f"{statement['statement_root_id']}/items",
            headers=self.auth(OWNER), json={
                "amount": "1.00", "adjustment_side": "deduct_from_bank",
                "reason_code": "bank_fee_pending",
                "evidence_source_record_ids": [source_record]})
        self.assertEqual(201, own_item.status_code, own_item.text)
        self_decision = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/items/"
            f"{own_item.json()['item_root_id']}/decisions",
            headers=self.auth(OWNER), json={"decision": "confirmed"})
        self.assertEqual(201, self_decision.status_code, self_decision.text)
        self.assertEqual("self_reviewed", self_decision.json()["review_mode"])

        prepared_item = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/statements/"
            f"{statement['statement_root_id']}/items",
            headers=self.auth(PREPARER), json={
                "amount": "5.00", "adjustment_side": "add_to_bank",
                "reason_code": "documented_timing",
                "evidence_source_record_ids": [source_record]})
        self.assertEqual(201, prepared_item.status_code, prepared_item.text)
        independent = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/items/"
            f"{prepared_item.json()['item_root_id']}/decisions",
            headers=self.auth(REVIEWER), json={"decision": "confirmed"})
        self.assertEqual(201, independent.status_code, independent.text)
        self.assertEqual("independent", independent.json()["review_mode"])

        # De vuelta en estricto, la autorrevision vuelve a estar prohibida.
        self.switch("estricto")
        strict_item = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/statements/"
            f"{statement['statement_root_id']}/items",
            headers=self.auth(OWNER), json={
                "amount": "2.00", "adjustment_side": "deduct_from_bank",
                "reason_code": "bank_fee_pending",
                "evidence_source_record_ids": [source_record]})
        self.assertEqual(201, strict_item.status_code, strict_item.text)
        strict_decision = self.client.post(
            f"/api/v1/companies/{ESPIGA}/balance-reconciliation/items/"
            f"{strict_item.json()['item_root_id']}/decisions",
            headers=self.auth(OWNER), json={"decision": "confirmed"})
        self.assertEqual(409, strict_decision.status_code, strict_decision.text)
        self.assertEqual("reconciling-item-sod-conflict", slug(strict_decision))
        strict_packet = self.client.post(
            f"/api/v1/companies/{ESPIGA}/close-review/packets",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"smb001-strict-packet-{uuid.uuid4()}"},
            json={"period_start": period_start, "period_end": period_end,
                  "assigned_reviewer_id": OWNER_ID})
        self.assertEqual(409, strict_packet.status_code, strict_packet.text)
        self.assertEqual("close-review-segregation-of-duties", slug(strict_packet))


if __name__ == "__main__":
    unittest.main()
