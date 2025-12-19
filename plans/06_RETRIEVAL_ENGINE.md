# Phase 5: Retrieval Engine (RAG)

## Objective
Implement the hybrid retrieval system combining graph traversal for temporal/structural queries with vector similarity for semantic search.

---

## 5.1 Query Types

### 5.1.1 Query Classification (The Planner)

The paper identifies three main query types:

| Type | Description | Example | Strategy |
|------|-------------|---------|----------|
| **Point-in-Time** | What was the law at a specific date? | "What did Art. 5 say in 2015?" | Graph traversal with date filter |
| **Provenance** | What changed and when? | "Which amendment added LXXIX?" | Graph traversal on Action/SUPERSEDES |
| **Semantic** | What does the law say about X? | "What are privacy rights?" | Vector similarity + graph context |

---

## 5.2 Implementation

### 5.2.1 Query Planner

**File:** `src/rag/planner.py`

```python
"""Query planner for classifying and routing queries."""

from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import re
from datetime import date


class QueryType(Enum):
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
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class QueryPlanner:
    """Classifies queries and creates execution plans."""
    
    # Patterns for classification
    PATTERNS = {
        "date": [
            r'em\s+(\d{4})',  # "em 2015"
            r'in\s+(\d{4})',  # "in 2015"
            r'(\d{1,2})[/.](\d{1,2})[/.](\d{4})',  # "01/01/2015"
            r'antes\s+d[aeo]\s+(\d{4})',  # "antes de 2015"
            r'before\s+(\d{4})',
            r'after\s+(\d{4})',
            r'após\s+(\d{4})',
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
            r'quando\s+foi\s+(?:incluído|adicionado|modificado)',
            r'who\s+added',
            r'when\s+was\s+.+\s+(?:added|modified|changed)',
            r'qual\s+emenda',
            r'which\s+amendment',
            r'histórico',
            r'history',
            r'evolução',
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
                    return date(int(year), int(month), int(day))
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
        
        # Remove article references for semantic search
        # (keep for structural queries)
        
        return result.strip()
```

### 5.2.2 Embeddings Generator

**File:** `src/rag/embeddings.py`

```python
"""Embedding generation for TextUnits."""

from typing import List, Optional
import os
import logging
from openai import OpenAI

from src.graph.connection import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate and store embeddings for TextUnits."""
    
    def __init__(
        self,
        model: str = None,
        batch_size: int = 100
    ):
        self.model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.batch_size = batch_size
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conn = get_connection()
        self.dimensions = 1536  # For text-embedding-3-small
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    def embed_all_text_units(self) -> dict:
        """Generate embeddings for all TextUnits without embeddings."""
        stats = {"processed": 0, "errors": 0}
        
        # Get TextUnits without embeddings
        result = self.conn.execute_query("""
            MATCH (t:TextUnit)
            WHERE t.embedding IS NULL AND t.full_text IS NOT NULL
            RETURN t.text_id AS text_id, t.full_text AS text
            LIMIT 1000
        """)
        
        if not result:
            logger.info("No TextUnits to embed")
            return stats
        
        # Process in batches
        for i in range(0, len(result), self.batch_size):
            batch = result[i:i + self.batch_size]
            text_ids = [r["text_id"] for r in batch]
            texts = [r["text"][:8000] for r in batch]  # Truncate to token limit
            
            try:
                embeddings = self.generate_embeddings(texts)
                
                # Store embeddings
                for text_id, embedding in zip(text_ids, embeddings):
                    self._store_embedding(text_id, embedding)
                    stats["processed"] += 1
                
                logger.info(f"Processed batch {i//self.batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Error in batch {i//self.batch_size + 1}: {e}")
                stats["errors"] += len(batch)
        
        return stats
    
    def _store_embedding(self, text_id: str, embedding: List[float]):
        """Store embedding in Neo4j."""
        self.conn.execute_write("""
            MATCH (t:TextUnit {text_id: $text_id})
            SET t.embedding = $embedding,
                t.embedding_model = $model
        """, {
            "text_id": text_id,
            "embedding": embedding,
            "model": self.model
        })
    
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a query."""
        embeddings = self.generate_embeddings([query])
        return embeddings[0]


def generate_all_embeddings() -> dict:
    """Convenience function to generate all embeddings."""
    generator = EmbeddingGenerator()
    return generator.embed_all_text_units()


if __name__ == "__main__":
    stats = generate_all_embeddings()
    print(f"Embedding stats: {stats}")
```

### 5.2.3 Graph Retriever

**File:** `src/rag/retriever.py`

