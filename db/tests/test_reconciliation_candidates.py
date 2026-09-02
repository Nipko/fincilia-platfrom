"""FNC-REC-001 contra PostgreSQL real, RLS y el borde HTTP."""

from __future__ import annotations

import json
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN
from db.tests.test_api_authorization import RUNTIME_DSN
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
        artifact = self.promoted(
            csv(rows), f"{marker}.csv", data_source_id=source)
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

    def test_mapping_versions_cannot_relabel_artifact_source(self) -> None:
        other_source, _ = self.second_channel()
        payload = csv([
            ("13/02/2026", "Origen declarado", "REF-SOURCE", "-10,00"),
        ])
        artifact = self.promoted(
            payload, "source-guard.csv", data_source_id=SOURCE)

        refused_name = f"source-refused-{uuid.uuid4().hex[:8]}"
        refused = self.create_mapping(
            artifact, data_source_id=other_source, display_name=refused_name)
        self.assertEqual(403, refused.status_code, refused.text)
        self.assertEqual("forbidden", refused.json()["type"].rsplit("/", 1)[-1])
        self.assertEqual((0, 0), self.mapping_row_counts(refused_name))

        # Evitar la API tampoco permite reinterpretar la procedencia. La
        # transaccion completa se revierte, incluida la plantilla provisional.
        bypass_name = f"source-bypass-{uuid.uuid4().hex[:8]}"
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, true)",
                            (ESPIGA,))
                        cursor.execute(
                            "SELECT set_config('fincilia.subject_id', %s, true)",
                            (stable_id("subject", "ana"),))
                        cursor.execute(
                            "INSERT INTO fincilia.column_mapping "
                            "(company_id, data_source_id, display_name, created_by) "
                            "VALUES (%s, %s, %s, %s) RETURNING mapping_id",
                            (ESPIGA, other_source, bypass_name,
                             stable_id("subject", "ana")))
                        mapping_id = str(cursor.fetchone()[0])
                        cursor.execute(
                            "INSERT INTO fincilia.column_mapping_version "
                            "(company_id, mapping_id, version_number, artifact_id, "
                            " definition, definition_digest, source_schema_digest, "
                            " created_by) VALUES (%s, %s, 1, %s, %s::jsonb, %s, %s, %s)",
                            (ESPIGA, mapping_id, artifact, json.dumps(MAPPING),
                             "0" * 64, "1" * 64,
                             stable_id("subject", "ana")))
        self.assertEqual(
            "ck_mapping_artifact_source", raised.exception.diag.constraint_name)
        self.assertEqual((0, 0), self.mapping_row_counts(bypass_name))

        template_name = f"source-template-{uuid.uuid4().hex[:8]}"
        original = self.create_mapping(
            artifact, data_source_id=SOURCE, display_name=template_name)
        self.assertEqual(201, original.status_code, original.text)
        other_artifact = self.promoted(
            payload, "source-guard-other.csv", data_source_id=other_source)
        reused = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mapping-templates/"
            f"{original.json()['mapping_id']}/versions",
            headers=self.auth(PREPARER),
            json={**MAPPING, "artifact_id": other_artifact})
        self.assertEqual(403, reused.status_code, reused.text)
        self.assertEqual((1, 1), self.mapping_row_counts(template_name))

        # El permiso UPDATE existe para avanzar el estado de la version, pero
        # no permite reescribir despues la evidencia que le dio origen.
        with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
            with self.assertRaises(psycopg.errors.CheckViolation) as changed:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('fincilia.company_id', %s, true)",
                            (ESPIGA,))
                        cursor.execute(
                            "SELECT set_config('fincilia.subject_id', %s, true)",
                            (stable_id("subject", "ana"),))
                        cursor.execute(
                            "UPDATE fincilia.column_mapping_version "
                            "SET artifact_id = %s WHERE mapping_version_id = %s",
                            (other_artifact,
                             original.json()["mapping_version_id"]))
        self.assertEqual(
            "ck_mapping_artifact_source", changed.exception.diag.constraint_name)
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('fincilia.company_id', %s, false)",
                    (ESPIGA,))
                cursor.execute(
                    "SELECT artifact_id FROM fincilia.column_mapping_version "
                    "WHERE mapping_version_id = %s",
                    (original.json()["mapping_version_id"],))
                self.assertEqual(artifact, str(cursor.fetchone()[0]))

    def test_mapping_version_payload_and_state_are_immutable(self) -> None:
        payload = csv([
            ("14/02/2026", "Version inmutable", "REF-IMMUTABLE", "25,00"),
        ])
        artifact = self.promoted(
            payload, "mapping-version-immutable.csv", data_source_id=SOURCE)
        created = self.create_mapping(
            artifact, data_source_id=SOURCE,
            display_name=f"immutable-{uuid.uuid4().hex[:8]}")
        self.assertEqual(201, created.status_code, created.text)
        version_id = created.json()["mapping_version_id"]

        def runtime_update(statement: str, parameters: tuple[object, ...]) -> None:
            with psycopg.connect(RUNTIME_DSN, autocommit=False) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, true)",
                        (ESPIGA,))
                    cursor.execute(
                        "SELECT set_config('fincilia.subject_id', %s, true)",
                        (stable_id("subject", "ana"),))
                    cursor.execute(statement, parameters)

        def stored_state() -> tuple[str, dict[str, object]]:
            with psycopg.connect(MIGRATOR_DSN) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('fincilia.company_id', %s, false)",
                        (ESPIGA,))
                    cursor.execute(
                        "SELECT state, definition FROM "
                        "fincilia.column_mapping_version "
                        "WHERE mapping_version_id = %s",
                        (version_id,))
                    row = cursor.fetchone()
                    self.assertIsNotNone(row)
                    return str(row[0]), row[1]

        initial_state = stored_state()
        self.assertEqual("draft", initial_state[0])
        with self.assertRaises(psycopg.errors.CheckViolation) as immutable:
            runtime_update(
                "UPDATE fincilia.column_mapping_version "
                "SET definition = jsonb_set(definition, '{currency}', "
                "to_jsonb(%s::text)) WHERE mapping_version_id = %s",
                ("USD", version_id))
        self.assertEqual(
            "ck_mapping_version_immutable",
            immutable.exception.diag.constraint_name)
        self.assertEqual(initial_state, stored_state())

        validated = self.client.post(
            f"/api/v1/companies/{ESPIGA}/mappings/{version_id}/validate",
            headers=self.auth(PREPARER))
        self.assertEqual(200, validated.status_code, validated.text)
        self.assertEqual("validated", stored_state()[0])

        with self.assertRaises(psycopg.errors.CheckViolation) as reversed_state:
            runtime_update(
                "UPDATE fincilia.column_mapping_version "
                "SET state = 'draft', validated_by = NULL, validated_at = NULL "
                "WHERE mapping_version_id = %s",
                (version_id,))
        self.assertEqual(
            "ck_mapping_version_state_transition",
            reversed_state.exception.diag.constraint_name)
        self.assertEqual("validated", stored_state()[0])

        runtime_update(
            "UPDATE fincilia.column_mapping_version SET state = 'superseded' "
            "WHERE mapping_version_id = %s",
            (version_id,))
        self.assertEqual("superseded", stored_state()[0])

        with self.assertRaises(psycopg.errors.CheckViolation) as resurrected:
            runtime_update(
                "UPDATE fincilia.column_mapping_version SET state = 'validated' "
                "WHERE mapping_version_id = %s",
                (version_id,))
        self.assertEqual(
            "ck_mapping_version_state_transition",
            resurrected.exception.diag.constraint_name)
        self.assertEqual("superseded", stored_state()[0])

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

        matching = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={**query, "reference_mode": "matching", "limit": 10})
        self.assertEqual(200, matching.status_code, matching.text)
        self.assertEqual("matching", matching.json()["reference_mode"])
        self.assertEqual(2, len(matching.json()["candidates"]))
        self.assertTrue(all(
            "same_normalised_reference" in item["signals"]
            for item in matching.json()["candidates"]))

        different = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={**query, "reference_mode": "different", "limit": 10})
        self.assertEqual(200, different.status_code, different.text)
        self.assertEqual(1, len(different.json()["candidates"]))
        self.assertNotIn(
            "same_normalised_reference", different.json()["candidates"][0]["signals"])

        invalid_reference_mode = self.client.get(
            endpoint, headers=self.auth(PREPARER),
            params={**query, "reference_mode": "similar"})
        self.assertEqual(422, invalid_reference_mode.status_code,
                         invalid_reference_mode.text)
        self.assertEqual("reference-mode-invalid",
                         invalid_reference_mode.json()["type"].rsplit("/", 1)[-1])

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
