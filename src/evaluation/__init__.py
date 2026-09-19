"""Evaluation-only access to hidden gold artifacts.

Do not import this package from verifier runtime components.
"""

from src.evaluation.loader import load_gold_packet, load_gold_packet_from_dir
from src.evaluation.models import GoldCriterionLabel, GoldEvaluationPacket, GoldLabels

__all__ = [
    "GoldCriterionLabel",
    "GoldEvaluationPacket",
    "GoldLabels",
    "load_gold_packet",
    "load_gold_packet_from_dir",
]
