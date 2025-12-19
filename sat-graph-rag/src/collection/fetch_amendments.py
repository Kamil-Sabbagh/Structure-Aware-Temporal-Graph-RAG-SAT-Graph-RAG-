"""Fetch all constitutional amendments."""

import re
import json
from typing import List, Dict
from bs4 import BeautifulSoup
from .scraper import PlanaltoScraper
from pathlib import Path


def parse_amendments_index(html: str) -> List[Dict]:
    """
    Parse the amendments index page to get amendment list.
    
    Returns:
        List of dicts with: number, date, url, description
    """
    soup = BeautifulSoup(html, 'lxml')
    amendments = []
    
    # The amendments are in a table
    # Structure: row with cells [number + date, description]
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 2:
            first_cell = cells[0]
            
            # Find the link to the amendment
            link = first_cell.find('a')
            if link and link.get('href'):
                href = link.get('href')
                text = link.get_text(strip=True)
                
                # Parse "137, de 9.12.2025" or "137 de 9.12.2025"
                match = re.match(r'(\d+),?\s*de\s+(\d+[./]\d+[./]\d+)', text)
                if match:
                    number = int(match.group(1))
                    date_str = match.group(2)  # DD.MM.YYYY format
                    
                    # Get description from second cell
                    description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    
                    amendments.append({
                        "number": number,
                        "date_str": date_str,
                        "url": href,
                        "description": description[:500]  # Truncate long descriptions
                    })
    
    return amendments


def fetch_amendments(
    output_dir: str = "data/raw/amendments",
    max_amendments: int | None = None  # None = all
) -> dict:
    """
    Fetch all constitutional amendments.
    
    Args:
        output_dir: Directory to save amendment files
        max_amendments: Limit number of amendments (for testing)
    
    Returns:
        dict with metadata and file paths
    """
    scraper = PlanaltoScraper(output_dir=output_dir)
    
    # 1. Fetch amendments index
    index_url = f"{scraper.BASE_URL}/Emendas/Emc/quadro_emc.htm"
    index_html = scraper.fetch(index_url)
    
    if not index_html:
        raise RuntimeError("Failed to fetch amendments index")
    
    # Save index
    scraper.save_html(index_html, "quadro_emc.htm")
    
    # 2. Parse index to get amendment list
    amendments = parse_amendments_index(index_html)
    print(f"Found {len(amendments)} amendments")
    
    if max_amendments:
        amendments = amendments[:max_amendments]
    
    # 3. Fetch each amendment
    results = {
        "index": amendments,
        "files": []
    }
    
    for amend in amendments:
        # Construct full URL
        if amend["url"].startswith("http"):
            url = amend["url"]
        else:
            # Handle relative URLs
            url = f"{scraper.BASE_URL}/Emendas/Emc/{amend['url']}"
        
        content = scraper.fetch(url)
        if content:
            filename = f"emc{amend['number']}.htm"
            filepath = scraper.save_html(content, filename)
            results["files"].append({
                "number": amend["number"],
                "path": str(filepath)
            })
    
    # 4. Save metadata as JSON
    metadata_path = Path(output_dir) / "amendments_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(results["index"], f, ensure_ascii=False, indent=2)
    
    return results


def verify_amendments_download(output_dir: str = "data/raw/amendments") -> bool:
    """Verify that amendment files were downloaded correctly."""
    output_path = Path(output_dir)
    
    # Check index exists
    index_file = output_path / "quadro_emc.htm"
    metadata_file = output_path / "amendments_metadata.json"
    
    checks = {
        "index_exists": index_file.exists(),
        "metadata_exists": metadata_file.exists(),
    }
    
    # Check amendment files
    amendment_files = list(output_path.glob("emc*.htm"))
    checks["has_amendment_files"] = len(amendment_files) > 0
    checks["amendment_count"] = len(amendment_files)
    
    # Sample content check
    if amendment_files:
        sample = amendment_files[0]
        content = sample.read_text(encoding='utf-8')
        checks["sample_has_content"] = len(content) > 1000
        checks["sample_has_art"] = "Art." in content or "art." in content
    
    print("Amendments Download Verification:")
    for check, value in checks.items():
        if isinstance(value, bool):
            status = "✓" if value else "✗"
            print(f"  {status} {check}")
        else:
            print(f"  • {check}: {value}")
    
    return checks.get("index_exists", False) and checks.get("has_amendment_files", False)


if __name__ == "__main__":
    # Test with first 5 amendments
    fetch_amendments(max_amendments=5)
    verify_amendments_download()

