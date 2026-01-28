# Temporal Legal Reasoning Benchmark (TLR-Bench)

A benchmark for evaluating temporal reasoning capabilities in legal RAG systems, based on the Brazilian Federal Constitution (1988-2025).

---

## Overview

**Problem**: Existing legal NLP benchmarks (LegalBench, LexGLUE, CUAD) do not test **temporal reasoning** - the ability to retrieve historically accurate legal text and track changes over time.

**Solution**: TLR-Bench provides standardized tasks for evaluating:
1. **Temporal Precision**: Retrieving correct historical versions
2. **Amendment Attribution**: Identifying which amendments changed what
3. **Provenance Tracking**: Tracing complete legislative history
4. **Temporal Consistency**: Avoiding anachronism errors

---

## Benchmark Structure

### Task Categories

#### Task 1: Point-in-Time Retrieval (Temporal Precision)
**Goal**: Retrieve the exact legal text valid at a specific historical date

**Format**:
```json
{
  "task": "point_in_time",
  "query": "What did Article 214 say on 2005-06-15?",
  "target_date": "2005-06-15",
  "target_component": "tit_08_cap_03_sec_01_art_214_art_214",
  "ground_truth": {
    "correct_version": 1,
    "valid_range": ["1988-10-05", "2009-01-01"],
    "text_hash": "a3f5e8c9...",
    "must_contain": ["lei estabelecerá", "plano nacional de educação"],
    "must_not_contain": ["EC 59", "EC 108"]
  }
}
```

**Evaluation Metric**: **Temporal Precision**
```python
temporal_precision = (# versions valid for date) / (# versions retrieved)
```

**Expected Performance**:
- ✅ Perfect System: 100% (always returns correct historical version)
- ❌ Baseline RAG: 0% (always returns current version)

---

#### Task 2: Amendment Attribution (Provenance)
**Goal**: Identify which constitutional amendment(s) modified a given article

**Format**:
```json
{
  "task": "amendment_attribution",
  "query": "Which constitutional amendments changed Article 214?",
  "target_component": "tit_08_cap_03_sec_01_art_214_art_214",
  "ground_truth": {
    "amendments": ["ec_59", "ec_108"],
    "dates": ["2009-01-01", "2020-01-01"],
    "chronological_order": true
  }
}
```

**Evaluation Metric**: **F1-Score**
```python
precision = TP / (TP + FP)  # Correct amendments / All returned amendments
recall = TP / (TP + FN)     # Correct amendments / All actual amendments
f1 = 2 * (precision * recall) / (precision + recall)
```

**Expected Performance**:
- ✅ Perfect System: F1 = 1.0 (identifies all amendments, no false positives)
- ❌ Baseline RAG: F1 = 0.0 (no amendment tracking capability)

---

#### Task 3: Temporal Difference (Change Detection)
**Goal**: Compare two versions of an article at different dates

**Format**:
```json
{
  "task": "temporal_difference",
  "query": "What changed in Article 214 between 2005 and 2015?",
  "date_1": "2005-01-01",
  "date_2": "2015-01-01",
  "target_component": "tit_08_cap_03_sec_01_art_214_art_214",
  "ground_truth": {
    "changed": true,
    "amendments_between": ["ec_59"],
    "version_1": 1,
    "version_2": 3,
    "change_description": "Modified by EC 59 in 2009"
  }
}
```

**Evaluation Metric**: **Change Detection Accuracy**
```python
accuracy = (correct_changes + correct_no_changes) / total_queries
```

---

#### Task 4: Causal-Lineage Reconstruction
**Goal**: Trace the complete version history of an article

**Format**:
```json
{
  "task": "causal_lineage",
  "query": "Show the complete version history of Article 214 from 1988 to 2025",
  "target_component": "tit_08_cap_03_sec_01_art_214_art_214",
  "ground_truth": {
    "version_chain": [
      {"version": 1, "date": "1988-10-05", "amendment": null},
      {"version": 2, "date": "2009-01-01", "amendment": "ec_59"},
      {"version": 3, "date": "2009-01-01", "amendment": "ec_59"},
      {"version": 4, "date": "2020-01-01", "amendment": "ec_108"}
    ],
    "total_versions": 4
  }
}
```

**Evaluation Metric**: **Causal-Chain Completeness**
```python
completeness = len(retrieved_chain ∩ ground_truth_chain) / len(ground_truth_chain)
```

---

#### Task 5: Temporal Consistency (Negative Test)
**Goal**: Correctly identify when an article has NOT been amended

**Format**:
```json
{
  "task": "temporal_consistency",
  "query": "Has Article 1 been amended since 1988?",
  "target_component": "tit_01_art_1_art_1",
  "ground_truth": {
    "amended": false,
    "versions": 1,
    "amendments": []
  }
}
```

**Evaluation Metric**: **Precision** (avoid false positives)
```python
precision = TN / (TN + FP)  # True negatives / (True negatives + False positives)
```

