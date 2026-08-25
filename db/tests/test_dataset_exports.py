"""FNC-EXP-001 contra PostgreSQL real, RLS, permisos y auditoria."""

from __future__ import annotations

import csv
import io

from db.tests.test_p3_vertical import (
    ANDINOS,
    ESPIGA,
    PREPARER,
    REVIEWER,
    VerticalHarness,
)
from db.tests import test_reconciliation_candidates as rec


class DatasetExportTests(VerticalHarness):
    """Usa los builders REC sin heredar sus tests ni sus colecciones mutables."""

    accounts: set[str] = set()
    sources: set[str] = set()
    second_channel = rec.ReconciliationCandidateTests.second_channel
    dataset = rec.ReconciliationCandidateTests.dataset

    @classmethod
    def tearDownClass(cls) -> None:
        # Este unico dataset es el fixture sintetico que consume el carril web
        # inmediatamente despues de la suite PostgreSQL. Sus colecciones son
        # propias (no contaminan REC) y el volumen desechable se purga al final
        # del job. Conservarlo hace al E2E reproducible sin abrir una puerta de
        # provisionamiento ni aprobar una release humana desde el navegador.
        cls.client.__exit__(None, None, None)

    def test_published_export_is_exact_safe_audited_and_company_scoped(
            self) -> None:
        source, account = self.second_channel()
        dataset_id = self.dataset([
            ("13/02/2026", "=SUM(A1:A2)", "+CMD", "1.234,56"),
            ("14/02/2026", 'Comision "cafe" Bogota', "REF-Ñ-02", "-500,00"),
        ], marker="exp001-canonical", source=source, account=account)
        endpoint = (
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/export")

        before_publish = self.client.get(
            endpoint, headers=self.auth(PREPARER))
        self.assertEqual(409, before_publish.status_code, before_publish.text)
        self.assertEqual("dataset-export-unavailable",
                         before_publish.json()["type"].rsplit("/", 1)[-1])

        published = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, published.status_code, published.text)
        self.assertEqual("published", published.json()["state"])

        first = self.client.get(endpoint, headers=self.auth(PREPARER))
        second = self.client.get(endpoint, headers=self.auth(PREPARER))
        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(first.content, second.content)
        self.assertTrue(first.content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual("private, no-store, max-age=0",
                         first.headers["cache-control"])
        self.assertEqual("nosniff", first.headers["x-content-type-options"])
        self.assertEqual("canonical-v1",
                         first.headers["x-fincilia-export-profile"])
        self.assertEqual("2", first.headers["x-fincilia-export-rows"])
        self.assertRegex(
            first.headers["content-disposition"],
            r'^attachment; filename="fincilia-canonico-[0-9a-f-]{12}\.csv"$')

        rows = list(csv.DictReader(io.StringIO(
            first.content.decode("utf-8-sig"))))
        # La coordenada conserva la fila fisica del CSV: la fila 1 es cabecera.
        # Renumerar desde uno borraria la posicion que sostiene el linaje.
        self.assertEqual(["2", "3"], [item["record_ordinal"] for item in rows])
        self.assertEqual("1234.560000000000", rows[0]["amount"])
        self.assertEqual("500.000000000000", rows[1]["amount"])
        self.assertEqual("inflow", rows[0]["direction"])
        self.assertEqual("outflow", rows[1]["direction"])
        self.assertEqual("'=SUM(A1:A2)", rows[0]["description"])
        self.assertEqual("'+CMD", rows[0]["reference"])
        self.assertEqual("Comision \"cafe\" Bogota", rows[1]["description"])
        self.assertEqual("REF-Ñ-02", rows[1]["reference"])

        # Sofia tiene acceso a ambas empresas: la negativa demuestra alcance
        # del dataset bajo RLS, no solamente ausencia de engagement.
        cross_company = self.client.get(
            f"/api/v1/companies/{ANDINOS}/datasets/{dataset_id}/export",
            headers=self.auth("sofia@demo.local"))
        self.assertEqual(403, cross_company.status_code, cross_company.text)

        audit = self.client.get(
            f"/api/v1/companies/{ESPIGA}/audit",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, audit.status_code, audit.text)
        exports = [item for item in audit.json()
                   if item["action"] == "dataset.export.request"
                   and item["resource_ref"] == dataset_id]
        self.assertGreaterEqual(len(exports), 3)
        self.assertTrue(any(item["outcome"] == "denied" for item in exports))
        allowed = [item for item in exports if item["outcome"] == "allowed"]
        self.assertGreaterEqual(len(allowed), 2)
        for item in allowed:
            self.assertEqual(2, item["detail"]["rows"])
            self.assertEqual("csv", item["detail"]["format"])
            self.assertNotIn("amount", item["detail"])
            self.assertNotIn("description", item["detail"])
            self.assertNotIn("reference", item["detail"])


if __name__ == "__main__":
    import unittest
    unittest.main()
