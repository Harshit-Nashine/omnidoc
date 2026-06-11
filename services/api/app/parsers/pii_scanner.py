# ================================================================
# services/api/app/parsers/pii_scanner.py
# ================================================================
# Scans extracted document text for PII using Microsoft Presidio.
#
# WHY PRESIDIO OVER CUSTOM REGEX:
# Presidio uses NLP context + pattern matching together.
# Pure regex misses contextual PII — e.g. "call me at five five
# five..." written out in words. Presidio catches these.
# It also ships with Indian-specific recognizers for Aadhaar + PAN.
#
# WHAT WE SCAN FOR:
# - Aadhaar numbers  (12-digit Indian national ID)
# - PAN card numbers (10-char Indian tax ID: ABCDE1234F)
# - Phone numbers
# - Email addresses
# - Credit/debit card numbers
# - Person names (flagged but not quarantined alone)
#
# COMPLIANCE STATUS RULES:
# clean      → no PII found
# flagged    → PII found, needs admin review before approving
# quarantined → failed minimum text check or unreadable
# ================================================================

from dataclasses import dataclass, field
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider


@dataclass
class PIIScanResult:
    """
    Result of scanning a document for PII.
    Returned by scan_for_pii() and stored with the document.
    """
    # Whether any PII was found
    has_pii: bool

    # compliance_status to set on the document
    # clean | flagged | quarantined
    compliance_status: str

    # List of PII types found — e.g. ["PHONE_NUMBER", "EMAIL_ADDRESS"]
    # Stored in PostgreSQL for admin review
    pii_types_found: list[str] = field(default_factory=list)

    # Human-readable summary for admin dashboard
    summary: str = ""


def _build_analyzer() -> AnalyzerEngine:
    """
    Builds the Presidio analyzer engine with English NLP.
    Called once — result cached at module level.

    We use en_core_web_sm (small model) for speed.
    Accuracy is sufficient for PII detection in documents.
    en_core_web_lg would be more accurate but 3x slower + larger.
    """
    # Configure NLP engine to use spacy with our downloaded model
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "en", "model_name": "en_core_web_sm"}
        ],
    }

    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()

    # AnalyzerEngine combines NLP + pattern recognizers
    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["en"],
    )

    return analyzer


# Build analyzer once at module import time
# Re-building on every scan is very slow (~2 seconds each time)
_analyzer = _build_analyzer()

# PII entity types we care about
# Full list: https://microsoft.github.io/presidio/supported_entities/
MONITORED_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "PERSON",
    "LOCATION",
    "IN_PAN",        # Indian PAN card — ABCDE1234F format
    "IN_AADHAAR",    # Indian Aadhaar — 12 digit number
]

# These entity types alone trigger quarantine — high confidence PII
# PERSON and LOCATION are common in business docs so they only flag
HIGH_RISK_ENTITIES = {
    "IN_AADHAAR",
    "IN_PAN",
    "CREDIT_CARD",
    "IBAN_CODE",
}

# Minimum text length to consider a document processable
# Documents with less text are likely scanned images that OCR
# failed on — quarantine them for manual review
MIN_TEXT_LENGTH = 50


def scan_for_pii(text: str) -> PIIScanResult:
    """
    Scans document text for PII entities.

    Decision logic:
        len(text) < 50 chars  → quarantined (unreadable)
        high-risk PII found   → flagged (Aadhaar, PAN, card numbers)
        low-risk PII only     → flagged (phone, email, names)
        no PII found          → clean

    Args:
        text: extracted document text from parser

    Returns:
        PIIScanResult with compliance_status and details
    """

    # ── Check minimum text length ────────────────────────────────
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return PIIScanResult(
            has_pii=False,
            compliance_status="quarantined",
            pii_types_found=[],
            summary=(
                f"Document has less than {MIN_TEXT_LENGTH} characters "
                f"of extractable text. May be a blank or failed scan. "
                f"Quarantined for manual review."
            ),
        )

    # ── Run Presidio analysis ────────────────────────────────────
    # score_threshold=0.6 means only report detections with
    # at least 60% confidence — reduces false positives
    results = _analyzer.analyze(
        text=text,
        language="en",
        entities=MONITORED_ENTITIES,
        score_threshold=0.6,
    )

    if not results:
        # No PII found — document is clean
        return PIIScanResult(
            has_pii=False,
            compliance_status="clean",
            pii_types_found=[],
            summary="No PII detected. Document is clean.",
        )

    # ── PII found — categorize it ────────────────────────────────
    found_types = list({result.entity_type for result in results})

    # Check if any high-risk entities were found
    high_risk_found = HIGH_RISK_ENTITIES.intersection(set(found_types))

    summary_parts = []
    for entity_type in found_types:
        count = sum(
            1 for r in results if r.entity_type == entity_type
        )
        summary_parts.append(f"{entity_type}: {count} instance(s)")

    summary = (
        f"PII detected — {', '.join(summary_parts)}. "
        f"Document flagged for admin review before ingestion."
    )

    return PIIScanResult(
        has_pii=True,
        compliance_status="flagged",
        pii_types_found=found_types,
        summary=summary,
    )