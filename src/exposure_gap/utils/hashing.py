"""Content hashing helpers.

`git_blob_sha1` reproduces Git's / Software Heritage's `sha1_git` so a locally fetched
file can be looked up against the SWH archive and The Stack v2 without any download.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    """`sha1_git` = SHA-1 of ``b"blob <len>\\0" + data`` (Git object identity)."""
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def git_blob_sha1_text(text: str) -> str:
    return git_blob_sha1(text.encode("utf-8"))
