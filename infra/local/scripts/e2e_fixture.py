"""Prepara datos sinteticos de aceptacion en una base E2E desechable.

No es la semilla de demo ni codigo productivo. Reutiliza el recorrido PostgreSQL
real de REC-002 para crear dos datasets con linaje y un ledger de revision, los
publica mediante la API con un revisor distinto y crea un ciclo operativo. El
proyecto Compose completo se elimina al terminar la regresion.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from db.seed.local import DEFAULT_SECRET, stable_id
from db.tests.test_api_authorization import build_settings
from db.tests import test_reconciliation_candidates as rec
from db.tests.test_reconciliation_decisions import ReconciliationDecisionTests
from fincilia_api.main import create_app


ESPIGA = stable_id("company", "espiga")
OWNER = "sofia@demo.local"
PREPARER = "ana@demo.local"
REVIEWER = "beto@demo.local"
SOURCE_NAME = "Ciclo sintetico E2E QA-009"


def require(response, *statuses: int):
    if response.status_code not in statuses:
        raise RuntimeError(
            f"fixture API returned {response.status_code}: {response.text[:300]}"
        )
    return response


def session(client: TestClient, username: str) -> tuple[str, str]:
    response = require(client.post(
        "/api/v1/auth/session",
        json={"username": username, "secret": DEFAULT_SECRET},
    ), 200)
    payload = response.json()
    return payload["token"], payload["subject_id"]


def run_reconciliation_fixture() -> str:
    suite = unittest.TestSuite([
        ReconciliationDecisionTests(
            "test_proposal_review_ledger_is_scoped_idempotent_and_append_only"
        )
    ])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("the PostgreSQL reconciliation fixture failed")
    return ReconciliationDecisionTests.release_key


class SmbInboxFixture(ReconciliationDecisionTests):
    """Par sintetico para la bandeja pyme (FNC-SMB-004): exactos, uno con
    diferencia (retencion simulada) y una comision sin pareja. Se publica con un
    revisor distinto; la prueba E2E cambia el perfil por la API y lo restaura."""

    def test_smb_inbox_pair(self) -> None:
        import uuid as _uuid
        m = _uuid.uuid4().hex[:6]
        source, account = self.second_channel()
        left = self.dataset([
            ("13/02/2026", f"Pago NIT FNC-SYN-NIT-0091 factura uno {m}", f"SMB-1-{m}",
             "-100.000,00"),
            ("16/02/2026", f"Pago NIT FNC-SYN-NIT-0091 factura dos {m}", f"SMB-2-{m}",
             "-200.000,00"),
            ("19/02/2026", f"Pago NIT FNC-SYN-NIT-0091 factura tres {m}", f"SMB-3-{m}",
             "-300.000,00"),
            ("22/02/2026", f"Comision bancaria sintetica {m}", f"SMB-4-{m}", "-9.500,00"),
            ("25/02/2026", f"Pago con retencion FNC-SYN-NIT-0092 {m}", f"SMB-5-{m}",
             "-97.500,00"),
        ], marker=f"smb-bank-{m}", source=rec.SOURCE, account=rec.ACCOUNT)
        right = self.dataset([
            ("13/02/2026", "Abono NIT FNC-SYN-NIT-0091", f"INV-1-{m}", "100.000,00"),
            ("16/02/2026", "Abono NIT FNC-SYN-NIT-0091", f"INV-2-{m}", "200.000,00"),
            ("19/02/2026", "Abono NIT FNC-SYN-NIT-0091", f"INV-3-{m}", "300.000,00"),
            ("25/02/2026", "Factura FNC-SYN-NIT-0092", f"INV-5-{m}", "100.000,00"),
        ], marker=f"smb-invoices-{m}", source=source, account=account)
        for dataset_id in (left, right):
            published = self.client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/{dataset_id}/publish",
                headers=self.auth(REVIEWER))
            self.assertEqual(200, published.status_code, published.text)
            self.assertEqual("published", published.json()["state"])


def run_smb_fixture() -> None:
    suite = unittest.TestSuite([SmbInboxFixture("test_smb_inbox_pair")])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("the PostgreSQL SMB inbox fixture failed")


def publish_and_create_cycle(release_key: str) -> dict[str, int]:
    settings = build_settings(engine_release_key=release_key)
    with TestClient(create_app(settings)) as client:
        reviewer_token, _ = session(client, REVIEWER)
        owner_token, _ = session(client, OWNER)
        _, preparer_id = session(client, PREPARER)
        reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        listed = require(client.get(
            f"/api/v1/companies/{ESPIGA}/datasets", headers=reviewer_headers,
        ), 200).json()
        published = 0
        for dataset in listed:
            if dataset["state"] not in {"validated", "published"}:
                continue
            response = require(client.post(
                f"/api/v1/companies/{ESPIGA}/datasets/"
                f"{dataset['dataset_version_id']}/publish",
                headers=reviewer_headers,
            ), 200)
            if response.json()["state"] != "published":
                raise RuntimeError("fixture dataset did not become published")
            published += 1
        if published < 2:
            raise RuntimeError("fixture requires at least two published datasets")

        sources = require(client.get(
            f"/api/v1/companies/{ESPIGA}/sources", headers=owner_headers,
        ), 200).json()
        source = next((item for item in sources
                       if item["display_name"] == SOURCE_NAME), None)
        if source is None:
            source = require(client.post(
                f"/api/v1/companies/{ESPIGA}/sources",
                headers=owner_headers,
                json={
                    "source_family": "bank_account",
                    "display_name": SOURCE_NAME,
                    "purpose_code": "operational",
                    "timezone": "America/Bogota",
                },
            ), 201).json()
        source_id = source["data_source_id"]
        local_date = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
        require(client.put(
            f"/api/v1/companies/{ESPIGA}/sources/{source_id}/cycle",
            headers=owner_headers,
            json={
                "periodicity": "custom",
                "custom_days": 1,
                "due_day_offset": 0,
                "grace_days": 2,
                "responsible_subject_id": preparer_id,
                "timezone": "America/Bogota",
                "anchor_date": local_date,
            },
        ), 200)
        expectations = require(client.post(
            f"/api/v1/companies/{ESPIGA}/sources/{source_id}/expectations",
            headers=owner_headers,
            json={"until": local_date},
        ), 201).json()
        return {"published_datasets": published,
                "expectations": int(expectations["periods"])}


def main() -> int:
    release_key = run_reconciliation_fixture()
    result = publish_and_create_cycle(release_key)
    # Despues de publicar el resto: este par queda como el mas reciente.
    run_smb_fixture()
    print(json.dumps({
        "ok": True,
        "data_ceiling": "synthetic_only",
        **result,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
