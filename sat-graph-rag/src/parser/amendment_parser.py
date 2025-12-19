"""Parser for individual amendment documents."""

from typing import List, Optional
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date
from dataclasses import dataclass
import re
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AmendmentInfo:
    """Information about a constitutional amendment."""
    number: int
    date: Optional[date]
    date_str: str
    articles_modified: List[str]
    articles_added: List[str]
    articles_repealed: List[str]
    full_text: str


def parse_date(date_str: str) -> Optional[date]:
    """Parse Brazilian date format to date object."""
    from datetime import datetime
    
    # Clean the string
    date_str = date_str.strip()
    
    # Try DD.MM.YYYY format
    match = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
    if match:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return date(year, month, day)
        except ValueError:
            pass
    
    # Try to extract just year
    year_match = re.search(r'(\d{4})', date_str)
    if year_match:
        year = int(year_match.group(1))
        return date(year, 1, 1)  # Default to Jan 1
    
    return None


def parse_amendment_file(filepath: str | Path) -> Optional[AmendmentInfo]:
    """Parse an individual amendment file."""
    filepath = Path(filepath)
    
    # Extract amendment number from filename
    match = re.search(r'emc(\d+)', filepath.stem, re.IGNORECASE)
    if not match:
        logger.warning(f"Could not extract amendment number from {filepath}")
        return None
    
    number = int(match.group(1))
    
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None
    
    soup = BeautifulSoup(content, 'lxml')
    
    full_text = soup.get_text(separator='\n', strip=True)
    
    # Extract date from content
    date_pattern = re.compile(
        r'de\s+(\d+)\s+de\s+(\w+)\s+de\s+(\d{4})',
        re.IGNORECASE
    )
    date_match = date_pattern.search(full_text[:1000])
    
    date_str = ""
    amendment_date = None
    if date_match:
        date_str = date_match.group(0)
        # Parse it
        amendment_date = parse_date(date_str)
    
    # Find articles affected
    # Patterns like "Art. 5º", "art. 6", "artigo 7"
    article_pattern = re.compile(r'art(?:igo)?\.?\s*(\d+)', re.IGNORECASE)
    articles_mentioned = list(set(article_pattern.findall(full_text)))
    
    # Determine modification type by context
    articles_modified = []
    articles_added = []
    articles_repealed = []
    
    # Look for specific patterns
    if re.search(r'nova\s+reda[çcş][ãaă]o|d[áaă]\s+nova\s+reda', full_text, re.IGNORECASE):
        articles_modified = articles_mentioned.copy()
    if re.search(r'acrescenta|inclui|adiciona', full_text, re.IGNORECASE):
        articles_added = articles_mentioned.copy()
    if re.search(r'revoga|suprime', full_text, re.IGNORECASE):
        articles_repealed = articles_mentioned.copy()
    
    # If no specific pattern found, default to modified
    if not articles_modified and not articles_added and not articles_repealed:
        articles_modified = articles_mentioned.copy()
    
    return AmendmentInfo(
        number=number,
        date=amendment_date,
        date_str=date_str,
        articles_modified=articles_modified,
        articles_added=articles_added,
        articles_repealed=articles_repealed,
        full_text=full_text[:5000],  # Truncate for storage
    )


def parse_all_amendments(
    input_dir: str = "data/raw/amendments",
    output_file: str = "data/intermediate/amendments/parsed_amendments.json"
) -> List[dict]:
    """Parse all amendment files."""
    input_path = Path(input_dir)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for filepath in sorted(input_path.glob("emc*.htm")):
        info = parse_amendment_file(filepath)
        if info:
            results.append({
                "number": info.number,
                "date": info.date.isoformat() if info.date else None,
                "date_str": info.date_str,
                "articles_modified": info.articles_modified,
                "articles_added": info.articles_added,
                "articles_repealed": info.articles_repealed,
            })
    
    # Sort by number
    results.sort(key=lambda x: x["number"])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Parsed {len(results)} amendments to {output_path}")
    
    return results


if __name__ == "__main__":
    parse_all_amendments()

