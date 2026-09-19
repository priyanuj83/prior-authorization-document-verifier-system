"""Render clinical notes from the ledger/facts. Templates never see the policy or labels."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader

from .context import CaseContext
from .names import KNEE_MECHANISMS, NECK_MECHANISMS, SHOULDER_MECHANISMS, pick
from .paths import TEMPLATES_DIR
from .yamlio import iso


def _env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR / "notes")),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _sex_word(sex: str) -> str:
    return "male" if sex == "M" else "female" if sex == "F" else "adult"


def _side_joint(ctx: CaseContext) -> str:
    if ctx.policy_id == "PA-SHOULDER-RCR-001":
        return f"{ctx.episode.laterality} shoulder"
    if ctx.policy_id == "PA-SPINE-MRI-001":
        return "neck"
    return f"{ctx.episode.laterality} knee"


def _mechanism(ctx: CaseContext) -> str:
    side = ctx.episode.laterality
    if ctx.policy_id == "PA-SHOULDER-RCR-001":
        return pick(ctx.seed, SHOULDER_MECHANISMS).format(side=side)
    if ctx.policy_id == "PA-SPINE-MRI-001":
        return pick(ctx.seed, NECK_MECHANISMS)
    return pick(ctx.seed, KNEE_MECHANISMS).format(side=side)


def _pmh(ctx: CaseContext) -> str:
    bits = []
    if ctx.facts.oa_present and ctx.facts.oa_onset:
        bits.append(f"knee osteoarthritis since {iso(ctx.facts.oa_onset)}")
    return "; ".join(bits) if bits else "Nil of note"


def render_notes(ctx: CaseContext) -> Dict[str, str]:
    """Return mapping slug -> relative path, and write files later from contents dict."""
    env = _env()
    visit_t = env.get_template("visit.md.j2")
    pt_t = env.get_template("pt_discharge.md.j2")
    img_t = env.get_template("imaging.md.j2")
    dist_t = env.get_template("distractor.md.j2")

    ep = ctx.episode
    f = ctx.facts
    r = ctx.render
    side = ep.laterality
    joint = _side_joint(ctx)
    contents: Dict[str, str] = {}
    files: Dict[str, str] = {}
    n = 1

    def rec(date, slug, text):
        nonlocal n
        rel = f"input/notes/{iso(date)}-{slug}.md"
        files[slug.split('-')[0] if False else slug] = rel
        contents[rel] = text
        n += 1
        return rel

    # --- ED ---
    if r.enclose_ed:
        if ctx.policy_id == "PA-SPINE-MRI-001":
            exam = (
                "Alert, cervical collar in place. Midline neck tenderness. No step-off. "
                "Upper limb power appears intact at the bedside though limited by pain. "
                "No obvious distal neurological deficit on a brief exam."
            )
            if f.cord_suspected:
                exam += " The team is concerned about possible cord involvement given the mechanism and midline pain."
            imaging = None
            plan = (
                f"Cervical spine films obtained. Orthopaedic/spine discussion. "
                f"Advanced imaging of the cervical spine requested."
            )
            hpi = (
                f"Neck pain began immediately. No loss of consciousness. "
                f"Unable to turn the head comfortably."
            )
            chief = "Neck pain after collision"
        elif ctx.policy_id == "PA-SHOULDER-RCR-001":
            exam = (
                f"{side.capitalize()} shoulder: limited active abduction, painful arc. "
                f"External rotation weaker than the other side. Neurovascularly intact distally."
            )
            if not f.exam_abnormal:
                exam = f"{side.capitalize()} shoulder mildly tender. Strength and range recorded as full."
            imaging = (
                f"> Radiologist read: {side.capitalize()} shoulder, three views. No acute fracture. "
                f"Acromial morphology unremarkable. Soft tissues non-diagnostic for cuff integrity."
            )
            plan = "Sling for comfort. Analgesia. Referral to physiotherapy and to orthopaedics."
            hpi = "Pain and weakness lifting the arm overhead. Sleeping on that side is difficult."
            chief = f"{side.capitalize()} shoulder injury"
        elif ctx.policy_id == "PA-TKA-001":
            exam = (
                f"{side.capitalize()} knee: small effusion, crepitus, limited flexion. "
                f"Medial joint-line tenderness. Gait antalgic."
            )
            kl = f.kl_grade
            oa_words = {
                0: "preserved joint spaces, no osteophytes",
                1: "minimal marginal change only, joint spaces preserved",
                2: "definite osteophytes with preserved joint space",
                3: "moderate joint-space narrowing with osteophytes",
                4: "bone-on-bone contact, complete joint-space loss, osteophytosis",
            }[min(max(kl, 0), 4)]
            imaging = (
                f"> Radiologist read: {side.capitalize()} knee, three views. No acute fracture. "
                f"{oa_words.capitalize()}. Kellgren-Lawrence grade {kl}."
            )
            plan = "Analgesia. Orthopaedic referral regarding possible joint replacement."
            hpi = (
                f"Longstanding {side} knee pain, worse over recent months, interfering with stairs and walking distance."
            )
            chief = f"{side.capitalize()} knee pain"
        else:
            exam = (
                f"{side.capitalize()} knee: {'moderate effusion. ' if f.effusion else 'no obvious effusion. '}"
                f"Tenderness along the medial joint line. Range limited by pain. "
                f"Ligament testing limited by guarding; no gross laxity appreciated. Neurovascularly intact distally."
            )
            if not f.exam_abnormal:
                exam = f"{side.capitalize()} knee mildly tender. No effusion recorded. Ligaments stable. Gait independent."
            kl = f.kl_grade
            oa_words = {
                0: "joint spaces well preserved, no osteophytes",
                1: "minimal marginal changes only, joint spaces preserved",
                2: "small osteophytes, joint space largely preserved",
                3: "moderate joint-space narrowing",
                4: "bone-on-bone contact with osteophytosis",
            }[min(max(kl, 0), 4)]
            imaging = (
                f"> Radiologist read: {side.capitalize()} knee, three views. No acute fracture or dislocation. "
                f"{oa_words.capitalize()}. Kellgren-Lawrence grade {kl}. "
                f"The menisci are not assessable on these films."
            )
            plan = (
                f"Analgesia. Crutches as needed. Referral placed today to the outpatient physiotherapy service "
                f"for the {side} knee. Orthopaedic follow-up arranged."
            )
            hpi = (
                f"Immediate pain on the inner side of the {side} knee. Unable to continue the activity. "
                f"{'Weight bearing is painful.' if f.effusion else 'Able to take some weight.'}"
            )
            chief = f"{side.capitalize()} knee injury"

        text = visit_t.render(
            note_id=f"{ctx.case_id}-ed",
            case_id=ctx.case_id,
            date=iso(ep.index_date),
            setting="Emergency Department",
            heading="EMERGENCY DEPARTMENT NOTE",
            author=ctx.ed_author,
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            chief_complaint=chief,
            age=ctx.age,
            sex_word=_sex_word(ctx.sex),
            mechanism=_mechanism(ctx),
            hpi_detail=hpi,
            pmh=_pmh(ctx),
            meds="None" if not ctx.facts.oa_present else "Occasional ibuprofen",
            exam=exam,
            imaging_block=imaging,
            plan=plan,
        )
        rec(ep.index_date, "ed-visit", text)
        files["ed"] = f"input/notes/{iso(ep.index_date)}-ed-visit.md"

    # --- ortho ---
    if r.enclose_ortho:
        ortho_date = ep.index_date + timedelta(days=12)
        if ctx.policy_id == "PA-TKA-001":
            exam = (
                f"{side.capitalize()} knee alignment in varus. Flexion to 95 degrees. "
                f"{'Needs a rail on stairs. Walking distance limited to a few blocks. ' if f.function_impaired else 'Walking independently without reported limitation. '}"
                f"Crepitus throughout motion."
            )
            plan_o = "Discussion of arthroplasty. Films reviewed."
            hpi_o = f"Pain of the {side} knee limits shopping, stairs, and sleep."
        elif ctx.policy_id == "PA-SHOULDER-RCR-001":
            exam = (
                f"{side.capitalize()} shoulder: drop-arm concern, weak external rotation, positive empty-can. "
                if f.exam_abnormal else
                f"{side.capitalize()} shoulder range and strength recorded as full today."
            )
            plan_o = "Advanced imaging of the cuff. Continue therapy directed at the shoulder."
            hpi_o = f"Overhead work remains painful. Night pain persists."
        else:
            lock = (
                f"Describes catching and then the {side} knee locking outright, needing to manually straighten the leg. "
                if f.locking else
                (
                    f"Describes catching of the {side} knee. "
                    f"One episode where it felt stuck for a moment before releasing on its own — not a fixed lock. "
                    if f.mechanical else
                    f"Pain without catching or locking."
                )
            )
            exam = (
                f"Joint-line tenderness medially. McMurray uncomfortable. "
                f"{'Small residual effusion. ' if f.effusion else ''}"
                f"No fixed locked position today."
            )
            plan_o = (
                f"Continue the physiotherapy already arranged. If symptoms persist, MRI of the {side} knee."
            )
            hpi_o = lock + f" Stairs and pivoting remain unreliable."
        text = visit_t.render(
            note_id=f"{ctx.case_id}-ortho",
            case_id=ctx.case_id,
            date=iso(ortho_date),
            setting="Orthopaedic clinic",
            heading="ORTHOPAEDIC CONSULTATION",
            author=ctx.provider[0],
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            chief_complaint=f"{joint} symptoms",
            age=ctx.age,
            sex_word=_sex_word(ctx.sex),
            mechanism=_mechanism(ctx),
            hpi_detail=hpi_o,
            pmh=_pmh(ctx),
            meds="As previously",
            exam=exam,
            imaging_block=None,
            plan=plan_o,
        )
        rec(ortho_date, "ortho-consult", text)
        files["ortho"] = f"input/notes/{iso(ortho_date)}-ortho-consult.md"

    # --- PT ---
    if r.enclose_pt and f.pt_start and f.pt_stop:
        region_label = {
            "knee": f"{side.capitalize()} knee",
            "shoulder": f"{side.capitalize()} shoulder",
            "neck": "Cervical spine",
            "ankle": "Ankle",
            "wrist": "Wrist",
        }.get(f.pt_body_region or "knee", f.pt_body_region)
        text = pt_t.render(
            note_id=f"{ctx.case_id}-pt",
            case_id=ctx.case_id,
            date=iso(f.pt_stop),
            author=ctx.pt_author,
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            referral_source="Referring clinician, referral dated " + iso(f.pt_start),
            body_region_label=region_label,
            modality=f.pt_modality,
            start=iso(f.pt_start),
            sessions=f.pt_sessions,
            response=f.pt_response,
        )
        rec(f.pt_stop, "pt-discharge", text)
        files["pt"] = f"input/notes/{iso(f.pt_stop)}-pt-discharge.md"

    # --- MRI ---
    if r.enclose_mri:
        mri_date = (f.pt_stop + timedelta(days=8)) if f.pt_stop else (ep.request_date - timedelta(days=7))
        if ctx.policy_id == "PA-SHOULDER-RCR-001":
            findings = (
                f"{side.capitalize()} shoulder MRI. Full-thickness tear of the supraspinatus tendon with mild retraction. "
                f"No advanced fatty atrophy of the muscle belly. Biceps tendon intact. "
                if f.cuff_tear else
                f"{side.capitalize()} shoulder MRI. Intact rotator cuff. Mild tendinosis without tear."
            )
            impression = "Rotator cuff tear as described." if f.cuff_tear else "No cuff tear."
            title = "MRI SHOULDER REPORT"
            indication = f"{side.capitalize()} shoulder pain and weakness"
            technique = "MRI without contrast"
        else:
            findings = (
                f"{side.capitalize()} knee MRI. Oblique tear of the posterior horn of the medial meniscus. "
                f"There is no displaced fragment and no bucket-handle configuration. "
                f"The meniscal root attachments are intact both anteriorly and posteriorly. "
                f"Grade {min(f.kl_grade, 2) if f.kl_grade <= 2 else f.kl_grade} chondral signal change. "
                f"{'No osteophytosis.' if f.kl_grade <= 1 else 'Osteophytes present, matching the plain films.'}"
            )
            impression = "Medial meniscus tear. Roots intact. No bucket-handle displacement."
            title = "MRI KNEE REPORT"
            indication = f"{side.capitalize()} knee mechanical symptoms"
            technique = "MRI without contrast"
        text = img_t.render(
            note_id=f"{ctx.case_id}-mri",
            case_id=ctx.case_id,
            date=iso(mri_date),
            author=ctx.radiologist,
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            title=title,
            indication=indication,
            technique=technique,
            findings=findings,
            impression=impression,
        )
        rec(mri_date, "mri-report", text)
        files["mri"] = f"input/notes/{iso(mri_date)}-mri-report.md"

    # --- cervical xray ---
    if r.enclose_xray_note:
        xdate = ep.index_date
        findings = (
            "AP, lateral, and odontoid views of the cervical spine. Alignment maintained. "
            "No definite fracture line. Prevertebral soft tissues not clearly assessed because of collar and body habitus. "
            "Films are not conclusive for subtle fracture or dislocation."
            if f.plain_film_inconclusive else
            "AP and lateral cervical spine. Alignment normal. No fracture. Films are technically adequate."
        )
        text = img_t.render(
            note_id=f"{ctx.case_id}-xray",
            case_id=ctx.case_id,
            date=iso(xdate),
            author=ctx.radiologist,
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            title="CERVICAL SPINE RADIOGRAPH",
            indication="Trauma, neck pain",
            technique="Plain radiographs",
            findings=findings,
            impression="Not conclusive for fracture; clinical correlation and further imaging as indicated."
            if f.plain_film_inconclusive else "No radiographic fracture.",
        )
        rec(xdate, "cervical-xray", text)
        files["xray"] = f"input/notes/{iso(xdate)}-cervical-xray.md"

    # --- followup ---
    if r.enclose_followup:
        fdate = ep.request_date
        if ctx.policy_id == "PA-TKA-001":
            extra = (
                "No fever, no wound, no hot joint. No clinical evidence of active infection today. "
                if f.infection_absent else ""
            )
            plan_f = f"Request authorisation for {side} total knee arthroplasty."
            hpi_f = "Pain and limitation unchanged. Patient wishes to proceed with replacement."
        elif ctx.policy_id == "PA-SPINE-MRI-001":
            extra = ""
            plan_f = "Request MRI of the cervical spine given the mechanism and inconclusive films."
            hpi_f = "Neck pain persists. No new limb weakness reported at this visit."
        elif ctx.policy_id == "PA-KNEE-MRI-001":
            extra = ""
            plan_f = f"Request MRI of the {side} knee."
            hpi_f = "Symptoms persist. Plain films do not explain the mechanical complaint."
        elif ctx.policy_id == "PA-SHOULDER-RCR-001":
            extra = ""
            plan_f = f"Request authorisation for {side} rotator cuff repair."
            hpi_f = "Overhead function remains limited."
        else:
            extra = ""
            plan_f = f"Request authorisation for arthroscopic treatment of the {side} meniscus."
            hpi_f = "Mechanical symptoms continue. Therapy has finished."
        exam_f = f"Examination of the {joint} is unchanged from the last clinic visit. {extra}".strip()
        text = visit_t.render(
            note_id=f"{ctx.case_id}-fu",
            case_id=ctx.case_id,
            date=iso(fdate),
            setting="Orthopaedic clinic",
            heading="ORTHOPAEDIC FOLLOW-UP",
            author=ctx.provider[0],
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            chief_complaint=f"{joint} — follow-up",
            age=ctx.age,
            sex_word=_sex_word(ctx.sex),
            mechanism="as previously documented",
            hpi_detail=hpi_f,
            pmh=_pmh(ctx),
            meds="As previously",
            exam=exam_f,
            imaging_block=None,
            plan=plan_f,
        )
        rec(fdate, "ortho-followup", text)
        files["followup"] = f"input/notes/{iso(fdate)}-ortho-followup.md"

    if r.enclose_distractor:
        ddate = ep.index_date - timedelta(days=20)
        if f.unrelated_pt:
            cp = f.unrelated_pt[0]
            ddate = cp.get("start_date") or ddate
            reason = cp.get("REASONDESCRIPTION") or "unrelated musculoskeletal complaint"
            body = (
                f"Seen for {reason}. A therapy programme was arranged for that problem. "
                f"No mention of the {joint} today."
            )
            chief = reason
        else:
            body = (
                "Viral upper respiratory illness. Congestion, facial pressure. "
                f"No complaint related to the {joint}."
            )
            chief = "Sinus congestion"
        text = dist_t.render(
            note_id=f"{ctx.case_id}-dist",
            case_id=ctx.case_id,
            date=iso(ddate),
            author=pick_author(ctx),
            last=ctx.last,
            first=ctx.first,
            dob=iso(ctx.birthdate),
            mrn=ctx.mrn,
            chief_complaint=chief,
            body=body,
        )
        rec(ddate, "distractor-clinic", text)
        files["distractor"] = f"input/notes/{iso(ddate)}-distractor-clinic.md"

    return {"files": files, "contents": contents}


def pick_author(ctx: CaseContext) -> str:
    return ctx.ed_author
