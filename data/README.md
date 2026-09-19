# Prior Authorisation Verification Corpus

Curated evaluation corpus for the Prior Authorisation Document Verifier. Everything
here is either hand-authored or derived from the Synthea extract in `../synthea_data/`.

**Version 0.3.0** — 5 policies, 3 plans, 3 hand-authored cases plus 194 generated cases.

> **0.3.0 adds a template generator** at `src/data_generation/`. Generated packets
> live beside the three frozen cases under `cases/`. Hand-authored `KNEE-ARTHRO-0001`
> through `0003` are never overwritten. Train/eval splits are patient-grouped in
> `generation/splits.yaml`.

> **0.2.0 is a breaking change from 0.1.0.** Cases are now split into `input/` and
> `gold/`; `plan.yaml` is renamed `generation_plan.yaml`; note paths are prefixed
> `input/`; the outcome vocabulary is provider-side (`READY_FOR_SUBMISSION` /
> `NOT_READY` / `REVIEW_NEEDED`) with `APPROVE` / `PEND` / `DENY` demoted to a derived
> `payer_view`; the gate vocabulary is now `AUTH_REQUIRED` /
> `COVERAGE_REVIEW_REQUIRED` / `NO_AUTH_REQUIRED`; and each policy's `decision` block
> is now a framework-neutral `criteria_logic` block. Per-criterion
> `SUPPORTED` / `MISSING` / `CONTRADICTED` labels are unchanged.

---

## 1. Why this folder is separate from `../synthea_data/`

```
../synthea_data/     raw Synthea CSVs. Immutable input. Never edited.
./                   curated corpus. Policies, plans, cases, labels.
```

`../synthea_data/` is the source of clinical facts. This folder is everything that
Synthea cannot give you: the payer's criteria, the submitted request, and the answer
key. Keeping them apart means you can regenerate Synthea, or swap in a different
extract, without touching the corpus.

---

## 2. Layout

```
data/
├── README.md                      you are here
│
├── policies/                      clinical criteria, decomposed into atomic checks
│   ├── PA-KNEE-ARTHRO-001.yaml    knee arthroscopy       [tier 1, conjunctive]
│   ├── PA-KNEE-MRI-001.yaml       knee MRI               [tier 1, disjunctive]
│   ├── PA-TKA-001.yaml            total knee replacement [tier 1, conjunctive]
│   ├── PA-SHOULDER-RCR-001.yaml   rotator cuff repair    [tier 1, conjunctive]
│   └── PA-SPINE-MRI-001.yaml      spine MRI/CT           [tier 2, disjunctive]
│
├── grounding/                     engineering notes: which criteria the data supports
│   ├── PA-KNEE-ARTHRO-001.yaml    per-criterion source mapping + seed patients
│   └── PA-SPINE-MRI-001.yaml      why this policy is blocked, and how to unblock it
│
├── pa_requirements/               does this PLAN require authorisation at all?
│   ├── README.md                  the medical-policy vs auth-requirement distinction
│   ├── AETNA-COMMERCIAL-01.yaml
│   ├── HUMANA-COMMERCIAL-01.yaml
│   └── MEDICARE-FFS-01.yaml       prospective auth off, coverage review on
│
├── generation/
│   └── splits.yaml                patient-grouped train/eval (never split by case)
│
└── cases/                         worked cases with gold labels
    ├── KNEE-ARTHRO-0001/          hand-authored; READY_FOR_SUBMISSION
    ├── KNEE-ARTHRO-0002/          hand-authored; NOT_READY
    ├── KNEE-ARTHRO-0003/          hand-authored; REVIEW_NEEDED
    ├── KNEE-ARTHRO-0004/ …        generated arthroscopy variants
    ├── KNEE-MRI-*/                generated knee MRI (disjunctive)
    ├── TKA-*/                     generated arthroplasty
    ├── SHOULDER-RCR-*/            generated rotator cuff repair
    └── SPINE-MRI-*/               generated cervical trauma MRI
        │
        ├── input/                 ===== MODEL-VISIBLE. Nothing else is. =====
        │   ├── pa_form.yaml       the submitted request, with attestations
        │   └── notes/*.md         clinical notes; a lossy rendering of the ledger
        │
        └── gold/                  ===== HIDDEN from the verifier, always =====
            ├── generation_plan.yaml  generation directives; labels are INPUTS
            ├── ledger.yaml           canonical truth + packet scope
            └── labels.yaml           gold per-criterion verdicts with citations
```