---

#### Task 6: Hierarchical Impact Analysis
**Goal**: Identify all articles within a constitutional section that have been amended

**Format**:
```json
{
  "task": "hierarchical_impact",
  "query": "Which articles in Title VIII have been amended since 2000?",
  "target_scope": "tit_08",
  "date_range": ["2000-01-01", "2025-01-01"],
  "ground_truth": {
    "affected_articles": [
      "tit_08_cap_03_sec_01_art_214_art_214",
      "tit_08_cap_05_art_221_inc_IV_art_222"
    ],
    "amendments": ["ec_36", "ec_59", "ec_108"],
    "total_changes": 3
  }
}
```

**Evaluation Metric**: **Article Recall**
```python
recall = # correctly identified articles / # actual affected articles
```

---

## Benchmark Dataset Specification

### Size Targets

| Task Category | # Queries | Difficulty Distribution |
|---------------|-----------|------------------------|
| Point-in-Time | 30 | Easy: 10, Medium: 15, Hard: 5 |
| Amendment Attribution | 20 | Easy: 10, Medium: 7, Hard: 3 |
| Temporal Difference | 15 | Easy: 5, Medium: 7, Hard: 3 |
| Causal-Lineage | 10 | Medium: 6, Hard: 4 |
| Temporal Consistency | 10 | All: Negative tests |
| Hierarchical Impact | 15 | Medium: 10, Hard: 5 |
| **TOTAL** | **100** | - |

### Difficulty Levels

**Easy**:
- Recent dates (2010-2025)
- Articles with 1-2 versions
- Single amendment changes

**Medium**:
- Historical dates (1990-2010)
- Articles with 3-5 versions
- Multiple amendments

**Hard**:
- Early dates (1988-1990)
- Articles with 10+ versions (e.g., ADCT Article 2: 151 versions)
- Complex amendment chains

---

## Ground Truth Verification

All ground truth derived from **Neo4j graph database queries**:

### Example Ground Truth Query
```cypher
// Verify Article 214 state in 2005
MATCH (c:Component {component_id: 'tit_08_cap_03_sec_01_art_214_art_214'})
      -[:HAS_VERSION]->(v:CTV)
WHERE v.date_start <= date('2005-01-01')
  AND (v.date_end IS NULL OR v.date_end > date('2005-01-01'))
MATCH (v)-[:EXPRESSED_IN]->(clv:CLV)-[:HAS_TEXT]->(t:TextUnit)
RETURN v.version_number AS version,
       v.date_start AS valid_from,
       v.date_end AS valid_to,
       t.full_text AS text,
       t.content_hash AS text_hash
```

**Verification Process**:
1. Generate query from template
2. Execute Cypher query to get ground truth
3. Manually review sample (10%)
4. Store in benchmark dataset with metadata

---

## Evaluation Protocol

### 1. System Under Test (SUT) Requirements

The SUT must implement a standard interface:

```python
class TemporalLegalRAG:
    def retrieve(self, query: str, target_date: date = None) -> List[Result]:
        """
        Retrieve legal text for a query, optionally at a specific date.

        Args:
            query: Natural language query
            target_date: Optional date for temporal queries

        Returns:
            List of results with text, version info, and provenance
        """
        pass
```

### 2. Evaluation Metrics

| Metric | Task | Formula | Range |
|--------|------|---------|-------|
| Temporal Precision | Point-in-Time | valid_ctvs / retrieved_ctvs | [0, 1] |
| Temporal Recall | Point-in-Time | retrieved_relevant / all_relevant | [0, 1] |
| Amendment F1 | Attribution | 2PR/(P+R) | [0, 1] |
| Causal Completeness | Lineage | correct_sequence / true_sequence | [0, 1] |
| Change Accuracy | Difference | correct / total | [0, 1] |
| Article Recall | Hierarchical | found_articles / true_articles | [0, 1] |

### 3. Aggregate Score

**TLR-Score** (Temporal Legal Reasoning Score):
```
TLR-Score = (
    0.40 × Temporal_Precision +
    0.25 × Amendment_F1 +
    0.15 × Causal_Completeness +
    0.10 × Change_Accuracy +
    0.10 × Article_Recall
)
```

Weights reflect importance of each capability for legal research.

---

## Baseline Systems

### Baseline 1: Flat-Text RAG (Current Version Only)
**Implementation**: `src/baseline/flat_rag.py`

**Characteristics**:
- Indexes current version of each article as text chunks
- Uses semantic search (embeddings)
- No temporal awareness
- No amendment tracking

**Expected Performance**:
- Temporal Precision: **0%** (always returns current version)
- Amendment F1: **0%** (no amendment data)
- TLR-Score: **≈0.15** (only performs on current-state queries)

### Baseline 2: Temporal-Naive RAG
**Implementation**: Stores all versions as flat chunks, but no temporal filtering

