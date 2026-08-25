"""FNC-CLN-002 contra PostgreSQL real, API, RLS y linaje."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg

from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import (
    ANDINOS,
    ESPIGA,
    PREPARER,
    REVIEWER,
    VerticalHarness,
    purge,
    statement_csv,
)


class CorrectionApplicationDatabaseTests(VerticalHarness):
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
                            "SELECT d.dataset_version_id FROM fincilia.dataset_version d "
                            "JOIN fincilia.source_artifact a ON a.artifact_id = d.artifact_id "
                            "WHERE a.content_sha256 = ANY(%s)", (keys,))
                        datasets = [str(row[0]) for row in cursor.fetchall()]
                        if not datasets:
                            continue
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay_application_item "
                            "WHERE application_id IN (SELECT application_id FROM "
                            "fincilia.field_overlay_application WHERE "
                            "base_dataset_version_id = ANY(%s::uuid[]) OR "
                            "result_dataset_version_id = ANY(%s::uuid[]))",
                            (datasets, datasets))
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay_application WHERE "
                            "base_dataset_version_id = ANY(%s::uuid[]) OR "
                            "result_dataset_version_id = ANY(%s::uuid[])",
                            (datasets, datasets))
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay_review WHERE "
                            "overlay_id IN (SELECT overlay_id FROM fincilia.field_overlay "
                            "WHERE dataset_version_id = ANY(%s::uuid[]))", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.field_overlay WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.lineage_row_override WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.movement_evidence_link WHERE "
                            "movement_id IN (SELECT movement_id FROM "
                            "fincilia.canonical_movement WHERE "
                            "dataset_version_id = ANY(%s::uuid[]))", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.canonical_movement WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.source_record WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.reproducibility_manifest WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.dataset_chunk WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.dataset_version WHERE "
                            "dataset_version_id = ANY(%s::uuid[])", (datasets,))
                        cursor.execute(
                            "DELETE FROM fincilia.processing_run WHERE kind = "
                            "'overlay_apply' AND artifact_id IN (SELECT artifact_id "
                            "FROM fincilia.source_artifact WHERE content_sha256 = ANY(%s))",
                            (keys,))
        purge(cls.created)

    def dataset(self, marker: str) -> tuple[str, dict]:
        artifact = self.promoted(statement_csv(marker), f"{marker}.csv")
        mapping = self.validated_mapping(artifact)
        prepared = self.prepared(artifact, mapping)
        self.assertIn(prepared.status_code, (200, 201), prepared.text)
        dataset = prepared.json()["dataset_version_id"]
        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements",
            headers=self.auth(PREPARER))
        self.assertEqual(200, movements.status_code, movements.text)
        return dataset, movements.json()[0]

    def propose_and_review(self, dataset: str, movement: dict,
                           field: str, value: str) -> str:
        targets = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements/"
            f"{movement['movement_id']}/correction-targets",
            headers=self.auth(PREPARER))
        self.assertEqual(200, targets.status_code, targets.text)
        target = {item["field"]: item for item in targets.json()}[field]
        proposed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(PREPARER), json={
                "movement_id": movement["movement_id"], "field": field,
                "expected_base_digest": target["expected_base_digest"],
                "new_value": value, "reason_code": "source_correction",
                "reason_comment": "evidencia sintética corregida",
            })
        self.assertEqual(201, proposed.status_code, proposed.text)
        overlay = proposed.json()["overlay_id"]
        reviewed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/corrections/{overlay}/review",
            headers=self.auth(REVIEWER), json={
                "decision": "approved",
                "rationale": "cotejo sintético independiente",
            })
        self.assertEqual(200, reviewed.status_code, reviewed.text)
        return overlay

    def apply(self, dataset: str, company: str = ESPIGA, user: str = PREPARER):
        return self.client.post(
            f"/api/v1/companies/{company}/datasets/{dataset}/corrections/apply",
            headers=self.auth(user))

    def test_apply_creates_reproducible_version_and_preserves_base_FNC_CLN_002_AC_01_09(
            self) -> None:
        dataset, movement = self.dataset("apply-approved")
        overlay = self.propose_and_review(dataset, movement, "amount", "2000.25")

        applied = self.apply(dataset)
        self.assertEqual(201, applied.status_code, applied.text)
        result = applied.json()
        derived = result["result_dataset_version_id"]
        self.assertEqual("validated", result["state"])
        self.assertFalse(result["idempotent_replay"])
        self.assertEqual(1, result["applied_correction_count"])

        base_movement = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{movement['movement_id']}",
            headers=self.auth(REVIEWER))
        self.assertEqual("1234.560000000000", base_movement.json()["amount"])
        derived_movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{derived}/movements",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, derived_movements.status_code, derived_movements.text)
        self.assertEqual("2000.250000000000", derived_movements.json()[0]["amount"])

        corrections = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(REVIEWER))
        self.assertTrue(corrections.json()[0]["applied"])
        self.assertEqual("applied", corrections.json()[0]["status"])
        self.assertEqual(derived, corrections.json()[0]["result_dataset_version_id"])

        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/"
            f"{derived_movements.json()[0]['movement_id']}", headers=self.auth(REVIEWER))
        self.assertTrue(detail.json()["lineage_complete"])
        amount_lineage = next(
            item for item in detail.json()["lineage"] if item["field"] == "amount")
        self.assertEqual(1, len(amount_lineage["overrides"]))

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                cursor.execute(
                    "SELECT deterministic_config::text, output_digests, "
                    "d.supersedes_dataset_version_id FROM "
                    "fincilia.reproducibility_manifest m JOIN fincilia.dataset_version d "
                    "ON d.dataset_version_id = m.dataset_version_id "
                    "WHERE m.dataset_version_id = %s", (derived,))
                config, outputs, supersedes = cursor.fetchone()
                self.assertNotIn("2000.250000000000", config)
                self.assertIn("overlay_set_sha256", outputs)
                self.assertEqual(dataset, str(supersedes))
                cursor.execute(
                    "SELECT proposed_value FROM fincilia.field_overlay WHERE "
                    "overlay_id = %s", (overlay,))
                self.assertEqual("2000.250000000000", cursor.fetchone()[0])

        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{derived}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

    def test_replay_and_concurrency_return_one_version_FNC_CLN_002_AC_03_08(
            self) -> None:
        dataset, movement = self.dataset("apply-concurrent")
        self.propose_and_review(dataset, movement, "amount", "3000.75")

        def send():
            return self.apply(dataset)

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: send(), range(2)))
        self.assertEqual([201, 201], sorted(item.status_code for item in responses))
        ids = {item.json()["result_dataset_version_id"] for item in responses}
        self.assertEqual(1, len(ids))
        self.assertEqual({False, True},
                         {item.json()["idempotent_replay"] for item in responses})

        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.field_overlay_application "
                    "WHERE base_dataset_version_id = %s", (dataset,))
                self.assertEqual(1, cursor.fetchone()[0])

    def test_pending_cross_company_and_invalid_dates_fail_closed_FNC_CLN_002_AC_02_05(
            self) -> None:
        dataset, movement = self.dataset("apply-negative")
        target_response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/movements/"
            f"{movement['movement_id']}/correction-targets",
            headers=self.auth(PREPARER))
        target = {item["field"]: item for item in target_response.json()}["currency"]
        pending = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset}/corrections",
            headers=self.auth(PREPARER), json={
                "movement_id": movement["movement_id"], "field": "currency",
                "expected_base_digest": target["expected_base_digest"],
                "new_value": "USD", "reason_code": "source_correction",
                "reason_comment": "pendiente sintético",
            })
        self.assertEqual(201, pending.status_code, pending.text)
        blocked = self.apply(dataset)
        self.assertEqual(409, blocked.status_code, blocked.text)
        self.assertEqual("correction-pending-review",
                         blocked.json()["type"].rsplit("/", 1)[-1])
        cross = self.apply(dataset, company=ANDINOS)
        self.assertEqual(403, cross.status_code, cross.text)

        dated, dated_movement = self.dataset("apply-invalid-date")
        self.propose_and_review(dated, dated_movement, "posted_on", "2020-01-01")
        invalid = self.apply(dated)
        self.assertEqual(409, invalid.status_code, invalid.text)
        self.assertEqual("correction-lineage-step-missing",
                         invalid.json()["type"].rsplit("/", 1)[-1])
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.field_overlay_application "
                    "WHERE base_dataset_version_id = %s", (dated,))
                self.assertEqual(0, cursor.fetchone()[0])

    def test_application_ledgers_are_append_only_and_rls_scoped_FNC_CLN_002_AC_04_07(
            self) -> None:
        dataset, movement = self.dataset("apply-immutable")
        self.propose_and_review(dataset, movement, "amount", "4567.89")
        applied = self.apply(dataset)
        self.assertEqual(201, applied.status_code, applied.text)
        result = applied.json()
        application_id = result["application_id"]
        for statement in (
            "UPDATE fincilia.field_overlay_application SET overlay_set_digest = %s "
            "WHERE application_id = %s",
            "DELETE FROM fincilia.field_overlay_application WHERE application_id = %s",
        ):
            with self.subTest(statement=statement.split()[0]), \
                    psycopg.connect(RUNTIME_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                    parameters = (("0" * 64, application_id)
                                  if statement.startswith("UPDATE")
                                  else (application_id,))
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(statement, parameters)
            with psycopg.connect(RUNTIME_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)", (ANDINOS,))
                    cursor.execute(
                        "SELECT count(*) FROM fincilia.field_overlay_application "
                        "WHERE application_id = %s", (application_id,))
                    self.assertEqual(0, cursor.fetchone()[0])


if __name__ == "__main__":
    import unittest
    unittest.main()
