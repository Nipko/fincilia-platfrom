"""Reglas de admision de ficheros. Solo biblioteca estandar, sin efectos.

Todo lo que decide si unos bytes entran vive aqui y es una funcion pura, para que
se pueda probar con los bytes exactos que causaron un problema en vez de tener
que reproducir una subida.

Tres decisiones ordenan el modulo:

1. **El tipo se decide por firma, nunca por extension.** La extension la elige
   quien sube el fichero; los primeros bytes los escribio el programa que lo
   genero. Renombrar `algo.exe` a `extracto.csv` no lo convierte en un CSV.
2. **Los limites se comprueban antes de descomprimir**, no despues. Un ZIP de
   dos kilobytes puede expandirse a varios gigabytes, y comprobar el tamano
   despues de expandirlo es comprobarlo cuando ya te lo comiste.
3. **Un hallazgo nunca repite el valor que encontro.** Si el escaner de
   tarjetas escribiera el numero en el log, habria copiado a un sitio con menos
   proteccion justo lo que estaba intentando contener.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Final

# --------------------------------------------------------------------------- #
# Limites
# --------------------------------------------------------------------------- #

MAX_UPLOAD_BYTES: Final[int] = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES: Final[int] = 200 * 1024 * 1024
# Un ZIP legitimo de datos tabulares comprime bien, pero no cien veces. Por
# encima de esta razon se rechaza sin expandir.
MAX_COMPRESSION_RATIO: Final[int] = 100
MAX_ARCHIVE_ENTRIES: Final[int] = 512
MAX_TEXT_LINES: Final[int] = 1_000_000
SNIFF_BYTES: Final[int] = 8192

# --------------------------------------------------------------------------- #
# Tipos
# --------------------------------------------------------------------------- #

# Orden significativo: la firma mas larga primero, para que un prefijo corto no
# se lleve un fichero que en realidad es de otro tipo.
SIGNATURES: Final[tuple[tuple[bytes, str], ...]] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/vnd.ms-excel"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x1f\x8b", "application/gzip"),
)

# Lo que nunca entra, se llame como se llame.
EXECUTABLE_SIGNATURES: Final[tuple[tuple[bytes, str], ...]] = (
    (b"MZ", "dos_or_windows_executable"),
    (b"\x7fELF", "elf_executable"),
    (b"\xca\xfe\xba\xbe", "java_class_or_macho_fat"),
    (b"\xfe\xed\xfa\xce", "mach_o_executable"),
    (b"\xfe\xed\xfa\xcf", "mach_o_executable"),
    (b"#!", "interpreter_script"),
)

ACCEPTED_MEDIA_TYPES: Final[frozenset[str]] = frozenset({
    "text/csv", "application/pdf",
    # `application/zip` cubre xlsx/ods: son ZIP por dentro y se miran como ZIP.
    "application/zip",
})

EXTENSION_TYPES: Final[dict[str, str]] = {
    ".csv": "text/csv", ".txt": "text/plain", ".tsv": "text/csv",
    ".pdf": "application/pdf", ".xlsx": "application/zip",
    ".ods": "application/zip", ".zip": "application/zip",
    ".xls": "application/vnd.ms-excel", ".gz": "application/gzip",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
}

DELIMITERS: Final[tuple[str, ...]] = (",", ";", "\t", "|")

# --------------------------------------------------------------------------- #
# Deteccion de secretos
# --------------------------------------------------------------------------- #

PAN_CANDIDATE = re.compile(r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])")
SECRET_PATTERNS: Final[tuple[tuple[str, "re.Pattern[str]"], ...]] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("password_assignment",
     re.compile(r"(?i)\b(?:password|passwd|contrase(?:n|ñ)a|secret|api[_-]?key)"
                r"\s*[:=]\s*\S{6,}")),
    ("connection_string",
     re.compile(r"(?i)\b(?:postgres|postgresql|mysql|mongodb)://[^\s:]+:[^\s@]+@")),
)


class RejectedUpload(ValueError):
    """Los bytes no se admiten. El motivo no repite el contenido."""


@dataclass(frozen=True)
class Finding:
    """Un hallazgo. Lleva donde y de que tipo, jamas el valor."""

    kind: str
    location: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "location": self.location, "detail": self.detail}


@dataclass(frozen=True)
class Detection:
    media_type: str
    declared_type: str | None
    extension_matches: bool
    sniffed_bytes: int

    @property
    def accepted(self) -> bool:
        return self.media_type in ACCEPTED_MEDIA_TYPES


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def extension_type(filename: str) -> str | None:
    lowered = filename.lower()
    for extension, media_type in EXTENSION_TYPES.items():
        if lowered.endswith(extension):
            return media_type
    return None


def looks_textual(head: bytes) -> bool:
    if b"\x00" in head:
        # Un NUL en los primeros kilobytes descarta texto: ningun CSV lo lleva y
        # si aparece es que estamos mirando un binario.
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass
    # Latin-1 decodifica cualquier byte, asi que no sirve como prueba. Se exige
    # que la practica totalidad sea imprimible.
    printable = sum(1 for byte in head if 9 <= byte <= 13 or 32 <= byte <= 126
                    or 160 <= byte <= 255)
    return bool(head) and printable / len(head) > 0.95


def detect(payload: bytes, filename: str = "") -> Detection:
    """Tipo real de los bytes, y si la extension decia la verdad."""
    head = payload[:SNIFF_BYTES]
    declared = extension_type(filename) if filename else None

    for signature, label in EXECUTABLE_SIGNATURES:
        if head.startswith(signature):
            raise RejectedUpload(f"executable content is never accepted ({label})")

    detected = ""
    for signature, media_type in SIGNATURES:
        if head.startswith(signature):
            detected = media_type
            break
    if not detected:
        if not looks_textual(head):
            raise RejectedUpload("unrecognised binary content")
        text = head.decode("utf-8", errors="replace")
        first = text.splitlines()[0] if text.splitlines() else ""
        detected = "text/csv" if any(item in first for item in DELIMITERS) else "text/plain"

    return Detection(detected, declared, declared is None or declared == detected,
                     len(head))


def check_size(byte_size: int) -> None:
    if byte_size <= 0:
        raise RejectedUpload("an empty file carries no evidence")
    if byte_size > MAX_UPLOAD_BYTES:
        raise RejectedUpload(
            f"file exceeds the {MAX_UPLOAD_BYTES} byte ceiling for a single upload")


def inspect_archive(payload: bytes) -> list[Finding]:
    """Mira un ZIP **sin** expandirlo: la cabecera ya dice cuanto ocuparia."""
    findings: list[Finding] = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
    except zipfile.BadZipFile as error:
        raise RejectedUpload("the archive is not readable") from error

    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise RejectedUpload(
            f"the archive declares {len(entries)} entries, over the {MAX_ARCHIVE_ENTRIES} ceiling")
    total = sum(entry.file_size for entry in entries)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise RejectedUpload(
            f"the archive declares {total} uncompressed bytes, over the ceiling")
    if payload and total / max(1, len(payload)) > MAX_COMPRESSION_RATIO:
        raise RejectedUpload(
            "the archive expands more than the accepted ratio; it is treated as a bomb")

    for entry in entries:
        name = entry.filename
        # Una entrada con `..` o ruta absoluta solo sirve para escribir fuera del
        # destino. No se expande nada aqui, pero admitirla seria dejar la trampa
        # armada para el primero que la expanda.
        if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
            raise RejectedUpload("the archive contains a path that escapes its root")
        if entry.file_size and entry.compress_size and \
                entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
            findings.append(Finding("high_compression_entry", name,
                                    "single entry expands far beyond its stored size"))
    return findings


def luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def scan_secrets(payload: bytes, *, max_findings: int = 50) -> list[Finding]:
    """Busca tarjetas y credenciales. Devuelve donde, nunca que.

    La comprobacion de Luhn no esta por elegancia: sin ella, cualquier columna de
    identificadores largos se marcaria como tarjeta y el escaner se volveria
    ruido que la gente aprende a ignorar.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("latin-1", errors="replace")

    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if len(findings) >= max_findings:
            break
        for match in PAN_CANDIDATE.finditer(line):
            digits = re.sub(r"[ -]", "", match.group())
            if 13 <= len(digits) <= 19 and luhn_valid(digits):
                findings.append(Finding(
                    "payment_card_number", f"line {line_number}",
                    f"{len(digits)} digits passing the Luhn check"))
                break
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(kind, f"line {line_number}",
                                        "matches a credential pattern"))
    return findings[:max_findings]


