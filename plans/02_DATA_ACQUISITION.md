# Phase 1: Data Acquisition

## Objective
Scrape the Brazilian Federal Constitution and all amendments from the Planalto government website.

---

## 1.1 Source Analysis

### Primary URLs

| Resource | URL | Content |
|----------|-----|---------|
| Main Constitution | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` | Full text with inline amendments |
| Compiled Version | `https://www.planalto.gov.br/ccivil_03/constituicao/ConstituicaoCompilado.htm` | Consolidated current text |
| Amendments Index | `https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm` | List of all amendments |
| Individual Amendment | `https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/emc{N}.htm` | Amendment N details |

### HTML Structure Analysis (Based on Live Inspection)

The Planalto website uses a **legacy HTML structure** with these patterns:

```
Structure Hierarchy:
├── <blockquote> - Main content container
├── <p> - Paragraphs containing:
│   ├── <span class=""> with "TÍTULO X" - Title headers
│   ├── <span class=""> with "CAPÍTULO X" - Chapter headers  
│   ├── <span class=""> with "Seção X" - Section headers
│   ├── "Art. N" text - Article content
│   ├── Roman numerals (I, II, III) - Items/Incisos
│   ├── Lowercase letters (a, b, c) - Subitems/Alíneas
│   ├── "§ N" - Paragraphs (parágrafos)
│   └── <a href="Emendas/..."> - Amendment references
```

### Amendment Markers (Critical for Temporal Data)

Look for these patterns in the HTML:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `(Incluído pela Emenda Constitucional nº X, de YYYY)` | Added by amendment | New article/item |
| `(Redação dada pela Emenda Constitucional nº X, de YYYY)` | Modified by amendment | Text changed |
| `(Revogado pela Emenda Constitucional nº X, de YYYY)` | Repealed by amendment | No longer valid |
| `(Vide Emenda Constitucional nº X, de YYYY)` | See amendment | Reference only |
| Strikethrough text (`<s>` or `<strike>`) | Historical/repealed text | Previous version |

---

## 1.2 Implementation

### 1.2.1 Base Scraper Class

**File:** `src/collection/scraper.py`

```python
"""Base scraper with rate limiting and error handling."""

import time
import requests
from typing import Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlanaltoScraper:
    """Scraper for Planalto government website."""
    
    BASE_URL = "https://www.planalto.gov.br/ccivil_03/constituicao"
    
    def __init__(
        self,
        delay_seconds: float = 1.0,
        user_agent: str = "SAT-Graph-RAG-Research/1.0",
        output_dir: str = "data/raw"
    ):
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.time()
    
    def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL with rate limiting and error handling."""
        self._rate_limit()
        
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Handle encoding (Planalto uses ISO-8859-1 / Latin-1)
            response.encoding = response.apparent_encoding or 'iso-8859-1'
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def save_html(self, content: str, filename: str, subdir: str = "") -> Path:
        """Save HTML content to file."""
        if subdir:
            save_dir = self.output_dir / subdir
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_dir = self.output_dir
        
        filepath = save_dir / filename
        filepath.write_text(content, encoding='utf-8')
        logger.info(f"Saved: {filepath}")
        return filepath
```

### 1.2.2 Constitution Scraper

**File:** `src/collection/fetch_constitution.py`

