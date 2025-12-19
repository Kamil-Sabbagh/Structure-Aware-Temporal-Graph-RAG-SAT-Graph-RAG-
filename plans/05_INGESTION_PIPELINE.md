# Phase 4: Ingestion Pipeline (SAT Logic)

## Objective
Implement the "Aggregation, Not Composition" ingestion logic that populates the graph while minimizing node duplication when amendments occur.

---

## 4.1 The Core Algorithm

### 4.1.1 First Load (Original Enactment)

When loading the original 1988 constitution:

```
1. Create Norm node
2. For each top-level component (Title):
   a. Create Component node
   b. Create CTV with date_start=1988-10-05
   c. Create CLV (Portuguese)
   d. Create TextUnit
   e. Recursively process children
   f. Parent CTV AGGREGATES child CTVs
```

### 4.1.2 Amendment Processing (The Key Innovation)

When processing an amendment that modifies Article 5:

```
1. Identify changed component (Article 5)
2. Create new CTV for Article 5 (date_start=amendment_date)
3. Close old CTV (date_end=amendment_date, is_active=false)
4. PROPAGATE UP the hierarchy:
   a. Create new CTV for Chapter I (parent of Article 5)
   b. New Chapter CTV AGGREGATES:
      - New Article 5 CTV (the changed one)
      - Old Article 6 CTV (REUSED - not duplicated!)
      - Old Article 7 CTV (REUSED)
      - ... all unchanged children
   c. Create new CTV for Title II (parent of Chapter I)
   d. Repeat until Norm root
5. Record Action node linking to new CTVs
```

### 4.1.3 The Re-use Principle

```python
# WRONG: Composition (creates new nodes for everything)
def update_composition(component, new_content):
    new_ctv = create_ctv(component)
    for child in component.children:
        new_child_ctv = create_ctv(child)  # Duplicates!
        new_ctv.add_child(new_child_ctv)

# CORRECT: Aggregation (reuses unchanged nodes)
def update_aggregation(component, new_content, change_date):
    new_ctv = create_ctv(component, date_start=change_date)
    
    for child in component.children:
        if child.was_changed:
            child_ctv = update_aggregation(child, child.new_content, change_date)
        else:
            child_ctv = get_current_ctv(child)  # Reuse existing!
        
        new_ctv.aggregates(child_ctv)
    
    return new_ctv
```

---

## 4.2 Implementation

### 4.2.1 Graph Loader (Initial Load)

**File:** `src/graph/loader.py`

