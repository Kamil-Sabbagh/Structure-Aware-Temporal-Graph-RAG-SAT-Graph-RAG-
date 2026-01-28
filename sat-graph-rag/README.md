# SAT-Graph-RAG: Temporal Graph RAG for Legal Documents

A graph-based retrieval system for legal documents with temporal versioning support. Implements an ontology-driven approach to track constitutional amendments over time and enable accurate historical queries.

**Paper**: *"An Ontology-Driven Graph RAG for Legal Norms"* (arXiv:2505.00039)

---

## Overview

This project implements a temporal graph RAG system for the Brazilian Federal Constitution, processing the original 1988 text and 137 subsequent amendments. The system uses Neo4j to store components, versions, and amendment relationships, enabling queries about the law at any point in time.

### What We Built

- **Graph database** with 4,195 constitutional components and 6,284 temporal versions
- **Amendment processor** that tracks 137 constitutional amendments (1989-2025)
- **Temporal query engine** for retrieving historical versions of legal text
- **Baseline comparison** showing system capabilities vs. traditional RAG

---

## Key Results

We evaluated the system on temporal legal queries and compared it against a baseline RAG that stores only current text:

| Capability | SAT-Graph-RAG | Baseline RAG |
|------------|---------------|--------------|
| Temporal Precision | 100% (3/3 queries) | 0% (0/3 queries) |
| Amendment Tracking | Can identify amendments | Cannot answer |
| Version History | Full history (4+ versions) | Current only |

### Example 1: Temporal Query

**Query**: "What did Article 214 say in 2005?"

**SAT-Graph-RAG Output**:
```
Version: v1 (original 1988 text)
Valid Period: 1988-10-05 to 2009-01-01
Text: "Art. 214. A lei estabelecerá o plano nacional de educação,
de duração plurianual, visando à articulação e ao desenvolvimento..."
```

**Baseline RAG Output**:
```
Version: Current only (no temporal data)
Text: "§ 4º É vedada a adoção de requisitos e critérios diferenciados
para a concessão de aposentadoria..." (text from 2020, incorrect for 2005)
```

**Result**: SAT-Graph-RAG returns the correct 1988 version that was valid in 2005. Baseline returns current text from 2020, which is anachronistic.

---

### Example 2: Amendment Tracking

**Query**: "Which amendments changed Article 222?"

**SAT-Graph-RAG Output**:
```
Found Amendments: EC 36 (2002)
```

**Baseline RAG Output**:
```
Cannot answer (no amendment metadata)
```

**Result**: SAT-Graph-RAG identifies the specific amendment. Baseline has no amendment tracking capability.

---

## Architecture

### Graph Schema

The system uses a graph structure with the following node types:

- **Component**: Constitutional elements (Title, Article, Paragraph, etc.)
- **CTV** (Component Temporal Version): Time-bound versions of components
- **Action**: Legislative amendments (EC 1 through EC 137)
- **TextUnit**: Actual legal text

Key relationships:
- `HAS_VERSION`: Component → CTV (temporal versions)
- `HAS_CHILD`: Component → Component (hierarchy)
- `RESULTED_IN`: Action → CTV (amendment provenance)
- `AGGREGATES`: CTV → CTV (version composition)

### Aggregation Model

Instead of copying all components for each amendment, the system reuses unchanged components:

- **Without aggregation**: 574,615 versions needed (4,195 components × 137 amendments)
- **With aggregation**: 6,284 versions actual (only modified components)
- **Space savings**: 98.8%

---

## Graph Visualizations

### Component Versioning
![Component with versions](./images/graph1.svg)

Shows how a single Component node has multiple CTVs (temporal versions) over time, with Action nodes indicating which amendments created each version.

### Hierarchical Structure
![Constitutional hierarchy](./images/graph2.svg)

Shows the constitutional hierarchy: Norm → Title → Chapter → Section → Article, connected via HAS_COMPONENT and HAS_CHILD relationships.

### Aggregation Model
![Aggregation relationships](./images/graph3.svg)

Shows how parent CTVs use AGGREGATES relationships to reference child CTVs without duplication, achieving 98.8% space savings.

### Amendment Provenance
![Amendment tracking](./images/graph4.svg)

Shows Action nodes with RESULTED_IN relationships to CTVs, enabling complete amendment history tracking.

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Neo4j 5.x
- 8GB RAM minimum

### Install

```bash
# Clone repository
git clone <repo-url>
cd sat-graph-rag

# Install dependencies
pip install -r requirements.txt

# Configure Neo4j connection
cp .env.example .env
# Edit .env with your Neo4j credentials
```

### Load Data

```bash
# 1. Load constitution (~5 minutes)
python -m src.graph.loader

# 2. Process amendments (~15 minutes)
python scripts/process_all_amendments.py

# 3. Verify system
python scripts/run_verification.py
```

