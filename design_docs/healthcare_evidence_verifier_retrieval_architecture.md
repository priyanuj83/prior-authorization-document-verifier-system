# Healthcare Evidence Verifier — Retrieval Strategy & Architecture

## 1. Purpose

This document captures the current retrieval-system design for the **Healthcare Evidence Verifier**.

It is intended as a technical handoff for a coding agent (for example, Cursor) to build the retrieval skeleton, interfaces, schemas, and module boundaries without prematurely hard-coding implementation choices that are still open.

Important:
- Retrieval architecture is now defined at the system-design level.
- Exact model choices are still open.
- Exact embedding model is still open.
- Exact reranker is still open.
- Exact ranking weights are still open.
- Exact datastore is still open.
- Retrieval must remain auditable and evidence-preserving.

---

# 2. Retrieval problem

The system must determine whether submitted clinical documentation contains enough evidence to prove or refute an atomic policy sub-requirement.

Example:

```text
PT duration >= 6 weeks
```

Relevant evidence may be spread across multiple notes:

```text
Jan 10:
Initial PT evaluation.

Jan 24:
PT session completed.

Feb 28:
Patient continues PT twice weekly.
```

The retrieval system may therefore need to:
- find several related documents,
- combine evidence across dates,
- distinguish recommendation from actual treatment,
- detect treatment interruptions,
- detect contradictory evidence,
- preserve exact source text,
- avoid treating relevance as proof.

The retrieval system should optimize primarily for **high recall, provenance, and semantic relevance**.

---

# 3. High-level architecture

```text
Atomic Sub-Requirement
        +
Neutral PA Case Context
        |
        v
+---------------------------+
| Retrieval Hint Generator  |
|         (LLM)             |
+---------------------------+
        |
        v
Structured Semantic Hints
        |
        v
+---------------------------+
| Hybrid Retrieval Engine   |
+---------------------------+
        |
        +----------------------+
        |                      |
        v                      v
Support Search        Contradiction Search
        |                      |
        +----------+-----------+
                   |
                   v
          Merge + Deduplicate
                   |
                   v
              Reranking
                   |
                   v
          Candidate Evidence
                   |
                   v
+---------------------------+
| Clinical Fact Extractor   |
|         (LLM)             |
+---------------------------+
                   |
                   v
      Structured Clinical Events
                   |
                   v
      Deterministic Calculations
                   |
                   v
           Atomic Verifier
                   |
          +--------+--------+
          |        |        |
        PROVEN  NOT_PROVEN REFUTED
```

---

# 4. Core separation of responsibilities

The system should separate these questions:

```text
1. What evidence should I look for?
2. Which documents are likely to contain it?
3. What facts do those documents actually establish?
4. Does that satisfy or refute the atomic requirement?
```

These are different responsibilities and should not be collapsed into one LLM call.

---

# 5. Role of the policy and PA form

The policy and PA form are not the main searchable evidence corpus.

They define **what to search for**.

## Policy contributes
- policy criterion,
- atomic sub-requirement,
- required fact,
- supporting patterns,
- refuting conditions,
- insufficient-information cases,
- whether calculations are required,
- whether continuity matters.

## PA form contributes neutral case context
Useful fields may include:

```text
requested_service.description
service_key
laterality
diagnosis
submitted_date
episode dates / policy lookback dates
```

The PA form should not be treated as clinical proof.

---

# 6. Attestations must not bias retrieval

Provider attestations should be excluded from retrieval-hint generation.

Example attestation:

```text
Patient completed 6 weeks of physical therapy.
```

If the retrieval system sees this too early, it may become confirmation-biased.

Attestation verification should happen later as a separate task:

```text
Provider attestation
        |
        v
Compare against retrieved/verified evidence
        |
        v
SUPPORTED / NOT_SUPPORTED / CONFLICTED
```

Policy verification and attestation verification are separate concerns.

---

# 7. Retrieval Hint Generator

## Responsibility

The Retrieval Hint Generator interprets:
- the atomic sub-requirement,
- structured policy semantics,
- neutral PA-form context.

