#!/usr/bin/env python
"""Export graph data for visualization."""

import sys
from pathlib import Path
import json
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from graph.connection import get_connection


def export_demo_data() -> dict:
    """Export a small demo dataset (just titles, chapters, and a few articles).
    
    Returns:
        Dictionary with nodes and edges for vis.js
    """
    conn = get_connection()
    conn.connect()
    
    # Get only high-level structure for demo
    with conn.session() as session:
        result = session.run("""
            // Get Norm
            MATCH (n:Norm)
            RETURN 'norm' AS type, n.official_id AS id, n.name AS label, 
                   null AS parent, 'norm' AS component_type
            
            UNION ALL
            
            // Get Titles
            MATCH (n:Norm)-[:HAS_COMPONENT]->(c:Component {component_type: 'title'})
            MATCH (c)-[:HAS_VERSION]->(v:CTV {is_active: true})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN 'component' AS type, c.component_id AS id, 
                   COALESCE(t.header, c.ordering_id) AS label,
                   n.official_id AS parent, c.component_type AS component_type
            
            UNION ALL
            
            // Get Chapters
            MATCH (parent:Component {component_type: 'title'})-[:HAS_CHILD]->(c:Component {component_type: 'chapter'})
            MATCH (c)-[:HAS_VERSION]->(v:CTV {is_active: true})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN 'component' AS type, c.component_id AS id,
                   COALESCE(t.header, c.ordering_id) AS label,
                   parent.component_id AS parent, c.component_type AS component_type
        """).data()
    
    return _build_graph_from_result(result, "demo")


def export_graph_data(max_articles: int = 200) -> dict:
    """Export graph data for visualization.
    
    Args:
        max_articles: Maximum number of articles to export (for performance)
    
    Returns:
        Dictionary with nodes and edges for vis.js
    """
    conn = get_connection()
    conn.connect()
    
    # Get high-level structure (Titles, Chapters, and some Articles)
    with conn.session() as session:
        result = session.run(f"""
            // Get Norm
            MATCH (n:Norm)
            RETURN 'norm' AS type, n.official_id AS id, n.name AS label, 
                   null AS parent, 'norm' AS component_type
            
            UNION ALL
            
            // Get Titles
            MATCH (n:Norm)-[:HAS_COMPONENT]->(c:Component {{component_type: 'title'}})
            MATCH (c)-[:HAS_VERSION]->(v:CTV {{is_active: true}})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN 'component' AS type, c.component_id AS id, 
                   COALESCE(t.header, c.ordering_id) AS label,
                   n.official_id AS parent, c.component_type AS component_type
            
            UNION ALL
            
            // Get Chapters
            MATCH (parent:Component {{component_type: 'title'}})-[:HAS_CHILD]->(c:Component {{component_type: 'chapter'}})
            MATCH (c)-[:HAS_VERSION]->(v:CTV {{is_active: true}})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN 'component' AS type, c.component_id AS id,
                   COALESCE(t.header, c.ordering_id) AS label,
                   parent.component_id AS parent, c.component_type AS component_type
            
            UNION ALL
            
            // Get Sections (optional)
            MATCH (parent:Component {{component_type: 'chapter'}})-[:HAS_CHILD]->(c:Component {{component_type: 'section'}})
            MATCH (c)-[:HAS_VERSION]->(v:CTV {{is_active: true}})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            RETURN 'component' AS type, c.component_id AS id,
                   COALESCE(t.header, c.ordering_id) AS label,
                   parent.component_id AS parent, c.component_type AS component_type
            
            UNION ALL
            
            // Get Articles (limit to keep visualization manageable)
            MATCH (parent:Component)-[:HAS_CHILD]->(c:Component {{component_type: 'article'}})
            WHERE parent.component_type IN ['chapter', 'section', 'title']
            MATCH (c)-[:HAS_VERSION]->(v:CTV {{is_active: true}})
            MATCH (v)-[:EXPRESSED_IN]->(:CLV)-[:HAS_TEXT]->(t:TextUnit)
            WITH c, parent, t, v
            LIMIT {max_articles}
            RETURN 'component' AS type, c.component_id AS id,
               COALESCE(t.header, 'Art. ' + c.ordering_id) AS label,
               parent.component_id AS parent, c.component_type AS component_type
        """).data()
    
    return _build_graph_from_result(result, "full")


