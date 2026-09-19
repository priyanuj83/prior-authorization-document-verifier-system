# Healthcare Evidence Verifier — System Design Architecture (Current State)

## 1. Purpose of this document

This document captures the system-design decisions made so far for the **Healthcare Evidence Verifier**.

It is intended to be used as a handoff document for a coding agent to build the **project skeleton only**.

Important:

- The retrieval strategy has **not** been designed yet.
- The final tech stack has **not** been selected yet.
- This document should therefore be used to create interfaces, data models, module boundaries, enums, and placeholder components — **not** to implement the full retrieval or verification pipeline prematurely.

---

# 2. Business problem

The system is a **provider-side prior-authorization evidence verification system**.

Its purpose is to help a healthcare provider determine whether a prior-authorization submission contains enough clinical documentation to support the applicable insurance-policy requirements.

The system does **not**:

- decide whether a patient should receive treatment,
- approve or deny insurance coverage,
- replace the insurer,
- make the final clinical decision.

Instead, it answers:

> Given a prior-authorization request, the submitted clinical notes, and the applicable insurance policy, does the submitted record contain enough evidence to support each policy criterion?

---

# 3. Primary system inputs

A case is evaluated from three main input categories.

## 3.1 Prior-authorization request

Example source:

```text
input/pa_form.yaml
```

The PA request contains case-level information such as:

- member / patient information,
- `plan_id`,
- requested service,
- `service_key`,
- `submitted_date`,
- diagnosis,
- provider attestations,
- list of enclosed clinical records.

Important resolver fields:

```text
plan_id
service_key
submitted_date
```

These are used to determine which policy version applies to the case.

---

## 3.2 Clinical notes

Example source:

```text
input/notes/*.md
```

These are the submitted medical records that the verifier is allowed to inspect.

Examples include:

- emergency department notes,
- orthopedic consultations,
- physical-therapy notes,
- MRI reports,
- follow-up notes.

The verifier must base its evidence judgments only on the records available to it.

---

## 3.3 Applicable insurance policy

The applicable policy is **not assumed directly from the case folder**.

The system first resolves the appropriate policy version using the case metadata.

The policy provides the criteria that must be verified against the submitted clinical documentation.

---

# 4. Hidden evaluation data

The dataset also contains hidden files used only for dataset generation and evaluation.

Examples:

```text
gold/labels.yaml
gold/ledger.yaml
gold/generation_plan.yaml
```

These files must **never** be exposed to the verifier during normal evaluation.

Their roles are:

- `labels.yaml` — gold-standard expected labels,
- `ledger.yaml` — underlying synthetic clinical truth,
- `generation_plan.yaml` — instructions used to construct the synthetic case.

The system should preserve a hard architectural boundary:

```text
MODEL / VERIFIER INPUT
----------------------
pa_form
clinical notes
resolved policy / structured requirements

HIDDEN EVALUATION DATA
----------------------
labels
ledger
generation plan
```

---

# 5. High-level workflow

```text
Prior-Authorization Case
        |
        v
Policy Resolver
        |
        |-- if RESOLVED --> selected policy version
        |
        |-- if UNRESOLVED --> manual review
        |
        |-- if MULTIPLE_MATCHES --> manual review
        |
        v
Structured Policy Criteria
        |
        v
Criterion Decomposition
        |
        v
Atomic Sub-Requirements
        |
        v
Atomic Verification
        |
        v
Sub-Requirement Results
        |
        v
Criterion Aggregation
        |
        v
Criterion-Level Results
        |
        v
Case-Level Deterministic Aggregation
        |
        v
Overall Submission Status
```

---

# 6. Policy criteria and decomposition

A policy criterion should not always be treated as one large sentence.

Example criterion:

```text
At least 6 weeks of supervised physical therapy.
```

This criterion should be decomposed into smaller atomic sub-requirements that can be verified independently.

Example decomposition:

```text
C4.1 Physical therapy actually occurred.
C4.2 The therapy was for the relevant body part / condition.
C4.3 The therapy was supervised.
C4.4 The documented therapy duration was at least 6 weeks.
```

This decomposition is important because a single criterion may require:

- multiple facts,
- evidence from multiple notes,
- date arithmetic,
- temporal reasoning,
- distinction between recommendation and actual treatment,
- distinction between relevant and irrelevant body regions or conditions.

---

# 7. Policy decomposition lifecycle

Policy criteria should be decomposed **once per policy version**, not separately for every patient case.

Reasoning:

- lower LLM cost,
- lower latency,
- more consistent behavior,
- easier debugging,
- easier evaluation,
- reduced risk that the same policy is decomposed differently for different patients.

