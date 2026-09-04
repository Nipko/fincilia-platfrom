"""FNC-DQ-001 contra PostgreSQL, RLS, privilegios y el borde HTTP."""

from __future__ import annotations

import uuid

import psycopg

from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_p3_vertical import (
    ACCOUNT, ANDINOS, ESPIGA, MAPPING, OWNER, PREPARER, SOURCE,
    VerticalHarness, purge,
)


REVIEWER = "beto@demo.local"
AUDITOR = "carla@demo.local"


def quality_csv(marker: str) -> bytes:
    rows = ["fecha;descripcion;referencia;valor"]
    # Veinte observaciones normales fijan una mediana exacta de 10 COP.
    for number in range(20):
        rows.append(
            f"13/02/2026;Movimiento sintetico {marker} {number};"
            f"REF-{number:03d};-10,00")
    # Misma referencia, importes distintos: senal, nunca unicidad economica.
    rows.extend((
        "13/02/2026;Conflicto sintetico A;QUALITY-CONFLICT;-11,00",
        "13/02/2026;Conflicto sintetico B;QUALITY-CONFLICT;-12,00",
        # Dos filas exactas producen la misma huella; ninguna se elimina.
        "14/02/2026;Duplicado sintetico;QUALITY-DUPLICATE;-15,00",
        "14/02/2026;Duplicado sintetico;QUALITY-DUPLICATE;-15,00",
        # Mas de diez veces la mediana de su particion.
        "15/02/2026;Atipico sintetico;QUALITY-OUTLIER;-1000,00",
    ))
    return ("\n".join(rows) + "\n").encode("utf-8")


def incomplete_csv(marker: str) -> bytes:
    return (
        "fecha;descripcion;referencia;valor\n"
        f"13/02/2026;Valido sintetico {marker};QUALITY-OK;-10,00\n"
        "fecha-invalida;Rechazado sintetico;QUALITY-BAD;-12,00\n"
    ).encode("utf-8")