### The `input` / `gold` split

The split is physical rather than conventional so that leakage is structurally
impossible rather than merely discouraged. Evaluation code can guarantee:

```python
model_input = glob(f"cases/{case_id}/input/**")   # plus the resolved policy
```

and there is no path by which `labels.yaml`, `ledger.yaml` or
`generation_plan.yaml` can reach a RAG index or a prompt. Leaking the answer key into
retrieval is one of the easiest ways to make an evaluation look excellent while
measuring nothing, and it is very hard to detect after the fact because the results
look plausible, just better than they should be.

**A case is an evidence packet for one prior-authorisation episode, not a patient's
complete chart.** `KNEE-ARTHRO-0001` is Ethan Goyette's knee episode from January to
April 2014; it is not his medical history. Every ledger carries a `scope` block
recording the episode window, the per-criterion lookback, and what was deliberately
excluded, so that a missing fact is always attributable to a decision rather than an
oversight.

**Path convention:** every path in the corpus is relative to the case root, so notes
are written as `input/notes/....md` everywhere, including from inside `input/`.

---

## 3. The runtime contract

### 3.1 What the verifier receives

Three things, and the third it must fetch for itself:

```
 1. THE REQUEST          input/pa_form.yaml
 2. THE RECORDS          input/notes/*.md
 3. THE POLICY           resolved at runtime, see below
```

The form and notes alone are **not** sufficient input. Given "completed 60 days of
therapy, MRI shows a meniscal tear, true locking present", a verifier has no basis
for deciding which of those facts matter, or against what threshold, without the
criteria. Resolution is therefore step one of the pipeline, not corpus metadata:

```
input/pa_form.yaml
    member.plan_id + requested_service.service_key + submitted_date
                             |
                             v
                POLICY RESOLVER
                             |
                             v
              pa_requirements/<plan_id>.yaml
                             |
        requires_prior_auth? --no--> requires_coverage_review?
               |                          |             |
              yes                        yes            no
               |                          |             |
               v                          v             v
        AUTH_REQUIRED      COVERAGE_REVIEW_REQUIRED   NO_AUTH_REQUIRED
               |                          |             |
               +------------+-------------+          STOP. No criteria are
                            |                        evaluated and there is
                            v                        nothing to prepare.
              governing_policy -> policies/<POLICY>.yaml
                            |
                            v
                  structured criteria
                            |
              +-------------+-------------+
              |                           |
        input/notes/*.md            the criteria
              |                           |
              +----------> VERIFIER <-----+
                               |
                               v
                    per-criterion labels
                               |
                               v
                      documentation status
```

Two properties of resolution are load-bearing and both are exercised by the corpus.
It is **date-dependent**: the same request is `NO_AUTH_REQUIRED` before
`HUMANA-COMMERCIAL-01`'s 2013-06-01 effective date and `AUTH_REQUIRED` after it. And
it is **two-field**: `MEDICARE-FFS-01` sets `requires_prior_auth: false` with
`requires_coverage_review: true`, so a resolver reading only the first field skips
verification entirely. That is the trap in `KNEE-ARTHRO-0003`, and it fires before any
clinical reasoning begins.

### 3.2 The corpus artifacts, and why there are four

```
                 gold/ledger.yaml
              (canonical truth, all facts)
                          |
            +-------------+-------------+
            |                           |
      lossy rendering              label derivation
            |                           |
            v                           v
   input/pa_form.yaml            gold/labels.yaml
   input/notes/*.md                      |
            |                            |
            v                            |
   ==== WHAT THE VERIFIER SEES ====      |
   (plus the resolved policy)            |
            |                            |
            +----------> compared <------+
```

The **ledger** exists because once the note generator authors facts Synthea cannot
express — symptom phenomenology, imaging grades, therapy modality — the Synthea
timeline is no longer ground truth. The ledger is the union of Synthea events and
authored events, each with a stable id and a `provenance` field of `synthea` or
`authored`.