The decomposed requirements should be treated as a **persisted structured policy representation**, not merely as a temporary cache.

A cache may later be added for performance, but the source of truth should be a persisted policy representation.

---

# 8. Atomic verifier

The atomic verifier evaluates **one sub-requirement at a time**.

Example:

```text
Sub-requirement:
PT was supervised.
```

Its job is to determine whether the submitted clinical record:

- proves the sub-requirement,
- fails to prove the sub-requirement,
- affirmatively refutes the sub-requirement.

---

# 9. Atomic verifier labels

Each sub-requirement receives one of three labels:

```text
PROVEN
NOT_PROVEN
REFUTED
```

## PROVEN

The submitted record contains sufficient evidence to establish the sub-requirement.

Example:

```text
"Each session was delivered here under direct supervision..."
```

## NOT_PROVEN

The submitted record does not contain enough evidence to establish the sub-requirement.

This does **not** necessarily mean that the event did not happen.

Example:

```text
"Physical therapy referral placed."
```

This proves recommendation/referral, but does not prove attendance, supervision, or completion.

## REFUTED

The submitted record contains affirmative evidence that conflicts with the sub-requirement.

Example:

```text
"Patient declined physical therapy."
```

This can affirmatively refute a claim that physical therapy was completed.

---

# 10. Atomic verifier output contract

The atomic verifier should return a **consistent structured schema** for every label.

Conceptually:

```yaml
criterion_id: C4
sub_requirement_id: C4.3
sub_requirement: "Physical therapy was supervised"

output_label: PROVEN | NOT_PROVEN | REFUTED

rationale: >
  Concise explanation of why the sub-requirement received this label.

notes:
  - file: "example-note.md"
    evidence: "Exact supporting, insufficient, or refuting passage from the note."
    evidence_rationale: >
      Explanation of why this passage proves, fails to prove,
      or refutes the sub-requirement.
```

Important design rule:

`notes` should be a **list**, because a sub-requirement may depend on evidence from multiple clinical documents.

Example:

```yaml
notes:
  - file: "2014-01-10-pt-evaluation.md"
    evidence: "Initial supervised PT evaluation completed."
    evidence_rationale: "Establishes PT start date."

  - file: "2014-02-28-followup.md"
    evidence: "Patient continues supervised PT twice weekly."
    evidence_rationale: "Establishes continuation of supervised PT."
```

---

# 11. Rationale vs evidence

The system must preserve the distinction between:

## Evidence

What the clinical record actually says.

Example:

```text
"Patient declined physical therapy."
```

## Rationale

Why that evidence leads to the verifier label.

Example:

```text
This statement affirmatively indicates that PT was not undertaken,
so the sub-requirement is REFUTED.
```

The system should not ask the user to trust only generated reasoning.

The exact supporting/refuting/insufficient evidence should be preserved for auditability.

---

# 12. Criterion-level labels

After all sub-requirements under a criterion are evaluated, the criterion receives one of three labels:

```text
SUPPORTED
MISSING
CONTRADICTED
```

The aggregation rule is deterministic.

## SUPPORTED

```text
All sub-requirements = PROVEN
```

Then:

```text
criterion = SUPPORTED
```

## MISSING

```text
At least one sub-requirement = NOT_PROVEN
AND
no sub-requirement = REFUTED
```

Then:

```text
criterion = MISSING
```

Interpretation:

The submitted documentation does not contain enough evidence to establish the entire criterion.

## CONTRADICTED

```text
At least one sub-requirement = REFUTED
```

Then:

```text
criterion = CONTRADICTED
```

This has higher precedence than `MISSING`.

Example:

```text
C4.1 PROVEN
C4.2 NOT_PROVEN
C4.3 REFUTED
C4.4 PROVEN
```

Final criterion result:

```text
CONTRADICTED
```

because affirmative contradictory evidence exists.

---

# 13. Criterion-level output expectations

For each policy criterion, the user should be able to see:

- criterion ID,
- criterion text,
- final criterion label,
- the evaluated sub-requirements,
- the result for each sub-requirement,
- the evidence used,
- exact source notes,
- concise rationales.

The system should make clear whether the issue is:

- enough evidence exists,
- evidence is missing or insufficient,
- evidence affirmatively conflicts with the policy requirement.

---

# 14. Case-level overall status

The overall case status should be derived using deterministic code, not an LLM.

The criterion-level labels are:

```text
SUPPORTED
MISSING
CONTRADICTED
```

The case-level statuses are:

