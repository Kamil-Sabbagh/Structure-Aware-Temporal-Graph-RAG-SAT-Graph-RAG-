"""Regex patterns for legal document parsing."""

import re

# Component header patterns
# Note: Using flexible patterns to handle encoding variations (ç vs ş, ã vs ă, etc.)
PATTERNS = {
    "title": re.compile(
        r'^T[IÍ]TULO\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "chapter": re.compile(
        r'^CAP[IÍ]TULO\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "section": re.compile(
        r'^Se[çcş][ãaă]o\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "subsection": re.compile(
        r'^Subse[çcş][ãaă]o\s+([IVXLCDM]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    "article": re.compile(
        r'^Art\.\s*(\d+)[º°]?\s*[-.]?\s*',
        re.IGNORECASE
    ),
    "paragraph": re.compile(
        r'^§\s*(\d+)[º°]?\s*[-.]?\s*|^Par[áaă]grafo\s+[úuű]nico\s*[-.]?\s*',
        re.IGNORECASE
    ),
    "item": re.compile(
        r'^([IVXLCDM]+)\s*[-–—]\s*',
        re.IGNORECASE
    ),
    "letter": re.compile(
        r'^([a-z])\)\s*',
        re.IGNORECASE
    ),
}

# Amendment markers - flexible for encoding variations
AMENDMENT_PATTERNS = {
    "included": re.compile(
        r'\(Inclu[íiî]d[oa]\s+pela\s+Emenda\s+Constitucional\s+n[º°ş]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "modified": re.compile(
        r'\(Reda[çcş][ãaă]o\s+dada\s+pela\s+Emenda\s+Constitucional\s+n[º°ş]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "repealed": re.compile(
        r'\(Revogad[oa]\s+pela\s+Emenda\s+Constitucional\s+n[º°ş]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
        re.IGNORECASE
    ),
    "reference": re.compile(
        r'\(Vide\s+Emenda\s+Constitucional\s+n[º°ş]\s*(\d+),?\s*de\s+(\d{4}|\d+[./]\d+[./]\d+)\)',
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
        if "nico" in text.lower():  # "único" with encoding variations
            ordering = "unico"
        else:
            ordering = match.group(1) if match.lastindex and match.group(1) else "unico"
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
                "event_type": "created" if event_type == "included" else event_type,
                "amendment_number": number,
                "amendment_date_str": date_str,
                "description": match.group(0)
            })
    
    return amendments

