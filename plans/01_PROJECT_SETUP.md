# Phase 0: Project Setup

## Objective
Establish a clean, modular environment for the SAT-Graph RAG pipeline.

---

## 0.1 Repository Structure

Create the following directory structure:

```
sat-graph-rag/
├── data/
│   ├── raw/                    # Original HTML files from Planalto
│   │   ├── constitution/       # Main constitution HTML
│   │   └── amendments/         # Individual amendment HTMLs
│   ├── intermediate/           # Parsed JSON hierarchy
│   │   ├── constitution.json   # Full parsed structure
│   │   └── amendments/         # Parsed amendment data
│   └── embeddings/             # Vector store data
├── docker/
│   ├── docker-compose.yml      # Neo4j service
│   └── neo4j/
│       ├── conf/               # Neo4j configuration
│       └── plugins/            # APOC plugin JAR
├── docs/
│   ├── schema.md               # Graph schema documentation
│   ├── api_reference.md        # API documentation
│   └── diagrams/               # Architecture diagrams
├── src/
│   ├── __init__.py
│   ├── collection/             # Web scraping
│   │   ├── __init__.py
│   │   ├── scraper.py          # Main scraper class
│   │   ├── fetch_constitution.py
│   │   └── fetch_amendments.py
│   ├── parser/                 # Structural parsing
│   │   ├── __init__.py
│   │   ├── legal_parser.py     # Hierarchical parser
│   │   ├── amendment_parser.py # Amendment metadata extraction
│   │   └── models.py           # Pydantic models
│   ├── graph/                  # Neo4j operations
│   │   ├── __init__.py
│   │   ├── connection.py       # Database connection
│   │   ├── schema.py           # Schema constraints
│   │   ├── loader.py           # Initial load
│   │   ├── temporal_engine.py  # Amendment handling
│   │   └── queries.py          # Cypher query builders
│   ├── rag/                    # Retrieval logic
│   │   ├── __init__.py
│   │   ├── embeddings.py       # Embedding generation
│   │   ├── planner.py          # Query classification
│   │   ├── retriever.py        # Graph + vector retrieval
│   │   └── generator.py        # LLM response generation
│   ├── api/                    # REST API
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app
│   │   └── routes/
│   │       ├── query.py        # Query endpoints
│   │       └── admin.py        # Admin endpoints
│   └── utils/
│       ├── __init__.py
│       ├── dates.py            # Date parsing utilities
│       └── text.py             # Text processing utilities
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_temporal_engine.py
│   │   └── test_queries.py
│   ├── integration/
│   │   ├── test_scraping.py
│   │   ├── test_ingestion.py
│   │   └── test_time_travel.py
│   └── fixtures/
│       ├── sample_article.html
│       └── sample_amendment.html
├── scripts/
│   ├── setup_neo4j.sh          # Neo4j initialization
│   ├── run_scraper.py          # Scraping script
│   ├── run_ingestion.py        # Full ingestion
│   └── run_api.py              # Start API server
├── modal_app/                  # Modal serverless (optional)
│   ├── __init__.py
│   ├── embeddings.py           # Batch embedding job
│   └── ingestion.py            # Large-scale ingestion
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 0.2 Dependencies

### requirements.txt

```txt
# Core
python-dotenv>=1.0.0
pydantic>=2.0.0

# Web Scraping
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# Graph Database
neo4j>=5.0.0

# Embeddings & LLM
openai>=1.0.0
tiktoken>=0.5.0

# API
fastapi>=0.100.0
uvicorn>=0.23.0

# Utilities
python-dateutil>=2.8.0
tqdm>=4.65.0

# Testing
pytest>=7.0.0
pytest-asyncio>=0.21.0

# Optional: Modal
modal>=0.50.0
```

### pyproject.toml

```toml
[project]
name = "sat-graph-rag"
version = "0.1.0"
description = "Structure-Aware Temporal Graph RAG for Legal Norms"
requires-python = ">=3.10"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I"]
```

---

## 0.3 Environment Configuration

### .env.example

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# OpenAI (for embeddings and LLM)
OPENAI_API_KEY=sk-...

# Optional: Alternative embedding model
EMBEDDING_MODEL=text-embedding-3-small

# Optional: Modal
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...

# Scraping
SCRAPE_DELAY_SECONDS=1.0
USER_AGENT=SAT-Graph-RAG-Research/1.0
```

---

## 0.4 Docker Configuration