The **notes** are a deliberately lossy, obfuscated rendering of the ledger. The gap
between ledger and notes *is* the task difficulty, and because it is explicit you can
measure and tune it rather than guess at it.

**Labels are computed from the ledger, never by reading the notes.** This is the rule
that keeps the corpus free of label noise. See §5.

---

## 4. Labels and outcomes

### 4.1 Per-criterion labels

Applied to each criterion independently. These are the ground truth of the corpus and
they are **framework-neutral**: they describe the evidence, and are identical whether
you build a provider-side or a payer-side product.

| Label | Meaning |
|---|---|
| `SUPPORTED` | The submitted record establishes that the criterion is met. |
| `MISSING` | The record does not contain sufficient evidence to establish the criterion. Silence or underspecification. |
| `CONTRADICTED` | The record contains positive evidence that the criterion is **not** met. |

### 4.2 Gate results

Produced by the resolver in §3.1, before any criterion is read.

| Result | Meaning |
|---|---|
| `AUTH_REQUIRED` | Authorisation required. Verify the criteria. |
| `COVERAGE_REVIEW_REQUIRED` | Not required prospectively, but reviewable afterwards against the same criteria. Verify them anyway. |
| `NO_AUTH_REQUIRED` | This plan does not require authorisation for this service on this date. No criterion is evaluated. |

### 4.3 Documentation status — the provider-side outcome

**This system is provider-side.** It tells a provider whether their documentation is
ready to submit. It is not an insurer and does not decide coverage.

| Status | Meaning | Remediable? |
|---|---|---|
| `READY_FOR_SUBMISSION` | Every criterion is supported by the enclosed records. Submit. | n/a |
| `NOT_READY` | One or more criteria are `MISSING` and none is `CONTRADICTED`. The evidence needed to decide is absent from the packet. | **Yes** — fetch the documents |
| `REVIEW_NEEDED` | One or more criteria are `CONTRADICTED`. The record affirmatively shows the patient falls outside the policy. | **No** — a human must decide whether to redirect, appeal or abandon |

`remediable` is the field that carries the product's value, and the distinction
between `NOT_READY` and `REVIEW_NEEDED` is the whole reason for a provider-side
framing. Both are "not submittable today", but one is a work queue item and the other
means stop and rethink the request. Telling a provider to go and find records that
cannot exist wastes real staff time on an unwinnable submission, which is why
`gold/labels.yaml` for `KNEE-ARTHRO-0003` carries a deliberately **empty**
`remediation` list and an `escalation` list instead.

`REVIEW_NEEDED` rather than a flat refusal because a human should look before the
request is abandoned: a grade may be mis-transcribed, an appeal pathway may exist, and
in `KNEE-ARTHRO-0003` a different policy is in fact the right route. What the system
must not do is let the packet be submitted as routine.

### 4.4 The payer-side view is derived, and is not scored

Each `labels.yaml` also carries a `payer_view` with the familiar
`APPROVE` / `PEND` / `DENY`. It is retained only to make the mapping visible, and
`KNEE-ARTHRO-0003` shows why the two are genuinely different functions rather than a
rename. Payer-side, `MISSING` and `CONTRADICTED` both collapse to "not approved".
Provider-side they must stay apart, because they imply opposite actions.

```
criterion labels  ---> provider_view   (the product; scored)
                  \
                   -> payer_view       (derived; not scored)
```

Both views are projections declared in each policy's `criteria_logic.projections`
block, so the mapping lives with the policy rather than being hard-coded.

### 4.5 The distinction that matters most

**Labels describe the documentation, not the patient.**

`KNEE-ARTHRO-0002` is built to make this concrete. The patient's therapy course really
was only 30 days, so clinically the criterion fails. But no duration reaches the
submitted record, so the correct label is `MISSING`, not `CONTRADICTED`. A verifier
answering `CONTRADICTED` has guessed correctly about the world while reasoning
incorrectly about the document, and should be scored wrong.

This is why `ledger.yaml` carries a two-column truth table:

