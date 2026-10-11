"""Vocabularies introduced by the retrieval architecture."""

from __future__ import annotations

from enum import Enum


class EvidenceScope(str, Enum):
    """Which evidence pool a note or chunk belongs to."""

    SUBMITTED_PACKET = "SUBMITTED_PACKET"
    AVAILABLE_EHR = "AVAILABLE_EHR"


class EvidenceState(str, Enum):
    """How directly an extracted fact is supported by source text.

    INFERRED is intentionally absent. Inference belongs after extraction.
    """

    EXPLICIT = "EXPLICIT"
    NOT_MENTIONED = "NOT_MENTIONED"
    AMBIGUOUS = "AMBIGUOUS"


class RetrievalChannel(str, Enum):
    """Independent search channels. Relevance in one is not proof."""

    SUPPORT = "SUPPORT"
    CONTRADICTION = "CONTRADICTION"


class AttestationVerdict(str, Enum):
    """Comparison of a provider attestation against verified evidence.

    This is a separate task from policy verification and from retrieval.
    """

    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    CONFLICTED = "CONFLICTED"


class RetrievalFailureCategory(str, Enum):
    """Component-level failure labels for retrieval evaluation."""

    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    TEMPORAL_REASONING_ERROR = "TEMPORAL_REASONING_ERROR"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"