```python
"""Fetch the Brazilian Federal Constitution."""

from .scraper import PlanaltoScraper
from pathlib import Path


def fetch_constitution(output_dir: str = "data/raw/constitution") -> dict:
    """
    Fetch all constitution-related pages.
    
    Returns:
        dict with paths to downloaded files
    """
    scraper = PlanaltoScraper(output_dir=output_dir)
    results = {}
    
    # 1. Main constitution page (with amendment markers)
    main_url = f"{scraper.BASE_URL}/constituicao.htm"
    main_content = scraper.fetch(main_url)
    if main_content:
        results["main"] = scraper.save_html(
            main_content, 
            "constituicao.htm"
        )
    
    # 2. Compiled version (current consolidated text)
    compiled_url = f"{scraper.BASE_URL}/ConstituicaoCompilado.htm"
    compiled_content = scraper.fetch(compiled_url)
    if compiled_content:
        results["compiled"] = scraper.save_html(
            compiled_content,
            "constituicao_compilado.htm"
        )
    
    # 3. ADCT (Transitional Provisions) - often on same page but check
    # The ADCT is typically at anchor #adct in the main page
    
    return results


def verify_constitution_download(output_dir: str = "data/raw/constitution") -> bool:
    """Verify that constitution files were downloaded correctly."""
    output_path = Path(output_dir)
    
    main_file = output_path / "constituicao.htm"
    compiled_file = output_path / "constituicao_compilado.htm"
    
    checks = {
        "main_exists": main_file.exists(),
        "compiled_exists": compiled_file.exists(),
        "main_has_content": main_file.stat().st_size > 100000 if main_file.exists() else False,
        "compiled_has_content": compiled_file.stat().st_size > 100000 if compiled_file.exists() else False,
    }
    
    # Content checks
    if main_file.exists():
        content = main_file.read_text(encoding='utf-8')
        checks["has_title_i"] = "TÍTULO I" in content
        checks["has_art_1"] = "Art. 1" in content
        checks["has_art_5"] = "Art. 5" in content
        checks["has_amendments"] = "Emenda Constitucional" in content
    
    all_passed = all(checks.values())
    
    print("Constitution Download Verification:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
    
    return all_passed


if __name__ == "__main__":
    fetch_constitution()
    verify_constitution_download()
```

### 1.2.3 Amendments Scraper

**File:** `src/collection/fetch_amendments.py`

```python
"""Fetch all constitutional amendments."""

import re
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
                
                # Parse "137, de 9.12.2025"
                match = re.match(r'(\d+),?\s*de\s+(\d+\.\d+\.\d+)', text)
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
    max_amendments: int = None  # None = all
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
    import json
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
```

---

## 1.3 Scraping Script

**File:** `scripts/run_scraper.py`

```python
#!/usr/bin/env python
"""Run the full scraping pipeline."""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
```

---

## 1.4 Validation Checks

### Check 1.4.1: URL Accessibility

```python
# tests/integration/test_scraping.py

import requests
import pytest


URLS_TO_CHECK = [
    "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    "https://www.planalto.gov.br/ccivil_03/constituicao/ConstituicaoCompilado.htm",
    "https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm",
]


@pytest.mark.parametrize("url", URLS_TO_CHECK)
def test_url_accessible(url):
    """Test that required URLs are accessible."""
    response = requests.head(url, timeout=10)
    assert response.status_code == 200, f"URL not accessible: {url}"


def test_constitution_has_expected_content():
    """Test that constitution page has expected content."""
    url = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"
    response = requests.get(url, timeout=30)
    response.encoding = 'iso-8859-1'
    content = response.text
    
    # Must contain key markers
    assert "TÍTULO I" in content, "Missing TÍTULO I"
    assert "Art. 1" in content, "Missing Art. 1"
    assert "Art. 5" in content, "Missing Art. 5"
    assert "Emenda Constitucional" in content, "Missing amendment references"
```

### Check 1.4.2: Downloaded File Integrity

```python
# tests/integration/test_scraping.py (continued)

from pathlib import Path
import json


def test_constitution_files_exist():
    """Test that constitution files were downloaded."""
    const_dir = Path("data/raw/constitution")
    
    assert (const_dir / "constituicao.htm").exists()
    assert (const_dir / "constituicao_compilado.htm").exists()


def test_constitution_file_sizes():
    """Test that constitution files have reasonable size."""
    const_dir = Path("data/raw/constitution")
    
    main_file = const_dir / "constituicao.htm"
    assert main_file.stat().st_size > 500_000, "Constitution file too small"


def test_amendments_metadata_valid():
    """Test that amendments metadata is valid JSON."""
    metadata_file = Path("data/raw/amendments/amendments_metadata.json")
    
    assert metadata_file.exists()
    
    with open(metadata_file) as f:
        data = json.load(f)
    
    assert isinstance(data, list)
    assert len(data) > 100, "Expected 100+ amendments"
    
    # Check structure
    for item in data[:5]:
        assert "number" in item
        assert "date_str" in item
        assert "url" in item


def test_amendment_files_match_metadata():
    """Test that downloaded amendments match metadata."""
    amend_dir = Path("data/raw/amendments")
    metadata_file = amend_dir / "amendments_metadata.json"
    
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    expected_numbers = {item["number"] for item in metadata}
    downloaded_files = list(amend_dir.glob("emc*.htm"))
    downloaded_numbers = set()
    
    for f in downloaded_files:
        # Extract number from filename "emc123.htm"
        num = int(f.stem.replace("emc", ""))
        downloaded_numbers.add(num)
    
    missing = expected_numbers - downloaded_numbers
    assert len(missing) == 0, f"Missing amendment files: {missing}"
```

