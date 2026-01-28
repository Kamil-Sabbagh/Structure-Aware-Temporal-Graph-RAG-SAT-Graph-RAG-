# Proper Baseline Comparison Plan

Based on the paper's evaluation framework, here's the roadmap for a proper comparison.

## Status: Implementation Required

The current comparison (`scripts/compare_baseline.py`) does NOT follow the paper's methodology. It needs to be redesigned from scratch.

## What We Need to Build

### 1. Three Query Patterns (From Paper)

#### Pattern A: Point-in-Time Retrieval (Determinism Test)
**Goal**: Test temporal precision - can the system retrieve the EXACT state of law at a specific date?

**Example Queries** (using real articles from our graph):
- "What did ADCT Article 2 say in 1995?" (should return v5, not v151)
- "What did Article 214 say in 2005?" (should return v1 original, not v2 from 2009)
- "What did Article 222 say in 2000?" (should return v1 original, not v2 from 2002)

**Expected Result**:
- SAT-Graph-RAG: Returns correct historical version ✅
- Baseline: Returns current version (anachronistic) ❌

**Metrics**:
- **Temporal Precision**: % of retrieved CTVs that are valid for the query date
- **Temporal Recall**: % of all ground-truth relevant CTVs retrieved

---

#### Pattern B: Hierarchical Impact Analysis
**Goal**: Test structural awareness - can the system identify all changes within a hierarchical scope?

**Example Queries**:
- "Summarize all changes to Title VIII (Social Order) since 2010"
- "What articles in Chapter II of Title II have been amended?"
- "Show all amendments affecting the Judiciary title (Title IV) between 2000-2010"

**Expected Result**:
- SAT-Graph-RAG: Traverses hierarchy, identifies all affected components ✅
- Baseline: Cannot understand hierarchy, returns keyword matches only ❌

**Metrics**:
- **Action-Attribution Accuracy**: F1-score for correctly identifying all Action nodes affecting the scope
- **Summary Completeness**: % of ground-truth changes correctly included

---

#### Pattern C: Provenance & Causal-Lineage Reconstruction
**Goal**: Test provenance tracking - can the system trace the legislative history of a provision?

**Example Queries**:
- "Which amendment first changed ADCT Article 2?" (Answer: EC 1 in 1992)
- "Trace the complete amendment history of Article 214" (Answer: EC 59 in 2009 created v2)
- "What was the sequence of amendments that affected Article 222?" (Answer: EC 36 in 2002)

**Expected Result**:
- SAT-Graph-RAG: Returns complete causal chain via Action nodes ✅
- Baseline: Cannot answer (no Action nodes) ❌

**Metrics**:
- **Causal-Chain Completeness**: % of ground-truth Action sequence correctly reconstructed
- **Attribution Accuracy**: Binary - did it correctly identify the amendment?

---

### 2. Proper Ground Truth (From Our Graph)

Using actual components we verified exist:

| Article | Component ID | Original Date | Amendments | Versions |
|---------|--------------|---------------|------------|----------|
| ADCT Art 2 | `tit_09_art_1_art_2` | 1988-10-05 | EC 1,3,6,7,... (137 total) | 151 |
| Art 214 | `tit_08_cap_03_sec_01_art_214_art_214` | 1988-10-05 | EC 59 (2009) | 2 |
| Art 222 | `tit_08_cap_05_art_221_inc_IV_art_222` | 1988-10-05 | EC 36 (2002) | 2 |
| Art 216 | `tit_08_cap_03_sec_02_art_215_par_3_art_216` | 1988-10-05 | Unknown | 2 |

---

### 3. Baseline Failure Modes to Demonstrate

#### Anachronism (Pattern A)
**Query**: "What did Article 214 say in 2005?"
- **Correct**: v1 (original 1988 text, valid until 2009)
- **Baseline Returns**: v2 (2009 text - anachronistic!)
- **Proof**: Baseline has no temporal filtering, always returns current version

#### No Structural Awareness (Pattern B)
**Query**: "What changed in Title VIII since 2010?"
- **Correct**: List of specific articles with amendment details
- **Baseline Returns**: Keyword matches, no hierarchical grouping
- **Proof**: Baseline has no HAS_CHILD relationships, cannot traverse hierarchy

