# Phase 2: Structural Parsing

## Objective
Convert raw HTML legal text into a structured, hierarchical Intermediate Representation (IR) using semantic segmentation based on Brazilian legal document structure.

---

## 2.1 Legal Document Hierarchy

### Brazilian Constitution Structure

The Brazilian Constitution follows a strict hierarchical structure:

```
Constituição (Norm)
├── TÍTULO I (Title)
│   └── [Articles directly under title, no chapters]
├── TÍTULO II (Title)
│   ├── CAPÍTULO I (Chapter)
│   │   └── Art. 5º (Article)
│   │       ├── I - ... (Item/Inciso)
│   │       ├── II - ... (Item/Inciso)
│   │       │   ├── a) ... (Letter/Alínea)
│   │       │   └── b) ... (Letter/Alínea)
│   │       ├── § 1º ... (Paragraph/Parágrafo)
│   │       └── § 2º ...
│   ├── CAPÍTULO II (Chapter)
│   │   ├── Seção I (Section)
│   │   │   └── Art. 7º ...
│   │   └── Seção II (Section)
│   └── ...
└── ADCT (Transitional Provisions)
```

### Component Types (Paper's Terminology)

| Type | Portuguese | Pattern | Example |
|------|------------|---------|---------|
| `title` | Título | `TÍTULO [ROMAN]` | TÍTULO I |
| `chapter` | Capítulo | `CAPÍTULO [ROMAN]` | CAPÍTULO I |
| `section` | Seção | `Seção [ROMAN]` | Seção I |
| `subsection` | Subseção | `Subseção [ROMAN]` | Subseção I |
| `article` | Artigo | `Art. [N]` | Art. 5º |
| `paragraph` | Parágrafo | `§ [N]` or `Parágrafo único` | § 1º |
| `item` | Inciso | `[ROMAN] -` | I - |
| `letter` | Alínea | `[a-z])` | a) |

---

## 2.2 Data Models

### 2.2.1 Pydantic Models

**File:** `src/parser/models.py`

```python
"""Pydantic models for parsed legal components."""

from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class AmendmentEvent(BaseModel):
    """An event that modified a legal component."""
    
    event_type: Literal["created", "modified", "repealed", "reference"]
    amendment_number: int
    amendment_date: Optional[date] = None
    amendment_date_str: str  # Original string like "2004" or "30.12.2004"
    description: Optional[str] = None  # "Incluído pela EC nº 45"
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "modified",
                "amendment_number": 45,
                "amendment_date": "2004-12-30",
                "amendment_date_str": "30.12.2004",
                "description": "Redação dada pela Emenda Constitucional nº 45, de 2004"
            }
        }


class LegalComponent(BaseModel):
    """A component of the legal document hierarchy."""
    
    # Identity
    component_type: Literal[
        "norm", "title", "chapter", "section", "subsection",
        "article", "paragraph", "item", "letter"
    ]
    component_id: str  # Unique ID like "art_5", "art_5_par_1", "art_5_inc_I"
    ordering_id: str   # For ordering: "01", "05", "I", "a"
    
    # Content
    header: Optional[str] = None  # "TÍTULO I", "Art. 5º"
    subheader: Optional[str] = None  # "Dos Princípios Fundamentais"
    content: Optional[str] = None  # The actual legal text
    full_text: str  # Header + subheader + content combined
    
    # Hierarchy
    parent_id: Optional[str] = None
    children: List["LegalComponent"] = Field(default_factory=list)
    depth: int = 0
    
    # Temporal metadata
    is_original: bool = True  # True if existed in 1988 original
    events: List[AmendmentEvent] = Field(default_factory=list)
    is_revoked: bool = False
    
    # Source tracking
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "component_type": "article",
                "component_id": "art_5",
                "ordering_id": "5",
                "header": "Art. 5º",
                "content": "Todos são iguais perante a lei...",
                "full_text": "Art. 5º Todos são iguais perante a lei...",
                "parent_id": "tit_II_cap_I",
                "is_original": True,
                "events": []
            }
        }


# Enable forward references
LegalComponent.model_rebuild()


class ParsedConstitution(BaseModel):
    """The complete parsed constitution."""
    
    name: str = "Constituição da República Federativa do Brasil"
    official_id: str = "CF1988"
    enactment_date: date = date(1988, 10, 5)
    
    # The root contains all top-level titles
    components: List[LegalComponent] = Field(default_factory=list)
    
    # Statistics
    total_titles: int = 0
    total_chapters: int = 0
    total_articles: int = 0
    total_amendments_referenced: int = 0
    
    # Metadata
    parse_timestamp: Optional[str] = None
    source_file: Optional[str] = None
```