```python
"""Hybrid retriever combining graph traversal and vector search."""

from typing import List, Dict, Optional
from datetime import date
from dataclasses import dataclass
import logging

from src.graph.connection import get_connection
from .planner import QueryPlan, QueryType
from .embeddings import EmbeddingGenerator

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
    - Semantic: Vector similarity search
    - Hybrid: Combine date filtering with vector search
    """
    
    def __init__(self):
        self.conn = get_connection()
        self.embedder = EmbeddingGenerator()
    
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
            query = """
            MATCH (c:Component {component_id: $comp_id})
            MATCH (c)-[:HAS_VERSION]->(v:CTV)
            WHERE v.date_start <= date($query_date)
              AND (v.date_end IS NULL OR v.date_end > date($query_date))
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN c.component_id AS component_id,
                   c.component_type AS component_type,
                   t.full_text AS text,
                   {
                       version: v.version_number,
                       start: v.date_start,
                       end: v.date_end,
                       is_active: v.is_active,
                       is_original: v.is_original
                   } AS version_info
            """
            results = self.conn.execute_query(query, {
                "comp_id": plan.target_component,
                "query_date": date_str
            })
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
                       start: v.date_start,
                       end: v.date_end
                   } AS version_info
            ORDER BY c.component_id
            LIMIT $limit
            """
            results = self.conn.execute_query(query, {
                "query_date": date_str,
                "limit": top_k
            })
        
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
                       date: a.amendment_date,
                       description: a.description,
                       previous_text: prev_text.full_text
                   } AS provenance,
                   {version: v.version_number, start: v.date_start} AS version_info
            LIMIT $limit
            """
            results = self.conn.execute_query(query, {
                "amend_num": plan.amendment_number,
                "limit": top_k
            })
        
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
                       start: v.date_start,
                       end: v.date_end,
                       amendment: v.amendment_number,
                       previous_version: prev.version_number
                   } AS version_info
            ORDER BY v.version_number DESC
            LIMIT $limit
            """
            results = self.conn.execute_query(query, {
                "comp_id": plan.target_component,
                "limit": top_k
            })
        
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
                       date: a.amendment_date
                   } AS provenance,
                   {version: v.version_number} AS version_info
            ORDER BY a.amendment_date DESC
            LIMIT $limit
            """
            results = self.conn.execute_query(query, {"limit": top_k})
        
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
        """Retrieve using vector similarity search."""
        
        # Generate query embedding
        query_embedding = self.embedder.embed_query(plan.semantic_query)
        
        # Vector similarity search in Neo4j
        query = """
        CALL db.index.vector.queryNodes('text_embedding', $top_k, $embedding)
        YIELD node AS t, score
        MATCH (t)<-[:HAS_TEXT]-(l:CLV)<-[:EXPRESSED_IN]-(v:CTV)<-[:HAS_VERSION]-(c:Component)
        WHERE v.is_active = true
        RETURN c.component_id AS component_id,
               c.component_type AS component_type,
               t.full_text AS text,
               {version: v.version_number, start: v.date_start} AS version_info,
               score
        ORDER BY score DESC
        """
        
        try:
            results = self.conn.execute_query(query, {
                "embedding": query_embedding,
                "top_k": top_k
            })
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            # Fallback to text search
            return self._retrieve_text_search(plan, top_k)
        
        return [
            RetrievalResult(
                component_id=r["component_id"],
                component_type=r["component_type"],
                text=r["text"],
                version_info=r["version_info"],
                relevance_score=r["score"]
            )
            for r in results
        ]
    
    def _retrieve_hybrid(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """Combine date filtering with semantic search."""
        
        date_str = plan.target_date.isoformat()
        query_embedding = self.embedder.embed_query(plan.semantic_query)
        
        # Vector search with date filter
        query = """
        CALL db.index.vector.queryNodes('text_embedding', $top_k * 2, $embedding)
        YIELD node AS t, score
        MATCH (t)<-[:HAS_TEXT]-(l:CLV)<-[:EXPRESSED_IN]-(v:CTV)<-[:HAS_VERSION]-(c:Component)
        WHERE v.date_start <= date($query_date)
          AND (v.date_end IS NULL OR v.date_end > date($query_date))
        RETURN c.component_id AS component_id,
               c.component_type AS component_type,
               t.full_text AS text,
               {version: v.version_number, start: v.date_start} AS version_info,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
        
        try:
            results = self.conn.execute_query(query, {
                "embedding": query_embedding,
                "query_date": date_str,
                "top_k": top_k
            })
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return self._retrieve_point_in_time(plan, top_k)
        
        return [
            RetrievalResult(
                component_id=r["component_id"],
                component_type=r["component_type"],
                text=r["text"],
                version_info=r["version_info"],
                relevance_score=r["score"]
            )
            for r in results
        ]
    
    def _retrieve_text_search(
        self,
        plan: QueryPlan,
        top_k: int
    ) -> List[RetrievalResult]:
        """Fallback text search using CONTAINS."""
        
        # Extract keywords
        keywords = plan.semantic_query.split()[:3]  # First 3 words
        pattern = ".*" + ".*".join(keywords) + ".*"
        
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
        
        results = self.conn.execute_query(query, {
            "pattern": f"(?i){pattern}",
            "limit": top_k
        })
        
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


def retrieve(query: str, date: str = None, top_k: int = 10) -> List[RetrievalResult]:
    """Convenience function for retrieval."""
    from .planner import QueryPlanner
    
    planner = QueryPlanner()
    plan = planner.plan(query)
    
    retriever = HybridRetriever()
    return retriever.retrieve(plan, top_k)
```

