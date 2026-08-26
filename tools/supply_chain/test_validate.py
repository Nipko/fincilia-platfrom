"""Pruebas del baseline de cadena de suministro (FNC-SUP-001).

Tres bloques:

1. positivas contra el modelo y el repositorio reales;
2. invariantes negativas sobre un árbol sintético en un directorio temporal, que
   da control total sobre las fuentes;
3. metamórficas y de determinismo.

Ningún test depende de red, hora real, locale, orden de directorio ni Git.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.supply_chain import cli as supply_cli
from tools.supply_chain.discovery import (
    collect_files,
    discover,
    resolve_inside,
    safe_relative,
    unsupported_yaml_constructs,
)
from tools.supply_chain.rules import Finding, reconcile, validate_model

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs/security/supply-chain.json"
SOURCE_DIR = ROOT / "tools/supply_chain"

WORKFLOW = ".github/workflows/ci.yml"
COMPOSE = "infra/synthetic/compose.yaml"
MANIFEST = "spikes/SYN-001/api/package.json"
LOCKFILE = "spikes/SYN-001/api/package-lock.json"
MONITOR = ".github/dependabot.yml"

GOOD_SHA = "a" * 40
GOOD_DIGEST = "b" * 64


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cli(argv: list[str]) -> tuple[int, dict]:
    """Ejecuta el CLI capturando su salida para no ensuciar el informe de tests."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = supply_cli.main(argv)
    text = out.getvalue() or err.getvalue()
    return code, (json.loads(text) if text.strip() else {})


def workflow_yaml(*, action_ref: str = GOOD_SHA, python_version: str = "3.12",
                  runner: str = "ubuntu-24.04",
                  install: str = "npm ci --ignore-scripts") -> str:
    return f"""name: synthetic
on: [push]
jobs:
  build:
    runs-on: {runner}
    steps:
      - name: Checkout
        uses: actions/checkout@{action_ref}
      - name: Set up Python
        uses: actions/setup-python@{GOOD_SHA}
        with:
          python-version: "{python_version}"
      - name: Install
        run: {install}
"""


def compose_yaml(image: str = f"postgres:17.11-alpine3.24@sha256:{GOOD_DIGEST}") -> str:
    return f"""name: synthetic-stack

services:
  db:
    image: {image}
"""


def manifest_json(*, lifecycle: bool = False) -> str:
    scripts = {"test": "vitest"}
    if lifecycle:
        scripts["postinstall"] = "node ./scripts/after.js"
    return json.dumps({
        "name": "@fincilia/synthetic",
        "version": "0.0.0",
        "scripts": scripts,
        "dependencies": {"pg": "8.11.3"},
    }, indent=2)


def lockfile_json() -> str:
    return json.dumps({"name": "@fincilia/synthetic", "lockfileVersion": 3,
                       "packages": {}}, indent=2)


def monitor_yaml(entries: list[tuple[str, str]]) -> str:
    body = "version: 2\nupdates:\n"
    for ecosystem, directory in entries:
        body += (f"  - package-ecosystem: {ecosystem}\n"
                 f"    directory: {directory}\n"
                 f"    schedule:\n      interval: weekly\n")
    return body


class SyntheticTreeMixin:
    """Un árbol mínimo, coherente y enteramente sintético."""

    model: dict

    def tree(self, directory: Path, **overrides) -> Path:
        write(directory / WORKFLOW, overrides.get("workflow", workflow_yaml()))
        write(directory / COMPOSE, overrides.get("compose", compose_yaml()))
        write(directory / MANIFEST, overrides.get("manifest", manifest_json()))
        if overrides.get("lockfile", True):
            write(directory / LOCKFILE, lockfile_json())
        write(directory / MONITOR, overrides.get("monitor", monitor_yaml([
            ("github-actions", "/"),
            ("npm", "/spikes/SYN-001/api"),
            ("docker", "/infra/synthetic"),
        ])))
        return directory

    def scan(self, directory: Path, model: dict | None = None) -> dict:
        used = model or self.model
        return reconcile(used, directory, discover(used, directory))

    def codes(self, result: dict) -> set[str]:
        return {item["code"] for item in result["findings"]}


