"""Tests for Neo4j schema setup."""

import pytest
from src.graph.schema import SchemaManager
from src.graph.connection import get_connection, Neo4jConnection


@pytest.fixture(scope="module")
def schema_manager():
    """Create and setup schema manager."""
    manager = SchemaManager()
    manager.connect()
    yield manager
    manager.close()


def test_connection(schema_manager):
    """Test database connection."""
    with schema_manager.connection.session() as session:
        result = session.run("RETURN 1 AS test")
        assert result.single()["test"] == 1


def test_constraints_created(schema_manager):
    """Test that all constraints exist."""
    schema_manager.create_constraints()

    constraints = schema_manager.get_constraints()
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

    indexes = schema_manager.get_indexes()
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

    indexes = schema_manager.get_indexes()
    vector_indexes = [i for i in indexes if i.get("type") == "VECTOR"]
    assert len(vector_indexes) > 0, "No vector index found"


def test_schema_info(schema_manager):
    """Test schema info retrieval."""
    info = schema_manager.get_schema_info()

    assert "constraints" in info
    assert "indexes" in info
    assert "node_counts" in info
    assert info["constraints"] >= 6  # We define 6 constraints


def test_node_creation():
    """Test that nodes can be created with correct schema."""
    conn = get_connection()

    try:
        # Create a test norm
        with conn.session() as session:
            session.run("""
                CREATE (n:Norm {
                    official_id: 'TEST_NORM',
                    name: 'Test Constitution',
                    enactment_date: date('2024-01-01')
                })
            """)

        # Verify creation
        with conn.session() as session:
            result = session.run("""
                MATCH (n:Norm {official_id: 'TEST_NORM'})
                RETURN n.name AS name
            """)
            record = result.single()

        assert record is not None
        assert record["name"] == "Test Constitution"

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("MATCH (n:Norm {official_id: 'TEST_NORM'}) DELETE n")


def test_relationship_creation():
    """Test that relationships can be created correctly."""
    conn = get_connection()

    try:
        # Create test nodes and relationships
        with conn.session() as session:
            session.run("""
                CREATE (n:Norm {official_id: 'TEST_REL_NORM', name: 'Test'})
                CREATE (c:Component {component_id: 'test_art_1', component_type: 'article'})
                CREATE (v:CTV {ctv_id: 'test_art_1_v1', component_id: 'test_art_1', is_active: true})
                CREATE (n)-[:HAS_COMPONENT]->(c)
                CREATE (c)-[:HAS_VERSION]->(v)
            """)

        # Verify relationships
        with conn.session() as session:
            result = session.run("""
                MATCH (n:Norm)-[:HAS_COMPONENT]->(c:Component)-[:HAS_VERSION]->(v:CTV)
                WHERE n.official_id = 'TEST_REL_NORM'
                RETURN c.component_id AS comp, v.ctv_id AS version
            """)
            record = result.single()

        assert record is not None
        assert record["comp"] == "test_art_1"
        assert record["version"] == "test_art_1_v1"

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("""
                MATCH (n:Norm {official_id: 'TEST_REL_NORM'})
                OPTIONAL MATCH (n)-[*]->(related)
                DETACH DELETE n, related
            """)


def test_aggregation_relationship():
    """Test the critical AGGREGATES relationship."""
    conn = get_connection()

    try:
        # Create parent and child CTVs with aggregation
        with conn.session() as session:
            session.run("""
                CREATE (parent:CTV {ctv_id: 'test_parent_v1', component_id: 'parent'})
                CREATE (child1:CTV {ctv_id: 'test_child1_v1', component_id: 'child1'})
                CREATE (child2:CTV {ctv_id: 'test_child2_v1', component_id: 'child2'})
                CREATE (parent)-[:AGGREGATES {ordering: 1}]->(child1)
                CREATE (parent)-[:AGGREGATES {ordering: 2}]->(child2)
            """)

        # Query aggregated children
        with conn.session() as session:
            result = session.run("""
                MATCH (parent:CTV {ctv_id: 'test_parent_v1'})-[:AGGREGATES]->(child:CTV)
                RETURN child.ctv_id AS child_id
                ORDER BY child.ctv_id
            """)
            records = list(result)

        assert len(records) == 2
        assert records[0]["child_id"] == "test_child1_v1"
        assert records[1]["child_id"] == "test_child2_v1"

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("""
                MATCH (v:CTV) WHERE v.ctv_id STARTS WITH 'test_'
                DETACH DELETE v
            """)


