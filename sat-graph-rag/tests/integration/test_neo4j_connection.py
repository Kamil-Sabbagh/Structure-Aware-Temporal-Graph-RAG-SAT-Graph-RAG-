"""Tests for Neo4j connection and APOC installation."""

import os
import pytest
from neo4j import GraphDatabase


@pytest.fixture
def neo4j_driver():
    """Create a Neo4j driver for testing."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "satgraphrag123")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()


def test_neo4j_connection(neo4j_driver):
    """Test that we can connect to Neo4j and run a simple query."""
    with neo4j_driver.session() as session:
        result = session.run("RETURN 1 AS test")
        record = result.single()
        assert record["test"] == 1


def test_apoc_installed(neo4j_driver):
    """Test that APOC plugin is installed and accessible."""
    with neo4j_driver.session() as session:
        result = session.run("RETURN apoc.version() AS version")
        record = result.single()
        assert record["version"] is not None, "APOC not installed"

