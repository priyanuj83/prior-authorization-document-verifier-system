"""Named documentation variants. Flags compose; later flags win."""

from dataclasses import dataclass, fields
from typing import Iterable, Optional


@dataclass
class VariantSpec:
    name: str
    enclose_pt: bool = True
    enclose_advanced_imaging: bool = True
    enclose_xray: bool = True
    enclose_distractor: bool = False
    pt_modality: str = "in_person"  # in_person | home_based
    pt_duration_source: str = "synthea"  # synthea | authored_long | authored_short
    authored_pt_days: Optional[int] = None
    oa_grade: str = "auto"  # auto | mild | severe
    overclaim_pt: bool = False
    pre_effective_date: bool = False
    mechanical_symptoms: bool = True
    locking: bool = True
    document_infection_absent: bool = True
    function_impaired: bool = True
    document_effusion: bool = True
    document_exam: bool = True
    trauma_plain_film_inconclusive: bool = True
    suspect_cord_injury: bool = False
    cuff_tear_present: bool = True


DEFAULTS = VariantSpec(name="full_packet")

_VARIANTS = {
    "full_packet": VariantSpec(name="full_packet"),
    "omit_pt_notes": VariantSpec(name="omit_pt_notes", enclose_pt=False),
    "omit_imaging": VariantSpec(
        name="omit_imaging",
        enclose_advanced_imaging=False,
        enclose_xray=False,
        trauma_plain_film_inconclusive=False,
    ),
    "omit_exam": VariantSpec(
        name="omit_exam",
        document_exam=False,
        document_effusion=False,
        locking=False,
        mechanical_symptoms=False,
    ),
    "short_pt_enclosed": VariantSpec(
        name="short_pt_enclosed",
        enclose_pt=True,
        pt_duration_source="authored_short",
        authored_pt_days=30,
    ),
    "home_pt_enclosed": VariantSpec(
        name="home_pt_enclosed",
        enclose_pt=True,
        pt_modality="home_based",
    ),
    "overclaim_attestation": VariantSpec(
        name="overclaim_attestation",
        enclose_pt=False,
        overclaim_pt=True,
    ),
    "severe_oa": VariantSpec(name="severe_oa", oa_grade="severe"),
    "mild_oa": VariantSpec(name="mild_oa", oa_grade="mild"),
    "pre_effective_date": VariantSpec(name="pre_effective_date", pre_effective_date=True),
    "distractor_unrelated": VariantSpec(name="distractor_unrelated", enclose_distractor=True),
    "authored_long_pt": VariantSpec(
        name="authored_long_pt",
        enclose_pt=True,
        pt_duration_source="authored_long",
        authored_pt_days=100,
    ),
}


def _merge(base: VariantSpec, overlay: VariantSpec) -> VariantSpec:
    kwargs = {f.name: getattr(base, f.name) for f in fields(VariantSpec)}
    default = VariantSpec(name="")
    for f in fields(VariantSpec):
        if f.name == "name":
            continue
        ov = getattr(overlay, f.name)
        if ov != getattr(default, f.name):
            kwargs[f.name] = ov
    kwargs["name"] = overlay.name or base.name
    # Keep stacked name readable.
    if base.name and overlay.name and base.name != overlay.name:
        kwargs["name"] = f"{base.name}+{overlay.name}"
    return VariantSpec(**kwargs)


def resolve_spec(variant: str, flags: Optional[Iterable[str]] = None) -> VariantSpec:
    if variant not in _VARIANTS:
        raise KeyError(f"Unknown variant: {variant}")
    spec = _VARIANTS[variant]
    spec = VariantSpec(**{f.name: getattr(spec, f.name) for f in fields(VariantSpec)})
    for flag in flags or []:
        if flag not in _VARIANTS:
            raise KeyError(f"Unknown variant flag: {flag}")
        spec = _merge(spec, _VARIANTS[flag])
    return spec


def apply_policy_defaults(spec: VariantSpec, policy_id: str) -> VariantSpec:
    """Policy-specific interpretation of full_packet etc."""
    kwargs = {f.name: getattr(spec, f.name) for f in fields(VariantSpec)}
    if policy_id == "PA-TKA-001":
        kwargs["oa_grade"] = "severe" if spec.oa_grade == "auto" else spec.oa_grade
        if spec.name.startswith("full_packet") and spec.pt_duration_source == "synthea":
            kwargs["pt_duration_source"] = "authored_long"
            kwargs["authored_pt_days"] = 100
            kwargs["enclose_pt"] = True
        if spec.pt_duration_source == "authored_short":
            kwargs["authored_pt_days"] = spec.authored_pt_days or 30
    if policy_id == "PA-KNEE-MRI-001":
        # MRI is the requested service; never enclose an MRI report of the same knee.
        kwargs["enclose_advanced_imaging"] = False
    if policy_id == "PA-SPINE-MRI-001":
        kwargs["enclose_advanced_imaging"] = False
        if spec.name.startswith("full_packet"):
            kwargs["enclose_xray"] = True
            kwargs["trauma_plain_film_inconclusive"] = True
    if policy_id == "PA-SHOULDER-RCR-001" and spec.enclose_distractor:
        # Distractor is extra; keep real shoulder docs unless omit_* was also set.
        pass
    return VariantSpec(**kwargs)