def advanced_risk_csv(marker: str) -> bytes:
    """Patrones sinteticos deliberados; no representan actividad real."""
    rows = [
        "fecha;descripcion;referencia;valor",
        # Esta fila se repite entre dos artefactos distintos y debe conservarse.
        "13/02/2026;Hecho compartido sintetico;RISK-CROSS;-77,00",
        f"13/02/2026;Control de artefacto {marker};RISK-{marker};-9,00",
        # Cinco usos de referencia y direcciones opuestas en tres dias.
        "14/02/2026;Par sintetico 1;RISK-REVERSAL;-50,00",
        "15/02/2026;Par sintetico 2;RISK-REVERSAL;50,00",
        "14/02/2026;Par sintetico 3;RISK-REVERSAL;-51,00",
        "15/02/2026;Par sintetico 4;RISK-REVERSAL;52,00",
        "16/02/2026;Par sintetico 5;RISK-REVERSAL;53,00",
        # Cuatro valores iguales, huellas distintas por referencia.
        "17/02/2026;Rafaga sintetica 1;RISK-BURST-1;-25,00",
        "17/02/2026;Rafaga sintetica 2;RISK-BURST-2;-25,00",
        "17/02/2026;Rafaga sintetica 3;RISK-BURST-3;-25,00",
        "17/02/2026;Rafaga sintetica 4;RISK-BURST-4;-25,00",
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")


class QualityIssuePostgresTests(VerticalHarness):
    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        # Las alertas y sus eventos son evidencia sintetica append-only y no
        # referencian datasets por FK. El helper puede retirar la vertical sin
        # reescribir el ledger de calidad.
        purge(cls.created)

    def dataset(self, payload: bytes, marker: str) -> str:
        artifact = self.promoted(payload, f"{marker}.csv")
        mapping = self.create_mapping(
            artifact, definition=MAPPING,
            display_name=f"quality {marker} {uuid.uuid4().hex[:8]}")
        self.assertEqual(201, mapping.status_code, mapping.text)
        mapping_id = mapping.json()["mapping_version_id"]
        validated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{mapping_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, validated.status_code, validated.text)
        prepared = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": mapping_id,
                  "financial_account_id": ACCOUNT})
        self.assertEqual(201, prepared.status_code, prepared.text)
        return prepared.json()["dataset_version_id"]

    def test_scan_lists_and_triages_without_exposing_values(self) -> None:
        marker = uuid.uuid4().hex[:8]
        dataset = self.dataset(quality_csv(marker), f"quality-{marker}")
        incomplete = self.dataset(
            incomplete_csv(marker), f"quality-bad-{marker}")

        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "UPDATE fincilia.dataset_version SET lineage_state = 'invalidated' "
                    "WHERE dataset_version_id = %s", (dataset,))
                cursor.execute(
                    "UPDATE fincilia.canonical_movement "
                    "SET posted_on = occurred_on + 40 "
                    "WHERE movement_id = (SELECT movement_id "
                    "FROM fincilia.canonical_movement WHERE dataset_version_id = %s "
                    "ORDER BY movement_id LIMIT 1)",
                    (dataset,))
                cursor.execute(
                    "SELECT movement_id::text FROM fincilia.canonical_movement "
                    "WHERE dataset_version_id = %s", (dataset,))
                movement_ids = {row[0] for row in cursor}

        endpoint = f"/api/v1/companies/{ESPIGA}/quality"
        scanned = self.client.post(
            endpoint + "/scan", headers=self.auth(OWNER))
        self.assertEqual(200, scanned.status_code, scanned.text)
        self.assertFalse(scanned.json()["truncated"])
        self.assertEqual("none", scanned.json()["financial_effect"])

        replay = self.client.post(endpoint + "/scan", headers=self.auth(OWNER))
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(0, replay.json()["created"])
        self.assertGreater(replay.json()["refreshed"], 0)

        expected_scopes = {dataset, incomplete, *movement_ids}
        expected_rules = {
            "lineage_invalidated", "duplicate_fingerprint",
            "reference_amount_conflict", "posting_delay_over_31_days",
            "amount_outlier_10x_median", "dataset_rejected_records",
        }
        ours: list[dict] = []
        response_bodies: list[str] = []
        for rule_code in sorted(expected_rules):
            response = self.client.get(
                endpoint + "/issues", headers=self.auth(OWNER),
                params={"status": "all", "rule": rule_code, "limit": 100})
            self.assertEqual(200, response.status_code, response.text)
            response_bodies.append(response.text)
            matching = [item for item in response.json()["items"]
                        if item["scope_ref"] in expected_scopes]
            self.assertTrue(matching, rule_code)
            ours.extend(matching)
        for item in ours:
            self.assertEqual("none", item["financial_effect"])
            self.assertFalse(item["proves_fraud"])
        for secret_value in ("QUALITY-CONFLICT", "QUALITY-DUPLICATE", "1000.00"):
            self.assertNotIn(secret_value, "".join(response_bodies))

        duplicate = next(
            item for item in ours if item["rule_code"] == "duplicate_fingerprint")
        issue_id = duplicate["issue_id"]
        taken = self.client.patch(
            endpoint + f"/issues/{issue_id}", headers=self.auth(PREPARER),
            json={"status": "acknowledged", "reason_code": "investigate",
                  "rationale": "Revisar evidencia sintetica de origen."})
        self.assertEqual(200, taken.status_code, taken.text)
        self.assertEqual("acknowledged", taken.json()["status"])
        self.assertIsNotNone(taken.json()["assigned_to"])
        repeated = self.client.patch(
            endpoint + f"/issues/{issue_id}", headers=self.auth(PREPARER),
            json={"status": "acknowledged", "reason_code": "investigate",
                  "rationale": "Revisar evidencia sintetica de origen."})
        self.assertTrue(repeated.json()["replayed"])

        resolved = self.client.patch(
            endpoint + f"/issues/{issue_id}", headers=self.auth(REVIEWER),
            json={"status": "resolved", "reason_code": "reviewed_source",
                  "rationale": "La fuente sintetica fue revisada y documentada."})
        self.assertEqual(200, resolved.status_code, resolved.text)
        self.assertEqual("resolved", resolved.json()["status"])
        terminal = self.client.patch(
            endpoint + f"/issues/{issue_id}", headers=self.auth(OWNER),
            json={"status": "dismissed", "reason_code": "false_positive",
                  "rationale": "Intento sintetico posterior al cierre del caso."})
        self.assertEqual(409, terminal.status_code, terminal.text)

        cross = self.client.patch(
            f"/api/v1/companies/{ANDINOS}/quality/issues/{issue_id}",
            headers=self.auth(OWNER),
            json={"status": "resolved", "reason_code": "reviewed_source",
                  "rationale": "No debe revelar que el caso existe en otra empresa."})
        self.assertEqual(403, cross.status_code, cross.text)

    def test_auditor_reads_but_cannot_scan_and_runtime_cannot_delete(self) -> None:
        andinos = f"/api/v1/companies/{ANDINOS}/quality"
        visible = self.client.get(
            andinos + "/issues", headers=self.auth(AUDITOR),
            params={"status": "all"})
        self.assertEqual(200, visible.status_code, visible.text)
        denied = self.client.post(andinos + "/scan", headers=self.auth(AUDITOR))
        self.assertEqual(403, denied.status_code, denied.text)

        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, true)", (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute("DELETE FROM fincilia.quality_issue")
            connection.rollback()

    def test_advanced_signals_converge_without_exposing_evidence_values(self) -> None:
        first = self.dataset(
            advanced_risk_csv("A"), f"quality-risk-a-{uuid.uuid4().hex[:8]}")
        second = self.dataset(
            advanced_risk_csv("B"), f"quality-risk-b-{uuid.uuid4().hex[:8]}")
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)", (ESPIGA,))
                cursor.execute(
                    "SELECT movement_id::text FROM fincilia.canonical_movement "
                    "WHERE dataset_version_id IN (%s, %s)", (first, second))
                scopes = {row[0] for row in cursor}

        endpoint = f"/api/v1/companies/{ESPIGA}/quality"
        scanned = self.client.post(endpoint + "/scan", headers=self.auth(OWNER))
        self.assertEqual(200, scanned.status_code, scanned.text)
        expected_rules = {
            "cross_dataset_duplicate_fingerprint",
            "reference_reuse_high_frequency",
            "same_day_same_amount_burst",
            "rapid_reversal_pair",
            "multiple_risk_indicators",
        }
        ours: list[dict] = []
        response_bodies: list[str] = []
        for rule_code in sorted(expected_rules):
            response = self.client.get(
                endpoint + "/issues", headers=self.auth(OWNER),
                params={"status": "all", "rule": rule_code, "limit": 100})
            self.assertEqual(200, response.status_code, response.text)
            response_bodies.append(response.text)
            matching = [item for item in response.json()["items"]
                        if item["scope_ref"] in scopes]
            self.assertTrue(matching, rule_code)
            ours.extend(matching)
        compound = [item for item in ours
                    if item["rule_code"] == "multiple_risk_indicators"]
        self.assertTrue(compound)
        self.assertTrue(all(item["severity"] == "high" for item in compound))
        self.assertTrue(all(item["occurrence_count"] >= 2 for item in compound))
        for forbidden in ("RISK-CROSS", "RISK-REVERSAL", "RISK-BURST", "77.00"):
            self.assertNotIn(forbidden, "".join(response_bodies))


if __name__ == "__main__":
    import unittest
    unittest.main()