# --------------------------------------------------------------------------- #
# Positivas contra el repositorio real
# --------------------------------------------------------------------------- #

class RealRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.inventory = discover(self.model, ROOT)

    def test_pos_01_the_real_model_is_structurally_valid(self) -> None:
        self.assertEqual(validate_model(self.model), [])

    def test_pos_02_discovery_finds_every_component_family(self) -> None:
        found = set(self.inventory["counts_by_type"])
        self.assertLessEqual(
            {"github_action", "oci_image", "runtime", "package_manifest", "lockfile"}, found)

    def test_pos_03_every_github_action_is_pinned_to_a_full_sha(self) -> None:
        unpinned = [
            component for component in self.inventory["components"]
            if component["component_type"] == "github_action"
            and component["attributes"].get("form") == "registry"
            and not re.fullmatch(r"[0-9a-f]{40}", component["attributes"].get("ref", ""))
        ]
        self.assertEqual(unpinned, [])

    def test_pos_04_every_oci_image_is_pinned_by_digest(self) -> None:
        unpinned = [component for component in self.inventory["components"]
                    if component["component_type"] == "oci_image"
                    and "@sha256:" not in component["reference"]]
        self.assertEqual(unpinned, [])

    def test_pos_05_no_file_is_unscannable_or_unsafe(self) -> None:
        self.assertEqual(self.inventory["unscannable_files"], [])
        self.assertEqual(self.inventory["unsafe_paths"], [])

    def test_pos_06_every_component_carries_path_line_and_source_digest(self) -> None:
        for component in self.inventory["components"]:
            self.assertTrue(component["path"])
            self.assertGreaterEqual(component["line"], 1)
            self.assertEqual(len(component["source_digest"]), 64)

    def test_pos_07_tm_005_stays_open_in_the_model(self) -> None:
        self.assertEqual(self.model["tm_005"]["state"], "open")
        self.assertFalse(self.model["tm_005"]["closed_by_this_tool"])

    def test_pos_08_the_model_never_claims_a_digest_proves_provenance(self) -> None:
        semantics = self.model["digest_semantics"]
        self.assertTrue(semantics["proves_artifact_identity"])
        for claim in ("proves_author", "proves_signature", "proves_provenance",
                      "substitutes_independent_verification"):
            self.assertFalse(semantics[claim], claim)

    def test_pos_09_no_evidence_claim_is_satisfied_without_verification(self) -> None:
        for claim in self.model["evidence_claims"]:
            if claim.get("satisfied"):
                self.assertTrue(claim.get("verification_ref"), claim["id"])

    def test_pos_10_every_declared_gap_keeps_its_gate_blocked(self) -> None:
        self.assertTrue(self.model["declared_gaps"])
        for gap in self.model["declared_gaps"]:
            self.assertTrue(gap["blocks_gate"], gap["id"])
            self.assertTrue(gap["owner_role"] and gap["gate"])


# --------------------------------------------------------------------------- #
# Invariantes negativas 1-16
# --------------------------------------------------------------------------- #

