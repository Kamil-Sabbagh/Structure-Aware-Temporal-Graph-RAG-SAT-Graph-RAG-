#!/usr/bin/env python3
"""Script to run the full ingestion pipeline."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()


def main():
    """Run the ingestion pipeline."""
    print("=== SAT-Graph RAG: Ingestion Pipeline ===")
    print("TODO: Implement in Phase 4 - Ingestion Pipeline")
    
    # Placeholder for Phase 4 implementation
    # from graph.loader import GraphLoader
    # loader = GraphLoader()
    # loader.load_all()


if __name__ == "__main__":
    main()

