"""FNC-REC-002 contra PostgreSQL real, RLS, SoD e idempotencia HTTP."""

from __future__ import annotations

import concurrent.futures
import json
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import ANDINOS, ESPIGA, OWNER, PREPARER, REVIEWER
from db.tests import test_reconciliation_candidates as rec


class ReconciliationDecisionTests(rec.ReconciliationCandidateTests):
    @classmethod
    def tearDownClass(cls) -> None:
        # El ledger es append-only y referencia movimientos con RESTRICT. Este
        # carril corre sobre una base desechable y la destruye completa; intentar
        # purgar hechos individuales seria precisamente evadir la invariante.
        cls.client.__exit__(None, None, None)

    def test_proposal_review_ledger_is_scoped_idempotent_and_append_only(self) -> None:
        run_key = uuid.uuid4().hex

        def key(label: str) -> str:
            return f"rec002-{label}-{run_key}"

        source, account = self.second_channel()
        left = self.dataset([
            ("13/02/2026", "Pago sintetico A", "REF-DEC-A", "-1.234,56"),
            ("14/02/2026", "Pago sintetico B", "REF-DEC-B", "-500,00"),
            ("15/02/2026", "Pago sintetico C", "REF-DEC-C", "-750,00"),
        ], marker="rec002-left", source=rec.SOURCE, account=rec.ACCOUNT)
        right = self.dataset([
            ("14/02/2026", "Abono sintetico A", "REF-DEC-A", "1.234,56"),
            ("15/02/2026", "Abono sintetico B", "REF-DEC-B", "500,00"),
            ("16/02/2026", "Abono sintetico C", "REF-DEC-C", "750,00"),
        ], marker="rec002-right", source=source, account=account)

        candidate_url = f"/api/v1/companies/{ESPIGA}/reconciliation/candidates"
        query = {"left_dataset_id": left, "right_dataset_id": right,
                 "max_days": 3, "limit": 20}
        explored = self.client.get(
            candidate_url, headers=self.auth(PREPARER), params=query)
        self.assertEqual(200, explored.status_code, explored.text)
        pairs = explored.json()["candidates"]
        self.assertEqual(3, len(pairs))
        first, second, third = pairs
        states_before = self._movement_states(first, second, third)

        review_url = f"/api/v1/companies/{ESPIGA}/reconciliation/reviews"
        first_body = {
            **query,
            "left_movement_id": first["left"]["movement_id"],
            "right_movement_id": first["right"]["movement_id"],
        }
        first_body.pop("limit")
        proposed = self.client.post(
            review_url, headers={**self.auth(PREPARER),
                                 "Idempotency-Key": key("propose-first")},
            json=first_body)
        self.assertEqual(200, proposed.status_code, proposed.text)
        proposal = proposed.json()
        self.assertTrue(proposal["created"])
        self.assertFalse(proposal["replayed"])
        self.assertEqual("open", proposal["status"])
        self.assertEqual("none", proposal["financial_effect"])
        self.assertFalse(proposal["proves_balance_reconciliation"])

        replay = self.client.post(
            review_url, headers={**self.auth(PREPARER),
                                 "Idempotency-Key": key("propose-first")},
            json=first_body)
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(proposal["candidate_id"], replay.json()["candidate_id"])

        changed_payload = self.client.post(
            review_url, headers={**self.auth(PREPARER),
                                 "Idempotency-Key": key("propose-first")},
            json={**first_body, "max_days": 4})
        self.assertEqual(409, changed_payload.status_code, changed_payload.text)
        self.assertEqual("idempotency-conflict",
                         changed_payload.json()["type"].rsplit("/", 1)[-1])

        reviewer_cannot_propose = self.client.post(
            review_url, headers={**self.auth(REVIEWER),
                                 "Idempotency-Key": key("reviewer-propose")},
            json=first_body)
        self.assertEqual(403, reviewer_cannot_propose.status_code,
                         reviewer_cannot_propose.text)

        preparer_cannot_confirm = self.client.post(
            f"{review_url}/{proposal['candidate_id']}/decision",
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": key("preparer-confirm")},
            json={"decision": "confirmed",
                  "reason_code": "documented_counterpart"})
        self.assertEqual(403, preparer_cannot_confirm.status_code,
                         preparer_cannot_confirm.text)

        third_body = {
            **query,
            "left_movement_id": third["left"]["movement_id"],
            "right_movement_id": third["right"]["movement_id"],
        }
        third_body.pop("limit")
        owner_proposal = self.client.post(
            review_url, headers={**self.auth(OWNER),
                                 "Idempotency-Key": key("owner-proposal")},
            json=third_body)
        self.assertEqual(200, owner_proposal.status_code, owner_proposal.text)
        owner_self_confirm = self.client.post(
            f"{review_url}/{owner_proposal.json()['candidate_id']}/decision",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": key("owner-self-confirm")},
            json={"decision": "confirmed",
                  "reason_code": "documented_counterpart"})
        self.assertEqual(409, owner_self_confirm.status_code,
                         owner_self_confirm.text)
        self.assertEqual("segregation-of-duties",
                         owner_self_confirm.json()["type"].rsplit("/", 1)[-1])

        confirmed = self.client.post(
            f"{review_url}/{proposal['candidate_id']}/decision",
            headers={**self.auth(REVIEWER),
                     "Idempotency-Key": key("confirm-first")},
            json={"decision": "confirmed",
                  "reason_code": "documented_counterpart"})
        self.assertEqual(200, confirmed.status_code, confirmed.text)
        decision = confirmed.json()
        self.assertEqual("confirmed", decision["status"])
        self.assertEqual(stable_id("subject", "beto"),
                         decision["decision"]["decided_by"])
        self.assertEqual("none", decision["financial_effect"])

        confirmed_replay = self.client.post(
            f"{review_url}/{proposal['candidate_id']}/decision",
            headers={**self.auth(REVIEWER),
                     "Idempotency-Key": key("confirm-first")},
            json={"decision": "confirmed",
                  "reason_code": "documented_counterpart"})
        self.assertEqual(200, confirmed_replay.status_code,
                         confirmed_replay.text)
        self.assertTrue(confirmed_replay.json()["replayed"])

        second_terminal = self.client.post(
            f"{review_url}/{proposal['candidate_id']}/decision",
            headers={**self.auth(REVIEWER),
                     "Idempotency-Key": key("second-terminal")},
            json={"decision": "rejected", "reason_code": "different_event"})
        self.assertEqual(409, second_terminal.status_code, second_terminal.text)
        self.assertEqual("candidate-already-decided",
                         second_terminal.json()["type"].rsplit("/", 1)[-1])

        # Dos comandos distintos y simultaneos sobre el mismo par convergen en
        # un expediente por la restriccion del par, no por monto/fecha.
        second_body = {
            **query,
            "left_movement_id": second["left"]["movement_id"],
            "right_movement_id": second["right"]["movement_id"],
        }
        second_body.pop("limit")

        def concurrent_proposal(suffix: str):
            return self.client.post(
                review_url, headers={**self.auth(PREPARER),
                                     "Idempotency-Key": key(f"concurrent-{suffix}")},
                json=second_body)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(concurrent_proposal, ("0001", "0002")))
        self.assertEqual([200, 200], sorted(item.status_code for item in responses))
        self.assertEqual(1, len({item.json()["candidate_id"] for item in responses}))
        second_candidate = responses[0].json()["candidate_id"]

        rejected = self.client.post(
            f"{review_url}/{second_candidate}/decision",
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": key("reject-second")},
            json={"decision": "rejected", "reason_code": "different_event"})
        self.assertEqual(200, rejected.status_code, rejected.text)
        self.assertEqual("rejected", rejected.json()["status"])

        listed = self.client.get(
            review_url, headers=self.auth(REVIEWER),
            params={"left_dataset_id": left, "right_dataset_id": right})
        self.assertEqual(200, listed.status_code, listed.text)
        self.assertEqual({"open", "confirmed", "rejected"},
                         {item["status"] for item in listed.json()})

        queue_url = f"/api/v1/companies/{ESPIGA}/reconciliation/review-queue"
        open_queue = self.client.get(
            queue_url, headers=self.auth(REVIEWER),
            params={"status": "open", "limit": 20})
        self.assertEqual(200, open_queue.status_code, open_queue.text)
        current_open = next(
            item for item in open_queue.json()["items"]
            if item["candidate_id"] == owner_proposal.json()["candidate_id"])
        self.assertTrue(all(item["status"] == "open"
                            for item in open_queue.json()["items"]))
        self.assertEqual(
            {left, right},
            {
                current_open["left_dataset_id"],
                current_open["right_dataset_id"],
            },
        )
        self.assertEqual("none", open_queue.json()["financial_effect"])
        self.assertFalse(open_queue.json()["proves_balance_reconciliation"])

        decided_page = self.client.get(
            queue_url, headers=self.auth(REVIEWER),
            params={"status": "all", "limit": 1})
        self.assertEqual(200, decided_page.status_code, decided_page.text)
        self.assertTrue(decided_page.json()["truncated"])
        next_page = self.client.get(
            queue_url, headers=self.auth(REVIEWER),
            params={"status": "all", "limit": 1, "offset": 1})
        self.assertEqual(200, next_page.status_code, next_page.text)
        self.assertNotEqual(decided_page.json()["items"][0]["candidate_id"],
                            next_page.json()["items"][0]["candidate_id"])

        invalid_filter = self.client.get(
            queue_url, headers=self.auth(REVIEWER), params={"status": "pending"})
        self.assertEqual(422, invalid_filter.status_code, invalid_filter.text)
        self.assertEqual("review-filter-invalid",
                         invalid_filter.json()["type"].rsplit("/", 1)[-1])

        other_company_queue = self.client.get(
            f"/api/v1/companies/{ANDINOS}/reconciliation/review-queue",
            headers=self.auth(OWNER), params={"status": "all"})
        self.assertEqual(200, other_company_queue.status_code,
                         other_company_queue.text)
        self.assertEqual([], other_company_queue.json()["items"])

        cross_company = self.client.post(
            f"/api/v1/companies/{ANDINOS}/reconciliation/reviews",
            headers={**self.auth(OWNER),
                     "Idempotency-Key": key("cross-company")},
            json=first_body)
        self.assertEqual(403, cross_company.status_code, cross_company.text)

        self.assertEqual(states_before, self._movement_states(first, second, third))
        self._assert_database_guards(proposal["candidate_id"], states_before)

    @staticmethod
    def _movement_states(*pairs: dict) -> dict[str, str]:
        movement_ids = sorted({
            side["movement_id"] for pair in pairs
            for side in (pair["left"], pair["right"])
        })
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT movement_id::text, state FROM fincilia.canonical_movement "
                    "WHERE movement_id = ANY(%s::uuid[]) ORDER BY movement_id",
                    (movement_ids,))
                return dict(cursor.fetchall())

    def _assert_database_guards(self, candidate_id: str,
                                states_before: dict[str, str]) -> None:
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT count(*), count(DISTINCT candidate_id) "
                    "FROM fincilia.match_candidate WHERE company_id = %s",
                    (ESPIGA,))
                count, distinct_count = cursor.fetchone()
                self.assertEqual(count, distinct_count)
                cursor.execute(
                    "SELECT d.evidence_refs, a.action, a.outcome, a.company_id "
                    "FROM fincilia.match_decision d "
                    "JOIN fincilia.audit_event a ON a.audit_event_id = d.audit_event_id "
                    "WHERE d.candidate_id = %s", (candidate_id,))
                evidence, action, outcome, audit_company = cursor.fetchone()
                self.assertEqual("match.confirm", action)
                self.assertEqual("allowed", outcome)
                self.assertEqual(ESPIGA, str(audit_company))
                self.assertEqual(2, len(evidence))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.audit_event "
                    "WHERE action = 'match.propose' AND outcome = 'denied' "
                    "AND detail->>'reason' = 'idempotency-conflict'")
                self.assertGreaterEqual(cursor.fetchone()[0], 1)
                cursor.execute(
                    "SELECT proposed_by, left_movement_id, right_movement_id "
                    "FROM fincilia.match_candidate WHERE candidate_id = %s",
                    (candidate_id,))
                proposer, left_movement, right_movement = cursor.fetchone()

        # RLS: otra empresa no ve ni candidatos ni decisions.
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ANDINOS,))
                cursor.execute("SELECT count(*) FROM fincilia.match_candidate")
                self.assertEqual(0, cursor.fetchone()[0])
                cursor.execute("SELECT count(*) FROM fincilia.match_decision")
                self.assertEqual(0, cursor.fetchone()[0])

        # El runtime no puede reescribir ni borrar el ledger.
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.match_candidate SET proposed_at = now() "
                        "WHERE candidate_id = %s", (candidate_id,))
            connection.rollback()

        # Incluso el migrator encuentra el trigger SoD y el trigger append-only.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                audit_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.audit_event "
                    "(audit_event_id, company_id, subject_id, action, resource_kind, "
                    " resource_ref, outcome) VALUES (%s, %s, %s, 'match.confirm', "
                    " 'match_candidate', %s, 'allowed')",
                    (audit_id, ESPIGA, proposer, candidate_id))
                evidence = [
                    {"kind": "movement", "ref": str(left_movement)},
                    {"kind": "movement", "ref": str(right_movement)},
                ]
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        cursor.execute(
                            "INSERT INTO fincilia.match_decision "
                            "(company_id, candidate_id, decision, reason_code, "
                            " evidence_refs, decided_by, audit_event_id) "
                            "VALUES (%s, %s, 'confirmed', 'documented_counterpart', "
                            " %s::jsonb, %s, %s)",
                            (ESPIGA, candidate_id, json.dumps(evidence),
                             proposer, audit_id))
                with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState):
                    with connection.transaction():
                        cursor.execute(
                            "DELETE FROM fincilia.match_candidate WHERE candidate_id = %s",
                            (candidate_id,))


if __name__ == "__main__":
    import unittest
    unittest.main()