def count_lines(payload: bytes) -> int:
    lines = payload.count(b"\n")
    if lines > MAX_TEXT_LINES:
        raise RejectedUpload(f"file exceeds the {MAX_TEXT_LINES} line ceiling")
    return lines


@dataclass(frozen=True)
class Admission:
    """Resultado de examinar unos bytes. `zone` dice donde pueden vivir."""

    content_sha256: str
    byte_size: int
    media_type: str
    extension_matches: bool
    zone: str
    findings: tuple[Finding, ...]

    @property
    def promoted(self) -> bool:
        return self.zone == "raw"

    def as_dict(self) -> dict[str, object]:
        return {"content_sha256": self.content_sha256, "byte_size": self.byte_size,
                "media_type": self.media_type,
                "extension_matches": self.extension_matches, "zone": self.zone,
                "findings": [item.as_dict() for item in self.findings]}


def admit(payload: bytes, filename: str) -> Admission:
    """Examina unos bytes y decide si pueden salir de cuarentena.

    Nada se promueve a `raw` si aparece un secreto. Se conserva en cuarentena en
    vez de borrarse: quien subio el fichero necesita saber que paso, y borrar la
    evidencia de un incidente es la peor forma de responder a uno.
    """
    check_size(len(payload))
    detection = detect(payload, filename)
    if not detection.accepted:
        raise RejectedUpload(f"{detection.media_type} is not an accepted document type")

    findings: list[Finding] = []
    if not detection.extension_matches:
        findings.append(Finding(
            "extension_mismatch", filename,
            f"the name suggests {detection.declared_type}, the bytes say "
            f"{detection.media_type}"))

    if detection.media_type == "application/zip":
        findings.extend(inspect_archive(payload))
    elif detection.media_type.startswith("text/"):
        count_lines(payload)

    # El escaner solo mira texto. Dentro de un PDF o un ZIP hay que extraer
    # primero, y eso lo hace el worker en su propio aislamiento.
    if detection.media_type.startswith("text/"):
        findings.extend(scan_secrets(payload))

    sensitive = any(item.kind in {"payment_card_number", "private_key",
                                  "aws_access_key", "bearer_token",
                                  "password_assignment", "connection_string"}
                    for item in findings)
    zone = "quarantine" if sensitive else "raw"
    return Admission(sha256_bytes(payload), len(payload), detection.media_type,
                     detection.extension_matches, zone, tuple(findings))