### Check 1.4.3: Content Parsing Readiness

```python
# tests/unit/test_html_structure.py

from bs4 import BeautifulSoup
from pathlib import Path
import re


def test_constitution_has_parseable_structure():
    """Test that constitution HTML has expected structure for parsing."""
    const_file = Path("data/raw/constitution/constituicao.htm")
    content = const_file.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'lxml')
    
    # Find paragraphs
    paragraphs = soup.find_all('p')
    assert len(paragraphs) > 500, "Expected 500+ paragraphs"
    
    # Find article patterns
    article_pattern = re.compile(r'Art\.\s*\d+')
    articles_found = 0
    
    for p in paragraphs:
        text = p.get_text()
        if article_pattern.search(text):
            articles_found += 1
    
    assert articles_found > 200, f"Expected 200+ articles, found {articles_found}"


def test_amendment_markers_present():
    """Test that amendment markers are detectable."""
    const_file = Path("data/raw/constitution/constituicao.htm")
    content = const_file.read_text(encoding='utf-8')
    
    markers = {
        "incluido": r'\(Incluído pela Emenda Constitucional',
        "redacao": r'\(Redação dada pela Emenda Constitucional',
        "revogado": r'\(Revogado pela Emenda Constitucional',
        "vide": r'\(Vide Emenda Constitucional',
    }
    
    for name, pattern in markers.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        print(f"{name}: {len(matches)} occurrences")
        # At least some markers should exist
        assert len(matches) > 0 or name == "revogado", f"No {name} markers found"
```

---

## 1.5 Expected Outputs

After successful completion:

```
data/raw/
├── constitution/
│   ├── constituicao.htm           # ~1-2 MB
│   └── constituicao_compilado.htm # ~800KB-1MB
└── amendments/
    ├── quadro_emc.htm             # Index page
    ├── amendments_metadata.json   # Structured metadata
    ├── emc1.htm                   # Amendment 1
    ├── emc2.htm                   # Amendment 2
    ├── ...
    └── emc137.htm                 # Latest amendment (as of Dec 2025)
```

### Sample amendments_metadata.json

```json
[
  {
    "number": 137,
    "date_str": "9.12.2025",
    "url": "emc137.htm",
    "description": "Altera o art. 155 da Constituição Federal para conceder imunidade do Imposto..."
  },
  {
    "number": 136,
    "date_str": "9.9.2025",
    "url": "emc136.htm",
    "description": "Altera a Constituição Federal, o Ato das Disposições..."
  }
]
```

---

## 1.6 Success Criteria

| Criterion | Metric |
|-----------|--------|
| Constitution main file downloaded | File > 500KB |
| Constitution compiled file downloaded | File > 500KB |
| Amendments index downloaded | File exists |
| Amendments metadata parsed | JSON with 100+ entries |
| All amendment files downloaded | Count matches metadata |
| HTML is parseable | BeautifulSoup parses without errors |
| Article pattern detected | 200+ "Art. N" patterns found |
| Amendment markers detected | Multiple marker types found |

---

## 1.7 Troubleshooting

### Connection Refused
```python
# The site may block automated requests. Try:
# 1. Increase delay between requests
# 2. Use a more browser-like User-Agent
# 3. Try from a different network/VPN
```

### Encoding Issues
```python
# Planalto uses Latin-1 (ISO-8859-1), not UTF-8
# Always decode with:
response.encoding = 'iso-8859-1'
# Then save as UTF-8 for consistency
```

### Missing Amendments
```python
# Some old amendments may have different URL patterns
# Check for variations like:
# - emc001.htm (leading zeros)
# - Emc/emc1.htm vs EMC/emc1.htm (case sensitivity)
```

---

## 1.8 Phase Completion Checklist

- [ ] Scraper classes implemented
- [ ] Constitution main page downloaded
- [ ] Constitution compiled page downloaded  
- [ ] Amendments index downloaded and parsed
- [ ] All amendments downloaded
- [ ] Metadata JSON generated
- [ ] All verification checks pass
- [ ] HTML structure suitable for parsing confirmed

**Next Phase:** `03_STRUCTURAL_PARSING.md`