**Characteristics**:
- Indexes ALL versions as separate chunks
- Uses semantic search
- No date-based filtering
- May return wrong version

**Expected Performance**:
- Temporal Precision: **10-20%** (random chance of getting right version)
- Amendment F1: **0%** (no amendment data)
- TLR-Score: **≈0.25**

### Baseline 3: SAT-Graph-RAG
**Implementation**: Full temporal graph with aggregation model

**Expected Performance**:
- Temporal Precision: **95-100%**
- Amendment F1: **80-95%**
- TLR-Score: **≈0.85-0.95**

---

## Benchmark Generation

### Automated Query Generation

```python
def generate_point_in_time_queries(
    graph: Neo4jGraph,
    n_queries: int = 30
) -> List[BenchmarkQuery]:
    """
    Generate point-in-time queries from graph data.

    Strategy:
    1. Find articles with multiple versions (2+)
    2. For each article, sample dates from its version ranges
    3. Generate query template
    4. Retrieve ground truth from graph
    5. Validate ground truth is correct
    """

    queries = []

    # Get articles with version history
    articles = graph.query("""
        MATCH (c:Component)-[:HAS_VERSION]->(v:CTV)
        WHERE c.component_type = 'article'
        WITH c, count(v) AS version_count
        WHERE version_count > 1
        RETURN c.component_id, version_count
        ORDER BY version_count DESC
        LIMIT 50
    """)

    for article in articles:
        component_id = article['component_id']

        # Get version history
        versions = graph.query(f"""
            MATCH (c:Component {{component_id: '{component_id}'}})
                  -[:HAS_VERSION]->(v:CTV)
            RETURN v.version_number, v.date_start, v.date_end
            ORDER BY v.version_number
        """)

        # Sample dates from each version range
        for version in versions:
            target_date = sample_date_from_range(
                version['date_start'],
                version['date_end']
            )

            # Generate query
            query = BenchmarkQuery(
                task="point_in_time",
                query=f"What did {get_article_name(component_id)} say on {target_date}?",
                target_date=target_date,
                target_component=component_id,
                ground_truth=get_ground_truth(graph, component_id, target_date)
            )

            queries.append(query)

    return queries[:n_queries]
```

---

## Usage

### 1. Generate Benchmark Dataset
```bash
python scripts/generate_benchmark.py --output data/benchmark/tlr_bench_v1.json
```

### 2. Evaluate System
```bash
python scripts/evaluate_benchmark.py \
    --system sat_graph_rag \
    --benchmark data/benchmark/tlr_bench_v1.json \
    --output results/sat_graph_rag_results.json
```

### 3. Compare Systems
```bash
python scripts/compare_systems.py \
    --systems baseline,sat_graph_rag \
    --benchmark data/benchmark/tlr_bench_v1.json \
    --output results/comparison.html
```

---

## Benchmark Versioning

**Current Version**: TLR-Bench v1.0 (2026-01-21)

**Data Source**:
- Brazilian Federal Constitution (1988-2025)
- 137 constitutional amendments
- 4,195 components, 6,284 temporal versions

**Future Versions**:
- v1.1: Add Portuguese-language queries
- v2.0: Expand to federal laws (not just constitution)
- v3.0: Multi-jurisdictional (US, EU constitutions)

---

## Reproducibility

All benchmark data, evaluation scripts, and results are open source:

**Repository**: `sat-graph-rag/data/benchmark/`
**Format**: JSON (queries + ground truth)
**License**: MIT

**Citation**:
```bibtex
@dataset{tlr_bench_2026,
  title={Temporal Legal Reasoning Benchmark (TLR-Bench)},
  author={SAT-Graph-RAG Team},
  year={2026},
  publisher={GitHub},
  url={https://github.com/.../sat-graph-rag}
}
```

---

## Comparison to Existing Benchmarks

| Benchmark | Domain | Temporal? | Size | Focus |
|-----------|--------|-----------|------|-------|
| **LegalBench** | US Law | ❌ | 162 tasks | Legal reasoning |
| **CUAD** | Contracts | ❌ | 13K clauses | Contract review |
| **CaseHOLD** | Case law | ❌ | 53K cases | Outcome prediction |
| **LexGLUE** | EU Law | ❌ | 11 tasks | Legal NLU |
| **TLR-Bench** | Brazilian Constitution | ✅ | 100 queries | **Temporal reasoning** |

**Key Difference**: TLR-Bench is the **only benchmark** testing temporal reasoning in legal RAG systems.

---

## Next Steps

1. ✅ Specification complete
2. ⏳ Implement benchmark generator (`scripts/generate_benchmark.py`)
3. ⏳ Generate TLR-Bench v1.0 dataset (100 queries)
4. ⏳ Run full evaluation on SAT-Graph-RAG vs Baseline
5. ⏳ Publish results and dataset
