"""Archivo determinista y verificador fail-closed para attestations."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path, PurePosixPath

from .model import EXPECTED_FILES, ReleaseError, verify_bundle

ARCHIVE_ROOT = "fincilia-release"


def create_archive(bundle: Path, output: Path) -> dict:
    """Empaqueta exactamente el bundle validado con metadatos normalizados."""
    bundle = bundle.resolve()
    manifest = verify_bundle(bundle)
    output = output.resolve()
    if output.exists():
        raise ReleaseError("archive output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                           compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
                for name in sorted(EXPECTED_FILES):
                    data = (bundle / name).read_bytes()
                    info = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{name}")
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
    verify_archive(bundle, output)
    return manifest


def verify_archive(bundle: Path, archive_path: Path) -> dict:
    """Comprueba inventario, metadatos y bytes sin extraer rutas no confiables."""
    bundle = bundle.resolve()
    manifest = verify_bundle(bundle)
    archive_path = archive_path.resolve()
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ReleaseError("archive must be a regular file")
    expected_names = {f"{ARCHIVE_ROOT}/{name}" for name in EXPECTED_FILES}
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)) or set(names) != expected_names:
                raise ReleaseError("archive inventory is missing, duplicated or has extras")
            for member in members:
                path = PurePosixPath(member.name)
                if (not member.isfile() or path.is_absolute() or ".." in path.parts
                        or member.mtime != 0 or member.mode != 0o644
                        or member.uid != 0 or member.gid != 0):
                    raise ReleaseError("archive entry type, path or metadata is unsafe")
                source = bundle / path.name
                extracted = archive.extractfile(member)
                if extracted is None or extracted.read() != source.read_bytes():
                    raise ReleaseError(f"archive entry differs from bundle: {path.name}")
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ReleaseError("archive is unreadable") from error
    return manifest
