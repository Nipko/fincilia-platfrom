"""FNC-SMB-003 contra PostgreSQL real: candidatos con tolerancia y senales llanas.

ADR-039 §4. Comprueba que la tolerancia es explicita, acotada y decimal; que la
diferencia de monto queda guardada y la base la recalcula; que las senales de
NIT, Bre-B y referencia contenida se derivan de forma determinista; que el
orden es estable (mas senales, fechas mas cercanas, menor diferencia) y que los
candidatos exactos de siempre siguen valiendo. Solo datos sinteticos.
"""

from __future__ import annotations

import json
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests import test_reconciliation_candidates as rec
from db.tests.test_api_authorization import MIGRATOR_DSN
from db.tests.test_p3_vertical import ESPIGA, PREPARER


def slug(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


def _only_smb_tests(cls: type) -> type:
    for name in dir(cls):
        if name.startswith("test") and not name.startswith("test_smb"):
            setattr(cls, name, None)
    return cls


@_only_smb_tests
class ToleranceCandidateTests(rec.ReconciliationCandidateTests):
    accounts: set[str] = set()
    sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        # Ledger append-only con RESTRICT, igual que test_reconciliation_decisions.
        cls.client.__exit__(None, None, None)

    def _datasets(self) -> tuple[dict, str]:
        source, account = self.second_channel()
        m = uuid.uuid4().hex[:8]
        left = self.dataset([
            ("13/02/2026", f"Pago factura NIT FNC-SYN-NIT-0002 {m}", f"REF-TOL-A-{m}",
             "-100.000,00"),
            ("14/02/2026", f"Transferencia BREB SYN{m}01", f"REF-TOL-B-{m}", "-500,00"),
            ("15/02/2026", f"Pago sintetico C {m}", f"SYNFAC{m}", "-750,00"),
        ], marker=f"tol-left-{m}", source=rec.SOURCE, account=rec.ACCOUNT)
        right = self.dataset([
            ("15/02/2026", "Abono cliente NIT FNC-SYN-NIT-0002", f"RIGHT-A-{m}",
             "98.810,00"),
            ("14/02/2026", f"Abono BRE-B SYN{m}01", f"RIGHT-B-{m}", "500,00"),
            ("15/02/2026", f"Abono SYNFAC{m}", f"RIGHT-C-{m}", "750,00"),
        ], marker=f"tol-right-{m}", source=source, account=account)
        return {"left_dataset_id": left, "right_dataset_id": right, "max_days": 3}, m

    def _explore(self, query: dict, **extra):
        return self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/candidates",
            headers=self.auth(PREPARER), params={**query, "limit": 20, **extra})

    def test_smb003_tolerance_is_explicit_ranked_and_explained(self) -> None:
        query, _ = self._datasets()
        exact = self._explore(query)
        self.assertEqual(200, exact.status_code, exact.text)
        self.assertEqual(2, len(exact.json()["candidates"]))
        for candidate in exact.json()["candidates"]:
            self.assertIn("exact_amount", candidate["signals"])
            self.assertIsNone(candidate["amount_difference"])

        tolerant = self._explore(query, tolerance_percent="2")
        self.assertEqual(200, tolerant.status_code, tolerant.text)
        body = tolerant.json()
        self.assertEqual("2", body["tolerance_percent"])
        pairs = body["candidates"]
        self.assertEqual(3, len(pairs))
        first, second, third = pairs
        self.assertIn("payment_reference", first["signals"])
        self.assertIn("Misma referencia de pago Bre-B", first["explanation"])
        self.assertIn("reference_contained", second["signals"])
        self.assertIn("amount_within_tolerance", third["signals"])
        self.assertIn("same_counterparty_id", third["signals"])
        self.assertEqual("1190.000000000000", third["amount_difference"])
        self.assertEqual(
            ["Diferencia de $1.190 (posible retención o comisión)",
             "NIT del pagador coincide", "Fechas a 2 días",
             "Un ingreso frente a un egreso"], third["explanation"])
        self.assertNotIn("score", json.dumps(body))

        for params in ({"tolerance_amount": "1e3"}, {"tolerance_amount": "-5"},
                       {"tolerance_percent": "6"},
                       {"tolerance_amount": "10000000.01"}):
            with self.subTest(params=params):
                refused = self._explore(query, **params)
                self.assertEqual(422, refused.status_code, refused.text)
                self.assertEqual("tolerance-invalid", slug(refused))

        proposed = self.client.post(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews",
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": f"smb003-tol-{uuid.uuid4().hex}"},
            json={**query, "left_movement_id": third["left"]["movement_id"],
                  "right_movement_id": third["right"]["movement_id"],
                  "tolerance_percent": "2"})
        self.assertEqual(200, proposed.status_code, proposed.text)
        review = proposed.json()
        self.assertEqual("fnc-rec-tolerance-v1", review["rule_version"])
        self.assertEqual("1190.000000000000", review["amount_difference"])
        self.assertIn("Diferencia de $1.190 (posible retención o comisión)",
                      review["explanation"])

        # Sin tolerancia el mismo par no es candidato.
        no_tolerance = self.client.post(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews",
            headers={**self.auth(PREPARER),
                     "Idempotency-Key": f"smb003-notol-{uuid.uuid4().hex}"},
            json={**query, "left_movement_id": third["left"]["movement_id"],
                  "right_movement_id": third["right"]["movement_id"]})
        self.assertEqual(403, no_tolerance.status_code, no_tolerance.text)

        self._database_recomputes_the_difference(third)

    def _database_recomputes_the_difference(self, pair: dict) -> None:
        left, right = sorted((pair["left"]["movement_id"],
                              pair["right"]["movement_id"]))
        owner = stable_id("subject", "sofia")
        cases = (
            ("exact claim with different amounts",
             ["exact_amount", "same_currency", "opposite_direction",
              "different_financial_account", "date_within_explicit_window"],
             None, None),
            ("wrong recorded difference",
             ["amount_within_tolerance", "same_currency", "opposite_direction",
              "different_financial_account", "date_within_explicit_window"],
             "1000", "5000"),
            ("difference beyond the declared tolerance",
             ["amount_within_tolerance", "same_currency", "opposite_direction",
              "different_financial_account", "date_within_explicit_window"],
             "1190", "1000"),
        )
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT engine_release_id, canonical_schema_version "
                    "FROM fincilia.canonical_movement WHERE movement_id = %s", (left,))
                release_id, schema = cursor.fetchone()
                for label, signals, difference, tolerance in cases:
                    with self.subTest(case=label):
                        with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                            with connection.transaction():
                                audit_id = str(uuid.uuid4())
                                cursor.execute(
                                    "INSERT INTO fincilia.audit_event (audit_event_id, "
                                    "company_id, subject_id, action, resource_kind, "
                                    "resource_ref, outcome) VALUES (%s, %s, %s, "
                                    "'match.propose', 'match_candidate', 'smb003', "
                                    "'allowed')", (audit_id, ESPIGA, owner))
                                cursor.execute(
                                    "INSERT INTO fincilia.match_candidate "
                                    "(company_id, left_movement_id, right_movement_id, "
                                    " rule_version, signals, date_window_days, "
                                    " date_distance_days, engine_release_ids, "
                                    " canonical_schema_versions, proposed_by, "
                                    " audit_event_id, amount_difference, "
                                    " amount_tolerance_absolute) "
                                    "VALUES (%s, %s, %s, %s, %s, 3, 2, %s::uuid[], %s, "
                                    "        %s, %s, %s::numeric, %s::numeric)",
                                    (ESPIGA, left, right, f"smb003-forged-{uuid.uuid4().hex[:6]}",
                                     signals, [str(release_id)], [schema], owner,
                                     audit_id, difference, tolerance))
                        self.assertEqual("ck_match_candidate_amount_evidence",
                                         raised.exception.diag.constraint_name)
                # La cardinalidad no se rellena con duplicados.
                cursor.execute(
                    "SELECT fincilia.text_array_is_distinct(%s), "
                    "       fincilia.text_array_is_distinct(%s)",
                    (["exact_amount", "exact_amount", "same_currency"],
                     ["exact_amount", "same_currency"]))
                self.assertEqual((False, True), cursor.fetchone())
            connection.rollback()


if __name__ == "__main__":
    import unittest
    unittest.main()
