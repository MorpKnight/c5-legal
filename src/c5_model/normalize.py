"""Conservative normalization helpers for Indonesian legal glossary records."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse


WHITESPACE_RE = re.compile(r"\s+")
YEAR_RE = re.compile(r"\bTahun\s+(?P<year>(?:19|20)\d{2})\b", re.IGNORECASE)
NUMBER_YEAR_RE = re.compile(
    r"\bNomor\s+(?P<number>.+?)\s+Tahun\s+(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"\bNomor\s+(?P<number>[A-Za-z0-9./-]+)", re.IGNORECASE)
ANY_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def normalize_display_text(value: str | None) -> str:
    """Normalize Unicode and whitespace while preserving display capitalization."""

    normalized = unicodedata.normalize("NFKC", value or "").replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", normalized).strip()


def normalize_key(value: str | None) -> str:
    """Return a case-insensitive deterministic comparison key."""

    return normalize_display_text(value).casefold()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\u001f".join(normalize_key(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{prefix}_{digest}"


def strip_term_prefix(term: str, definition: str) -> tuple[str, bool]:
    """Remove an answer-bearing term prefix without rewriting the definition."""

    clean_term = normalize_display_text(term)
    clean_definition = normalize_display_text(definition)
    if not clean_term or not clean_definition:
        return clean_definition, False

    pattern = re.compile(
        rf"^{re.escape(clean_term)}(?:\s*[,;:\-–—]\s*|\s+)(?:(?:adalah|merupakan)\s+)?",
        re.IGNORECASE,
    )
    retrieval_text, substitutions = pattern.subn("", clean_definition, count=1)
    retrieval_text = retrieval_text.strip()
    if substitutions and retrieval_text:
        return retrieval_text, True
    return clean_definition, False


def parse_regulation_label(label: str) -> dict[str, str]:
    """Best-effort parsing that always preserves the original source label."""

    clean_label = normalize_display_text(label)
    regulation_type = clean_label
    regulation_number = ""
    regulation_year = ""

    type_match = re.match(r"^(?P<type>.+?)\s+Nomor\b", clean_label, re.IGNORECASE)
    if type_match:
        regulation_type = type_match.group("type").strip()

    number_year_match = NUMBER_YEAR_RE.search(clean_label)
    if number_year_match:
        regulation_number = number_year_match.group("number").strip()
        regulation_year = number_year_match.group("year")
    else:
        number_match = NUMBER_RE.search(clean_label)
        if number_match:
            regulation_number = number_match.group("number").strip()
        year_match = YEAR_RE.search(clean_label)
        if year_match:
            regulation_year = year_match.group("year")
        else:
            years = ANY_YEAR_RE.findall(clean_label)
            if years:
                regulation_year = years[-1]

    return {
        "regulation_label": clean_label,
        "regulation_type": regulation_type,
        "regulation_number": regulation_number,
        "regulation_year": regulation_year,
    }


def source_host(url: str) -> str:
    return (urlparse(normalize_display_text(url)).hostname or "").casefold()
