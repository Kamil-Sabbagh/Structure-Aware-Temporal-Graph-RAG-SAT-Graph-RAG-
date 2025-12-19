"""Neo4j database connection management."""

import os
from contextlib import contextmanager
from typing import Generator

from neo4j import GraphDatabase, Driver, Session


class Neo4jConnection:
    """Manages Neo4j database connections."""
    
    _driver: Driver | None = None
    
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """Initialize the connection with credentials.
        
        Args:
            uri: Neo4j bolt URI (defaults to NEO4J_URI env var)
            user: Neo4j username (defaults to NEO4J_USER env var)
            password: Neo4j password (defaults to NEO4J_PASSWORD env var)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "satgraphrag123")
    
    def connect(self) -> Driver:
        """Establish connection to Neo4j.
        
        Returns:
            Neo4j driver instance
        """
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
        return self._driver
    
    def close(self) -> None:
        """Close the database connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
    
    @contextmanager
    def session(self, database: str = "neo4j") -> Generator[Session, None, None]:
        """Get a database session.
        
        Args:
            database: Database name to connect to
            
        Yields:
            Neo4j session
        """
        driver = self.connect()
        session = driver.session(database=database)
        try:
            yield session
        finally:
            session.close()
    
    def verify_connection(self) -> bool:
        """Verify that the connection is working.
        
        Returns:
            True if connection is successful
        """
        try:
            with self.session() as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                return record["test"] == 1
        except Exception:
            return False
    
    def verify_apoc(self) -> bool:
        """Verify that APOC plugin is installed.
        
        Returns:
            True if APOC is available
        """
        try:
            with self.session() as session:
                result = session.run("RETURN apoc.version() AS version")
                record = result.single()
                return record["version"] is not None
        except Exception:
            return False


# Global connection instance
_connection: Neo4jConnection | None = None


def get_connection() -> Neo4jConnection:
    """Get the global Neo4j connection instance.
    
    Returns:
        Neo4jConnection instance
    """
    global _connection
    if _connection is None:
        _connection = Neo4jConnection()
    return _connection

