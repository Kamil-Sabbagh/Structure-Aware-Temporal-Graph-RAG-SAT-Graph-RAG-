"""Neo4j schema setup for SAT-Graph RAG.

Implements the LRMoo-inspired schema for temporal versioning of legal documents.

Node Types:
- Norm: Root legal document
- Component: Abstract structural unit (Title, Chapter, Article, etc.)
- CTV: ComponentTemporalVersion - version valid in a time period
- CLV: ComponentLanguageVersion - language expression of a CTV
- TextUnit: Actual text content with embeddings
- Action: Amendment action (create, modify, repeal)

Key Relationships:
- HAS_COMPONENT: Norm -> Component
- HAS_CHILD: Component -> Component (hierarchy)
- HAS_VERSION: Component -> CTV
- AGGREGATES: CTV -> CTV (paper's key innovation)
- EXPRESSED_IN: CTV -> CLV
- HAS_TEXT: CLV -> TextUnit
- RESULTED_IN: Action -> CTV
- SUPERSEDES: CTV -> CTV (version chain)
"""

from typing import Optional
import logging

from .connection import Neo4jConnection, get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages Neo4j schema constraints and indexes."""

    # Uniqueness constraints for each node type
    CONSTRAINTS = [
        # Norm - root document
        "CREATE CONSTRAINT norm_official_id IF NOT EXISTS FOR (n:Norm) REQUIRE n.official_id IS UNIQUE",
        # Component - abstract structural unit
        "CREATE CONSTRAINT component_id IF NOT EXISTS FOR (c:Component) REQUIRE c.component_id IS UNIQUE",
        # CTV - temporal version
        "CREATE CONSTRAINT ctv_id IF NOT EXISTS FOR (v:CTV) REQUIRE v.ctv_id IS UNIQUE",
        # CLV - language version
        "CREATE CONSTRAINT clv_id IF NOT EXISTS FOR (l:CLV) REQUIRE l.clv_id IS UNIQUE",
        # TextUnit - text content
        "CREATE CONSTRAINT text_id IF NOT EXISTS FOR (t:TextUnit) REQUIRE t.text_id IS UNIQUE",
        # Action - amendment action
        "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:Action) REQUIRE a.action_id IS UNIQUE",
    ]

    # Performance indexes
    INDEXES = [
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

    def __init__(self, connection: Optional[Neo4jConnection] = None):
        """Initialize schema manager.

        Args:
            connection: Neo4j connection instance (uses global if not provided)
        """
        self.connection = connection or get_connection()
        self._connected = False

    def connect(self) -> None:
        """Establish database connection."""
        self.connection.connect()
        if self.connection.verify_connection():
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.connection.uri}")
        else:
            raise ConnectionError("Failed to verify Neo4j connection")

    def close(self) -> None:
        """Close database connection."""
        self.connection.close()
        self._connected = False

    def create_constraints(self) -> int:
        """Create all uniqueness constraints.

        Returns:
            Number of constraints created
        """
        created = 0
        with self.connection.session() as session:
            for constraint in self.CONSTRAINTS:
                try:
                    session.run(constraint)
                    constraint_name = constraint.split("CONSTRAINT")[1].split("IF")[0].strip()
                    logger.info(f"Created constraint: {constraint_name}")
                    created += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"Constraint already exists: {e}")
                    else:
                        logger.warning(f"Failed to create constraint: {e}")
        return created

    def create_indexes(self) -> int:
        """Create performance indexes.

        Returns:
            Number of indexes created
        """
        created = 0
        with self.connection.session() as session:
            for index in self.INDEXES:
                try:
                    session.run(index)
                    index_name = index.split("INDEX")[1].split("IF")[0].strip()
                    logger.info(f"Created index: {index_name}")
                    created += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"Index already exists: {e}")
                    else:
                        logger.warning(f"Failed to create index: {e}")
        return created

    def create_vector_index(self, dimensions: int = 1536) -> bool:
        """Create vector index for embeddings.

        Args:
            dimensions: Embedding vector dimensions (1536 for OpenAI ada-002)

        Returns:
            True if created successfully
        """
        query = f"""
        CREATE VECTOR INDEX text_embedding IF NOT EXISTS
        FOR (t:TextUnit) ON (t.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {dimensions},
            `vector.similarity_function`: 'cosine'
        }}}}
        """

        with self.connection.session() as session:
            try:
                session.run(query)
                logger.info(f"Created vector index with {dimensions} dimensions")
                return True
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Vector index already exists: {e}")
                    return True
                logger.warning(f"Failed to create vector index: {e}")
                return False

    def setup_all(self) -> dict:
        """Run complete schema setup.

        Returns:
            Dictionary with setup results
        """
        logger.info("Setting up Neo4j schema...")

        if not self._connected:
            self.connect()

        constraints_created = self.create_constraints()
        indexes_created = self.create_indexes()
        vector_created = self.create_vector_index()

        logger.info("Schema setup complete!")

        return {
            "constraints_created": constraints_created,
            "indexes_created": indexes_created,
            "vector_index_created": vector_created,
        }

    def clear_database(self) -> None:
        """Clear all nodes and relationships (for testing)."""
        with self.connection.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.warning("Database cleared!")

    def get_schema_info(self) -> dict:
        """Get current schema information.

        Returns:
            Dictionary with schema details
        """
        with self.connection.session() as session:
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
            "node_counts": {r["label"]: r["count"] for r in counts},
        }

    def get_constraints(self) -> list:
        """Get list of all constraints.

        Returns:
            List of constraint definitions
        """
        with self.connection.session() as session:
            return session.run("SHOW CONSTRAINTS").data()

    def get_indexes(self) -> list:
        """Get list of all indexes.

        Returns:
            List of index definitions
        """
        with self.connection.session() as session:
            return session.run("SHOW INDEXES").data()


def setup_schema() -> dict:
    """Convenience function to setup schema.

    Returns:
        Schema setup results
    """
    manager = SchemaManager()
    manager.connect()
    result = manager.setup_all()
    info = manager.get_schema_info()
    manager.close()
    return {**result, **info}


if __name__ == "__main__":
    info = setup_schema()
    print("\nSchema Setup Results:")
    for key, value in info.items():
        print(f"  {key}: {value}")