```yaml
C4_conservative_therapy:
  clinical_truth: NOT_MET          # what is actually so
  documentation_state: SILENT      # what the record establishes
  label_follows: MISSING           # labels.yaml follows documentation_state
```

A prior authorisation reviewer does not know ground truth. They know what arrived in
the envelope. The system should model that.

---

## 5. Two rules for the generator

Both exist to prevent the corpus from silently invalidating itself.

**Rule 1 — the note generator must never see the policy.** If it does, it writes notes
in the policy's own vocabulary ("patient failed a course of conservative therapy") and
the verification task collapses into paraphrase matching. Every
`gold/generation_plan.yaml` carries a `forbidden_vocabulary` list for this reason. No
note in this corpus contains the phrases "conservative therapy", "six weeks", or
"in-person".

**Rule 2 — labels are inputs to generation, not outputs of it.** Deciding the label
first and rendering prose to match gives noise-free ground truth and per-criterion
difficulty control. Generating notes and then labelling them with a model caps your
accuracy at the labeller's, and correlates your label errors with your verifier's
errors, which inflates measured performance on exactly the hard cases you built the
corpus to study.

---

## 6. Case summary

All three cases run against `PA-KNEE-ARTHRO-001` and are grounded in real Synthea
patients. Codes used: PT careplan `91251008`, meniscus tear `239720000`, knee OA
`239873007`, knee X-ray `74016001`, ER admission `50849002`.

| Case | Patient | Age | Plan | PT days | Status | Primary skill tested |
|---|---|---|---|---|---|---|
| `0001` | `34382e29` Ethan Goyette | 33 | Humana | 60 | `READY_FOR_SUBMISSION` | false-positive control; two-hop date arithmetic |
| `0002` | `c2128123` Gianna Kling | 24 | Aetna | 30 | `NOT_READY` | documentation sufficiency; resisting attestations |
| `0003` | `1ab6d5c8` Sharilyn Romaguera | 67 | Medicare | 60 | `REVIEW_NEEDED` | conjunctive logic; policy resolution; remediability |

### Generated inventory (0.3.0)

Template-generated packets are produced by `src/data_generation/` from
`src/data_generation/catalog.yaml`. They use the same `input/` / `gold/` layout.
`labelled_by: template-v0.3` distinguishes them from the frozen slice.

| Prefix | Policy | Generated cases | What they test |
|---|---|---|---|
| `KNEE-ARTHRO-0004` … | `PA-KNEE-ARTHRO-001` | 18 | Meniscus variants: missing PT, short PT, home PT, omitted MRI |
| `KNEE-MRI-*` | `PA-KNEE-MRI-001` | 60 | Disjunctive trauma vs conservative branches; OA exclusion; date gate |
| `TKA-*` | `PA-TKA-001` | 50 | Inverse OA rule; 90-day therapy (authored when READY) |
| `SHOULDER-RCR-*` | `PA-SHOULDER-RCR-001` | 36 | Body-region distractors; missing MRI |
| `SPINE-MRI-*` | `PA-SPINE-MRI-001` | 30 | Trauma branches `B8`/`B9` only — no invented lumbar disease |

197 case folders total (3 hand-authored + 194 generated). Splits in
`generation/splits.yaml` are **by patient**: every variant of one Synthea ID is
train or eval together. Frozen seed patients are always in eval.

Regenerate (never touches `KNEE-ARTHRO-0001` … `0003`):

```bash
python -m src.data_generation.generate --rebuild-catalog
python -m src.data_generation.validate
```

### What each case is for

**`0001` is the false-positive control.** Every criterion passes. A corpus made only
of defective cases cannot distinguish a good verifier from one that flags everything,
and false-positive rate is what will determine whether clinicians trust the system.
Its `C4` is deliberately hard: no note states a duration, so the start date must be
found in the ED note, the end date in the therapy discharge summary, and 60 days
computed.

**`0002` tests documentation reasoning.** Two criteria are `MISSING` for structurally
different reasons — no MRI was ever done, and no therapy paperwork was enclosed. The
form attests that the patient "completed a course of physical therapy", which nothing
in the envelope corroborates. Three plausible shortcuts all lead to a packet being
wrongly reported as clean: trusting the attestation, treating the X-ray as satisfying
the imaging criterion, or firing the locked-knee waiver on a transient stuck episode
that the treating surgeon explicitly declined to call locking.

