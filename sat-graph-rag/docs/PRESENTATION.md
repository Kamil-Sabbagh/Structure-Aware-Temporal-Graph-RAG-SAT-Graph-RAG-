# 🏛️ SAT-Graph-RAG: Ontology-Driven Graph RAG for Legal Norms

## A Structural, Temporal, and Deterministic Approach for the Brazilian Federal Constitution

---

## 📋 Project Overview

**SAT-Graph-RAG** is an implementation of an ontology-driven Graph RAG (Retrieval-Augmented Generation) system specifically designed for legal documents, focusing on the **Brazilian Federal Constitution (CF1988)**.

### Key Innovation: "Aggregation, Not Composition"

Unlike traditional RAG systems that treat documents as flat text, SAT-Graph-RAG:
- Preserves the **hierarchical structure** of legal documents
- Supports **temporal versioning** (time-travel queries)
- Uses the **LRMoo ontology** for legal document modeling

---

## 🎯 What We Built

### Phase 0: Project Setup ✅
- Python 3.10+ environment with dependencies
- Docker-based Neo4j 5.15 with APOC plugin
- Configuration management with `.env`

### Phase 1: Data Acquisition ✅
- Web scraper for Planalto government website
- Downloaded Brazilian Constitution (main + compiled versions)
- Fetched all **137 Constitutional Amendments** (EC 1-137)

### Phase 2: Structural Parsing ✅
- Hierarchical parser using Pydantic models
- Extracted **4,195 components** from the constitution
- Detected amendment markers (Incluído, Redação, Revogado)

### Phase 3: Graph Schema ✅
- Implemented LRMoo-inspired ontology in Neo4j
- 6 node types: Norm, Component, CTV, CLV, TextUnit, Action
- 7 relationship types including the key `AGGREGATES` relationship

### Phase 4: Ingestion Pipeline ✅
- Loaded full constitution into Neo4j
- Created **19,868 relationships**
- Built interactive visualization

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| **Total Components** | 3,893 |
| **Relationships** | 19,868 |
| **Temporal Versions (CTVs)** | 3,893 |
| **Amendments Processed** | 137 |
| **Unit Tests** | 57 passing |
| **Integration Tests** | 27 passing |

### Component Breakdown

| Type | Count | Description |
|------|-------|-------------|
| 🔵 Title | 9 | TÍTULO I-IX |
| 🟢 Chapter | 35 | CAPÍTULO I, II, etc. |
| 🟣 Section | 52 | Seção I, II, etc. |
| 🟠 Article | 556 | Art. 1º, Art. 2º, etc. |
| 🟢 Paragraph | 1,253 | §1º, §2º, etc. |
| 🟠 Item | 1,596 | I, II, III, etc. |
| ⚪ Letter | 387 | a), b), c), etc. |

---

## 🖼️ Screenshots

### Demo View (45 Nodes)
![Demo View](./demo_view_description.png)

The demo view shows the high-level structure:
- **Red center node**: Constitution (root)
- **Blue nodes**: 9 Titles (TÍTULO I-IX)
- **Green nodes**: 35 Chapters (CAPÍTULO)

### Full View (197 Nodes)
![Full View](./full_view_description.png)

The full view includes:
- All Titles, Chapters, and Sections
- 100 Articles with their connections
- Purple "FULL" badge indicating mode

---

## 🔧 Technical Architecture

### Graph Schema (LRMoo-Inspired)

```
                    NORM (Constitution)
                         │
                   [:HAS_COMPONENT]
                         │
                    COMPONENT (Article 5)
                         │
                    [:HAS_VERSION]
                         │
                       CTV (Temporal Version)
                         │
                   [:EXPRESSED_IN]
                         │
                       CLV (Language Version)
                         │
                     [:HAS_TEXT]
                         │
                    TEXTUNIT (Actual Text)
```

### Key Relationship: AGGREGATES

The `AGGREGATES` relationship enables the paper's key innovation:

```
Chapter_v2 ──AGGREGATES──> Article_v1 (REUSED - unchanged)
           ──AGGREGATES──> Article_v2 (NEW - changed)
           ──AGGREGATES──> Article_v1 (REUSED - unchanged)
```

When an amendment changes only Article 5:
- ❌ **Wrong**: Create new versions for ALL components
- ✅ **Right**: Create new version for Article 5 + ancestors, REUSE unchanged siblings

---

## 🚀 How to Run

### 1. Start Neo4j
```bash
cd sat-graph-rag/docker
docker-compose up -d
```

### 2. Load Constitution
```bash
cd sat-graph-rag
source .venv/bin/activate
python -c "from src.graph.loader import load_constitution; load_constitution()"
```

### 3. Export Visualization Data
```bash
# Demo mode (fast, 45 nodes)
python scripts/export_graph_for_viz.py --demo

# Full mode (197 nodes)
python scripts/export_graph_for_viz.py --max-articles 100
```

### 4. View Visualization
```bash
cd visualization
python -m http.server 8888
# Open http://localhost:8888
```

---

## 🎨 Visualization Features

### Interactive Controls
- **Search**: Find components by name
- **Zoom/Pan**: Navigate the graph
- **Physics Toggle**: Enable/disable force simulation
- **Click nodes**: View component details

### Loading Progress
- Progress bar showing stabilization percentage
- Iteration counter during physics simulation
- Mode badge (DEMO/FULL)

---

## 📁 Project Structure

```
sat-graph-rag/
├── src/
│   ├── collection/     # Web scraping
│   ├── parser/         # Structural parsing
│   ├── graph/          # Neo4j operations
│   └── rag/            # (Future) RAG queries
├── data/
│   ├── raw/            # Downloaded HTML
│   └── intermediate/   # Parsed JSON
├── visualization/      # Interactive HTML viz
├── tests/              # Unit & integration tests
└── docker/             # Neo4j container
```

---

## 🔮 Next Steps

### Remaining Phases
- **Phase 5**: Retrieval Engine (semantic search + graph traversal)
- **Phase 6**: Time-Travel Queries (query law at any historical date)
- **Phase 7**: RAG Integration (LLM-powered Q&A)

### Future Features
- Embeddings for semantic similarity search
- Temporal queries ("What was Article 5 in 2010?")
- Natural language Q&A interface

---

## 📚 References

- **Paper**: "An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach"
- **LRMoo**: Library Reference Model - object oriented (ISO/IEC)
- **Data Source**: [Planalto.gov.br](https://www.planalto.gov.br/ccivil_03/constituicao/)



