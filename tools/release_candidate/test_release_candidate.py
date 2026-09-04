from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from .archive import ARCHIVE_ROOT, create_archive, verify_archive
from .model import (
    AGGREGATE_SBOM_NAME,
    CHECKSUM_NAME,
    EXPECTED_FILES,
    ReleaseError,
    clean_git_state,
    create_bundle,
    digest_source_input,
    load_contract,
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
    path.write_text(content, encoding="utf-8", newline="\n")


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
        "schema_version": "1.1.0",
        "source_inputs": [
            "apps/api", "apps/web", "db", "packages/contracts/python",
            "packages/platform/python", ".github/workflows/release-candidate.yml",
            "tools/release_candidate", "workers/document",
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
        write(self.root / ".gitattributes", "* text=auto eol=lf\n")
        write(self.root / ".github/workflows/release-candidate.yml",
              "name: synthetic-release\n")
        write(self.root / "tools/release_candidate/model.py", "synthetic = True\n")
        dockerfiles = {
            "apps/api/Dockerfile": (
                "FROM scratch@sha256:" + "c" * 64 + "\n"
                "COPY apps/api/requirements.txt /app/requirements.txt\n"
                "COPY apps/api/src /app/src\n"
            ),
            "apps/web/Dockerfile": (
                "FROM scratch@sha256:" + "c" * 64 + " AS build\n"
                "COPY apps/web/package-lock.json /app/package-lock.json\n"
                "COPY [\"apps/web/src\", \"/app/src\"]\n"
                "FROM scratch@sha256:" + "d" * 64 + "\n"
                "COPY --from=build /app/src /app/src\n"
            ),
            "workers/document/Dockerfile": (
                "FROM scratch@sha256:" + "c" * 64 + "\n"
                "COPY workers/document/requirements.txt /app/requirements.txt\n"
                "COPY workers/document/src /app/src\n"
            ),
        }
        for path, content in dockerfiles.items():
            write(self.root / path, content)
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
        git(self.root, "config", "core.autocrlf", "true")
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

    def test_uncovered_docker_copy_source_is_rejected(self) -> None:
        write(self.fixture.root / "scripts/bootstrap.sh", "#!/bin/sh\nexit 0\n")
        dockerfile = self.fixture.root / "apps/api/Dockerfile"
        write(dockerfile, dockerfile.read_text() + "COPY scripts/bootstrap.sh /app/bootstrap.sh\n")
        git(self.fixture.root, "add", ".")
        git(self.fixture.root, "-c", "user.name=Fincilia Test",
            "-c", "user.email=synthetic@demo.local", "commit", "-qm", "uncovered copy")
        with self.assertRaisesRegex(ReleaseError, "not covered"):
            self.fixture.create(self.bundle)

    def test_overlapping_source_inputs_are_rejected(self) -> None:
        for index, reverse in enumerate((False, True)):
            payload = contract()
            if reverse:
                payload["source_inputs"].insert(0, "apps/api/src")
            else:
                payload["source_inputs"].append("apps/api/src")
            write(self.fixture.root / "docs/platform/release-candidate.json",
                  json.dumps(payload, sort_keys=True))
            git(self.fixture.root, "add", ".")
            git(self.fixture.root, "-c", "user.name=Fincilia Test",
                "-c", "user.email=synthetic@demo.local", "commit", "-qm",
                f"overlap-{index}")
            with self.assertRaisesRegex(ReleaseError, "overlapping"):
                self.fixture.create(self.base / f"overlap-{index}")

    def test_add_and_dynamic_copy_are_rejected_fail_closed(self) -> None:
        dockerfile = self.fixture.root / "apps/api/Dockerfile"
        for index, instruction in enumerate((
            "ADD apps/api/src /app/src\n",
            "COPY apps/api/src/*.py /app/src\n",
            "COPY --chown 10001 apps/api/src /app/src\n",
        )):
            with self.subTest(instruction=instruction):
                write(dockerfile, "FROM scratch@sha256:" + "c" * 64 + "\n" + instruction)
                git(self.fixture.root, "add", ".")
                git(self.fixture.root, "-c", "user.name=Fincilia Test",
                    "-c", "user.email=synthetic@demo.local", "commit", "-qm",
                    f"unsupported-{index}")
                with self.assertRaises(ReleaseError):
                    self.fixture.create(self.base / f"unsupported-{index}")

    def test_repository_contract_covers_every_current_local_copy(self) -> None:
        root = Path(__file__).resolve().parents[2]
        loaded = load_contract(root)
        self.assertEqual(loaded["source_inputs"], [
            "apps/api", "apps/web", "db", "packages/contracts/python",
            "packages/platform/python", ".github/workflows/release-candidate.yml",
            "tools/release_candidate", "workers/document",
        ])

    def test_source_verification_rejects_a_different_commit(self) -> None:
        self.fixture.create(self.bundle)
        write(self.fixture.root / "apps/api/src/main.py", "synthetic = False\n")
        git(self.fixture.root, "add", ".")
        git(self.fixture.root, "-c", "user.name=Fincilia Test",
            "-c", "user.email=synthetic@demo.local", "commit", "-qm", "changed")
        with self.assertRaisesRegex(ReleaseError, "requested revision"):
            verify_source(self.fixture.root, self.bundle)

    def test_release_identity_survives_clean_checkout_line_endings(self) -> None:
        manifest = self.fixture.create(self.bundle)
        source = self.fixture.root / "apps/api/src/main.py"
        source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
        git(self.fixture.root, "add", "apps/api/src/main.py")
        self.assertEqual(git(self.fixture.root, "status", "--porcelain=v1"), "")
        self.assertEqual(verify_source(self.fixture.root, self.bundle), manifest)

        second = self.base / "bundle-crlf"
        self.fixture.create(second)
        for name in EXPECTED_FILES:
            self.assertEqual((self.bundle / name).read_bytes(), (second / name).read_bytes())

    def test_tree_digest_still_binds_every_tracked_file(self) -> None:
        before, count = digest_source_input(self.fixture.root, "apps/api")
        self.assertGreaterEqual(count, 3)
        write(self.fixture.root / "apps/api/tests/new_test.py", "synthetic = True\n")
        git(self.fixture.root, "add", ".")
        git(self.fixture.root, "-c", "user.name=Fincilia Test",
            "-c", "user.email=synthetic@demo.local", "commit", "-qm", "new input")
        after, next_count = digest_source_input(self.fixture.root, "apps/api")
        self.assertNotEqual(after, before)
        self.assertEqual(next_count, count + 1)

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

    def test_aggregate_sbom_covers_all_three_artifact_inventories(self) -> None:
        manifest = self.fixture.create(self.bundle)
        aggregate = json.loads((self.bundle / AGGREGATE_SBOM_NAME).read_text())
        expected = {
            package["SPDXID"]
            for name in ("api", "worker", "web")
            for package in json.loads(
                (self.bundle / f"{name}-dependencies.spdx.json").read_text()
            )["packages"]
        }
        self.assertEqual({package["SPDXID"] for package in aggregate["packages"]}, expected)
        self.assertEqual(manifest["release_sbom"]["path"], AGGREGATE_SBOM_NAME)

    def test_aggregate_sbom_tamper_is_rejected_even_with_bundle_checksums(self) -> None:
        self.fixture.create(self.bundle)
        path = self.bundle / AGGREGATE_SBOM_NAME
        document = json.loads(path.read_text())
        document["packages"].pop()
        path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["release_sbom"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        self._refresh_checksums()
        with self.assertRaisesRegex(ReleaseError, "does not cover"):
            verify_bundle(self.bundle)

    def test_clean_git_state_returns_full_revision(self) -> None:
        state = clean_git_state(self.fixture.root)
        self.assertRegex(state.revision, r"^[0-9a-f]{40}$")


class ReleaseArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.fixture = RepositoryFixture(self.base)
        self.bundle = self.base / "bundle"
        self.fixture.create(self.bundle)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_archive_is_deterministic_and_matches_the_validated_bundle(self) -> None:
        first = self.base / "first.tar.gz"
        second = self.base / "second.tar.gz"
        manifest = create_archive(self.bundle, first)
        create_archive(self.bundle, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(verify_archive(self.bundle, first), manifest)
        with tarfile.open(first, "r:gz") as archive:
            for member in archive.getmembers():
                self.assertEqual(member.mtime, 0)
                self.assertEqual(member.mode, 0o644)
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.gid, 0)

    def test_archive_rejects_existing_output_and_tamper(self) -> None:
        output = self.base / "candidate.tar.gz"
        output.write_bytes(b"occupied")
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            create_archive(self.bundle, output)
        output.unlink()
        create_archive(self.bundle, output)
        payload = bytearray(output.read_bytes())
        payload[len(payload) // 2] ^= 1
        output.write_bytes(payload)
        with self.assertRaises(ReleaseError):
            verify_archive(self.bundle, output)

    def test_archive_rejects_links_even_when_names_look_complete(self) -> None:
        output = self.base / "unsafe.tar.gz"
        with tarfile.open(output, "w:gz") as archive:
            for index, name in enumerate(sorted(EXPECTED_FILES)):
                info = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{name}")
                info.mode = 0o644
                info.mtime = 0
                if index == 0:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "../../outside"
                    archive.addfile(info)
                else:
                    data = (self.bundle / name).read_bytes()
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
        with self.assertRaisesRegex(ReleaseError, "unsafe"):
            verify_archive(self.bundle, output)


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.workflow = (root / ".github/workflows/release-candidate.yml").read_text(
            encoding="utf-8"
        )

    def test_attestation_action_and_permissions_are_minimal_and_pinned(self) -> None:
        pin = "actions/attest@a1948c3f048ba23858d222213b7c278aabede763"
        self.assertEqual(self.workflow.count(pin), 2)
        self.assertNotIn("actions/attest@v", self.workflow)
        self.assertIn("  id-token: write", self.workflow)
        self.assertIn("  attestations: write", self.workflow)
        self.assertNotIn("  packages: write", self.workflow)

    def test_workflow_attests_archive_and_aggregate_sbom_without_publish(self) -> None:
        self.assertEqual(
            self.workflow.count("subject-path: ${{ runner.temp }}/fincilia-release.tar.gz"),
            2,
        )
        self.assertIn(
            "sbom-path: ${{ runner.temp }}/fincilia-release/release-dependencies.spdx.json",
            self.workflow,
        )
        self.assertNotIn("docker push", self.workflow)
        self.assertNotIn("push-to-registry:", self.workflow)

    def test_verification_binds_signer_source_commit_ref_and_runner(self) -> None:
        for required in (
            "--signer-workflow \"$SIGNER_WORKFLOW\"",
            "--source-digest \"$GITHUB_SHA\"",
            "--source-ref \"$GITHUB_REF\"",
            "--deny-self-hosted-runners",
            "--predicate-type \"https://spdx.dev/Document/v2.3\"",
        ):
            self.assertIn(required, self.workflow)


if __name__ == "__main__":
    unittest.main()
