"""A scan for personal data, run on every import and over the synthetic content in git.

It looks for emails, phone numbers, Medicare numbers, long identifiers, and (for
imports) people's names. Synthetic content stays recognisably fictional:

- emails use reserved domains such as ``example.test``;
- phone numbers come from ACMA's ranges reserved for fiction, or are public
  service lines (13, 1300 and 1800 numbers, and listed services);
- member and claim numbers carry a ``TEST`` marker.

A hit blocks an import until an admin approves it. The scan is a safety net, not a
guarantee: reviewers still read what they approve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RESERVED_EMAIL_DOMAINS = ("example.test", "example.com", "example.org", "example.net")
RESERVED_TLDS = (".test", ".example", ".invalid", ".localhost")

# ACMA numbers for use in fiction: a fixed list of mobiles, and landline blocks
# (area code then 5550 xxxx or 7010 xxxx).
FICTIONAL_MOBILES = {
    "0491570006", "0491570156", "0491570157", "0491570158", "0491570159",
    "0491570110", "0491570313", "0491570737", "0491571266", "0491571491",
    "0491571804", "0491572549", "0491572665", "0491572983", "0491573770",
    "0491573087", "0491574118", "0491574632", "0491575254", "0491575789",
    "0491576398", "0491576801", "0491577426", "0491577644", "0491578957",
    "0491578148", "0491578888", "0491579212", "0491579760", "0491579455",
}  # fmt: skip
FICTIONAL_LANDLINE = re.compile(r"^0[2378](5550|7010)\d{4}$")
# Public support lines that may appear in agent content.
PUBLIC_SERVICE_NUMBERS = {"0477131114"}  # Lifeline's text line

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w-])(?:\+61[\s-]?|\(?0)[2-478]\)?(?:[\s-]?\d){8}(?![\w-])")
SERVICE_LINE = re.compile(r"^(13\d{4}|1[38]00\d{6})$")
MEDICARE = re.compile(r"(?<![\w-])[2-6]\d{3}\s?\d{5}\s?\d(?:[\s-]?\d)?(?![\w-])")
LONG_NUMBER = re.compile(r"(?<![\w.,-])\d{8,}(?![\w.,-])")
MARKED_IDENTIFIER = re.compile(r"\bTEST\b|-TEST-|TEST-", re.IGNORECASE)
# Given names common in Australia; two capitalised words led by one suggest a person.
GIVEN_NAMES = {
    "james", "john", "robert", "michael", "william", "david", "richard", "joseph",
    "thomas", "charles", "daniel", "matthew", "anthony", "mark", "paul", "steven",
    "andrew", "joshua", "peter", "jack", "oliver", "noah", "liam", "lucas", "ethan",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan",
    "jessica", "sarah", "karen", "emily", "emma", "olivia", "charlotte", "amelia",
    "isla", "mia", "chloe", "sophie", "grace", "ruby", "lily", "zoe", "hannah",
    "michelle", "nicole", "rebecca", "kylie", "melissa", "lisa", "amanda", "rachel",
    "wei", "li", "priya", "raj", "mohammed", "fatima", "aisha", "ahmed", "nguyen",
}  # fmt: skip
NAME = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b")


@dataclass(frozen=True)
class Finding:
    kind: str
    value: str
    line: int
    path: str | None = None

    @property
    def masked(self) -> str:
        keep = max(2, len(self.value) // 5)
        return self.value[:keep] + "…" + self.value[-keep:] if len(self.value) > 6 else "…"

    def describe(self) -> str:
        where = f"{self.path}:{self.line}" if self.path else f"line {self.line}"
        return f"{where}: possible {self.kind} ({self.masked})"


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return "0" + digits[2:] if digits.startswith("61") else digits


def _medicare_valid(digits: str) -> bool:
    weights = (1, 3, 7, 9, 1, 3, 7, 9)
    if len(digits) < 10 or digits[0] not in "23456":
        return False
    check = sum(int(d) * w for d, w in zip(digits[:8], weights, strict=True)) % 10
    return check == int(digits[8])


def _email_allowed(email: str) -> bool:
    domain = email.rsplit("@", 1)[1].lower()
    return domain in RESERVED_EMAIL_DOMAINS or domain.endswith(RESERVED_TLDS)


def _phone_allowed(digits: str) -> bool:
    return (
        digits in FICTIONAL_MOBILES
        or digits in PUBLIC_SERVICE_NUMBERS
        or bool(FICTIONAL_LANDLINE.match(digits))
    )


def scan_text(text: str, *, check_names: bool, path: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in EMAIL.finditer(line):
            if not _email_allowed(match.group(0)):
                findings.append(Finding("email address", match.group(0), number, path))
        for match in PHONE.finditer(line):
            digits = _digits(match.group(0))
            if not _phone_allowed(digits):
                findings.append(Finding("phone number", match.group(0), number, path))
        for match in MEDICARE.finditer(line):
            digits = re.sub(r"\D", "", match.group(0))
            if _medicare_valid(digits) and not _phone_allowed(digits):
                findings.append(Finding("Medicare number", match.group(0), number, path))
        for match in LONG_NUMBER.finditer(line):
            value = match.group(0)
            if SERVICE_LINE.match(value) or _phone_allowed(_digits(value)):
                continue
            window = line[max(0, match.start() - 6) : match.end() + 6]
            if not MARKED_IDENTIFIER.search(window):
                findings.append(Finding("identifier", value, number, path))
        if check_names:
            for match in NAME.finditer(line):
                if match.group(1).lower() in GIVEN_NAMES:
                    findings.append(Finding("person's name", match.group(0), number, path))
    return findings


SCANNED_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".txt", ".csv"}


def scan_tree(root: Path, folders: list[str]) -> list[Finding]:
    """Scan synthetic content in git. Names are not checked: personas are fictional people."""
    findings: list[Finding] = []
    for folder in folders:
        for path in sorted((root / folder).rglob("*")):
            if path.is_file() and path.suffix in SCANNED_SUFFIXES:
                text = path.read_text(encoding="utf-8")
                relative = path.relative_to(root).as_posix()
                findings.extend(scan_text(text, check_names=False, path=relative))
    return findings
