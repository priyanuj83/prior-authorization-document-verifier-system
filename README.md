# Prior Authorization Document Verifier

A provider-side system that checks whether a prior-authorization packet contains enough clinical documentation to support the insurance policy that applies to the request.

It answers one question:

> Given the prior-authorization request, the submitted clinical notes, and the applicable policy, does the record contain enough evidence for each policy criterion?

`READY_FOR_SUBMISSION` means the submitted notes appear complete relative to the evaluated criteria. It does not mean the insurer will approve coverage, and it does not mean a clinician has approved the treatment.

## Status vocabulary

The pipeline uses a different label at each stage. The words are intentional.

| Stage | Labels | Meaning |
|---|---|---|
| Atomic sub-requirement | `PROVEN`, `NOT_PROVEN`, `REFUTED` | What the submitted notes establish about one small fact |
| Policy criterion | `SUPPORTED`, `MISSING`, `CONTRADICTED` | Roll-up of the sub-requirements under one criterion |
| Whole packet | `READY_FOR_SUBMISSION`, `DOCUMENTATION_INCOMPLETE`, `NEEDS_CLINICAL_REVIEW` | What the provider should do next |
| Policy resolution | `RESOLVED`, `UNRESOLVED`, `MULTIPLE_MATCHES` | Whether exactly one policy version applies |
| Next action | `START_VERIFICATION`, `MANUAL_REVIEW` | What to do after resolution |

`NOT_PROVEN` and `MISSING` mean the packet does not establish the requirement. They do not mean the event never happened. `REFUTED` and `CONTRADICTED` mean the notes contain affirmative evidence against the requirement.

Criterion and case labels are deterministic:

- Any `REFUTED` sub-requirement makes the criterion `CONTRADICTED`.
- Any `NOT_PROVEN` sub-requirement, with no `REFUTED`, makes the criterion `MISSING`.
- Every sub-requirement `PROVEN` makes the criterion `SUPPORTED`.
- Any `CONTRADICTED` criterion makes the case `NEEDS_CLINICAL_REVIEW`.
- Any `MISSING` criterion, with no contradiction, makes the case `DOCUMENTATION_INCOMPLETE`.
- Every criterion `SUPPORTED` makes the case `READY_FOR_SUBMISSION`.

## How a case moves through the system

```text
input/pa_form.yaml + input/notes/*.md
        |
        v
Policy Resolver
  plan_id + service_key + submitted_date
  against policy effective dates
        |
        +-- UNRESOLVED or MULTIPLE_MATCHES --> MANUAL_REVIEW
        |
        v
Selected policy version
        |
        v
Criterion decomposition
  stored once per policy version
        |
        v
For each atomic sub-requirement:
  neutral PA context
  retrieval hints
  hybrid search of the submitted packet
  fact extraction
  date and threshold calculations
  atomic label
  optional broader-chart follow-up
        |
        v
Criterion aggregation
        |
        v
Case aggregation
```

Provider attestations on the PA form are claims, not evidence. They are excluded from retrieval hints and checked later as a separate step.

### Policy resolution

The resolver reads `member.plan_id`, `requested_service.service_key`, and `submitted_date` from the PA form. A policy version applies only when:

```text
effective_from <= submitted_date
and (effective_to is empty or submitted_date <= effective_to)
```

A gap between versions returns `UNRESOLVED`. Two versions that both cover the submission date return `MULTIPLE_MATCHES`. In both cases the system stops and asks for manual review. It does not pick a nearby policy.

Plan files in `data/pa_requirements/` say whether a service needs authorization for that plan. Clinical criteria live in `data/policies/`. The repository joins those two sources into dated policy versions.

### Retrieval

Retrieval finds candidate passages. It does not decide whether those passages prove anything.

1. A hint generator turns the atomic requirement, the structured policy semantics, and a neutral case context into search hints: concepts, body part, laterality, date window, supporting patterns, and contradictory patterns.
2. Notes are parsed, split on clinical sections, and stored with provenance: patient, case, file, section, date, and evidence scope.
3. Two searches run over the submitted packet: one for supporting patterns and one for contradictory patterns.
4. Hits are merged, duplicate chunks are collapsed, and a reranker orders them.
5. A fact extractor turns the candidate text into structured events. Each fact is `EXPLICIT`, `NOT_MENTIONED`, or `AMBIGUOUS`.
6. Deterministic code sorts dates, measures elapsed time and gaps, and applies a threshold only when the policy states one. A continuity limit is applied only when the policy states a maximum gap.

Hard filters are limited to patient identity, evidence scope, and a date window when the policy marks that window as mandatory. Note type, body part, and laterality affect ranking. Unknown laterality stays unknown. A left-versus-right mismatch lowers rank and still keeps the note, because a contradiction can appear in an unexpected document.

If the submitted packet is `NOT_PROVEN`, the system can search other provider documents (`AVAILABLE_EHR`) and suggest attaching one. That suggestion leaves the packet label unchanged. If the packet is already `PROVEN`, the system runs a narrower contradiction search against those other documents. A `REFUTED` result does not automatically search for more support.

### Evidence boundary

