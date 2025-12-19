"""Unit tests for HTML structure parsing."""

from bs4 import BeautifulSoup
from pathlib import Path
import re
import pytest


@pytest.fixture
def constitution_file():
    """Path to main constitution file."""
    return Path("data/raw/constitution/constituicao.htm")


def test_constitution_has_parseable_structure(constitution_file):
    """Test that constitution HTML has expected structure for parsing."""
    if not constitution_file.exists():
        pytest.skip("Constitution not downloaded yet")
    
    content = constitution_file.read_text(encoding='utf-8')
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


def test_amendment_markers_present(constitution_file):
    """Test that amendment markers are detectable."""
    if not constitution_file.exists():
        pytest.skip("Constitution not downloaded yet")
    
    content = constitution_file.read_text(encoding='utf-8')
    
    # Note: Due to encoding variations, we use flexible patterns
    # The patterns handle both proper UTF-8 and encoding quirks
    markers = {
        "incluido": r'\(Inclu.do pela Emenda Constitucional',
        "redacao": r'\(Reda..o dada pela Emenda Constitucional',
        "revogado": r'\(Revogado pela Emenda Constitucional',
        "vide": r'\(Vide Emenda Constitucional',
    }
    
    for name, pattern in markers.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        print(f"{name}: {len(matches)} occurrences")
        # At least some markers should exist (revogado might be rare)
        if name != "revogado":
            assert len(matches) > 0, f"No {name} markers found"


def test_constitution_hierarchy_elements(constitution_file):
    """Test that hierarchical elements are detectable."""
    if not constitution_file.exists():
        pytest.skip("Constitution not downloaded yet")
    
    content = constitution_file.read_text(encoding='utf-8')
    
    # Check for hierarchical elements
    # Note: Using flexible patterns due to encoding variations
    hierarchy_patterns = {
        "titulos": r'T.TULO\s+[IVXLCDM]+',
        "capitulos": r'CAP.TULO\s+[IVXLCDM]+',
        "secoes": r'Se..o\s+[IVXLCDM]+',  # Seção with encoding flexibility
        "artigos": r'Art\.\s*\d+',
        "paragrafos": r'§\s*\d+',
        "incisos": r'\b[IVXLCDM]+\s*[-–—]',
    }
    
    for name, pattern in hierarchy_patterns.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        print(f"{name}: {len(matches)} occurrences")
        assert len(matches) > 0, f"No {name} found"