def _build_graph_from_result(result: list, mode: str) -> dict:
    """Build graph data structure from query result."""
    # Build nodes and edges
    nodes = []
    edges = []
    node_ids = set()
    
    # Color scheme
    colors = {
        'norm': '#E74C3C',      # Red
        'title': '#3498DB',     # Blue
        'chapter': '#2ECC71',   # Green
        'section': '#9B59B6',   # Purple
        'article': '#F39C12',   # Orange
        'paragraph': '#1ABC9C', # Teal
        'item': '#E67E22',      # Dark Orange
        'letter': '#95A5A6',    # Gray
    }
    
    sizes = {
        'norm': 50,
        'title': 35,
        'chapter': 25,
        'section': 20,
        'article': 15,
        'paragraph': 12,
        'item': 10,
        'letter': 8,
    }
    
    for row in result:
        node_id = row['id']
        if node_id in node_ids:
            continue
        node_ids.add(node_id)
        
        comp_type = row['component_type']
        
        # Truncate label for display
        label = row['label'] or node_id
        if len(label) > 30:
            label = label[:27] + '...'
        
        nodes.append({
            'id': node_id,
            'label': label,
            'group': comp_type,
            'color': colors.get(comp_type, '#95A5A6'),
            'size': sizes.get(comp_type, 10),
            'title': f"{comp_type.upper()}: {row['label'] or node_id}",  # Tooltip
        })
        
        if row['parent']:
            edges.append({
                'from': row['parent'],
                'to': node_id,
                'arrows': 'to',
            })
    
    return {
        'nodes': nodes,
        'edges': edges,
        'mode': mode,
        'stats': {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
        }
    }


def get_graph_stats() -> dict:
    """Get overall graph statistics."""
    conn = get_connection()
    conn.connect()
    
    with conn.session() as session:
        result = session.run("""
            MATCH (n:Norm) WITH count(n) AS norms
            MATCH (c:Component) WITH norms, count(c) AS components
            MATCH (v:CTV) WITH norms, components, count(v) AS ctvs
            MATCH (l:CLV) WITH norms, components, ctvs, count(l) AS clvs
            MATCH (t:TextUnit) WITH norms, components, ctvs, clvs, count(t) AS texts
            MATCH ()-[r]->() WITH norms, components, ctvs, clvs, texts, count(r) AS rels
            RETURN norms, components, ctvs, clvs, texts, rels
        """).data()
    
    if result:
        r = result[0]
        return {
            'norms': r['norms'],
            'components': r['components'],
            'ctvs': r['ctvs'],
            'clvs': r['clvs'],
            'text_units': r['texts'],
            'relationships': r['rels'],
        }
    return {}


def get_component_breakdown() -> dict:
    """Get breakdown by component type."""
    conn = get_connection()
    conn.connect()
    
    with conn.session() as session:
        result = session.run("""
            MATCH (c:Component)
            RETURN c.component_type AS type, count(c) AS count
            ORDER BY count DESC
        """).data()
    
    return {r['type']: r['count'] for r in result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export graph data for visualization")
    parser.add_argument("--demo", action="store_true", help="Export small demo dataset (titles + chapters only)")
    parser.add_argument("--max-articles", type=int, default=200, help="Maximum articles to include in full export")
    args = parser.parse_args()
    
    print("Exporting graph data...")
    
    if args.demo:
        print("Demo mode: exporting titles and chapters only")
        data = export_demo_data()
    else:
        print(f"Full mode: exporting up to {args.max_articles} articles")
        data = export_graph_data(max_articles=args.max_articles)
    
    stats = get_graph_stats()
    breakdown = get_component_breakdown()
    
    output = {
        'graph': data,
        'stats': stats,
        'breakdown': breakdown,
    }
    
    # Save to file (in visualization folder for HTML access)
    output_path = Path(__file__).parent.parent / "visualization" / "graph_data.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Exported to {output_path}")
    print(f"Mode: {data['mode']}")
    print(f"Visible nodes: {data['stats']['total_nodes']}")
    print(f"Total in DB: {stats}")
    print(f"Breakdown: {breakdown}")

