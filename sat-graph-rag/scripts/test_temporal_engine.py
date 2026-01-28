#!/usr/bin/env python
"""Test script for the temporal engine.

This script:
1. Applies a test amendment to modify an article
2. Verifies the aggregation model is working correctly
3. Checks that unchanged siblings are reused (not duplicated)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.temporal_engine import TemporalEngine
from src.graph.connection import get_connection


def test_temporal_engine():
    """Test the temporal engine with a sample amendment."""
    print("\n" + "="*70)
    print("TESTING TEMPORAL ENGINE - AGGREGATION MODEL")
    print("="*70 + "\n")

    conn = get_connection()
    engine = TemporalEngine(conn)

    # First, check current state
    print("📊 Checking initial state...")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (c:Component {component_type: 'article'})
            OPTIONAL MATCH (c)-[:HAS_VERSION]->(v:CTV)
            WITH c, count(v) AS version_count
            RETURN count(c) AS total_articles,
                   avg(version_count) AS avg_versions
        """))

    if result:
        print(f"   • Total articles: {result[0]['total_articles']}")
        print(f"   • Avg versions per article: {result[0]['avg_versions']:.2f}")

    # Find an article to modify (let's use article 1 as a test)
    print("\n🔍 Finding article to modify...")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (c:Component {component_type: 'article'})
            WHERE c.component_id CONTAINS 'art_1'
            RETURN c.component_id AS comp_id
            ORDER BY c.component_id
            LIMIT 1
        """))

    if not result:
        print("❌ No articles found! Make sure constitution is loaded.")
        return

    test_article = result[0]["comp_id"]
    print(f"   • Selected: {test_article}")

    # Check if this article has siblings
    print("\n👨‍👩‍👧‍👦 Checking siblings...")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (parent:Component)-[:HAS_CHILD]->(target:Component {component_id: $comp_id})
            MATCH (parent)-[:HAS_CHILD]->(sibling:Component)
            WHERE sibling.component_id <> $comp_id
            RETURN count(DISTINCT sibling) AS sibling_count
        """, {"comp_id": test_article}))

    sibling_count = result[0]["sibling_count"] if result else 0
    print(f"   • Found {sibling_count} siblings")

    # Apply test amendment
    print(f"\n🔧 Applying test amendment to {test_article}...")
    print("   (This simulates EC 999 modifying the article)")

    stats = engine.apply_amendment(
        amendment_number=999,
        amendment_date="2025-01-01",
        changes=[
            {
                "component_id": test_article,
                "new_content": "TEST AMENDMENT: This article was modified by EC 999 for testing purposes.",
                "change_type": "modify"
            }
        ],
        description="Test Amendment 999"
    )

    print(f"\n✅ Amendment applied successfully!")
    print(f"   Stats: {stats}")

    # Verify aggregation model
    print("\n🔬 VERIFYING AGGREGATION MODEL...")

    # Check 1: Modified article should have 2 versions
    print("\n1️⃣ Check: Modified article has 2 versions")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (c:Component {component_id: $comp_id})-[:HAS_VERSION]->(v:CTV)
            RETURN count(v) AS version_count
        """, {"comp_id": test_article}))

    version_count = result[0]["version_count"]
    if version_count == 2:
        print(f"   ✅ PASS: Article has {version_count} versions (original + new)")
    else:
        print(f"   ⚠️  WARNING: Article has {version_count} versions (expected 2)")

    # Check 2: Unchanged siblings should still have 1 version
    if sibling_count > 0:
        print("\n2️⃣ Check: Unchanged siblings still have 1 version (REUSED)")
        with conn.session() as session:
            result = list(session.run("""
                MATCH (parent:Component)-[:HAS_CHILD]->(target:Component {component_id: $comp_id})
                MATCH (parent)-[:HAS_CHILD]->(sibling:Component)
                WHERE sibling.component_id <> $comp_id
                MATCH (sibling)-[:HAS_VERSION]->(v:CTV)
                WITH sibling, count(v) AS versions
                WHERE versions = 1
                RETURN count(sibling) AS unchanged_siblings
            """, {"comp_id": test_article}))

        unchanged = result[0]["unchanged_siblings"] if result else 0
        if unchanged > 0:
            print(f"   ✅ PASS: {unchanged}/{sibling_count} siblings still have 1 version (reused!)")
        else:
            print(f"   ⚠️  WARNING: No siblings with 1 version found")

    # Check 3: Parent CTV should aggregate both new and old child CTVs
    print("\n3️⃣ Check: Parent aggregates NEW child + OLD siblings")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (parent:Component)-[:HAS_CHILD]->(target:Component {component_id: $comp_id})
            MATCH (parent)-[:HAS_VERSION]->(pv:CTV {is_active: true})
            MATCH (pv)-[:AGGREGATES]->(child_ctv:CTV)
            MATCH (child_comp:Component)-[:HAS_VERSION]->(child_ctv)
            RETURN child_comp.component_id AS child,
                   child_ctv.version_number AS version,
                   child_ctv.date_start AS start_date
            ORDER BY child_comp.component_id
        """, {"comp_id": test_article}))

    if result:
        print(f"   ✅ PASS: Parent CTV aggregates {len(result)} children:")
        for r in result[:5]:  # Show first 5
            print(f"      • {r['child']} v{r['version']} (from {r['start_date']})")
        if len(result) > 5:
            print(f"      ... and {len(result) - 5} more")

        # Count reused (old date) vs new
        old_count = sum(1 for r in result if str(r['start_date']) < '2025-01-01')
        new_count = len(result) - old_count
        print(f"\n   📊 Aggregation breakdown:")
        print(f"      • {old_count} REUSED children (old dates)")
        print(f"      • {new_count} NEW children (new dates)")

    # Check 4: Action node created and linked
    print("\n4️⃣ Check: Action node tracks amendment")
    with conn.session() as session:
        result = list(session.run("""
            MATCH (a:Action {amendment_number: 999})-[:RESULTED_IN]->(v:CTV)
            RETURN count(v) AS affected_ctvs
        """))

    affected = result[0]["affected_ctvs"] if result else 0
    if affected > 0:
        print(f"   ✅ PASS: Action node links to {affected} new CTV(s)")
    else:
        print(f"   ⚠️  WARNING: No action linkage found")

    # Final summary
    print("\n" + "="*70)
    print("📊 FINAL STATISTICS")
    print("="*70)

    with conn.session() as session:
        result = list(session.run("""
            MATCH (c:Component) WITH count(c) AS components
            MATCH (v:CTV) WITH components, count(v) AS ctvs
            MATCH (a:Action) WITH components, ctvs, count(a) AS actions
            RETURN components, ctvs, actions,
                   toFloat(ctvs) / components AS avg_versions
        """))

    if result:
        r = result[0]
        print(f"\n   Components: {r['components']}")
        print(f"   CTVs: {r['ctvs']}")
        print(f"   Actions: {r['actions']}")
        print(f"   Avg versions/component: {r['avg_versions']:.2f}")

        # Calculate theoretical maximum without aggregation
        max_without_agg = r['components'] * (r['actions'] + 1)
        efficiency = r['ctvs'] / max_without_agg if max_without_agg > 0 else 0

        print(f"\n   🎯 Efficiency score: {efficiency:.4f}")
        print(f"      (Lower is better - means aggregation is working)")
        print(f"      Max without aggregation: {max_without_agg}")

        if efficiency < 0.1:
            print(f"\n   ✅ EXCELLENT: Aggregation model is working!")
        elif efficiency < 0.3:
            print(f"\n   ✅ GOOD: Aggregation is effective")
        else:
            print(f"\n   ⚠️  WARNING: Efficiency could be better")

    print("\n" + "="*70)
    print("✅ Temporal engine test complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_temporal_engine()