```python
"""Initial load of constitution into Neo4j graph."""

from typing import Dict, List, Optional
from pathlib import Path
from datetime import date
import json
import logging

from .connection import get_connection
from .schema import SchemaManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConstitutionLoader:
    """Loads parsed constitution into Neo4j graph."""
    
    def __init__(self, conn=None):
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
        enactment_date: str = "1988-10-05"
    ) -> dict:
        """Load constitution from parsed JSON."""
        logger.info(f"Loading constitution from {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create Norm node
        norm_id = data.get("official_id", "CF1988")
        self._create_norm(
            official_id=norm_id,
            name=data.get("name", "Constituição"),
            enactment_date=enactment_date
        )
        
        # Process top-level components (Titles)
        for component in data.get("components", []):
            self._load_component(
                component=component,
                norm_id=norm_id,
                parent_id=None,
                parent_ctv_id=None,
                enactment_date=enactment_date,
                ordering=0
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
            n.created_at = datetime()
        """
        self.conn.execute_write(query, {
            "official_id": official_id,
            "name": name,
            "enactment_date": enactment_date
        })
        self.stats["norms"] += 1
        logger.info(f"Created Norm: {official_id}")
    
    def _load_component(
        self,
        component: dict,
        norm_id: str,
        parent_id: Optional[str],
        parent_ctv_id: Optional[str],
        enactment_date: str,
        ordering: int
    ) -> str:
        """
        Recursively load a component and its children.
        
        Returns:
            The CTV ID of the created version
        """
        comp_id = component.get("component_id")
        comp_type = component.get("component_type")
        ordering_id = component.get("ordering_id")
        
        # Create Component node
        self._create_component(
            component_id=comp_id,
            component_type=comp_type,
            ordering_id=ordering_id,
            norm_id=norm_id,
            parent_id=parent_id
        )
        
        # Create CTV (version)
        ctv_id = f"{comp_id}_v1"
        is_original = component.get("is_original", True)
        
        # Determine actual start date
        if is_original:
            start_date = enactment_date
        else:
            # Use first amendment date if available
            events = component.get("events", [])
            if events:
                start_date = self._parse_event_date(events[0]) or enactment_date
            else:
                start_date = enactment_date
        
        self._create_ctv(
            ctv_id=ctv_id,
            component_id=comp_id,
            version_number=1,
            date_start=start_date,
            is_original=is_original,
            events=component.get("events", [])
        )
        
        # Create CLV (language version)
        clv_id = f"{ctv_id}_pt"
        self._create_clv(
            clv_id=clv_id,
            ctv_id=ctv_id,
            language="pt"
        )
        
        # Create TextUnit
        text_id = f"{clv_id}_text"
        self._create_text_unit(
            text_id=text_id,
            clv_id=clv_id,
            header=component.get("header"),
            content=component.get("content"),
            full_text=component.get("full_text", "")
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
                ordering=idx + 1
            )
        
        return ctv_id
    
    def _create_component(
        self,
        component_id: str,
        component_type: str,
        ordering_id: str,
        norm_id: str,
        parent_id: Optional[str]
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
        self.conn.execute_write(query, {
            "component_id": component_id,
            "component_type": component_type,
            "ordering_id": ordering_id,
            "norm_id": norm_id,
            "parent_id": parent_id
        })
        self.stats["components"] += 1
        
        # Create HAS_CHILD relationship if has parent
        if parent_id:
            self.conn.execute_write("""
                MATCH (parent:Component {component_id: $parent_id})
                MATCH (child:Component {component_id: $child_id})
                MERGE (parent)-[:HAS_CHILD]->(child)
            """, {"parent_id": parent_id, "child_id": component_id})
            self.stats["relationships"] += 1
    
    def _create_ctv(
        self,
        ctv_id: str,
        component_id: str,
        version_number: int,
        date_start: str,
        is_original: bool,
        events: list
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
        
        amendment_numbers = [e.get("amendment_number") for e in events if e.get("amendment_number")]
        
        self.conn.execute_write(query, {
            "ctv_id": ctv_id,
            "component_id": component_id,
            "version_number": version_number,
            "date_start": date_start,
            "is_original": is_original,
            "amendment_numbers": amendment_numbers
        })
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
        self.conn.execute_write(query, {
            "clv_id": clv_id,
            "ctv_id": ctv_id,
            "language": language
        })
        self.stats["clvs"] += 1
        self.stats["relationships"] += 1
    
    def _create_text_unit(
        self,
        text_id: str,
        clv_id: str,
        header: Optional[str],
        content: Optional[str],
        full_text: str
    ):
        """Create a TextUnit node."""
        query = """
        MATCH (l:CLV {clv_id: $clv_id})
        MERGE (t:TextUnit {text_id: $text_id})
        ON CREATE SET
            t.clv_id = $clv_id,
            t.header = $header,
            t.content = $content,
            t.full_text = $full_text,
            t.char_count = size($full_text),
            t.created_at = datetime()
        MERGE (l)-[:HAS_TEXT]->(t)
        """
        self.conn.execute_write(query, {
            "text_id": text_id,
            "clv_id": clv_id,
            "header": header,
            "content": content,
            "full_text": full_text
        })
        self.stats["text_units"] += 1
        self.stats["relationships"] += 1
    
    def _create_aggregation(self, parent_ctv_id: str, child_ctv_id: str, ordering: int):
        """Create AGGREGATES relationship between CTVs."""
        query = """
        MATCH (parent:CTV {ctv_id: $parent_id})
        MATCH (child:CTV {ctv_id: $child_id})
        MERGE (parent)-[:AGGREGATES {ordering: $ordering}]->(child)
        """
        self.conn.execute_write(query, {
            "parent_id": parent_ctv_id,
            "child_id": child_ctv_id,
            "ordering": ordering
        })
        self.stats["relationships"] += 1
    
    def _link_to_norm(self, norm_id: str, component_id: str):
        """Link top-level component to Norm."""
        query = """
        MATCH (n:Norm {official_id: $norm_id})
        MATCH (c:Component {component_id: $component_id})
        MERGE (n)-[:HAS_COMPONENT]->(c)
        """
        self.conn.execute_write(query, {
            "norm_id": norm_id,
            "component_id": component_id
        })
        self.stats["relationships"] += 1
    
    def _parse_event_date(self, event: dict) -> Optional[str]:
        """Parse date from amendment event."""
        date_str = event.get("amendment_date_str", "")
        
        # Try to parse various formats
        import re
        
        # Try DD.MM.YYYY
        match = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try just year
        match = re.match(r'(\d{4})', date_str)
        if match:
            return f"{match.group(1)}-01-01"
        
        return None


def load_constitution(json_path: str = "data/intermediate/constitution.json"):
    """Convenience function to load constitution."""
    # Setup schema first
    SchemaManager().setup_all()
    
    # Load data
    loader = ConstitutionLoader()
    return loader.load_from_json(json_path)


if __name__ == "__main__":
    stats = load_constitution()
    print("\nLoad Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
```