---

## 2.3 Parser Implementation

### 2.3.1 Pattern Definitions

**File:** `src/parser/patterns.py`

```python
"""Regex patterns for legal document parsing."""

import re

# Component header patterns
PATTERNS = {
    "title": re.compile(
        r'^TÍTULO\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "chapter": re.compile(
        r'^CAPÍTULO\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "section": re.compile(
        r'^Seção\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "subsection": re.compile(
        r'^Subseção\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "article": re.compile(
        r'^Art\.\s*(\d+)[º°]?\s*[-.]?\s*',
        re.IGNORECASE
    ),
    "paragraph": re.compile(
        r'^§\s*(\d+)[º°]?\s*[-.]?\s*|^Parágrafo\s+único\s*[-.]?\s*',
        re.IGNORECASE
    ),
    "item": re.compile(
        r'^([IVXLCDM]+)\s*[-–]\s*',
        re.IGNORECASE
    ),
    "letter": re.compile(
        r'^([a-z])\)\s*',
        re.IGNORECASE
    ),
}

# Amendment markers
AMENDMENT_PATTERNS = {
    "included": re.compile(
        r'\(Incluíd[oa]\s+pela\s+Emenda\s+Constitucional\s+n[º°]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "modified": re.compile(
        r'\(Redação\s+dada\s+pela\s+Emenda\s+Constitucional\s+n[º°]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "repealed": re.compile(
        r'\(Revogad[oa]\s+pela\s+Emenda\s+Constitucional\s+n[º°]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "reference": re.compile(
        r'\(Vide\s+Emenda\s+Constitucional\s+n[º°]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
}


def roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer."""
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    result = 0
    prev = 0
    for char in reversed(roman.upper()):
        curr = values.get(char, 0)
        if curr < prev:
            result -= curr
        else:
            result += curr
        prev = curr
    return result


def detect_component_type(text: str) -> tuple[str, str, str] | None:
    """
    Detect the component type from text.
    
    Returns:
        Tuple of (component_type, ordering_id, remaining_text) or None
    """
    text = text.strip()
    
    # Check each pattern in order of specificity
    for comp_type in ["title", "chapter", "section", "subsection"]:
        match = PATTERNS[comp_type].match(text)
        if match:
            roman = match.group(1)
            ordering = str(roman_to_int(roman)).zfill(2)
            remaining = text[match.end():].strip()
            return (comp_type, ordering, remaining)
    
    # Article
    match = PATTERNS["article"].match(text)
    if match:
        num = match.group(1)
        remaining = text[match.end():].strip()
        return ("article", num, remaining)
    
    # Paragraph
    match = PATTERNS["paragraph"].match(text)
    if match:
        if "único" in text.lower():
            ordering = "unico"
        else:
            ordering = match.group(1) if match.group(1) else "unico"
        remaining = text[match.end():].strip()
        return ("paragraph", ordering, remaining)
    
    # Item (Roman numeral)
    match = PATTERNS["item"].match(text)
    if match:
        roman = match.group(1)
        remaining = text[match.end():].strip()
        return ("item", roman.upper(), remaining)
    
    # Letter
    match = PATTERNS["letter"].match(text)
    if match:
        letter = match.group(1).lower()
        remaining = text[match.end():].strip()
        return ("letter", letter, remaining)
    
    return None


def extract_amendments(text: str) -> list[dict]:
    """Extract amendment markers from text."""
    amendments = []
    
    for event_type, pattern in AMENDMENT_PATTERNS.items():
        for match in pattern.finditer(text):
            number = int(match.group(1))
            date_str = match.group(2)
            
            amendments.append({
                "event_type": event_type if event_type != "included" else "created",
                "amendment_number": number,
                "amendment_date_str": date_str,
                "description": match.group(0)
            })
    
    return amendments
```

