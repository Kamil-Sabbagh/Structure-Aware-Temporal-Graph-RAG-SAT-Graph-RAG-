#!/usr/bin/env python
"""Test script for RAG retrieval system.

Demonstrates:
1. Point-in-time queries (time-travel)
2. Provenance queries (amendment tracking)
3. Semantic queries (text search)
"""

import sys
from pathlib import Path
from datetime import date

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.planner import QueryPlanner
from src.rag.retriever import HybridRetriever


def print_result(result, index=1):
    """Pretty print a retrieval result."""
    print(f"\n{'='*70}")
    print(f"Result #{index}: {result.component_id}")
    print(f"{'='*70}")
    print(f"Type: {result.component_type}")
    print(f"Version: v{result.version_info.get('version', '?')}")
    if result.version_info.get('start'):
        print(f"Valid from: {result.version_info['start']}")
    if result.version_info.get('end'):
        print(f"Valid until: {result.version_info['end']}")
    print(f"\nText preview:")
    print(f"  {result.text[:300]}...")
    if result.provenance:
        print(f"\nProvenance:")
        for key, val in result.provenance.items():
            print(f"  {key}: {val}")


def test_time_travel():
    """Test time-travel queries."""
    print("\n" + "="*70)
    print("🕰️  TEST 1: TIME-TRAVEL QUERIES")
    print("="*70)

    planner = QueryPlanner()
    retriever = HybridRetriever()

    # Test query: What was Article 1 in 1988?
    query1 = "O que dizia o artigo 1 em 1988?"
    print(f"\nQuery: '{query1}'")

    plan = planner.plan(query1)
    print(f"  → Classified as: {plan.query_type.value}")
    print(f"  → Target component: {plan.target_component}")
    print(f"  → Target date: {plan.target_date}")

    results = retriever.retrieve(plan, top_k=1)
    if results:
        print_result(results[0])
    else:
        print("  ⚠️  No results found")

    # Test query: What was Article 1 in 2025? (after our test amendment)
    query2 = "O que diz o artigo 1 em 2025?"
    print(f"\n\nQuery: '{query2}'")

    plan = planner.plan(query2)
    print(f"  → Classified as: {plan.query_type.value}")
    print(f"  → Target component: {plan.target_component}")
    print(f"  → Target date: {plan.target_date}")

    results = retriever.retrieve(plan, top_k=1)
    if results:
        print_result(results[0])
        # Should show v2 from test amendment!
    else:
        print("  ⚠️  No results found")


def test_provenance():
    """Test provenance queries."""
    print("\n\n" + "="*70)
    print("📜 TEST 2: PROVENANCE QUERIES")
    print("="*70)

    planner = QueryPlanner()
    retriever = HybridRetriever()

    # Test: What did EC 999 change?
    query = "O que mudou com a EC 999?"
    print(f"\nQuery: '{query}'")

    plan = planner.plan(query)
    print(f"  → Classified as: {plan.query_type.value}")
    print(f"  → Amendment number: {plan.amendment_number}")

    results = retriever.retrieve(plan, top_k=5)
    print(f"\n  Found {len(results)} changes:")

    for i, result in enumerate(results, 1):
        print_result(result, i)


def test_version_history():
    """Test version history of a component."""
    print("\n\n" + "="*70)
    print("📚 TEST 3: VERSION HISTORY")
    print("="*70)

    planner = QueryPlanner()
    retriever = HybridRetriever()

    # Get history of article 1
    query = "Histórico do artigo 1"
    print(f"\nQuery: '{query}'")

    plan = planner.plan(query)
    print(f"  → Classified as: {plan.query_type.value}")

    # Manually set target for this test
    plan.target_component = "tit_01_art_1"

    results = retriever.retrieve(plan, top_k=10)
    print(f"\n  Found {len(results)} versions:")

    for i, result in enumerate(results, 1):
        print(f"\n  Version {i}:")
        print(f"    • v{result.version_info.get('version', '?')}")
        print(f"    • From: {result.version_info.get('start', '?')}")
        if result.version_info.get('amendment'):
            print(f"    • Amendment: EC {result.version_info['amendment']}")
        print(f"    • Text: {result.text[:100]}...")


def test_semantic():
    """Test semantic search (text-based for now)."""
    print("\n\n" + "="*70)
    print("🔍 TEST 4: SEMANTIC SEARCH")
    print("="*70)

    planner = QueryPlanner()
    retriever = HybridRetriever()

    query = "Quais são os fundamentos da República?"
    print(f"\nQuery: '{query}'")

    plan = planner.plan(query)
    print(f"  → Classified as: {plan.query_type.value}")
    print(f"  → Semantic query: '{plan.semantic_query}'")

    results = retriever.retrieve(plan, top_k=3)
    print(f"\n  Found {len(results)} relevant components:")

    for i, result in enumerate(results, 1):
        print_result(result, i)


def main():
    """Run all tests."""
    print("\n" + "🚀"*35)
    print("TESTING RAG RETRIEVAL SYSTEM")
    print("🚀"*35)

    try:
        test_time_travel()
        test_provenance()
        test_version_history()
        test_semantic()

        print("\n\n" + "="*70)
        print("✅ All retrieval tests complete!")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