### 5.2.4 Response Generator

**File:** `src/rag/generator.py`

```python
"""LLM-based response generation."""

from typing import List, Optional
import os
from openai import OpenAI
import logging

from .retriever import RetrievalResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates responses using LLM with retrieved context."""
    
    SYSTEM_PROMPT = """Você é um assistente jurídico especializado na Constituição Federal do Brasil de 1988.

Responda às perguntas do usuário com base EXCLUSIVAMENTE no contexto fornecido.
Se a informação não estiver no contexto, diga que não foi possível encontrar a resposta.

Quando citar artigos, sempre mencione:
- O número do artigo
- A versão (se histórico for relevante)
- A data de vigência (se aplicável)

Seja preciso e objetivo nas respostas."""

    def __init__(self, model: str = None):
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate(
        self,
        query: str,
        results: List[RetrievalResult],
        include_provenance: bool = False
    ) -> str:
        """
        Generate a response based on retrieved results.
        
        Args:
            query: Original user query
            results: Retrieved legal content
            include_provenance: Include version history in context
            
        Returns:
            Generated response text
        """
        if not results:
            return "Não foi possível encontrar informações relevantes para sua consulta."
        
        # Build context
        context = self._build_context(results, include_provenance)
        
        # Generate response
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"""Contexto legal:

{context}

---

Pergunta do usuário: {query}

Responda com base no contexto acima:"""}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return f"Erro ao gerar resposta: {e}"
    
    def _build_context(
        self,
        results: List[RetrievalResult],
        include_provenance: bool
    ) -> str:
        """Build context string from results."""
        context_parts = []
        
        for i, result in enumerate(results, 1):
            part = f"[{i}] {result.component_id.upper()}\n"
            part += f"Tipo: {result.component_type}\n"
            
            # Version info
            v = result.version_info
            if v:
                part += f"Versão: {v.get('version', 'N/A')}"
                if v.get('start'):
                    part += f" (desde {v['start']})"
                part += "\n"
            
            # Text content
            part += f"Texto:\n{result.text}\n"
            
            # Provenance
            if include_provenance and result.provenance:
                p = result.provenance
                part += f"\nHistórico:\n"
                if p.get('amendment'):
                    part += f"  - Alterado pela EC {p['amendment']}"
                    if p.get('date'):
                        part += f" em {p['date']}"
                    part += "\n"
                if p.get('previous_text'):
                    part += f"  - Texto anterior: {p['previous_text'][:200]}...\n"
            
            context_parts.append(part)
        
        return "\n---\n".join(context_parts)


class RAGPipeline:
    """Complete RAG pipeline combining retrieval and generation."""
    
    def __init__(self):
        from .planner import QueryPlanner
        from .retriever import HybridRetriever
        
        self.planner = QueryPlanner()
        self.retriever = HybridRetriever()
        self.generator = ResponseGenerator()
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        include_sources: bool = True
    ) -> dict:
        """
        Execute full RAG pipeline.
        
        Args:
            question: User's question
            top_k: Number of results to retrieve
            include_sources: Include source citations in response
            
        Returns:
            Dict with 'answer', 'sources', and 'query_plan'
        """
        # Plan
        plan = self.planner.plan(question)
        
        # Retrieve
        results = self.retriever.retrieve(plan, top_k)
        
        # Generate
        include_provenance = plan.query_type.value == "provenance"
        answer = self.generator.generate(
            question,
            results,
            include_provenance=include_provenance
        )
        
        # Format response
        response = {
            "answer": answer,
            "query_type": plan.query_type.value,
            "sources": []
        }
        
        if include_sources:
            response["sources"] = [
                {
                    "component_id": r.component_id,
                    "component_type": r.component_type,
                    "text_preview": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                    "version": r.version_info,
                    "relevance": r.relevance_score
                }
                for r in results
            ]
        
        return response


def ask(question: str) -> dict:
    """Convenience function for RAG query."""
    pipeline = RAGPipeline()
    return pipeline.query(question)
```