### 2.3.2 Main Parser

**File:** `src/parser/legal_parser.py`

```python
"""Hierarchical parser for Brazilian legal documents."""

from typing import List, Optional, Generator
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import json
import logging

from .models import LegalComponent, ParsedConstitution, AmendmentEvent
from .patterns import detect_component_type, extract_amendments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalDocumentParser:
    """Parser for Brazilian legal documents (Constitution)."""
    
    # Hierarchy levels for proper nesting
    HIERARCHY = {
        "norm": 0,
        "title": 1,
        "chapter": 2,
        "section": 3,
        "subsection": 4,
        "article": 5,
        "paragraph": 6,
        "item": 7,
        "letter": 8,
    }
    
    def __init__(self):
        self.current_path: List[LegalComponent] = []  # Stack for hierarchy
        self.all_components: List[LegalComponent] = []
        self.stats = {
            "titles": 0,
            "chapters": 0,
            "sections": 0,
            "articles": 0,
            "paragraphs": 0,
            "items": 0,
            "letters": 0,
            "amendments": set(),
        }
    
    def parse_file(self, filepath: str | Path) -> ParsedConstitution:
        """Parse a constitution HTML file."""
        filepath = Path(filepath)
        logger.info(f"Parsing: {filepath}")
        
        content = filepath.read_text(encoding='utf-8')
        soup = BeautifulSoup(content, 'lxml')
        
        # Reset state
        self.current_path = []
        self.all_components = []
        
        # Extract text blocks
        paragraphs = self._extract_paragraphs(soup)
        logger.info(f"Found {len(paragraphs)} text blocks")
        
        # Parse each paragraph
        root_components = []
        
        for i, (text, amendments_in_text) in enumerate(paragraphs):
            component = self._parse_text_block(text, amendments_in_text, i)
            if component:
                # If it's a top-level component (title), add to root
                if component.component_type == "title":
                    root_components.append(component)
                # Otherwise it was already added to parent via stack
        
        # Build the result
        result = ParsedConstitution(
            components=root_components,
            total_titles=self.stats["titles"],
            total_chapters=self.stats["chapters"],
            total_articles=self.stats["articles"],
            total_amendments_referenced=len(self.stats["amendments"]),
            parse_timestamp=datetime.now().isoformat(),
            source_file=str(filepath),
        )
        
        return result
    
    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[tuple[str, list]]:
        """Extract text paragraphs from HTML."""
        results = []
        
        for p in soup.find_all(['p', 'div']):
            # Get text content
            text = p.get_text(separator=' ', strip=True)
            if not text or len(text) < 3:
                continue
            
            # Extract amendment markers from the raw HTML
            amendments = extract_amendments(str(p))
            
            results.append((text, amendments))
        
        return results
    
    def _parse_text_block(
        self, 
        text: str, 
        amendments: list,
        line_num: int
    ) -> Optional[LegalComponent]:
        """Parse a single text block into a component."""
        
        # Detect component type
        detection = detect_component_type(text)
        
        if not detection:
            # This is continuation text - append to current component
            if self.current_path:
                current = self.current_path[-1]
                current.content = (current.content or "") + " " + text
                current.full_text = (current.full_text or "") + " " + text
            return None
        
        comp_type, ordering, remaining = detection
        
        # Update stats
        if comp_type in self.stats:
            self.stats[comp_type + "s" if not comp_type.endswith("s") else comp_type] += 1
        elif comp_type + "s" in self.stats:
            self.stats[comp_type + "s"] += 1
        
        # Track amendments
        for a in amendments:
            self.stats["amendments"].add(a.get("amendment_number"))
        
        # Create component ID
        component_id = self._generate_component_id(comp_type, ordering)
        
        # Find parent
        parent = self._find_parent(comp_type)
        parent_id = parent.component_id if parent else None
        
        # Create component
        component = LegalComponent(
            component_type=comp_type,
            component_id=component_id,
            ordering_id=ordering,
            header=text.split()[0] if text else None,  # First word as header
            content=remaining,
            full_text=text,
            parent_id=parent_id,
            depth=self.HIERARCHY.get(comp_type, 0),
            is_original=len(amendments) == 0,
            events=[
                AmendmentEvent(**a) for a in amendments
            ],
            is_revoked=any(a.get("event_type") == "repealed" for a in amendments),
            source_line_start=line_num,
        )
        
        # Add to parent's children
        if parent:
            parent.children.append(component)
        
        # Update stack
        self._update_stack(component)
        
        self.all_components.append(component)
        
        return component
    
    def _generate_component_id(self, comp_type: str, ordering: str) -> str:
        """Generate a unique component ID based on current path."""
        if comp_type == "title":
            return f"tit_{ordering}"
        
        # Build path-based ID
        path_parts = []
        for comp in self.current_path:
            if comp.component_type == "title":
                path_parts.append(f"tit_{comp.ordering_id}")
            elif comp.component_type == "chapter":
                path_parts.append(f"cap_{comp.ordering_id}")
            elif comp.component_type == "section":
                path_parts.append(f"sec_{comp.ordering_id}")
            elif comp.component_type == "article":
                path_parts.append(f"art_{comp.ordering_id}")
            elif comp.component_type == "paragraph":
                path_parts.append(f"par_{comp.ordering_id}")
            elif comp.component_type == "item":
                path_parts.append(f"inc_{comp.ordering_id}")
        
        # Add current component
        type_abbrev = {
            "title": "tit",
            "chapter": "cap",
            "section": "sec",
            "subsection": "subsec",
            "article": "art",
            "paragraph": "par",
            "item": "inc",
            "letter": "ali",
        }
        
        abbrev = type_abbrev.get(comp_type, comp_type[:3])
        path_parts.append(f"{abbrev}_{ordering}")
        
        return "_".join(path_parts)
    
    def _find_parent(self, comp_type: str) -> Optional[LegalComponent]:
        """Find the appropriate parent for a component type."""
        comp_level = self.HIERARCHY.get(comp_type, 0)
        
        # Pop stack until we find a valid parent
        while self.current_path:
            potential_parent = self.current_path[-1]
            parent_level = self.HIERARCHY.get(potential_parent.component_type, 0)
            
            if parent_level < comp_level:
                return potential_parent
            else:
                self.current_path.pop()
        
        return None
    
    def _update_stack(self, component: LegalComponent):
        """Update the component stack with the new component."""
        comp_level = self.HIERARCHY.get(component.component_type, 0)
        
        # Remove components at same or lower level
        while self.current_path:
            top_level = self.HIERARCHY.get(self.current_path[-1].component_type, 0)
            if top_level >= comp_level:
                self.current_path.pop()
            else:
                break
        
        self.current_path.append(component)


def parse_constitution(
    input_file: str = "data/raw/constitution/constituicao.htm",
    output_file: str = "data/intermediate/constitution.json"
) -> ParsedConstitution:
    """Parse the constitution and save to JSON."""
    parser = LegalDocumentParser()
    result = parser.parse_file(input_file)
    
    # Save to JSON
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved parsed constitution to {output_path}")
    logger.info(f"Statistics: {parser.stats}")
    
    return result


if __name__ == "__main__":
    parse_constitution()
```

