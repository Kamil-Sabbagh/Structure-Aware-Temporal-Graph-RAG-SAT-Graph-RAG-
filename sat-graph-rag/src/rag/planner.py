"""Query planner for classifying and routing queries.

This module implements query classification as described in the paper:
- Point-in-time: "What was Art 5 in 2015?"
- Provenance: "Which amendment changed Art 5?"
- Semantic: "What are privacy rights?"
"""

from typing import Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from datetime import date
import re


class QueryType(Enum):
    """Types of queries supported by the system."""
    POINT_IN_TIME = "point_in_time"
    PROVENANCE = "provenance"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class QueryPlan:
    """A plan for executing a query."""
    query_type: QueryType
    original_query: str

    # For point-in-time queries
    target_date: Optional[date] = None

    # For component-specific queries
    target_component: Optional[str] = None  # e.g., "art_5"

    # For provenance queries
    amendment_number: Optional[int] = None

    # For semantic queries
    semantic_query: Optional[str] = None

    # Additional context
    metadata: Dict = field(default_factory=dict)


class QueryPlanner:
    """Classifies queries and creates execution plans."""

    # Patterns for classification
    PATTERNS = {
        "date": [
            r'em\s+(\d{4})',  # "em 2015"
            r'in\s+(\d{4})',  # "in 2015"
            r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})',  # "01/01/2015"
            r'antes\s+d[aeo]\s+(\d{4})',  # "antes de 2015"
            r'before\s+(\d{4})',
            r'after\s+(\d{4})',
            r'ap[oó]s\s+(\d{4})',
        ],
        "article": [
            r'art(?:igo)?\.?\s*(\d+)',  # "art 5", "artigo 5"
            r'article\s*(\d+)',
        ],
        "amendment": [
            r'emenda\s+(?:constitucional\s+)?(?:n[º°]?\s*)?(\d+)',
            r'ec\s*(\d+)',
            r'amendment\s*(?:no?\.?\s*)?(\d+)',
        ],
        "provenance": [
            r'quem\s+(?:incluiu|adicionou|modificou|alterou)',
            r'quando\s+foi\s+(?:inclu[ií]do|adicionado|modificado)',
            r'who\s+added',
            r'when\s+was\s+.+\s+(?:added|modified|changed)',
            r'qual\s+emenda',
            r'which\s+amendment',
            r'hist[oó]rico',
            r'history',
            r'evolu[cç][aã]o',
            r'mudou',
            r'changed',
        ],
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        self._compiled = {}
        for category, patterns in self.PATTERNS.items():
            self._compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def plan(self, query: str) -> QueryPlan:
        """
        Analyze a query and create an execution plan.

        Args:
            query: Natural language query

        Returns:
            QueryPlan with classified type and extracted parameters
        """
        query_lower = query.lower()

        # Extract entities
        target_date = self._extract_date(query)
        target_article = self._extract_article(query)
        amendment_num = self._extract_amendment(query)
        is_provenance = self._is_provenance_query(query)

        # Classify query type
        if is_provenance or amendment_num:
            query_type = QueryType.PROVENANCE
        elif target_date and target_article:
            query_type = QueryType.POINT_IN_TIME
        elif target_date:
            query_type = QueryType.HYBRID  # Date + semantic search
        else:
            query_type = QueryType.SEMANTIC

        return QueryPlan(
            query_type=query_type,
            original_query=query,
            target_date=target_date,
            target_component=f"art_{target_article}" if target_article else None,
            amendment_number=amendment_num,
            semantic_query=self._clean_for_semantic(query),
            metadata={
                "has_date": target_date is not None,
                "has_article": target_article is not None,
                "has_amendment": amendment_num is not None,
            }
        )

    def _extract_date(self, query: str) -> Optional[date]:
        """Extract a date from the query."""
        for pattern in self._compiled["date"]:
            match = pattern.search(query)
            if match:
                groups = match.groups()
                if len(groups) == 1:  # Just year
                    return date(int(groups[0]), 7, 1)  # Middle of year
                elif len(groups) == 3:  # Full date
                    day, month, year = groups
                    try:
                        return date(int(year), int(month), int(day))
                    except ValueError:
                        continue
        return None

    def _extract_article(self, query: str) -> Optional[str]:
        """Extract article number from query."""
        for pattern in self._compiled["article"]:
            match = pattern.search(query)
            if match:
                return match.group(1)
        return None

    def _extract_amendment(self, query: str) -> Optional[int]:
        """Extract amendment number from query."""
        for pattern in self._compiled["amendment"]:
            match = pattern.search(query)
            if match:
                return int(match.group(1))
        return None

    def _is_provenance_query(self, query: str) -> bool:
        """Check if query is about provenance/history."""
        for pattern in self._compiled["provenance"]:
            if pattern.search(query):
                return True
        return False

    def _clean_for_semantic(self, query: str) -> str:
        """Clean query for semantic search by removing specific references."""
        result = query

        # Remove date references
        for pattern in self._compiled["date"]:
            result = pattern.sub("", result)

        return result.strip()