It returns **semantic search hints only**.

It does not:
- search the chart,
- decide final ranking,
- decide what counts as proof,
- assign PROVEN / NOT_PROVEN / REFUTED,
- use attestations as truth.

---

# 8. Retrieval Hint Generator inputs

Conceptually:

```text
atomic_sub_requirement
+
structured_policy_semantics
+
neutral_PA_context
```

Example:

```text
Atomic requirement:
PT duration >= 6 weeks

Case:
Right knee arthroscopy
Right knee
Meniscal tear
Submitted 2014-04-16
```

---

# 9. Retrieval Hint Generator output

Conceptual schema:

```yaml
concept: "physical therapy duration"

body_part: "knee"

laterality: "right"

relevant_concepts:
  - physical therapy
  - rehabilitation
  - PT evaluation
  - PT attendance
  - therapy continuation
  - therapy discharge
  - therapy interruption
  - therapy resumption

relevant_date_range:
  start: "..."
  end: "..."

likely_notes:
  - physical therapy note
  - rehabilitation note
  - orthopedic follow-up

supporting_patterns:
  - PT start documented
  - continued treatment over time
  - course completion
  - supervised attendance

contradictory_patterns:
  - PT declined
  - treatment discontinued early
  - prolonged interruption
  - therapy for wrong body part
  - documented duration below threshold
```

The field names can evolve, but the semantic roles should remain stable.

---

# 10. Supporting patterns are not evidence

`supporting_patterns` means:

> What kinds of facts would help establish the atomic requirement?

`contradictory_patterns` means:

> What kinds of facts could refute the atomic requirement?

Actual evidence only comes from clinical records.

---

# 11. Policy decomposition must support retrieval

The persisted policy representation should contain more than atomic text.

Example:

```yaml
atomic_fact: "PT duration >= 6 weeks"

required_facts:
  - PT start
  - PT continuation/end
  - same treatment episode
  - treatment continuity

supporting_patterns:
  - documented PT start
  - documented ongoing attendance
  - documented completion

refuting_conditions:
  - documented duration < 42 days
  - PT never started
  - PT discontinued before threshold
  - treatment involved a different body part

insufficient_information:
  - PT merely recommended
  - PT mentioned without dates
  - no duration evidence
  - ambiguous attendance history

calculation_required: true
calculation_type: temporal_duration
continuity_required: true
```

This representation should be persisted once per policy version and reused across cases.

---

# 12. Retrieval Engine responsibility

The Retrieval Engine receives semantic hints and searches the clinical corpus.

The LLM interprets meaning.

The retrieval engine executes search using predictable, testable logic.

---

# 13. Retrieval signals

The retrieval engine should combine:

```text
1. Metadata
2. Lexical search
3. Semantic/vector search
4. Reranking
```

This is a hybrid design.

Pure vector search is not sufficient.

---

# 14. Metadata

Each note or chunk should carry metadata such as:

```text
case_id
patient_id
note_id
note_date
note_type
body_part
laterality
source_file
section
evidence_scope
```

Potential future fields:

```text
encounter_id
provider_specialty
diagnosis_codes
procedure_codes
document_subtype
```

Metadata supports:
- patient isolation,
- date constraints,
- body-part relevance,
- laterality relevance,
- note-type ranking,
- evidence-scope separation.

---

# 15. Hard filters vs ranking signals

Use hard filters only when exclusion is safe.

## Good hard filters

```text
patient_id == current patient
```

Potentially also:

```text
document date inside a policy-defined hard lookback window
```

if the policy explicitly defines one.

## Usually ranking signals, not hard filters

```text
note_type
body_part
laterality
keywords
provider specialty
```

Reason:
relevant evidence may appear in unexpected note types.

Example:
a contradiction about PT may appear in an orthopedic follow-up rather than a PT note.

---

# 16. Missing vs contradictory metadata

These should not be treated the same.

```text
laterality = null
```

means:

> unknown

while:

```text
laterality = left
```

when the case concerns the right knee means:

> likely mismatch

This distinction should influence ranking.

---

# 17. Lexical retrieval