```text
READY_FOR_SUBMISSION
DOCUMENTATION_INCOMPLETE
NEEDS_CLINICAL_REVIEW
```

---

# 15. Case-level aggregation rules

## Rule 1 — contradiction has highest priority

If **any** criterion is:

```text
CONTRADICTED
```

then:

```text
overall_status = NEEDS_CLINICAL_REVIEW
```

This includes cases where some criteria are also `MISSING`.

Example:

```text
C1 SUPPORTED
C2 CONTRADICTED
C3 SUPPORTED
C4 MISSING
```

Result:

```text
NEEDS_CLINICAL_REVIEW
```

## Rule 2 — missing documentation

If no criterion is contradicted, but **at least one** criterion is:

```text
MISSING
```

then:

```text
overall_status = DOCUMENTATION_INCOMPLETE
```

Example:

```text
C1 SUPPORTED
C2 SUPPORTED
C3 MISSING
C4 SUPPORTED
```

Result:

```text
DOCUMENTATION_INCOMPLETE
```

Recommended behavior:

- identify which requirements are missing,
- explain what documentation was insufficient,
- suggest locating or adding appropriate supporting documentation if it exists.

The system should **not assume** that the missing evidence definitely exists somewhere else.

## Rule 3 — all criteria supported

If all applicable criteria are:

```text
SUPPORTED
```

then:

```text
overall_status = READY_FOR_SUBMISSION
```

Important:

`READY_FOR_SUBMISSION` does **not** mean:

- insurance approval is guaranteed,
- the procedure is medically approved,
- coverage is guaranteed.

It means the submitted evidence appears complete relative to the evaluated policy criteria.

---

# 16. Why case-level aggregation is deterministic

The system should not use an LLM to decide:

```text
SUPPORTED + SUPPORTED + MISSING + SUPPORTED
```

means:

```text
DOCUMENTATION_INCOMPLETE
```

This is explicit business logic and should therefore be implemented as deterministic application code.

General principle:

> Do not use an LLM for a decision that can be expressed as a simple, explicit, testable rule.

---

# 17. Policy Resolver

A dedicated **Policy Resolver** is required because insurers may update policies over time.

A case must be evaluated against the policy version that was applicable on the case's submission date.

The resolver operates before verification.

Architecture boundary:

```text
Policy Resolver responsibility:
Determine which policy/version applies to the case.

Atomic Verifier responsibility:
Given an already-resolved sub-requirement and clinical evidence,
determine PROVEN / NOT_PROVEN / REFUTED.
```

The atomic verifier should **not** decide which policy version applies.

---

# 18. Policy resolver inputs

The resolver uses information already present in the prior-authorization request:

```text
plan_id
service_key
submitted_date
```

Conceptually:

```text
plan_id        -> which insurance plan?
service_key    -> which requested service?
submitted_date -> which version was active at the time?
```

---

# 19. Policy version matching rule

A policy version is applicable only if the case submission date falls within its effective window.

Conceptually:

```text
effective_from <= submitted_date
```

AND:

```text
effective_to is null
OR
submitted_date <= effective_to
```

A policy version must **not** be selected before its `effective_from` date.

A previous policy version must **not** be selected after its `effective_to` date.

---

# 20. Policy gaps

Example:

```text
V1:
effective_from = 2024-01-01
effective_to   = 2024-12-31

V2:
effective_from = 2025-02-01
effective_to   = null

Case submitted:
2025-01-15
```

No policy is valid on the submission date.

The system must **not**:

- silently choose V1,
- silently choose V2,
- invent an applicable policy.

Instead, policy resolution should return an unresolved result requiring human review.

General principle:

> When the system cannot establish which rule applies, represent the uncertainty explicitly rather than forcing a policy choice.

---

# 21. Overlapping policy versions

Example:

```text
V1:
2025-01-01 -> 2025-12-31

V2:
2025-06-01 -> 2026-05-31

Case submitted:
2025-08-10
```

Both versions appear applicable.

The system should not arbitrarily choose one.

It should return a multiple-match result and require human review.

---

# 22. Policy resolver statuses

The resolver has three possible statuses:

```text
RESOLVED
UNRESOLVED
MULTIPLE_MATCHES
```

## RESOLVED

Exactly one policy version applies.

Next action:

```text
START_VERIFICATION
```

## UNRESOLVED

No policy version applies.

Next action:

```text
MANUAL_REVIEW
```

## MULTIPLE_MATCHES

More than one policy version appears applicable.

Next action:

```text
MANUAL_REVIEW
```

---

# 23. Policy resolver recommended-action enum

Recommended actions are machine-readable enums:

