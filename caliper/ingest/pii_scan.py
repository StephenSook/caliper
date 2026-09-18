"""Identifier scanner run across every supplied sheet at ingest.

One of the supplied training workbooks contains member-format identifiers, group
numbers, dates of service, dollar amounts and full names used as practice
examples. We therefore treat EVERY supplied sheet as potentially carrying
identifiers, scan all of them, and report a redaction count on the intake screen.

That count is the product demonstrating responsible data use rather than
claiming it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered most specific first so a value is attributed to its narrowest pattern.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("MEMBER_ID", re.compile(r"\b[A-Z]{3}\d{6,12}\b")),
    # "grp" alone missed the spelling people actually use. The untested pattern
    # was the ineffective one, which is not a coincidence: nothing ever planted a
    # violation against it, so nothing ever exercised what it matches.
    ("GROUP_NUMBER", re.compile(r"\b(?:grp|group)\s*(?:no\.?|#)?\s*:?\s*\d{4,}\b", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")),
    ("DATE_OF_SERVICE", re.compile(r"\b(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b")),
    ("CLAIM_OR_CALL_ID", re.compile(r"\b(?:claim|call|ref)\s*(?:id|no|#)?\s*:?\s*\d{5,}\b", re.I)),
]

REDACTION = "[REDACTED:{kind}]"


@dataclass
class ScanResult:
    redacted_text: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def scan_and_redact(text: str) -> ScanResult:
    if not text:
        return ScanResult("", {})
    counts: dict[str, int] = {}
    out = text
    for kind, pattern in PATTERNS:
        found = pattern.findall(out)
        if found:
            counts[kind] = counts.get(kind, 0) + len(found)
            out = pattern.sub(REDACTION.format(kind=kind), out)
    return ScanResult(out, counts)


def scan_many(values) -> ScanResult:
    """Scan an iterable of cell values and aggregate the counts."""
    total: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        result = scan_and_redact(str(value))
        for kind, count in result.counts.items():
            total[kind] = total.get(kind, 0) + count
    return ScanResult("", total)