Lexical retrieval remains useful for exact terminology.

Examples:

```text
physical therapy
physiotherapy
PT
Kellgren-Lawrence grade 4
bucket-handle tear
medial meniscus
```

Exact terminology can be highly valuable in clinical records.

---

# 18. Semantic/vector retrieval

Semantic retrieval handles wording variation.

Example atomic requirement:

```text
PT was supervised
```

Possible note wording:

```text
Patient participated in therapist-guided strengthening exercises
in the outpatient rehabilitation department.
```

This may not match exact keywords but is semantically relevant.

Clinical note chunks should therefore be embedded and indexed.

---

# 19. Vector similarity is not proof

Vector retrieval returns candidates.

It does not determine evidence status.

A semantically similar note can still be:
- irrelevant,
- insufficient,
- contradictory.

Downstream extraction and verification determine what the note establishes.

---

# 20. Two retrieval channels

Retrieval should run two channels:

```text
SUPPORT SEARCH
```

and:

```text
CONTRADICTION SEARCH
```

---

# 21. Support search

Support search asks:

> Which documents are likely to contain evidence that establishes the atomic requirement?

Signals include:

```text
concept
relevant concepts/events
supporting patterns
body part
laterality
likely note types
date range
```

---

# 22. Contradiction search

Contradiction search asks:

> Which documents may contain evidence that refutes or conflicts with the atomic requirement?

Signals include:

```text
refuting conditions
contradictory patterns
body part
laterality
relevant events
date range
```

---

# 23. Why support and contradiction search are separate

Example:

Many notes say:

```text
PT continued.
```

One note says:

```text
PT was discontinued after three weeks.
```

A generic relevance search may over-rank the repeated supporting notes.

A dedicated contradiction channel deliberately searches for counter-evidence.

---

# 24. Merge and deduplicate

Support and contradiction candidate sets should be:

1. merged,
2. deduplicated,
3. reranked.

A single note may appear in both channels.

---

# 25. Reranking

Hybrid retrieval may produce a moderate candidate set.

Example:

```text
100 chunks
   |
   v
Hybrid retrieval
   |
   v
15 candidates
   |
   v
Reranker
   |
   v
5-8 strongest candidates
```

Exact values should be configurable and evaluated.

Do not hard-code final production values yet.

---

# 26. Ranking strategy

Potential ranking signals:

```text
semantic similarity
event/concept relevance
body-part match
laterality match
note-type relevance
temporal relevance
support-pattern match
contradiction-pattern match
```

Exact numeric weights are intentionally not fixed yet.

---

# 27. Initial ranking philosophy

Possible starting hierarchy:

```text
semantic relevance               strong
event / concept relevance        strong
support/refute pattern match     strong in relevant channel

body-part match                  medium
laterality match                 medium
note-type relevance              medium/small
temporal relevance               context-dependent
```

This is a design hypothesis, not a final scoring formula.

---

# 28. Optimize recall first

For evidence verification:

> Missing a critical evidence note is worse than retrieving a few extra irrelevant notes.

Initial retrieval should therefore optimize for:

```text
high evidence recall
```

The fact extractor and verifier provide downstream precision.

---

# 29. Chunking strategy

Avoid blind fixed-token chunking when possible.

Prefer **section-aware clinical chunking**.

Example note:

```text
HPI
Examination
Imaging
Assessment
Plan
```

Possible chunks:

```text
Chunk 1: HPI
Chunk 2: Examination
Chunk 3: Imaging
Chunk 4: Assessment / Plan
```

---

# 30. Chunk provenance

Each chunk should preserve:

```text
patient_id
case_id
note_id
source_file
note_date
note_type
section
body_part
laterality
evidence_scope
```

This supports:
- exact citation,
- reconstruction,
- filtering,
- debugging,
- auditability.

---

# 31. Multi-note evidence

The system must support evidence sets spanning multiple notes.

Example:

```text
Jan 10:
Initial PT evaluation.

Feb 28:
Patient continues PT.
```

A duration requirement may depend on both.

Retrieval should therefore return a **candidate evidence set**, not only one top chunk.

