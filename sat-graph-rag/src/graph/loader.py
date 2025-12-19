"""Initial load of constitution into Neo4j graph.

This module loads the parsed constitution JSON into the Neo4j graph,
creating the full node chain: Norm -> Component -> CTV -> CLV -> TextUnit
with proper AGGREGATES relationships between CTVs.
"""

from typing import Dict, List, Optional
from pathlib import Path
import json
import logging
import hashlib

from .connection import get_connection, Neo4jConnection
from .schema import SchemaManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConstitutionLoader:
    """Loads parsed constitution into Neo4j graph."""

    def __init__(self, conn: Optional[Neo4jConnection] = None):
        self.conn = conn or get_connection()
        self.stats = {
            "norms": 0,
            "components": 0,
            "ctvs": 0,
            "clvs": 0,
            "text_units": 0,
            "relationships": 0,
        }

    def load_from_json(
        self,
        json_path: str = "data/intermediate/constitution.json",
        enactment_date: str = "1988-10-05",
    ) -> dict:
        """Load constitution from parsed JSON.

        Args:
            json_path: Path to parsed constitution JSON
            enactment_date: Date the constitution was enacted

        Returns:
            Statistics about loaded nodes and relationships
        """
        logger.info(f"Loading constitution from {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create Norm node
        norm_id = data.get("official_id", "CF1988")
        self._create_norm(
            official_id=norm_id,
            name=data.get("name", "Constituição da República Federativa do Brasil"),
            enactment_date=enactment_date,
        )

        # Process top-level components (Titles)
        for idx, component in enumerate(data.get("components", [])):
            self._load_component(
                component=component,
                norm_id=norm_id,
                parent_id=None,
                parent_ctv_id=None,
                enactment_date=enactment_date,
                ordering=idx + 1,
            )

        logger.info(f"Load complete. Stats: {self.stats}")
        return self.stats

    def _create_norm(self, official_id: str, name: str, enactment_date: str):
        """Create the Norm node."""
        query = """
        MERGE (n:Norm {official_id: $official_id})
        ON CREATE SET
            n.name = $name,
            n.enactment_date = date($enactment_date),
            n.jurisdiction = 'Brazil',
            n.document_type = 'Constitution',
            n.created_at = datetime()
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "official_id": official_id,
                    "name": name,
                    "enactment_date": enactment_date,
                },
            )
        self.stats["norms"] += 1
        logger.info(f"Created Norm: {official_id}")

    def _load_component(
        self,
        component: dict,
        norm_id: str,
        parent_id: Optional[str],
        parent_ctv_id: Optional[str],
        enactment_date: str,
        ordering: int,
    ) -> str:
        """Recursively load a component and its children.

        Returns:
            The CTV ID of the created version
        """
        comp_id = component.get("component_id")
        comp_type = component.get("component_type")
        ordering_id = component.get("ordering_id", "")

        # Create Component node
        self._create_component(
            component_id=comp_id,
            component_type=comp_type,
            ordering_id=ordering_id,
            norm_id=norm_id,
            parent_id=parent_id,
        )

        # Create CTV (version)
        ctv_id = f"{comp_id}_v1"
        is_original = component.get("is_original", True)

        # Get events (amendment markers)
        events = component.get("events", [])

        self._create_ctv(
            ctv_id=ctv_id,
            component_id=comp_id,
            version_number=1,
            date_start=enactment_date,
            is_original=is_original,
            events=events,
        )

        # Create CLV (language version)
        clv_id = f"{ctv_id}_pt"
        self._create_clv(clv_id=clv_id, ctv_id=ctv_id, language="pt")

        # Create TextUnit
        text_id = f"{clv_id}_text"
        self._create_text_unit(
            text_id=text_id,
            clv_id=clv_id,
            header=component.get("header"),
            content=component.get("content"),
            full_text=component.get("full_text", ""),
        )

        # Link to parent CTV via AGGREGATES
        if parent_ctv_id:
            self._create_aggregation(parent_ctv_id, ctv_id, ordering)
        else:
            # Top-level: link to Norm
            self._link_to_norm(norm_id, comp_id)

        # Process children recursively
        children = component.get("children", [])
        for idx, child in enumerate(children):
            self._load_component(
                component=child,
                norm_id=norm_id,
                parent_id=comp_id,
                parent_ctv_id=ctv_id,
                enactment_date=enactment_date,
                ordering=idx + 1,
            )

        return ctv_id

    def _create_component(
        self,
        component_id: str,
        component_type: str,
        ordering_id: str,
        norm_id: str,
        parent_id: Optional[str],
    ):
        """Create a Component node."""
        query = """
        MERGE (c:Component {component_id: $component_id})
        ON CREATE SET
            c.component_type = $component_type,
            c.ordering_id = $ordering_id,
            c.norm_id = $norm_id,
            c.parent_id = $parent_id,
            c.created_at = datetime()
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "component_id": component_id,
                    "component_type": component_type,
                    "ordering_id": ordering_id,
                    "norm_id": norm_id,
                    "parent_id": parent_id,
                },
            )
        self.stats["components"] += 1

        # Create HAS_CHILD relationship if has parent
        if parent_id:
            with self.conn.session() as session:
                session.run(
                    """
                    MATCH (parent:Component {component_id: $parent_id})
                    MATCH (child:Component {component_id: $child_id})
                    MERGE (parent)-[:HAS_CHILD]->(child)
                    """,
                    {"parent_id": parent_id, "child_id": component_id},
                )
            self.stats["relationships"] += 1

    def _create_ctv(
        self,
        ctv_id: str,
        component_id: str,
        version_number: int,
        date_start: str,
        is_original: bool,
        events: list,
    ):
        """Create a CTV (temporal version) node."""
        query = """
        MATCH (c:Component {component_id: $component_id})
        MERGE (v:CTV {ctv_id: $ctv_id})
        ON CREATE SET
            v.component_id = $component_id,
            v.version_number = $version_number,
            v.date_start = date($date_start),
            v.date_end = null,
            v.is_active = true,
            v.is_original = $is_original,
            v.amendment_numbers = $amendment_numbers,
            v.created_at = datetime()
        MERGE (c)-[:HAS_VERSION]->(v)
        """

        amendment_numbers = [
            e.get("amendment_number") for e in events if e.get("amendment_number")
        ]

        with self.conn.session() as session:
            session.run(
                query,
                {
                    "ctv_id": ctv_id,
                    "component_id": component_id,
                    "version_number": version_number,
                    "date_start": date_start,
                    "is_original": is_original,
                    "amendment_numbers": amendment_numbers,
                },
            )
        self.stats["ctvs"] += 1
        self.stats["relationships"] += 1

    def _create_clv(self, clv_id: str, ctv_id: str, language: str):
        """Create a CLV (language version) node."""
        query = """
        MATCH (v:CTV {ctv_id: $ctv_id})
        MERGE (l:CLV {clv_id: $clv_id})
        ON CREATE SET
            l.ctv_id = $ctv_id,
            l.language = $language,
            l.created_at = datetime()
        MERGE (v)-[:EXPRESSED_IN]->(l)
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "clv_id": clv_id,
                    "ctv_id": ctv_id,
                    "language": language,
                },
            )
        self.stats["clvs"] += 1
        self.stats["relationships"] += 1

    def _create_text_unit(
        self,
        text_id: str,
        clv_id: str,
        header: Optional[str],
        content: Optional[str],
        full_text: str,
    ):
        """Create a TextUnit node."""
        # Create content hash for deduplication
        content_hash = hashlib.md5(full_text.encode()).hexdigest()[:16]

        query = """
        MATCH (l:CLV {clv_id: $clv_id})
        MERGE (t:TextUnit {text_id: $text_id})
        ON CREATE SET
            t.clv_id = $clv_id,
            t.header = $header,
            t.content = $content,
            t.full_text = $full_text,
            t.char_count = size($full_text),
            t.content_hash = $content_hash,
            t.created_at = datetime()
        MERGE (l)-[:HAS_TEXT]->(t)
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "text_id": text_id,
                    "clv_id": clv_id,
                    "header": header,
                    "content": content,
                    "full_text": full_text,
                    "content_hash": content_hash,
                },
            )
        self.stats["text_units"] += 1
        self.stats["relationships"] += 1

    def _create_aggregation(
        self, parent_ctv_id: str, child_ctv_id: str, ordering: int
    ):
        """Create AGGREGATES relationship between CTVs."""
        query = """
        MATCH (parent:CTV {ctv_id: $parent_id})
        MATCH (child:CTV {ctv_id: $child_id})
        MERGE (parent)-[:AGGREGATES {ordering: $ordering}]->(child)
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "parent_id": parent_ctv_id,
                    "child_id": child_ctv_id,
                    "ordering": ordering,
                },
            )
        self.stats["relationships"] += 1

    def _link_to_norm(self, norm_id: str, component_id: str):
        """Link top-level component to Norm."""
        query = """
        MATCH (n:Norm {official_id: $norm_id})
        MATCH (c:Component {component_id: $component_id})
        MERGE (n)-[:HAS_COMPONENT]->(c)
        """
        with self.conn.session() as session:
            session.run(
                query,
                {
                    "norm_id": norm_id,
                    "component_id": component_id,
                },
            )
        self.stats["relationships"] += 1


def load_constitution(
    json_path: str = "data/intermediate/constitution.json",
) -> dict:
    """Convenience function to load constitution.

    Args:
        json_path: Path to parsed constitution JSON

    Returns:
        Load statistics
    """
    # Setup schema first
    manager = SchemaManager()
    manager.connect()
    manager.setup_all()
    manager.close()

    # Load data
    loader = ConstitutionLoader()
    return loader.load_from_json(json_path)


if __name__ == "__main__":
    stats = load_constitution()
    print("\nLoad Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

