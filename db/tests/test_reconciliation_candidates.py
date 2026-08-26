"""FNC-REC-001 contra PostgreSQL real, RLS y el borde HTTP."""

from __future__ import annotations

import uuid

import psycopg

from db.tests.test_api_authorization import MIGRATOR_DSN
from db.tests.test_p3_vertical import (
    ACCOUNT,
    ANDINOS,
    ESPIGA,
    MAPPING,
    OWNER,
    PREPARER,
    SOURCE,
    VerticalHarness,
    purge,
)


def csv(rows: list[tuple[str, str, str, str]]) -> bytes:
    body = ["fecha;descripcion;referencia;valor"]
    body.extend(";".join(row) for row in rows)
    return ("\n".join(body) + "\n").encode("utf-8")


class ReconciliationCandidateTests(VerticalHarness):
    accounts: set[str] = set()
    sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        purge(cls.created)
        if cls.accounts or cls.sources:
            with psycopg.connect(MIGRATOR_DSN, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    if cls.sources:
                        cursor.execute(
                            "DELETE FROM fincilia.data_source_account "
                            "WHERE data_source_id = ANY(%s::uuid[])",
                            (list(cls.sources),))
                        cursor.execute(
                            "DELETE FROM fincilia.data_source "
                            "WHERE data_source_id = ANY(%s::uuid[])",
                            (list(cls.sources),))
                    if cls.accounts:
                        cursor.execute(
                            "DELETE FROM fincilia.financial_account "
                            "WHERE account_id = ANY(%s::uuid[])",
                            (list(cls.accounts),))

    def second_channel(self, *, currency: str = "COP") -> tuple[str, str]:
        marker = uuid.uuid4().hex[:10]
        account_response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/accounts", headers=self.auth(OWNER),
            json={"account_family": "bank_account",
                  "display_name": f"Cuenta contraparte {marker}",
                  "identifier": f"SYN-{marker}-9876",
                  "currency_code": currency, "timezone": "America/Bogota"})
        self.assertEqual(201, account_response.status_code, account_response.text)
        account = account_response.json()["account_id"]
        type(self).accounts.add(account)

        source_response = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources", headers=self.auth(OWNER),
            json={"source_family": "bank_account",
                  "display_name": f"Fuente contraparte {marker}",
                  "purpose_code": "operational", "timezone": "America/Bogota"})
        self.assertEqual(201, source_response.status_code, source_response.text)
        source = source_response.json()["data_source_id"]
        type(self).sources.add(source)

        linked = self.client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source}/accounts",
            headers=self.auth(OWNER),
            json={"financial_account_id": account, "relation_role": "primary"})
        self.assertEqual(201, linked.status_code, linked.text)
        return source, account

    def dataset(self, rows: list[tuple[str, str, str, str]], *, marker: str,
                source: str, account: str, currency: str = "COP") -> str:
        artifact = self.promoted(csv(rows), f"{marker}.csv")
        mapping = self.create_mapping(
            artifact, definition={**MAPPING, "currency": currency},
            data_source_id=source,
            display_name=f"mapeo {marker} {uuid.uuid4().hex[:6]}")
        self.assertEqual(201, mapping.status_code, mapping.text)
        mapping_id = mapping.json()["mapping_version_id"]
        validated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{mapping_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, validated.status_code, validated.text)
        prepared = self.client.post(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=self.auth(PREPARER),
            json={"artifact_id": artifact, "mapping_version_id": mapping_id,
                  "financial_account_id": account})
        self.assertEqual(201, prepared.status_code, prepared.text)
        return prepared.json()["dataset_version_id"]

    def test_exact_candidates_are_explained_paginated_and_many_to_many(self) -> None:
        source, account = self.second_channel()
        left = self.dataset([
            ("13/02/2026", "Pago principal", "REF-EXACTA", "-1.234,56"),
            ("13/02/2026", "Pago repetible", "REF-OTRA", "-100,00"),
            ("13/02/2026", "Misma direccion", "REF-DIR", "-300,00"),
            ("01/01/2026", "Fuera de ventana", "REF-LATE", "-400,00"),
            ("13/02/2026", "Importe sin par", "REF-AMOUNT", "-999,00"),
        ], marker="rec-left", source=SOURCE, account=ACCOUNT)
        right = self.dataset([
            ("14/02/2026", "Abono exacto", "REF-EXACTA", "1.234,56"),
            # Mismo importe y otra referencia: sigue siendo candidato, porque la
            # referencia explica y ordena pero no decide ni excluye.
            ("15/02/2026", "Abono alterno", "REF-DISTINTA", "1.234,56"),
            ("14/02/2026", "Abono repetible", "REF-OTRA", "100,00"),
            # Misma direccion que el dataset izquierdo: no es candidato.
            ("14/02/2026", "Salida espejo", "REF-DIR", "-300,00"),
            # El importe coincide, la fecha no cae en la ventana de tres dias.
            ("05/03/2026", "Abono tardio", "REF-LATE", "400,00"),
        ], marker="rec-right", source=source, account=account)

        endpoint = f"/api/v1/companies/{ESPIGA}/reconciliation/candidates"
        query = {"left_dataset_id": left, "right_dataset_id": right,
                 "max_days": 3, "offset": 0, "limit": 2}
        first = self.client.get(endpoint, headers=self.auth(PREPARER), params=query)
        self.assertEqual(200, first.status_code, first.text)
        body = first.json()
        self.assertEqual("candidate_only", body["mode"])
        self.assertFalse(body["proves_balance_reconciliation"])
        self.assertTrue(body["truncated"])
        self.assertEqual(2, len(body["candidates"]))
        self.assertEqual("1234.560000000000",
                         body["candidates"][0]["left"]["amount"])
        self.assertIn("same_normalised_reference",
                      body["candidates"][0]["signals"])
        for candidate in body["candidates"]:
            self.assertNotIn("score", candidate)
            self.assertNotIn("confidence", candidate)

        second = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={**query, "offset": 2})
        self.assertEqual(200, second.status_code, second.text)
        self.assertFalse(second.json()["truncated"])
        self.assertEqual(1, len(second.json()["candidates"]))
        # Las coincidencias de referencia se ordenan primero. La tercera pareja
        # es el mismo 1234 con referencia distinta: existe y prueba que la
        # referencia nunca excluye. El 100 estaba en la primera pagina.
        self.assertEqual("1234.560000000000",
                         second.json()["candidates"][0]["left"]["amount"])
        self.assertNotIn("same_normalised_reference",
                         second.json()["candidates"][0]["signals"])
        self.assertEqual(
            ["100.000000000000", "1234.560000000000"],
            sorted(candidate["left"]["amount"] for candidate in body["candidates"]))
        # Los importes 300, 400 y 999 prueban direccion, ventana e importe
        # exacto al no aparecer en ninguna pagina.

        same = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={"left_dataset_id": left, "right_dataset_id": left})
        self.assertEqual(422, same.status_code, same.text)
        self.assertEqual("datasets-must-differ",
                         same.json()["type"].rsplit("/", 1)[-1])

        invalid_window = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={"left_dataset_id": left, "right_dataset_id": right,
                    "max_days": 32})
        self.assertEqual(422, invalid_window.status_code, invalid_window.text)

        usd_source, usd_account = self.second_channel(currency="USD")
        usd = self.dataset([
            ("14/02/2026", "Abono en otra moneda", "REF-EXACTA", "1.234,56"),
        ], marker="rec-usd", source=usd_source, account=usd_account,
            currency="USD")
        currency_mismatch = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={"left_dataset_id": left, "right_dataset_id": usd,
                    "max_days": 3})
        self.assertEqual(200, currency_mismatch.status_code,
                         currency_mismatch.text)
        self.assertEqual([], currency_mismatch.json()["candidates"])

        incomplete = self.dataset([
            ("14/02/2026", "Abono valido", "REF-EXACTA", "1.234,56"),
            ("fecha-invalida", "Fila rechazada", "REF-BAD", "10,00"),
        ], marker="rec-incomplete", source=source, account=account)
        ineligible = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={"left_dataset_id": left,
                    "right_dataset_id": incomplete, "max_days": 3})
        self.assertEqual(403, ineligible.status_code, ineligible.text)

        # Sofia tiene acceso a ambas empresas, asi que esta negativa prueba el
        # dataset company-scoped y no solamente la falta de engagement.
        cross_company = self.client.get(
            f"/api/v1/companies/{ANDINOS}/reconciliation/candidates",
            headers=self.auth(OWNER),
            params={"left_dataset_id": left, "right_dataset_id": right})
        self.assertEqual(403, cross_company.status_code, cross_company.text)


if __name__ == "__main__":
    import unittest
    unittest.main()
