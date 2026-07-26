"""Cross-platform integrity helpers for packaged model artifacts."""

from __future__ import annotations

import hashlib
from os import PathLike
from pathlib import Path


def artifact_sha256(path: str | PathLike[str]) -> str:
    """Return a stable checksum for an artifact on Windows and Linux.

    Git normalizes tracked JSON files to LF, while locally generated files may
    use CRLF on Windows. JSON line endings do not change its meaning, so they
    are canonicalized before hashing. Binary model artifacts remain byte-exact.
    """
    artifact_path = Path(path)
    content = artifact_path.read_bytes()
    if artifact_path.suffix.lower() == ".json":
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()
