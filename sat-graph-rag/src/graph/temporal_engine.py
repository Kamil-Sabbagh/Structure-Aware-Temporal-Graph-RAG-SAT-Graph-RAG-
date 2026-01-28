"""Temporal engine for processing amendments using the aggregation model.

This module implements the core "Aggregation, Not Composition" algorithm from the paper.
When an amendment changes a component:
1. Create new CTV for the changed component
2. Close the old CTV
3. Propagate up to ancestors, creating new ancestor CTVs
4. REUSE unchanged sibling CTVs (don't duplicate!)

This ensures that unchanged components don't get duplicated across amendments.
"""

from typing import List, Dict, Set, Optional
from datetime import date
import logging

from .connection import get_connection, Neo4jConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemporalEngine:
    """
    Handles temporal versioning using the Aggregation model.

    Key principle: When a component changes, create new CTVs for:
    1. The changed component itself
    2. All ancestors up to the root
    But REUSE unchanged sibling CTVs (don't duplicate!)
    """

    def __init__(self, conn: Optional[Neo4jConnection] = None):
        self.conn = conn or get_connection()
        self.stats = {
            "new_ctvs": 0,
            "closed_ctvs": 0,
            "reused_ctvs": 0,
            "new_aggregations": 0,
            "actions_created": 0,
        }

    def apply_amendment(
        self,
        amendment_number: int,
        amendment_date: str,
        changes: List[Dict],
        description: str = ""
    ) -> dict:
        """
        Apply an amendment that modifies one or more components.

        Args:
            amendment_number: EC number (e.g., 45)
            amendment_date: Date string "YYYY-MM-DD"
            changes: List of {component_id, new_content, change_type}
            description: Amendment description

        Returns:
            Statistics about the changes made
        """
        logger.info(f"Applying EC {amendment_number} ({amendment_date})")

        # Create Action node
        action_id = f"ec_{amendment_number}"
        self._create_action(
            action_id=action_id,
            amendment_number=amendment_number,
            amendment_date=amendment_date,
            description=description,
            affected_components=[c["component_id"] for c in changes]
        )

        # Track which components need new parent CTVs
        affected_ancestors: Set[str] = set()

        # Process each changed component
        for change in changes:
            comp_id = change["component_id"]
            new_content = change.get("new_content", "")
            change_type = change.get("change_type", "modify")

            # Create new CTV for the changed component
            new_ctv_id = self._create_new_version(
                component_id=comp_id,
                date_start=amendment_date,
                new_content=new_content,
                change_type=change_type,
                amendment_number=amendment_number
            )

            if new_ctv_id:
                # Link action to new CTV
                self._link_action_to_ctv(action_id, new_ctv_id)

                # Collect ancestors that need updating
                ancestors = self._get_ancestor_chain(comp_id)
                affected_ancestors.update(ancestors)

        # Process ancestors from bottom up
        # This ensures child CTVs exist before parent CTVs aggregate them
        sorted_ancestors = self._sort_by_depth(affected_ancestors, reverse=True)

        for ancestor_id in sorted_ancestors:
            self._update_ancestor_aggregation(
                component_id=ancestor_id,
                amendment_date=amendment_date,
                amendment_number=amendment_number
            )

        logger.info(f"Amendment applied. Stats: {self.stats}")
        return self.stats

    def _create_action(
        self,
        action_id: str,
        amendment_number: int,
        amendment_date: str,
        description: str,
        affected_components: List[str]
    ):
        """Create an Action node for the amendment."""
        query = """
        MERGE (a:Action {action_id: $action_id})
        ON CREATE SET
            a.action_type = 'amendment',
            a.amendment_number = $amendment_number,
            a.amendment_date = date($amendment_date),
            a.description = $description,
            a.affected_components = $affected_components,
            a.created_at = datetime()
        """
        with self.conn.session() as session:
            session.run(query, {
                "action_id": action_id,
                "amendment_number": amendment_number,
                "amendment_date": amendment_date,
                "description": description,
                "affected_components": affected_components
            })
        self.stats["actions_created"] += 1

    def _create_new_version(
        self,
        component_id: str,
        date_start: str,
        new_content: str,
        change_type: str,
        amendment_number: int
    ) -> Optional[str]:
        """
        Create a new CTV for a changed component.
        Also closes the previous version.

        Returns:
            The new CTV ID, or None if failed
        """
        # Get current version number
        query = """
        MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
        WHERE v.is_active = true
        RETURN v.ctv_id AS current_ctv, v.version_number AS version
        LIMIT 1
        """

        with self.conn.session() as session:
            result = list(session.run(query, {"comp_id": component_id}))

        if not result:
            logger.error(f"No active CTV found for {component_id}")
            return None

        current_ctv_id = result[0]["current_ctv"]
        current_version = result[0]["version"]
        new_version = current_version + 1
        new_ctv_id = f"{component_id}_v{new_version}"

        # Close the current version
        with self.conn.session() as session:
            session.run("""
                MATCH (v:CTV {ctv_id: $ctv_id})
                SET v.date_end = date($end_date),
                    v.is_active = false
            """, {"ctv_id": current_ctv_id, "end_date": date_start})
        self.stats["closed_ctvs"] += 1

        # Create new version
        is_repeal = change_type == "repeal"

        with self.conn.session() as session:
            session.run("""
                MATCH (c:Component {component_id: $comp_id})
                CREATE (v:CTV {
                    ctv_id: $ctv_id,
                    component_id: $comp_id,
                    version_number: $version,
                    date_start: date($date_start),
                    date_end: null,
                    is_active: true,
                    is_original: false,
                    created_by_action: 'amendment',
                    amendment_number: $amendment_number,
                    is_repealed: $is_repeal,
                    created_at: datetime()
                })
                CREATE (c)-[:HAS_VERSION]->(v)
                WITH v
                MATCH (prev:CTV {ctv_id: $prev_ctv})
                CREATE (v)-[:SUPERSEDES]->(prev)
            """, {
                "ctv_id": new_ctv_id,
                "comp_id": component_id,
                "version": new_version,
                "date_start": date_start,
                "amendment_number": amendment_number,
                "is_repeal": is_repeal,
                "prev_ctv": current_ctv_id
            })
        self.stats["new_ctvs"] += 1

        # Create CLV and TextUnit for new version (if not repealed)
        if not is_repeal and new_content:
            clv_id = f"{new_ctv_id}_pt"
            text_id = f"{clv_id}_text"

            with self.conn.session() as session:
                session.run("""
                    MATCH (v:CTV {ctv_id: $ctv_id})
                    CREATE (l:CLV {
                        clv_id: $clv_id,
                        ctv_id: $ctv_id,
                        language: 'pt',
                        created_at: datetime()
                    })
                    CREATE (t:TextUnit {
                        text_id: $text_id,
                        clv_id: $clv_id,
                        full_text: $content,
                        char_count: size($content),
                        created_at: datetime()
                    })
                    CREATE (v)-[:EXPRESSED_IN]->(l)
                    CREATE (l)-[:HAS_TEXT]->(t)
                """, {
                    "ctv_id": new_ctv_id,
                    "clv_id": clv_id,
                    "text_id": text_id,
                    "content": new_content
                })

        return new_ctv_id

    def _get_ancestor_chain(self, component_id: str) -> List[str]:
        """Get all ancestors of a component up to root."""
        query = """
        MATCH (c:Component {component_id: $comp_id})
        MATCH path = (c)<-[:HAS_CHILD*]-(ancestor:Component)
        RETURN ancestor.component_id AS ancestor_id,
               length(path) AS depth
        ORDER BY depth ASC
        """

        with self.conn.session() as session:
            result = list(session.run(query, {"comp_id": component_id}))

        return [r["ancestor_id"] for r in result]

    def _sort_by_depth(self, component_ids: Set[str], reverse: bool = False) -> List[str]:
        """Sort components by their depth in hierarchy."""
        if not component_ids:
            return []

        query = """
        UNWIND $comp_ids AS comp_id
        MATCH (c:Component {component_id: comp_id})
        OPTIONAL MATCH path = (c)<-[:HAS_CHILD*]-(root:Component)
        WHERE NOT (:Component)-[:HAS_CHILD]->(root)
        RETURN comp_id,
               CASE WHEN path IS NULL THEN 0 ELSE length(path) END AS depth
        ORDER BY depth
        """

        with self.conn.session() as session:
            result = list(session.run(query, {"comp_ids": list(component_ids)}))

        sorted_ids = [r["comp_id"] for r in result]
        if reverse:
            sorted_ids.reverse()
        return sorted_ids

    def _update_ancestor_aggregation(
        self,
        component_id: str,
        amendment_date: str,
        amendment_number: int
    ):
        """
        Update an ancestor's aggregation by creating a new CTV
        that aggregates the new child CTVs while REUSING unchanged ones.

        This is the KEY INNOVATION - unchanged children are reused!
        """
        # Get current version
        query = """
        MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
        WHERE v.is_active = true
        RETURN v.ctv_id AS current_ctv, v.version_number AS version
        LIMIT 1
        """

        with self.conn.session() as session:
            result = list(session.run(query, {"comp_id": component_id}))

        if not result:
            logger.warning(f"No active CTV for ancestor {component_id}")
            return

        current_ctv_id = result[0]["current_ctv"]
        current_version = result[0]["version"]
        new_version = current_version + 1
        new_ctv_id = f"{component_id}_v{new_version}"

        # Close current version
        with self.conn.session() as session:
            session.run("""
                MATCH (v:CTV {ctv_id: $ctv_id})
                SET v.date_end = date($end_date),
                    v.is_active = false
            """, {"ctv_id": current_ctv_id, "end_date": amendment_date})
        self.stats["closed_ctvs"] += 1

        # Create new ancestor CTV
        with self.conn.session() as session:
            session.run("""
                MATCH (c:Component {component_id: $comp_id})
                CREATE (v:CTV {
                    ctv_id: $ctv_id,
                    component_id: $comp_id,
                    version_number: $version,
                    date_start: date($date_start),
                    date_end: null,
                    is_active: true,
                    is_original: false,
                    created_by_action: 'amendment_propagation',
                    amendment_number: $amendment_number,
                    created_at: datetime()
                })
                CREATE (c)-[:HAS_VERSION]->(v)
                WITH v
                MATCH (prev:CTV {ctv_id: $prev_ctv})
                CREATE (v)-[:SUPERSEDES]->(prev)
            """, {
                "ctv_id": new_ctv_id,
                "comp_id": component_id,
                "version": new_version,
                "date_start": amendment_date,
                "amendment_number": amendment_number,
                "prev_ctv": current_ctv_id
            })
        self.stats["new_ctvs"] += 1

        # Copy CLV and TextUnit from previous version (content unchanged for ancestor)
        with self.conn.session() as session:
            session.run("""
                MATCH (prev:CTV {ctv_id: $prev_ctv})-[:EXPRESSED_IN]->(prev_clv:CLV)-[:HAS_TEXT]->(prev_text:TextUnit)
                MATCH (new:CTV {ctv_id: $new_ctv})
                CREATE (new_clv:CLV {
                    clv_id: $new_ctv + '_pt',
                    ctv_id: $new_ctv,
                    language: prev_clv.language,
                    created_at: datetime()
                })
                CREATE (new_text:TextUnit {
                    text_id: $new_ctv + '_pt_text',
                    clv_id: $new_ctv + '_pt',
                    full_text: prev_text.full_text,
                    header: prev_text.header,
                    content: prev_text.content,
                    char_count: prev_text.char_count,
                    created_at: datetime()
                })
                CREATE (new)-[:EXPRESSED_IN]->(new_clv)
                CREATE (new_clv)-[:HAS_TEXT]->(new_text)
            """, {"prev_ctv": current_ctv_id, "new_ctv": new_ctv_id})

        # KEY: Create aggregation relationships
        # For each child, use the ACTIVE version (which may be new or old)
        with self.conn.session() as session:
            result = session.run("""
                MATCH (new_parent:CTV {ctv_id: $new_ctv})
                MATCH (parent_comp:Component {component_id: $comp_id})
                MATCH (parent_comp)-[:HAS_CHILD]->(child_comp:Component)
                MATCH (child_comp)-[:HAS_VERSION]->(child_ctv:CTV {is_active: true})

                // Get ordering from old relationship or default
                OPTIONAL MATCH (old_parent:CTV {ctv_id: $old_ctv})-[old_rel:AGGREGATES]->(old_child:CTV)
                WHERE old_child.component_id = child_comp.component_id

                WITH new_parent, child_ctv, COALESCE(old_rel.ordering, 0) AS ordering
                CREATE (new_parent)-[:AGGREGATES {ordering: ordering}]->(child_ctv)
                RETURN count(*) AS created
            """, {
                "new_ctv": new_ctv_id,
                "comp_id": component_id,
                "old_ctv": current_ctv_id
            })

            aggregations_created = result.single()["created"]
            self.stats["new_aggregations"] += aggregations_created

        # Count reused CTVs (children that weren't changed)
        with self.conn.session() as session:
            result = list(session.run("""
                MATCH (v:CTV {ctv_id: $new_ctv})-[:AGGREGATES]->(child:CTV)
                WHERE child.date_start < date($date_start)
                RETURN count(child) AS reused
            """, {"new_ctv": new_ctv_id, "date_start": amendment_date}))

        if result:
            self.stats["reused_ctvs"] += result[0]["reused"]

    def _link_action_to_ctv(self, action_id: str, ctv_id: str):
        """Link Action to resulting CTV."""
        with self.conn.session() as session:
            session.run("""
                MATCH (a:Action {action_id: $action_id})
                MATCH (v:CTV {ctv_id: $ctv_id})
                MERGE (a)-[:RESULTED_IN]->(v)
            """, {"action_id": action_id, "ctv_id": ctv_id})


def apply_amendment(
    amendment_number: int,
    amendment_date: str,
    changes: List[Dict],
    description: str = ""
) -> dict:
    """Convenience function to apply an amendment."""
    engine = TemporalEngine()
    return engine.apply_amendment(
        amendment_number=amendment_number,
        amendment_date=amendment_date,
        changes=changes,
        description=description
    )
