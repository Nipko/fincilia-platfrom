from __future__ import annotations

import unittest
from pathlib import Path

from .model import validate_bootstrap, validate_compose, validate_repository


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infra/local/compose.yaml").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "infra/local/db/init/001_bootstrap.sql").read_text(encoding="utf-8")


class LocalStackContractTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], validate_repository(ROOT))

    def test_floating_image_bites(self) -> None:
        mutated = COMPOSE.replace("@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73", "", 1)
        self.assertIn("LOCAL-IMAGE-PIN", {item.code for item in validate_compose(mutated)})

    def test_public_bind_bites(self) -> None:
        mutated = COMPOSE.replace("127.0.0.1:", "0.0.0.0:")
        self.assertIn("LOCAL-LOOPBACK", {item.code for item in validate_compose(mutated)})

    def test_missing_healthcheck_bites(self) -> None:
        mutated = COMPOSE.replace("pg_isready", "health_probe_removed")
        self.assertIn("LOCAL-HEALTHCHECK", {item.code for item in validate_compose(mutated)})

    def test_external_network_bites(self) -> None:
        mutated = COMPOSE.replace("internal: true", "internal: false")
        self.assertIn("LOCAL-INTERNAL-NETWORK", {item.code for item in validate_compose(mutated)})

    def test_privileged_container_bites(self) -> None:
        mutated = COMPOSE.replace("security_opt:", "privileged: true\n    security_opt:", 1)
        self.assertIn("LOCAL-PRIVILEGE", {item.code for item in validate_compose(mutated)})

    def test_superuser_application_role_bites(self) -> None:
        mutated = BOOTSTRAP.replace("NOSUPERUSER", "SUPERUSER")
        self.assertIn("LOCAL-BOOTSTRAP-PRIVILEGE", {item.code for item in validate_bootstrap(mutated)})

    def test_bypass_rls_application_role_bites(self) -> None:
        mutated = BOOTSTRAP.replace("NOBYPASSRLS", "BYPASSRLS")
        self.assertIn("LOCAL-BOOTSTRAP-PRIVILEGE", {item.code for item in validate_bootstrap(mutated)})

    def test_real_data_marker_cannot_replace_synthetic(self) -> None:
        mutated = COMPOSE.replace("synthetic", "customer")
        self.assertIn("LOCAL-DATA-CEILING", {item.code for item in validate_compose(mutated)})


if __name__ == "__main__":
    unittest.main()