---

## 2.4 Amendment Parser

**File:** `src/parser/amendment_parser.py`

```python
"""Parser for individual amendment documents."""

from typing import List, Optional
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date
import re
import json
import logging

from .models import AmendmentEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AmendmentInfo:
    """Information about a constitutional amendment."""
    
    def __init__(
        self,
        number: int,
        date: Optional[date],
        date_str: str,
        articles_modified: List[str],
        articles_added: List[str],
        articles_repealed: List[str],
        full_text: str,
    ):
        self.number = number
        self.date = date
        self.date_str = date_str
        self.articles_modified = articles_modified
        self.articles_added = articles_added
        self.articles_repealed = articles_repealed
        self.full_text = full_text


def parse_date(date_str: str) -> Optional[date]:
    """Parse Brazilian date format to date object."""
    # Try various formats
    formats = [
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d de %B de %Y",
    ]
    
    # Clean the string
    date_str = date_str.strip()
    
    for fmt in formats:
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
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
    
    content = filepath.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'lxml')
    
    full_text = soup.get_text(separator='\n', strip=True)
    
    # Extract date from content
    date_pattern = re.compile(
        r'de\s+(\d+)\s+de\s+(\w+)\s+de\s+(\d{4})',
        re.IGNORECASE
    )
    date_match = date_pattern.search(full_text[:500])
    
    date_str = ""
    amendment_date = None
    if date_match:
        date_str = date_match.group(0)
        # Parse it
        amendment_date = parse_date(date_str)
    
    # Find articles affected
    # Patterns like "Art. 5º", "art. 6", "artigo 7"
    article_pattern = re.compile(r'art(?:igo)?\.?\s*(\d+)', re.IGNORECASE)
    articles_mentioned = set(article_pattern.findall(full_text))
    
    # Determine modification type by context
    articles_modified = []
    articles_added = []
    articles_repealed = []
    
    # Look for specific patterns
    if re.search(r'nova\s+redação|dá\s+nova\s+redação', full_text, re.IGNORECASE):
        articles_modified = list(articles_mentioned)
    if re.search(r'acrescenta|inclui|adiciona', full_text, re.IGNORECASE):
        articles_added = list(articles_mentioned)
    if re.search(r'revoga|suprime', full_text, re.IGNORECASE):
        articles_repealed = list(articles_mentioned)
    
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
```