### 4.2.2 Temporal Engine (Amendment Processing)

**File:** `src/graph/temporal_engine.py`

```python
"""Temporal engine for processing amendments using aggregation logic."""

from typing import List, Optional, Dict, Set
from datetime import date
import logging

from .connection import get_connection

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
    
    def __init__(self, conn=None):
        self.conn = conn or get_connection()
        self.stats = {
            "new_ctvs": 0,
            "closed_ctvs": 0,
            "reused_ctvs": 0,
            "new_aggregations": 0,
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
        self.conn.execute_write(query, {
            "action_id": action_id,
            "amendment_number": amendment_number,
            "amendment_date": amendment_date,
            "description": description,
            "affected_components": affected_components
        })
    
    def _create_new_version(
        self,
        component_id: str,
        date_start: str,
        new_content: str,
        change_type: str,
        amendment_number: int
    ) -> str:
        """
        Create a new CTV for a changed component.
        Also closes the previous version.
        
        Returns:
            The new CTV ID
        """
        # Get current version number
        result = self.conn.execute_query("""
            MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
            WHERE v.is_active = true
            RETURN v.ctv_id AS current_ctv, v.version_number AS version
        """, {"comp_id": component_id})
        
        if not result:
            logger.error(f"No active CTV found for {component_id}")
            return None
        
        current_ctv_id = result[0]["current_ctv"]
        current_version = result[0]["version"]
        new_version = current_version + 1
        new_ctv_id = f"{component_id}_v{new_version}"
        
        # Close the current version
        self.conn.execute_write("""
            MATCH (v:CTV {ctv_id: $ctv_id})
            SET v.date_end = date($end_date),
                v.is_active = false
        """, {"ctv_id": current_ctv_id, "end_date": date_start})
        self.stats["closed_ctvs"] += 1
        
        # Create new version
        is_repeal = change_type == "repeal"
        
        self.conn.execute_write("""
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
        
        # Create CLV and TextUnit for new version
        if not is_repeal and new_content:
            clv_id = f"{new_ctv_id}_pt"
            text_id = f"{clv_id}_text"
            
            self.conn.execute_write("""
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
        result = self.conn.execute_query("""
            MATCH (c:Component {component_id: $comp_id})
            MATCH path = (c)<-[:HAS_CHILD*]-(ancestor:Component)
            RETURN ancestor.component_id AS ancestor_id,
                   length(path) AS depth
            ORDER BY depth ASC
        """, {"comp_id": component_id})
        
        return [r["ancestor_id"] for r in result]
    
    def _sort_by_depth(self, component_ids: Set[str], reverse: bool = False) -> List[str]:
        """Sort components by their depth in hierarchy."""
        result = self.conn.execute_query("""
            UNWIND $comp_ids AS comp_id
            MATCH (c:Component {component_id: comp_id})
            OPTIONAL MATCH path = (c)<-[:HAS_CHILD*]-(root:Component)
            WHERE NOT (:Component)-[:HAS_CHILD]->(root)
            RETURN comp_id,
                   CASE WHEN path IS NULL THEN 0 ELSE length(path) END AS depth
            ORDER BY depth
        """, {"comp_ids": list(component_ids)})
        
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
        """
        # Get current version
        result = self.conn.execute_query("""
            MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
            WHERE v.is_active = true
            RETURN v.ctv_id AS current_ctv, v.version_number AS version
        """, {"comp_id": component_id})
        
        if not result:
            return
        
        current_ctv_id = result[0]["current_ctv"]
        current_version = result[0]["version"]
        new_version = current_version + 1
        new_ctv_id = f"{component_id}_v{new_version}"
        
        # Close current version
        self.conn.execute_write("""
            MATCH (v:CTV {ctv_id: $ctv_id})
            SET v.date_end = date($end_date),
                v.is_active = false
        """, {"ctv_id": current_ctv_id, "end_date": amendment_date})
        self.stats["closed_ctvs"] += 1
        
        # Create new ancestor CTV
        self.conn.execute_write("""
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
        self.conn.execute_write("""
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
        self.conn.execute_write("""
            MATCH (new_parent:CTV {ctv_id: $new_ctv})
            MATCH (parent_comp:Component {component_id: $comp_id})
            MATCH (parent_comp)-[:HAS_CHILD]->(child_comp:Component)
            MATCH (child_comp)-[:HAS_VERSION]->(child_ctv:CTV {is_active: true})
            
            // Get ordering from old relationship or default
            OPTIONAL MATCH (old_parent:CTV {ctv_id: $old_ctv})-[old_rel:AGGREGATES]->(old_child:CTV)
            WHERE old_child.component_id = child_comp.component_id
            
            WITH new_parent, child_ctv, COALESCE(old_rel.ordering, 0) AS ordering
            CREATE (new_parent)-[:AGGREGATES {ordering: ordering}]->(child_ctv)
        """, {
            "new_ctv": new_ctv_id,
            "comp_id": component_id,
            "old_ctv": current_ctv_id
        })
        
        # Count reused CTVs (children that weren't changed)
        result = self.conn.execute_query("""
            MATCH (v:CTV {ctv_id: $new_ctv})-[:AGGREGATES]->(child:CTV)
            WHERE child.date_start < date($date_start)
            RETURN count(child) AS reused
        """, {"new_ctv": new_ctv_id, "date_start": amendment_date})
        
        if result:
            self.stats["reused_ctvs"] += result[0]["reused"]
        
        self.stats["new_aggregations"] += 1
    
    def _link_action_to_ctv(self, action_id: str, ctv_id: str):
        """Link Action to resulting CTV."""
        self.conn.execute_write("""
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
```