class NegativeInvariantTests(SyntheticTreeMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def test_neg_00_the_coherent_synthetic_tree_has_no_pin_defects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.scan(self.tree(Path(directory)))
            defects = {item["code"] for item in result["findings"]
                       if item["classification"] == "defect"}
            self.assertEqual(defects, set())

    # 1. Action con tag, branch, SHA corto o referencia vacía.
    def test_neg_01a_action_pinned_to_a_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), workflow=workflow_yaml(action_ref="v4"))
            self.assertIn("SUP-ACTION-UNPINNED", self.codes(self.scan(tree)))

    def test_neg_01b_action_pinned_to_a_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), workflow=workflow_yaml(action_ref="main"))
            self.assertIn("SUP-ACTION-UNPINNED", self.codes(self.scan(tree)))

    def test_neg_01c_action_pinned_to_a_short_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), workflow=workflow_yaml(action_ref="a1b2c3d"))
            result = self.scan(tree)
            self.assertIn("SUP-ACTION-UNPINNED", self.codes(result))
            message = next(item["message"] for item in result["findings"]
                           if item["code"] == "SUP-ACTION-UNPINNED")
            self.assertIn("short commit sha", message)

    def test_neg_01d_action_without_any_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = workflow_yaml().replace(f"actions/checkout@{GOOD_SHA}",
                                               "actions/checkout")
            tree = self.tree(Path(directory), workflow=workflow)
            self.assertIn("SUP-ACTION-UNPINNED", self.codes(self.scan(tree)))

    # 2. Imagen sin digest, con `latest` o digest mal formado.
    def test_neg_02a_image_without_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), compose=compose_yaml("postgres:17.11-alpine3.24"))
            self.assertIn("SUP-IMAGE-UNPINNED", self.codes(self.scan(tree)))

    def test_neg_02b_image_tagged_latest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), compose=compose_yaml("postgres:latest"))
            result = self.scan(tree)
            self.assertIn("SUP-IMAGE-UNPINNED", self.codes(result))
            message = next(item["message"] for item in result["findings"]
                           if item["code"] == "SUP-IMAGE-UNPINNED")
            self.assertIn("floating tag", message)

    def test_neg_02c_image_with_a_malformed_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory),
                             compose=compose_yaml("postgres:17.11@sha256:not-a-digest"))
            self.assertIn("SUP-IMAGE-UNPINNED", self.codes(self.scan(tree)))

    # 3. Runtime flotante o rango abierto.
    def test_neg_03a_runtime_declared_as_a_floating_token(self) -> None:
        for token in ("latest", "current", "stable", "main"):
            with self.subTest(token=token), tempfile.TemporaryDirectory() as directory:
                tree = self.tree(Path(directory),
                                 workflow=workflow_yaml(python_version=token))
                self.assertIn("SUP-RUNTIME-FLOATING", self.codes(self.scan(tree)))

    def test_neg_03b_runtime_declared_as_an_open_range(self) -> None:
        for value in ("^3.12", "~3.12", ">=3.12", "3.x"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                tree = self.tree(Path(directory),
                                 workflow=workflow_yaml(python_version=value))
                self.assertIn("SUP-RUNTIME-FLOATING", self.codes(self.scan(tree)))

    def test_neg_03c_a_latest_runner_label_floats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), workflow=workflow_yaml(runner="ubuntu-latest"))
            self.assertIn("SUP-RUNTIME-FLOATING", self.codes(self.scan(tree)))

    # 4. Manifest sin lockfile.
    def test_neg_04_manifest_without_a_sibling_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), lockfile=False)
            self.assertIn("SUP-MANIFEST-NO-LOCKFILE", self.codes(self.scan(tree)))

    # 5. Lockfile huérfano o duplicado incompatible.
    def test_neg_05a_orphan_lockfile_without_a_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            (tree / MANIFEST).unlink()
            self.assertIn("SUP-LOCKFILE-ORPHAN", self.codes(self.scan(tree)))

    def test_neg_05b_incompatible_lockfiles_in_the_same_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "spikes/SYN-001/api/pnpm-lock.yaml", "lockfileVersion: 9\n")
            result = self.scan(tree)
            self.assertIn("SUP-LOCKFILE-ORPHAN", self.codes(result))
            message = " ".join(item["message"] for item in result["findings"]
                               if item["code"] == "SUP-LOCKFILE-ORPHAN")
            self.assertIn("incompatible lockfiles", message)

    # 6. Instalación no acotada presentada como reproducible.
    def test_neg_06_unbounded_install_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory),
                             workflow=workflow_yaml(install="npm install --ignore-scripts"))
            self.assertIn("SUP-INSTALL-UNBOUNDED", self.codes(self.scan(tree)))

    def test_neg_06b_a_bounded_install_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), workflow=workflow_yaml(install="npm ci"))
            self.assertNotIn("SUP-INSTALL-UNBOUNDED", self.codes(self.scan(tree)))

    # 7. Lifecycle scripts permitidos en silencio.
    def test_neg_07_lifecycle_scripts_with_an_install_that_runs_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), manifest=manifest_json(lifecycle=True),
                             workflow=workflow_yaml(install="npm ci"))
            self.assertIn("SUP-LIFECYCLE-SCRIPTS", self.codes(self.scan(tree)))

    def test_neg_07b_lifecycle_scripts_with_ignore_scripts_are_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), manifest=manifest_json(lifecycle=True),
                             workflow=workflow_yaml(install="npm ci --ignore-scripts"))
            self.assertNotIn("SUP-LIFECYCLE-SCRIPTS", self.codes(self.scan(tree)))

    # 8. Componente sin owner, riesgo o gate.
    def test_neg_08_component_type_without_owner_risk_or_gate(self) -> None:
        broken = copy.deepcopy(self.model)
        del broken["ownership"]["oci_image"]
        self.assertIn("SUP-COMPONENT-UNOWNED",
                      {item.code for item in validate_model(broken)})

    def test_neg_08b_owner_cannot_be_its_own_reviewer(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["ownership"]["oci_image"]["reviewer_roles"] = ["Platform"]
        self.assertIn("SUP-COMPONENT-UNOWNED",
                      {item.code for item in validate_model(broken)})

    # 9. Digest confundido con firma o procedencia.
    def test_neg_09_digest_claimed_as_provenance(self) -> None:
        for field in ("proves_author", "proves_signature", "proves_provenance",
                      "substitutes_independent_verification"):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.model)
                broken["digest_semantics"][field] = True
                self.assertIn("SUP-DIGEST-AS-PROVENANCE",
                              {item.code for item in validate_model(broken)})

    # 10. SBOM/provenance/signature marcados completos sin evidencia.
    def test_neg_10a_evidence_claim_satisfied_without_verification(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["evidence_claims"][0]["satisfied"] = True
        self.assertIn("SUP-EVIDENCE-UNSUPPORTED",
                      {item.code for item in validate_model(broken)})

    def test_neg_10b_a_pending_state_can_never_be_satisfied(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["evidence_claims"][0].update(satisfied=True, verification_ref="trust me")
        self.assertIn("SUP-EVIDENCE-UNSUPPORTED",
                      {item.code for item in validate_model(broken)})

    # 11. Excepción incompleta.
    def test_neg_11a_exception_missing_owner_reviewer_expiry_or_gate(self) -> None:
        for missing in ("owner_role", "reviewer_role", "expires_on", "gate", "reason"):
            with self.subTest(missing=missing):
                broken = copy.deepcopy(self.model)
                exception = {
                    "id": "EXC-1", "component": "actions/checkout@v4",
                    "rule": "SUP-ACTION-UNPINNED", "reason": "r", "owner_role": "Security",
                    "reviewer_role": "Platform", "expires_on": "2026-12-31",
                    "gate": "DRG-00", "approved_by_human": True,
                }
                del exception[missing]
                broken["exceptions"] = [exception]
                self.assertIn("SUP-EXCEPTION-INCOMPLETE",
                              {item.code for item in validate_model(broken)})

    def test_neg_11b_exception_without_human_approval_does_not_suspend_a_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = copy.deepcopy(self.model)
            model["exceptions"] = [{
                "id": "EXC-1", "component": "actions/checkout@v4",
                "rule": "SUP-ACTION-UNPINNED", "reason": "pendiente",
                "owner_role": "Security", "reviewer_role": "Platform",
                "expires_on": "2026-12-31", "gate": "DRG-00", "approved_by_human": False,
            }]
            tree = self.tree(Path(directory), workflow=workflow_yaml(action_ref="v4"))
            self.assertIn("SUP-ACTION-UNPINNED", self.codes(self.scan(tree, model)))

    def test_neg_11c_an_approved_exception_suspends_exactly_its_own_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = copy.deepcopy(self.model)
            model["exceptions"] = [{
                "id": "EXC-1", "component": "actions/checkout@v4",
                "rule": "SUP-ACTION-UNPINNED", "reason": "adjudicado",
                "owner_role": "Security", "reviewer_role": "Platform",
                "expires_on": "2026-12-31", "gate": "DRG-00", "approved_by_human": True,
            }]
            tree = self.tree(Path(directory), workflow=workflow_yaml(action_ref="v4"))
            self.assertNotIn("SUP-ACTION-UNPINNED", self.codes(self.scan(tree, model)))

    # 12. Fichero vendorizado contado como fuente propia.
    def test_neg_12a_a_vendored_glob_in_the_model_is_refused(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["discovery_rules"]["package_manifests"]["include_globs"].append(
            "node_modules/*/package.json")
        self.assertIn("SUP-VENDORED-SOURCE", {item.code for item in validate_model(broken)})

    def test_neg_12b_a_vendored_file_is_never_inventoried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "spikes/SYN-001/api/node_modules/left-pad/package.json",
                  manifest_json())
            paths = {item["path"] for item in discover(self.model, tree)["components"]}
            self.assertFalse(any("node_modules" in path for path in paths))

    # 13. Ruta absoluta, traversal o symlink externo.
    def test_neg_13a_safe_relative_rejects_absolute_and_traversal(self) -> None:
        for candidate in ("/etc/passwd", "C:/Windows/win.ini", "../outside.json",
                          "docs/../../outside.json", ""):
            self.assertFalse(safe_relative(candidate), candidate)

    def test_neg_13b_traversal_is_rejected_even_when_it_resolves_inside(self) -> None:
        candidate = "docs/../docs/security/supply-chain.json"
        self.assertTrue((ROOT / candidate).resolve().is_file())
        self.assertIsNone(resolve_inside(ROOT, candidate))

    def test_neg_13c_a_symlink_is_never_collected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            link = tree / ".github/workflows/linked.yml"
            try:
                link.symlink_to(tree / WORKFLOW)
            except (OSError, NotImplementedError):
                self.skipTest("this platform does not allow creating symlinks")
            collected = {item.as_posix() for item in collect_files(
                tree, [".github/workflows/*.yml"])}
            self.assertNotIn(".github/workflows/linked.yml", collected)

    def test_neg_13c2_generated_framework_cache_is_never_inventoried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            generated = tree / "apps/web/.next/package.json"
            write(generated, manifest_json())
            inventory = discover(self.model, tree)
            paths = {item["path"] for item in inventory["components"]}
            self.assertNotIn("apps/web/.next/package.json", paths)

    def test_neg_13d_the_cli_refuses_a_traversing_root(self) -> None:
        code, payload = run_cli(["--root", "../outside", "discover"])
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])

    # 14. El orden del filesystem no cambia inventario ni digest.
    def test_neg_14_discovery_is_stable_across_repeated_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            self.assertEqual(discover(self.model, tree), discover(self.model, tree))

    # 15. La salida no filtra variables, secretos ni contenido de ficheros.
    def test_neg_15a_the_inventory_never_carries_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / ".github/workflows/secret.yml", workflow_yaml() +
                  "    env:\n      SYNTHETIC_TOKEN: synthetic-value-do-not-leak\n")
            serialised = json.dumps(discover(self.model, tree), ensure_ascii=False)
            self.assertNotIn("synthetic-value-do-not-leak", serialised)
            self.assertNotIn("SYNTHETIC_TOKEN", serialised)

    def test_neg_15b_the_report_carries_no_environment(self) -> None:
        _, payload = run_cli(["report"])
        serialised = json.dumps(payload, ensure_ascii=False)
        for forbidden in ("PATH=", "PYTHONPATH", "TEMP=", "USERPROFILE", "Users\\\\"):
            self.assertNotIn(forbidden, serialised, forbidden)

    # 16. El agente no cierra TM-005.
    def test_neg_16a_marking_tm005_resolved_is_refused(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["tm_005"]["state"] = "resolved"
        self.assertIn("SUP-TM005-CLOSED", {item.code for item in validate_model(broken)})

    def test_neg_16b_claiming_the_tool_closed_tm005_is_refused(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["tm_005"]["closed_by_this_tool"] = True
        self.assertIn("SUP-TM005-CLOSED", {item.code for item in validate_model(broken)})

    def test_neg_16c_an_agent_cannot_mark_a_gate_as_met(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["gates"][0]["status"] = "met"
        self.assertIn("SUP-MODEL-GATE", {item.code for item in validate_model(broken)})

    def test_neg_16d_an_agent_cannot_record_human_acceptance(self) -> None:
        broken = copy.deepcopy(self.model)
        broken["human_acceptance"] = "accepted"
        self.assertIn("SUP-MODEL-ACCEPTANCE", {item.code for item in validate_model(broken)})

    # Fuentes no inventariadas y límites del escáner.
    def test_neg_17_a_new_ecosystem_without_an_extractor_is_reported(self) -> None:
        # Rust y Go están en `watch_globs` y no tienen extractor: son exactamente el
        # caso de «el inventario parece completo y le falta un ecosistema entero».
        for relative, body in (("workers/parser/Cargo.toml", '[package]\nname = "p"\n'),
                               ("workers/parser/go.mod", "module fincilia/parser\n")):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                tree = self.tree(Path(directory))
                write(tree / relative, body)
                self.assertIn("SUP-SOURCE-NOT-INVENTORIED", self.codes(self.scan(tree)))

    def test_neg_17b_an_ecosystem_with_an_extractor_is_inventoried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "apps/api/requirements.in", "fastapi==0.115.6\n")
            write(tree / "apps/api/requirements.txt",
                  "fastapi==0.115.6 \\\n    --hash=sha256:" + "a" * 64 + "\n")
            codes = self.codes(self.scan(tree))
            self.assertNotIn("SUP-SOURCE-NOT-INVENTORIED", codes)
            self.assertNotIn("SUP-LOCKFILE-NO-HASHES", codes)

    def test_neg_17c_a_python_lockfile_without_hashes_bites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "apps/api/requirements.in", "fastapi==0.115.6\n")
            write(tree / "apps/api/requirements.txt", "fastapi==0.115.6\n")
            self.assertIn("SUP-LOCKFILE-NO-HASHES", self.codes(self.scan(tree)))

    def test_neg_17d_an_unpinned_dockerfile_base_bites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "apps/api/Dockerfile", 'FROM python:3.12-slim\nCMD ["true"]\n')
            self.assertIn("SUP-IMAGE-UNPINNED", self.codes(self.scan(tree)))

    def test_neg_17e_a_digest_only_base_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "apps/api/Dockerfile",
                  "FROM python@sha256:" + "d" * 64 + '\nCMD ["true"]\n')
            self.assertNotIn("SUP-IMAGE-UNPINNED", self.codes(self.scan(tree)))

    def test_neg_17f_a_manifest_without_dependencies_needs_no_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            write(tree / "packages/shared/python/pyproject.toml",
                  '[project]\nname = "shared"\ndependencies = []\n')
            self.assertNotIn("SUP-MANIFEST-NO-LOCKFILE", self.codes(self.scan(tree)))

    def test_neg_18_unsupported_yaml_is_reported_instead_of_silently_missed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            anchored = ("name: synthetic\ndefaults: &base\n  shell: bash\njobs:\n"
                        "  build:\n    defaults: *base\n")
            tree = self.tree(Path(directory), workflow=anchored)
            result = self.scan(tree)
            self.assertIn("SUP-YAML-UNSCANNABLE", self.codes(result))

    def test_neg_18b_a_shell_glob_is_not_mistaken_for_a_yaml_alias(self) -> None:
        text = "      - run: node --test spikes/FNC-SEC-001/test/*.test.mjs\n"
        self.assertEqual(unsupported_yaml_constructs(text), [])

    def test_neg_19_an_unmonitored_scope_is_reported_once_per_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory), monitor=monitor_yaml(
                [("github-actions", "/")]))
            findings = [item for item in self.scan(tree)["findings"]
                        if item["code"] == "SUP-UPDATES-UNMONITORED"]
            self.assertEqual(len(findings), 2)
            self.assertEqual({item["location"] for item in findings},
                             {"spikes/SYN-001/api", "infra/synthetic"})


