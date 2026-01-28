"""Evaluation metrics for SAT-Graph-RAG baseline comparison.

Implements the metrics from the paper's evaluation framework:
- Temporal Precision/Recall (Pattern A: Point-in-Time)
- Action-Attribution F1 (Pattern B: Hierarchical)
- Causal-Chain Completeness (Pattern C: Provenance)
"""

from typing import List, Set, Dict, Any
from datetime import date
from dataclasses import dataclass


@dataclass
class CTV:
    """Component Temporal Version."""
    ctv_id: str
    component_id: str
    version_number: int
    date_start: date
    date_end: date | None


@dataclass
class ActionNode:
    """Amendment action node."""
    action_id: str
    amendment_number: str
    date: date


def temporal_precision(retrieved_ctvs: List[CTV], query_date: date) -> float:
    """Calculate temporal precision.

    Definition: Percentage of retrieved CTVs that are valid for the query date.

    A CTV is valid for a date if:
    - date_start <= query_date
    - date_end is None OR date_end > query_date

    Args:
        retrieved_ctvs: List of CTVs retrieved by the system
        query_date: The target date from the query

    Returns:
        Float between 0.0 and 1.0

    Expected Results:
        - SAT-Graph-RAG: 1.0 (100%) - always returns temporally valid versions
        - Baseline RAG: 0.0 (0%) - returns current version regardless of date
    """
    if not retrieved_ctvs:
        return 0.0

    valid_ctvs = [
        ctv for ctv in retrieved_ctvs
        if ctv.date_start <= query_date and (ctv.date_end is None or ctv.date_end > query_date)
    ]

    return len(valid_ctvs) / len(retrieved_ctvs)


def temporal_recall(retrieved_ctvs: List[CTV], ground_truth_ctvs: List[CTV]) -> float:
    """Calculate temporal recall.

    Definition: Percentage of all ground-truth relevant CTVs that were retrieved.

    Args:
        retrieved_ctvs: List of CTVs retrieved by the system
        ground_truth_ctvs: List of CTVs that should have been retrieved

    Returns:
        Float between 0.0 and 1.0

    Expected Results:
        - SAT-Graph-RAG: High (0.8-1.0)
        - Baseline RAG: Low (0.0-0.2)
    """
    if not ground_truth_ctvs:
        return 1.0  # No ground truth to recall

    retrieved_ids = {ctv.ctv_id for ctv in retrieved_ctvs}
    ground_truth_ids = {ctv.ctv_id for ctv in ground_truth_ctvs}

    recalled = retrieved_ids & ground_truth_ids

    return len(recalled) / len(ground_truth_ids)


def action_attribution_f1(
    predicted_actions: List[str],
    ground_truth_actions: List[str]
) -> Dict[str, float]:
    """Calculate F1-score for Action node attribution.

    Definition: F1-score for correctly identifying which Action nodes
    (amendments) affected a given scope (e.g., all articles in a Title).

    Args:
        predicted_actions: List of action IDs predicted by the system
        ground_truth_actions: List of action IDs that actually affected the scope

    Returns:
        Dict with 'precision', 'recall', and 'f1' scores

    Expected Results:
        - SAT-Graph-RAG: High F1 (0.8-1.0) - can traverse relationships
        - Baseline RAG: 0.0 - has no Action nodes
    """
    if not ground_truth_actions:
        # No ground truth - if system returned nothing, that's correct
        if not predicted_actions:
            return {'precision': 1.0, 'recall': 1.0, 'f1': 1.0}
        else:
            return {'precision': 0.0, 'recall': 1.0, 'f1': 0.0}

    if not predicted_actions:
        return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

    predicted_set = set(predicted_actions)
    ground_truth_set = set(ground_truth_actions)

    true_positives = len(predicted_set & ground_truth_set)
    false_positives = len(predicted_set - ground_truth_set)
    false_negatives = len(ground_truth_set - predicted_set)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives
    }


def causal_chain_completeness(
    retrieved_chain: List[str],
    ground_truth_chain: List[str]
) -> float:
    """Calculate causal chain completeness.

    Definition: Percentage of ground-truth causal chain correctly reconstructed.
    Compares sequences of Action nodes in chronological order.

    Args:
        retrieved_chain: Ordered list of action IDs retrieved by the system
        ground_truth_chain: Ordered list of action IDs in correct sequence

    Returns:
        Float between 0.0 and 1.0

    Expected Results:
        - SAT-Graph-RAG: High (0.8-1.0) - has provenance tracking
        - Baseline RAG: 0.0 - cannot answer provenance queries
    """
    if not ground_truth_chain:
        return 1.0  # No chain to reconstruct

    if not retrieved_chain:
        return 0.0

    # Count how many positions match in sequence
    correct_sequence = 0
    for i, gt_action in enumerate(ground_truth_chain):
        if i < len(retrieved_chain) and retrieved_chain[i] == gt_action:
            correct_sequence += 1

    return correct_sequence / len(ground_truth_chain)


