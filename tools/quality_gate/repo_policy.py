from __future__ import annotations

import io
import re
import subprocess
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

FORBIDDEN_PREFIXES = (
    "artifacts/",
    "data/",
    "exports/",
    "quarantine/",
    "raw/",
    "secrets/",
    "uploads/",
)
SENSITIVE_SUFFIXES = (".key", ".p12", ".pem", ".pfx")
SENSITIVE_NAMES = {"id_ed25519", "id_rsa"}
TODO_SCAN_EXTENSIONS = {".js", ".mjs", ".py", ".sql", ".ts", ".tsx", ".yaml", ".yml"}
MAX_TRACKED_FILE_BYTES = 5 * 1024 * 1024
PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[0-9a-f]{40}$")
PINNED_IMAGE = re.compile(r"^\s*image:\s*[^\s#]+@sha256:[0-9a-f]{64}(?:\s*(?:#.*)?)$")
TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME)\b", re.IGNORECASE)
TASK_ID_PATTERN = re.compile(r"\bFNC-[A-Z]+-\d{3}\b")
SECRET_PATTERNS = {
    "POL-AWS-ACCESS-KEY": re.compile(rb"AKIA[A-Z0-9]{16}"),
    "POL-GITHUB-TOKEN": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "POL-GOOGLE-API-KEY": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "POL-OPENAI-KEY": re.compile(rb"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "POL-PRIVATE-KEY": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "POL-SLACK-TOKEN": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "POL-STRIPE-LIVE-KEY": re.compile(rb"sk_live_[A-Za-z0-9]{20,}"),
}


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _normalized_path(raw_path: str) -> str:
    return PurePosixPath(raw_path.replace("\\", "/")).as_posix()


def _decode_text(content: bytes) -> str | None:
    if b"\x00" in content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError:
            return None


def _scan_workflow(path: str, text: str) -> Iterable[Finding]:
    lowered = text.lower()
    if re.search(r"(?m)^\s*pull_request_target\s*:", text):
        yield Finding("POL-WORKFLOW-DANGEROUS-TRIGGER", path, "pull_request_target is prohibited")
    if "write-all" in lowered or re.search(r"(?m)^\s*(?:contents|id-token)\s*:\s*write\s*$", text):
        yield Finding("POL-WORKFLOW-WRITE-PERMISSION", path, "workflow requests a prohibited write permission")
    if not re.search(r"(?ms)^permissions:\s*\n\s+contents:\s*read\s*$", text):
        yield Finding("POL-WORKFLOW-PERMISSIONS", path, "workflow must declare top-level contents: read")
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\s*-?\s*uses:\s*([^\s#]+)", line)
        if not match:
            continue
        action = match.group(1)
        if action.startswith("./"):
            continue
        if not PINNED_ACTION.fullmatch(action):
            yield Finding(
                "POL-ACTION-UNPINNED",
                path,
                f"line {line_number}: action must be pinned to a 40-character commit SHA",
            )


def _scan_compose(path: str, text: str) -> Iterable[Finding]:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not re.match(r"^\s*image:\s*", line):
            continue
        if not PINNED_IMAGE.fullmatch(line):
            yield Finding(
                "POL-IMAGE-UNPINNED",
                path,
                f"line {line_number}: image must include an immutable sha256 digest",
            )


def _comment_lines(suffix: str, text: str) -> Iterable[tuple[int, str]]:
    if suffix == ".py":
        try:
            tokens = tokenize.generate_tokens(io.StringIO(text).readline)
            for token in tokens:
                if token.type == tokenize.COMMENT:
                    yield token.start[0], token.string
        except (IndentationError, tokenize.TokenError):
            return
        return

    markers = {
        ".js": ("//", "/*", "*"),
        ".mjs": ("//", "/*", "*"),
        ".sql": ("--", "/*", "*"),
        ".ts": ("//", "/*", "*"),
        ".tsx": ("//", "/*", "*"),
        ".yaml": ("#",),
        ".yml": ("#",),
    }
    allowed_markers = markers.get(suffix, ())
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(allowed_markers):
            yield line_number, stripped


def scan_entries(entries: Mapping[str, bytes]) -> list[Finding]:
    findings: list[Finding] = []
    for raw_path, content in sorted(entries.items()):
        path = _normalized_path(raw_path)
        lowered = path.lower()
        file_name = PurePosixPath(path).name.lower()
        suffix = PurePosixPath(path).suffix.lower()

        if any(lowered.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            findings.append(Finding("POL-DATA-PATH-PROHIBITED", path, "tracked data path is prohibited"))
        if file_name == ".env" or (file_name.startswith(".env.") and file_name != ".env.example"):
            findings.append(Finding("POL-ENV-TRACKED", path, "tracked environment file is prohibited"))
        if suffix in SENSITIVE_SUFFIXES or file_name in SENSITIVE_NAMES:
            findings.append(Finding("POL-SENSITIVE-FILE", path, "tracked key/certificate container is prohibited"))
        if len(content) > MAX_TRACKED_FILE_BYTES:
            findings.append(Finding("POL-FILE-TOO-LARGE", path, "tracked file exceeds the 5 MiB E0 limit"))

        for code, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(Finding(code, path, "high-signal secret pattern detected"))

        text = _decode_text(content)
        if text is None:
            continue
        if suffix in TODO_SCAN_EXTENSIONS:
            for line_number, comment in _comment_lines(suffix, text):
                if TODO_PATTERN.search(comment) and not TASK_ID_PATTERN.search(comment):
                    findings.append(
                        Finding(
                            "POL-ANONYMOUS-TODO",
                            path,
                            f"line {line_number}: TODO/FIXME requires an FNC task ID",
                        )
                    )
        if lowered.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
            findings.extend(_scan_workflow(path, text))
        if file_name in {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
            findings.extend(_scan_compose(path, text))

    return sorted(set(findings))


def tracked_entries(root: Path) -> dict[str, bytes]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = [item.decode("utf-8") for item in result.stdout.split(b"\x00") if item]
    entries: dict[str, bytes] = {}
    for path in paths:
        candidate = root / path
        if candidate.is_symlink():
            entries[path] = b"SYMLINK\x00" + str(candidate.readlink()).encode("utf-8")
            continue
        entries[path] = candidate.read_bytes()
    return entries


def scan_repository(root: Path) -> list[Finding]:
    entries = tracked_entries(root)
    findings = scan_entries(entries)
    for path, content in entries.items():
        if content.startswith(b"SYMLINK\x00"):
            findings.append(Finding("POL-TRACKED-SYMLINK", path, "tracked symlinks are prohibited in E0"))
    return sorted(set(findings))
