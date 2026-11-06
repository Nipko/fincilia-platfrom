"""FNC-SMB-002 contra PostgreSQL y MinIO reales: DIAN, MT940 y plantillas.

Recorre lo que hace una pyme: sube el XML de su factura emitida, su MT940 o la
exportacion de su banco, y el servidor propone el mapeo sin que nadie asigne
columnas. Comprueba los localizadores `xml_element` y `mt940_tag` de V0068, el
linaje por campo, que una fuente parcial nunca queda `verified` y que una
deteccion ambigua deja el mapeo manual de siempre.

Solo datos sinteticos (prefijos FNC-SYN / SYN).
"""

from __future__ import annotations

import json
import sys
import uuid

import psycopg

sys.path.insert(0, "/app/packages/contracts/python/tests")

from db.tests.test_api_authorization import MIGRATOR_DSN  # noqa: E402
from db.tests.test_p3_vertical import (  # noqa: E402
    ACCOUNT,
    ESPIGA,
    PREPARER,
    REVIEWER,
    SOURCE,
    VerticalHarness,
    statement_csv,
)
from structured_factory import invoice, mt940  # noqa: E402


def slug(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


def bancolombia_csv(marker: str) -> bytes:
    return (
        "Fecha;Descripcion;Sucursal;Documento;Valor;Saldo\n"
        f"13/02/2026;Pago proveedor SYN {marker};Centro SYN;SYN-0001;-1.234,56;10.000,00\n"
        "14/02/2026;Abono cliente SYN;Centro SYN;SYN-0002;2.500,00;12.500,00\n"
    ).encode("utf-8")


class StructuredIngestTests(VerticalHarness):
    def detection(self, artifact: str) -> dict:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/template-detection",
            headers=self.auth(PREPARER))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def template_mapping(self, artifact: str, *, validate: bool = True):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/documents/{artifact}/template-mapping",
            headers=self.auth(PREPARER),
            json={"data_source_id": SOURCE, "validate_when_clear": validate})

    def locators(self, artifact: str) -> list[dict]:
        with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT origin_locator FROM fincilia.raw_record "
                    "WHERE artifact_id = %s ORDER BY record_ordinal", (artifact,))
                return [row[0] for row in cursor]

    def prepare(self, artifact: str, mapping_version_id: str) -> dict:
        prepared = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": mapping_version_id,
                  "financial_account_id": ACCOUNT})
        self.assertEqual(201, prepared.status_code, prepared.text)
        dataset_id = prepared.json()["dataset_version_id"]
        read = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, read.status_code, read.text)
        return read.json()

    def test_smb002_dian_invoice_maps_itself_with_field_lineage(self) -> None:
        marker = uuid.uuid4().hex[:8].upper()
        artifact = self.promoted(invoice(number=f"SYN-FE-{marker}"),
                                 f"factura-{marker}.xml")
        locators = self.locators(artifact)
        self.assertEqual(2, len(locators))
        self.assertTrue(locators[0]["synthetic_header"])
        self.assertEqual("xml_element", locators[1]["locator_kind"])
        self.assertEqual(9, len(locators[1]["field_paths"]))

        detection = self.detection(artifact)
        self.assertEqual("ready", detection["status"])
        self.assertEqual("format_specification", detection["template"]["source"])
        self.assertEqual("dian-ubl-invoice", detection["template"]["template_id"])

        created = self.template_mapping(artifact)
        self.assertEqual(201, created.status_code, created.text)
        body = created.json()
        self.assertTrue(body["validated"])
        self.assertEqual([], body["blockers"])
        self.assertEqual("validated", body["state"])

        dataset = self.prepare(artifact, body["mapping_version_id"])
        self.assertEqual("verified", dataset["completeness_state"])
        self.assertEqual(1, dataset["movement_count"])

        movements = self.client.get(
            f"/api/v1/companies/{ESPIGA}/datasets/{dataset['dataset_version_id']}"
            "/movements", headers=self.auth(REVIEWER))
        self.assertEqual(200, movements.status_code, movements.text)
        listed = movements.json()
        items = listed["items"] if isinstance(listed, dict) else listed
        movement = items[0]
        self.assertEqual("119000.000000000000", movement["amount"])
        self.assertEqual("inflow", movement["direction"])
        detail = self.client.get(
            f"/api/v1/companies/{ESPIGA}/movements/{movement['movement_id']}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, detail.status_code, detail.text)
        amount = next(item for item in detail.json()["lineage"]
                      if item["field"] == "amount")
        self.assertTrue(amount["cell"]["field_origin"].endswith("cbc:PayableAmount[1]"))

    def test_smb002_mt940_maps_itself_and_mismatch_is_never_verified(self) -> None:
        marker = uuid.uuid4().hex[:8].upper()
        balanced = mt940().replace(b"SYN-STMT-0001", f"SYN-STMT-{marker}".encode())
        artifact = self.promoted(balanced, f"extracto-{marker}.sta")
        locators = self.locators(artifact)
        self.assertEqual(4, len(locators))
        self.assertEqual({"mt940_tag"}, {item["locator_kind"] for item in locators})
        self.assertEqual("61", locators[1]["tag"])

        created = self.template_mapping(artifact)
        self.assertEqual(201, created.status_code, created.text)
        self.assertEqual("swift-mt940", created.json()["template"]["template_id"])
        dataset = self.prepare(artifact, created.json()["mapping_version_id"])
        self.assertEqual("verified", dataset["completeness_state"])
        self.assertEqual(3, dataset["movement_count"])

        unbalanced = mt940(closing="C260331COP1080001,00").replace(
            b"SYN-STMT-0001", f"SYN-STMT-{marker}X".encode())
        other = self.promoted(unbalanced, f"extracto-{marker}-x.sta")
        again = self.template_mapping(other)
        self.assertEqual(201, again.status_code, again.text)
        mismatched = self.prepare(other, again.json()["mapping_version_id"])
        # Un extracto que no cuadra se extrae, pero nunca alimenta cruce ni cierre.
        self.assertEqual("mismatch", mismatched["completeness_state"])

    def test_smb002_bank_template_is_used_only_when_unambiguous(self) -> None:
        marker = uuid.uuid4().hex[:8]
        artifact = self.promoted(bancolombia_csv(marker), f"bancolombia-{marker}.csv")
        detection = self.detection(artifact)
        self.assertEqual("ready", detection["status"], detection)
        self.assertEqual("bancolombia-cuenta-movimientos",
                         detection["template"]["template_id"])
        self.assertEqual("synthetic_hypothesis", detection["template"]["calibration"])
        first = self.template_mapping(artifact)
        self.assertEqual(201, first.status_code, first.text)
        self.assertEqual([], first.json()["blockers"])
        replay = self.template_mapping(artifact)
        self.assertEqual(201, replay.status_code, replay.text)
        self.assertEqual(first.json()["mapping_version_id"],
                         replay.json()["mapping_version_id"])

        plain = self.promoted(statement_csv(f"tpl-{marker}"), f"plano-{marker}.csv")
        self.assertEqual("not_detected", self.detection(plain)["status"])
        refused = self.template_mapping(plain)
        self.assertEqual(409, refused.status_code, refused.text)
        self.assertEqual("template-not-detected", slug(refused))

    def test_smb002_structured_locators_are_checked_by_the_database(self) -> None:
        marker = uuid.uuid4().hex[:8].upper()
        artifact = self.promoted(invoice(number=f"SYN-FE-{marker}"),
                                 f"factura-check-{marker}.xml")
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT processing_run_id, origin_locator FROM fincilia.raw_record "
                    "WHERE artifact_id = %s AND record_ordinal = 2", (artifact,))
                run_id, locator = cursor.fetchone()
                broken = dict(locator)
                broken["record_ordinal"] = 9
                broken["field_paths"] = broken["field_paths"][:3]
                with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                    cursor.execute(
                        "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                        "artifact_id, processing_run_id, record_ordinal, "
                        "origin_locator, raw_values, values_digest) "
                        "VALUES (gen_random_uuid(), %s, %s, %s, 9, %s::jsonb, "
                        "%s::jsonb, %s)",
                        (ESPIGA, artifact, run_id, json.dumps(broken),
                         json.dumps(["x"] * 9), "0" * 64))
                self.assertEqual("ck_raw_locator_bounds",
                                 raised.exception.diag.constraint_name)
            connection.rollback()


if __name__ == "__main__":
    import unittest
    unittest.main()
