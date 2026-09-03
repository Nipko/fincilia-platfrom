"""Identidad OIDC nominal contra PostgreSQL real, sin correo ni tokens reales."""

from __future__ import annotations

import hashlib
import unittest
import uuid

import psycopg

from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN


def ref(marker: str) -> str:
    return "hmac-sha256:v1:" + hashlib.sha256(marker.encode()).hexdigest()


def digest(marker: str) -> str:
    return "sha256:" + hashlib.sha256(marker.encode()).hexdigest()


class ManagedOidcIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex
        self.issuer = "https://issuer.synthetic.invalid/pool"
        self.subjects: set[str] = set()
        self.invitations: set[str] = set()

    def tearDown(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE fincilia_identity")
                if self.invitations:
                    cursor.execute(
                        "DELETE FROM fincilia.pilot_identity_invitation "
                        "WHERE invitation_id = ANY(%s::uuid[])",
                        (list(self.invitations),))
                for subject_id in self.subjects:
                    cursor.execute(
                        "DELETE FROM fincilia.subject_legal_acceptance "
                        "WHERE subject_id=%s", (subject_id,))
                cursor.execute("RESET ROLE")
                for subject_id in self.subjects:
                    cursor.execute(
                        "SELECT firm_id FROM fincilia.membership WHERE subject_id=%s",
                        (subject_id,))
                    firms = [row[0] for row in cursor.fetchall()]
                    cursor.execute(
                        "DELETE FROM fincilia.membership WHERE subject_id=%s",
                        (subject_id,))
                    cursor.execute(
                        "DELETE FROM fincilia.identity_binding WHERE subject_id=%s",
                        (subject_id,))
                    cursor.execute(
                        "DELETE FROM fincilia.subject WHERE subject_id=%s",
                        (subject_id,))
                    for firm_id in firms:
                        cursor.execute(
                            "DELETE FROM fincilia.firm WHERE firm_id=%s", (firm_id,))

    def invite(self, *, email_ref: str, code_digest: str | None = None) -> str:
        invitation_id = str(uuid.uuid4())
        self.invitations.add(invitation_id)
        value = code_digest or digest("code-" + invitation_id)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE fincilia_identity")
                cursor.execute(
                    "INSERT INTO fincilia.pilot_identity_invitation "
                    "(invitation_id, code_digest, expected_email_ref, expires_at) "
                    "VALUES (%s,%s,%s,clock_timestamp()+interval '1 hour')",
                    (invitation_id, value, email_ref))
                cursor.execute("RESET ROLE")
        return value

    def register(self, *, code: str, email_ref: str, external_ref: str,
                 subject_id: str | None = None):
        subject = subject_id or str(uuid.uuid4())
        with psycopg.connect(MIGRATOR_DSN, autocommit=False) as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE fincilia_identity")
                cursor.execute(
                    "SELECT fincilia.register_external_account_with_invite("
                    "%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (code, email_ref, subject, str(uuid.uuid4()), str(uuid.uuid4()),
                     self.issuer, external_ref, "Persona Piloto Sintetica",
                     "Firma Piloto Sintetica"))
        self.subjects.add(subject)
        return subject

    def register_public(self, *, email_ref: str, external_ref: str,
                        subject_id: str | None = None,
                        terms_version: str = "terms-2026-09-03-en",
                        privacy_version: str = "privacy-2026-09-03-en") -> str:
        subject = subject_id or str(uuid.uuid4())
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fincilia.register_external_account_public("
                    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (email_ref, subject, str(uuid.uuid4()), str(uuid.uuid4()),
                     self.issuer, external_ref, "Persona Google Sintetica",
                     "Firma Google Sintetica", terms_version, privacy_version))
        self.subjects.add(subject)
        return subject

    def test_nominal_invitation_creates_and_resolves_one_atomic_account(self) -> None:
        email_ref = ref("email-" + self.marker)
        external_ref = ref("sub-" + self.marker)
        code = self.invite(email_ref=email_ref)
        subject_id = self.register(
            code=code, email_ref=email_ref, external_ref=external_ref)

        with psycopg.connect(RUNTIME_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT subject_id::text, display_name, status "
                    "FROM fincilia.resolve_external_identity(%s,%s)",
                    (self.issuer, external_ref))
                self.assertEqual(
                    (subject_id, "Persona Piloto Sintetica", "active"),
                    cursor.fetchone())

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT b.issuer,b.external_subject_ref,m.firm_role,m.status "
                    "FROM fincilia.identity_binding b "
                    "JOIN fincilia.membership m USING(subject_id) "
                    "WHERE b.subject_id=%s", (subject_id,))
                self.assertEqual(
                    (self.issuer, external_ref, "owner", "active"),
                    cursor.fetchone())
                cursor.execute("SET ROLE fincilia_identity")
                cursor.execute(
                    "SELECT consumed_at IS NOT NULL, consumed_by::text, "
                    "expected_email_ref FROM fincilia.pilot_identity_invitation "
                    "WHERE code_digest=%s", (code,))
                self.assertEqual((True, subject_id, email_ref), cursor.fetchone())
                cursor.execute("RESET ROLE")

    def test_wrong_email_and_replay_leave_no_partial_identity(self) -> None:
        expected = ref("email-" + self.marker)
        code = self.invite(email_ref=expected)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.register(
                code=code, email_ref=ref("different-" + self.marker),
                external_ref=ref("loser-" + self.marker))

        subject = self.register(
            code=code, email_ref=expected,
            external_ref=ref("winner-" + self.marker))
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.register(
                code=code, email_ref=expected,
                external_ref=ref("replay-" + self.marker))
        self.subjects.add(subject)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.subject "
                    "WHERE display_name='Persona Piloto Sintetica'")
                self.assertGreaterEqual(cursor.fetchone()[0], 1)
                cursor.execute(
                    "SELECT count(*) FROM fincilia.identity_binding "
                    "WHERE issuer=%s AND external_subject_ref IN (%s,%s)",
                    (self.issuer, ref("loser-" + self.marker),
                     ref("replay-" + self.marker)))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_duplicate_binding_rolls_back_the_second_invitation(self) -> None:
        email_ref = ref("email-" + self.marker)
        external_ref = ref("same-sub-" + self.marker)
        first_code = self.invite(email_ref=email_ref)
        self.register(code=first_code, email_ref=email_ref,
                      external_ref=external_ref)
        second_code = self.invite(email_ref=email_ref)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.register(code=second_code, email_ref=email_ref,
                          external_ref=external_ref)
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE fincilia_identity")
                cursor.execute(
                    "SELECT consumed_at IS NULL FROM "
                    "fincilia.pilot_identity_invitation WHERE code_digest=%s",
                    (second_code,))
                self.assertTrue(cursor.fetchone()[0])
                cursor.execute("RESET ROLE")

    def test_public_google_registration_is_atomic_and_records_legal_versions(self) -> None:
        email_ref = ref("public-email-" + self.marker)
        external_ref = ref("public-sub-" + self.marker)
        subject_id = self.register_public(
            email_ref=email_ref, external_ref=external_ref)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT b.verified_email_ref,m.firm_role,m.status "
                    "FROM fincilia.identity_binding b "
                    "JOIN fincilia.membership m USING(subject_id) "
                    "WHERE b.subject_id=%s", (subject_id,))
                self.assertEqual((email_ref, "owner", "active"), cursor.fetchone())
                cursor.execute("SET ROLE fincilia_identity")
                cursor.execute(
                    "SELECT document_kind,document_version,acceptance_channel "
                    "FROM fincilia.subject_legal_acceptance "
                    "WHERE subject_id=%s ORDER BY document_kind", (subject_id,))
                self.assertEqual([
                    ("privacy", "privacy-2026-09-03-en", "google_oidc_registration"),
                    ("terms", "terms-2026-09-03-en", "google_oidc_registration"),
                ], cursor.fetchall())
                cursor.execute(
                    "SELECT document_kind,document_version,active_for_registration "
                    "FROM fincilia.legal_document_version "
                    "ORDER BY document_kind,document_version")
                self.assertEqual([
                    ("privacy", "privacy-2026-08-29", False),
                    ("privacy", "privacy-2026-09-03", False),
                    ("privacy", "privacy-2026-09-03-en", True),
                    ("terms", "terms-2026-08-29", False),
                    ("terms", "terms-2026-09-03", False),
                    ("terms", "terms-2026-09-03-en", True),
                ], cursor.fetchall())
                cursor.execute("RESET ROLE")

    def test_stale_legal_version_and_duplicate_email_leave_no_partial_account(self) -> None:
        email_ref = ref("unique-email-" + self.marker)
        first = self.register_public(
            email_ref=email_ref, external_ref=ref("first-sub-" + self.marker))
        stale_subject = str(uuid.uuid4())
        duplicate_subject = str(uuid.uuid4())
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.register_public(
                email_ref=ref("stale-email-" + self.marker),
                external_ref=ref("stale-sub-" + self.marker),
                subject_id=stale_subject, terms_version="terms-2026-08-29")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.register_public(
                email_ref=email_ref,
                external_ref=ref("different-sub-" + self.marker),
                subject_id=duplicate_subject)
        self.subjects.update({first, stale_subject, duplicate_subject})
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM fincilia.subject "
                    "WHERE subject_id IN (%s,%s)",
                    (stale_subject, duplicate_subject))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_runtime_has_only_resolve_and_public_registration(self) -> None:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    "has_function_privilege('public', "
                    "'fincilia.resolve_external_identity(text,text)','EXECUTE'),"
                    "has_function_privilege('fincilia_app', "
                    "'fincilia.resolve_external_identity(text,text)','EXECUTE'),"
                    "has_function_privilege('public', "
                    "'fincilia.register_external_account_with_invite(text,text,uuid,uuid,uuid,text,text,text,text)','EXECUTE'),"
                    "has_function_privilege('fincilia_app', "
                    "'fincilia.register_external_account_with_invite(text,text,uuid,uuid,uuid,text,text,text,text)','EXECUTE'),"
                    "has_function_privilege('public', "
                    "'fincilia.register_external_account_public(text,uuid,uuid,uuid,text,text,text,text,text,text)','EXECUTE'),"
                    "has_function_privilege('fincilia_app', "
                    "'fincilia.register_external_account_public(text,uuid,uuid,uuid,text,text,text,text,text,text)','EXECUTE'),"
                    "has_table_privilege('fincilia_app', "
                    "'fincilia.pilot_identity_invitation','SELECT,INSERT,UPDATE,DELETE'),"
                    "has_table_privilege('fincilia_app', "
                    "'fincilia.subject_legal_acceptance','SELECT,INSERT,UPDATE,DELETE'),"
                    "has_table_privilege('fincilia_app','fincilia.subject','INSERT,UPDATE'),"
                    "has_table_privilege('fincilia_app','fincilia.membership','INSERT,UPDATE')")
                self.assertEqual(
                    (False, True, False, False, False, True, False, False,
                     False, False),
                    cursor.fetchone())


if __name__ == "__main__":
    unittest.main()