---

## 5.3 API Implementation

**File:** `src/api/routes/query.py`

```python
"""Query API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

from src.rag.planner import QueryPlanner
from src.rag.retriever import HybridRetriever
from src.rag.generator import RAGPipeline

router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    """Query request model."""
    question: str = Field(..., description="Natural language question")
    date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD)")
    top_k: int = Field(5, description="Number of results", ge=1, le=20)
    include_sources: bool = Field(True, description="Include source citations")


class SourceInfo(BaseModel):
    """Source information in response."""
    component_id: str
    component_type: str
    text_preview: str
    relevance: float


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    query_type: str
    sources: List[SourceInfo]


class TimeTravelRequest(BaseModel):
    """Time-travel query request."""
    component_id: str = Field(..., description="Component ID (e.g., 'art_5')")
    date: str = Field(..., description="Target date (YYYY-MM-DD)")


class TimeTravelResponse(BaseModel):
    """Time-travel response."""
    component_id: str
    text: str
    version_number: int
    valid_from: str
    valid_until: Optional[str]


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Execute a natural language query against the legal knowledge base.
    
    Supports:
    - Semantic queries: "What are privacy rights?"
    - Point-in-time: "What did Art. 5 say in 2015?"
    - Provenance: "Which amendment added LXXIX?"
    """
    try:
        pipeline = RAGPipeline()
        result = pipeline.query(
            question=request.question,
            top_k=request.top_k,
            include_sources=request.include_sources
        )
        
        return QueryResponse(
            answer=result["answer"],
            query_type=result["query_type"],
            sources=[
                SourceInfo(
                    component_id=s["component_id"],
                    component_type=s["component_type"],
                    text_preview=s["text_preview"],
                    relevance=s["relevance"]
                )
                for s in result.get("sources", [])
            ]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/time-travel", response_model=TimeTravelResponse)
async def time_travel(request: TimeTravelRequest):
    """
    Retrieve the exact text of a component at a specific date.
    
    This is the deterministic "time-travel" query from the paper.
    """
    from src.rag.planner import QueryPlan, QueryType
    from datetime import datetime
    
    try:
        # Parse date
        target_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        
        # Create plan
        plan = QueryPlan(
            query_type=QueryType.POINT_IN_TIME,
            original_query=f"{request.component_id} at {request.date}",
            target_date=target_date,
            target_component=request.component_id
        )
        
        # Retrieve
        retriever = HybridRetriever()
        results = retriever.retrieve(plan, top_k=1)
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Component {request.component_id} not found at {request.date}"
            )
        
        r = results[0]
        return TimeTravelResponse(
            component_id=r.component_id,
            text=r.text,
            version_number=r.version_info.get("version", 1),
            valid_from=str(r.version_info.get("start", "")),
            valid_until=str(r.version_info.get("end", "")) if r.version_info.get("end") else None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/amendments/{amendment_number}")
async def get_amendment_changes(amendment_number: int):
    """Get all changes made by a specific amendment."""
    from src.graph.connection import get_connection
    
    conn = get_connection()
    results = conn.execute_query("""
        MATCH (a:Action {amendment_number: $num})-[:RESULTED_IN]->(v:CTV)
        MATCH (c:Component {component_id: v.component_id})
        MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
        RETURN c.component_id AS component_id,
               c.component_type AS component_type,
               t.full_text AS text,
               a.amendment_date AS date
    """, {"num": amendment_number})
    
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Amendment {amendment_number} not found"
        )
    
    return {
        "amendment_number": amendment_number,
        "date": str(results[0].get("date", "")),
        "changes": [
            {
                "component_id": r["component_id"],
                "component_type": r["component_type"],
                "text": r["text"]
            }
            for r in results
        ]
    }
```

---

## 5.4 Validation Checks

### Check 5.4.1: Planner Tests

**File:** `tests/unit/test_planner.py`

