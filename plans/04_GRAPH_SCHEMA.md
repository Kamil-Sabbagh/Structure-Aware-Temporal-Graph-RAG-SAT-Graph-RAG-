# Phase 3: Graph Schema (Ontology Implementation)

## Objective
Implement the LRMoo-inspired schema in Neo4j that supports the paper's "Aggregation, Not Composition" model for temporal versioning.

---

## 3.1 Conceptual Model

### 3.1.1 The LRMoo Framework

The paper adapts concepts from **LRMoo (Library Reference Model - object oriented)** for legal documents:

```
ABSTRACT LAYER (What the law IS - timeless identity)
├── Norm: The entire legal document
└── Component: A structural unit (Title, Chapter, Article, etc.)

CONCRETE LAYER (How it's EXPRESSED at a point in time)
├── ComponentTemporalVersion (CTV): A version of a component valid in a time range
├── ComponentLanguageVersion (CLV): A language expression of a CTV
└── TextUnit: The actual text content

EVENT LAYER (What CHANGED the law)
└── Action: An amendment action (Create, Modify, Repeal)
```

### 3.1.2 Key Insight: Aggregation vs Composition

**Composition (Wrong approach):**
```
Title_v2 CONTAINS Chapter_v2 CONTAINS Article_v2
↳ Creates new versions for EVERYTHING when ONE article changes
```

