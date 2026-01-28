#!/usr/bin/env python
"""Reset database and reload constitution from scratch."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.connection import get_connection
from src.graph.loader import load_constitution


def clear_database():
    """Clear all nodes and relationships from the database."""
    print("\n" + "="*70)
    print("CLEARING DATABASE")
    print("="*70)

    conn = get_connection()

    with conn.session() as session:
        # Get counts before deletion
        result = list(session.run("MATCH (n) RETURN count(n) AS count"))
        node_count = result[0]["count"]

        result = list(session.run("MATCH ()-[r]->() RETURN count(r) AS count"))
        rel_count = result[0]["count"]

        print(f"\n  Current database state:")
        print(f"    • Nodes: {node_count:,}")
        print(f"    • Relationships: {rel_count:,}")

        # Delete everything
        print(f"\n  Deleting all nodes and relationships...")
        session.run("MATCH (n) DETACH DELETE n")

        print(f"  ✅ Database cleared!")


def reload_constitution():
    """Reload the constitution from JSON."""
    print("\n" + "="*70)
    print("LOADING CONSTITUTION")
    print("="*70)

    stats = load_constitution()

    print("\n  ✅ Constitution loaded successfully!")
    print("\n  Load Statistics:")
    for key, value in stats.items():
        print(f"    • {key}: {value:,}")


def main():
    """Main execution."""
    print("\n" + "🔄"*35)
    print("DATABASE RESET AND RELOAD")
    print("🔄"*35)

    try:
        clear_database()
        reload_constitution()

        print("\n" + "="*70)
        print("✅ RESET COMPLETE!")
        print("="*70)
        print("\nNext steps:")
        print("  1. Run: python scripts/process_all_amendments.py")
        print("  2. Run: python scripts/run_verification.py")
        print("\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
