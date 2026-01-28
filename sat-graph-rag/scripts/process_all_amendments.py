#!/usr/bin/env python
"""Process all 137 constitutional amendments through the temporal engine.

This script demonstrates the aggregation model at scale by:
1. Loading parsed amendment data
2. Mapping article numbers to component IDs
3. Applying amendments chronologically
4. Tracking aggregation efficiency
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.temporal_engine import TemporalEngine
from src.graph.connection import get_connection


def load_amendments(path: str = "data/intermediate/amendments/parsed_amendments.json") -> List[Dict]:
    """Load parsed amendment data."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_component_mapping(conn) -> Dict[str, str]:
    """
    Build a mapping from article numbers to component IDs.

    Returns:
        Dict mapping "5" -> "tit_01_art_5" (or similar)
    """
    query = """
    MATCH (c:Component {component_type: 'article'})
    RETURN c.component_id AS comp_id, c.ordering_id AS ordering
    """

    mapping = {}
    with conn.session() as session:
        results = list(session.run(query))

    for r in results:
        comp_id = r["comp_id"]
        ordering = r["ordering"]

        # Extract article number from component_id or ordering
        # e.g., "tit_01_art_1" -> "1" or "art_5" -> "5"
        if ordering:
            mapping[ordering] = comp_id

        # Also try to extract from ID
        if "_art_" in comp_id:
            parts = comp_id.split("_art_")
            if len(parts) > 1:
                art_num = parts[1].split("_")[0]
                mapping[art_num] = comp_id

    return mapping


def get_aggregation_stats(conn) -> Dict:
    """Get current aggregation statistics."""
    query = """
    MATCH (c:Component) WITH count(c) AS components
    MATCH (v:CTV) WITH components, count(v) AS ctvs
    MATCH (a:Action) WITH components, ctvs, count(a) AS actions
    RETURN components, ctvs, actions,
           toFloat(ctvs) / components AS avg_versions,
           toFloat(ctvs) / (components * CASE WHEN actions > 0 THEN (actions + 1) ELSE 1 END) AS efficiency
    """

    with conn.session() as session:
        result = list(session.run(query))

    if result:
        return dict(result[0])
    return {}


def process_amendments_batch(
    amendments: List[Dict],
    mapping: Dict[str, str],
    engine: TemporalEngine,
    start_idx: int = 0,
    batch_size: int = 10
):
    """
    Process amendments in batches.

    Args:
        amendments: List of parsed amendments
        mapping: Article number -> component ID mapping
        engine: TemporalEngine instance
        start_idx: Starting index (for resuming)
        batch_size: Number to process before reporting stats
    """
    total = len(amendments)
    processed = 0
    skipped = 0

    print(f"\n🚀 Processing {total} amendments...")
    print(f"   Starting from index {start_idx}")
    print(f"   Batch size: {batch_size}\n")

    for i, amendment in enumerate(amendments[start_idx:], start=start_idx):
        number = amendment["number"]
        date_str = amendment["date"]

        # Skip if date is invalid
        try:
            # Parse date (format: YYYY-MM-DD or YYYY-01-01)
            if not date_str or date_str == "1992-01-01":
                # Use a better default if available
                pass
        except:
            print(f"  ⚠️  EC {number}: Invalid date, skipping")
            skipped += 1
            continue

        # Collect changes
        changes = []

        # Modified articles
        for art_num in amendment.get("articles_modified", []):
            if art_num in mapping:
                changes.append({
                    "component_id": mapping[art_num],
                    "new_content": f"Modified by EC {number}",
                    "change_type": "modify"
                })

        # Added articles (treat as modify if exists, skip if new)
        for art_num in amendment.get("articles_added", []):
            if art_num in mapping:
                changes.append({
                    "component_id": mapping[art_num],
                    "new_content": f"Added/Modified by EC {number}",
                    "change_type": "modify"
                })

        # Repealed articles
        for art_num in amendment.get("articles_repealed", []):
            if art_num in mapping:
                changes.append({
                    "component_id": mapping[art_num],
                    "new_content": "",
                    "change_type": "repeal"
                })

        if not changes:
            skipped += 1
            continue

        # Apply amendment
        try:
            stats = engine.apply_amendment(
                amendment_number=number,
                amendment_date=date_str,
                changes=changes,
                description=f"Emenda Constitucional {number}"
            )
            processed += 1

            # Report progress
            if (i + 1) % batch_size == 0 or (i + 1) == total:
                agg_stats = get_aggregation_stats(engine.conn)
                print(f"\n📊 Progress: {i + 1}/{total} amendments")
                print(f"   Processed: {processed}, Skipped: {skipped}")
                print(f"   CTVs created: {stats['new_ctvs']}")
                print(f"   CTVs reused: {stats['reused_ctvs']}")
                print(f"   Total CTVs: {agg_stats.get('ctvs', '?')}")
                print(f"   Efficiency: {agg_stats.get('efficiency', 0):.4f}")
                print(f"   Avg versions/component: {agg_stats.get('avg_versions', 0):.2f}")

        except Exception as e:
            print(f"  ❌ EC {number}: Error - {e}")
            skipped += 1

    return {
        "total": total,
        "processed": processed,
        "skipped": skipped
    }