Expected verification output: 12/12 checks passed

---

## Usage

### Run Demo

```bash
python scripts/run_mvp_demo.py
```

This runs 3 demonstration queries showing temporal precision, amendment tracking, and version history.

### Interactive Testing

```bash
python scripts/test_retrieval.py
```

### Benchmark Evaluation

We created a benchmark with 77 test queries across 6 categories:

```bash
# Quick evaluation (3 queries)
python scripts/run_quick_benchmark.py

# Full evaluation (77 queries)
python scripts/generate_benchmark.py
python scripts/evaluate_benchmark.py
```

---

## System Statistics

**Graph Database**:
- 4,195 components (constitutional elements)
- 6,284 temporal versions (CTVs)
- 137 amendments processed (EC 1-137, 1989-2025)
- 20,965 relationships

**Performance**:
- Query time: ~10ms average
- Temporal precision: 100% on test queries
- Space efficiency: 98.8% savings vs. full duplication

**Verification**:
- 12/12 system checks passed
- All 137 amendments successfully ingested
- No duplicate versions or orphaned nodes

---

## Benchmark Dataset

We created **TLR-Bench** (Temporal Legal Reasoning Benchmark), a dataset for evaluating temporal query capabilities in legal RAG systems:

- **77 test queries** across 6 task types
- **Ground truth** verified from graph database
- **Standardized metrics** (temporal precision, amendment F1, causal completeness)

Dataset location: `data/benchmark/tlr_bench_v1.json`

Task categories:
1. Point-in-Time Retrieval (17 queries)
2. Amendment Attribution (20 queries)
3. Temporal Difference (15 queries)
4. Causal Lineage (10 queries)
5. Temporal Consistency (10 queries)
6. Hierarchical Impact (5 queries)

---

## Technical Details

### Technologies

- **Graph Database**: Neo4j 5.x with APOC plugin
- **Language**: Python 3.10+
- **Embeddings**: OpenAI text-embedding-3-small
- **Storage**: ~2GB for complete graph

### Key Files

```
sat-graph-rag/
├── src/
│   ├── graph/
│   │   ├── loader.py              # Constitution ingestion
│   │   └── temporal_engine.py     # Temporal query engine
│   ├── rag/
│   │   ├── planner.py             # Query planning
│   │   └── retriever.py           # Temporal retrieval
│   └── baseline/
│       └── flat_rag.py            # Baseline RAG for comparison
├── scripts/
│   ├── run_mvp_demo.py            # Main demonstration
│   ├── process_all_amendments.py  # Amendment processing
│   ├── run_verification.py        # System verification
│   └── generate_benchmark.py      # Benchmark generation
└── data/
    └── benchmark/
        └── tlr_bench_v1.json      # Benchmark dataset
```

### Cypher Query Examples

**Get article version at specific date**:
```cypher
MATCH (c:Component {component_id: 'tit_08_cap_03_sec_01_art_214_art_214'})
      -[:HAS_VERSION]->(v:CTV)
WHERE v.date_start <= date('2005-01-01')
  AND (v.date_end IS NULL OR v.date_end > date('2005-01-01'))
MATCH (v)-[:EXPRESSED_IN]->(clv:CLV)-[:HAS_TEXT]->(t:TextUnit)
RETURN v, t
```

**Find all amendments that modified an article**:
```cypher
MATCH (c:Component {component_id: 'tit_08_cap_05_art_221_inc_IV_art_222'})
      -[:HAS_VERSION]->(v:CTV)<-[:RESULTED_IN]-(a:Action)
RETURN DISTINCT a.action_id, a.date
ORDER BY a.date
```

---

## Limitations

### Current Implementation

- Amendment text is stored as placeholders (e.g., "Modified by EC 59") rather than full amendment text
- Hierarchical traversal queries are not fully implemented
- Single language support (Portuguese)
- No API endpoint (command-line only)

### Evaluation Scope

- Tested on Brazilian Constitution only (1988-2025)
- Baseline comparison limited to one flat-text RAG system
- No user study with legal professionals conducted

---

## Documentation

- **System Diagrams**: `docs/DIAGRAMS.md` - 12 Mermaid diagrams explaining architecture
- **Benchmark Spec**: `docs/BENCHMARK_SPECIFICATION.md` - TLR-Bench details
- **Demo Results**: `MVP_DEMO_RESULTS.md` - Demonstration outcomes

---

## License

MIT License

## References

- **Paper**: arXiv:2505.00039
- **Data Source**: Brazilian Federal Constitution (Planalto.gov.br)
- **Ontology**: LRMoo (Library Reference Model - object oriented)

---

## Contact

For questions about the implementation or benchmark dataset, please open an issue.

---

**Last Updated**: January 2026