def test_supersedes_relationship():
    """Test the SUPERSEDES relationship for version chains."""
    conn = get_connection()

    try:
        # Create version chain
        with conn.session() as session:
            session.run("""
                CREATE (v1:CTV {ctv_id: 'test_comp_v1', component_id: 'test_comp', 
                               version_number: 1, is_active: false})
                CREATE (v2:CTV {ctv_id: 'test_comp_v2', component_id: 'test_comp', 
                               version_number: 2, is_active: true})
                CREATE (v2)-[:SUPERSEDES]->(v1)
            """)

        # Query version chain
        with conn.session() as session:
            result = session.run("""
                MATCH (v:CTV {ctv_id: 'test_comp_v2'})-[:SUPERSEDES]->(prev:CTV)
                RETURN v.ctv_id AS current, prev.ctv_id AS previous
            """)
            record = result.single()

        assert record is not None
        assert record["current"] == "test_comp_v2"
        assert record["previous"] == "test_comp_v1"

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("""
                MATCH (v:CTV) WHERE v.ctv_id STARTS WITH 'test_comp_v'
                DETACH DELETE v
            """)


def test_full_node_chain():
    """Test creation of full node chain: Norm -> Component -> CTV -> CLV -> TextUnit."""
    conn = get_connection()

    try:
        # Create full chain
        with conn.session() as session:
            session.run("""
                CREATE (n:Norm {official_id: 'TEST_CHAIN', name: 'Test Norm'})
                CREATE (c:Component {component_id: 'test_chain_art_1', 
                                     component_type: 'article', 
                                     norm_id: 'TEST_CHAIN'})
                CREATE (v:CTV {ctv_id: 'test_chain_art_1_v1', 
                              component_id: 'test_chain_art_1',
                              date_start: date('1988-10-05'),
                              is_active: true})
                CREATE (l:CLV {clv_id: 'test_chain_art_1_v1_pt', 
                              ctv_id: 'test_chain_art_1_v1',
                              language: 'pt'})
                CREATE (t:TextUnit {text_id: 'test_chain_art_1_v1_pt_text',
                                   clv_id: 'test_chain_art_1_v1_pt',
                                   header: 'Art. 1º',
                                   content: 'Test content',
                                   full_text: 'Art. 1º Test content'})
                CREATE (n)-[:HAS_COMPONENT]->(c)
                CREATE (c)-[:HAS_VERSION]->(v)
                CREATE (v)-[:EXPRESSED_IN]->(l)
                CREATE (l)-[:HAS_TEXT]->(t)
            """)

        # Query full chain
        with conn.session() as session:
            result = session.run("""
                MATCH (n:Norm {official_id: 'TEST_CHAIN'})
                MATCH (n)-[:HAS_COMPONENT]->(c:Component)
                MATCH (c)-[:HAS_VERSION]->(v:CTV)
                MATCH (v)-[:EXPRESSED_IN]->(l:CLV)
                MATCH (l)-[:HAS_TEXT]->(t:TextUnit)
                RETURN n.name AS norm, c.component_id AS comp, 
                       v.ctv_id AS version, l.language AS lang, 
                       t.full_text AS text
            """)
            record = result.single()

        assert record is not None
        assert record["norm"] == "Test Norm"
        assert record["comp"] == "test_chain_art_1"
        assert record["version"] == "test_chain_art_1_v1"
        assert record["lang"] == "pt"
        assert "Art. 1º" in record["text"]

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("""
                MATCH (n:Norm {official_id: 'TEST_CHAIN'})
                OPTIONAL MATCH (n)-[*]->(related)
                DETACH DELETE n, related
            """)


def test_action_resulted_in():
    """Test Action -> RESULTED_IN -> CTV relationship."""
    conn = get_connection()

    try:
        # Create action and resulting version
        with conn.session() as session:
            session.run("""
                CREATE (a:Action {
                    action_id: 'ec_45_2004',
                    action_type: 'modify',
                    amendment_number: 45,
                    amendment_name: 'Emenda Constitucional nº 45',
                    amendment_date: date('2004-12-30')
                })
                CREATE (v:CTV {
                    ctv_id: 'test_art_5_par_3_v2',
                    component_id: 'test_art_5_par_3',
                    date_start: date('2004-12-30'),
                    is_active: true
                })
                CREATE (a)-[:RESULTED_IN]->(v)
            """)

        # Query the relationship
        with conn.session() as session:
            result = session.run("""
                MATCH (a:Action)-[:RESULTED_IN]->(v:CTV)
                WHERE a.action_id = 'ec_45_2004'
                RETURN a.amendment_number AS num, v.ctv_id AS version
            """)
            record = result.single()

        assert record is not None
        assert record["num"] == 45
        assert record["version"] == "test_art_5_par_3_v2"

    finally:
        # Cleanup
        with conn.session() as session:
            session.run("""
                MATCH (a:Action {action_id: 'ec_45_2004'})
                OPTIONAL MATCH (a)-[*]->(related)
                DETACH DELETE a, related
            """)

