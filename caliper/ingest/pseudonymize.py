"""Deterministic pseudonymization applied at ingest.

The supplied exports already carry personnel pseudonyms ("Agent 1", "QA 1").
We do not rely on that. We apply our own mapping at the boundary and never emit
the source value anywhere downstream, so no rendered surface, log line, export or
screenshot can carry a supplied identifier even by accident.

The salt is per run and is not persisted with the output, so the mapping is
stable within a run and not reversible from the artifacts alone.
"""

from __future__ import annotations

import hashlib
import os
import secrets


def new_salt() -> str:
    return os.environ.get("CALIPER_PSEUDONYM_SALT") or secrets.token_hex(16)


def pseudonymize(raw: str, salt: str, prefix: str) -> str:
    """Stable short pseudonym, e.g. "A-4f2c"."""
    digest = hashlib.blake2s((salt + str(raw)).encode("utf-8"), digest_size=2).hexdigest()
    return f"{prefix}-{digest}"