---

# 32. Clinical Fact Extractor

After retrieval and reranking, candidate notes go to an LLM-based fact extractor.

The extractor should not directly make the policy decision.

Its job is to convert unstructured clinical text into grounded facts/events.

---

# 33. Extraction vs verification

Extraction asks:

> What does the note actually establish?

Verification asks:

> What does that fact mean for the policy requirement?

Keep these stages separate.

---

# 34. Structured clinical event object

Conceptual fields may include:

```text
event_date
event_type
treatment_type
body_part
laterality
attendance_status

gap_present
gap_start_date
gap_end_date
gap_duration
resumed_after_gap

source_file
evidence
extraction_rationale
```

Only add fields that are useful for verification.

---

# 35. Unknown facts

The extractor must not invent missing information.

Unknown values should be explicit.

Example:

```yaml
supervised:
  value: null
  evidence_state: NOT_MENTIONED
```

---

# 36. Evidence-state enum

Each extracted fact should have one of:

```text
EXPLICIT
NOT_MENTIONED
AMBIGUOUS
```

Do not use:

```text
INFERRED
```

at the extraction layer.

Inference belongs later.

---

# 37. EXPLICIT

`EXPLICIT` means:

> The fact is directly supported by the semantics of the source text.

It does not require exact keyword matching.

Example:

```text
therapist-guided strengthening exercises
```

can support:

```text
supervised = true
evidence_state = EXPLICIT
```

---

# 38. NOT_MENTIONED

Use when the note provides no meaningful information about the fact.

Example:

```text
Patient attended PT.
```

with no supervision information:

```text
supervised = null
evidence_state = NOT_MENTIONED
```

---

# 39. AMBIGUOUS

Use when the note discusses the concept but does not allow a safe determination.

Example:

```text
Therapy occurred, though supervision status is unclear.
```

Then:

```text
supervised = null
evidence_state = AMBIGUOUS
```

---

# 40. Temporal reasoning

The system must distinguish:

```text
elapsed calendar duration
```

from:

```text
continuous treatment duration
```

Example:

```text
Jan 1: PT started
Feb 20: Returned after a 5-week break
```

A simple date subtraction is not enough to establish continuous PT.

---

# 41. LLM vs deterministic temporal reasoning

The LLM should extract:

```text
event dates
attendance events
gap mentions
gap duration if explicitly stated
resumption events
treatment type
body part
laterality
```

Deterministic code should perform:

```text
event sorting
date arithmetic
gap calculation
duration calculation
continuity-rule application
threshold comparison
```

Principle:

> Use LLMs for semantic interpretation.
> Use code for explicit calculations and business rules.

---

# 42. Continuity rules

The system must not invent what counts as an unacceptable treatment gap.

Continuity thresholds should come from:
- explicit policy language, or
- explicitly defined benchmark rules.

If no continuity rule exists, do not fabricate one.

---

# 43. Evidence scopes

The provider-side product has two evidence pools:

```text
SUBMITTED_PACKET
```

and:

```text
AVAILABLE_EHR
```

This distinction is essential.

---

# 44. SUBMITTED_PACKET

These are the documents actually attached to the PA request.

Evidence from this scope can directly contribute to:

```text
PROVEN
NOT_PROVEN
REFUTED
```

for the submitted packet.

---

# 45. AVAILABLE_EHR

These are other provider-side EHR documents that were not included in the packet.

Evidence from this scope should not silently make the packet complete.

Instead, it can be used to:
- suggest documents to attach,
- detect contradictions,
- inform manual review.

---

# 46. Evidence-scope metadata

Every note/chunk should carry:

```text
evidence_scope = SUBMITTED_PACKET
```

or:

```text
evidence_scope = AVAILABLE_EHR
```

---

# 47. Primary submitted-packet search

The initial verification pass searches only:

```text
SUBMITTED_PACKET
```

for:
- supporting evidence,
- contradictory evidence.

---

# 48. Broader-EHR search after NOT_PROVEN

If submitted evidence produces:

```text
NOT_PROVEN
```

run a broader-EHR support search.