---

## 2.5 Validation Checks

### Check 2.5.1: Parser Unit Tests

**File:** `tests/unit/test_parser.py`

```python
"""Unit tests for legal document parser."""

import pytest
from src.parser.patterns import detect_component_type, extract_amendments, roman_to_int
from src.parser.models import LegalComponent, AmendmentEvent


class TestPatternDetection:
    """Tests for pattern detection."""
    
    def test_title_detection(self):
        result = detect_component_type("TÍTULO I")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "title"
        assert ordering == "01"
    
    def test_chapter_detection(self):
        result = detect_component_type("CAPÍTULO IV")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "chapter"
        assert ordering == "04"
    
    def test_article_detection(self):
        result = detect_component_type("Art. 5º Todos são iguais perante a lei")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "article"
        assert ordering == "5"
        assert "iguais" in remaining
    
    def test_paragraph_detection(self):
        result = detect_component_type("§ 1º As normas definidoras...")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "paragraph"
        assert ordering == "1"
    
    def test_paragraph_unico_detection(self):
        result = detect_component_type("Parágrafo único. Todo o poder emana do povo")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "paragraph"
        assert ordering == "unico"
    
    def test_item_detection(self):
        result = detect_component_type("I - a soberania;")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "item"
        assert ordering == "I"
    
    def test_letter_detection(self):
        result = detect_component_type("a) proteção às participações individuais")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "letter"
        assert ordering == "a"
    
    def test_plain_text_returns_none(self):
        result = detect_component_type("Este é um texto normal sem marcadores")
        assert result is None


class TestRomanNumerals:
    """Tests for Roman numeral conversion."""
    
    @pytest.mark.parametrize("roman,expected", [
        ("I", 1),
        ("IV", 4),
        ("V", 5),
        ("IX", 9),
        ("X", 10),
        ("XL", 40),
        ("L", 50),
        ("XC", 90),
        ("C", 100),
        ("LXXVIII", 78),
    ])
    def test_roman_to_int(self, roman, expected):
        assert roman_to_int(roman) == expected


class TestAmendmentExtraction:
    """Tests for amendment marker extraction."""
    
    def test_extract_included(self):
        text = "(Incluído pela Emenda Constitucional nº 45, de 2004)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "created"
        assert amendments[0]["amendment_number"] == 45
    
    def test_extract_modified(self):
        text = "(Redação dada pela Emenda Constitucional nº 115, de 2022)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "modified"
        assert amendments[0]["amendment_number"] == 115
    
    def test_extract_repealed(self):
        text = "(Revogado pela Emenda Constitucional nº 32, de 2001)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "repealed"
        assert amendments[0]["amendment_number"] == 32
    
    def test_extract_multiple(self):
        text = """
        (Incluído pela Emenda Constitucional nº 45, de 2004)
        (Redação dada pela Emenda Constitucional nº 115, de 2022)
        """
        amendments = extract_amendments(text)
        assert len(amendments) == 2


class TestLegalComponentModel:
    """Tests for Pydantic models."""
    
    def test_create_article(self):
        article = LegalComponent(
            component_type="article",
            component_id="art_5",
            ordering_id="5",
            content="Todos são iguais perante a lei",
            full_text="Art. 5º Todos são iguais perante a lei",
        )
        assert article.component_type == "article"
        assert article.is_original == True
        assert len(article.events) == 0
    
    def test_article_with_amendment(self):
        event = AmendmentEvent(
            event_type="modified",
            amendment_number=45,
            amendment_date_str="2004",
        )
        article = LegalComponent(
            component_type="article",
            component_id="art_5",
            ordering_id="5",
            content="Modified text",
            full_text="Art. 5º Modified text",
            is_original=False,
            events=[event],
        )
        assert article.is_original == False
        assert len(article.events) == 1
```