**`0003` tests conjunctive logic and remediability.** Three of four criteria pass. The
one that fails, osteoarthritis severity at Kellgren-Lawrence grade 4, governs
absolutely. It also routes through `MEDICARE-FFS-01`, where `requires_prior_auth` is
`false` but `requires_coverage_review` is `true` — a verifier that collapses those two
fields returns `NO_AUTH_REQUIRED` and never verifies anything. Verification effort is
deliberately concentrated on `C4`, which passes, drawing attention away from the
trivially detectable `C2`, which decides the case. It is the only case where the
correct output is *not* a list of documents to go and fetch.

### The paired traps

Several mechanisms appear twice with opposite consequences, so a verifier cannot score
well by adopting a fixed heuristic:

| Mechanism | In `0001` | In `0002` / `0003` |
|---|---|---|
| Locked-knee waiver | wrongly firing is harmless | wrongly firing flips `NOT_READY` to `READY_FOR_SUBMISSION` |
| Attestation `AT4` | fully corroborated | `0002`: not supported |
| Severe osteoarthritis | absent | `0003`: contradicts arthroscopy, **supports** `PA-TKA-001` |
| 60-day therapy course | supports at 42-day threshold | contradicts `PA-TKA-001` at 90-day threshold |

The last two rows are the most valuable property of the corpus. The **same radiology
report** contradicts one policy and supports another, and the **same therapy episode**
supports one threshold and fails another. No single-policy corpus can produce that,
and it is what stops a verifier learning that "severe osteoarthritis" is generically
disqualifying rather than policy-specific.

---

## 7. Tier 1 versus tier 2

**Tier 1** policies are grounded in the current extract and can be generated against
today. **Tier 2** cannot. `PA-SPINE-MRI-001` is tier 2 because the extract contains no
low back pain, no lumbar radiculopathy, and no MRI modality anywhere — Synthea has no
back pain module, so regenerating with default modules will not help.

