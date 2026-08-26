"""FNC-REC-005 contra PostgreSQL real, RLS, idempotencia y HTTP."""

from __future__ import annotations

import concurrent.futures
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import ANDINOS, ESPIGA, PREPARER, REVIEWER
from db.tests import test_reconciliation_candidates as rec


class ReconciliationGroupProposalTests(rec.ReconciliationCandidateTests):
    @classmethod
    def tearDownClass(cls) -> None:
        # El borrador y sus recibos son append-only. El carril CI destruye su
        # base completa; purgarlos por fila ocultaria la invariante probada.
        cls.client.__exit__(None, None, None)

    def _movements(self, dataset_id: str, actor: str = PREPARER) -> list[dict]:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/movements",
            headers=self.auth(actor), params={"limit": 50})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    @staticmethod
    def _states(movement_ids: list[str]) -> dict[str, str]:
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT movement_id::text, state "
                    "FROM fincilia.canonical_movement "
                    "WHERE movement_id = ANY(%s::uuid[]) ORDER BY movement_id",
                    (movement_ids,))
                return dict(cursor.fetchall())

    def test_group_proposals_are_exact_scoped_idempotent_and_append_only(self) -> None:
        marker = uuid.uuid4().hex[:10]
        source, account = self.second_channel()
        left = self.dataset([
            ("13/02/2026", "Pago sintetico cien", "GRP-L-100", "-100,00"),
            ("14/02/2026", "Pago sintetico doscientos", "GRP-L-200", "-200,00"),
        ], marker=f"rec005-left-{marker}", source=rec.SOURCE,
            account=rec.ACCOUNT)
        right = self.dataset([
            ("15/02/2026", "Abono sintetico total", "GRP-R-300", "300,00"),
            ("16/02/2026", "Abono sintetico parcial", "GRP-R-050", "50,00"),
        ], marker=f"rec005-right-{marker}", source=source, account=account)
        left_movements = self._movements(left)
        right_movements = self._movements(right)
        left_ids = sorted(item["movement_id"] for item in left_movements)
        right_by_amount = {item["amount"]: item["movement_id"]
                           for item in right_movements}
        anchor_id = right_by_amount["300.000000000000"]
        endpoint = (
            f"/api/v1/companies/{ESPIGA}/reconciliation/group-proposals")
        body = {
            "anchor_dataset_id": right,
            "related_dataset_id": left,
            "anchor_movement_id": anchor_id,
            "related_movement_ids": list(reversed(left_ids)),
        }
        states_before = self._states([*left_ids, anchor_id])

        created = self.client.post(
            endpoint,
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": f"rec005-create-{marker}"},
            json=body)
        self.assertEqual(200, created.status_code, created.text)
        group = created.json()
        self.assertTrue(group["created"])
        self.assertFalse(group["replayed"])
        self.assertEqual("draft", group["status"])
        self.assertEqual("300.000000000000", group["related_total"])
        self.assertEqual("0.000000000000", group["difference"])
        self.assertEqual("COP", group["currency"])
        self.assertEqual(2, group["related_movement_count"])
        self.assertEqual("none", group["financial_effect"])
        self.assertFalse(group["proves_balance_reconciliation"])
        self.assertFalse(group["can_confirm"])

        replay = self.client.post(
            endpoint,
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": f"rec005-create-{marker}"},
            json={**body, "related_movement_ids": left_ids})
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(group["group_candidate_id"],
                         replay.json()["group_candidate_id"])

        conflict = self.client.post(
            endpoint,
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": f"rec005-create-{marker}"},
            json={**body,
                  "anchor_movement_id": right_by_amount["50.000000000000"]})
        self.assertEqual(409, conflict.status_code, conflict.text)
        self.assertEqual("idempotency-conflict",
                         conflict.json()["type"].rsplit("/", 1)[-1])

        listed = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={"left_dataset_id": left, "right_dataset_id": right})
        self.assertEqual(200, listed.status_code, listed.text)
        listed_group = next(item for item in listed.json()
                            if item["group_candidate_id"]
                            == group["group_candidate_id"])
        self.assertEqual("many_to_one", listed_group["view_relation"])
        self.assertEqual("0.000000000000", listed_group["difference"])

        denied = self.client.post(
            endpoint,
            headers={**self.auth(REVIEWER),
                     "Idempotency-Key": f"rec005-denied-{marker}"},
            json=body)
        self.assertEqual(403, denied.status_code, denied.text)

        states_after = self._states([*left_ids, anchor_id])
        self.assertEqual(states_before, states_after)

        group_id = group["group_candidate_id"]
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ANDINOS,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.match_group_candidate "
                    "WHERE group_candidate_id = %s", (group_id,))
                self.assertEqual(0, cursor.fetchone()[0])
            connection.rollback()
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.match_group_candidate "
                        "SET rule_version = 'forbidden' "
                        "WHERE group_candidate_id = %s", (group_id,))
            connection.rollback()

    def test_concurrent_same_composition_converges_and_trigger_bites(self) -> None:
        marker = uuid.uuid4().hex[:10]
        source, account = self.second_channel()
        left = self.dataset([
            ("13/03/2026", "Pago sintetico cuarenta", "GRP-C-40", "-40,00"),
            ("14/03/2026", "Pago sintetico sesenta", "GRP-C-60", "-60,00"),
        ], marker=f"rec005-con-left-{marker}", source=rec.SOURCE,
            account=rec.ACCOUNT)
        right = self.dataset([
            ("15/03/2026", "Abono sintetico cien", "GRP-C-100", "100,00"),
        ], marker=f"rec005-con-right-{marker}", source=source, account=account)
        left_ids = sorted(item["movement_id"] for item in self._movements(left))
        anchor_id = self._movements(right)[0]["movement_id"]
        endpoint = (
            f"/api/v1/companies/{ESPIGA}/reconciliation/group-proposals")
        body = {
            "anchor_dataset_id": right,
            "related_dataset_id": left,
            "anchor_movement_id": anchor_id,
            "related_movement_ids": left_ids,
        }

        def propose(index: int):
            return self.client.post(
                endpoint,
                headers={**self.auth(PREPARER),
                         "Idempotency-Key": f"rec005-race-{index}-{marker}"},
                json=body)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(propose, (0, 1)))
        self.assertEqual([200, 200], sorted(item.status_code for item in responses))
        payloads = [item.json() for item in responses]
        self.assertEqual(1, sum(bool(item["created"]) for item in payloads))
        self.assertEqual(1, len({item["group_candidate_id"] for item in payloads}))

        actor_id = stable_id("subject", "ana")
        canonical = sorted(left_ids)
        unsorted_ids = list(reversed(canonical))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), count(DISTINCT idempotency_key) "
                    "FROM fincilia.match_group_command_receipt "
                    "WHERE idempotency_key LIKE %s",
                    (f"rec005-race-%-{marker}",))
                self.assertEqual((2, 2), cursor.fetchone())

                invalid_group_id = str(uuid.uuid4())
                invalid_audit_id = str(uuid.uuid4())
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        cursor.execute(
                            "INSERT INTO fincilia.audit_event "
                            "(audit_event_id, company_id, subject_id, action, "
                            " resource_kind, resource_ref, outcome) "
                            "VALUES (%s, %s, %s, 'match.group.propose', "
                            "'match_group_candidate', %s, 'allowed')",
                            (invalid_audit_id, ESPIGA, actor_id,
                             invalid_group_id))
                        cursor.execute(
                            "INSERT INTO fincilia.match_group_candidate "
                            "(group_candidate_id, company_id, "
                            " anchor_dataset_version_id, related_dataset_version_id, "
                            " anchor_movement_id, related_movement_ids, "
                            " rule_version, proposed_by, audit_event_id) "
                            "VALUES (%s, %s, %s, %s, %s, %s::uuid[], "
                            "'fnc-rec-group-whole-v1', %s, %s)",
                            (invalid_group_id, ESPIGA, right, left, anchor_id,
                             unsorted_ids, actor_id, invalid_audit_id))

                cursor.execute(
                    "SELECT count(*) FROM fincilia.audit_event "
                    "WHERE audit_event_id = %s", (invalid_audit_id,))
                self.assertEqual(0, cursor.fetchone()[0])


if __name__ == "__main__":
    import unittest
    unittest.main()
