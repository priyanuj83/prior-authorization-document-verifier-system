"""Clinical fact extraction."""

from src.clinical_extraction.fact_extractor.placeholder import PlaceholderClinicalFactExtractor
from src.clinical_extraction.fact_extractor.protocol import ClinicalFactExtractor

__all__ = ["ClinicalFactExtractor", "PlaceholderClinicalFactExtractor"]
