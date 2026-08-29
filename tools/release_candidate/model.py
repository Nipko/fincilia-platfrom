"""Generación y verificación fail-closed de un candidato de release.

El bundle no firma ni publica nada. Acredita identidad de bytes y conserva
explícitamente como pendientes la aprobación humana, firma y procedencia. El
formato evita timestamps de ejecución: usa la fecha del commit para que dos
builds del mismo árbol produzcan los mismos documentos.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
PACKAGE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]+\])?==([^\s\\]+)")
HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")

CONTRACT_PATH = Path("docs/platform/release-candidate.json")
MANIFEST_NAME = "manifest.json"
CHECKSUM_NAME = "checksums.sha256"
SBOM_NAMES = {
    "api": "api-dependencies.spdx.json",
    "worker": "worker-dependencies.spdx.json",
    "web": "web-dependencies.spdx.json",
}
AGGREGATE_SBOM_NAME = "release-dependencies.spdx.json"
EXPECTED_FILES = frozenset({
    MANIFEST_NAME, CHECKSUM_NAME, AGGREGATE_SBOM_NAME, *SBOM_NAMES.values(),
})


class ReleaseError(ValueError):
    """El candidato no puede construirse o no demuestra lo que declara."""


@dataclass(frozen=True)
class GitState:
    revision: str
    created: str


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
            encoding="utf-8")
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseError(f"git command failed: {' '.join(args)}") from error
    return result.stdout.strip()


def _git_blob(root: Path, relative: str) -> bytes:
    """Read the committed bytes, independent of checkout line-ending filters.

    Release identity belongs to the Git object selected by ``HEAD``. Reading the
    worktree here makes the same clean commit hash differently on Windows when
    Git materialises CRLF, even though the index and the Linux release build use
    the canonical LF blob.
    """
    _safe_relative(relative)
    try:
        result = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{relative}"], cwd=root,
            check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseError(f"tracked release input has no Git blob: {relative}") from error
    return result.stdout


def clean_git_state(root: Path, expected_revision: str | None = None) -> GitState:
    revision = _run_git(root, "rev-parse", "HEAD")
    if not REVISION.fullmatch(revision):
        raise ReleaseError("source revision must be a full 40-character Git SHA")
    if expected_revision is not None and expected_revision != revision:
        raise ReleaseError("requested revision is not the checked out HEAD")
    if _run_git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReleaseError("release candidates require a clean Git worktree")
    raw_date = _run_git(root, "show", "-s", "--format=%cI", revision)
    try:
        parsed = datetime.fromisoformat(raw_date).astimezone(timezone.utc)
    except ValueError as error:
        raise ReleaseError("commit date is not ISO-8601") from error
    created = parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return GitState(revision, created)


def _safe_relative(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ReleaseError(f"path must use canonical POSIX separators: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ReleaseError(f"path must be canonical and relative: {value}")
    return path


def _resolved(root: Path, relative: str) -> Path:
    canonical = _safe_relative(relative)
    root = root.resolve()
    candidate = root.joinpath(*canonical.parts)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ReleaseError(f"path leaves repository: {relative}") from error
    if candidate.is_symlink():
        raise ReleaseError(f"symlinks are not release inputs: {relative}")
    return resolved


def load_contract(root: Path) -> dict[str, Any]:
    path = _resolved(root, CONTRACT_PATH.as_posix())
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError("release candidate contract is unreadable") from error
    required = {
        "schema_version", "task", "state", "allowed_data", "artifact_names",
        "source_inputs", "dependency_locks", "claims", "workflow",
    }
    if set(contract) != required:
        raise ReleaseError("release candidate contract fields drifted")
    if contract["schema_version"] != "1.1.0" or contract["task"] != "FNC-REL-001":
        raise ReleaseError("release candidate contract version or owner drifted")
    if contract["state"] != "review_pending" or contract["allowed_data"] != "synthetic_only":
        raise ReleaseError("contract may only describe a synthetic review candidate")
    if contract["artifact_names"] != ["api", "worker", "web"]:
        raise ReleaseError("the release must bind api, worker and web exactly once")
    claims = contract["claims"]
    if claims != {
        "approved": False, "published": False, "signed": False,
        "provenance_verified": False, "production_authorized": False,
    }:
        raise ReleaseError("contract attempts to claim an unproved release property")
    return contract


def _tracked_files(root: Path, relative: str) -> list[str]:
    path = _resolved(root, relative)
    if not path.exists():
        raise ReleaseError(f"declared source input is absent: {relative}")
    if path.is_file():
        files = [relative]
    elif path.is_dir():
        output = _run_git(root, "ls-files", "--", relative)
        files = sorted(line for line in output.splitlines() if line)
        if not files:
            raise ReleaseError(f"source directory has no tracked files: {relative}")
    else:
        raise ReleaseError(f"unsupported source input: {relative}")
    for item in files:
        candidate = _resolved(root, item)
        if not candidate.is_file() or candidate.is_symlink():
            raise ReleaseError(f"tracked release input is not a regular file: {item}")
    return files


def digest_source_input(root: Path, relative: str) -> tuple[str, int]:
    files = _tracked_files(root, relative)
    digest = hashlib.sha256()
    for item in files:
        raw = _git_blob(root, item)
        digest.update(item.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).digest())
        digest.update(b"\0")
    return digest.hexdigest(), len(files)


def _logical_requirements(text: str) -> Iterable[str]:
    buffer = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        buffer = f"{buffer} {stripped}".strip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1].strip()
            continue
        yield buffer
        buffer = ""
    if buffer:
        raise ReleaseError("requirements file ends in an incomplete continuation")


def python_packages(path: Path, scope: str) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line in _logical_requirements(path.read_text(encoding="utf-8")):
        match = PACKAGE.match(line)
        if not match:
            raise ReleaseError(f"unbounded or unsupported Python requirement: {line}")
        name, version = match.groups()
        hashes = sorted(set(HASH.findall(line)))
        if not hashes:
            raise ReleaseError(f"Python requirement has no SHA-256 hashes: {name}")
        key = (name.lower().replace("_", "-"), version)
        if key in seen:
            raise ReleaseError(f"duplicate Python package: {name}=={version}")
        seen.add(key)
        package_id = re.sub(r"[^A-Za-z0-9.-]", "-", f"SPDXRef-Py-{scope}-{name}-{version}")
        packages.append({
            "SPDXID": package_id,
            "checksums": [{"algorithm": "SHA256", "checksumValue": value}
                          for value in hashes],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "name": name,
            "supplier": "NOASSERTION",
            "versionInfo": version,
        })
    return sorted(packages, key=lambda item: (item["name"].lower(), item["versionInfo"]))


def _integrity_checksum(value: str) -> dict[str, str]:
    if "-" not in value:
        raise ReleaseError("npm integrity is malformed")
    algorithm, encoded = value.split("-", 1)
    spdx_algorithm = {"sha256": "SHA256", "sha512": "SHA512"}.get(algorithm)
    if spdx_algorithm is None:
        raise ReleaseError(f"unsupported npm integrity algorithm: {algorithm}")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ReleaseError("npm integrity is not valid base64") from error
    expected = 32 if algorithm == "sha256" else 64
    if len(decoded) != expected:
        raise ReleaseError("npm integrity digest has the wrong length")
    return {"algorithm": spdx_algorithm, "checksumValue": decoded.hex()}


def npm_packages(path: Path) -> list[dict[str, Any]]:
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError("npm lockfile is unreadable") from error
    if lock.get("lockfileVersion") != 3 or not isinstance(lock.get("packages"), dict):
        raise ReleaseError("only npm lockfileVersion 3 is supported")
    packages: list[dict[str, Any]] = []
    for locator, entry in sorted(lock["packages"].items()):
        if locator == "":
            continue
        if not isinstance(entry, dict):
            raise ReleaseError(f"npm package entry is not an object: {locator}")
        version, integrity = entry.get("version"), entry.get("integrity")
        if not isinstance(version, str) or not version:
            raise ReleaseError(f"npm package has no exact version: {locator}")
        if not isinstance(integrity, str) or not integrity:
            raise ReleaseError(f"npm package has no integrity digest: {locator}")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            parts = locator.removeprefix("node_modules/").split("/node_modules/")
            name = parts[-1]
        suffix = hashlib.sha256(locator.encode()).hexdigest()[:16]
        package_id = re.sub(r"[^A-Za-z0-9.-]", "-", f"SPDXRef-Npm-{name}-{version}-{suffix}")
        packages.append({
            "SPDXID": package_id,
            "checksums": [_integrity_checksum(integrity)],
            "downloadLocation": entry.get("resolved", "NOASSERTION"),
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "name": name,
            "supplier": "NOASSERTION",
            "versionInfo": version,
        })
    return packages


def spdx_document(scope: str, packages: list[dict[str, Any]], state: GitState,
                  lock_digest: str) -> dict[str, Any]:
    namespace = f"https://fincilia.invalid/spdx/{state.revision}/{scope}/{lock_digest}"
    relationships = [{
        "spdxElementId": "SPDXRef-DOCUMENT",
        "relationshipType": "DESCRIBES",
        "relatedSpdxElement": package["SPDXID"],
    } for package in packages]
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": state.created,
            "creators": ["Tool: fincilia-release-candidate-1.0"],
            "licenseListVersion": "3.26",
        },
        "dataLicense": "CC0-1.0",
        "documentNamespace": namespace,
        "name": f"fincilia-{scope}-dependencies-{state.revision[:12]}",
        "packages": packages,
        "relationships": relationships,
        "spdxVersion": "SPDX-2.3",
    }


def _schema_head(root: Path) -> str:
    migrations = _resolved(root, "db/migrations")
    versions = []
    for path in migrations.glob("V*__*.sql"):
        match = re.fullmatch(r"(V\d{4})__.+\.sql", path.name)
        if not match:
            raise ReleaseError(f"migration has a noncanonical name: {path.name}")
        versions.append(match.group(1))
    if not versions:
        raise ReleaseError("no migrations found")
    return sorted(versions)[-1]


def _validate_images(images: dict[str, str]) -> None:
    if set(images) != set(SBOM_NAMES):
        raise ReleaseError("api, worker and web image IDs are required exactly once")
    if any(not IMAGE_ID.fullmatch(value) for value in images.values()):
        raise ReleaseError("image IDs must be sha256 followed by 64 lowercase hex digits")
    if len(set(images.values())) != len(images):
        raise ReleaseError("three different services cannot share one image ID")


def create_bundle(root: Path, output: Path, images: dict[str, str], *,
                  revision: str | None = None, classification: str = "neutral",
                  ci_run_url: str) -> dict[str, Any]:
    root = root.resolve()
    state = clean_git_state(root, revision)
    contract = load_contract(root)
    _validate_images(images)
    if classification not in ("neutral", "affects_results"):
        raise ReleaseError("release classification must be neutral or affects_results")
    if not re.fullmatch(r"https://github\.com/[^/]+/[^/]+/actions/runs/\d+", ci_run_url):
        raise ReleaseError("CI evidence must be a canonical GitHub Actions run URL")

    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ReleaseError("output directory must not already contain files")
    output.mkdir(parents=True, exist_ok=True)

    locks = contract["dependency_locks"]
    if set(locks) != set(SBOM_NAMES):
        raise ReleaseError("dependency lock scopes must match artifact names")
    sbom_digests: dict[str, str] = {}
    all_packages: list[dict[str, Any]] = []
    lock_digests: dict[str, str] = {}
    for scope, relative in sorted(locks.items()):
        lock_path = _resolved(root, relative)
        lock_digest = _sha256(_git_blob(root, relative))
        packages = (npm_packages(lock_path) if scope == "web"
                    else python_packages(lock_path, scope))
        if not packages:
            raise ReleaseError(f"dependency inventory is empty: {scope}")
        all_packages.extend(packages)
        lock_digests[scope] = lock_digest
        document = spdx_document(scope, packages, state, lock_digest)
        encoded = _json_bytes(document)
        (output / SBOM_NAMES[scope]).write_bytes(encoded)
        sbom_digests[scope] = _sha256(encoded)

    aggregate_lock_digest = _sha256(_json_bytes(lock_digests))
    aggregate = spdx_document("release", all_packages, state, aggregate_lock_digest)
    aggregate_bytes = _json_bytes(aggregate)
    (output / AGGREGATE_SBOM_NAME).write_bytes(aggregate_bytes)
    aggregate_digest = _sha256(aggregate_bytes)

    inputs = []
    for relative in contract["source_inputs"]:
        digest, count = digest_source_input(root, relative)
        inputs.append({"path": relative, "sha256": digest, "tracked_file_count": count})

    artifacts = [{
        "image_id": images[name],
        "name": name,
        "published": False,
        "sbom_path": SBOM_NAMES[name],
        "sbom_sha256": sbom_digests[name],
    } for name in contract["artifact_names"]]
    manifest = {
        "approval": {
            "approved": False,
            "human_review": "pending",
            "production_authorized": False,
            "provenance_verified": False,
            "signed": False,
        },
        "artifacts": artifacts,
        "build": {
            "builder": "github-hosted-runner-unverified",
            "classification": classification,
            "created": state.created,
            "evidence": {"ci_run": ci_run_url, "state": "passed"},
        },
        "data_ceiling": "synthetic_only",
        "kind": "fincilia_release_candidate",
        "release_sbom": {
            "path": AGGREGATE_SBOM_NAME,
            "sha256": aggregate_digest,
        },
        "schema_head": _schema_head(root),
        "schema_version": "1.1.0",
        "source": {"clean": True, "inputs": inputs, "revision": state.revision},
        "state": "candidate",
    }
    manifest_bytes = _json_bytes(manifest)
    (output / MANIFEST_NAME).write_bytes(manifest_bytes)

    checksums = []
    for name in sorted(EXPECTED_FILES - {CHECKSUM_NAME}):
        checksums.append(f"{_file_digest(output / name)}  {name}")
    (output / CHECKSUM_NAME).write_text("\n".join(checksums) + "\n", encoding="ascii")
    verify_bundle(output)
    return manifest


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"{label} must be a JSON object")
    return value


def _verify_spdx(document: dict[str, Any], revision: str, scope: str) -> None:
    required = {
        "SPDXID", "creationInfo", "dataLicense", "documentNamespace", "name",
        "packages", "relationships", "spdxVersion",
    }
    if set(document) != required or document["spdxVersion"] != "SPDX-2.3":
        raise ReleaseError(f"{scope} SBOM is not the supported SPDX document")
    if document["SPDXID"] != "SPDXRef-DOCUMENT" or document["dataLicense"] != "CC0-1.0":
        raise ReleaseError(f"{scope} SBOM has invalid document identity")
    if f"/{revision}/{scope}/" not in document["documentNamespace"]:
        raise ReleaseError(f"{scope} SBOM is not bound to the release revision")
    packages = document.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ReleaseError(f"{scope} SBOM has no packages")
    ids = [package.get("SPDXID") for package in packages if isinstance(package, dict)]
    if len(ids) != len(packages) or len(set(ids)) != len(ids):
        raise ReleaseError(f"{scope} SBOM package identifiers are invalid or duplicated")
    for package in packages:
        if package.get("filesAnalyzed") is not False:
            raise ReleaseError(f"{scope} SBOM overclaims file analysis")
        checksums = package.get("checksums")
        if not isinstance(checksums, list) or not checksums:
            raise ReleaseError(f"{scope} SBOM package has no integrity checksum")


def _read_checksums(bundle: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = (bundle / CHECKSUM_NAME).read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError("bundle checksums are unreadable") from error
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9.-]*)", line)
        if not match:
            raise ReleaseError("bundle checksum line is not canonical")
        digest, name = match.groups()
        if name in checksums:
            raise ReleaseError(f"duplicate checksum entry: {name}")
        checksums[name] = digest
    expected = EXPECTED_FILES - {CHECKSUM_NAME}
    if set(checksums) != expected:
        raise ReleaseError("bundle checksum inventory is incomplete or has extras")
    return checksums


def verify_bundle(bundle: Path) -> dict[str, Any]:
    bundle = bundle.resolve()
    if not bundle.is_dir() or bundle.is_symlink():
        raise ReleaseError("bundle must be a regular directory")
    entries = {path.name for path in bundle.iterdir()}
    if entries != EXPECTED_FILES:
        raise ReleaseError("bundle contains missing, extra or nested files")
    for path in bundle.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"bundle entry is not a regular file: {path.name}")
    checksums = _read_checksums(bundle)
    for name, expected in checksums.items():
        if _file_digest(bundle / name) != expected:
            raise ReleaseError(f"bundle file digest mismatch: {name}")

    manifest = _load_json(bundle / MANIFEST_NAME, "manifest")
    required = {
        "approval", "artifacts", "build", "data_ceiling", "kind", "schema_head",
        "schema_version", "source", "state", "release_sbom",
    }
    if set(manifest) != required:
        raise ReleaseError("manifest fields drifted")
    if manifest["kind"] != "fincilia_release_candidate" or manifest["state"] != "candidate":
        raise ReleaseError("bundle is not a release candidate")
    if manifest["schema_version"] != "1.1.0" or manifest["data_ceiling"] != "synthetic_only":
        raise ReleaseError("unsupported schema or data ceiling")
    approval = manifest["approval"]
    if approval != {
        "approved": False, "human_review": "pending", "production_authorized": False,
        "provenance_verified": False, "signed": False,
    }:
        raise ReleaseError("manifest claims an approval, signature or provenance it cannot prove")
    revision = manifest.get("source", {}).get("revision")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ReleaseError("manifest source revision is not a full Git SHA")
    if manifest["source"].get("clean") is not True:
        raise ReleaseError("manifest does not attest a clean source tree")
    if not re.fullmatch(r"V\d{4}", str(manifest["schema_head"])):
        raise ReleaseError("manifest schema head is invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or [item.get("name") for item in artifacts] != ["api", "worker", "web"]:
        raise ReleaseError("manifest artifacts are missing, duplicated or reordered")
    image_ids: set[str] = set()
    for artifact in artifacts:
        scope = artifact["name"]
        if set(artifact) != {"image_id", "name", "published", "sbom_path", "sbom_sha256"}:
            raise ReleaseError(f"artifact fields drifted: {scope}")
        if artifact["published"] is not False or not IMAGE_ID.fullmatch(artifact["image_id"]):
            raise ReleaseError(f"artifact is published or has invalid identity: {scope}")
        if artifact["image_id"] in image_ids:
            raise ReleaseError("artifact image IDs must be unique")
        image_ids.add(artifact["image_id"])
        if artifact["sbom_path"] != SBOM_NAMES[scope] or not SHA256.fullmatch(artifact["sbom_sha256"]):
            raise ReleaseError(f"artifact SBOM reference is invalid: {scope}")
        if _file_digest(bundle / artifact["sbom_path"]) != artifact["sbom_sha256"]:
            raise ReleaseError(f"artifact SBOM digest does not match: {scope}")
        _verify_spdx(_load_json(bundle / artifact["sbom_path"], f"{scope} SBOM"), revision, scope)
    release_sbom = manifest.get("release_sbom")
    if release_sbom != {
        "path": AGGREGATE_SBOM_NAME,
        "sha256": _file_digest(bundle / AGGREGATE_SBOM_NAME),
    }:
        raise ReleaseError("aggregate release SBOM reference is invalid")
    aggregate = _load_json(bundle / AGGREGATE_SBOM_NAME, "release SBOM")
    _verify_spdx(aggregate, revision, "release")
    expected_package_ids = {
        package["SPDXID"]
        for scope in SBOM_NAMES
        for package in _load_json(bundle / SBOM_NAMES[scope], f"{scope} SBOM")["packages"]
    }
    actual_package_ids = {package["SPDXID"] for package in aggregate["packages"]}
    if actual_package_ids != expected_package_ids:
        raise ReleaseError("aggregate release SBOM does not cover every artifact package")
    return manifest


def verify_source(root: Path, bundle: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = verify_bundle(bundle)
    state = clean_git_state(root, manifest["source"]["revision"])
    if state.revision != manifest["source"]["revision"]:
        raise ReleaseError("bundle revision differs from checked out source")
    contract = load_contract(root)
    actual = []
    for relative in contract["source_inputs"]:
        digest, count = digest_source_input(root, relative)
        actual.append({"path": relative, "sha256": digest, "tracked_file_count": count})
    if actual != manifest["source"].get("inputs"):
        raise ReleaseError("source inputs differ from the release manifest")
    if _schema_head(root) != manifest["schema_head"]:
        raise ReleaseError("source migration head differs from release manifest")
    return manifest
