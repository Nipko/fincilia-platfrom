"""FNC-RPT-001 contra el recorrido y PostgreSQL reales."""

from __future__ import annotations

import datetime as dt
import uuid

from db.tests.test_p3_vertical import (
    ANDINOS, ESPIGA, PREPARER, REVIEWER, VerticalHarness, purge, statement_csv,
)


OWNER = "sofia@demo.local"
AUDITOR = "carla@demo.local"


class OperationalReportPostgresTests(VerticalHarness):
    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        purge(cls.created)

    def test_report_and_csv_use_published_verified_company_data(self) -> None:
        artifact = self.promoted(
            statement_csv(f"report-{uuid.uuid4().hex[:8]}"), "informe.csv")
        mapping = self.validated_mapping(artifact)
        prepared = self.prepared(artifact, mapping, user=PREPARER)
        self.assertEqual(201, prepared.status_code, prepared.text)
        dataset_id = prepared.json()["dataset_version_id"]
        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)

        today = dt.datetime.now(dt.timezone.utc).date()
        start = today - dt.timedelta(days=364)
        endpoint = f"/api/v1/companies/{ESPIGA}/reports/operational"
        response = self.client.get(
            endpoint, headers=self.auth(OWNER),
            params={"days": 365, "as_of": today.isoformat()})
        self.assertEqual(200, response.status_code, response.text)
        report = response.json()
        self.assertEqual({"days": 365, "start": start.isoformat(),
                          "end": today.isoformat(), "timezone": "UTC"},
                         report["range"])
        self.assertGreaterEqual(report["summary"]["documents"]["total"], 1)
        self.assertGreaterEqual(report["summary"]["datasets"]["published"], 1)
        self.assertIn(dataset_id, {item["dataset_version_id"]
                                  for item in report["recent_datasets"]})
        cop = next(item for item in report["money_totals"]
                   if item["currency"] == "COP")
        self.assertGreaterEqual(cop["movement_count"], 3)
        for name in ("inflow_amount", "outflow_amount"):
            self.assertRegex(cop[name], r"^\d+\.\d{12}$")
        self.assertIn("no_balance_or_close", report["notice"])

        exported = self.client.get(
            endpoint + ".csv", headers=self.auth(OWNER),
            params={"days": 365, "as_of": today.isoformat()})
        self.assertEqual(200, exported.status_code, exported.text)
        self.assertTrue(exported.content.startswith(b"\xef\xbb\xbfmonth,currency"))
        self.assertIn("attachment;", exported.headers["content-disposition"])
        self.assertNotIn(dataset_id, exported.text)

    def test_permissions_validation_and_tenancy_fail_closed(self) -> None:
        espiga = f"/api/v1/companies/{ESPIGA}/reports/operational"
        invalid = self.client.get(
            espiga, headers=self.auth(OWNER), params={"days": 31})
        self.assertEqual(422, invalid.status_code, invalid.text)
        future = self.client.get(
            espiga, headers=self.auth(OWNER),
            params={"days": 90, "as_of": "2999-01-01"})
        self.assertEqual(422, future.status_code, future.text)

        # Beto solo esta vinculado a Espiga; Andinos no se vuelve un reporte vacio.
        denied = self.client.get(
            f"/api/v1/companies/{ANDINOS}/reports/operational",
            headers=self.auth(REVIEWER))
        self.assertEqual(403, denied.status_code, denied.text)

        # Auditoria puede leer y exportar su propia empresa, sin administrar nada.
        auditor = self.client.get(
            f"/api/v1/companies/{ANDINOS}/reports/operational.csv",
            headers=self.auth(AUDITOR), params={"days": 30})
        self.assertEqual(200, auditor.status_code, auditor.text)


if __name__ == "__main__":
    import unittest
    unittest.main()
