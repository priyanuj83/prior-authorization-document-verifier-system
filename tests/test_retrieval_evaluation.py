from src.enums import RetrievalFailureCategory
from src.retrieval_evaluation import categorize_failure, evidence_note_recall, recall_at_k


def test_recall_uses_caller_supplied_gold_names() -> None:
    retrieved = [
        "input/notes/2014-02-12-ortho.md",
        "input/notes/2014-04-01-pt-discharge.md",
    ]
    gold = ["2014-04-01-pt-discharge.md"]
    assert evidence_note_recall(retrieved, gold) == 1.0
    assert recall_at_k(retrieved, gold, k=1) == 0.0
    assert recall_at_k(retrieved, gold, k=2) == 1.0


def test_failure_category_stops_at_the_earliest_stage() -> None:
    assert (
        categorize_failure(
            gold_files=["pt.md"],
            retrieved_files=["other.md"],
            extraction_correct=True,
            temporal_correct=True,
            verification_correct=True,
        )
        is RetrievalFailureCategory.RETRIEVAL_MISS
    )
    assert (
        categorize_failure(
            gold_files=["pt.md"],
            retrieved_files=["pt.md"],
            extraction_correct=False,
            temporal_correct=False,
            verification_correct=False,
        )
        is RetrievalFailureCategory.EXTRACTION_ERROR
    )
    assert (
        categorize_failure(
            gold_files=["pt.md"],
            retrieved_files=["notes/pt.md"],
            extraction_correct=True,
            temporal_correct=True,
            verification_correct=True,
        )
        is None
    )