```text
START_VERIFICATION
MANUAL_REVIEW
```

Status and action are intentionally separate.

Example:

```text
status = UNRESOLVED
recommended_action = MANUAL_REVIEW
```

The status answers:

> What happened?

The action answers:

> What should happen next?

---

# 24. Policy resolver output contract

The resolver should return the **same schema shape** for all outcomes.

Conceptually:

```yaml
status: RESOLVED | UNRESOLVED | MULTIPLE_MATCHES

submission_date: "YYYY-MM-DD"

candidates:
  - policy_id: "..."
    version: "..."
    plan_id: "..."
    service_key: "..."
    effective_from: "YYYY-MM-DD"
    effective_to: "YYYY-MM-DD | null"

status_rationale: >
  Human-readable explanation of why the resolver reached this state.

recommended_action: START_VERIFICATION | MANUAL_REVIEW
```

For `UNRESOLVED`:

```yaml
candidates: []
```

Do not change the schema shape.

---

# 25. Why the resolver returns candidates

The resolver should preserve candidate metadata for:

- debugging,
- auditability,
- human review,
- policy-version troubleshooting,
- investigation of overlapping policy windows.

For a single resolved match:

```text
candidates contains one item
```

For multiple matches:

```text
candidates contains multiple items
```

For no match:

```text
candidates is an empty list
```

---

# 26. Current architecture boundary

The system currently has the following established boundaries:

```text
              PA Request
                  |
                  v
          +----------------+
          | Policy Resolver|
          +----------------+
                  |
          RESOLVED?
          /       \
        no         yes
        |           |
        v           v
 Manual Review   Selected Policy Version
                    |
                    v
          Structured Policy Criteria
                    |
                    v
           Criterion Decomposition
                    |
                    v
          Atomic Sub-Requirements
                    |
                    v
           +----------------+
           | Atomic Verifier|
           +----------------+
                    |
                    v
     PROVEN / NOT_PROVEN / REFUTED
                    |
                    v
          Criterion Aggregation
                    |
                    v
SUPPORTED / MISSING / CONTRADICTED
                    |
                    v
      Deterministic Case Aggregator
                    |
                    v
READY_FOR_SUBMISSION
DOCUMENTATION_INCOMPLETE
NEEDS_CLINICAL_REVIEW
```

---

# 27. Responsibilities by component

## Policy Resolver

Responsible for:

- reading case policy-routing metadata,
- matching plan,
- matching service,
- matching submission date against policy effective windows,
- detecting gaps,
- detecting overlapping versions,
- returning policy-resolution status and candidates.

Not responsible for:

- evaluating medical evidence,
- decomposing clinical evidence,
- assigning clinical-evidence labels.

## Policy Representation / Decomposition Layer

Responsible for:

- storing policy versions,
- storing effective date ranges,
- storing policy criteria,
- decomposing criteria into reusable atomic sub-requirements,
- preserving version-specific structured requirements.

Not responsible for:

- evaluating patient records.

## Atomic Verifier

Responsible for:

- evaluating one atomic sub-requirement,
- returning `PROVEN`, `NOT_PROVEN`, or `REFUTED`,
- returning evidence provenance,
- returning concise justification,
- preserving exact note passages used.

Not responsible for:

- resolving which policy applies,
- deciding the final case-level submission status.

## Criterion Aggregator

Responsible for converting:

```text
PROVEN / NOT_PROVEN / REFUTED
```

into:

```text
SUPPORTED / MISSING / CONTRADICTED
```

using deterministic rules.

## Case Aggregator

Responsible for converting criterion-level results into:

```text
READY_FOR_SUBMISSION
DOCUMENTATION_INCOMPLETE
NEEDS_CLINICAL_REVIEW
```

using deterministic rules.

---

# 28. Important terminology

## Atomic sub-requirement labels

```text
PROVEN
NOT_PROVEN
REFUTED
```

## Criterion-level labels

```text
SUPPORTED
MISSING
CONTRADICTED
```

## Case-level statuses

```text
READY_FOR_SUBMISSION
DOCUMENTATION_INCOMPLETE
NEEDS_CLINICAL_REVIEW
```

## Policy resolver statuses

```text
RESOLVED
UNRESOLVED
MULTIPLE_MATCHES
```

## Policy resolver actions

```text
START_VERIFICATION
MANUAL_REVIEW
```

---

# 29. Design principles established so far

## 29.1 Separate interpretation from deterministic rules

Use model-based reasoning where interpretation is necessary.

Use deterministic code where explicit rules exist.

Examples of deterministic logic:

- policy version date-window matching,
- criterion aggregation,
- case-level status aggregation.