### docker/docker-compose.yml

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.15.0-community
    container_name: sat-graph-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/satgraphrag123
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
      - NEO4J_apoc_import_file_use__neo4j__config=true
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./neo4j/plugins:/plugins
      - ./neo4j/import:/var/lib/neo4j/import

volumes:
  neo4j_data:
  neo4j_logs:
```

---

## 0.5 Setup Tasks

### Task 0.5.1: Create Directory Structure

```bash
# Run from project root
mkdir -p sat-graph-rag/{data/{raw/{constitution,amendments},intermediate/amendments,embeddings},docker/neo4j/{conf,plugins},docs/diagrams,src/{collection,parser,graph,rag,api/routes,utils},tests/{unit,integration,fixtures},scripts,modal_app}

# Create __init__.py files
find sat-graph-rag/src -type d -exec touch {}/__init__.py \;
touch sat-graph-rag/tests/__init__.py
touch sat-graph-rag/modal_app/__init__.py
```

### Task 0.5.2: Initialize Git

```bash
cd sat-graph-rag
git init

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
*.egg

# Environment
.env
.venv/
venv/
env/

# IDE
.idea/
.vscode/
*.swp

# Data (large files)
data/raw/
data/embeddings/
*.pkl

# Neo4j
docker/neo4j/plugins/*.jar

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db
EOF
```

### Task 0.5.3: Start Neo4j

```bash
cd docker
docker-compose up -d

# Wait for Neo4j to be ready
sleep 30

# Verify connection
docker exec sat-graph-neo4j cypher-shell -u neo4j -p satgraphrag123 "RETURN 1 AS test"
```

---

## 0.6 Validation Checks

### Check 0.6.1: Directory Structure Exists

```bash
# Verify all directories exist
test -d sat-graph-rag/src/collection && echo "✓ collection dir"
test -d sat-graph-rag/src/parser && echo "✓ parser dir"
test -d sat-graph-rag/src/graph && echo "✓ graph dir"
test -d sat-graph-rag/src/rag && echo "✓ rag dir"
test -d sat-graph-rag/data/raw && echo "✓ data/raw dir"
test -d sat-graph-rag/tests && echo "✓ tests dir"
```

### Check 0.6.2: Python Environment

```python
# tests/unit/test_setup.py
import sys
import importlib

def test_python_version():
    assert sys.version_info >= (3, 10), "Python 3.10+ required"

def test_dependencies_installed():
    required = [
        "requests",
        "bs4",
        "neo4j",
        "pydantic",
        "fastapi",
        "openai",
    ]
    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            raise AssertionError(f"Missing package: {pkg}")
```

### Check 0.6.3: Neo4j Connection

```python
# tests/integration/test_neo4j_connection.py
from neo4j import GraphDatabase
import os

def test_neo4j_connection():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "satgraphrag123")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        result = session.run("RETURN 1 AS test")
        record = result.single()
        assert record["test"] == 1
    
    driver.close()

def test_apoc_installed():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "satgraphrag123")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        result = session.run("RETURN apoc.version() AS version")
        record = result.single()
        assert record["version"] is not None, "APOC not installed"
    
    driver.close()
```

---

## 0.7 Success Criteria

| Criterion | Validation |
|-----------|------------|
| Directory structure matches spec | `ls -R` shows all required dirs |
| Python 3.10+ installed | `python --version` returns 3.10+ |
| All dependencies installed | `pip list` shows all required packages |
| Neo4j running and accessible | Connection test passes |
| APOC plugin installed | `apoc.version()` returns version |
| Environment variables configured | `.env` file exists with valid values |

---

## 0.8 Troubleshooting

### Neo4j Won't Start
```bash
# Check logs
docker logs sat-graph-neo4j

# Common fix: Remove old data
docker-compose down -v
docker-compose up -d
```

### APOC Not Found
```bash
# Download APOC manually
curl -L https://github.com/neo4j/apoc/releases/download/5.15.0/apoc-5.15.0-core.jar \
  -o docker/neo4j/plugins/apoc-5.15.0-core.jar

docker-compose restart neo4j
```

### Permission Denied on Data Dir
```bash
chmod -R 755 data/
```

---

## 0.9 Phase Completion Checklist

- [ ] Directory structure created
- [ ] `pyproject.toml` and `requirements.txt` created
- [ ] `.env` file configured
- [ ] Virtual environment created and activated
- [ ] All dependencies installed
- [ ] Docker Compose file created
- [ ] Neo4j container running
- [ ] APOC plugin verified
- [ ] All validation checks pass
- [ ] Git repository initialized

**Next Phase:** `02_DATA_ACQUISITION.md`