Goal:

> Find potentially relevant evidence omitted from the PA packet.

If found:

```text
Potential supporting document found in EHR.
Consider attaching it.
```

This does not automatically convert the submitted packet result to PROVEN.

---

# 49. Broader-EHR search after PROVEN

If submitted evidence already produces:

```text
PROVEN
```

do not run another broad support search.

Instead run a cheaper targeted contradiction search against:

```text
AVAILABLE_EHR
```

using:
- refuting conditions,
- contradictory patterns,
- body part,
- laterality,
- date range.

---

# 50. Why targeted contradiction search exists

Example:

Submitted packet says:

```text
Patient completed six weeks of PT.
```

Broader EHR says:

```text
Patient stopped PT after two weeks.
```

The system should be capable of surfacing this conflict.

---

# 51. Broader-EHR behavior after REFUTED

Default design:

A clear refutation is already a high-severity result.

A broad support search is not automatically required.

Future versions may optionally search for conflicting documentation for reconciliation.

This behavior is not fully finalized.

---

# 52. Retrieval is not verification

Critical boundary:

Retrieval says:

> These notes are likely relevant.

Verification says:

> These facts prove / fail to prove / refute the requirement.

Example:

```text
Retrieved:
"Physical therapy referral placed."
```

Fact extraction:

```text
PT was recommended.
```

Atomic verification:

```text
Recommendation does not establish attendance.
```

Result:

```text
NOT_PROVEN
```

---

# 53. Retrieval query lifecycle

```text
1. Receive atomic requirement.
2. Load neutral PA context.
3. Generate semantic retrieval hints.
4. Apply patient/scope constraints.
5. Run lexical search.
6. Run semantic/vector search.
7. Run support channel.
8. Run contradiction channel.
9. Merge candidates.
10. Deduplicate.
11. Rerank.
12. Select evidence set.
13. Send candidates to fact extractor.
14. Run deterministic reasoning.
15. Run atomic verification.
```

---

# 54. Retrieval-engine input contract

Conceptually:

```yaml
case_id: "..."
patient_id: "..."

atomic_requirement:
  id: "C4.4"
  text: "PT duration >= 6 weeks"

case_context:
  service_key: "knee_arthroscopy"
  requested_service: "Arthroscopic partial meniscectomy"
  body_part: "knee"
  laterality: "right"
  submitted_date: "2014-04-16"
  relevant_date_range:
    start: "..."
    end: "..."

retrieval_hints:
  concept: "physical therapy duration"
  relevant_concepts: [...]
  likely_notes: [...]
  supporting_patterns: [...]
  contradictory_patterns: [...]
```

---

# 55. Retrieval-engine output contract

Conceptually:

```yaml
support_candidates:
  - note_id: "..."
    chunk_id: "..."
    source_file: "..."
    section: "..."
    note_date: "..."
    evidence_scope: "SUBMITTED_PACKET"
    retrieval_score: 0.0
    retrieval_signals:
      semantic_similarity: 0.0
      lexical_match: 0.0
      body_part_match: true
      laterality_match: true

contradiction_candidates:
  - note_id: "..."
    chunk_id: "..."
    source_file: "..."
    section: "..."
    note_date: "..."
    evidence_scope: "SUBMITTED_PACKET"
    retrieval_score: 0.0
    retrieval_signals:
      semantic_similarity: 0.0
      lexical_match: 0.0
      contradiction_pattern_match: true

merged_candidates:
  - ...
```

Exact score representation is not finalized.

---

# 56. Provenance requirements

Every candidate must retain enough information to trace back to:

```text
patient
case
note
file
section
date
scope
original text
```

This is required for:
- citations,
- debugging,
- evaluation,
- auditability.

---

# 57. Storage / indexing recommendation

Current dataset scale:

```text
197 cases
720 clinical notes
```

This is small.

Do not introduce unnecessary infrastructure solely because embeddings are used.

A reasonable initial architecture could be:

```text
PostgreSQL
+
pgvector
+
full-text search
```

This can support:
- metadata,
- embeddings,
- lexical search,
- date filters,
- case filters,
- evidence scopes.