## 29.2 Preserve structured outputs

Downstream code should not have to parse arbitrary natural-language responses.

Every major component should return a predictable schema.

## 29.3 Preserve provenance

Every evidence judgment should be traceable to:

- file,
- exact evidence passage,
- evidence rationale.

## 29.4 Missing is not contradiction

`NOT_PROVEN` / `MISSING` means:

> the supplied documentation does not establish the requirement.

`REFUTED` / `CONTRADICTED` means:

> the supplied documentation contains affirmative evidence against the requirement.

## 29.5 Do not infer absent facts

The system should not convert:

```text
"No evidence found"
```

into:

```text
"The event definitely did not happen."
```

The verifier judges the **submitted documentation**, not unknowable clinical reality.

## 29.6 Do not invent policy applicability

If policy resolution is ambiguous or impossible:

```text
MANUAL_REVIEW
```

rather than guessing.

## 29.7 Policy versions are persistent domain data

A decomposed policy version should be stored and reusable across cases.

It should not be recreated probabilistically for every patient.

---

# 30. What has NOT been designed yet

The following decisions are intentionally still open:

## Evidence retrieval strategy

Not yet decided:

- scan all notes vs retrieve subsets,
- keyword search,
- lexical search,
- embeddings,
- hybrid retrieval,
- reranking,
- note-type filtering,
- date filtering,
- body-region filtering,
- use of PA-form attestations as retrieval hints.

## LLM / model strategy

Not yet decided:

- which model,
- hosted vs local,
- one model vs multiple models,
- structured-output mechanism,
- prompt design,
- whether temporal calculations should be delegated to code.

## Storage layer

Not yet decided:

- relational database,
- document store,
- vector database,
- local filesystem,
- combination of these.

## Application stack

Not yet decided:

- backend framework,
- frontend framework,
- orchestration framework,
- API boundaries,
- deployment environment.

## Evaluation framework

The dataset contains gold labels, but the final evaluation plan is still to be designed.

Possible future evaluation layers may include:

- atomic sub-requirement accuracy,
- criterion-level accuracy,
- citation accuracy,
- evidence-span accuracy,
- false-support rate,
- case-level status accuracy,
- policy-resolution accuracy.

These metrics are not yet finalized.

---

# 31. Skeleton implementation guidance for a coding agent

At this stage, a coding agent should focus on creating:

1. domain models,
2. enums,
3. interfaces / protocols,
4. data-transfer objects,
5. component boundaries,
6. deterministic aggregation functions,
7. placeholder policy resolver,
8. placeholder atomic verifier,
9. test fixtures,
10. clear separation between runtime input and gold evaluation data.

The coding agent should **not yet commit the project to a specific retrieval architecture**.

Recommended placeholder module boundaries might conceptually include:

```text
case_loading
policy_resolution
policy_models
requirement_models
atomic_verification
criterion_aggregation
case_aggregation
evaluation
```

The exact package/framework structure can be decided later.

---

# 32. Current end-to-end contract

The current conceptual contract is:

```text
INPUT
-----
Prior-authorization request
Clinical notes
Policy repository

        |
        v

POLICY RESOLUTION
-----------------
plan_id
service_key
submitted_date

        |
        v

Resolved policy version
or manual-review outcome

        |
        v

POLICY CRITERIA
---------------
Criterion -> decomposed atomic sub-requirements

        |
        v

ATOMIC VERIFICATION
-------------------
Each sub-requirement ->
PROVEN / NOT_PROVEN / REFUTED
+ rationale
+ exact note evidence

        |
        v

CRITERION AGGREGATION
---------------------
SUPPORTED / MISSING / CONTRADICTED

        |
        v

CASE AGGREGATION
----------------
READY_FOR_SUBMISSION
DOCUMENTATION_INCOMPLETE
NEEDS_CLINICAL_REVIEW

        |
        v

USER-FACING RESULT
------------------
- overall case status
- criterion-level status
- sub-requirement-level findings
- exact clinical evidence
- concise rationale
- recommended next action where appropriate
```

---

# 33. Next design topic

The next unresolved engineering question is:

> How should the system find the relevant clinical evidence for each atomic sub-requirement?

Example:

```text
Sub-requirement:
PT duration >= 6 weeks
```

Possible design dimensions still to be explored:

- whether to scan every note,
- whether to narrow notes first,
- whether to organize by date/type,
- whether the PA form should be used as a retrieval hint,
- whether multiple retrieval stages are needed,
- how temporal evidence should be gathered across notes.

This should be designed before selecting the retrieval technology.
