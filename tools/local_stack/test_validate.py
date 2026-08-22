from __future__ import annotations

import re
import unittest
from pathlib import Path

from .model import validate_bootstrap, validate_compose, validate_repository

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infra/local/compose.yaml").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "infra/local/db/init/001_bootstrap.sql").read_text(encoding="utf-8")


def codes(findings) -> set[str]:
    return {item.code for item in findings}


SERVICE_HEAD = re.compile(r"(?m)^  (?P<name>[a-z][a-z0-9-]*):$")


def service_block(text: str, name: str) -> str:
    """Bloque exacto de un servicio.

    Anclar una mutacion en «el servicio que va justo antes de X» deja de morder
    en cuanto alguien inserta un servicio en medio: es exactamente lo que paso
    al anadir `migrate`.
    """
    heads = list(SERVICE_HEAD.finditer(text))
    for index, match in enumerate(heads):
        if match.group("name") != name:
            continue
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        return text[match.start():end]
    raise AssertionError(f"{name} is not a service in compose.yaml")


class LocalStackContractTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], validate_repository(ROOT))

    def test_floating_image_bites(self) -> None:
        mutated = COMPOSE.replace(
            "@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73",
            "", 1)
        self.assertIn("LOCAL-IMAGE-PIN", codes(validate_compose(mutated)))

    def test_every_image_must_be_pinned_not_only_the_first(self) -> None:
        for digest in ("e0eb7c480958d32bdc4357a74bdd70653ae15f2f9b4c93c4a5a9fad1dc471c84",
                       "a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e"):
            with self.subTest(digest=digest[:12]):
                mutated = COMPOSE.replace(f"@sha256:{digest}", "")
                self.assertIn("LOCAL-IMAGE-PIN", codes(validate_compose(mutated)))

    def test_public_bind_bites(self) -> None:
        mutated = COMPOSE.replace("127.0.0.1:", "0.0.0.0:")
        self.assertIn("LOCAL-LOOPBACK", codes(validate_compose(mutated)))

    def test_missing_healthcheck_bites(self) -> None:
        mutated = COMPOSE.replace("pg_isready", "health_probe_removed")
        self.assertIn("LOCAL-HEALTHCHECK", codes(validate_compose(mutated)))

    def test_a_generic_probe_does_not_count_as_a_healthcheck(self) -> None:
        for probe in ("valkey-cli ping", "/minio/health/live"):
            with self.subTest(probe=probe):
                mutated = COMPOSE.replace(probe, "true")
                self.assertIn("LOCAL-HEALTHCHECK", codes(validate_compose(mutated)))

    def test_removing_the_healthcheck_block_bites(self) -> None:
        mutated = COMPOSE.replace("    healthcheck:", "    disabled_healthcheck:")
        self.assertIn("LOCAL-HEALTHCHECK", codes(validate_compose(mutated)))

    def test_publishing_the_database_bites(self) -> None:
        marker = '    healthcheck:\n      test: ["CMD-SHELL", "pg_isready'
        mutated = COMPOSE.replace(
            marker,
            '    ports:\n      - "127.0.0.1:55430:5432"\n' + marker, 1)
        self.assertIn("LOCAL-DATA-EXPOSED", codes(validate_compose(mutated)))

    def test_putting_the_worker_on_a_routable_network_bites(self) -> None:
        block = service_block(COMPOSE, "worker")
        self.assertIn("      - fincilia_local_private\n", block)
        mutated = COMPOSE.replace(block, block.replace(
            "      - fincilia_local_private\n",
            "      - fincilia_local_private\n      - fincilia_local_edge\n", 1), 1)
        self.assertIn("LOCAL-WORKER-EGRESS", codes(validate_compose(mutated)))

    def test_the_egress_rule_targets_the_worker_and_not_any_service(self) -> None:
        # Si la regla mordiera por el fichero entero, dar salida al `migrate`
        # tambien la disparararia y no probaria nada sobre el worker.
        block = service_block(COMPOSE, "migrate")
        mutated = COMPOSE.replace(block, block.replace(
            "      - fincilia_local_private\n",
            "      - fincilia_local_private\n      - fincilia_local_edge\n", 1), 1)
        self.assertNotIn("LOCAL-WORKER-EGRESS", codes(validate_compose(mutated)))

    def test_a_migrator_without_a_profile_bites(self) -> None:
        block = service_block(COMPOSE, "migrate")
        self.assertIn('profiles: ["migrate"]', block)
        mutated = COMPOSE.replace(block, block.replace(
            '    profiles: ["migrate"]\n', "", 1), 1)
        self.assertIn("LOCAL-MIGRATE-PROFILE", codes(validate_compose(mutated)))

    def test_a_stack_that_never_migrates_bites(self) -> None:
        mutated = COMPOSE.replace("db.migrate.apply", "db.migrate.noop")
        self.assertIn("LOCAL-MIGRATE-MISSING", codes(validate_compose(mutated)))

    def test_a_service_without_a_declared_network_bites(self) -> None:
        mutated = COMPOSE.replace(
            "    networks:\n      - fincilia_local_private\n", "", 1)
        self.assertIn("LOCAL-NETWORK-MEMBERSHIP", codes(validate_compose(mutated)))

    def test_external_network_bites(self) -> None:
        mutated = COMPOSE.replace("internal: true", "internal: false")
        self.assertIn("LOCAL-INTERNAL-NETWORK", codes(validate_compose(mutated)))

    def test_privileged_container_bites(self) -> None:
        mutated = COMPOSE.replace("security_opt:", "privileged: true\n    security_opt:", 1)
        self.assertIn("LOCAL-PRIVILEGE", codes(validate_compose(mutated)))

    def test_superuser_application_role_bites(self) -> None:
        mutated = BOOTSTRAP.replace("NOSUPERUSER", "SUPERUSER")
        self.assertIn("LOCAL-BOOTSTRAP-PRIVILEGE", codes(validate_bootstrap(mutated)))

    def test_bypass_rls_application_role_bites(self) -> None:
        mutated = BOOTSTRAP.replace("NOBYPASSRLS", "BYPASSRLS")
        self.assertIn("LOCAL-BOOTSTRAP-PRIVILEGE", codes(validate_bootstrap(mutated)))

    def test_real_data_marker_cannot_replace_synthetic(self) -> None:
        mutated = COMPOSE.replace("synthetic", "customer")
        self.assertIn("LOCAL-DATA-CEILING", codes(validate_compose(mutated)))

    def test_the_stack_declares_the_five_expected_services(self) -> None:
        for service in ("postgres", "valkey", "objectstore", "api", "worker"):
            self.assertIn(f"\n  {service}:\n", COMPOSE, service)


if __name__ == "__main__":
    unittest.main()
