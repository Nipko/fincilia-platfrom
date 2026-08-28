from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .model import (
    CHECKSUM_NAME,
    EXPECTED_FILES,
    ReleaseError,
    clean_git_state,
    create_bundle,
    digest_source_input,
    npm_packages,
    python_packages,
    verify_bundle,
    verify_source,
)


IMAGES = {
    "api": "sha256:" + "1" * 64,
    "worker": "sha256:" + "2" * 64,
    "web": "sha256:" + "3" * 64,
}
CI_URL = "https://github.com/Nipko/fincilia-platfrom/actions/runs/123456"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True,
                            capture_output=True, text=True, env=env)
    return result.stdout.strip()


def contract() -> dict:
    return {
        "allowed_data": "synthetic_only",
        "artifact_names": ["api", "worker", "web"],
        "claims": {
            "approved": False, "production_authorized": False,
            "provenance_verified": False, "published": False, "signed": False,
        },
        "dependency_locks": {
            "api": "apps/api/requirements.txt",
            "web": "apps/web/package-lock.json",
            "worker": "workers/document/requirements.txt",
        },
        "schema_version": "1.0.0",
        "source_inputs": [
            "apps/api/Dockerfile", "apps/api/requirements.txt", "apps/api/src",
            "apps/web/Dockerfile", "apps/web/package-lock.json", "apps/web/src",
            "db/migrations", "packages/contracts/python", "packages/platform/python",
            "workers/document/Dockerfile", "workers/document/requirements.txt",
            "workers/document/src",
        ],
        "state": "review_pending", "task": "FNC-REL-001",
        "workflow": {
            "external_publish": False, "manual_only": True, "real_data": False,
            "signing": "pending_human_root_of_trust",
        },
    }


class RepositoryFixture:
    def __init__(self, parent: Path) -> None:
        self.root = parent / "repo"
        self.root.mkdir()
        requirement = "demo-package==1.2.3 \\\n+    --hash=sha256:" + "a" * 64 + "\n"
        integrity = base64.b64encode(bytes.fromhex("b" * 128)).decode()
        lock = {
            "name": "demo", "version": "1.0.0", "lockfileVersion": 3,
            "packages": {
                "": {"name": "demo", "version": "1.0.0"},
                "node_modules/demo": {
                    "version": "4.5.6", "integrity": f"sha512-{integrity}",
                    "resolved": "https://registry.npmjs.org/demo/-/demo-4.5.6.tgz",
                },
            },
        }
        write(self.root / "docs/platform/release-candidate.json",
              json.dumps(contract(), sort_keys=True))
        for path in ("apps/api/Dockerfile", "apps/web/Dockerfile",
                     "workers/document/Dockerfile"):
            write(self.root / path, "FROM scratch@sha256:" + "c" * 64 + "\n")
        write(self.root / "apps/api/requirements.txt", requirement)
        write(self.root / "workers/document/requirements.txt", requirement)
        write(self.root / "apps/web/package-lock.json", json.dumps(lock, sort_keys=True))
        for path in ("apps/api/src/main.py", "apps/web/src/page.tsx",
                     "packages/contracts/python/contract.py",
                     "packages/platform/python/platform.py",
                     "workers/document/src/main.py"):
            write(self.root / path, "synthetic = True\n")
        write(self.root / "db/migrations/V0001__initial.sql", "SELECT 1;\n")
        git(self.root, "init", "-q")
        git(self.root, "add", ".")
        fixed = {**os.environ, "GIT_AUTHOR_DATE": "2026-08-28T00:00:00Z",
                 "GIT_COMMITTER_DATE": "2026-08-28T00:00:00Z"}
        git(self.root, "-c", "user.name=Fincilia Test",
            "-c", "user.email=synthetic@demo.local", "commit", "-qm", "fixture",
            env=fixed)

    def create(self, output: Path, **overrides):
        options = {"ci_run_url": CI_URL, **overrides}
        return create_bundle(self.root, output, IMAGES, **options)