#### No Provenance Capability (Pattern C)
**Query**: "Which amendment changed Article 214?"
- **Correct**: EC 59 in 2009
- **Baseline Returns**: Cannot answer (no Action nodes)
- **Proof**: Baseline has no RESULTED_IN relationships, no amendment tracking

---

### 4. Quantitative Metrics Implementation

```python
def temporal_precision(retrieved_ctvs, query_date):
    """% of retrieved CTVs that are valid for the query date"""
    valid = [ctv for ctv in retrieved_ctvs
             if ctv.date_start <= query_date < ctv.date_end]
    return len(valid) / len(retrieved_ctvs) if retrieved_ctvs else 0.0

def temporal_recall(retrieved_ctvs, ground_truth_ctvs):
    """% of all ground-truth CTVs that were retrieved"""
    retrieved_ids = {ctv.id for ctv in retrieved_ctvs}
    ground_truth_ids = {ctv.id for ctv in ground_truth_ctvs}
    return len(retrieved_ids & ground_truth_ids) / len(ground_truth_ids)

def action_attribution_f1(predicted_actions, ground_truth_actions):
    """F1-score for correctly identifying Action nodes"""
    tp = len(set(predicted_actions) & set(ground_truth_actions))
    fp = len(set(predicted_actions) - set(ground_truth_actions))
    fn = len(set(ground_truth_actions) - set(predicted_actions))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

def causal_chain_completeness(retrieved_chain, ground_truth_chain):
    """% of ground-truth causal chain correctly reconstructed"""
    # Compare sequences of Actions in order
    correct_sequence = 0
    for i, gt_action in enumerate(ground_truth_chain):
        if i < len(retrieved_chain) and retrieved_chain[i] == gt_action:
            correct_sequence += 1
    return correct_sequence / len(ground_truth_chain)
```

---

### 5. User-Centered Measures

Beyond automated metrics:

1. **Time-to-Answer**: Measure wall-clock time for complex queries
   - SAT-Graph-RAG: ~25ms (measured)
   - Baseline: ~12ms (measured)
   - **Trade-off**: Baseline is faster but less accurate

2. **Auditability**: Can users verify the answer?
   - SAT-Graph-RAG: YES - provides version numbers, amendment numbers, dates ✅
   - Baseline: NO - black box, no provenance ❌

3. **Trustworthiness** (would require user study):
   - Show lawyers both outputs
   - Ask: "Which answer do you trust more?"
   - Expected: SAT-Graph-RAG wins due to auditability

---

## Implementation Priority

Given time constraints, implement in this order:

### Phase 1: Minimal Viable Comparison (MVP) ✅ RECOMMENDED
**3-5 carefully chosen queries, one per pattern, with proper metrics**

**Queries**:
1. Point-in-time: "What did Article 214 say in 2005?"
   - Ground truth: v1 (1988 text)
   - Metric: Temporal precision

2. Hierarchical: "Which articles in Title VIII have been amended?"
   - Ground truth: List from graph
   - Metric: Action-attribution F1

3. Provenance: "Which amendment changed Article 214?"
   - Ground truth: EC 59
   - Metric: Attribution accuracy (binary)

**Output**: Clean comparison showing SAT-Graph wins on all 3 patterns

### Phase 2: Full Evaluation (If Time Permits)
- 20-30 queries across all patterns
- All quantitative metrics
- Statistical significance testing
- User study with legal experts

---

## Expected Results

### Pattern A (Point-in-Time)
- SAT-Graph-RAG: **100% temporal precision** (always returns correct version)
- Baseline: **0% temporal precision** (always returns current version)

### Pattern B (Hierarchical)
- SAT-Graph-RAG: **High F1** (can traverse hierarchy)
- Baseline: **Low F1** (keyword matching only)

### Pattern C (Provenance)
- SAT-Graph-RAG: **Can answer** (has Action nodes)
- Baseline: **Cannot answer** (no provenance)

**Overall Conclusion**: SAT-Graph-RAG significantly outperforms baseline on all tasks requiring temporal or structural reasoning, at the cost of slightly higher latency.

---

## Next Steps

1. ✅ Identify real articles with amendment history (DONE - see above)
2. ⏳ Build 3-5 test queries with ground truth from graph
3. ⏳ Implement proper metrics (temporal precision/recall, F1, etc.)
4. ⏳ Run comparison and generate clean report
5. ⏳ Add to METRICS_REPORT.md

**Time Estimate**: 2-3 hours for MVP, 1-2 days for full evaluation
