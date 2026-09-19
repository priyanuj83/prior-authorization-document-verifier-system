"""Display names, laterality, phrasing banks — policy-blind."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Tuple


def strip_synthea_name(first: str, last: str) -> Tuple[str, str]:
    def clean(part: str) -> str:
        return re.sub(r"\d+", "", part or "").strip() or part

    return clean(first), clean(last)


def display_name(first: str, last: str) -> str:
    a, b = strip_synthea_name(first, last)
    return f"{a} {b}".strip()


def laterality_for(patient_id: str, body: str = "joint") -> str:
    h = hashlib.md5(f"{patient_id}:{body}".encode()).hexdigest()
    return "left" if int(h[:2], 16) % 2 == 0 else "right"


def pick(seed: int, options):
    return options[seed % len(options)]


PROVIDERS = [
    ("R. Danvers, MD", "Orthopaedic Surgery", "Orthopaedic Associates of Middlesex", "SYN-0000001"),
    ("S. Patel, MD", "Orthopaedic Surgery", "Riverbend Orthopaedics", "SYN-0000002"),
    ("L. Chen, MD", "Orthopaedic Surgery", "North Shore Joint Centre", "SYN-0000003"),
    ("A. Okonkwo, MD", "Orthopaedic Surgery", "Commonwealth Bone and Joint", "SYN-0000004"),
    ("M. Alvarez, MD", "Radiology", "Metro Imaging Associates", "SYN-0000005"),
]

ED_AUTHORS = [
    "A. Whitfield, PA-C",
    "J. Moreau, MD",
    "K. Singh, NP",
    "T. Bradley, MD",
]

PT_AUTHORS = [
    "M. Okonkwo, PT, DPT",
    "H. Ellis, PT",
    "R. Nguyen, PT, DPT",
    "C. Fraser, PT",
]

RADIOLOGISTS = [
    "P. Rahman, MD",
    "E. Walsh, MD",
    "N. Ibarra, MD",
]

KNEE_MECHANISMS = [
    "twisting the {side} knee during a pickup basketball game",
    "planting and pivoting on the {side} foot while playing rec league football",
    "a stumble on uneven ground with a twist of the {side} knee",
    "coming down awkwardly from a jump during a gym class",
]

SHOULDER_MECHANISMS = [
    "a fall onto the outstretched {side} arm",
    "catching a heavy object as it slipped, with a sudden jolt to the {side} shoulder",
    "a stumble on stairs, reaching out with the {side} hand",
]

NECK_MECHANISMS = [
    "a rear-end motor vehicle collision at low speed",
    "being struck from behind while stopped at a junction",
    "a sudden deceleration in a staff-park collision",
]


def age_on(birth: date, on: date) -> int:
    years = on.year - birth.year
    if (on.month, on.day) < (birth.month, birth.day):
        years -= 1
    return years


def mrn_for(patient_id: str) -> str:
    return "SYN-" + patient_id.replace("-", "")[:8].upper()
