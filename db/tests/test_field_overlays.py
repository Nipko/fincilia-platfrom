"""FNC-CLN-001 contra PostgreSQL real, RLS y los dos roles humanos sintéticos."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import (
    ACCOUNT,
    ANDINOS,
    ESPIGA,
    OWNER,
    PREPARER,
    REVIEWER,
    VerticalHarness,
    purge,
    statement_csv,
)


class FieldOverlayTests(VerticalHarness):
    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        if cls.created:
            keys = list(cls.created)
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    for company in (ESPIGA, ANDINOS):
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, false)",
                            (company,))
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay_review "
                            "WHERE overlay_id IN (SELECT o.overlay_id "
                            "FROM fincilia.field_overlay o "
                            "JOIN fincilia.dataset_version d "
                            "ON d.dataset_version_id = o.dataset_version_id "
                            "JOIN fincilia.source_artifact a "
                            "ON a.artifact_id = d.artifact_id "
                            "WHERE a.content_sha256 = ANY(%s))", (keys,))
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay "
                            "WHERE dataset_version_id IN ("
                            "SELECT d.dataset_version_id "
                            "FROM fincilia.dataset_version d "
                            "JOIN fincilia.source_artifact a "
                            "ON a.artifact_id = d.artifact_id "
                            "WHERE a.content_sha256 = ANY(%s))", (keys,))
        purge(cls.created)

    def dataset(self, marker: str) -> tuple[str, dict, list[dict]]:
        artifact = self.promoted(statement_csv(marker), f"{marker}.csv")
        mapping = self.validated_mapping(artifact)
        prepared = self.prepared(artifact, mapping)
        self.assertIn(prepared.status_code, (200, 201), prepared.text)
        dataset = prepared.json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements",
            headers=self.auth(PREPARER))
        self.assertEqual(200, movements.status_code, movements.text)
        return dataset, movements.json()[0], movements.json()

    def targets(self, dataset: str, movement: str, user: str = PREPARER) -> dict:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements/"
            f"{movement}/correction-targets", headers=self.auth(user))
        self.assertEqual(200, response.status_code, response.text)
        return {item["field"]: item for item in response.json()}

    def propose(self, dataset: str, movement: str, field: str, value: str,
                user: str = PREPARER, digest: str | None = None):
        target = self.targets(dataset, movement, user)[field]
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(user), json={
                "movement_id": movement, "field": field,
                "expected_base_digest": digest or target["expected_base_digest"],
                "new_value": value, "reason_code": "source_correction",
                "reason_comment": "evidencia sintética revisada",
            })

    def test_proposal_review_blocks_base_and_never_mutates_movement_FNC_CLN_001_AC_01_07(
            self) -> None:
        dataset, movement, _ = self.dataset("correction-approved")
        created = self.propose(dataset, movement["movement_id"], "amount", "2000.25")
        self.assertEqual(201, created.status_code, created.text)
        overlay = created.json()
        self.assertEqual("2000.250000000000", overlay["proposed_value"])
        self.assertEqual("pending_review", overlay["status"])
        self.assertFalse(overlay["applied"])

        listed = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, listed.status_code, listed.text)
        self.assertEqual("pending_review", listed.json()[0]["status"])

        reviewed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{overlay['overlay_id']}/review",
            headers=self.auth(REVIEWER),
            json={"decision": "approved", "rationale": "cotejo sintético correcto"})
        self.assertEqual(200, reviewed.status_code, reviewed.text)
        self.assertFalse(reviewed.json()["applied"])

        publication = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(422, publication.status_code, publication.text)
        self.assertEqual("correction-not-applied",
                         publication.json()["type"].rsplit("/", 1)[-1])

        unchanged = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{movement['movement_id']}",
            headers=self.auth(REVIEWER))
        self.assertEqual("1234.560000000000", unchanged.json()["amount"])

    def test_rejection_unblocks_publication_and_review_is_once_FNC_CLN_001_AC_05_06(
            self) -> None:
        dataset, movement, _ = self.dataset("correction-rejected")
        created = self.propose(dataset, movement["movement_id"], "currency", "USD")
        self.assertEqual(201, created.status_code, created.text)
        overlay_id = created.json()["overlay_id"]
        first = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{overlay_id}/review",
            headers=self.auth(REVIEWER),
            json={"decision": "rejected", "rationale": "no coincide con evidencia"})
        self.assertEqual(200, first.status_code, first.text)
        second = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{overlay_id}/review",
            headers=self.auth(OWNER),
            json={"decision": "approved", "rationale": "intento posterior"})
        self.assertEqual(409, second.status_code, second.text)
        self.assertEqual("correction-already-reviewed",
                         second.json()["type"].rsplit("/", 1)[-1])
        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

    def test_stale_noop_invalid_and_unknown_are_fail_closed_FNC_CLN_001_AC_02_03_08(
            self) -> None:
        dataset, movement, _ = self.dataset("correction-negative")
        target = self.targets(dataset, movement["movement_id"])["amount"]
        cases = (
            ({"field": "amount", "new_value": movement["amount"],
              "digest": target["expected_base_digest"]}, 409, "correction-no-op"),
            ({"field": "amount", "new_value": "10.50", "digest": "0" * 64},
             409, "correction-base-stale"),
            ({"field": "amount", "new_value": "1e3",
              "digest": target["expected_base_digest"]}, 422,
             "correction-value-invalid"),
        )
        for body, status, code in cases:
            with self.subTest(code=code):
                response = self.propose(
                    dataset, movement["movement_id"], body["field"],
                    body["new_value"], digest=body["digest"])
                self.assertEqual(status, response.status_code, response.text)
                self.assertEqual(code, response.json()["type"].rsplit("/", 1)[-1])

        unknown = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(PREPARER), json={
                "movement_id": str(uuid.uuid4()), "field": "amount",
                "expected_base_digest": target["expected_base_digest"],
                "new_value": "10.50", "reason_code": "source_correction",
                "reason_comment": "objetivo sintético inexistente",
            })
        self.assertEqual(403, unknown.status_code, unknown.text)

        cross = self.client.get(
            f"/api/v1/companies/{ANDINOS}/datasets/{dataset}/corrections",
            headers=self.auth(PREPARER))
        self.assertEqual(403, cross.status_code, cross.text)

    def test_owner_cannot_review_own_critical_correction_FNC_CLN_001_AC_05(self) -> None:
        dataset, movement, _ = self.dataset("correction-sod")
        created = self.propose(dataset, movement["movement_id"], "direction",
                               "inflow", user=OWNER)
        self.assertEqual(201, created.status_code, created.text)
        response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{created.json()['overlay_id']}/review",
            headers=self.auth(OWNER),
            json={"decision": "approved", "rationale": "autorrevisión prohibida"})
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual("segregation-of-duties",
                         response.json()["type"].rsplit("/", 1)[-1])

    def test_runtime_cannot_update_or_delete_overlay_FNC_CLN_001_AC_04(self) -> None:
        dataset, movement, _ = self.dataset("correction-immutable")
        created = self.propose(dataset, movement["movement_id"], "currency", "USD")
        self.assertEqual(201, created.status_code, created.text)
        subject = stable_id("subject", PREPARER)
        for statement in (
            "UPDATE fincilia.field_overlay SET reason_code = 'other_reviewed' "
            "WHERE overlay_id = %s",
            "DELETE FROM fincilia.field_overlay WHERE overlay_id = %s",
        ):
            with self.subTest(statement=statement.split()[0]), \
                    psycopg.connect(RUNTIME_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                                   (ESPIGA,))
                    cursor.execute("SELECT set_config('fincilia.subject_id', %s, true)",
                                   (subject,))
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement, (created.json()["overlay_id"],))

    def test_concurrent_proposals_have_one_winner_FNC_CLN_001_AC_03(self) -> None:
        dataset, movement, _ = self.dataset("correction-concurrent")
        target = self.targets(dataset, movement["movement_id"])["amount"]
        headers = self.auth(PREPARER)
        body = {
            "movement_id": movement["movement_id"], "field": "amount",
            "expected_base_digest": target["expected_base_digest"],
            "new_value": "777.77", "reason_code": "source_correction",
            "reason_comment": "propuesta concurrente sintética",
        }

        def send() -> int:
            return self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
                headers=headers, json=body).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = sorted(executor.map(lambda _: send(), range(2)))
        self.assertEqual([201, 409], statuses)

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.field_overlay "
                    "WHERE dataset_version_id = %s AND movement_id = %s "
                    "AND target_field = 'amount'", (dataset, movement["movement_id"]))
                self.assertEqual(1, cursor.fetchone()[0])


if __name__ == "__main__":
    import unittest
    unittest.main()