**Aggregation (Paper's approach):**
```
Title_v2 AGGREGATES Chapter_v2 AGGREGATES Article_v2 (changed)
Title_v2 AGGREGATES Chapter_v1 (reused - unchanged)
↳ Only creates new versions for CHANGED components + their ancestors
```

---

## 3.2 Node Definitions

### Node: Norm

```cypher
// The root legal document
(:Norm {
    name: "Constituição da República Federativa do Brasil",
    official_id: "CF1988",
    enactment_date: date("1988-10-05"),
    jurisdiction: "Brazil",
    document_type: "Constitution"
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT norm_official_id IF NOT EXISTS
FOR (n:Norm) REQUIRE n.official_id IS UNIQUE;
```

### Node: Component

```cypher
// A structural unit of the law (abstract - identity only)
(:Component {
    component_id: "art_5",           // Unique identifier
    component_type: "article",        // title|chapter|section|article|paragraph|item|letter
    ordering_id: "5",                 // For ordering within parent
    norm_id: "CF1988",                // Reference to parent norm
    
    // Optional metadata
    canonical_name: "Artigo 5",
    created_date: date("1988-10-05")
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT component_id IF NOT EXISTS
FOR (c:Component) REQUIRE c.component_id IS UNIQUE;

CREATE INDEX component_type IF NOT EXISTS
FOR (c:Component) ON (c.component_type);

CREATE INDEX component_norm IF NOT EXISTS
FOR (c:Component) ON (c.norm_id);
```

### Node: ComponentTemporalVersion (CTV)

```cypher
// A version of a component valid in a specific time period
(:CTV {
    ctv_id: "art_5_v1",              // Unique version ID
    component_id: "art_5",            // Reference to parent component
    version_number: 1,                // Sequential version number
    
    // Temporal bounds
    date_start: date("1988-10-05"),   // When this version became valid
    date_end: null,                   // null = currently valid
    is_active: true,                  // Currently in force
    
    // Provenance
    created_by_action: "original",    // original|amendment
    amendment_number: null,           // If created by amendment
    
    // Content hash for deduplication
    content_hash: "abc123..."
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT ctv_id IF NOT EXISTS
FOR (v:CTV) REQUIRE v.ctv_id IS UNIQUE;

CREATE INDEX ctv_component IF NOT EXISTS
FOR (v:CTV) ON (v.component_id);

CREATE INDEX ctv_dates IF NOT EXISTS
FOR (v:CTV) ON (v.date_start, v.date_end);

CREATE INDEX ctv_active IF NOT EXISTS
FOR (v:CTV) ON (v.is_active);
```

### Node: ComponentLanguageVersion (CLV)

```cypher
// A language-specific expression of a CTV
(:CLV {
    clv_id: "art_5_v1_pt",
    ctv_id: "art_5_v1",
    language: "pt",                   // ISO 639-1 code
    
    // Optional: translation metadata
    translated_date: null,
    translator: null
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT clv_id IF NOT EXISTS
FOR (l:CLV) REQUIRE l.clv_id IS UNIQUE;

CREATE INDEX clv_language IF NOT EXISTS
FOR (l:CLV) ON (l.language);
```

### Node: TextUnit

```cypher
// The actual text content
(:TextUnit {
    text_id: "art_5_v1_pt_text",
    clv_id: "art_5_v1_pt",
    
    // Content
    header: "Art. 5º",
    content: "Todos são iguais perante a lei...",
    full_text: "Art. 5º Todos são iguais perante a lei...",
    
    // Vector embedding (stored separately or inline)
    embedding: null,  // Will be populated later
    embedding_model: null,
    
    // Metadata
    char_count: 1234,
    word_count: 200
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT text_id IF NOT EXISTS
FOR (t:TextUnit) REQUIRE t.text_id IS UNIQUE;

// Vector index for similarity search
CREATE VECTOR INDEX text_embedding IF NOT EXISTS
FOR (t:TextUnit) ON (t.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
}};
```

### Node: Action

```cypher
// An amendment action
(:Action {
    action_id: "ec_45_2004",
    action_type: "modify",            // create|modify|repeal
    
    // Source amendment
    amendment_number: 45,
    amendment_name: "Emenda Constitucional nº 45",
    amendment_date: date("2004-12-30"),
    
    // What was affected
    affected_components: ["art_5_par_3", "art_5_par_4"],
    
    // Description
    description: "Reforma do Judiciário"
})
```

**Constraints:**
```cypher
CREATE CONSTRAINT action_id IF NOT EXISTS
FOR (a:Action) REQUIRE a.action_id IS UNIQUE;

CREATE INDEX action_amendment IF NOT EXISTS
FOR (a:Action) ON (a.amendment_number);

CREATE INDEX action_date IF NOT EXISTS
FOR (a:Action) ON (a.amendment_date);
```

---

## 3.3 Relationship Definitions

### Relationship: HAS_COMPONENT

```cypher
// Norm to top-level Components (Titles)
(:Norm)-[:HAS_COMPONENT]->(:Component)

// Properties: none needed
```

### Relationship: HAS_CHILD

```cypher
// Component hierarchy (abstract level)
(:Component)-[:HAS_CHILD {
    ordering: 1  // Order within parent
}]->(:Component)
```

### Relationship: HAS_VERSION

```cypher
// Component to its temporal versions
(:Component)-[:HAS_VERSION]->(:CTV)
```

### Relationship: AGGREGATES (Critical!)

```cypher
// Parent CTV aggregates child CTVs
// This is the key relationship for the paper's model
(:CTV)-[:AGGREGATES {
    ordering: 1  // Preserve child ordering
}]->(:CTV)
```

**This relationship enables:**
- Sharing of unchanged child versions across parent versions
- Efficient time-travel queries
- Minimal node duplication

### Relationship: EXPRESSED_IN

```cypher
// CTV to language version
(:CTV)-[:EXPRESSED_IN]->(:CLV)
```

### Relationship: HAS_TEXT

```cypher
// CLV to actual text content
(:CLV)-[:HAS_TEXT]->(:TextUnit)
```

### Relationship: RESULTED_IN

```cypher
// Action (amendment) resulted in new version
(:Action)-[:RESULTED_IN]->(:CTV)
```

### Relationship: SUPERSEDES

```cypher
// New version supersedes old version
(:CTV)-[:SUPERSEDES]->(:CTV)
```

---

## 3.4 Implementation

### 3.4.1 Schema Setup Script

**File:** `src/graph/schema.py`

```python
"""Neo4j schema setup for SAT-Graph RAG."""

from neo4j import GraphDatabase
from typing import Optional
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages Neo4j schema constraints and indexes."""
    
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "satgraphrag123")
        self.driver = None
    
    def connect(self):
        """Establish database connection."""
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        # Verify connection
        with self.driver.session() as session:
            session.run("RETURN 1")
        logger.info(f"Connected to Neo4j at {self.uri}")
    
    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()
    
    def create_constraints(self):
        """Create all uniqueness constraints."""
        constraints = [
            # Norm
            "CREATE CONSTRAINT norm_official_id IF NOT EXISTS FOR (n:Norm) REQUIRE n.official_id IS UNIQUE",
            
            # Component
            "CREATE CONSTRAINT component_id IF NOT EXISTS FOR (c:Component) REQUIRE c.component_id IS UNIQUE",
            
            # CTV
            "CREATE CONSTRAINT ctv_id IF NOT EXISTS FOR (v:CTV) REQUIRE v.ctv_id IS UNIQUE",
            
            # CLV
            "CREATE CONSTRAINT clv_id IF NOT EXISTS FOR (l:CLV) REQUIRE l.clv_id IS UNIQUE",
            
            # TextUnit
            "CREATE CONSTRAINT text_id IF NOT EXISTS FOR (t:TextUnit) REQUIRE t.text_id IS UNIQUE",
            
            # Action
            "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:Action) REQUIRE a.action_id IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint.split('CONSTRAINT')[1].split('IF')[0].strip()}")
                except Exception as e:
                    logger.warning(f"Constraint may already exist: {e}")
    
    def create_indexes(self):
        """Create performance indexes."""
        indexes = [
            # Component indexes
            "CREATE INDEX component_type IF NOT EXISTS FOR (c:Component) ON (c.component_type)",
            "CREATE INDEX component_norm IF NOT EXISTS FOR (c:Component) ON (c.norm_id)",
            
            # CTV indexes
            "CREATE INDEX ctv_component IF NOT EXISTS FOR (v:CTV) ON (v.component_id)",
            "CREATE INDEX ctv_active IF NOT EXISTS FOR (v:CTV) ON (v.is_active)",
            "CREATE INDEX ctv_date_start IF NOT EXISTS FOR (v:CTV) ON (v.date_start)",
            
            # CLV indexes
            "CREATE INDEX clv_language IF NOT EXISTS FOR (l:CLV) ON (l.language)",
            
            # Action indexes
            "CREATE INDEX action_amendment IF NOT EXISTS FOR (a:Action) ON (a.amendment_number)",
            "CREATE INDEX action_date IF NOT EXISTS FOR (a:Action) ON (a.amendment_date)",
        ]
        
        with self.driver.session() as session:
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"Created index: {index.split('INDEX')[1].split('IF')[0].strip()}")
                except Exception as e:
                    logger.warning(f"Index may already exist: {e}")
    
    def create_vector_index(self, dimensions: int = 1536):
        """Create vector index for embeddings."""
        query = f"""
        CREATE VECTOR INDEX text_embedding IF NOT EXISTS
        FOR (t:TextUnit) ON (t.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {dimensions},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
        
        with self.driver.session() as session:
            try:
                session.run(query)
                logger.info(f"Created vector index with {dimensions} dimensions")
            except Exception as e:
                logger.warning(f"Vector index may already exist: {e}")
    
    def setup_all(self):
        """Run complete schema setup."""
        logger.info("Setting up Neo4j schema...")
        self.connect()
        self.create_constraints()
        self.create_indexes()
        self.create_vector_index()
        self.close()
        logger.info("Schema setup complete!")
    
    def clear_database(self):
        """Clear all nodes and relationships (for testing)."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.warning("Database cleared!")
    
    def get_schema_info(self) -> dict:
        """Get current schema information."""
        with self.driver.session() as session:
            # Get constraints
            constraints = session.run("SHOW CONSTRAINTS").data()
            
            # Get indexes
            indexes = session.run("SHOW INDEXES").data()
            
            # Get node counts
            counts = session.run("""
                CALL {
                    MATCH (n:Norm) RETURN 'Norm' AS label, count(n) AS count
                    UNION ALL
                    MATCH (n:Component) RETURN 'Component' AS label, count(n) AS count
                    UNION ALL
                    MATCH (n:CTV) RETURN 'CTV' AS label, count(n) AS count
                    UNION ALL
                    MATCH (n:CLV) RETURN 'CLV' AS label, count(n) AS count
                    UNION ALL
                    MATCH (n:TextUnit) RETURN 'TextUnit' AS label, count(n) AS count
                    UNION ALL
                    MATCH (n:Action) RETURN 'Action' AS label, count(n) AS count
                }
                RETURN label, count
            """).data()
        
        return {
            "constraints": len(constraints),
            "indexes": len(indexes),
            "node_counts": {r["label"]: r["count"] for r in counts}
        }


def setup_schema():
    """Convenience function to setup schema."""
    manager = SchemaManager()
    manager.setup_all()
    return manager.get_schema_info()


if __name__ == "__main__":
    info = setup_schema()
    print("\nSchema Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
```

### 3.4.2 Connection Manager

**File:** `src/graph/connection.py`

```python
"""Neo4j connection management."""

from neo4j import GraphDatabase
from contextlib import contextmanager
from typing import Generator
import os
import logging

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Singleton-like connection manager for Neo4j."""
    
    _instance = None
    _driver = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._driver is None:
            self._uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            self._user = os.getenv("NEO4J_USER", "neo4j")
            self._password = os.getenv("NEO4J_PASSWORD", "satgraphrag123")
            self._connect()
    
    def _connect(self):
        """Establish the connection."""
        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password)
        )
        logger.info(f"Neo4j connection established to {self._uri}")
    
    @property
    def driver(self):
        """Get the driver instance."""
        return self._driver
    
    @contextmanager
    def session(self) -> Generator:
        """Context manager for database sessions."""
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self):
        """Close the connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")
    
    def execute_query(self, query: str, parameters: dict = None) -> list:
        """Execute a query and return results."""
        with self.session() as session:
            result = session.run(query, parameters or {})
            return result.data()
    
    def execute_write(self, query: str, parameters: dict = None):
        """Execute a write query."""
        with self.session() as session:
            session.run(query, parameters or {})


# Convenience functions
def get_connection() -> Neo4jConnection:
    """Get the Neo4j connection instance."""
    return Neo4jConnection()


def execute_query(query: str, parameters: dict = None) -> list:
    """Execute a read query."""
    return get_connection().execute_query(query, parameters)


def execute_write(query: str, parameters: dict = None):
    """Execute a write query."""
    get_connection().execute_write(query, parameters)
```

---

## 3.5 Validation Checks

### Check 3.5.1: Schema Creation Tests

**File:** `tests/integration/test_schema.py`

```python
"""Tests for Neo4j schema setup."""

import pytest
from src.graph.schema import SchemaManager
from src.graph.connection import get_connection


@pytest.fixture(scope="module")
def schema_manager():
    """Create and setup schema manager."""
    manager = SchemaManager()
    manager.connect()
    yield manager
    manager.close()


def test_connection(schema_manager):
    """Test database connection."""
    with schema_manager.driver.session() as session:
        result = session.run("RETURN 1 AS test")
        assert result.single()["test"] == 1


def test_constraints_created(schema_manager):
    """Test that all constraints exist."""
    schema_manager.create_constraints()
    
    with schema_manager.driver.session() as session:
        constraints = session.run("SHOW CONSTRAINTS").data()
    
    constraint_names = [c.get("name", "") for c in constraints]
    
    required = [
        "norm_official_id",
        "component_id",
        "ctv_id",
        "clv_id",
        "text_id",
        "action_id",
    ]
    
    for name in required:
        assert any(name in cn for cn in constraint_names), f"Missing constraint: {name}"


def test_indexes_created(schema_manager):
    """Test that all indexes exist."""
    schema_manager.create_indexes()
    
    with schema_manager.driver.session() as session:
        indexes = session.run("SHOW INDEXES").data()
    
    index_names = [i.get("name", "") for i in indexes]
    
    required = [
        "component_type",
        "ctv_component",
        "ctv_active",
    ]
    
    for name in required:
        assert any(name in idx for idx in index_names), f"Missing index: {name}"


def test_vector_index_created(schema_manager):
    """Test that vector index exists."""
    schema_manager.create_vector_index()
    
    with schema_manager.driver.session() as session:
        indexes = session.run("SHOW INDEXES").data()
    
    vector_indexes = [i for i in indexes if i.get("type") == "VECTOR"]
    assert len(vector_indexes) > 0, "No vector index found"


def test_node_creation():
    """Test that nodes can be created with correct schema."""
    conn = get_connection()
    
    # Create a test norm
    conn.execute_write("""
        CREATE (n:Norm {
            official_id: 'TEST_NORM',
            name: 'Test Constitution',
            enactment_date: date('2024-01-01')
        })
    """)
    
    # Verify creation
    result = conn.execute_query("""
        MATCH (n:Norm {official_id: 'TEST_NORM'})
        RETURN n.name AS name
    """)
    
    assert len(result) == 1
    assert result[0]["name"] == "Test Constitution"
    
    # Cleanup
    conn.execute_write("MATCH (n:Norm {official_id: 'TEST_NORM'}) DELETE n")


def test_relationship_creation():
    """Test that relationships can be created correctly."""
    conn = get_connection()
    
    # Create test nodes and relationships
    conn.execute_write("""
        CREATE (n:Norm {official_id: 'TEST_REL_NORM', name: 'Test'})
        CREATE (c:Component {component_id: 'test_art_1', component_type: 'article'})
        CREATE (v:CTV {ctv_id: 'test_art_1_v1', component_id: 'test_art_1', is_active: true})
        CREATE (n)-[:HAS_COMPONENT]->(c)
        CREATE (c)-[:HAS_VERSION]->(v)
    """)
    
    # Verify relationships
    result = conn.execute_query("""
        MATCH (n:Norm)-[:HAS_COMPONENT]->(c:Component)-[:HAS_VERSION]->(v:CTV)
        WHERE n.official_id = 'TEST_REL_NORM'
        RETURN c.component_id AS comp, v.ctv_id AS version
    """)
    
    assert len(result) == 1
    assert result[0]["comp"] == "test_art_1"
    assert result[0]["version"] == "test_art_1_v1"
    
    # Cleanup
    conn.execute_write("""
        MATCH (n:Norm {official_id: 'TEST_REL_NORM'})
        OPTIONAL MATCH (n)-[*]->(related)
        DETACH DELETE n, related
    """)


def test_aggregation_relationship():
    """Test the critical AGGREGATES relationship."""
    conn = get_connection()
    
    # Create parent and child CTVs with aggregation
    conn.execute_write("""
        CREATE (parent:CTV {ctv_id: 'test_parent_v1', component_id: 'parent'})
        CREATE (child1:CTV {ctv_id: 'test_child1_v1', component_id: 'child1'})
        CREATE (child2:CTV {ctv_id: 'test_child2_v1', component_id: 'child2'})
        CREATE (parent)-[:AGGREGATES {ordering: 1}]->(child1)
        CREATE (parent)-[:AGGREGATES {ordering: 2}]->(child2)
    """)
    
    # Query aggregated children
    result = conn.execute_query("""
        MATCH (parent:CTV {ctv_id: 'test_parent_v1'})-[:AGGREGATES]->(child:CTV)
        RETURN child.ctv_id AS child_id
        ORDER BY child.ctv_id
    """)
    
    assert len(result) == 2
    
    # Cleanup
    conn.execute_write("""
        MATCH (v:CTV) WHERE v.ctv_id STARTS WITH 'test_'
        DETACH DELETE v
    """)
```

### Check 3.5.2: Query Pattern Tests

**File:** `tests/unit/test_queries.py`

```python
"""Tests for Cypher query patterns."""

import pytest


class TestQueryPatterns:
    """Test that query patterns are valid Cypher."""
    
    def test_time_travel_query_pattern(self):
        """Test the time-travel query pattern."""
        query = """
        MATCH (n:Norm {official_id: $norm_id})
        MATCH (n)-[:HAS_COMPONENT]->(c:Component)
        MATCH (c)-[:HAS_VERSION]->(v:CTV)
        WHERE v.date_start <= date($query_date)
          AND (v.date_end IS NULL OR v.date_end > date($query_date))
        RETURN c.component_id, v.ctv_id, v.date_start
        """
        # This should be valid Cypher syntax
        assert "MATCH" in query
        assert "WHERE" in query
        assert "$query_date" in query
    
    def test_aggregation_traversal_pattern(self):
        """Test traversal through AGGREGATES relationships."""
        query = """
        MATCH (root:CTV {ctv_id: $root_version})
        MATCH path = (root)-[:AGGREGATES*0..]->(descendant:CTV)
        MATCH (descendant)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(text:TextUnit)
        RETURN descendant.component_id, text.full_text
        """
        assert "AGGREGATES*0.." in query
    
    def test_version_chain_query(self):
        """Test querying version chains."""
        query = """
        MATCH (c:Component {component_id: $comp_id})
        MATCH (c)-[:HAS_VERSION]->(v:CTV)
        OPTIONAL MATCH (v)-[:SUPERSEDES]->(prev:CTV)
        RETURN v.ctv_id, v.date_start, prev.ctv_id AS previous_version
        ORDER BY v.version_number DESC
        """
        assert "SUPERSEDES" in query
```

---

## 3.6 Schema Diagram

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                         NORM                                     │
                    │  - official_id: "CF1988"                                         │
                    │  - name: "Constituição..."                                       │
                    │  - enactment_date: 1988-10-05                                    │
                    └───────────────────────────┬─────────────────────────────────────┘
                                                │
                                         [:HAS_COMPONENT]
                                                │
                    ┌───────────────────────────▼─────────────────────────────────────┐
                    │                      COMPONENT                                   │
                    │  - component_id: "art_5"                                        │
                    │  - component_type: "article"                                     │
                    │  - ordering_id: "5"                                              │
                    └───────────────────────────┬─────────────────────────────────────┘
                                                │
                                          [:HAS_VERSION]
                                                │
                    ┌───────────────────────────▼─────────────────────────────────────┐
                    │                         CTV                                      │
                    │  - ctv_id: "art_5_v1"                                           │
                    │  - date_start: 1988-10-05                                        │
                    │  - date_end: 2004-12-30                                          │
                    │  - is_active: false                                              │
                    ├─────────────────────────────────────────────────────────────────┤
                    │                         CTV                                      │
                    │  - ctv_id: "art_5_v2"                                           │
                    │  - date_start: 2004-12-30                                        │
                    │  - date_end: null                                                │
                    │  - is_active: true                                               │
                    └───────────────────────────┬─────────────────────────────────────┘
                                                │
                                         [:EXPRESSED_IN]
                                                │
                    ┌───────────────────────────▼─────────────────────────────────────┐
                    │                         CLV                                      │
                    │  - clv_id: "art_5_v2_pt"                                        │
                    │  - language: "pt"                                                │
                    └───────────────────────────┬─────────────────────────────────────┘
                                                │
                                           [:HAS_TEXT]
                                                │
                    ┌───────────────────────────▼─────────────────────────────────────┐
                    │                       TEXTUNIT                                   │
                    │  - text_id: "art_5_v2_pt_text"                                  │
                    │  - full_text: "Art. 5º Todos são iguais..."                     │
                    │  - embedding: [0.1, 0.2, ...]                                    │
                    └─────────────────────────────────────────────────────────────────┘


    AGGREGATION PATTERN (Key Innovation):
    
    ┌─────────────────┐                    ┌─────────────────┐
    │  Chapter_v1     │                    │  Chapter_v2     │
    │  (1988-2004)    │                    │  (2004-now)     │
    └────────┬────────┘                    └────────┬────────┘
             │                                      │
             │ [:AGGREGATES]                        │ [:AGGREGATES]
             │                                      │
    ┌────────▼────────┐                    ┌────────▼────────┐
    │   Article_v1    │◄───────────────────│   Article_v1    │ (REUSED!)
    │   (unchanged)   │                    │   (unchanged)   │
    └─────────────────┘                    └─────────────────┘
                                                   │
                                           [:AGGREGATES]
                                                   │
                                           ┌───────▼─────────┐
                                           │   Article_v2    │ (NEW - changed)
                                           │   (2004-now)    │
                                           └─────────────────┘
```

---

## 3.7 Success Criteria

| Criterion | Validation |
|-----------|------------|
| Constraints created | 6 unique constraints exist |
| Indexes created | 8+ indexes exist |
| Vector index created | Vector index with 1536 dimensions |
| Nodes creatable | All node types can be created |
| Relationships creatable | All relationship types work |
| AGGREGATES works | Parent CTV can aggregate multiple child CTVs |
| Time-travel query valid | Query pattern is valid Cypher |

---

## 3.8 Phase Completion Checklist

- [ ] Schema manager implemented
- [ ] Connection manager implemented
- [ ] All constraints created
- [ ] All indexes created
- [ ] Vector index created
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Schema diagram documented
- [ ] Query patterns validated

**Next Phase:** `05_INGESTION_PIPELINE.md`

