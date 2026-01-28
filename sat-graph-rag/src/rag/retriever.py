"""Hybrid retriever combining graph traversal and vector search.

This module implements the retrieval strategies from the paper:
- Point-in-time: Graph traversal with date filtering (time-travel)
- Provenance: Graph traversal on amendment chains
- Semantic: Vector similarity search (when embeddings available)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import date
import logging
import re

from ..graph.connection import get_connection, Neo4jConnection
from .planner import QueryPlan, QueryType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result."""
    component_id: str
    component_type: str
    text: str
    version_info: Dict
    relevance_score: float = 0.0
    provenance: Optional[Dict] = None


class HybridRetriever:
    """
    Retrieves legal content using hybrid graph + vector approach.

    Strategies:
    - Point-in-time: Graph traversal with date filtering
    - Provenance: Graph traversal on amendment chains
    - Semantic: Vector similarity search (when available)
    - Hybrid: Combine date filtering with semantic search
    """

    def __init__(self, conn: Optional[Neo4jConnection] = None):
        self.conn = conn or get_connection()

    def retrieve(
        self,
        plan: QueryPlan,
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        Execute retrieval based on query plan.

        Args:
            plan: QueryPlan from the planner
            top_k: Maximum results to return

        Returns:
            List of RetrievalResult objects
        """
        if plan.query_type == QueryType.POINT_IN_TIME:
            return self._retrieve_point_in_time(plan, top_k)
        elif plan.query_type == QueryType.PROVENANCE:
            return self._retrieve_provenance(plan, top_k)
        elif plan.query_type == QueryType.SEMANTIC:
            return self._retrieve_semantic(plan, top_k)
        else:  # HYBRID
            return self._retrieve_hybrid(plan, top_k)

    def _retrieve_point_in_time(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Retrieve the exact state of law at a specific date.

        This is the "time-travel" query from the paper.
        """
        date_str = plan.target_date.isoformat()

        if plan.target_component:
            # Specific component requested
            # Try exact match first, then partial match
            query = """
            MATCH (c:Component)
            WHERE c.component_id = $comp_id OR c.component_id ENDS WITH $comp_id
            MATCH (c)-[:HAS_VERSION]->(v:CTV)
            WHERE v.date_start <= date($query_date)
              AND (v.date_end IS NULL OR v.date_end > date($query_date))
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       version: v.version_number,
                       start: toString(v.date_start),
                       end: toString(v.date_end),
                       is_active: v.is_active,
                       is_original: v.is_original
                   } AS version_info
            LIMIT 1
            """
            params = {
                "comp_id": plan.target_component,
                "query_date": date_str
            }
        else:
            # Get entire constitution state at date
            query = """
            MATCH (n:Norm)-[:HAS_COMPONENT]->(c:Component)
            MATCH (c)-[:HAS_VERSION]->(v:CTV)
            WHERE v.date_start <= date($query_date)
              AND (v.date_end IS NULL OR v.date_end > date($query_date))
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       version: v.version_number,
                       start: toString(v.date_start),
                       end: toString(v.date_end)
                   } AS version_info
            ORDER BY c.component_id
            LIMIT $limit
            """
            params = {
                "query_date": date_str,
                "limit": top_k
            }

        with self.conn.session() as session:
            results = list(session.run(query, params))

        return [
            RetrievalResult(
                component_id=r["component_id"],
                component_type=r["component_type"],
                text=r["text"],
                version_info=r["version_info"],
                relevance_score=1.0
            )
            for r in results
        ]

    def _retrieve_provenance(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """Retrieve provenance/history information."""

        if plan.amendment_number:
            # Get all changes from a specific amendment
            query = """
            MATCH (a:Action {amendment_number: $amend_num})-[:RESULTED_IN]->(v:CTV)
            MATCH (c:Component {component_id: v.component_id})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            OPTIONAL MATCH (v)-[:SUPERSEDES]->(prev:CTV)
            OPTIONAL MATCH (prev)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(prev_text:TextUnit)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       amendment: a.amendment_number,
                       date: toString(a.amendment_date),
                       description: a.description,
                       previous_text: prev_text.full_text
                   } AS provenance,
                   {version: v.version_number, start: toString(v.date_start)} AS version_info
            LIMIT $limit
            """
            params = {
                "amend_num": plan.amendment_number,
                "limit": top_k
            }

        elif plan.target_component:
            # Get version history of a component
            query = """
            MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            OPTIONAL MATCH (v)-[:SUPERSEDES]->(prev:CTV)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       version: v.version_number,
                       start: toString(v.date_start),
                       end: toString(v.date_end),
                       amendment: v.amendment_number,
                       previous_version: prev.version_number
                   } AS version_info
            ORDER BY v.version_number DESC
            LIMIT $limit
            """
            params = {
                "comp_id": plan.target_component,
                "limit": top_k
            }

        else:
            # General provenance - recent changes
            query = """
            MATCH (a:Action)-[:RESULTED_IN]->(v:CTV)
            MATCH (c:Component {component_id: v.component_id})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       amendment: a.amendment_number,
                       date: toString(a.amendment_date)
                   } AS provenance,
                   {version: v.version_number} AS version_info
            ORDER BY a.amendment_date DESC
            LIMIT $limit
            """
            params = {"limit": top_k}

        with self.conn.session() as session:
            results = list(session.run(query, params))

        return [
            RetrievalResult(
                component_id=r["component_id"],
                component_type=r["component_type"],
                text=r["text"],
                version_info=r["version_info"],
                provenance=r.get("provenance"),
                relevance_score=1.0
            )
            for r in results
        ]

    def _retrieve_semantic(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Retrieve using vector similarity search.

        Falls back to text search if embeddings not available.
        """
        # For now, use text search as fallback
        # TODO: Implement vector search when embeddings are generated
        return self._retrieve_text_search(plan, top_k)

    def _retrieve_hybrid(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """Combine date filtering with semantic search."""
        # For now, fall back to point-in-time
        # TODO: Add semantic filtering
        return self._retrieve_point_in_time(plan, top_k)

    def _retrieve_text_search(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """Fallback text search using CONTAINS."""

        # Extract keywords (simple approach)
        keywords = plan.semantic_query.split()[:3]  # First 3 words
        if not keywords:
            return []

        # Build regex pattern
        pattern = ".*" + ".*".join(re.escape(k) for k in keywords) + ".*"

        query = """
        MATCH (c:Component)-[:HAS_VERSION]->(v:CTV {is_active: true})
              -[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
        WHERE t.full_text =~ $pattern
        RETURN c.component_id AS component_id,
               c.component_type AS component_type,
               t.full_text AS text,
               {version: v.version_number} AS version_info
        LIMIT $limit
        """

        with self.conn.session() as session:
            results = list(session.run(query, {
                "pattern": f"(?i){pattern}",
                "limit": top_k
            }))

        return [
            RetrievalResult(
                component_id=r["component_id"],
                component_type=r["component_type"],
                text=r["text"],
                version_info=r["version_info"],
                relevance_score=0.5
            )
            for r in results
        ]


def retrieve(query: str, date_str: Optional[str] = None, top_k: int = 10) -> List[RetrievalResult]:
    """Convenience function for retrieval."""
    from .planner import QueryPlanner

    planner = QueryPlanner()
    plan = planner.plan(query)

    retriever = HybridRetriever()
    return retriever.retrieve(plan, top_k)