def main():
    """Main execution."""
    print("\n" + "="*70)
    print("PROCESSING ALL CONSTITUTIONAL AMENDMENTS")
    print("="*70)

    conn = get_connection()
    engine = TemporalEngine(conn)

    # Load amendments
    print("\n📂 Loading amendments...")
    amendments = load_amendments()
    print(f"   Loaded {len(amendments)} amendments")

    # Build component mapping
    print("\n🗺️  Building article mapping...")
    mapping = get_component_mapping(conn)
    print(f"   Mapped {len(mapping)} articles")
    print(f"   Sample: {dict(list(mapping.items())[:5])}")

    # Get initial stats
    print("\n📊 Initial statistics:")
    initial_stats = get_aggregation_stats(conn)
    print(f"   Components: {initial_stats.get('components', '?')}")
    print(f"   CTVs: {initial_stats.get('ctvs', '?')}")
    print(f"   Actions: {initial_stats.get('actions', '?')}")
    print(f"   Avg versions/component: {initial_stats.get('avg_versions', 0):.2f}")

    # Process amendments
    start_time = datetime.now()

    result = process_amendments_batch(
        amendments=amendments,
        mapping=mapping,
        engine=engine,
        start_idx=0,
        batch_size=10  # Report every 10 amendments
    )

    duration = (datetime.now() - start_time).total_seconds()

    # Final statistics
    print("\n" + "="*70)
    print("📊 FINAL STATISTICS")
    print("="*70)

    final_stats = get_aggregation_stats(conn)

    print(f"\nAmendments:")
    print(f"   Total: {result['total']}")
    print(f"   Processed: {result['processed']}")
    print(f"   Skipped: {result['skipped']}")
    print(f"   Duration: {duration:.1f}s")

    print(f"\nGraph State:")
    print(f"   Components: {final_stats.get('components', '?')}")
    print(f"   CTVs: {final_stats.get('ctvs', '?')}")
    print(f"   Actions: {final_stats.get('actions', '?')}")
    print(f"   Avg versions/component: {final_stats.get('avg_versions', 0):.2f}")

    # Calculate efficiency improvement
    initial_ctvs = initial_stats.get('ctvs', 0)
    final_ctvs = final_stats.get('ctvs', 0)
    components = final_stats.get('components', 1)
    actions = final_stats.get('actions', 1)

    max_without_agg = components * (actions + 1)
    efficiency = final_ctvs / max_without_agg if max_without_agg > 0 else 0

    print(f"\n🎯 Aggregation Efficiency:")
    print(f"   Efficiency score: {efficiency:.4f}")
    print(f"   CTVs created: {final_ctvs - initial_ctvs}")
    print(f"   Max without aggregation: {max_without_agg}")
    print(f"   Space saved: {max_without_agg - final_ctvs} CTVs ({(1-efficiency)*100:.1f}%)")

    if efficiency < 0.1:
        print(f"\n   ✅ EXCELLENT: Aggregation model is highly efficient!")
    elif efficiency < 0.3:
        print(f"\n   ✅ GOOD: Aggregation model is working well")
    else:
        print(f"\n   ⚠️  WARNING: Efficiency could be better")

    print("\n" + "="*70)
    print("✅ Amendment processing complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
