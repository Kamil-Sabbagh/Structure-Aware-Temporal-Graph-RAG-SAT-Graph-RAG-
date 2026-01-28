"""Baseline RAG system for comparison.

This is a standard flat-chunk RAG with no temporal or structural awareness:
- Uses only current version of constitution (no historical data)
- Splits text into flat chunks
- Simple text-based retrieval (no temporal filtering)
- No amendment tracking or version history
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import re
import json

from ..graph.connection import get_connection, Neo4jConnection


@dataclass
class BaselineResult:
    """A single baseline retrieval result."""
    component_id: str
    text: str
    score: float
    metadata: Dict = None


class FlatChunkRAG:
    """
    Baseline RAG system using flat text chunks.

    Key limitations (by design):
    - No temporal awareness (only current version)
    - No structural hierarchy
    - No amendment tracking
    - No version history
    - Simple keyword matching
    """

    def __init__(self, conn: Optional[Neo4jConnection] = None):
        self.conn = conn or get_connection()
        self.chunks = []
        self._build_flat_index()

    def _build_flat_index(self):
        """Build flat index of current constitution text only."""
        # Get ONLY active (current) versions - no historical data
        query = """
        MATCH (c:Component)-[:HAS_VERSION]->(v:CTV {is_active: true})
              -[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
        WHERE c.component_type IN ['article', 'paragraph', 'item']
        RETURN c.component_id AS id,
               c.component_type AS type,
               c.ordering_id AS ordering,
               t.full_text AS text,
               t.header AS header
        ORDER BY c.component_id
        """

        with self.conn.session() as session:
            results = list(session.run(query))

        self.chunks = []
        for r in results:
            # Flatten everything into simple chunks (lose structure)
            chunk = {
                'id': r['id'],
                'type': r['type'],
                'text': r['text'] or '',
                'header': r['header'] or '',
                'full_content': f"{r['header'] or ''} {r['text'] or ''}".strip()
            }
            self.chunks.append(chunk)

        print(f"📦 Baseline RAG: Indexed {len(self.chunks)} flat chunks (current version only)")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        date: Optional[str] = None  # Ignored - no temporal capability
    ) -> List[BaselineResult]:
        """
        Retrieve using simple keyword matching.

        Note: 'date' parameter is IGNORED - baseline has no temporal awareness.
        """
        # Simple keyword extraction
        keywords = self._extract_keywords(query)

        # Score each chunk by keyword overlap
        scored_chunks = []
        for chunk in self.chunks:
            score = self._score_chunk(chunk, keywords)
            if score > 0:
                scored_chunks.append((chunk, score))

        # Sort by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Return top-k
        results = []
        for chunk, score in scored_chunks[:top_k]:
            results.append(BaselineResult(
                component_id=chunk['id'],
                text=chunk['full_content'],
                score=score,
                metadata={'type': chunk['type']}
            ))

        return results

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query (simple approach)."""
        # Remove common words (stop words)
        stop_words = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'dos', 'das',
            'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 'sem',
            'e', 'ou', 'que', 'qual', 'quais', 'quando', 'onde', 'como',
            'artigo', 'art', 'emenda', 'ec', 'são', 'foi', 'era', 'diz',
            'dizia', 'the', 'what', 'which', 'when', 'how', 'did', 'was'
        }

        # Tokenize and filter
        words = re.findall(r'\w+', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def _score_chunk(self, chunk: Dict, keywords: List[str]) -> float:
        """Score a chunk by keyword overlap."""
        text = chunk['full_content'].lower()

        # Count keyword matches
        matches = 0
        for keyword in keywords:
            if keyword in text:
                # Count occurrences (but cap at 3 per keyword)
                count = min(text.count(keyword), 3)
                matches += count

        # Normalize by chunk length (prefer concise chunks)
        if matches == 0:
            return 0.0

        chunk_len = len(text.split())
        score = matches / (1 + chunk_len / 100.0)  # Penalize very long chunks

        return score

    def get_stats(self) -> Dict:
        """Get baseline system statistics."""
        return {
            'total_chunks': len(self.chunks),
            'temporal_capability': False,
            'structural_capability': False,
            'provenance_capability': False,
            'version_history_capability': False,
            'data_source': 'current version only (no historical data)'
        }


def create_baseline_retriever() -> FlatChunkRAG:
    """Convenience function to create baseline retriever."""
    return FlatChunkRAG()