---

## 4.3 Batch Amendment Processing

**File:** `src/graph/batch_processor.py`

```python
"""Batch processing of amendments from parsed data."""

from typing import List, Dict
from pathlib import Path
import json
import logging

from .temporal_engine import TemporalEngine
from .connection import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AmendmentBatchProcessor:
    """Process amendments from parsed constitution data."""
    
    def __init__(self):
        self.engine = TemporalEngine()
        self.stats = {
            "amendments_processed": 0,
            "components_updated": 0,
            "errors": []
        }
    
    def process_from_constitution(
        self,
        json_path: str = "data/intermediate/constitution.json"
    ):
        """
        Process amendments embedded in constitution data.
        
        The parsed constitution contains components with 'events' 
        that indicate amendments. We need to replay these in 
        chronological order.
        """
        logger.info("Processing amendments from constitution data...")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Collect all amendment events with their components
        amendment_events = []
        self._collect_events(data.get("components", []), amendment_events)
        
        logger.info(f"Found {len(amendment_events)} amendment events")
        
        # Group by amendment number
        by_amendment: Dict[int, List] = {}
        for event in amendment_events:
            num = event["amendment_number"]
            if num not in by_amendment:
                by_amendment[num] = []
            by_amendment[num].append(event)
        
        # Process in order
        for num in sorted(by_amendment.keys()):
            events = by_amendment[num]
            self._process_amendment_group(num, events)
        
        logger.info(f"Processing complete. Stats: {self.stats}")
        return self.stats
    
    def _collect_events(self, components: List[Dict], events: List[Dict]):
        """Recursively collect amendment events from components."""
        for comp in components:
            for event in comp.get("events", []):
                if event.get("amendment_number"):
                    events.append({
                        "component_id": comp["component_id"],
                        "amendment_number": event["amendment_number"],
                        "amendment_date_str": event.get("amendment_date_str", ""),
                        "event_type": event.get("event_type", "modified"),
                        "content": comp.get("full_text", "")
                    })
            
            # Recurse
            self._collect_events(comp.get("children", []), events)
    
    def _process_amendment_group(self, amendment_number: int, events: List[Dict]):
        """Process all changes for a single amendment."""
        # Get date from first event
        date_str = events[0].get("amendment_date_str", "")
        amendment_date = self._parse_date(date_str, amendment_number)
        
        if not amendment_date:
            logger.warning(f"Could not parse date for EC {amendment_number}: {date_str}")
            return
        
        changes = [
            {
                "component_id": e["component_id"],
                "new_content": e.get("content", ""),
                "change_type": e.get("event_type", "modify")
            }
            for e in events
        ]
        
        try:
            self.engine.apply_amendment(
                amendment_number=amendment_number,
                amendment_date=amendment_date,
                changes=changes,
                description=f"EC {amendment_number}"
            )
            self.stats["amendments_processed"] += 1
            self.stats["components_updated"] += len(changes)
        except Exception as e:
            logger.error(f"Error processing EC {amendment_number}: {e}")
            self.stats["errors"].append({
                "amendment": amendment_number,
                "error": str(e)
            })
    
    def _parse_date(self, date_str: str, amendment_number: int) -> str:
        """Parse date string to YYYY-MM-DD format."""
        import re
        
        # Try DD.MM.YYYY or DD/MM/YYYY
        match = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try just year
        match = re.match(r'(\d{4})', date_str)
        if match:
            return f"{match.group(1)}-01-01"
        
        # Fallback: estimate from amendment number (rough approximation)
        # EC 1-6: 1992-1994
        # EC 7-20: 1995-1998
        # etc.
        if amendment_number <= 6:
            return "1993-01-01"
        elif amendment_number <= 20:
            return "1997-01-01"
        elif amendment_number <= 45:
            return "2003-01-01"
        else:
            return "2010-01-01"


def process_amendments():
    """Convenience function to process amendments."""
    processor = AmendmentBatchProcessor()
    return processor.process_from_constitution()
```

