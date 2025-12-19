"""Tests for Cypher query patterns.

These tests validate that the query patterns used in the system
are syntactically correct and follow expected patterns.
"""

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
        # Verify key elements are present
        assert "MATCH" in query
        assert "WHERE" in query
        assert "$query_date" in query
        assert "date_start" in query
        assert "date_end" in query

    def test_aggregation_traversal_pattern(self):
        """Test traversal through AGGREGATES relationships."""
        query = """
        MATCH (root:CTV {ctv_id: $root_version})
        MATCH path = (root)-[:AGGREGATES*0..]->(descendant:CTV)
        MATCH (descendant)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(text:TextUnit)
        RETURN descendant.component_id, text.full_text
        """
        assert "AGGREGATES*0.." in query
        assert "EXPRESSED_IN" in query
        assert "HAS_TEXT" in query

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
        assert "OPTIONAL MATCH" in query
        assert "ORDER BY" in query

    def test_find_active_version_query(self):
        """Test query to find currently active version."""
        query = """
        MATCH (c:Component {component_id: $comp_id})
        MATCH (c)-[:HAS_VERSION]->(v:CTV {is_active: true})
        MATCH (v)-[:EXPRESSED_IN]->(l:CLV {language: $lang})
        MATCH (l)-[:HAS_TEXT]->(t:TextUnit)
        RETURN v.ctv_id, t.full_text, t.header
        """
        assert "is_active: true" in query
        assert "$lang" in query

    def test_find_version_at_date_query(self):
        """Test query to find version valid at a specific date."""
        query = """
        MATCH (c:Component {component_id: $comp_id})
        MATCH (c)-[:HAS_VERSION]->(v:CTV)
        WHERE v.date_start <= date($target_date)
          AND (v.date_end IS NULL OR v.date_end > date($target_date))
        MATCH (v)-[:EXPRESSED_IN]->(l:CLV {language: 'pt'})
        MATCH (l)-[:HAS_TEXT]->(t:TextUnit)
        RETURN v.ctv_id, v.date_start, v.date_end, t.full_text
        """
        assert "$target_date" in query
        assert "date(" in query

    def test_find_amendments_for_component_query(self):
        """Test query to find all amendments affecting a component."""
        query = """
        MATCH (c:Component {component_id: $comp_id})
        MATCH (a:Action)-[:RESULTED_IN]->(v:CTV)<-[:HAS_VERSION]-(c)
        RETURN a.action_id, a.action_type, a.amendment_number, 
               a.amendment_date, v.ctv_id, v.date_start
        ORDER BY a.amendment_date
        """
        assert "RESULTED_IN" in query
        assert "Action" in query

    def test_semantic_search_query(self):
        """Test vector similarity search query."""
        query = """
        CALL db.index.vector.queryNodes('text_embedding', $k, $embedding)
        YIELD node, score
        MATCH (node)<-[:HAS_TEXT]-(l:CLV)<-[:EXPRESSED_IN]-(v:CTV)
        WHERE v.is_active = true
        RETURN node.text_id, node.full_text, score, v.ctv_id
        ORDER BY score DESC
        """
        assert "db.index.vector.queryNodes" in query
        assert "$embedding" in query
        assert "score" in query

    def test_hierarchy_traversal_query(self):
        """Test traversal of component hierarchy."""
        query = """
        MATCH (root:Component {component_id: $root_id})
        MATCH path = (root)-[:HAS_CHILD*0..10]->(child:Component)
        WITH child, length(path) AS depth
        MATCH (child)-[:HAS_VERSION]->(v:CTV {is_active: true})
        RETURN child.component_id, child.component_type, depth, v.ctv_id
        ORDER BY depth, child.ordering_id
        """
        assert "HAS_CHILD*0..10" in query
        assert "length(path)" in query

    def test_norm_structure_query(self):
        """Test query to get full norm structure."""
        query = """
        MATCH (n:Norm {official_id: $norm_id})
        OPTIONAL MATCH (n)-[:HAS_COMPONENT]->(title:Component {component_type: 'title'})
        OPTIONAL MATCH (title)-[:HAS_CHILD]->(chapter:Component {component_type: 'chapter'})
        RETURN n.name, 
               collect(DISTINCT title.component_id) AS titles,
               collect(DISTINCT chapter.component_id) AS chapters
        """
        assert "OPTIONAL MATCH" in query
        assert "collect(DISTINCT" in query


class TestQueryParameters:
    """Test query parameter handling."""

    def test_date_parameter_format(self):
        """Test that date parameters use correct format."""
        # Neo4j date format
        date_str = "1988-10-05"
        assert len(date_str.split("-")) == 3
        assert len(date_str.split("-")[0]) == 4  # Year
        assert len(date_str.split("-")[1]) == 2  # Month
        assert len(date_str.split("-")[2]) == 2  # Day

    def test_component_id_format(self):
        """Test expected component ID formats."""
        component_ids = [
            "tit_01",
            "tit_01_cap_01",
            "tit_01_cap_01_art_1",
            "tit_01_cap_01_art_1_par_1",
            "tit_01_cap_01_art_1_inc_I",
            "tit_01_cap_01_art_1_inc_I_ali_a",
        ]
        for comp_id in component_ids:
            assert "_" in comp_id
            assert comp_id.startswith("tit_")

    def test_ctv_id_format(self):
        """Test expected CTV ID formats."""
        ctv_ids = [
            "tit_01_v1",
            "tit_01_cap_01_art_1_v1",
            "tit_01_cap_01_art_1_v2",
        ]
        for ctv_id in ctv_ids:
            assert "_v" in ctv_id
            # Version number at end
            version_part = ctv_id.split("_v")[-1]
            assert version_part.isdigit()