### Check 2.5.2: Integration Tests

**File:** `tests/integration/test_parsing.py`

```python
"""Integration tests for parsing pipeline."""

import pytest
from pathlib import Path
import json

from src.parser.legal_parser import LegalDocumentParser, parse_constitution
from src.parser.models import ParsedConstitution


@pytest.fixture
def constitution_file():
    """Path to downloaded constitution file."""
    path = Path("data/raw/constitution/constituicao.htm")
    if not path.exists():
        pytest.skip("Constitution file not downloaded yet")
    return path


def test_parse_constitution_structure(constitution_file):
    """Test that parser produces correct structure."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    assert isinstance(result, ParsedConstitution)
    assert result.official_id == "CF1988"
    assert len(result.components) > 0  # Has titles


def test_parse_constitution_stats(constitution_file):
    """Test that parser finds expected number of components."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Brazilian Constitution has 9 titles
    assert result.total_titles >= 9, f"Expected at least 9 titles, got {result.total_titles}"
    
    # Has many chapters
    assert result.total_chapters >= 20, f"Expected at least 20 chapters, got {result.total_chapters}"
    
    # Has 250 articles
    assert result.total_articles >= 250, f"Expected at least 250 articles, got {result.total_articles}"


def test_article_5_structure(constitution_file):
    """Test that Article 5 is correctly parsed with its items."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Find Article 5
    art_5 = None
    for comp in parser.all_components:
        if comp.component_type == "article" and comp.ordering_id == "5":
            art_5 = comp
            break
    
    assert art_5 is not None, "Article 5 not found"
    assert "iguais" in art_5.full_text.lower(), "Article 5 should mention equality"
    
    # Article 5 has 78+ items (incisos)
    items = [c for c in art_5.children if c.component_type == "item"]
    assert len(items) >= 70, f"Article 5 should have 70+ items, got {len(items)}"


def test_amendment_markers_detected(constitution_file):
    """Test that amendment markers are detected."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Should find components with amendments
    amended_components = [
        c for c in parser.all_components 
        if len(c.events) > 0
    ]
    
    assert len(amended_components) > 50, \
        f"Expected 50+ amended components, got {len(amended_components)}"
    
    # Check for EC 45 (famous amendment)
    ec45_found = any(
        any(e.amendment_number == 45 for e in c.events)
        for c in parser.all_components
    )
    assert ec45_found, "EC 45 not found in any component"


def test_hierarchy_integrity(constitution_file):
    """Test that hierarchy relationships are valid."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Build ID lookup
    id_lookup = {c.component_id: c for c in parser.all_components}
    
    for comp in parser.all_components:
        if comp.parent_id:
            parent = id_lookup.get(comp.parent_id)
            assert parent is not None, f"Parent {comp.parent_id} not found for {comp.component_id}"
            
            # Check hierarchy level
            assert parser.HIERARCHY[parent.component_type] < parser.HIERARCHY[comp.component_type], \
                f"Parent {parent.component_type} should be higher level than {comp.component_type}"


def test_output_json_valid(constitution_file, tmp_path):
    """Test that output JSON is valid and complete."""
    output_file = tmp_path / "constitution.json"
    
    result = parse_constitution(
        input_file=str(constitution_file),
        output_file=str(output_file)
    )
    
    assert output_file.exists()
    
    with open(output_file) as f:
        data = json.load(f)
    
    assert "components" in data
    assert len(data["components"]) > 0
    assert data["official_id"] == "CF1988"
```