---

## 4.4 Validation Checks

### Check 4.4.1: Initial Load Tests

**File:** `tests/integration/test_ingestion.py`

```python
"""Tests for ingestion pipeline."""

import pytest
from pathlib import Path

from src.graph.loader import ConstitutionLoader, load_constitution
from src.graph.connection import get_connection
from src.graph.schema import SchemaManager


@pytest.fixture(scope="module")
def setup_db():
    """Setup database for testing."""
    manager = SchemaManager()
    manager.connect()
    manager.clear_database()
    manager.create_constraints()
    manager.create_indexes()
    yield manager
    manager.close()


@pytest.fixture
def constitution_json(tmp_path):
    """Create minimal test constitution JSON."""
    import json
    
    data = {
        "official_id": "TEST_CF",
        "name": "Test Constitution",
        "components": [
            {
                "component_type": "title",
                "component_id": "tit_1",
                "ordering_id": "01",
                "full_text": "TÍTULO I - Test Title",
                "is_original": True,
                "events": [],
                "children": [
                    {
                        "component_type": "article",
                        "component_id": "tit_1_art_1",
                        "ordering_id": "1",
                        "full_text": "Art. 1º Test article one",
                        "is_original": True,
                        "events": [],
                        "children": []
                    },
                    {
                        "component_type": "article",
                        "component_id": "tit_1_art_2",
                        "ordering_id": "2",
                        "full_text": "Art. 2º Test article two",
                        "is_original": True,
                        "events": [],
                        "children": []
                    }
                ]
            }
        ]
    }
    
    json_file = tmp_path / "test_constitution.json"
    with open(json_file, 'w') as f:
        json.dump(data, f)
    
    return json_file


def test_load_constitution(setup_db, constitution_json):
    """Test initial constitution load."""
    loader = ConstitutionLoader()
    stats = loader.load_from_json(str(constitution_json))
    
    assert stats["norms"] == 1
    assert stats["components"] == 3  # 1 title + 2 articles
    assert stats["ctvs"] == 3
    assert stats["clvs"] == 3
    assert stats["text_units"] == 3


def test_norm_created(setup_db, constitution_json):
    """Test Norm node created correctly."""
    loader = ConstitutionLoader()
    loader.load_from_json(str(constitution_json))
    
    conn = get_connection()
    result = conn.execute_query("""
        MATCH (n:Norm {official_id: 'TEST_CF'})
        RETURN n.name AS name
    """)
    
    assert len(result) == 1
    assert result[0]["name"] == "Test Constitution"


def test_hierarchy_created(setup_db, constitution_json):
    """Test component hierarchy created correctly."""
    loader = ConstitutionLoader()
    loader.load_from_json(str(constitution_json))
    
    conn = get_connection()
    
    # Check title exists
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'tit_1'})
        RETURN c.component_type AS type
    """)
    assert result[0]["type"] == "title"
    
    # Check articles are children of title
    result = conn.execute_query("""
        MATCH (t:Component {component_id: 'tit_1'})-[:HAS_CHILD]->(a:Component)
        RETURN count(a) AS count
    """)
    assert result[0]["count"] == 2


def test_aggregation_created(setup_db, constitution_json):
    """Test AGGREGATES relationships created correctly."""
    loader = ConstitutionLoader()
    loader.load_from_json(str(constitution_json))
    
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (parent:CTV {component_id: 'tit_1'})-[:AGGREGATES]->(child:CTV)
        RETURN child.component_id AS comp_id
        ORDER BY comp_id
    """)
    
    assert len(result) == 2
    assert result[0]["comp_id"] == "tit_1_art_1"
    assert result[1]["comp_id"] == "tit_1_art_2"


def test_text_units_created(setup_db, constitution_json):
    """Test TextUnit nodes have correct content."""
    loader = ConstitutionLoader()
    loader.load_from_json(str(constitution_json))
    
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'tit_1_art_1'})
              -[:HAS_VERSION]->(v:CTV)
              -[:EXPRESSED_IN]->(l:CLV)
              -[:HAS_TEXT]->(t:TextUnit)
        RETURN t.full_text AS text
    """)
    
    assert len(result) == 1
    assert "Art. 1" in result[0]["text"]
```

