#!/usr/bin/env python3
"""Script to start the FastAPI server."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
import uvicorn

load_dotenv()


def main():
    """Start the API server."""
    print("=== SAT-Graph RAG: API Server ===")
    
    # Placeholder for Phase 5/6 implementation
    # uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
    print("TODO: Implement in Phase 5 - Retrieval Engine")


if __name__ == "__main__":
    main()

