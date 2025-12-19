#!/usr/bin/env python3
"""Run the full scraping pipeline."""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from collection.fetch_constitution import fetch_constitution, verify_constitution_download
from collection.fetch_amendments import fetch_amendments, verify_amendments_download


def main():
    parser = argparse.ArgumentParser(description="Scrape Planalto Constitution")
    parser.add_argument(
        "--max-amendments", 
        type=int, 
        default=None,
        help="Limit amendments to fetch (for testing)"
    )
    parser.add_argument(
        "--skip-constitution",
        action="store_true",
        help="Skip constitution download"
    )
    parser.add_argument(
        "--skip-amendments",
        action="store_true", 
        help="Skip amendments download"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification checks"
    )
    args = parser.parse_args()
    
    if args.verify_only:
        print("\n=== Verification Only ===\n")
        const_ok = verify_constitution_download()
        amend_ok = verify_amendments_download()
        sys.exit(0 if (const_ok and amend_ok) else 1)
    
    # Scrape constitution
    if not args.skip_constitution:
        print("\n=== Fetching Constitution ===\n")
        fetch_constitution()
        if not verify_constitution_download():
            print("ERROR: Constitution verification failed!")
            sys.exit(1)
    
    # Scrape amendments
    if not args.skip_amendments:
        print("\n=== Fetching Amendments ===\n")
        fetch_amendments(max_amendments=args.max_amendments)
        if not verify_amendments_download():
            print("ERROR: Amendments verification failed!")
            sys.exit(1)
    
    print("\n=== Scraping Complete ===\n")


if __name__ == "__main__":
    main()