---

## 2.6 Expected Output

### Sample constitution.json structure

```json
{
  "name": "Constituição da República Federativa do Brasil",
  "official_id": "CF1988",
  "enactment_date": "1988-10-05",
  "components": [
    {
      "component_type": "title",
      "component_id": "tit_01",
      "ordering_id": "01",
      "header": "TÍTULO",
      "subheader": "Dos Princípios Fundamentais",
      "children": [
        {
          "component_type": "article",
          "component_id": "tit_01_art_1",
          "ordering_id": "1",
          "header": "Art.",
          "content": "A República Federativa do Brasil...",
          "full_text": "Art. 1º A República Federativa do Brasil...",
          "is_original": true,
          "events": [],
          "children": [
            {
              "component_type": "item",
              "component_id": "tit_01_art_1_inc_I",
              "ordering_id": "I",
              "content": "a soberania;",
              "full_text": "I - a soberania;",
              "is_original": true
            }
          ]
        }
      ]
    }
  ],
  "total_titles": 9,
  "total_chapters": 27,
  "total_articles": 250,
  "total_amendments_referenced": 137
}
```

---

## 2.7 Success Criteria

| Criterion | Metric |
|-----------|--------|
| Titles detected | 9 titles |
| Chapters detected | 25+ chapters |
| Articles detected | 250+ articles |
| Items detected | 1000+ items |
| Amendment markers extracted | 100+ unique amendments |
| Hierarchy valid | All parent-child relationships valid |
| Article 5 items | 70+ items under Article 5 |
| JSON output valid | Passes json.load() |

---

## 2.8 Troubleshooting

### Pattern Not Matching
```python
# Debug by testing pattern in isolation
from src.parser.patterns import PATTERNS
import re

text = "Your problematic text here"
for name, pattern in PATTERNS.items():
    match = pattern.match(text)
    print(f"{name}: {match}")
```

### Hierarchy Issues
```python
# Print stack at each step
def _update_stack(self, component):
    print(f"Adding: {component.component_type} {component.ordering_id}")
    print(f"Stack: {[c.component_type for c in self.current_path]}")
    # ... rest of method
```

### Missing Content
```python
# Check what paragraphs are being skipped
# Add logging to _extract_paragraphs
```

---

## 2.9 Phase Completion Checklist

- [ ] Pydantic models defined
- [ ] Pattern detection implemented
- [ ] Amendment extraction implemented
- [ ] Hierarchical parser implemented
- [ ] Amendment parser implemented
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Constitution parsed to JSON
- [ ] Amendments parsed to JSON
- [ ] Statistics match expected values

**Next Phase:** `04_GRAPH_SCHEMA.md`