### Check 4.4.2: Amendment Processing Tests

**File:** `tests/integration/test_temporal_engine.py`

```python
"""Tests for temporal engine (amendment processing)."""

import pytest
from src.graph.temporal_engine import TemporalEngine
from src.graph.loader import ConstitutionLoader
from src.graph.connection import get_connection
from src.graph.schema import SchemaManager
import json


@pytest.fixture(scope="module")
def loaded_constitution(tmp_path_factory):
    """Load a test constitution."""
    tmp_path = tmp_path_factory.mktemp("data")
    
    # Setup
    manager = SchemaManager()
    manager.connect()
    manager.clear_database()
    manager.create_constraints()
    manager.create_indexes()
    
    # Create test data
    data = {
        "official_id": "TEST_CF2",
        "name": "Test Constitution 2",
        "components": [
            {
                "component_type": "title",
                "component_id": "test_tit_1",
                "ordering_id": "01",
                "full_text": "TÍTULO I",
                "is_original": True,
                "events": [],
                "children": [
                    {
                        "component_type": "chapter",
                        "component_id": "test_tit_1_cap_1",
                        "ordering_id": "01",
                        "full_text": "CAPÍTULO I",
                        "is_original": True,
                        "events": [],
                        "children": [
                            {
                                "component_type": "article",
                                "component_id": "test_art_1",
                                "ordering_id": "1",
                                "full_text": "Art. 1º Original text",
                                "is_original": True,
                                "events": [],
                                "children": []
                            },
                            {
                                "component_type": "article",
                                "component_id": "test_art_2",
                                "ordering_id": "2",
                                "full_text": "Art. 2º Unchanged text",
                                "is_original": True,
                                "events": [],
                                "children": []
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    json_file = tmp_path / "test_cf2.json"
    with open(json_file, 'w') as f:
        json.dump(data, f)
    
    # Load
    loader = ConstitutionLoader()
    loader.load_from_json(str(json_file))
    
    yield
    
    manager.close()


def test_apply_amendment(loaded_constitution):
    """Test applying an amendment creates correct structure."""
    engine = TemporalEngine()
    
    stats = engine.apply_amendment(
        amendment_number=99,
        amendment_date="2020-01-01",
        changes=[
            {
                "component_id": "test_art_1",
                "new_content": "Art. 1º Modified text by EC 99",
                "change_type": "modify"
            }
        ],
        description="Test Amendment"
    )
    
    assert stats["new_ctvs"] >= 1
    assert stats["closed_ctvs"] >= 1


def test_old_version_closed(loaded_constitution):
    """Test that old version is properly closed."""
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'test_art_1'})-[:HAS_VERSION]->(v:CTV)
        WHERE v.version_number = 1
        RETURN v.is_active AS active, v.date_end AS end_date
    """)
    
    assert len(result) == 1
    assert result[0]["active"] == False
    assert result[0]["end_date"] is not None


def test_new_version_active(loaded_constitution):
    """Test that new version is active."""
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'test_art_1'})-[:HAS_VERSION]->(v:CTV)
        WHERE v.is_active = true
        RETURN v.version_number AS version
    """)
    
    assert len(result) == 1
    assert result[0]["version"] == 2


def test_ancestor_updated(loaded_constitution):
    """Test that ancestor CTVs were updated."""
    conn = get_connection()
    
    # Chapter should have v2
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'test_tit_1_cap_1'})-[:HAS_VERSION]->(v:CTV)
        WHERE v.is_active = true
        RETURN v.version_number AS version
    """)
    
    assert result[0]["version"] == 2


def test_unchanged_sibling_reused(loaded_constitution):
    """Test that unchanged sibling CTV is reused (not duplicated)."""
    conn = get_connection()
    
    # Article 2 should still have only v1
    result = conn.execute_query("""
        MATCH (c:Component {component_id: 'test_art_2'})-[:HAS_VERSION]->(v:CTV)
        RETURN count(v) AS count
    """)
    
    assert result[0]["count"] == 1  # Still only 1 version!


def test_new_parent_aggregates_reused_child(loaded_constitution):
    """Test that new parent CTV aggregates the reused child CTV."""
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (parent:CTV {component_id: 'test_tit_1_cap_1', is_active: true})
              -[:AGGREGATES]->(child:CTV {component_id: 'test_art_2'})
        RETURN child.version_number AS version
    """)
    
    assert len(result) == 1
    assert result[0]["version"] == 1  # The old version is reused!


def test_supersedes_relationship(loaded_constitution):
    """Test that SUPERSEDES relationship exists."""
    conn = get_connection()
    
    result = conn.execute_query("""
        MATCH (new:CTV {component_id: 'test_art_1', version_number: 2})
              -[:SUPERSEDES]->(old:CTV)
        RETURN old.version_number AS old_version
    """)
    
    assert len(result) == 1
    assert result[0]["old_version"] == 1
```