class DependencyInventoryTests(unittest.TestCase):
    def test_python_requires_exact_version_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "requirements.txt"
            write(path, "alpha==1.2.3 \\\n+  --hash=sha256:" + "a" * 64 + "\n")
            packages = python_packages(path, "api")
            self.assertEqual((packages[0]["name"], packages[0]["versionInfo"]),
                             ("alpha", "1.2.3"))
            self.assertEqual(packages[0]["checksums"][0]["algorithm"], "SHA256")

    def test_python_rejects_range_and_missing_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "requirements.txt"
            for value in ("alpha>=1.0\n", "alpha==1.0\n"):
                with self.subTest(value=value):
                    write(path, value)
                    with self.assertRaises(ReleaseError):
                        python_packages(path, "api")

    def test_python_rejects_duplicate_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "requirements.txt"
            line = "alpha==1.0 --hash=sha256:" + "a" * 64 + "\n"
            write(path, line + line)
            with self.assertRaisesRegex(ReleaseError, "duplicate"):
                python_packages(path, "api")

    def test_npm_converts_integrity_to_spdx_hex(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "package-lock.json"
            raw = bytes.fromhex("d" * 128)
            write(path, json.dumps({
                "lockfileVersion": 3,
                "packages": {"node_modules/pkg": {
                    "version": "1.0.0",
                    "integrity": "sha512-" + base64.b64encode(raw).decode(),
                }},
            }))
            package = npm_packages(path)[0]
            self.assertEqual(package["checksums"], [{
                "algorithm": "SHA512", "checksumValue": "d" * 128}])

    def test_npm_rejects_missing_integrity_and_old_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "package-lock.json"
            for value in (
                {"lockfileVersion": 2, "packages": {}},
                {"lockfileVersion": 3,
                 "packages": {"node_modules/pkg": {"version": "1.0.0"}}},
            ):
                with self.subTest(value=value):
                    write(path, json.dumps(value))
                    with self.assertRaises(ReleaseError):
                        npm_packages(path)


class ReleaseBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.fixture = RepositoryFixture(self.base)
        self.bundle = self.base / "bundle"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_and_verify_release_candidate(self) -> None:
        manifest = self.fixture.create(self.bundle)
        self.assertEqual(manifest["state"], "candidate")
        self.assertEqual(manifest["schema_head"], "V0001")
        self.assertEqual({path.name for path in self.bundle.iterdir()}, EXPECTED_FILES)
        self.assertEqual(verify_bundle(self.bundle), manifest)
        self.assertEqual(verify_source(self.fixture.root, self.bundle), manifest)

    def test_bundle_is_deterministic_for_same_commit_and_images(self) -> None:
        second = self.base / "bundle-2"
        self.fixture.create(self.bundle)
        self.fixture.create(second)
        for name in EXPECTED_FILES:
            self.assertEqual((self.bundle / name).read_bytes(), (second / name).read_bytes())

    def test_manifest_cannot_claim_approval_signature_or_provenance(self) -> None:
        for index, field in enumerate((
                "approved", "production_authorized", "provenance_verified", "signed")):
            with self.subTest(field=field):
                self.bundle = self.base / f"bundle-claim-{index}"
                self.fixture.create(self.bundle)
                manifest_path = self.bundle / "manifest.json"
                original = json.loads(manifest_path.read_text())
                original["approval"][field] = True
                manifest_path.write_text(json.dumps(original, sort_keys=True), encoding="utf-8")
                self._refresh_checksums()
                with self.assertRaisesRegex(ReleaseError, "claims"):
                    verify_bundle(self.bundle)

    def _refresh_checksums(self) -> None:
        lines = []
        for name in sorted(EXPECTED_FILES - {CHECKSUM_NAME}):
            digest = hashlib.sha256((self.bundle / name).read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")
        (self.bundle / CHECKSUM_NAME).write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_tampered_file_is_rejected(self) -> None:
        self.fixture.create(self.bundle)
        path = self.bundle / "api-dependencies.spdx.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ReleaseError, "digest mismatch"):
            verify_bundle(self.bundle)

    def test_extra_missing_and_nested_entries_are_rejected(self) -> None:
        for action in ("extra", "missing", "nested"):
            with self.subTest(action=action):
                bundle = self.base / action
                self.fixture.create(bundle)
                if action == "extra":
                    write(bundle / "surprise.txt", "no")
                elif action == "missing":
                    (bundle / "web-dependencies.spdx.json").unlink()
                else:
                    (bundle / "nested").mkdir()
                with self.assertRaisesRegex(ReleaseError, "missing, extra or nested"):
                    verify_bundle(bundle)

    def test_invalid_image_ids_duplicate_images_and_bad_ci_url_are_rejected(self) -> None:
        cases = [
            ({**IMAGES, "api": "latest"}, CI_URL),
            ({**IMAGES, "worker": IMAGES["api"]}, CI_URL),
            (IMAGES, "https://example.invalid/passed"),
        ]
        for index, (images, url) in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ReleaseError):
                create_bundle(self.fixture.root, self.base / f"invalid-{index}", images,
                              ci_run_url=url)

    def test_dirty_source_and_wrong_revision_are_rejected(self) -> None:
        write(self.fixture.root / "untracked.txt", "dirty")
        with self.assertRaisesRegex(ReleaseError, "clean"):
            self.fixture.create(self.bundle)
        (self.fixture.root / "untracked.txt").unlink()
        with self.assertRaisesRegex(ReleaseError, "requested revision"):
            self.fixture.create(self.bundle, revision="0" * 40)

    def test_output_must_be_empty(self) -> None:
        self.bundle.mkdir()
        write(self.bundle / "existing", "no")
        with self.assertRaisesRegex(ReleaseError, "must not already contain"):
            self.fixture.create(self.bundle)

    def test_source_input_rejects_traversal_and_aliases(self) -> None:
        for value in ("../repo", "apps/../apps/api", "/absolute", "apps\\api"):
            with self.subTest(value=value), self.assertRaises(ReleaseError):
                digest_source_input(self.fixture.root, value)

    def test_source_verification_rejects_a_different_commit(self) -> None:
        self.fixture.create(self.bundle)
        write(self.fixture.root / "apps/api/src/main.py", "synthetic = False\n")
        git(self.fixture.root, "add", ".")
        git(self.fixture.root, "-c", "user.name=Fincilia Test",
            "-c", "user.email=synthetic@demo.local", "commit", "-qm", "changed")
        with self.assertRaisesRegex(ReleaseError, "requested revision"):
            verify_source(self.fixture.root, self.bundle)

    def test_spdx_overclaim_is_rejected_even_with_recomputed_checksums(self) -> None:
        self.fixture.create(self.bundle)
        path = self.bundle / "api-dependencies.spdx.json"
        document = json.loads(path.read_text())
        document["packages"][0]["filesAnalyzed"] = True
        path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["artifacts"][0]["sbom_sha256"] = digest
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        self._refresh_checksums()
        with self.assertRaisesRegex(ReleaseError, "overclaims"):
            verify_bundle(self.bundle)

    def test_commit_date_not_wall_clock_drives_sbom(self) -> None:
        self.fixture.create(self.bundle)
        document = json.loads((self.bundle / "api-dependencies.spdx.json").read_text())
        self.assertEqual(document["creationInfo"]["created"], "2026-08-28T00:00:00Z")

    def test_clean_git_state_returns_full_revision(self) -> None:
        state = clean_git_state(self.fixture.root)
        self.assertRegex(state.revision, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
