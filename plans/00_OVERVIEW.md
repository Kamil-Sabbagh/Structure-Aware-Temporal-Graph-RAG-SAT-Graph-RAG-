# SAT-Graph RAG Replication Plan - Overview

## Project Summary

**Objective:** Replicate an ontology-driven Graph RAG system for legal norms supporting:
- Hierarchical structure preservation
- Temporal versioning (time-travel queries)
- Deterministic retrieval

**Reference Paper:** "An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach" (arXiv:2505.00039)

**Target Domain:** Brazilian Federal Constitution (1988) - Case Study

---

## Phase Index

| Phase | File | Description | Dependencies |
|-------|------|-------------|--------------|
| 0 | `01_PROJECT_SETUP.md` | Repository structure, environment, dependencies | None |
| 1 | `02_DATA_ACQUISITION.md` | Web scraping and data collection | Phase 0 |
| 2 | `03_STRUCTURAL_PARSING.md` | Hierarchical parsing of legal text | Phase 1 |
| 3 | `04_GRAPH_SCHEMA.md` | Neo4j ontology implementation (LRMoo-inspired) | Phase 0 |
| 4 | `05_INGESTION_PIPELINE.md` | SAT logic for graph population | Phases 2, 3 |
| 5 | `06_RETRIEVAL_ENGINE.md` | RAG with temporal queries | Phases 4 |
| 6 | `07_VERIFICATION.md` | End-to-end validation and testing | All |

---

## Execution Order

```
Phase 0 (Setup)
     │
     ├──────────────────┐
     ▼                  ▼
Phase 1 (Scraping)  Phase 3 (Schema)
     │                  │
     ▼                  │
Phase 2 (Parsing)       │
     │                  │
     └────────┬─────────┘
              ▼
       Phase 4 (Ingestion)
              │
              ▼
       Phase 5 (RAG)
              │
              ▼
       Phase 6 (Verification)
```

---

## Tech Stack

| Component | Technology | Reason |
|-----------|------------|--------|
| Graph Database | Neo4j + APOC | Deep traversals, temporal queries |
| Language | Python 3.10+ | Ecosystem, Neo4j drivers |
| Compute | Modal (optional) | Scalable serverless for heavy tasks |
| Parsing | BeautifulSoup4, Regex, Pydantic | HTML parsing, validation |
| Embeddings | OpenAI/HuggingFace | Vector representations |
| LLM | OpenAI GPT-4 / Anthropic Claude | Generation step |
| API | FastAPI | REST endpoints |

---

## Key Concepts from Paper

### 1. Aggregation vs Composition
- **Composition:** Parent contains children (copying)
- **Aggregation:** Parent references children (sharing)
- Paper uses **aggregation** to avoid redundant node creation on amendments

### 2. LRMoo-Inspired Schema
- **Work Level (Abstract):** `Norm`, `Component` - What the law IS
- **Expression Level (Concrete):** `TemporalVersion`, `LanguageVersion`, `TextUnit` - How it's expressed at a point in time

### 3. Component Temporal Version (CTV)
- Each component has multiple temporal versions
- Versions have `date_start`, `date_end`, `is_active`
- Parent CTVs aggregate child CTVs

### 4. Time-Travel Query
- Given a date, reconstruct the exact state of the law
- Traverse from Norm → valid CTV → aggregated child CTVs → TextUnits

---

## Validation Philosophy

Each phase has:
1. **Inputs:** What it receives
2. **Processing:** What it does
3. **Outputs:** What it produces
4. **Checks:** Automated validations
5. **Success Criteria:** How to know it worked

---

## Quick Start for Agent

```bash
# 1. Read phases in order
# 2. Execute each phase's tasks
# 3. Run each phase's checks before proceeding
# 4. Document any deviations in phase notes
```

---

## Source URLs

| Resource | URL |
|----------|-----|
| Constitution (Current) | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` |
| Constitution (Compiled) | `https://www.planalto.gov.br/ccivil_03/constituicao/ConstituicaoCompilado.htm` |
| Amendments List | `https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm` |
| Individual Amendment | `https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/emc{N}.htm` |

---

## Notes

- All file paths are relative to project root `sat-graph-rag/`
- Modal can be used for compute-intensive tasks (embeddings, large ingestion)
- Each phase should be completed and validated before moving to dependent phases

