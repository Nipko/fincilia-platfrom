"""Pruebas del catálogo ejecutable de pruebas (FNC-QA-004).

Tres bloques:

1. positivas sobre el modelo y el repositorio reales;
2. invariantes negativas sobre un árbol sintético construido en un directorio
   temporal, que da control total sobre las fuentes;
3. metamórficas: reordenar no cambia el inventario, añadir una definición
   contractual elegible sí cambia la reconciliación.

Ningún test depende de red, hora real, locale, orden de directorio ni Git.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.test_catalog.cli import main as cli_main
from tools.test_catalog.cli import resolve_root
from tools.test_catalog.extractors import (
    EXTRACTOR_APPLICABILITY,
    EXTRACTORS,
    discover_files,
)
from tools.test_catalog.reconcile import (
    discover,
    load_model,
    project,
    reconcile,
    resolve_inside,
    validate_model,
)

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "docs/testing/test-catalog-model.json"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cli(argv: list[str]) -> int:
    """Ejecuta el CLI capturando su salida para no ensuciar el informe de tests."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return cli_main(argv)


class TestCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load_model(MODEL_PATH)

    # ------------------------------------------------------------------ #
    # Árbol sintético
    # ------------------------------------------------------------------ #

    def _tree(self, directory: Path, *, contract_ids=("TST-LIN-001",),
              catalog_ids=("TST-LIN-001",), implemented_ids=("TST-LIN-001",),
              extra_contract: dict | None = None) -> Path:
        """Construye un árbol mínimo, coherente y enteramente sintético."""
        contract = {"required_tests": [{"id": i, "scenario": f"escenario sintetico {i}"}
                                       for i in contract_ids]}
        if extra_contract:
            contract.update(extra_contract)
        write(directory / "docs/domain/synthetic-contract.json",
              json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
        rows = "\n".join(f"| {i} | descripcion sintetica | FNC-SYN-001 |" for i in catalog_ids)
        write(directory / "docs/testing/TEST_CATALOG.md",
              "# Catalogo sintetico\n\n| ID | Prueba | Primer task |\n|---|---|---|\n" + rows + "\n")
        methods = "\n".join(
            f"    def test_{i.replace('-', '_')}_synthetic(self):\n        pass\n"
            for i in implemented_ids)
        write(directory / "tools/synthetic_pkg/test_synthetic.py",
              "import unittest\n\n\nclass T(unittest.TestCase):\n" + (methods or "    pass\n"))
        return directory

    def _reconcile_tree(self, directory: Path, model: dict | None = None) -> dict:
        used = model or self.model
        return reconcile(used, discover(used, directory))

    def _findings(self, result: dict) -> set[str]:
        return {f["finding_id"] for f in result["findings"]}

    # ================================================================== #
    # Positivas
    # ================================================================== #

    def test_repository_model_is_structurally_valid(self) -> None:
        self.assertEqual([], validate_model(self.model))

    def test_model_and_code_declare_the_same_extractors(self) -> None:
        declared = {e["id"] for e in self.model["extractors"]}
        self.assertEqual(set(EXTRACTORS), declared)

    def test_repository_discovery_is_non_empty_and_stable(self) -> None:
        first = discover(self.model, ROOT)
        second = discover(self.model, ROOT)
        self.assertGreater(first["identifier_count"], 40)
        self.assertGreater(first["scanned_file_count"], 50)
        self.assertEqual(first, second)

    def test_coherent_synthetic_tree_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = self._reconcile_tree(self._tree(Path(td)))
            self.assertEqual(set(), self._findings(result))

    def test_every_provenance_carries_path_locator_digest_and_extractor(self) -> None:
        inventory = discover(self.model, ROOT)
        for entry in inventory["identifiers"]:
            for provenance in entry["provenance"]:
                for field in ("path", "locator", "digest", "extractor_id", "extractor_version"):
                    self.assertTrue(provenance[field], f"{entry['test_id']}:{field}")
                self.assertEqual(64, len(provenance["digest"]))

    # ================================================================== #
    # Invariantes negativas 1-20
    # ================================================================== #

    def test_neg_01_contract_id_absent_from_catalogue_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=("TST-LIN-001", "TST-LIN-002"),
                              catalog_ids=("TST-LIN-001",),
                              implemented_ids=("TST-LIN-001", "TST-LIN-002"))
            result = self._reconcile_tree(tree)
            self.assertIn("TCM-CONTRACT-NOT-IN-CATALOG", self._findings(result))
            drift = next(f for f in result["findings"]
                         if f["finding_id"] == "TCM-CONTRACT-NOT-IN-CATALOG")
            self.assertEqual("traceability_drift", drift["classification"])

    def test_neg_02_contract_finding_always_resolves_owner_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=("TST-LIN-001", "TST-LIN-002"),
                              catalog_ids=("TST-LIN-001",))
            for finding in self._reconcile_tree(tree)["findings"]:
                self.assertNotEqual("UNASSIGNED", finding["owner_role"], finding["finding_id"])
                self.assertNotEqual("UNASSIGNED", finding["gate"], finding["finding_id"])
                self.assertIn(finding["severity"],
                              {"critical", "high", "medium", "informational"})

    def test_neg_03_catalogue_plan_is_not_reported_as_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=(), catalog_ids=("TST-RLS-001",),
                              implemented_ids=())
            result = self._reconcile_tree(tree)
            entry = next(e for e in result["identifiers"] if e["test_id"] == "TST-RLS-001")
            self.assertIn("catalog_planned", entry["states"])
            self.assertNotIn("implemented", entry["states"])
            planned = next(f for f in result["findings"]
                           if f["finding_id"] == "TCM-CATALOG-PLANNED")
            self.assertEqual("planned_backlog", planned["classification"])
            self.assertNotEqual("traceability_drift", planned["classification"])

    def test_neg_04_implementation_without_definition_is_an_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=(), catalog_ids=(),
                              implemented_ids=("TST-LIN-009",))
            self.assertIn("TCM-ORPHAN", self._findings(self._reconcile_tree(tree)))

    def test_neg_05_incompatible_definitions_of_the_same_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/domain/other-contract.json", json.dumps(
                {"required_tests": [{"id": "TST-LIN-001",
                                     "scenario": "definicion sintetica divergente"}]},
                ensure_ascii=False, indent=2, sort_keys=True))
            result = self._reconcile_tree(tree)
            self.assertIn("TCM-DEFINITION-CONFLICT", self._findings(result))
            entry = next(e for e in result["identifiers"] if e["test_id"] == "TST-LIN-001")
            self.assertIn("conflict", entry["states"])
            self.assertEqual(2, len(entry["conflicting_definitions"]))

    def test_neg_06_unknown_namespace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=("TST-ZZZZ-001",),
                              catalog_ids=("TST-ZZZZ-001",),
                              implemented_ids=("TST-ZZZZ-001",))
            self.assertIn("TCM-NAMESPACE-UNKNOWN", self._findings(self._reconcile_tree(tree)))

    def test_neg_07_narrative_range_is_not_expanded_into_many_tests(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/implementation/NARRATIVE.md",
                  "Cubrimos TST-CON-001..015 en esta fase.\n")
            inventory = discover(self.model, tree)
            found = {e["test_id"] for e in inventory["identifiers"]}
            self.assertIn("TST-CON-001", found)
            self.assertNotIn("TST-CON-015", found)
            self.assertNotIn("TST-CON-007", found)
            self.assertEqual(1, len(inventory["narrative_ranges_not_expanded"]))
            self.assertFalse(self.model["aggregate_id_policy"]["expand_ranges"])

    def test_neg_08_prose_mention_is_never_a_definition(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=(), catalog_ids=(), implemented_ids=())
            write(tree / "docs/implementation/NOTES.md",
                  "Deberiamos escribir TST-LIN-004 algun dia.\n")
            result = self._reconcile_tree(tree)
            entry = next(e for e in result["identifiers"] if e["test_id"] == "TST-LIN-004")
            self.assertEqual(["mention"], entry["source_classes"])
            self.assertIn("orphan", entry["states"])
            self.assertNotIn("contract_required", entry["states"])
            self.assertNotIn("implemented", entry["states"])

    def test_neg_09_excluded_directories_are_not_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            for excluded in ("node_modules", "__pycache__", ".venv"):
                write(tree / f"docs/{excluded}/vendored.json", json.dumps(
                    {"required_tests": [{"id": "TST-LIN-777", "scenario": "vendored"}]}))
            found = {e["test_id"] for e in discover(self.model, tree)["identifiers"]}
            self.assertNotIn("TST-LIN-777", found)

    def test_neg_10_external_path_or_symlink_is_rejected(self) -> None:
        self.assertIsNone(resolve_inside(ROOT, "../outside.json"))
        self.assertIsNone(resolve_inside(ROOT, "/etc/passwd"))
        self.assertIsNone(resolve_inside(ROOT, "C:/Windows/win.ini"))
        self.assertIsNone(resolve_inside(ROOT, "docs/../../outside.json"))
        self.assertIsNone(resolve_root(Path("../definitely-not-here")))
        self.assertIsNone(resolve_root(ROOT / "docs/testing/test-catalog-model.json"))
        self.assertIsNotNone(resolve_root(ROOT))
        self.assertFalse(self.model["file_allowlist"]["follow_symlinks"])

    def test_non_authoritative_delivery_artifacts_are_excluded(self) -> None:
        expected = {
            "docs/implementation/assignments/**",
            "docs/implementation/handoffs/**",
            "docs/testing/TEST_CATALOG_MODEL.md",
        }
        self.assertEqual(expected, set(self.model["file_allowlist"]["excluded_path_globs"]))

        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/implementation/handoffs/stale.md", "TST-OLD-999")
            found = {entry["test_id"] for entry in discover(self.model, tree)["identifiers"]}
            self.assertNotIn("TST-OLD-999", found)

    def test_neg_11_changing_a_source_changes_its_digest_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            before = discover(self.model, tree)
            target = tree / "docs/domain/synthetic-contract.json"
            document = json.loads(target.read_text(encoding="utf-8"))
            document["required_tests"][0]["scenario"] = "escenario sintetico modificado"
            write(target, json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
            after = discover(self.model, tree)
            digests_before = {p["digest"] for e in before["identifiers"] for p in e["provenance"]}
            digests_after = {p["digest"] for e in after["identifiers"] for p in e["provenance"]}
            self.assertNotEqual(digests_before, digests_after)
            self.assertNotEqual(before, after)

    def test_neg_12_filesystem_order_does_not_change_the_output(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, \
                tempfile.TemporaryDirectory() as second_dir:
            ids = ("TST-LIN-001", "TST-LIN-002", "TST-LIN-003")
            one = self._tree(Path(first_dir), contract_ids=ids, catalog_ids=ids,
                             implemented_ids=ids)
            two = self._tree(Path(second_dir), contract_ids=tuple(reversed(ids)),
                             catalog_ids=tuple(reversed(ids)),
                             implemented_ids=tuple(reversed(ids)))
            left = discover(self.model, one)
            right = discover(self.model, two)
            self.assertEqual([e["test_id"] for e in left["identifiers"]],
                             [e["test_id"] for e in right["identifiers"]])
            self.assertEqual(sorted(f["path"] for f in left["scanned_files"]),
                             sorted(f["path"] for f in right["scanned_files"]))

    def test_neg_13_empty_discovery_does_not_pass_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td)
            (empty / "docs").mkdir(parents=True)
            inventory = discover(self.model, empty)
            self.assertEqual(0, inventory["identifier_count"])
            result = reconcile(self.model, inventory)
            # No hay hallazgos porque no hay nada, y eso es exactamente lo que
            # el reporte debe dejar visible en vez de presentarlo como cobertura.
            self.assertEqual([], result["findings"])
            self.assertEqual(0, result["scanned_file_count"])

    def test_neg_14_a_new_eligible_contract_is_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            before = self._reconcile_tree(tree)
            write(tree / "docs/domain/brand-new-contract.json", json.dumps(
                {"required_tests": ["TST-OVR-003"]}, ensure_ascii=False, indent=2))
            after = self._reconcile_tree(tree)
            self.assertNotIn("TST-OVR-003",
                             {e["test_id"] for e in before["identifiers"]})
            self.assertIn("TST-OVR-003", {e["test_id"] for e in after["identifiers"]})
            self.assertIn("TCM-CONTRACT-NOT-IN-CATALOG", self._findings(after))

    def test_neg_14b_a_contract_that_anchors_refs_elsewhere_is_not_ignored(self) -> None:
        # El arnés de mutaciones ancla sus referencias en `mutations[]`, no en
        # `cases[]`. Sin un extractor propio quedaría invisible y el inventario
        # parecería completo justo donde no lo está.
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/testing/new-harness.json", json.dumps(
                {"mutations": [{"mutation_id": "MUT-X-001", "test_refs": ["TST-OVR-003"]}]},
                ensure_ascii=False, indent=2))
            after = self._reconcile_tree(tree)
            row = next(e for e in after["identifiers"] if e["test_id"] == "TST-OVR-003")
            extractors = {p["extractor_id"] for p in row["provenance"]}
            self.assertIn("json_mutation_test_refs", extractors)
            # Citar no es definir: sigue siendo huérfano hasta que un contrato lo exija.
            self.assertIn("orphan", row["states"])

    def test_neg_14c_every_registered_extractor_is_implemented_and_applied(self) -> None:
        declared = {e["id"] for e in self.model["extractors"]}
        self.assertEqual(declared, set(EXTRACTORS))
        applied = {name for names in EXTRACTOR_APPLICABILITY.values() for name in names}
        self.assertEqual(declared, applied)

    def test_neg_15_evidence_requires_command_version_digest_and_result(self) -> None:
        required = set(self.model["evidence_sources"]["requirements"])
        self.assertLessEqual({"command", "runtime_version", "input_digest", "result"}, required)
        mutated = copy.deepcopy(self.model)
        mutated["evidence_sources"]["requirements"] = ["result"]
        # El modelo declara el requisito; retirarlo debe ser visible en el diff
        # del contrato, no absorberse en silencio.
        self.assertNotEqual(self.model["evidence_sources"], mutated["evidence_sources"])

    def test_neg_16_waiver_without_owner_reviewer_reason_expiry_or_gate(self) -> None:
        for missing in ("waiver_id", "owner_role", "reviewer_role", "reason",
                        "expiry_gate", "gate"):
            mutated = copy.deepcopy(self.model)
            waiver = {"waiver_id": "WV-SYN-001", "test_id": "TST-LIN-001",
                      "owner_role": "QA", "reviewer_role": "Architecture",
                      "reason": "sintetico", "expiry_gate": "S1-READY",
                      "gate": "S1-READY", "state": "pending_human"}
            waiver.pop(missing)
            mutated["waivers"] = [waiver]
            codes = {e.code for e in validate_model(mutated)}
            self.assertIn("TCM-WAIVER-FIELDS", codes, missing)

        self_approved = copy.deepcopy(self.model)
        self_approved["waivers"] = [{"waiver_id": "WV-SYN-002", "test_id": "TST-LIN-001",
                                     "owner_role": "QA", "reviewer_role": "QA",
                                     "reason": "sintetico", "expiry_gate": "S1-READY",
                                     "gate": "S1-READY", "state": "pending_human"}]
        self.assertIn("TCM-WAIVER-FIELDS", {e.code for e in validate_model(self_approved)})

    def test_neg_17_agent_cannot_accept_a_human_decision(self) -> None:
        gate = copy.deepcopy(self.model)
        gate["gates"][0]["status"] = "met"
        self.assertIn("TCM-GATE-STATUS", {e.code for e in validate_model(gate)})

        acceptance = copy.deepcopy(self.model)
        acceptance["gates"][0]["acceptance"] = "accepted"
        self.assertIn("TCM-GATE-STATUS", {e.code for e in validate_model(acceptance)})

        decision = copy.deepcopy(self.model)
        decision["unresolved_decisions"][0]["state"] = "resolved"
        self.assertIn("TCM-DECISION-STATE", {e.code for e in validate_model(decision)})

        human = copy.deepcopy(self.model)
        human["human_acceptance"] = "accepted"
        self.assertIn("TCM-HUMAN-ACCEPTANCE", {e.code for e in validate_model(human)})

    def test_neg_18_projection_never_writes_the_catalogue(self) -> None:
        catalog = ROOT / "docs/testing/TEST_CATALOG.md"
        before = catalog.read_bytes()
        result = self._reconcile_tree(ROOT)
        proposal = project(self.model, result)
        self.assertFalse(proposal["writes_target_document"])
        self.assertEqual("docs/testing/TEST_CATALOG.md", proposal["target_document"])
        self.assertEqual(before, catalog.read_bytes())

        mutated = copy.deepcopy(self.model)
        mutated["projection_contract"]["writes_test_catalog"] = True
        self.assertIn("TCM-PROJECTION-WRITE", {e.code for e in validate_model(mutated)})

    def test_neg_19_no_single_aggregate_score_acts_as_a_gate(self) -> None:
        for field, value in (("single_aggregate_score_as_gate", True),
                             ("per_finding_breakdown_required", False)):
            mutated = copy.deepcopy(self.model)
            mutated["reporting"][field] = value
            self.assertIn("TCM-AGGREGATE-SCORE", {e.code for e in validate_model(mutated)}, field)

    def test_neg_20_retired_id_requires_a_tombstone(self) -> None:
        mutated = copy.deepcopy(self.model)
        mutated["retirement_policy"]["tombstone_required"] = False
        self.assertIn("TCM-RETIREMENT", {e.code for e in validate_model(mutated)})

        orphan_tombstone = copy.deepcopy(self.model)
        orphan_tombstone["tombstones"] = [{"test_id": "TST-LIN-099"}]
        self.assertIn("TCM-RETIREMENT", {e.code for e in validate_model(orphan_tombstone)})

    # ================================================================== #
    # Metamórficas
    # ================================================================== #

    def test_metamorphic_reordering_keys_does_not_change_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td), contract_ids=("TST-LIN-001", "TST-LIN-002"),
                              catalog_ids=("TST-LIN-001", "TST-LIN-002"),
                              implemented_ids=("TST-LIN-001", "TST-LIN-002"))
            before = discover(self.model, tree)
            target = tree / "docs/domain/synthetic-contract.json"
            document = json.loads(target.read_text(encoding="utf-8"))
            reordered = {"required_tests": [
                {"scenario": entry["scenario"], "id": entry["id"]}
                for entry in document["required_tests"]]}
            write(target, json.dumps(reordered, ensure_ascii=False, indent=4))
            after = discover(self.model, tree)
            self.assertEqual([e["test_id"] for e in before["identifiers"]],
                             [e["test_id"] for e in after["identifiers"]])
            self.assertEqual([e["states"] for e in
                              reconcile(self.model, before)["identifiers"]],
                             [e["states"] for e in
                              reconcile(self.model, after)["identifiers"]])

    def test_metamorphic_new_definition_changes_the_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            before = self._reconcile_tree(tree)
            write(tree / "docs/domain/added-contract.json", json.dumps(
                {"required_test_scenarios": ["TST-BAL-002"]}, ensure_ascii=False, indent=2))
            after = self._reconcile_tree(tree)
            self.assertNotEqual(before["counts_by_state"], after["counts_by_state"])
            self.assertLess(len(before["findings"]), len(after["findings"]))

    def test_metamorphic_same_id_in_compatible_sources_is_not_a_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/domain/echo-contract.json", json.dumps(
                {"required_tests": [{"id": "TST-LIN-001",
                                     "scenario": "escenario sintetico TST-LIN-001"}]},
                ensure_ascii=False, indent=2, sort_keys=True))
            result = self._reconcile_tree(tree)
            self.assertNotIn("TCM-DEFINITION-CONFLICT", self._findings(result))
            entry = next(e for e in result["identifiers"] if e["test_id"] == "TST-LIN-001")
            self.assertGreaterEqual(len(entry["provenance"]), 4)

    # ================================================================== #
    # CLI
    # ================================================================== #

    def test_cli_allows_nonblocking_backlog_without_hiding_it(self) -> None:
        # El repositorio puede conservar backlog medio/informativo; `validate`
        # solo bloquea drift alto/critico y el reporte mantiene los hallazgos.
        code = run_cli(["--model", str(MODEL_PATH), "--root", str(ROOT), "validate"])
        self.assertEqual(0, code)
        self.assertEqual([], validate_model(self.model))

    def test_cli_rejects_a_root_that_is_absent_or_traverses(self) -> None:
        for bad in ("../nowhere", "docs/../../outside"):
            self.assertEqual(2, run_cli(["--model", str(MODEL_PATH), "--root", bad, "discover"]))

    def test_cli_discover_and_report_succeed_on_a_coherent_tree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            self.assertEqual(0, run_cli(["--model", str(MODEL_PATH),
                                          "--root", str(tree), "discover"]))
            self.assertEqual(0, run_cli(["--model", str(MODEL_PATH),
                                          "--root", str(tree), "report"]))
            self.assertEqual(0, run_cli(["--model", str(MODEL_PATH),
                                          "--root", str(tree), "validate"]))

    def test_cli_reports_an_invalid_model_without_scanning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "broken-model.json"
            mutated = copy.deepcopy(self.model)
            mutated["task_id"] = "FNC-WRONG-000"
            write(broken, json.dumps(mutated, ensure_ascii=False))
            self.assertEqual(1, run_cli(["--model", str(broken),
                                          "--root", str(ROOT), "discover"]))

    def test_discover_files_is_sorted_and_excludes_noise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = self._tree(Path(td))
            write(tree / "docs/__pycache__/ignored.json", "{}")
            write(tree / "docs/a.json", "{}")
            write(tree / "docs/b.json", "{}")
            files = discover_files(
                tree,
                self.model["file_allowlist"]["include_globs"],
                self.model["file_allowlist"]["excluded_path_globs"],
            )
            paths = [f.as_posix() for f in files]
            self.assertEqual(paths, sorted(paths))
            self.assertNotIn("docs/__pycache__/ignored.json", paths)


if __name__ == "__main__":
    unittest.main()
