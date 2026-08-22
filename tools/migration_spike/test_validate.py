"""Pruebas del spike de migraciones (FNC-DB-002).

Cuatro bloques:

1. positivas contra el contrato y el manifiesto reales;
2. negativas sobre un spike sintetico construido en un directorio temporal;
3. la capa de proceso, con dobles y comandos locales inocuos;
4. los casos estaticos del suite y el CLI.

Ningun test de este fichero levanta Docker, y por tanto **ninguno es evidencia de
integracion**. La evidencia de PostgreSQL la produce `run`, y solo ella.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tools.migration_spike import cli as spike_cli
from tools.migration_spike.contract import validate_contract
from tools.migration_spike.manifest import (
    plan,
    plan_digest,
    resolve_inside,
    safe_relative,
    sha256_file,
    validate_manifest,
)
from tools.migration_spike.runner import (
    ADAPTERS,
    Execution,
    SpikeLab,
    SpikeRunnerError,
    build_environment,
    host_path,
    probe_adapter,
    run_argv,
    to_wsl_path,
)
from tools.migration_spike.suite import (
    CASE_CATALOGUE,
    _expect_failure,
    _expect_success,
    case_checksum_order,
    case_cleanup_scope,
    case_unknown_migration,
    static_cases,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs/database/migration-spike.json"
SPIKE_ROOT = ROOT / "spikes/FNC-DB-002"
MANIFEST_PATH = SPIKE_ROOT / "MANIFEST.json"
SOURCE_DIR = ROOT / "tools/migration_spike"

NULL_ADAPTER = {"id": "none", "prefix": ("docker",),
                "probe": (sys.executable, "-c", "raise SystemExit(9)"),
                "translate_paths": False}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cli(argv: list[str]) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spike_cli.main(argv)
    text = out.getvalue() or err.getvalue()
    return code, (json.loads(text) if text.strip() else {})


def synthetic_spike(directory: Path, *, migrations: list[tuple[str, str, str]] | None = None,
                    extra_files: dict[str, str] | None = None) -> tuple[Path, dict]:
    """Un spike minimo, coherente y enteramente sintetico."""
    steps = migrations if migrations is not None else [
        ("V0001", "create_table", "CREATE TABLE spike.a (id integer);\n"),
        ("V0002", "add_column", "ALTER TABLE spike.a ADD COLUMN b text;\n"),
    ]
    write(directory / "compose.yaml", "name: fincilia-db-spike\nservices:\n  postgres:\n")
    write(directory / "sql/apply_one.sql", "\\set ON_ERROR_STOP on\n")
    write(directory / "db/init/001_spike_bootstrap.sql", "CREATE SCHEMA spike;\n")
    for version, name, body in steps:
        write(directory / f"sql/migrations/{version}__{name}.sql", body)
    for relative, body in (extra_files or {}).items():
        write(directory / relative, body)

    def entry(relative: str) -> dict:
        absolute = directory / relative
        return {"path": relative, "sha256": sha256_file(absolute),
                "bytes": absolute.stat().st_size}

    manifest = {
        "schema_version": 1, "task_id": "FNC-DB-002", "status": "review_pending",
        "human_acceptance": "pending", "data_classification": "synthetic_only",
        "compose_project": "fincilia-db-spike", "compose_file": "compose.yaml",
        "database": "fincilia_db_spike",
        "driver": entry("sql/apply_one.sql"),
        "bootstrap": [entry("db/init/001_spike_bootstrap.sql")],
        "migrations": [{"version": version, "name": name,
                        **entry(f"sql/migrations/{version}__{name}.sql")}
                       for version, name, _ in steps],
        "cases": [], "tampered": [], "failing": [],
    }
    for relative in (extra_files or {}):
        if relative.endswith(".sql"):
            manifest["cases"].append(entry(relative))
    write(directory / "MANIFEST.json", json.dumps(manifest, indent=2))
    return directory, manifest


# --------------------------------------------------------------------------- #
# Positivas contra el spike real
# --------------------------------------------------------------------------- #

class RealSpikeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_pos_01_the_real_contract_is_valid(self) -> None:
        self.assertEqual(validate_contract(self.contract, ROOT), [])

    def test_pos_02_the_real_manifest_is_valid(self) -> None:
        self.assertEqual(validate_manifest(self.manifest, SPIKE_ROOT), [])

    def test_pos_03_every_sql_file_is_manifested_with_its_digest(self) -> None:
        declared = {entry["path"]: entry["sha256"]
                    for key in ("migrations", "bootstrap", "cases", "tampered", "failing")
                    for entry in self.manifest[key]}
        declared[self.manifest["driver"]["path"]] = self.manifest["driver"]["sha256"]
        on_disk = {path.relative_to(SPIKE_ROOT).as_posix()
                   for path in SPIKE_ROOT.rglob("*.sql")}
        self.assertEqual(on_disk, set(declared))
        for relative, digest in declared.items():
            self.assertEqual(sha256_file(SPIKE_ROOT / relative), digest, relative)

    def test_pos_04_the_spike_reuses_the_already_adjudicated_image(self) -> None:
        compose = (SPIKE_ROOT / "compose.yaml").read_text(encoding="utf-8")
        local = (ROOT / "infra/local/compose.yaml").read_text(encoding="utf-8")
        pinned = re.search(r"image:\s*(\S+)", compose).group(1)
        self.assertIn(pinned, local)
        self.assertRegex(pinned, r"@sha256:[0-9a-f]{64}$")
        self.assertEqual(pinned, self.contract["environment"]["postgres_image"])

    def test_pos_05_the_spike_publishes_no_host_port(self) -> None:
        compose = (SPIKE_ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("ports:", compose)
        self.assertIn("internal: true", compose)

    def test_pos_06_the_compose_project_is_the_spike_only(self) -> None:
        compose = (SPIKE_ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("name: fincilia-db-spike", compose)
        self.assertEqual(self.manifest["compose_project"], "fincilia-db-spike")

    def test_pos_07_the_bootstrap_creates_three_unprivileged_roles(self) -> None:
        bootstrap = (SPIKE_ROOT / "db/init/001_spike_bootstrap.sql").read_text(encoding="utf-8")
        for token in ("NOSUPERUSER", "NOBYPASSRLS", "NOCREATEDB", "NOCREATEROLE"):
            self.assertEqual(bootstrap.count(token), 2, token)
        for role in ("fnc_spike_migrator", "fnc_spike_runtime"):
            self.assertIn(f"CREATE ROLE {role}", bootstrap)

    def test_pos_08_the_company_scoped_table_forces_row_level_security(self) -> None:
        migration = (SPIKE_ROOT / "sql/migrations/V0001__create_company_ledger.sql"
                     ).read_text(encoding="utf-8")
        self.assertIn("ENABLE ROW LEVEL SECURITY", migration)
        self.assertIn("FORCE ROW LEVEL SECURITY", migration)
        self.assertIn("CREATE POLICY", migration)

    def test_pos_09_the_driver_serialises_with_an_advisory_lock(self) -> None:
        driver = (SPIKE_ROOT / "sql/apply_one.sql").read_text(encoding="utf-8")
        self.assertIn("pg_advisory_xact_lock", driver)
        self.assertIn("FNC_SPIKE_CHECKSUM_MISMATCH", driver)

    def test_pos_10_the_history_records_a_server_side_timestamp(self) -> None:
        bootstrap = (SPIKE_ROOT / "db/init/001_spike_bootstrap.sql").read_text(encoding="utf-8")
        self.assertIn("applied_at  timestamptz NOT NULL DEFAULT now()", bootstrap)
        self.assertIn("GRANT SELECT ON spike.schema_history TO fnc_spike_runtime", bootstrap)

    def test_pos_11_no_migration_contains_a_destructive_statement(self) -> None:
        for entry in self.manifest["migrations"]:
            body = (SPIKE_ROOT / entry["path"]).read_text(encoding="utf-8")
            code = "\n".join(line for line in body.splitlines()
                             if not line.strip().startswith("--"))
            for token in ("DROP TABLE", "DROP SCHEMA", "TRUNCATE", "DELETE FROM"):
                self.assertNotIn(token, code.upper(), entry["path"])

    def test_pos_12_the_contract_neither_selects_a_tool_nor_accepts_adr_002(self) -> None:
        self.assertIsNone(self.contract["tooling_decision"]["selected_tool"])
        self.assertEqual(self.contract["tooling_decision"]["state"], "pending_human")
        self.assertEqual(self.contract["tooling_decision"]["adr_state"], "proposed")

    def test_pos_13_the_contract_declares_the_two_uncovered_matrix_cases(self) -> None:
        relation = self.contract["relation_to_fnc_db_001"]
        self.assertEqual(sorted(relation["not_covered"]), ["DBS-03", "DBS-08"])
        self.assertTrue(relation["not_covered_reason"])


# --------------------------------------------------------------------------- #
# Negativas del manifiesto
# --------------------------------------------------------------------------- #

class ManifestNegativeTests(unittest.TestCase):
    def codes(self, manifest: dict, spike_root: Path) -> set[str]:
        return {item.code for item in validate_manifest(manifest, spike_root)}

    def test_neg_01_the_synthetic_spike_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            self.assertEqual(validate_manifest(manifest, root), [])

    def test_neg_02_a_drifted_checksum_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["sha256"] = "0" * 64
            self.assertIn("MSP-CHECKSUM", self.codes(manifest, root))

    def test_neg_03_a_malformed_checksum_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["sha256"] = "not-a-digest"
            self.assertIn("MSP-CHECKSUM", self.codes(manifest, root))

    def test_neg_04_a_duplicate_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"].append(copy.deepcopy(manifest["migrations"][0]))
            self.assertIn("MSP-VERSION-DUPLICATE", self.codes(manifest, root))

    def test_neg_05_a_version_gap_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory), migrations=[
                ("V0001", "one", "SELECT 1;\n"), ("V0003", "three", "SELECT 3;\n")])
            self.assertIn("MSP-VERSION-GAP", self.codes(manifest, root))

    def test_neg_06_a_malformed_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["version"] = "1"
            self.assertIn("MSP-VERSION-FORMAT", self.codes(manifest, root))

    def test_neg_07_a_filename_that_disagrees_with_the_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["name"] = "renamed_without_moving_the_file"
            self.assertIn("MSP-FILENAME", self.codes(manifest, root))

    def test_neg_08_a_path_escaping_the_spike_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["path"] = "../outside/V0001__escape.sql"
            self.assertIn("MSP-PATH-UNSAFE", self.codes(manifest, root))

    def test_neg_09_an_absolute_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"][0]["path"] = "C:/Windows/win.ini"
            self.assertIn("MSP-PATH-UNSAFE", self.codes(manifest, root))

    def test_neg_10_a_missing_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            (root / manifest["migrations"][0]["path"]).unlink()
            self.assertIn("MSP-FILE-MISSING", self.codes(manifest, root))

    def test_neg_11_an_unmanifested_sql_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            write(root / "sql/migrations/V0003__sneaked_in.sql", "DROP SCHEMA spike;\n")
            self.assertIn("MSP-FILE-NOT-MANIFESTED", self.codes(manifest, root))

    def test_neg_12_a_migration_outside_sql_migrations_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(
                Path(directory), extra_files={"sql/loose.sql": "SELECT 1;\n"})
            manifest["migrations"].append({
                "version": "V0003", "name": "loose", "path": "sql/loose.sql",
                "sha256": sha256_file(root / "sql/loose.sql"), "bytes": 10})
            self.assertIn("MSP-SQL-OUTSIDE", self.codes(manifest, root))

    def test_neg_13_a_destructive_migration_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory), migrations=[
                ("V0001", "create_table", "CREATE TABLE spike.a (id integer);\n"),
                ("V0002", "drop_table", "DROP TABLE spike.a;\n")])
            self.assertIn("MSP-DESTRUCTIVE", self.codes(manifest, root))

    def test_neg_14_a_comment_mentioning_drop_is_not_a_destructive_statement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory), migrations=[
                ("V0001", "create_table",
                 "-- no hacemos DROP TABLE aqui\nCREATE TABLE spike.a (id integer);\n")])
            self.assertNotIn("MSP-DESTRUCTIVE", self.codes(manifest, root))

    def test_neg_15_a_non_transactional_statement_is_refused(self) -> None:
        for statement in ("CREATE INDEX CONCURRENTLY i ON spike.a (id);\n",
                          "VACUUM spike.a;\n",
                          "CREATE DATABASE other;\n"):
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                root, manifest = synthetic_spike(Path(directory), migrations=[
                    ("V0001", "risky", statement)])
                self.assertIn("MSP-NON-TRANSACTIONAL", self.codes(manifest, root))

    def test_neg_16_a_foreign_compose_project_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["compose_project"] = "fincilia-local"
            self.assertIn("MSP-PROJECT", self.codes(manifest, root))

    def test_neg_17_recorded_human_acceptance_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["human_acceptance"] = "accepted"
            self.assertIn("MSP-ACCEPTANCE", self.codes(manifest, root))

    def test_neg_18_an_empty_plan_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            manifest["migrations"] = []
            self.assertIn("MSP-EMPTY-PLAN", self.codes(manifest, root))

    def test_neg_19_a_symlinked_sql_file_is_never_a_spike_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = synthetic_spike(Path(directory))
            link = root / "sql/migrations/V0009__linked.sql"
            try:
                link.symlink_to(root / manifest["migrations"][0]["path"])
            except (OSError, NotImplementedError):
                self.skipTest("this platform does not allow creating symlinks")
            self.assertIn("MSP-PATH-UNSAFE", self.codes(manifest, root))

    def test_neg_20_safe_relative_and_resolve_inside_reject_traversal(self) -> None:
        for candidate in ("/etc/passwd", "C:/Windows/win.ini", "../x.sql", "a/../../b.sql"):
            self.assertFalse(safe_relative(candidate), candidate)
        self.assertIsNone(resolve_inside(SPIKE_ROOT, "../FNC-PLT-001/compose.yaml"))


# --------------------------------------------------------------------------- #
# Plan canonico
# --------------------------------------------------------------------------- #

class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_plan_01_is_ordered_by_version(self) -> None:
        versions = [step["version"] for step in plan(self.manifest)]
        self.assertEqual(versions, sorted(versions))

    def test_plan_02_is_independent_of_manifest_order(self) -> None:
        shuffled = copy.deepcopy(self.manifest)
        shuffled["migrations"] = list(reversed(shuffled["migrations"]))
        self.assertEqual(plan(self.manifest), plan(shuffled))

    def test_plan_03_digest_is_stable_and_changes_with_content(self) -> None:
        first = plan(self.manifest)
        self.assertEqual(plan_digest(first), plan_digest(list(first)))
        mutated = copy.deepcopy(self.manifest)
        mutated["migrations"][0]["sha256"] = "1" * 64
        self.assertNotEqual(plan_digest(first), plan_digest(plan(mutated)))

    def test_plan_04_carries_version_name_path_and_checksum(self) -> None:
        for step in plan(self.manifest):
            self.assertEqual(sorted(step), ["name", "path", "sha256", "version"])
            self.assertTrue(all(step.values()))


# --------------------------------------------------------------------------- #
# Negativas del contrato
# --------------------------------------------------------------------------- #

class ContractNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def codes(self, contract: dict) -> set[str]:
        return {item.code for item in validate_contract(contract, ROOT)}

    def broken(self, **changes) -> dict:
        contract = copy.deepcopy(self.contract)
        for path, value in changes.items():
            keys = path.split("__")
            target = contract
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = value
        return contract

    def test_con_01_selecting_a_tool_is_refused(self) -> None:
        self.assertIn("MSC-TOOLING",
                      self.codes(self.broken(tooling_decision__selected_tool="flyway")))

    def test_con_02_accepting_adr_002_is_refused(self) -> None:
        self.assertIn("MSC-ADR-ACCEPTED",
                      self.codes(self.broken(tooling_decision__adr_state="accepted")))

    def test_con_03_a_tooling_decision_that_is_not_pending_is_refused(self) -> None:
        self.assertIn("MSC-TOOLING",
                      self.codes(self.broken(tooling_decision__state="decided")))

    def test_con_04_an_image_without_a_digest_is_refused(self) -> None:
        self.assertIn("MSC-IMAGE-PIN",
                      self.codes(self.broken(environment__postgres_image="postgres:17.11")))

    def test_con_05_a_floating_image_tag_is_refused(self) -> None:
        self.assertIn("MSC-IMAGE-PIN",
                      self.codes(self.broken(environment__postgres_image="postgres:latest")))

    def test_con_06_publishing_a_host_port_is_refused(self) -> None:
        self.assertIn("MSC-PORT",
                      self.codes(self.broken(environment__publishes_host_port=True)))

    def test_con_07_a_routable_network_is_refused(self) -> None:
        self.assertIn("MSC-NETWORK",
                      self.codes(self.broken(environment__network_internal=False)))

    def test_con_08_collapsing_the_three_roles_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["environment"]["roles"]["migrator"] = \
            contract["environment"]["roles"]["runtime"]
        self.assertIn("MSC-ROLES", self.codes(contract))

    def test_con_09_a_missing_role_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        del contract["environment"]["roles"]["migrator"]
        self.assertIn("MSC-ROLES", self.codes(contract))

    def test_con_10_dropping_atomicity_is_refused(self) -> None:
        self.assertIn("MSC-POLICY",
                      self.codes(self.broken(migration_policy__transaction_per_migration=False)))

    def test_con_11_allowing_destructive_down_migrations_is_refused(self) -> None:
        self.assertIn("MSC-POLICY",
                      self.codes(self.broken(migration_policy__destructive_down_migrations=True)))

    def test_con_12_letting_the_runtime_migrate_is_refused(self) -> None:
        self.assertIn("MSC-POLICY",
                      self.codes(self.broken(migration_policy__runtime_role_can_migrate=True)))

    def test_con_13_letting_the_runtime_own_tables_is_refused(self) -> None:
        self.assertIn("MSC-POLICY",
                      self.codes(self.broken(migration_policy__runtime_role_owns_tables=True)))

    def test_con_14_auto_migrate_on_startup_is_refused(self) -> None:
        self.assertIn("MSC-POLICY",
                      self.codes(self.broken(migration_policy__startup_auto_migrate=True)))

    def test_con_15_a_foreign_cleanup_scope_is_refused(self) -> None:
        self.assertIn("MSC-CLEANUP", self.codes(self.broken(cleanup__scope="fincilia-local")))

    def test_con_16_removing_foreign_volumes_is_refused(self) -> None:
        self.assertIn("MSC-CLEANUP",
                      self.codes(self.broken(cleanup__removes_foreign_volumes=True)))

    def test_con_17_marking_a_gate_as_met_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["gates"][0]["status"] = "met"
        self.assertIn("MSC-GATE", self.codes(contract))

    def test_con_18_recording_gate_acceptance_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["gates"][0]["acceptance"] = "accepted"
        self.assertIn("MSC-GATE", self.codes(contract))

    def test_con_19_fabricated_runtime_evidence_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["cases"][0]["evidence_state"] = "passed"
        self.assertIn("MSC-EVIDENCE-FABRICATED", self.codes(contract))

    def test_con_20_an_unknown_execution_state_is_refused(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["cases"][0]["evidence_state"] = "probably_fine"
        self.assertIn("MSC-EVIDENCE-STATE", self.codes(contract))

    def test_con_21_the_contract_and_the_runner_must_declare_the_same_cases(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["cases"].pop()
        self.assertIn("MSC-CASES", self.codes(contract))

    def test_con_22_claiming_expand_contract_is_proven_is_refused(self) -> None:
        self.assertIn("MSC-EXPAND",
                      self.codes(self.broken(expand_contract__proven_by_this_spike=True)))

    def test_con_23_claiming_this_is_a_production_decision_is_refused(self) -> None:
        self.assertIn("MSC-SCOPE", self.codes(self.broken(is_production_decision=True)))

    def test_con_24_allowing_product_migrations_is_refused(self) -> None:
        self.assertIn("MSC-SCOPE", self.codes(self.broken(product_migrations_allowed=True)))

    def test_con_25_claiming_it_modifies_shared_infrastructure_is_refused(self) -> None:
        self.assertIn("MSC-SCOPE",
                      self.codes(self.broken(modifies_shared_infrastructure=True)))

    def test_con_26_recorded_human_acceptance_is_refused(self) -> None:
        self.assertIn("MSC-ACCEPTANCE", self.codes(self.broken(human_acceptance="accepted")))

    def test_con_27_empty_limits_or_anti_promises_are_refused(self) -> None:
        self.assertIn("MSC-LIMITS", self.codes(self.broken(limits=[])))
        self.assertIn("MSC-ANTI-PROMISES", self.codes(self.broken(anti_promises=[])))

    def test_con_28_a_spike_root_outside_the_repository_is_refused(self) -> None:
        self.assertIn("MSC-PATH-UNSAFE", self.codes(self.broken(spike_root="../elsewhere")))


# --------------------------------------------------------------------------- #
# Capa de proceso: dobles y comandos locales inocuos
# --------------------------------------------------------------------------- #

class ProcessLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = dict(ADAPTERS[0])
        self.lab = SpikeLab(self.adapter, SPIKE_ROOT)

    def test_proc_01_every_compose_argv_pins_the_project_and_file(self) -> None:
        for arguments in (("up", "-d"), ("down", "--volumes"), ("config", "--quiet")):
            argv = self.lab.compose_argv(*arguments)
            self.assertEqual(argv[argv.index("-p") + 1], "fincilia-db-spike")
            self.assertTrue(argv[argv.index("-f") + 1].endswith(
                "spikes/FNC-DB-002/compose.yaml"))

    def test_proc_02_a_foreign_compose_project_is_refused(self) -> None:
        with self.assertRaises(SpikeRunnerError):
            SpikeLab(self.adapter, SPIKE_ROOT, project="fincilia-local")

    def test_proc_03_a_compose_file_outside_the_spike_is_refused(self) -> None:
        with self.assertRaises(SpikeRunnerError):
            SpikeLab(self.adapter, SPIKE_ROOT, compose_file="../FNC-PLT-001/compose.yaml")

    def test_proc_04_a_script_outside_the_container_sql_root_is_refused(self) -> None:
        with self.assertRaises(SpikeRunnerError):
            self.lab.psql_argv("fnc_spike_migrator", "/etc/passwd")

    def test_proc_05_a_traversing_script_path_is_refused(self) -> None:
        for candidate in ("../../etc/passwd", "db/init/001_spike_bootstrap.sql",
                          "sql/../../escape.sql"):
            with self.assertRaises(SpikeRunnerError):
                self.lab.container_script(candidate)

    def test_proc_06_psql_always_runs_in_a_single_transaction_with_error_stop(self) -> None:
        argv = self.lab.psql_argv("fnc_spike_migrator", "/spike/sql/apply_one.sql")
        self.assertIn("--single-transaction", argv)
        self.assertIn("ON_ERROR_STOP=1", argv)
        self.assertIn("-T", argv)

    def test_proc_07_psql_variables_are_sorted_for_determinism(self) -> None:
        first = self.lab.psql_argv("r", "/spike/sql/apply_one.sql",
                                   {"b": "2", "a": "1", "c": "3"})
        second = self.lab.psql_argv("r", "/spike/sql/apply_one.sql",
                                    {"c": "3", "a": "1", "b": "2"})
        self.assertEqual(first, second)

    def test_proc_08_shell_metacharacters_in_argv_are_refused(self) -> None:
        for poisoned in ("docker && rm -rf /", "docker; whoami", "docker `id`",
                         "docker $(id)"):
            with self.assertRaises(SpikeRunnerError):
                run_argv([poisoned])

    def test_proc_09_a_non_list_argv_is_refused(self) -> None:
        with self.assertRaises(SpikeRunnerError):
            run_argv([])
        with self.assertRaises(SpikeRunnerError):
            run_argv([1, 2])  # type: ignore[list-item]

    def test_proc_10_the_environment_drops_proxies_and_tokens(self) -> None:
        env = build_environment({"PATH": "p", "HTTP_PROXY": "http://proxy",
                                 "AWS_SECRET_ACCESS_KEY": "sk", "GITHUB_TOKEN": "gh",
                                 "PGPASSWORD": "secret"})
        self.assertEqual(env, {"PATH": "p"})

    def test_proc_11_windows_paths_translate_only_for_the_wsl_adapter(self) -> None:
        windows = Path("C:/Users/example/repo/compose.yaml")
        self.assertEqual(to_wsl_path(windows), "/mnt/c/Users/example/repo/compose.yaml")
        direct = {"id": "direct", "translate_paths": False}
        wsl = {"id": "wsl", "translate_paths": True}
        self.assertEqual(host_path(direct, windows), "C:/Users/example/repo/compose.yaml")
        self.assertEqual(host_path(wsl, windows), "/mnt/c/Users/example/repo/compose.yaml")

    def test_proc_12_a_posix_path_is_left_alone(self) -> None:
        self.assertEqual(to_wsl_path(Path("/srv/repo/compose.yaml")),
                         "/srv/repo/compose.yaml")

    def test_proc_13_a_timeout_is_reported_as_timeout_not_as_failure(self) -> None:
        execution = run_argv([sys.executable, "-c", "__import__('time').sleep(5)"], timeout=1)
        self.assertEqual(execution.status, "timeout")
        self.assertIsNone(execution.exit_code)

    def test_proc_14_a_missing_binary_is_reported_as_unavailable(self) -> None:
        execution = run_argv(["fincilia-command-that-does-not-exist", "--version"])
        self.assertEqual(execution.status, "unavailable")

    def test_proc_15_output_beyond_the_cap_is_marked_truncated(self) -> None:
        execution = run_argv([sys.executable, "-c", "print('x' * 5000)"], cap=100)
        self.assertTrue(execution.truncated)
        self.assertLessEqual(len(execution.stdout), 100)

    def test_proc_16_the_execution_manifest_hides_output_by_default(self) -> None:
        # El valor viaja por stdin para que NO aparezca en el argv: el argv si se
        # registra a proposito, porque sin el no se puede reproducir la ejecucion.
        execution = run_argv([sys.executable, "-c", "print(input())"],
                             stdin_text="sensitive-synthetic-value\n")
        payload = json.dumps(execution.as_dict(), ensure_ascii=False)
        self.assertNotIn("sensitive-synthetic-value", payload)
        self.assertIn("sensitive-synthetic-value",
                      json.dumps(execution.as_dict(include_output=True)))

    def test_proc_17_probe_adapter_returns_none_when_nothing_answers(self) -> None:
        self.assertIsNone(probe_adapter(adapters=(NULL_ADAPTER,)))

    def test_proc_18_probe_adapter_picks_the_first_that_answers(self) -> None:
        working = {"id": "fake", "prefix": ("x",),
                   "probe": (sys.executable, "-c", "print('9.9.9')"),
                   "translate_paths": False}
        adapter = probe_adapter(adapters=(NULL_ADAPTER, working))
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter["id"], "fake")
        self.assertEqual(adapter["server_version"], "9.9.9")


# --------------------------------------------------------------------------- #
# Veredictos del suite y casos estaticos
# --------------------------------------------------------------------------- #

class SuiteVerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def completed(self, exit_code: int, out: str = "", err: str = "",
                  truncated: bool = False) -> Execution:
        return Execution(("x",), exit_code, out, err, truncated, "completed")

    def test_ver_01_a_denial_that_succeeds_is_a_failure(self) -> None:
        result = _expect_failure("DBS-RLS", self.completed(0), "policy")
        self.assertEqual(result.outcome, "fail")

    def test_ver_02_failing_for_another_reason_is_not_a_pass(self) -> None:
        result = _expect_failure("DBS-RLS", self.completed(3, err="syntax error"), "policy")
        self.assertEqual(result.outcome, "fail")
        self.assertIn("not for the declared reason", result.detail)

    def test_ver_03_failing_for_the_declared_reason_is_a_pass(self) -> None:
        result = _expect_failure(
            "DBS-RLS", self.completed(3, err="row-level security policy"),
            "row-level security policy")
        self.assertEqual(result.outcome, "pass")

    def test_ver_04_a_timeout_is_an_error_not_a_pass(self) -> None:
        timed_out = Execution(("x",), None, "", "", False, "timeout")
        self.assertEqual(_expect_success("DBS-BLANK", [timed_out], "OK").outcome, "error")
        self.assertEqual(_expect_failure("DBS-RLS", timed_out, "policy").outcome, "error")

    def test_ver_05_truncated_output_is_an_error_not_a_pass(self) -> None:
        truncated = self.completed(0, out="FNC_SPIKE_OK head_state", truncated=True)
        self.assertEqual(_expect_success("DBS-BLANK", [truncated], "OK").outcome, "error")

    def test_ver_06_a_success_without_its_marker_is_a_failure(self) -> None:
        result = _expect_success("DBS-BLANK", [self.completed(0, out="nothing useful")],
                                 "FNC_SPIKE_OK head_state")
        self.assertEqual(result.outcome, "fail")
        self.assertIn("never emitted", result.detail)

    def test_ver_07_checksum_order_case_passes_on_the_real_manifest(self) -> None:
        self.assertEqual(case_checksum_order(self.manifest).outcome, "pass")

    def test_ver_08_unknown_migration_case_passes_on_the_real_manifest(self) -> None:
        self.assertEqual(case_unknown_migration(self.manifest, SPIKE_ROOT).outcome, "pass")

    def test_ver_09_cleanup_scope_case_passes_without_any_runtime(self) -> None:
        self.assertEqual(case_cleanup_scope(None, SPIKE_ROOT, None).outcome, "pass")

    def test_ver_10_the_static_cases_run_without_a_container_runtime(self) -> None:
        results = static_cases(self.manifest, SPIKE_ROOT)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(item.outcome == "pass" for item in results))

    def test_ver_11_the_catalogue_covers_the_twelve_required_invariants(self) -> None:
        self.assertEqual(len(CASE_CATALOGUE), 12)
        self.assertEqual(sum(1 for item in CASE_CATALOGUE if item["kind"] == "static"), 3)
        self.assertEqual(sum(1 for item in CASE_CATALOGUE if item["kind"] == "runtime"), 9)


# --------------------------------------------------------------------------- #
# CLI y disciplina del codigo fuente
# --------------------------------------------------------------------------- #

class CliAndSourceTests(unittest.TestCase):
    def test_cli_01_validate_succeeds_on_the_real_contract(self) -> None:
        code, payload = run_cli(["validate"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["structural_valid"])

    def test_cli_02_plan_never_mutates_anything(self) -> None:
        before = sha256_file(MANIFEST_PATH)
        code, payload = run_cli(["plan"])
        self.assertEqual(code, 0)
        self.assertFalse(payload["mutates_anything"])
        self.assertEqual(sha256_file(MANIFEST_PATH), before)

    def test_cli_03_report_does_not_fabricate_runtime_evidence(self) -> None:
        _, payload = run_cli(["report"])
        for row in payload["cases"]:
            self.assertEqual(row["declared_evidence_state"], "not_executed")
        self.assertIsNone(payload["aggregate_score"])

    def test_cli_04_report_keeps_the_limits_and_anti_promises_visible(self) -> None:
        _, payload = run_cli(["report"])
        self.assertTrue(payload["limits"])
        self.assertTrue(payload["anti_promises"])
        self.assertIsNone(payload["tooling_decision"]["selected_tool"])

    def test_cli_05_a_traversing_root_is_refused(self) -> None:
        code, _ = run_cli(["--root", "../outside", "validate"])
        self.assertEqual(code, 2)

    def test_cli_06_an_unreadable_contract_fails_operationally(self) -> None:
        code, _ = run_cli(["--contract", str(ROOT / "docs/database/absent.json"), "validate"])
        self.assertEqual(code, 2)

    def test_cli_07_static_suite_runs_without_touching_docker(self) -> None:
        code, payload = run_cli(["run", "--suite", "static"])
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual(payload["lifecycle"], [])

    def test_cli_08_the_cli_never_claims_adr_002_is_accepted(self) -> None:
        _, payload = run_cli(["run", "--suite", "static"])
        self.assertFalse(payload["adr_002_accepted"])

    def test_src_01_no_shell_eval_or_exec_in_the_tool(self) -> None:
        forbidden = ("shell=True", "eval(", "exec(", "os.system", "import random",
                     "datetime.now(", "time.time(")
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_validate.py":
                continue
            text = source.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_02_no_anonymous_todo_survives(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_validate.py":
                continue
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)

    def test_src_03_no_password_literal_leaves_the_spike_directory(self) -> None:
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_validate.py":
                continue
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("_only'", text, source.name)
            self.assertNotIn("PGPASSWORD", text, source.name)


if __name__ == "__main__":
    unittest.main()