def attribution_accuracy(
    predicted_amendment: str | None,
    ground_truth_amendment: str
) -> bool:
    """Binary attribution accuracy.

    Definition: Did the system correctly identify the amendment?
    Used for simple provenance queries like "Which amendment changed Article X?"

    Args:
        predicted_amendment: Amendment ID predicted by system (or None)
        ground_truth_amendment: Correct amendment ID

    Returns:
        True if correct, False otherwise

    Expected Results:
        - SAT-Graph-RAG: True (100%) - has Action nodes with amendment data
        - Baseline RAG: False (0%) - cannot answer
    """
    if predicted_amendment is None:
        return False

    return predicted_amendment.lower() == ground_truth_amendment.lower()


def evaluate_text_containment(
    text: str,
    should_contain: List[str],
    should_not_contain: List[str]
) -> Dict[str, Any]:
    """Evaluate if retrieved text contains expected keywords.

    Helper metric for validating that correct version was retrieved.

    Args:
        text: Retrieved text
        should_contain: Keywords that should be present
        should_not_contain: Keywords that should NOT be present

    Returns:
        Dict with scores and details
    """
    text_lower = text.lower()

    contains_count = sum(1 for keyword in should_contain if keyword.lower() in text_lower)
    not_contains_count = sum(1 for keyword in should_not_contain if keyword.lower() in text_lower)

    contains_rate = contains_count / len(should_contain) if should_contain else 1.0
    not_contains_penalty = not_contains_count / len(should_not_contain) if should_not_contain else 0.0

    # Score = fraction of required keywords present - fraction of forbidden keywords present
    score = contains_rate - not_contains_penalty
    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

    return {
        'score': score,
        'contains_count': contains_count,
        'contains_total': len(should_contain),
        'not_contains_count': not_contains_count,
        'not_contains_total': len(should_not_contain),
        'passed': score >= 0.8
    }


def calculate_summary_completeness(
    retrieved_articles: List[str],
    ground_truth_articles: List[str]
) -> float:
    """Calculate summary completeness for hierarchical queries.

    Definition: Percentage of ground-truth affected articles that were
    correctly included in the summary.

    Args:
        retrieved_articles: List of article IDs retrieved
        ground_truth_articles: List of article IDs that should be included

    Returns:
        Float between 0.0 and 1.0
    """
    if not ground_truth_articles:
        return 1.0

    retrieved_set = set(retrieved_articles)
    ground_truth_set = set(ground_truth_articles)

    found = len(retrieved_set & ground_truth_set)

    return found / len(ground_truth_set)


# Example usage for testing
if __name__ == "__main__":
    from datetime import date

    # Test temporal_precision
    print("Testing temporal_precision...")

    # SAT-Graph-RAG case: Returns correct historical version
    query_date = date(2005, 1, 1)
    sat_ctvs = [
        CTV("ctv1", "art_214", 1, date(1988, 10, 5), date(2009, 1, 1))  # Valid for 2005
    ]
    baseline_ctvs = [
        CTV("ctv4", "art_214", 4, date(2020, 1, 1), None)  # Invalid for 2005 (anachronistic)
    ]

    sat_precision = temporal_precision(sat_ctvs, query_date)
    baseline_precision = temporal_precision(baseline_ctvs, query_date)

    print(f"  SAT-Graph-RAG: {sat_precision:.1%} (expected: 100%)")
    print(f"  Baseline RAG: {baseline_precision:.1%} (expected: 0%)")

    # Test action_attribution_f1
    print("\nTesting action_attribution_f1...")

    sat_actions = ["ec_59", "ec_108"]
    baseline_actions = []  # Baseline has no Action nodes
    ground_truth = ["ec_59", "ec_108"]

    sat_f1 = action_attribution_f1(sat_actions, ground_truth)
    baseline_f1 = action_attribution_f1(baseline_actions, ground_truth)

    print(f"  SAT-Graph-RAG F1: {sat_f1['f1']:.1%}")
    print(f"  Baseline RAG F1: {baseline_f1['f1']:.1%}")

    print("\n✅ Metrics implementation complete!")