`grounding/PA-SPINE-MRI-001.yaml` records the blocking findings and two remediation
paths. The recommended one is a custom Synthea module (roughly a day's work) which
reproduces the property that makes the knee scenario work: a real careplan duration
distribution straddling the policy threshold, so labels derive from data rather than
from generator choice.

Keep the spine policy in the corpus regardless. It is the only disjunctive policy with
nested logic, and its four-week threshold in branch `B2` versus six weeks in branch
`B1` is the cleanest test of whether a model reads thresholds from the policy in force
or recites a memorised number.

---

## 8. The strongest signal in the data

`PA-KNEE-ARTHRO-001 C4` requires at least six weeks of physical therapy. Six weeks is
42 days. The 230 PT careplans in `../synthea_data/careplans.csv` have these durations:

| Days | 14 | 21 | 28 | 30 | 35 | 37 | 60 | 67 |
|---|---|---|---|---|---|---|---|---|
| Count | 59 | 41 | 47 | 7 | 41 | 9 | 9 | 15 |

**204 fail the threshold, 24 satisfy it** (228 ended, 2 still open). That split comes
from the data, not from a generator's sampling choice, which is what makes it
trustworthy as an evaluation signal. For a balanced split, oversample the 60- and
67-day careplans rather than reweighting.

Three features of the real Aetna policy make this scenario unusually well suited to
the task: the requirement specifies therapy that is in-person **as opposed to home or
virtual**; it accepts **either** therapy notes **or** claims history as proof; and it
**waives** the requirement entirely for a locked knee with a displaced bucket-handle
tear. Modality discrimination, alternative evidence pathways, and conditional logic
are all written into the source policy rather than invented here.

### One caveat that will cost you if ignored

**Do not ground symptom persistence in Synthea's pain scores.** The 16,820 "Pain
severity" observations are attached predominantly to wellness encounters (9,964) and
are not clinically coherent. Chronic-pain patients average 3.36 versus 2.57 for
everyone else, which is noise. Patient `1c591f0d-95b1-4289-94a9-9713ab3834e7` has had
knee osteoarthritis since 1989 and annual pain scores of 1, 3, 1, 3, 2, 1, 2, 3, 0, 1.

Synthea does not model symptom trajectory. "Symptoms persisted despite treatment" must
be **authored**, which is precisely why the ledger owns the truth and not the timeline.

---

## 9. Licensing and provenance

Every policy carries a `provenance` block with a source URL and an explicit
`relationship` field. **No criterion text in this corpus reproduces source policy
prose.** All criterion text is original paraphrase.

| Source | Status | How it is used here |
|---|---|---|
| [CMS Medicare Coverage Database](https://www.cms.gov/medicare-coverage-database/search.aspx) | US Government work, not subject to copyright | Safest to build on. LCD *structure* consulted. |
| [Aetna CPB 0673](https://www.aetna.com/cpb/medical/data/600_699/0673.html), [CPB 0236](https://www.aetna.com/cpb/medical/data/200_299/0236.html) | Copyrighted, publicly readable | Clinical logic adapted, text paraphrased, URL cited. |
| [Carelon guidelines](https://guidelines.carelonmedicalbenefitsmanagement.com/current-radiology-guidelines/) | Proprietary, reproduction restricted | Design reference only. **No text or close paraphrase included.** |
| [UnitedHealthcare policies](https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html) | Copyrighted | The medical-policy vs auth-requirement architecture, which is an idea rather than protected expression. |

**CPT codes are deliberately absent everywhere.** CPT descriptors are AMA-copyrighted
and CMS LCDs embed them. Services here are keyed on SNOMED CT and free-text
descriptions only, which costs nothing since Synthea uses SNOMED anyway.

All plan IDs (`AETNA-COMMERCIAL-01` and the rest) are fictional constructs layered on
the payer names Synthea already uses. The authorisation requirements are illustrative
and are not a transcription of any real plan's requirement list.

---

## 10. Suggested next steps

Corpus scale (0.3.0) is in place: `KNEE-ARTHRO-0002-B` is generated as a Gianna
variant with PT enclosed; Sharilyn is also run against `PA-TKA-001`; distractors
and the other four policies are in the generated set. Remaining work is the
verifier, not more packets.

1. **Validate the schema by hand.** Read `cases/KNEE-ARTHRO-0002/` end to end against
   `policies/PA-KNEE-ARTHRO-001.yaml`. If anything in the schema is going to break, it
   will show up there.

2. **Build the policy resolver first**, before any verification code. It is §3.1.
   A generator-side copy lives in `src/data_generation/resolve.py`; reuse it at
   runtime. Every case already carries the gold answer in `gold/labels.yaml` under
   `policy_resolution`.

3. **Score frozen vs generated separately.** The three hand-authored cases remain
   the human-audited slice. Generated packets share `labelled_by: template-v0.3`.

### Corpus hygiene to preserve as you scale

- Keep clean, fully compliant cases in the mix or false-positive rate becomes
  unmeasurable.
- **Never let anything under `gold/` reach a prompt or a retrieval index.** Assert it
  in the loader, not in a comment.
- **Never let post-request events into a packet.** This is the most damaging scoping
  bug available, because it hands the verifier information the real reviewer could not
  have had, and the case still looks entirely plausible. `KNEE-ARTHRO-0003` is the
  live hazard: a 2016 fracture careplan of exactly 60 days, which would satisfy the
  therapy criterion from the wrong body region two years after the request.
- **Keep the lookback per-criterion, not global.** `KNEE-ARTHRO-0003` depends on a
  1986 osteoarthritis diagnosis that no sensible global window would retain.
- Hold out entire **policies**, not just cases, to test generalisation to unseen
  criteria.
- Use different model families for generation and verification, at least in the
  evaluation split. A single-model monoculture will flatter you.
- Keep a small human-audited slice, around 100 criteria, as insurance against a
  systematic prompt bug.
- Version and seed everything. Record generator model and prompt hash per case. You
  will regenerate this corpus several times.
- Generated notes are templates, not LLM prose. Score the frozen three separately
  if you need a human-audited slice.