---

## 4.5 Success Criteria

| Criterion | Validation |
|-----------|------------|
| Initial load creates all node types | Norm, Component, CTV, CLV, TextUnit exist |
| HAS_COMPONENT relationships exist | Norm → Components |
| HAS_VERSION relationships exist | Component → CTVs |
| AGGREGATES relationships exist | Parent CTV → Child CTVs |
| Amendment creates new CTVs | new_ctvs > 0 |
| Amendment closes old CTVs | Old CTV has date_end, is_active=false |
| Amendment propagates to ancestors | Ancestor CTVs have new versions |
| Unchanged siblings are REUSED | No duplicate CTVs for unchanged components |
| SUPERSEDES chain exists | New → Old relationship |

---

## 4.6 Redundancy Verification

The most important validation: **amendments should NOT create duplicate nodes for unchanged components**.

```cypher
// Check for redundancy: Count CTVs per component
MATCH (c:Component)-[:HAS_VERSION]->(v:CTV)
WITH c.component_id AS comp, count(v) AS versions
WHERE versions > 1
RETURN comp, versions
ORDER BY versions DESC
LIMIT 10

// If component was never amended, should have exactly 1 CTV
// If amended once, should have exactly 2 CTVs
// NOT: should have 100 CTVs because constitution was amended 100 times
```

---

## 4.7 Phase Completion Checklist

- [ ] ConstitutionLoader implemented
- [ ] TemporalEngine implemented
- [ ] Initial load creates correct structure
- [ ] Amendments create new versions
- [ ] Amendments close old versions
- [ ] Ancestor propagation works
- [ ] Sibling reuse verified (no duplicates)
- [ ] SUPERSEDES relationships exist
- [ ] Action nodes created for amendments
- [ ] All integration tests pass

**Next Phase:** `06_RETRIEVAL_ENGINE.md`