```text
cases/<id>/input/     visible to the verifier
  pa_form.yaml
  notes/*.md

cases/<id>/gold/      hidden evaluation data
  labels.yaml
  ledger.yaml
  generation_plan.yaml
```

The case loader and the indexer refuse paths under `gold/`. Evaluation code in `src/evaluation` is the only runtime package allowed to read those files, and the verifier packages do not import it. Retrieval scoring can accept a list of gold filenames from a caller. It does not open the gold directory itself.

## Repository layout

```text
design_docs/          system-design handoff documents
data/                 policies, plan requirements, and cases
synthea_data/         raw Synthea extract used by the corpus generator
src/                  verifier and corpus-generator code
tests/                unit and pipeline tests
```

`data/README.md` documents the corpus: how cases are generated, how labels are derived, and how plan requirements differ from clinical policy. This file documents the verifier.

## Code map

Business logic lives under `src/`, with one package per component.

| Package | Responsibility |
|---|---|
| `src/pipeline` | Runs the workflow and returns `CaseVerificationResult` |
| `src/case_loading` | Loads `input/pa_form.yaml` and `input/notes/` |
| `src/policy_models` | Policy versions, criteria, waivers, and the on-disk catalog |
| `src/policy_resolution` | Date-window matching and resolver statuses |
| `src/policy_decomposition` | Turns each criterion into atomic sub-requirements, once per version |
| `src/requirement_models` | Atomic requirements and the policy semantics used for search |
| `src/indexing` | Note parsing, section chunking, metadata, embeddings, in-memory index |
| `src/retrieval` | Hints, lexical search, vector search, merge, rerank, EHR follow-up |
| `src/clinical_extraction` | Structured clinical events and evidence states |
| `src/reasoning` | Date arithmetic, continuity rules, and threshold checks |
| `src/atomic_verification` | `PROVEN` / `NOT_PROVEN` / `REFUTED` for one sub-requirement |
| `src/criterion_aggregation` | Sub-requirement labels to a criterion label |
| `src/case_aggregation` | Criterion labels to the packet status |
| `src/attestation_verification` | Compares provider attestations with verified evidence |
| `src/retrieval_evaluation` | Recall and failure-stage hooks for retrieval experiments |
| `src/evaluation` | Loads hidden gold labels for scoring |
| `src/data_generation` | Builds the synthetic case corpus. Separate from verification |
| `src/enums` | Shared labels, scopes, and evidence states |

`src/common` holds paths, YAML loading, dates, and errors shared by those packages.

### Entry point

```python
from src.pipeline import EvidenceVerifierPipeline

result = EvidenceVerifierPipeline().run_case("KNEE-ARTHRO-0001")

print(result.policy_resolution.status)
print(result.overall_status)
for criterion in result.criteria:
    print(criterion.criterion_id, criterion.label.value)
```

`result.retrieval_traces` holds the hints, candidate passages, and any EHR follow-up for each sub-requirement. `result.attestation_checks` holds the separate attestation comparison.

The current atomic verifier, hint generator, and fact extractor are placeholders behind stable interfaces. On a real case they return `NOT_PROVEN` for each sub-requirement, so a resolved case currently aggregates to `DOCUMENTATION_INCOMPLETE`. The placeholders preserve source text and do not invent clinical facts. A real model can replace `PlaceholderAtomicVerifier`, `PlaceholderRetrievalHintGenerator`, or `PlaceholderClinicalFactExtractor` without changing the pipeline shape.

## What is still open

The design documents deliberately leave these choices unset:

- embedding model
- reranker and ranking weights
- datastore (the current index is in memory)
- LLM prompts for hint generation and fact extraction
- a full atomic-verification model
- final retrieval-evaluation protocol

Lexical and vector scores are ordering signals. A high similarity score does not make a passage proof.

## Design documents

- [Verifier architecture](design_docs/healthcare_evidence_verifier_architecture.md) covers policy resolution, atomic labels, and case aggregation.
- [Retrieval architecture](design_docs/healthcare_evidence_verifier_retrieval_architecture.md) covers hints, hybrid search, extraction, temporal reasoning, and evidence scope.
- [Corpus guide](data/README.md) covers policies, plans, cases, and gold labels.

## Setup

Python 3.9 or newer.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
```

`pytest.ini` adds the repository root to `PYTHONPATH`, so tests import `src` directly.

Regenerate the synthetic cases, without touching the frozen cases `KNEE-ARTHRO-0001` through `KNEE-ARTHRO-0003`:

```bash
python -m src.data_generation.generate --rebuild-catalog
python -m src.data_generation.validate
```

## Corpus at a glance

`data/` contains 5 clinical policies, 3 plans, 3 hand-authored cases, and 194 generated cases. Each case is one prior-authorization episode, not a patient's full chart.

| Path | Role |
|---|---|
| `data/policies/` | Clinical criteria for a service |
| `data/pa_requirements/` | Whether that plan requires authorization on a given date |
| `data/cases/<id>/input/` | Request and notes the verifier may read |
| `data/cases/<id>/gold/` | Expected labels and the hidden ledger |
| `synthea_data/` | Source extract used to build the corpus |