# --------------------------------------------------------------------------- #
# Metamórficas y determinismo
# --------------------------------------------------------------------------- #

class MetamorphicTests(SyntheticTreeMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def semantic(self, inventory: dict) -> set[tuple[str, str]]:
        return {(item["component_type"], item["reference"])
                for item in inventory["components"]}

    def test_meta_01_reordering_yaml_keys_does_not_change_the_inventory(self) -> None:
        reordered = """name: synthetic
on: [push]
jobs:
  build:
    steps:
      - name: Set up Python
        uses: actions/setup-python@{sha}
        with:
          python-version: "3.12"
      - name: Checkout
        uses: actions/checkout@{sha}
      - name: Install
        run: npm ci --ignore-scripts
    runs-on: ubuntu-24.04
""".format(sha=GOOD_SHA)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = discover(self.model, self.tree(Path(one)))
            second = discover(self.model, self.tree(Path(two), workflow=reordered))
            self.assertEqual(self.semantic(first), self.semantic(second))

    def test_meta_02_a_new_eligible_action_appears_in_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            before = self.semantic(discover(self.model, tree))
            write(tree / ".github/workflows/extra.yml", workflow_yaml().replace(
                "actions/checkout", "actions/cache"))
            after = self.semantic(discover(self.model, tree))
            self.assertNotIn(("github_action", f"actions/cache@{GOOD_SHA}"), before)
            self.assertIn(("github_action", f"actions/cache@{GOOD_SHA}"), after)

    def test_meta_03_a_new_eligible_image_appears_in_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            before = self.semantic(discover(self.model, tree))
            write(tree / "spikes/SYN-002/compose.yaml",
                  compose_yaml(f"redis:7.4.1-alpine@sha256:{'c' * 64}"))
            after = self.semantic(discover(self.model, tree))
            self.assertLess(len(before), len(after))
            self.assertIn(("oci_image", f"redis:7.4.1-alpine@sha256:{'c' * 64}"), after)

    def test_meta_04_moving_a_reference_changes_its_line_but_not_its_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            first = discover(self.model, tree)
            write(tree / WORKFLOW, "# comentario nuevo\n" + workflow_yaml())
            second = discover(self.model, tree)
            self.assertEqual(self.semantic(first), self.semantic(second))
            self.assertNotEqual(
                [item["line"] for item in first["components"]],
                [item["line"] for item in second["components"]])

    def test_meta_05_changing_a_source_changes_its_recorded_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = self.tree(Path(directory))
            before = {item["path"]: item["sha256"]
                      for item in discover(self.model, tree)["scanned_files"]}
            write(tree / COMPOSE, compose_yaml(f"postgres:17.11@sha256:{'d' * 64}"))
            after = {item["path"]: item["sha256"]
                     for item in discover(self.model, tree)["scanned_files"]}
            self.assertNotEqual(before[COMPOSE], after[COMPOSE])


# --------------------------------------------------------------------------- #
# CLI y disciplina del código fuente
# --------------------------------------------------------------------------- #

class CliAndSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def test_cli_01_discover_succeeds_on_the_real_tree(self) -> None:
        code, payload = run_cli(["discover"])
        self.assertEqual(code, 0)
        self.assertGreater(payload["component_count"], 10)

    def test_cli_02_validate_separates_model_validity_from_repository_findings(self) -> None:
        code, payload = run_cli(["validate"])
        self.assertEqual(1, code)
        self.assertTrue(payload["model_valid"])
        self.assertIn("repository_findings", payload)
        self.assertIn("blocking_findings", payload)

    def test_cli_02b_gate_scope_keeps_later_blockers_visible_but_non_blocking(self) -> None:
        code, payload = run_cli(["validate", "--gate", "S1-READY"])
        self.assertEqual(0, code)
        self.assertTrue(payload["ok"])
        self.assertEqual("S1-READY", payload["target_gate"])
        self.assertEqual(0, payload["blocking_findings"])
        self.assertGreater(payload["out_of_scope_blocking_findings"], 0)
        self.assertTrue(any(item["gate"] == "DRG-00" for item in payload["findings"]))

    def test_cli_02c_unknown_gate_fails_closed(self) -> None:
        code, payload = run_cli(["validate", "--gate", "GA-UNKNOWN"])
        self.assertEqual(2, code)
        self.assertFalse(payload["ok"])

    def test_cli_03_report_never_produces_an_aggregate_score(self) -> None:
        _, payload = run_cli(["report"])
        self.assertIsNone(payload["aggregate_score"])
        self.assertIn("counts_by_owner", payload)
        self.assertIn("counts_by_gate", payload)

    def test_cli_04_report_keeps_the_declared_gaps_and_tm005_visible(self) -> None:
        _, payload = run_cli(["report"])
        self.assertTrue(payload["declared_gaps"])
        self.assertEqual(payload["tm_005"]["state"], "open")

    def test_cli_05_an_invalid_model_stops_the_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.json"
            model = copy.deepcopy(self.model)
            model["task_id"] = "FNC-WRONG-000"
            write(broken, json.dumps(model, ensure_ascii=False))
            code, payload = run_cli(["--model", str(broken), "discover"])
            self.assertEqual(code, 1)
            self.assertFalse(payload["model_valid"])
            self.assertNotIn("components", payload)

    def test_cli_06_an_unreadable_model_fails_operationally(self) -> None:
        code, _ = run_cli(["--model", str(ROOT / "docs/security/does-not-exist.json"),
                           "discover"])
        self.assertEqual(code, 2)

    def test_cli_07_the_root_must_be_an_existing_directory(self) -> None:
        code, _ = run_cli(["--root", str(MODEL_PATH), "discover"])
        self.assertEqual(code, 2)

    def test_src_01_the_tool_never_reaches_the_network_clock_or_randomness(self) -> None:
        forbidden = (
            "import socket", "import urllib", "import requests", "import http.client",
            "import random", "import secrets", "time.time(", "datetime.now(",
            "datetime.utcnow(", "import subprocess", "shell=True", "eval(", "exec(",
            "os.environ", "os.getenv",
        )
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_validate.py":
                continue
            text = source.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_02_no_anonymous_todo_survives_in_the_tool(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_validate.py":
                continue
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)

    def test_src_03_findings_are_totally_ordered_and_deduplicated(self) -> None:
        one = Finding("SUP-X", "a", "m", "high", "Security", "DRG-00", ("TM-005",))
        two = Finding("SUP-X", "a", "m", "high", "Security", "DRG-00", ("TM-005",))
        self.assertEqual(len({one, two}), 1)
        self.assertEqual(sorted([two, one]), [one, two])


if __name__ == "__main__":
    unittest.main()
