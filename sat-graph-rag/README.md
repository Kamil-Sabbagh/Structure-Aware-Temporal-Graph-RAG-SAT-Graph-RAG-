# SAT-Graph RAG

**Structure-Aware Temporal Graph RAG for Legal Norms**

An ontology-driven Graph RAG system for legal norms supporting hierarchical structure preservation, temporal versioning (time-travel queries), and deterministic retrieval.

Based on the paper: *"An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach"* (arXiv:2505.00039)

## Target Domain

Brazilian Federal Constitution (1988) - Case Study

## Features

- **Hierarchical Structure Preservation**: Maintains the legal document hierarchy (Titles, Chapters, Sections, Articles, etc.)
- **Temporal Versioning**: Track amendments and query the law at any point in time
- **Deterministic Retrieval**: Structure-aware retrieval that respects legal document organization
- **LRMoo-Inspired Schema**: Work Level (Norm, Component) and Expression Level (TemporalVersion, TextUnit)

## Project Structure

```
sat-graph-rag/
├── data/                    # Data storage
│   ├── raw/                 # Original HTML files
│   ├── intermediate/        # Parsed JSON hierarchy
│   └── embeddings/          # Vector store data
├── docker/                  # Docker configuration
│   └── docker-compose.yml   # Neo4j service
├── docs/                    # Documentation
├── src/                     # Source code
│   ├── collection/          # Web scraping
│   ├── parser/              # Structural parsing
│   ├── graph/               # Neo4j operations
│   ├── rag/                 # Retrieval logic
│   ├── api/                 # REST API
│   └── utils/               # Utilities
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
└── modal_app/               # Modal serverless (optional)
```

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd sat-graph-rag

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start Neo4j

```bash
cd docker
docker-compose up -d

# Wait for Neo4j to be ready (about 30 seconds)
# Access Neo4j Browser at http://localhost:7474
# Default credentials: neo4j / satgraphrag123
```

### 3. Verify Setup

```bash
# Run setup validation tests
pytest tests/unit/test_setup.py -v

# Run Neo4j connection test (requires running Neo4j)
pytest tests/integration/test_neo4j_connection.py -v
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Graph Database | Neo4j + APOC |
| Language | Python 3.10+ |
| Compute | Modal (optional) |
| Parsing | BeautifulSoup4, Pydantic |
| Embeddings | OpenAI |
| LLM | OpenAI GPT-4 / Anthropic Claude |
| API | FastAPI |

## Key Concepts

### Aggregation vs Composition
- **Composition**: Parent contains children (copying)
- **Aggregation**: Parent references children (sharing)
- Uses **aggregation** to avoid redundant node creation on amendments

### LRMoo-Inspired Schema
- **Work Level (Abstract)**: `Norm`, `Component` - What the law IS
- **Expression Level (Concrete)**: `TemporalVersion`, `LanguageVersion`, `TextUnit` - How it's expressed at a point in time

### Component Temporal Version (CTV)
- Each component has multiple temporal versions
- Versions have `date_start`, `date_end`, `is_active`
- Parent CTVs aggregate child CTVs

### Time-Travel Query
- Given a date, reconstruct the exact state of the law
- Traverse from Norm → valid CTV → aggregated child CTVs → TextUnits

## Source URLs

| Resource | URL |
|----------|-----|
| Constitution (Current) | https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm |
| Constitution (Compiled) | https://www.planalto.gov.br/ccivil_03/constituicao/ConstituicaoCompilado.htm |
| Amendments List | https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm |

## Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Format code
ruff format .

# Lint code
ruff check .
```

## License

MIT License

## References

- Paper: arXiv:2505.00039
- Brazilian Federal Constitution: Planalto.gov.br