This is a recommendation, not a locked technology choice.

---

# 58. Why not immediately use a dedicated vector DB

For this scale, a stack such as:

```text
Postgres
+
Pinecone
+
Elasticsearch
+
Redis
```

would likely add complexity without enough benefit.

Prove the retrieval design first.

Scale infrastructure later if needed.

---

# 59. Indexing workflow

```text
Clinical note
        |
        v
Parse metadata
        |
        v
Section-aware chunking
        |
        v
Attach chunk metadata
        |
        v
Generate embedding
        |
        v
Store:
- raw text
- metadata
- embedding
- lexical-searchable text
```

---

# 60. Query-time workflow

```text
Atomic requirement
        +
PA context
        |
        v
Hint generator
        |
        v
Semantic hints
        |
        v
Hard patient/scope constraints
        |
        v
Lexical + vector retrieval
        |
        v
Support + contradiction channels
        |
        v
Merge / dedupe
        |
        v
Rerank
        |
        v
Fact extraction
        |
        v
Deterministic reasoning
```

---

# 61. Ranking weights remain open

Possible signals:

```text
semantic_similarity
lexical_score
body_part_match
laterality_match
note_type_match
date relevance
support_pattern_match
contradiction_pattern_match
```

Initial weights can be heuristic.

Final weights should be informed by evaluation.

---

# 62. Retrieval evaluation

Retrieval should be evaluated separately from verification.

Potential metrics:

```text
Recall@K
Precision@K
MRR
evidence-note recall
evidence-span recall
contradiction recall
```

The most important early question is:

> Did the candidate set contain the gold evidence required to make the correct decision?

---

# 63. Gold evidence and retrieval evaluation

Example:

```text
Gold evidence:
2014-04-01-pt-discharge.md

Retriever Top 5:
1. 2014-02-12-ortho.md
2. 2014-04-01-pt-discharge.md
...
```

In this case retrieval succeeded even if the verifier later failed.

This separation helps debug the right component.

---

# 64. Failure categories

Potential failure categories:

```text
RETRIEVAL_MISS
Gold evidence was not retrieved.

EXTRACTION_ERROR
Evidence was retrieved but structured facts were wrong.

TEMPORAL_REASONING_ERROR
Facts were correct but time/gap logic was wrong.

VERIFICATION_ERROR
Facts were correct but atomic label was wrong.
```

These categories can support observability and evaluation.

---

# 65. Recommended module boundaries

Conceptually:

```text
retrieval/
    hint_generation
    query_models
    hybrid_search
    lexical_search
    semantic_search
    contradiction_search
    reranking
    deduplication

indexing/
    note_parser
    chunking
    metadata_extraction
    embeddings
    index_writer

clinical_extraction/
    fact_extractor
    event_models
    evidence_state_models

reasoning/
    temporal_reasoning
    continuity_rules
    threshold_checks

verification/
    atomic_verifier
```

Exact package names are flexible.

---

# 66. Recommended interfaces

Define interfaces before committing to providers.

Examples:

```text
RetrievalHintGenerator
HybridRetriever
Reranker
ClinicalFactExtractor
TemporalReasoner
AtomicVerifier
```

This keeps implementation technology replaceable.

---

# 67. RetrievalHintGenerator interface

Input:

```text
AtomicRequirement
CaseContext
```

Output:

```text
RetrievalHints
```

It should not access the note index directly.

---

# 68. HybridRetriever interface

Input:

```text
RetrievalHints
CaseContext
EvidenceScope
```

Output:

```text
CandidateEvidenceSet
```

It should not assign atomic labels.

---

# 69. ClinicalFactExtractor interface

Input:

```text
AtomicRequirement
CandidateEvidenceSet
```

Output:

```text
StructuredClinicalEvents / Facts
```

It must preserve source evidence.

---

# 70. TemporalReasoner interface

Input:

```text
StructuredClinicalEvents
PolicyCalculationRules
```

Output:

```text
DerivedFacts
```

Examples:

```text
elapsed_days
continuous_duration
gap_days
threshold_met
```

