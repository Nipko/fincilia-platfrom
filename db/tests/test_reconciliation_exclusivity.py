"""FNC-REC-004: exclusividad de confirmaciones contra PostgreSQL real."""

from __future__ import annotations

import concurrent.futures
import json
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import ESPIGA, OWNER, PREPARER, REVIEWER
from db.tests import test_reconciliation_candidates as rec


class ReconciliationExclusivityTests(rec.ReconciliationCandidateTests):
    @classmethod
    def tearDownClass(cls) -> None:
        # Este ledger es append-only y referencia la evidencia con RESTRICT. El
        # carril de CI destruye su base completa; no falseamos la invariante con
        # una purga selectiva de hechos.
        cls.client.__exit__(None, None, None)

    def test_one_movement_has_one_confirmed_counterpart_under_concurrency(self) -> None:
        run_key = uuid.uuid4().hex
        source, account = self.second_channel()
        left_dataset = self.dataset([
            ("13/02/2026", "Pago sintetico compartido", "REF-ONE", "-100,00"),
        ], marker=f"rec004-left-{run_key[:6]}", source=rec.SOURCE,
            account=rec.ACCOUNT)
        right_dataset = self.dataset([
            ("13/02/2026", "Abono sintetico uno", "REF-ONE", "100,00"),
            ("14/02/2026", "Abono sintetico dos", "REF-TWO", "100,00"),
            ("15/02/2026", "Abono sintetico tres", "REF-THREE", "100,00"),
        ], marker=f"rec004-right-{run_key[:6]}", source=source, account=account)

        candidates_url = f"/api/v1/companies/{ESPIGA}/reconciliation/candidates"
        query = {"left_dataset_id": left_dataset,
                 "right_dataset_id": right_dataset, "max_days": 3,
                 "limit": 20}
        explored = self.client.get(
            candidates_url, headers=self.auth(PREPARER), params=query)
        self.assertEqual(200, explored.status_code, explored.text)
        candidates = explored.json()["candidates"]
        self.assertEqual(3, len(candidates))
        shared = {item["left"]["movement_id"] for item in candidates}
        self.assertEqual(1, len(shared))

        reviews_url = f"/api/v1/companies/{ESPIGA}/reconciliation/reviews"
        proposals: list[dict] = []
        for index, candidate in enumerate(candidates):
            body = {
                "left_dataset_id": left_dataset,
                "right_dataset_id": right_dataset,
                "left_movement_id": candidate["left"]["movement_id"],
                "right_movement_id": candidate["right"]["movement_id"],
                "max_days": 3,
            }
            response = self.client.post(
                reviews_url,
                headers={**self.auth(PREPARER),
                         "Idempotency-Key": f"rec004-propose-{index}-{run_key}"},
                json=body)
            self.assertEqual(200, response.status_code, response.text)
            proposals.append(response.json())

        def confirm(index: int):
            candidate_id = proposals[index]["candidate_id"]
            return self.client.post(
                f"{reviews_url}/{candidate_id}/decision",
                headers={**self.auth(REVIEWER),
                         "Idempotency-Key": f"rec004-confirm-{index}-{run_key}"},
                json={"decision": "confirmed",
                      "reason_code": "documented_counterpart"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            concurrent_results = list(executor.map(confirm, (0, 1)))

        self.assertEqual([200, 409], sorted(
            response.status_code for response in concurrent_results))
        winner = next(response for response in concurrent_results
                      if response.status_code == 200)
        loser = next(response for response in concurrent_results
                     if response.status_code == 409)
        self.assertEqual("confirmed", winner.json()["status"])
        self.assertEqual(
            "movement-already-confirmed",
            loser.json()["type"].rsplit("/", 1)[-1],
        )

        listed = self.client.get(
            reviews_url, headers=self.auth(REVIEWER),
            params={"left_dataset_id": left_dataset,
                    "right_dataset_id": right_dataset})
        self.assertEqual(200, listed.status_code, listed.text)
        by_id = {item["candidate_id"]: item for item in listed.json()}
        open_conflicts = [item for item in by_id.values()
                          if item["status"] == "open"]
        self.assertEqual(2, len(open_conflicts))
        self.assertTrue(all(item["confirmation_conflict"]
                            for item in open_conflicts))

        # Una insercion directa tampoco puede saltarse la reserva. El trigger
        # materializa los miembros y la PK company/movement cierra la carrera.
        direct_candidate = proposals[2]["candidate_id"]
        reviewer_id = stable_id("subject", "beto")
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT left_movement_id, right_movement_id "
                    "FROM fincilia.match_candidate WHERE candidate_id = %s",
                    (direct_candidate,))
                direct_left, direct_right = cursor.fetchone()
                evidence = [
                    {"kind": "movement", "ref": str(direct_left)},
                    {"kind": "movement", "ref": str(direct_right)},
                ]
                with self.assertRaises(psycopg.errors.UniqueViolation) as raised:
                    with connection.transaction():
                        audit_id = str(uuid.uuid4())
                        cursor.execute(
                            "INSERT INTO fincilia.audit_event "
                            "(audit_event_id, company_id, subject_id, action, "
                            " resource_kind, resource_ref, outcome) "
                            "VALUES (%s, %s, %s, 'match.confirm', "
                            "'match_candidate', %s, 'allowed')",
                            (audit_id, ESPIGA, reviewer_id, direct_candidate))
                        cursor.execute(
                            "INSERT INTO fincilia.match_decision "
                            "(company_id, candidate_id, decision, reason_code, "
                            " evidence_refs, decided_by, audit_event_id) "
                            "VALUES (%s, %s, 'confirmed', "
                            "'documented_counterpart', %s::jsonb, %s, %s)",
                            (ESPIGA, direct_candidate, json.dumps(evidence),
                             reviewer_id, audit_id))
                self.assertEqual("pk_match_confirmation_member",
                                 raised.exception.diag.constraint_name)

        # El perdedor no dejo decision, recibo ni auditoria allowed. La
        # denegacion, en cambio, sobrevivio al rollback de su savepoint.
        loser_index = concurrent_results.index(loser)
        loser_candidate = proposals[loser_index]["candidate_id"]
        proposal_ids = [item["candidate_id"] for item in proposals]
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.match_confirmation_member "
                    "WHERE candidate_id = ANY(%s::uuid[])", (proposal_ids,))
                self.assertEqual(2, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT count(*) FROM fincilia.match_decision "
                    "WHERE candidate_id = %s", (loser_candidate,))
                self.assertEqual(0, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT count(*) FROM fincilia.match_command_receipt "
                    "WHERE idempotency_key = %s",
                    (f"rec004-confirm-{loser_index}-{run_key}",))
                self.assertEqual(0, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT count(*) FROM fincilia.audit_event "
                    "WHERE action = 'match.confirm' AND outcome = 'denied' "
                    "AND detail->>'reason' = 'movement-already-confirmed'")
                self.assertGreaterEqual(cursor.fetchone()[0], 1)

        # Rechazar el expediente conflictivo sigue siendo una salida explicita.
        rejected = self.client.post(
            f"{reviews_url}/{loser_candidate}/decision",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": f"rec004-reject-{run_key}"},
            json={"decision": "rejected", "reason_code": "wrong_counterpart"})
        self.assertEqual(200, rejected.status_code, rejected.text)
        self.assertEqual("rejected", rejected.json()["status"])

        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.match_confirmation_member "
                    "WHERE candidate_id = ANY(%s::uuid[])", (proposal_ids,))
                self.assertEqual(2, cursor.fetchone()[0])
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "DELETE FROM fincilia.match_confirmation_member")
            connection.rollback()


if __name__ == "__main__":
    import unittest
    unittest.main()
