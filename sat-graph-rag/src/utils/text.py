"""Text processing utilities."""

import re
import unicodedata
from typing import Optional


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and normalizing unicode.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    
    # Replace multiple whitespace with single space
    text = re.sub(r"\s+", " ", text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def clean_html_text(text: str) -> str:
    """Clean text extracted from HTML.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove common HTML entities
    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }
    
    for entity, replacement in replacements.items():
        text = text.replace(entity, replacement)
    
    return normalize_text(text)


def extract_article_number(text: str) -> Optional[str]:
    """Extract article number from text.
    
    Handles formats like:
    - "Art. 1º"
    - "Art. 5°"
    - "Artigo 10"
    
    Args:
        text: Text containing article reference
        
    Returns:
        Article number as string or None
    """
    patterns = [
        r"Art\.?\s*(\d+)[º°]?",
        r"Artigo\s+(\d+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_amendment_number(text: str) -> Optional[int]:
    """Extract amendment number from text or filename.
    
    Handles formats like:
    - "Emenda Constitucional nº 45"
    - "emc45.htm"
    - "EC 45"
    
    Args:
        text: Text containing amendment reference
        
    Returns:
        Amendment number as integer or None
    """
    patterns = [
        r"Emenda\s+Constitucional\s+n[º°]?\s*(\d+)",
        r"EC\s*(\d+)",
        r"emc(\d+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return None


def slugify(text: str) -> str:
    """Convert text to URL-safe slug.
    
    Args:
        text: Text to slugify
        
    Returns:
        URL-safe slug
    """
    # Normalize unicode and convert to ASCII
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    
    # Remove leading/trailing hyphens
    text = text.strip("-")
    
    return text