---

# 71. AtomicVerifier interface

Input:

```text
AtomicRequirement
ExtractedFacts
DerivedFacts
Evidence
```

Output:

```text
PROVEN / NOT_PROVEN / REFUTED
+
rationale
+
notes/evidence
```

---

# 72. Still unresolved

The following are intentionally not finalized:

- embedding model,
- lexical search engine,
- reranker,
- exact top-K values,
- exact ranking weights,
- exact datastore,
- exact note-section parser,
- whether contradiction retrieval uses separate embeddings,
- whether REFUTED triggers broader-EHR reconciliation search.

---

# 73. Coding-agent guidance

At this stage, the coding agent should:

1. create retrieval domain models,
2. create enums,
3. create stable schemas,
4. create retrieval interfaces,
5. implement section-aware chunking skeleton,
6. create metadata models,
7. create placeholder lexical/vector adapters,
8. create merge/deduplication logic,
9. create a reranker interface,
10. create evidence-scope handling,
11. create event extraction schemas,
12. create temporal-reasoning interfaces,
13. create retrieval evaluation hooks,
14. keep model providers abstract,
15. keep database implementation replaceable.

The coding agent should **not**:

- hard-code final retrieval weights,
- assume vector similarity equals evidence,
- expose gold files to runtime retrieval,
- use attestations as retrieval truth,
- collapse retrieval and verification into one LLM call,
- force one-note answers,
- infer missing facts.

---

# 74. End-to-end retrieval contract

```text
INPUT
-----
Atomic sub-requirement
Neutral PA context
Structured policy semantics
Clinical-note corpus

        |
        v

HINT GENERATION
---------------
LLM produces semantic search hints

        |
        v

HYBRID RETRIEVAL
----------------
Metadata constraints
+
Lexical search
+
Vector search
+
Support channel
+
Contradiction channel

        |
        v

MERGE + DEDUPLICATE
-------------------

        |
        v

RERANK
------

        |
        v

CANDIDATE EVIDENCE SET
----------------------

        |
        v

FACT EXTRACTION
---------------
LLM extracts grounded clinical facts/events

        |
        v

DETERMINISTIC REASONING
-----------------------
Date arithmetic
Gap calculation
Continuity rules
Threshold comparison

        |
        v

ATOMIC VERIFICATION
-------------------
PROVEN
NOT_PROVEN
REFUTED
```

Conditional broader-EHR behavior:

```text
NOT_PROVEN
        |
        v
Search AVAILABLE_EHR for missing support
        |
        v
Suggest document to attach


PROVEN
        |
        v
Run targeted contradiction search
against AVAILABLE_EHR
        |
        v
Surface possible conflicts
```

---

# 75. Guiding design principles

## 75.1 Optimize recall before aggressive precision
Do not miss critical evidence to save a small amount of compute.

## 75.2 Retrieval is not proof
A relevant note is not automatically supporting evidence.

## 75.3 Preserve provenance
Every evidence judgment must trace back to source text.

## 75.4 Search for contradictions deliberately
Counter-evidence should not be an accidental by-product.

## 75.5 Separate LLM interpretation from deterministic rules
Use LLMs for semantics.
Use code for explicit calculations and business logic.

## 75.6 Do not let provider attestations bias retrieval
Use neutral case context.

## 75.7 Distinguish submitted evidence from broader EHR evidence
Only attached evidence makes the current packet complete.

## 75.8 Do not overbuild infrastructure
The benchmark is small enough to start with a simple integrated search stack.

## 75.9 Keep technology replaceable
Define interfaces before committing to vendors/frameworks.

---

# 76. Next engineering decisions

The next design topics should be handled separately:

1. exact datastore choice,
2. exact embedding model,
3. exact lexical search approach,
4. exact reranking strategy,
5. exact chunking rules,
6. retrieval evaluation protocol,
7. query-generation prompts,
8. clinical fact-extraction prompt/schema,
9. temporal reasoning implementation,
10. broader-EHR contradiction-search optimization.

These should be driven by benchmark results rather than guesswork.