```python
"""Tests for query planner."""

import pytest
from datetime import date
from src.rag.planner import QueryPlanner, QueryType


class TestQueryPlanner:
    
    @pytest.fixture
    def planner(self):
        return QueryPlanner()
    
    def test_semantic_query(self, planner):
        plan = planner.plan("Quais são os direitos de privacidade?")
        assert plan.query_type == QueryType.SEMANTIC
        assert plan.semantic_query is not None
    
    def test_point_in_time_with_article(self, planner):
        plan = planner.plan("O que dizia o artigo 5 em 2015?")
        assert plan.query_type == QueryType.POINT_IN_TIME
        assert plan.target_date.year == 2015
        assert plan.target_component == "art_5"
    
    def test_provenance_query(self, planner):
        plan = planner.plan("Qual emenda incluiu o inciso LXXIX?")
        assert plan.query_type == QueryType.PROVENANCE
    
    def test_amendment_reference(self, planner):
        plan = planner.plan("O que mudou com a EC 45?")
        assert plan.query_type == QueryType.PROVENANCE
        assert plan.amendment_number == 45
    
    def test_date_extraction_year(self, planner):
        plan = planner.plan("Lei em 2020")
        assert plan.target_date is not None
        assert plan.target_date.year == 2020
    
    def test_date_extraction_full(self, planner):
        plan = planner.plan("Em 15/03/2010")
        assert plan.target_date is not None
        assert plan.target_date == date(2010, 3, 15)
    
    def test_article_extraction(self, planner):
        plan = planner.plan("Artigo 225")
        assert plan.target_component == "art_225"


class TestQueryTypeClassification:
    
    @pytest.fixture
    def planner(self):
        return QueryPlanner()
    
    @pytest.mark.parametrize("query,expected_type", [
        ("What are fundamental rights?", QueryType.SEMANTIC),
        ("Art 5 in 2015", QueryType.POINT_IN_TIME),
        ("Which amendment added LXXIX?", QueryType.PROVENANCE),
        ("EC 45 changes", QueryType.PROVENANCE),
        ("Privacy in 2020", QueryType.HYBRID),
    ])
    def test_classification(self, planner, query, expected_type):
        plan = planner.plan(query)
        assert plan.query_type == expected_type
```

### Check 5.4.2: Retrieval Tests

**File:** `tests/integration/test_retrieval.py`

```python
"""Tests for retrieval engine."""

import pytest
from datetime import date

from src.rag.planner import QueryPlanner, QueryPlan, QueryType
from src.rag.retriever import HybridRetriever


@pytest.fixture
def retriever():
    return HybridRetriever()


@pytest.fixture
def planner():
    return QueryPlanner()


def test_point_in_time_retrieval(retriever, planner):
    """Test time-travel query."""
    plan = QueryPlan(
        query_type=QueryType.POINT_IN_TIME,
        original_query="Art 5 em 2000",
        target_date=date(2000, 1, 1),
        target_component="art_5"
    )
    
    results = retriever.retrieve(plan, top_k=1)
    
    # Should return results if data exists
    if results:
        assert results[0].component_id == "art_5"
        assert results[0].text is not None


def test_semantic_retrieval(retriever, planner):
    """Test semantic search."""
    plan = QueryPlan(
        query_type=QueryType.SEMANTIC,
        original_query="direitos fundamentais",
        semantic_query="direitos fundamentais"
    )
    
    results = retriever.retrieve(plan, top_k=5)
    
    # Should return relevant results
    if results:
        assert len(results) <= 5
        assert all(r.text for r in results)


def test_provenance_retrieval(retriever):
    """Test provenance query."""
    plan = QueryPlan(
        query_type=QueryType.PROVENANCE,
        original_query="EC 45",
        amendment_number=45
    )
    
    results = retriever.retrieve(plan, top_k=10)
    
    # Should return changes from EC 45
    if results:
        assert all(r.provenance or r.version_info for r in results)
```

---

## 5.5 Success Criteria

| Criterion | Validation |
|-----------|------------|
| Query classification works | Planner correctly identifies query type |
| Date extraction works | Dates parsed from various formats |
| Article extraction works | "art_5" extracted from "artigo 5" |
| Point-in-time returns valid text | Text from correct version at date |
| Semantic search returns relevant | Top results match query semantically |
| Provenance shows history | Amendment info included in results |
| API endpoints respond | /query and /time-travel return 200 |
| Vector index works | Similarity search executes without error |

---

## 5.6 Phase Completion Checklist

- [ ] QueryPlanner implemented
- [ ] EmbeddingGenerator implemented
- [ ] HybridRetriever implemented
- [ ] ResponseGenerator implemented
- [ ] RAGPipeline integrated
- [ ] API endpoints created
- [ ] Embeddings generated for TextUnits
- [ ] Point-in-time queries work
- [ ] Provenance queries work
- [ ] Semantic queries work
- [ ] All tests pass

**Next Phase:** `07_VERIFICATION.md`

